#!/usr/bin/env python3
"""第 79 天：参考实现与误差指标 —— 参考测试工具 ref_check.py

功能：
  1. Golden Reference：用 FP64 NumPy 产生参考结果；
  2. 统一误差检查函数 check_close()：绝对误差 / 相对误差 / ULP 三种指标一次算完；
  3. 不同 dtype 的阈值配置 TOLERANCES（FP32 / FP16 / BF16 / FP64）；
  4. 五组可复跑实验：MatMul 实现、换 golden 对照、0.1+0.2、大数吸收、近零残差。

运行方式：
    python3 ref_check.py

依赖：Python 3.8+，numpy（本文环境：Python 3.11.4，numpy 1.26.4）。
"""

import math

import numpy as np

# ---------------------------------------------------------------------------
# 1. 不同 dtype 的阈值配置（工具的“验收标准表”）
# ---------------------------------------------------------------------------

# np.dtype 对象 -> 阈值。rtol/atol 语义与 np.allclose 相同：
#     逐元素满足 |actual - desired| <= atol + rtol * |desired| 才算 PASS。
# max_ulp 是 ULP 指标的阈值：被测值与“参考值舍入到该 dtype 后的格子”最多差几格。
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


# ---------------------------------------------------------------------------
# 2. ULP：把浮点数轴变成单调整数轴再数格子
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# 3. 统一误差检查函数
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# 4. Golden Reference 与被测实现（贯穿例子：2x3 @ 3x2 MatMul）
# ---------------------------------------------------------------------------

A = np.array([[0.1, 0.2, 0.3],
              [1.0, 2.0, 3.0]], dtype=np.float64)
B = np.array([[0.4, 1.0],
              [0.5, 2.0],
              [0.6, 3.0]], dtype=np.float64)


def golden_matmul(A, B):
    """Golden Reference：FP64 的 NumPy matmul。"""
    return np.asarray(A, dtype=np.float64) @ np.asarray(B, dtype=np.float64)


def matmul_impl(A, B, in_dtype, acc_dtype, out_dtype):
    """被测实现：显式三重循环，输入量化/累加器/输出三处精度全部可控。"""
    Aq = quantize(A, in_dtype)
    Bq = quantize(B, in_dtype)
    M, K, N = Aq.shape[0], Aq.shape[1], Bq.shape[1]
    C = np.zeros((M, N), dtype=np.float64)
    for i in range(M):
        for j in range(N):
            acc = 0.0
            if acc_dtype == "bfloat16":
                for k in range(K):
                    acc = float(bf16(np.float32(acc + np.float32(Aq[i, k] * Bq[k, j]))))
            else:
                adt = DTYPES[acc_dtype]
                acc = adt(0)
                for k in range(K):
                    acc = adt(acc + adt(Aq[i, k] * Bq[k, j]))
            C[i, j] = acc
    return quantize(C, out_dtype)


# ---------------------------------------------------------------------------
# 5. 四组实验
# ---------------------------------------------------------------------------

def exp1_matmul():
    print("=" * 74)
    print("实验 1：MatMul 2x3 @ 3x2，五种实现 vs FP64 golden")
    print(f"  A = {A.tolist()}")
    print(f"  B = {B.tolist()}")
    g = golden_matmul(A, B)
    print(f"  golden (FP64) = {g.tolist()}")
    print("-" * 74)
    impls = [
        ("fp32输入·fp32累加·fp32出", "float32", "float32", "float32"),
        ("fp16输入·fp32累加·fp32出", "float16", "float32", "float32"),
        ("fp16输入·fp32累加·fp16出", "float16", "float32", "float16"),
        ("fp16输入·fp16累加·fp16出", "float16", "float16", "float16"),
        ("bf16输入·fp32累加·bf16出", "bfloat16", "float32", "bfloat16"),
    ]
    results = []
    for name, ind, acc, out in impls:
        C = matmul_impl(A, B, ind, acc, out)
        r = check_close(C, g, dtype_name=out, name=name)
        results.append((name, C, r))
    print("  注：ULP 距离按“输出 dtype 的刻度”数格子，fp16 一格比 fp32 一格宽，")
    print("      所以不同输出 dtype 的 ULP 数值之间不能直接比大小。")
    return results


def exp2_should_be_equal():
    print("=" * 74)
    print("实验 2：数学上应该相等 —— 0.1 + 0.2 vs 0.3，三种 dtype")
    print("-" * 74)
    print(f"  {'dtype':9s} {'actual(0.1+0.2)':>22s} {'desired(0.3)':>22s} "
          f"{'abs':>10s} {'rel':>10s} {'ulp':>5s}")
    for dt in ("float64", "float32", "float16"):
        one = quantize(0.1, dt)
        two = quantize(0.2, dt)
        act = float(quantize(one + two, dt))
        des = float(quantize(0.3, dt))
        diff = abs(act - des)
        rel = diff / abs(des)
        ulp = int(ulp_distance(np.array([act]), np.array([des]), dt)[0])
        print(f"  {dt:9s} {act!r:>24} {des!r:>24} {diff:.2e} {rel:.2e} {ulp:>5d}")
    print("  观察：FP64/FP16 各差 1 格（不是 bug，只是舍入路径不同）；")
    print("        FP32 恰好同格；abs/rel 只给出一个很小的数，")
    print("        只有 ULP 直接说出“差几格”。")


def exp1b_refined_golden():
    print("=" * 74)
    print("实验 1b：换一个 golden —— 参考实现先把输入量化到 FP16 再用 FP64 算")
    print("-" * 74)
    A16 = quantize(A, "float16")
    B16 = quantize(B, "float16")
    g16 = np.asarray(A16, dtype=np.float64) @ np.asarray(B16, dtype=np.float64)
    print(f"  golden2 = A16 @ B16 (FP64 计算) = {np.asarray(g16).tolist()}")
    C = matmul_impl(A, B, "float16", "float32", "float32")
    check_close(C, g16, dtype_name="float32",
                name="fp16输入·fp32累加 vs golden2")
    print("  同一个被测实现，实验 1 里对“全 FP64 golden”FAIL，")
    print("  现在对“FP16 输入的 golden”PASS —— 差别全在输入量化误差算谁的。")
    print("  工程含义：golden 应该对齐被测实现的输入约定，")
    print("  否则测的是“格式差异”，不是“实现是否正确”。")


def exp3_absorption():
    print("=" * 74)
    print("实验 3：格子装不下 —— FP32 计算 1e8 + 1 vs FP64 真值 100000001")
    print("-" * 74)
    act = np.float32(np.float32(1e8) + np.float32(1.0))
    des = np.float64(1e8) + 1.0
    r = check_close(np.array([act]), np.array([des]), dtype_name="float32",
                    name="1e8+1")
    print(f"  actual = {act!r}")
    print(f"  golden = {des!r}")
    print(f"  abs = 1.0 但 rel = 1e-8（通过 rtol=1e-5）；ulp = 0 ——")
    print(f"  因为 100000001 舍入到 FP32 最近的格子还是 1e8（该区间间距是 8）。")
    print(f"  结论：不是算错，是 FP32 的格子本来装不下这个数 —— rel/ulp 都放过它。")
    return r


def exp4_near_zero():
    print("=" * 74)
    print("实验 4：近零残差 —— 相对误差爆炸，atol 兜底")
    print("-" * 74)
    # 两个接近的大数相减，FP64 精确得到 1.0000000116860974e-07
    des = math.fsum([1.0000000, -0.9999999])
    act = np.float32(np.float32(1.0000000) - np.float32(0.9999999))
    print(f"  golden (fsum, FP64) = {des!r}")
    print(f"  actual (FP32 减法)  = {act!r}")
    diff = float(abs(act - des))
    rel = diff / abs(des)
    ulp = int(ulp_distance(np.array([act]), np.array([des]), "float32")[0])
    print(f"  abs = {diff:.3e}   rel = {rel:.3e}   ulp = {ulp} 格")
    print(f"  纯 rtol 检查（1e-5）: {'PASS' if rel <= 1e-5 else 'FAIL'}  <- 相对误差 19%，误报")
    print(f"  纯 atol 检查（1e-6）: {'PASS' if diff <= 1e-6 else 'FAIL'}  <- 差 1.9e-8，物理上确实小")
    print(f"  组合公式 atol+rtol*|d| = 1e-6 + 1e-13: "
          f"{'PASS' if diff <= 1e-6 + 1e-5 * abs(des) else 'FAIL'}  <- atol 兜住了近零")
    print(f"  ULP（阈值 4）: {'PASS' if ulp <= 4 else 'FAIL'}  <- 近零区刻度极细，数格子失去意义")
    print(f"  教训：可能接近 0 的结果（残差/差分），要靠 atol 兜底，别单用 rtol。")


def main():
    print(f"环境：Python {__import__('sys').version.split()[0]}，numpy {np.__version__}")
    print("阈值配置 TOLERANCES：")
    for k, v in TOLERANCES.items():
        ulp = "-" if v["max_ulp"] is None else v["max_ulp"]
        print(f"  {k:9s} rtol={v['rtol']:<8g} atol={v['atol']:<8g} max_ulp={ulp}")
    print()
    exp1_matmul()
    print()
    exp1b_refined_golden()
    print()
    exp2_should_be_equal()
    print()
    exp3_absorption()
    print()
    exp4_near_zero()


if __name__ == "__main__":
    main()
