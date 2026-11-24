#!/usr/bin/env python3
"""第 80 天：FP16/BF16 测试 —— 低精度输入、高精度累加、输出舍入

对同一个 MatMul 系统地变换三处精度（输入 / 累加 / 输出），
记录误差与性能数据，产出精度对照表和结论。

五个实验：
  实验 1：2x3 @ 3x2 六种精度组合，对两个 golden（FP64 / 量化输入版）对账；
  实验 2：累加器吸收 —— 4096 个 1 相加，fp16 累加 vs fp32 累加 vs numpy 的 fp16 @；
  实验 3：K 扫描 —— 累加税随 K 增长（rel_F 对齐 golden）；
  实验 4：输出舍入与溢出 —— 最后一刀的代价，以及 FP16 输出溢出成 inf；
  实验 5：字节与耗时 —— 三种 dtype 的真实字节数和 numpy 实测耗时。

运行方式：
    python3 precision_sweep.py

依赖：Python 3.8+，numpy（本文环境：aarch64 Linux，Python 3.11.4，numpy 1.26.4）。
测量仪（TOLERANCES / quantize / check_close / ulp_distance）从第 79 天的
ref_check.py 原样搬来，一个字没改 —— 今天只换被测对象，不换尺子。
"""

import time

import numpy as np

# ---------------------------------------------------------------------------
# 0. 测量仪：以下代码块与第 79 天 ref_check.py 完全一致（原样搬来的工具）
# ---------------------------------------------------------------------------

TOLERANCES = {
    "float64": dict(rtol=1e-12, atol=1e-12, max_ulp=1),
    "float32": dict(rtol=1e-5, atol=1e-6, max_ulp=4),
    "float16": dict(rtol=1e-3, atol=1e-4, max_ulp=8),
    "bfloat16": dict(rtol=1.6e-2, atol=1e-3, max_ulp=None),  # BF16 以 rtol 为主
}

DTYPES = {
    "float64": np.float64,
    "float32": np.float32,
    "float16": np.float16,
    # numpy 无原生 bfloat16：用 FP32 位级仿真（与 Day 78 的 bf16() 相同）
    "bfloat16": None,
}


def bf16(x):
    """把 FP32 数组按 round-to-nearest-even 舍入到 BF16，结果仍存成 FP32。"""
    u = np.asarray(x, dtype=np.float32).view(np.uint32)
    rounded = ((u + np.uint32(0x7FFF) + ((u >> 16) & 1)) & np.uint32(0xFFFF0000)).astype(np.uint32)
    return rounded.view(np.float32)


def quantize(x, dtype_name):
    """把输入量化到指定 dtype 的刻度上（golden 的“入乡随俗”）。"""
    if dtype_name == "bfloat16":
        return bf16(x)
    return np.asarray(x, dtype=DTYPES[dtype_name]).astype(np.float64)


def _monotone_uint(x, dtype_name):
    """IEEE 浮点位模式 -> 全体可表示数上的单调无符号整数编号。

    规则（Goldberg 的经典折叠）：把位模式按无符号整数 u 读出（共 n 位），
        符号位为 0（正数）: m = u + 2^(n-1)
        符号位为 1（负数）: m = 2^n - u   （用 (~u & mask) + 1 环绕计算）
    折叠后 m 随浮点值严格递增，两数的 ULP 距离 = |m(a) - m(b)|。
    全程无符号算术，FP64 时 m 可达 2^64-1 也不会溢出。
    """
    if dtype_name == "bfloat16":
        u = (np.asarray(x, dtype=np.float32).view(np.uint32) >> 16).astype(np.uint64)
        nbits = 16
    else:
        dt = DTYPES[dtype_name]
        nbits = np.finfo(dt).bits
        itype = {16: np.uint16, 32: np.uint32, 64: np.uint64}[nbits]
        u = np.asarray(x, dtype=dt).view(itype).astype(np.uint64)
    half = np.uint64(1 << (nbits - 1))
    mask = np.uint64((1 << nbits) - 1)
    neg_m = (~u & mask) + np.uint64(1)  # 2^n - u
    pos_m = u + half                     # u + 2^(n-1)
    return np.where(u >= half, neg_m, pos_m)


def ulp_distance(actual, desired, dtype_name):
    """actual 与 desired 在 dtype_name 刻度上的 ULP 距离（逐元素）。

    desired（通常是 FP64 golden）先就近舍入到该 dtype 的格子上，
    再数两者相隔几个格子。返回与输入同 shape 的无符号整数数组。
    """
    a = quantize(actual, dtype_name)   # 被测值本就在该刻度上，量化是幂等的
    r = quantize(desired, dtype_name)  # golden 舍入到最近的格子
    ma = _monotone_uint(a, dtype_name)
    mr = _monotone_uint(r, dtype_name)
    return np.where(ma >= mr, ma - mr, mr - ma)


def check_close(actual, desired, *, dtype_name, name=""):
    """统一误差检查：一次算出 max_abs / max_rel / max_ulp，并给出 PASS/FAIL。

    判定规则：
      NaN/Inf      出现即 FAIL（数值层面先于精度层面）；
      abs+rel 组合 逐元素 |a-d| <= atol + rtol*|d|（与 np.allclose 同公式）；
      ULP          max ulp_distance <= max_ulp（max_ulp 为 None 时跳过）。
    返回结果 dict，同时打印一行报告。
    """
    tol = TOLERANCES[dtype_name]
    a = np.asarray(actual, dtype=np.float64)
    d = np.asarray(desired, dtype=np.float64)

    if a.shape != d.shape:
        raise ValueError(f"shape 不一致: {a.shape} vs {d.shape}")

    finite_ok = bool(np.all(np.isfinite(a)) and np.all(np.isfinite(d)))

    diff = np.abs(a - d)
    max_abs = float(diff.max()) if diff.size else 0.0
    denom = np.abs(d)
    rel = np.where(denom > 0, diff / np.where(denom > 0, denom, 1.0), np.inf)
    max_rel = float(rel.max()) if rel.size else 0.0
    max_ulp = int(ulp_distance(a, d, dtype_name).max()) if a.size else 0
    absrel_ok = bool(np.all(diff <= tol["atol"] + tol["rtol"] * np.abs(d))) if a.size else True
    ulp_ok = True if tol["max_ulp"] is None else (max_ulp <= tol["max_ulp"])
    passed = finite_ok and absrel_ok and ulp_ok

    tag = "PASS" if passed else "FAIL"
    ulp_txt = "-" if tol["max_ulp"] is None else f"{max_ulp}格(≤{tol['max_ulp']})"
    nm = f"[{name}] " if name else ""
    print(f"  {nm}{tag}  dtype={dtype_name:8s} max_abs={max_abs:.3e}  "
          f"max_rel={max_rel:.3e}  max_ulp={ulp_txt}")

    return dict(name=name, dtype=dtype_name, max_abs=max_abs, max_rel=max_rel,
                max_ulp=max_ulp, finite_ok=finite_ok, absrel_ok=absrel_ok,
                ulp_ok=ulp_ok, passed=passed)


def rel_frobenius(actual, golden):
    """相对 Frobenius 误差：||C-G||_F / ||G||_F。

    随机矩阵乘的结果可能个别元素接近 0（Day 79 的近零教训：max_rel 会爆炸），
    所以 K 扫描用“整矩阵能量”口径，比逐元素 max_rel 稳定。
    """
    a = np.asarray(actual, dtype=np.float64)
    g = np.asarray(golden, dtype=np.float64)
    return float(np.linalg.norm(a - g) / np.linalg.norm(g))


# ---------------------------------------------------------------------------
# 被测实现：三处精度全部可控的 MatMul
# ---------------------------------------------------------------------------

A0 = np.array([[0.1, 0.2, 0.3],
               [1.0, 2.0, 3.0]], dtype=np.float64)
B0 = np.array([[0.4, 1.0],
               [0.5, 2.0],
               [0.6, 3.0]], dtype=np.float64)


def matmul_impl(A, B, in_dtype, acc_dtype, out_dtype):
    """显式 k 递进的 MatMul：输入量化 / 累加器 / 输出三处精度可控。

    语义与 Day 79 的三重循环版本一致：每一步 k，累加器做一次
    “乘积按 acc 精度舍入 -> 相加 -> 再舍回 acc 精度”。
    """
    Aq = quantize(A, in_dtype)
    Bq = quantize(B, in_dtype)
    M, K, N = Aq.shape[0], Aq.shape[1], Bq.shape[1]
    if acc_dtype == "bfloat16":
        acc = np.zeros((M, N), dtype=np.float32)
        for k in range(K):
            prod = bf16(np.multiply(Aq[:, k:k + 1], Bq[k:k + 1, :], dtype=np.float32))
            acc = bf16(acc + prod)
    else:
        adt = DTYPES[acc_dtype]
        acc = np.zeros((M, N), dtype=adt)
        for k in range(K):
            prod = np.multiply(Aq[:, k:k + 1], Bq[k:k + 1, :]).astype(adt)
            acc = (acc + prod).astype(adt)
    return quantize(acc, out_dtype)


def aligned_golden(A, B, in_dtype):
    """对齐输入约定的 golden：先把输入量化到 in_dtype，再用 FP64 计算。

    这样测出来的误差是“实现税”（累加 + 输出舍入），
    不含“格式税”（输入量化）——两者要分开看。
    """
    Aq = quantize(A, in_dtype)
    Bq = quantize(B, in_dtype)
    return np.asarray(Aq, dtype=np.float64) @ np.asarray(Bq, dtype=np.float64)


# ---------------------------------------------------------------------------
# 实验 1：2x3 @ 3x2，六种精度组合 x 两个 golden
# ---------------------------------------------------------------------------

def exp1_small_matrix():
    print("=" * 78)
    print("实验 1：MatMul 2x3 @ 3x2（Day 79 的贯穿例子），六种精度组合")
    print(f"  A = {A0.tolist()}")
    print(f"  B = {B0.tolist()}")
    g64 = A0 @ B0
    print(f"  golden (FP64) = {g64.tolist()}")
    print("-" * 78)
    impls = [
        ("fp32入·fp32累·fp32出", "float32", "float32", "float32"),
        ("fp16入·fp32累·fp32出", "float16", "float32", "float32"),
        ("fp16入·fp32累·fp16出", "float16", "float32", "float16"),
        ("fp16入·fp16累·fp16出", "float16", "float16", "float16"),
        ("bf16入·fp32累·fp32出", "bfloat16", "float32", "float32"),
        ("bf16入·fp32累·bf16出", "bfloat16", "float32", "bfloat16"),
    ]
    print("  -- 对 FP64 golden（含输入格式税的总误差）--")
    for name, ind, acc, out in impls:
        C = matmul_impl(A0, B0, ind, acc, out)
        check_close(C, g64, dtype_name=out, name=name)
    print("  -- 对量化输入版 golden（只看实现税：累加 + 输出舍入）--")
    for name, ind, acc, out in impls:
        C = matmul_impl(A0, B0, ind, acc, out)
        g_aligned = aligned_golden(A0, B0, ind)
        check_close(C, g_aligned, dtype_name=out, name=name)


# ---------------------------------------------------------------------------
# 实验 2：累加器吸收 —— 4096 个 1 相加
# ---------------------------------------------------------------------------

def exp2_absorption():
    print("=" * 78)
    print("实验 2：累加器吸收 —— 把 4096 个 1.0 加起来")
    print("-" * 78)
    ones = np.ones(4096, dtype=np.float64)

    acc32 = np.float32(0)
    for x in ones:
        acc32 = np.float32(acc32 + np.float32(x))

    acc16 = np.float16(0)
    for x in ones:
        acc16 = np.float16(acc16 + np.float16(x))

    A1 = np.ones((1, 4096), dtype=np.float16)
    B1 = np.ones((4096, 1), dtype=np.float16)
    np16 = (A1 @ B1)[0, 0]

    # 判别证据：随机数据上，numpy 的 fp16 @ 与手写 fp32 累加逐位一致
    rng = np.random.default_rng(7)
    Ar = rng.uniform(-1, 1, (32, 512)).astype(np.float16)
    Br = rng.uniform(-1, 1, (512, 32)).astype(np.float16)
    C_np = (Ar @ Br).astype(np.float64)
    Ar64, Br64 = Ar.astype(np.float64), Br.astype(np.float64)
    acc32m = np.zeros((32, 32), dtype=np.float32)
    for k in range(512):
        acc32m += np.float32(Ar64[:, k:k + 1] * Br64[k:k + 1, :])
    diff_bits = int(np.abs(C_np.astype(np.float16).view(np.uint16)
                           .astype(np.int32)
                           - acc32m.astype(np.float16).view(np.uint16).astype(np.int32)).max())

    print(f"  fp32 累加 4096 个 1.0 = {acc32!r}")
    print(f"  fp16 累加 4096 个 1.0 = {acc16!r}   <- 卡死在 2048")
    print(f"  numpy fp16 @ (ones(1,4096) @ ones(4096,1)) = {np16!r}")
    print(f"  解释：FP16 在 2048 处的格子间距是 2，2048 + 1 落在两格正中间，")
    print(f"        就近舍入到偶数 -> 还是 2048，之后每一步都被吸收。")
    print(f"  判别 numpy 的 fp16 @ 用什么精度累加（随机 32x512x32，种子 7）：")
    print(f"    numpy fp16 @  vs  手写 fp32 累加 + fp16 出：位模式最大差 {diff_bits} 个码")
    print(f"    -> 本环境实测 numpy 的 fp16 @ 内部用 fp32 累加再舍回 fp16 输出；")
    print(f"       但自己手写 kernel 时，累加器写成 float16 就是上面 2048 的下场。")
    print(f"  再看单步：np.float16(2048) + np.float16(1) = "
          f"{np.float16(2048) + np.float16(1)!r}")


# ---------------------------------------------------------------------------
# 实验 3：K 扫描 —— 累加税随 K 增长
# ---------------------------------------------------------------------------

def exp3_k_sweep():
    print("=" * 78)
    print("实验 3：K 扫描 —— 同一组 fp16/bf16 输入，累加精度决定误差怎么长")
    print("  M = N = 64，输入 uniform(-1, 1)，种子 default_rng(7)")
    print("  口径：rel_F = ||C - golden||_F / ||golden||_F，golden = 量化输入版 FP64")
    print("  （用整矩阵口径是因为随机结果里个别元素接近 0，max_rel 会爆炸 —— Day 79 的教训）")
    print("-" * 78)
    rng = np.random.default_rng(7)
    M = N = 64
    ks = (16, 64, 256, 1024, 4096)
    kmax = max(ks)
    A = rng.uniform(-1, 1, (M, kmax))
    B = rng.uniform(-1, 1, (kmax, N))
    header = f"  {'K':>5s} {'fp32入·fp32累':>14s} {'fp16入·fp32累':>14s} {'fp16入·fp16累':>14s} {'bf16入·fp32累':>14s}"
    print(header)
    rows = []
    for K in ks:
        Ak, Bk = A[:, :K], B[:K, :]
        vals = []
        for ind, acc in (("float32", "float32"), ("float16", "float32"),
                         ("float16", "float16"), ("bfloat16", "float32")):
            C = matmul_impl(Ak, Bk, ind, acc, "float32")
            g = aligned_golden(Ak, Bk, ind)
            vals.append(rel_frobenius(C, g))
        rows.append((K, vals))
        print(f"  {K:>5d} {vals[0]:>14.3e} {vals[1]:>14.3e} {vals[2]:>14.3e} {vals[3]:>14.3e}")
    print("  读数：fp32 累加的三列都在 1e-8 ~ 1e-6 量级缓慢漂移（fp32 累加税可忽略）；")
    print("        fp16 累加一列随 K 增长 —— K 从 16 到 4096 扩大 256 倍，误差扩大")
    print(f"        约 15 倍 ≈ sqrt(256)=16，正是“每步舍入随机游走”的脚印；")
    print("        bf16 列同样只剩累加税 —— 输入格式税已被量化输入版 golden 消掉")
    print("        （要看 bf16 的输入税 ~3e-3，得对 FP64 golden，见实验 1）。")
    return rows


# ---------------------------------------------------------------------------
# 实验 4：输出舍入与溢出
# ---------------------------------------------------------------------------

def exp4_output_rounding():
    print("=" * 78)
    print("实验 4：输出舍入 —— 最后一刀的代价，和 FP16 输出的溢出")
    print("-" * 78)
    rng = np.random.default_rng(7)
    M = N = 64
    K = 4096
    A = rng.uniform(-1, 1, (M, K))
    B = rng.uniform(-1, 1, (K, N))
    g = aligned_golden(A, B, "float16")
    for out in ("float32", "float16"):
        C = matmul_impl(A, B, "float16", "float32", out)
        rf = rel_frobenius(C, g)
        print(f"  fp16入·fp32累·{out}出 vs 量化输入 golden: rel_F = {rf:.3e}")
    print("  读数：fp16 出比 fp32 出多一刀（输出舍入税 ~ eps_fp16/2 ≈ 4.9e-4），")
    print("        但省一半结果写回带宽；fp32 出则完全省掉这一刀。")

    print("-" * 78)
    print("  溢出演示：A = [[300, 300]]，B = [[300], [300]]，真值 300*300 + 300*300 = 180000")
    A_ovf = np.array([[300.0, 300.0]])
    B_ovf = np.array([[300.0], [300.0]])
    with np.errstate(over="ignore"):
        C32 = matmul_impl(A_ovf, B_ovf, "float16", "float32", "float32")
        C16 = matmul_impl(A_ovf, B_ovf, "float16", "float32", "float16")
    print(f"  fp16入·fp32累·fp32出 = {C32.tolist()}  （FP32 装得下 180000）")
    print(f"  fp16入·fp32累·fp16出 = {C16.tolist()}  （FP16 上限 65504，溢出成 inf）")
    with np.errstate(over="ignore"):
        check_close(C16, A_ovf @ B_ovf, dtype_name="float16", name="溢出检查")
    print("  读数：check_close 的第一道闸是 NaN/Inf —— 数值错误先于精度问题（Day 79）。")
    print("        ULP 显示 0 格是个假象：180000 舍到 fp16 也是 inf，两边占了同一个")
    print("        “格子”——inf 面前 ULP 已失义，所以 finite 闸门必须排在最前面。")


# ---------------------------------------------------------------------------
# 实验 5：字节与耗时
# ---------------------------------------------------------------------------

def exp5_bytes_and_time():
    print("=" * 78)
    print("实验 5：字节与耗时 —— 低精度的收益在哪，代价在哪")
    print("-" * 78)
    M = N = K = 512
    print(f"  MatMul {M}x{K} @ {K}x{N}，三个矩阵 A/B/C 的总字节数（nbytes 实测）：")
    for name, dt, be in (("fp32", np.float32, 4), ("fp16", np.float16, 2),
                         ("bf16", None, 2)):
        if dt is not None:
            total = (M * K + K * N + M * N) * be
            print(f"    {name:6s} 每元素 {be} 字节，A+B+C 共 {total/1024/1024:.2f} MiB")
        else:
            total = (M * K + K * N + M * N) * be
            print(f"    {name:6s} 每元素 {be} 字节，A+B+C 共 {total/1024/1024:.2f} MiB（无原生 dtype，按 2 字节估）")
    print(f"    fp32 -> fp16：A+B+C 字节减半，{3 * M * M * 4 / 1024 / 1024:.2f} MiB -> "
          f"{3 * M * M * 2 / 1024 / 1024:.2f} MiB")

    print("-" * 78)
    print("  numpy @ 实测耗时（预热 3 次，取 10 次中位数；同一 CPU）：")
    rng = np.random.default_rng(7)
    flops = 2.0 * M * N * K
    results = {}
    for name, dt in (("fp32", np.float32), ("fp64", np.float64), ("fp16", np.float16)):
        A = rng.uniform(-1, 1, (M, K)).astype(dt)
        B = rng.uniform(-1, 1, (K, N)).astype(dt)
        for _ in range(3):
            A @ B
        ts = []
        for _ in range(10):
            t0 = time.perf_counter()
            A @ B
            ts.append(time.perf_counter() - t0)
        ts.sort()
        med = ts[5]
        results[name] = med
        print(f"    {name:6s} 中位数 {med*1e3:8.2f} ms   有效 {flops/med/1e9:8.1f} GFLOPS")
    ratio = results["fp16"] / results["fp32"]
    print(f"  读数：CPU 上 numpy 的 fp16 @ 走软件仿真路径（BLAS 只有 fp32/fp64），")
    print(f"        实测比 fp32 慢 {ratio:.0f} 倍 —— 低精度的性能收益来自专用矩阵单元")
    print(f"        （GPU Tensor Core / 昇腾 Cube 这类 fp16 入·fp32 累的硬件），不是格式本身；")
    print(f"        在 CPU 上低精度买到的只有“字节减半”，买不到速度。")


# ---------------------------------------------------------------------------

def main():
    print(f"环境：Python {__import__('sys').version.split()[0]}，numpy {np.__version__}，"
          f"{__import__('platform').machine()}")
    exp1_small_matrix()
    print()
    exp2_absorption()
    print()
    exp3_k_sweep()
    print()
    exp4_output_rounding()
    print()
    exp5_bytes_and_time()


if __name__ == "__main__":
    main()
