#!/usr/bin/env python3
"""flops_bytes_lab.py —— 第 71 天主实验：计算量与访存量。

给三个算子（MatMul / Add / Relu）独立执行时算一笔「理论账」：
FLOPs（计算量）、字节数（访存量）、算术强度 AI = FLOPs / Bytes、
以及整条链独立执行时的中间 Tensor 流量。

口径声明（贯穿全文，写死在代码里）：
  1) FLOP = 一次浮点运算；FLOPs = 浮点运算总数。MatMul 的乘累加
     MAC（multiply-accumulate）= 1 次乘 + 1 次加 = 2 FLOPs。
     累加器从 0 开始，每次 += 记 1 次加法，因此 MatMul = 2·M·N·K。
  2) Relu 今天计为每个元素 1 次「比较」运算（count_compare=True 口径）。
     有的 cost model 把 Relu 记 0——分类结论不变（都是访存受限），
     但口径必须写明，否则两个模型对同一张图算出不同 FLOPs。
  3) 字节数 = 算子「必须从内存读入 + 必须写回内存」的字节数，
     即 compulsory traffic（强制流量）的理想下界：假设片上缓存完美复用，
     每个输入元素只读一次、每个输出元素只写回一次。真实硬件流量只会
     >= 这个数（naive 循环没有 tile 时远超；Day 94 Tiling 才逼近下界）。
  4) 机器平衡点 balance = 峰值算力(FLOP/s) / 峰值带宽(Byte/s)，单位 FLOP/Byte。
     算术强度 AI >= balance → 算力受限；AI < balance → 访存受限（一阶模型）。
     引用硬件：NVIDIA A100 SXM 40GB 公开 datasheet 峰值
     FP32 19.5 TFLOPS ÷ HBM2 1555 GB/s ≈ 12.54 FLOP/Byte。
     datasheet 数字、非本机实测；实测口径在 Day 107/109 建立。

运行：python3 flops_bytes_lab.py   （在 code/ 目录下）
"""

from __future__ import annotations

import math
import numpy as np

ITEMSIZE = {"fp32": 4, "fp16": 2, "bf16": 2, "int8": 1}
BALANCE_A100_FP32 = 19.5e12 / 1555e9          # FLOP/Byte（datasheet 峰值口径）

PASS = 0
FAIL = 0


def check(name: str, cond: bool) -> bool:
    global PASS, FAIL
    mark = "PASS" if cond else "FAIL"
    if cond:
        PASS += 1
    else:
        FAIL += 1
    print(f"[{mark}] {name}")
    return cond


# ============================================================
# 1. 公式：FLOPs 与访存字节
# ============================================================

def matmul_flops(M: int, K: int, N: int) -> int:
    """C(M,N) = A(M,K) @ B(K,N)：每个输出元素做 K 次乘 + K 次加。"""
    return 2 * M * N * K


def add_flops(M: int, N: int) -> int:
    """逐元素加：每个元素 1 次加法。"""
    return M * N


def relu_flops(M: int, N: int, count_compare: bool = True) -> int:
    """逐元素 Relu：本日口径每元素 1 次比较；记 0 的口径见 count_compare。"""
    return M * N if count_compare else 0


def matmul_rw(M: int, K: int, N: int, itemsize: int = 4):
    """返回 (读字节, 写字节)：读 A(M·K) + B(K·N)，写 C(M·N)。"""
    read = (M * K + K * N) * itemsize
    write = M * N * itemsize
    return read, write


def add_rw(M: int, N: int, itemsize: int = 4):
    """读两个输入各 M·N，写一个输出 M·N。"""
    read = 2 * M * N * itemsize
    write = M * N * itemsize
    return read, write


def relu_rw(M: int, N: int, itemsize: int = 4):
    """读一个输入 M·N，写一个输出 M·N。"""
    read = M * N * itemsize
    write = M * N * itemsize
    return read, write


# ============================================================
# 2. 仪器化实现对拍：真的数一遍运算次数
# ============================================================

def naive_matmul_counted(A: np.ndarray, B: np.ndarray):
    """朴素三重循环 + 运算计数器。返回 (C, 乘法数, 加法数)。"""
    M, K = A.shape
    K2, N = B.shape
    assert K == K2, "内维不匹配"
    C = np.zeros((M, N), dtype=A.dtype)
    mul = add = 0
    for i in range(M):
        for j in range(N):
            acc = A.dtype.type(0)
            for k in range(K):
                acc = acc + A[i, k] * B[k, j]
                mul += 1
                add += 1
            C[i, j] = acc
    return C, mul, add


def naive_add_counted(X: np.ndarray, Y: np.ndarray):
    out = np.empty_like(X)
    add = 0
    it = np.nditer(X, flags=["multi_index"])
    for _ in it:
        i = it.multi_index
        out[i] = X[i] + Y[i]
        add += 1
    return out, add


def naive_relu_counted(X: np.ndarray):
    out = np.empty_like(X)
    cmp_ = 0
    it = np.nditer(X, flags=["multi_index"])
    for _ in it:
        i = it.multi_index
        out[i] = X[i] if X[i] > 0 else X.dtype.type(0)
        cmp_ += 1
    return out, cmp_


# ============================================================
# 3. 链账本：MatMul → Add → Relu 独立执行
# ============================================================

def chain_ledger(M: int, K: int, N: int, itemsize: int = 4) -> dict:
    """A(M,K)@B(K,N)→C；C+D(M,N)→E；relu(E)→F。独立执行、单使用者。

    中间 Tensor = C 和 E：各被生产者写一遍 + 被消费者读一遍（2 遍）。
    """
    mm_r, mm_w = matmul_rw(M, K, N, itemsize)
    ad_r, ad_w = add_rw(M, N, itemsize)
    re_r, re_w = relu_rw(M, N, itemsize)
    ops = [
        ("matmul", matmul_flops(M, K, N), mm_r, mm_w),
        ("add",    add_flops(M, N),       ad_r, ad_w),
        ("relu",   relu_flops(M, N),      re_r, re_w),
    ]
    total_flops = sum(o[1] for o in ops)
    total_bytes = sum(o[2] + o[3] for o in ops)
    # 外部输入 A、B、D 只读一遍；最终输出 F 只写一遍
    io_bytes = (M * K + K * N + M * N + M * N) * itemsize
    # 中间 C、E：写一遍 + 读一遍
    inter_bytes = 2 * (M * N * itemsize) * 2
    return dict(ops=ops, total_flops=total_flops, total_bytes=total_bytes,
                io_bytes=io_bytes, inter_bytes=inter_bytes)


def ai(flops: float, byte_count: float) -> float:
    return flops / byte_count if byte_count else math.inf


# ============================================================
# 主流程
# ============================================================

def main() -> int:
    M, K, N = 2, 3, 2
    A = np.array([[1, 2, 3], [4, 5, 6]], dtype=np.float32)
    B = np.array([[7, 8], [9, 10], [11, 12]], dtype=np.float32)
    D = np.array([[-60, 1], [-200, 3]], dtype=np.float32)

    print("== 1. 口径卡（今天的计数约定） ==")
    print("  FLOP = 一次浮点运算；MAC = 1 乘 + 1 加 = 2 FLOPs")
    print("  MatMul FLOPs = 2·M·N·K（累加器从 0 起，每次 += 记 1 加）")
    print("  Relu 记 1 比较/元素（count_compare=True；记 0 的口径分类不变）")
    print("  字节 = compulsory 理想下界：输入只读一遍 + 输出只写一遍")
    print("  balance = 峰值算力/峰值带宽；A100 SXM 40GB FP32 datasheet：")
    print(f"            19.5 TFLOPS ÷ 1555 GB/s = {BALANCE_A100_FP32:.2f} FLOP/Byte")
    print(f"  贯穿示例：A({M},{K}) @ B({K},{N}) → C({M},{N})，fp32")

    print("\n== 2. 公式 vs 仪器化对拍（真的数一遍） ==")
    C, mul, add = naive_matmul_counted(A, B)
    C_ref = A @ B
    print(f"  朴素三重循环 MatMul：乘法 {mul} 次 + 加法 {add} 次 = {mul + add} FLOPs"
          f"（公式 2·M·N·K = {matmul_flops(M, K, N)}）")
    print(f"  数值与 numpy 对拍：{np.array_equal(C, C_ref)}，C = {C.tolist()}")
    check("2a MatMul 仪器化计数 == 2·M·N·K", mul + add == matmul_flops(M, K, N))
    check("2b 仪器化值 == numpy 值", np.array_equal(C, C_ref))

    E, addc = naive_add_counted(C, D)
    print(f"  Add：加法 {addc} 次（公式 M·N = {add_flops(M, N)}），"
          f"E = C+D = {E.tolist()}")
    check("2c Add 计数 == M·N", addc == add_flops(M, N))
    check("2d Add 值 == numpy", np.array_equal(E, C + D))

    F, cmpc = naive_relu_counted(E)
    print(f"  Relu：比较 {cmpc} 次（口径 1/元素），relu(E) = {F.tolist()}")
    check("2e Relu 计数 == M·N（口径 1/元素）", cmpc == relu_flops(M, N))
    check("2f Relu 值 == numpy", np.array_equal(F, np.maximum(E, 0)))
    check("2g Relu 记 0 口径可切换",
          relu_flops(M, N, count_compare=False) == 0)

    print("\n== 3. 字节数 vs numpy nbytes 对账 ==")
    for name, arr in [("A(2,3)", A), ("B(3,2)", B), ("C(2,2)", C),
                      ("E(2,2)", E), ("F(2,2)", F)]:
        numel = arr.size
        expect = numel * arr.itemsize
        print(f"  {name}: numel {numel} × itemsize {arr.itemsize} = "
              f"{expect} B；numpy nbytes = {arr.nbytes} B")
        check(f"3* {name} nbytes 对账", expect == arr.nbytes)

    print("\n== 4. 三算子独立账单 + 链账本（代入示例） ==")
    it = ITEMSIZE["fp32"]
    rows = [
        ("MatMul", matmul_flops(M, K, N), *matmul_rw(M, K, N, it)),
        ("Add",    add_flops(M, N),       *add_rw(M, N, it)),
        ("Relu",   relu_flops(M, N),      *relu_rw(M, N, it)),
    ]
    print("  算子    FLOPs   读(B)  写(B)  合计(B)   AI(FLOP/B)")
    for name, fl, r, w in rows:
        tb = r + w
        print(f"  {name:<7} {fl:>5}   {r:>4}   {w:>4}   {tb:>5}    {ai(fl, tb):.4g}")
    led = chain_ledger(M, K, N, it)
    print(f"  链合计：FLOPs {led['total_flops']}，字节 {led['total_bytes']} B，"
          f"链 AI = {ai(led['total_flops'], led['total_bytes']):.4g} FLOP/B")
    print(f"  拆账：外部输入+最终输出 = {led['io_bytes']} B"
          f"（A 24 + B 24 + D 16 + F 16）")
    print(f"        中间 Tensor（C、E 各写一遍+读一遍）= {led['inter_bytes']} B，"
          f"占总流量 {led['inter_bytes'] / led['total_bytes']:.1%}")
    check("4a MatMul 账单 24 FLOPs / 64 B",
          rows[0][1] == 24 and rows[0][2] + rows[0][3] == 64)
    check("4b Add 账单 4 FLOPs / 48 B（AI = 1/12）",
          rows[1][1] == 4 and rows[1][2] + rows[1][3] == 48
          and abs(ai(4, 48) - 1 / 12) < 1e-12)
    check("4c Relu 账单 4 FLOPs / 32 B（AI = 1/8）",
          rows[2][1] == 4 and rows[2][2] + rows[2][3] == 32
          and abs(ai(4, 32) - 0.125) < 1e-12)
    check("4d 链总流量 = 各算子之和 = 144 B", led["total_bytes"] == 144)
    check("4e 中间 Tensor 流量 = 2 个 × 16 B × 写+读两遍 = 64 B",
          led["inter_bytes"] == 64)
    check("4f 拆账闭合：io + intermediates == 总流量",
          led["io_bytes"] + led["inter_bytes"] == led["total_bytes"])

    print("\n== 5. Shape 扫描数据表（方阵 n×n×n，fp32） ==")
    print(f"  方阵 MatMul：FLOPs = 2n³，字节 = 12n²，AI = n/6；"
          f"阈值 = A100 FP32 {BALANCE_A100_FP32:.2f} FLOP/B")
    print("  n      FLOPs         字节(B)     AI(FLOP/B)   一阶判断")
    for n in (16, 64, 256, 1024, 4096):
        fl = matmul_flops(n, n, n)
        r, w = matmul_rw(n, n, n, 4)
        a = ai(fl, r + w)
        verdict = "算力受限" if a >= BALANCE_A100_FP32 else "访存受限"
        print(f"  {n:<6} {fl:>12,}   {r + w:>10,}   {a:>9.2f}   {verdict}")
    print("  （Add 恒为 1/12 ≈ 0.083，Relu 恒为 1/8 = 0.125，"
          "与 n 无关——逐元素算子永远访存受限）")
    n_crit = math.ceil(6 * BALANCE_A100_FP32)
    print(f"  临界规模：AI = n/6 ≥ {BALANCE_A100_FP32:.2f} 需要 n ≥ "
          f"6×{BALANCE_A100_FP32:.2f} = {6 * BALANCE_A100_FP32:.2f}，"
          f"即 n ≥ {n_crit}")
    check("5a 方阵 AI 律：AI(n) == n/6（扫描内精确成立）",
          all(abs(ai(matmul_flops(n, n, n), sum(matmul_rw(n, n, n, 4)))
                  - n / 6) < 1e-9 for n in (16, 64, 256, 1024, 4096)))
    check("5b n=64 时 AI = 10.67 < 12.54：仍访存受限",
          abs(ai(matmul_flops(64, 64, 64), sum(matmul_rw(64, 64, 64, 4)))
              - 64 / 6) < 1e-9
          and ai(matmul_flops(64, 64, 64), sum(matmul_rw(64, 64, 64, 4)))
          < BALANCE_A100_FP32)
    check("5c 临界 n = 76（ceil(6×12.54)）",
          n_crit == 76
          and ai(matmul_flops(76, 76, 76), sum(matmul_rw(76, 76, 76, 4)))
          >= BALANCE_A100_FP32
          and ai(matmul_flops(75, 75, 75), sum(matmul_rw(75, 75, 75, 4)))
          < BALANCE_A100_FP32)
    check("5d 逐元素算子 AI 与 shape 无关",
          ai(add_flops(1024, 1024), sum(add_rw(1024, 1024, 4))) == 1 / 12
          and ai(add_flops(4, 6), sum(add_rw(4, 6, 4))) == 1 / 12)

    print("\n== 6. 改一个参数再观察：dtype fp32 → fp16 / int8 ==")
    print("  dtype  itemsize  链总字节(B)  MatMul AI  Add AI   Relu AI")
    for dt in ("fp32", "fp16", "bf16", "int8"):
        isz = ITEMSIZE[dt]
        l2 = chain_ledger(M, K, N, isz)
        a_mm = ai(matmul_flops(M, K, N), sum(matmul_rw(M, K, N, isz)))
        a_ad = ai(add_flops(M, N), sum(add_rw(M, N, isz)))
        a_re = ai(relu_flops(M, N), sum(relu_rw(M, N, isz)))
        print(f"  {dt:<6} {isz:>8}  {l2['total_bytes']:>10}  "
              f"{a_mm:>9.4g}  {a_ad:>6.4g}  {a_re:>7.4g}")
    print("  （FLOPs 一律不变：24+4+4 = 32；字节随 itemsize 线性缩放，AI 反比）")
    l32 = chain_ledger(M, K, N, 4)
    l16 = chain_ledger(M, K, N, 2)
    l8 = chain_ledger(M, K, N, 1)
    check("6a fp16 链总字节 = fp32 的一半（72 B）",
          l16["total_bytes"] * 2 == l32["total_bytes"] == 144
          and l16["total_bytes"] == 72)
    check("6b FLOPs 不随 dtype 变化",
          l8["total_flops"] == l16["total_flops"] == l32["total_flops"] == 32)
    check("6c fp16 MatMul AI = 2× fp32 AI（0.75 vs 0.375）",
          abs(ai(matmul_flops(M, K, N), sum(matmul_rw(M, K, N, 2))) - 0.75)
          < 1e-12)
    check("6d int8 链总字节 = 36 B", l8["total_bytes"] == 36)

    print(f"\n== 汇总：{PASS} PASS / {FAIL} FAIL ==")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
