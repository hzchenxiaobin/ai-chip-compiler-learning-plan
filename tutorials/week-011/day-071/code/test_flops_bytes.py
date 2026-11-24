#!/usr/bin/env python3
"""test_flops_bytes.py —— 第 71 天独立验收测试。

与主实验（flops_bytes_lab.py）独立：不同随机种子、随机 Shape、
性质测试为主，防止「公式只对贯穿示例成立」。

段划分：
  A  公式 vs 仪器化计数（随机 Shape，25 组，含 M=1/N=1/K=1 边界）
  B  字节公式 vs numpy nbytes（随机 Shape）
  C  链账本一致性（逐算子之和 == 总账；拆账闭合）
  D  算术强度性质（方阵 n/6 律、GEMV 上界、AI 随 K 单调有界）
  E  dtype 缩放（字节 ∝ itemsize，FLOPs 不变，AI 反比）
  F  临界规模公式（n_crit = ceil(6·balance) 及越界验证）

运行：python3 test_flops_bytes.py   （在 code/ 目录下）
"""

from __future__ import annotations

import math
import random

import numpy as np

from flops_bytes_lab import (
    BALANCE_A100_FP32, ITEMSIZE, add_flops, add_rw, ai, chain_ledger,
    matmul_flops, matmul_rw, naive_add_counted, naive_matmul_counted,
    naive_relu_counted, relu_flops, relu_rw,
)

PASS = 0
FAIL = 0


def check(name: str, cond: bool) -> bool:
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
    print(f"[{'PASS' if cond else 'FAIL'}] {name}")
    return cond


def main() -> int:
    rng = random.Random(711)

    print("== A. 公式 vs 仪器化计数（随机 Shape，25 组） ==")
    cases = [(1, 1, 1), (1, 5, 1), (5, 1, 3), (3, 7, 1)]
    while len(cases) < 25:
        cases.append((rng.randint(1, 8), rng.randint(1, 8), rng.randint(1, 8)))
    ok_all = ok_val = True
    for (M, K, N) in cases:
        A = np.arange(M * K, dtype=np.float32).reshape(M, K)
        B = np.arange(K * N, dtype=np.float32).reshape(K, N)
        C, mul, add = naive_matmul_counted(A, B)
        if mul + add != matmul_flops(M, K, N):
            ok_all = False
        if not np.allclose(C, A @ B):
            ok_val = False
    check(f"A1 25 组随机 MatMul 计数 == 2·M·N·K（含 M=1/N=1/K=1）", ok_all)
    check("A2 25 组随机 MatMul 数值 == numpy", ok_val)

    X = np.random.default_rng(1).standard_normal((5, 7)).astype(np.float32)
    Y = np.random.default_rng(2).standard_normal((5, 7)).astype(np.float32)
    _, addc = naive_add_counted(X, Y)
    _, cmpc = naive_relu_counted(X)
    check("A3 Add 计数 == M·N（5×7 → 35）", addc == 35 == add_flops(5, 7))
    check("A4 Relu 计数 == M·N（口径 1/元素）", cmpc == 35 == relu_flops(5, 7))
    check("A5 Relu 记 0 口径恒为 0",
          relu_flops(64, 64, count_compare=False) == 0)

    print("== B. 字节公式 vs numpy nbytes ==")
    ok = True
    for shape in [(1,), (1, 1024), (64, 64), (3, 5, 7), (2, 3), (256, 256)]:
        arr = np.zeros(shape, dtype=np.float32)
        if arr.size * arr.itemsize != arr.nbytes:
            ok = False
    check("B1 numel×itemsize == ndarray.nbytes（6 组 Shape）", ok)
    M, K, N = 64, 128, 32
    r, w = matmul_rw(M, K, N, 4)
    ok = (r == (np.zeros((M, K), dtype=np.float32).nbytes
                + np.zeros((K, N), dtype=np.float32).nbytes)
          and w == np.zeros((M, N), dtype=np.float32).nbytes)
    check("B2 MatMul 读写字节 == 对应 ndarray.nbytes 之和", ok)
    r2, w2 = add_rw(M, N, 4)
    check("B3 Add 读 == 两个输入 nbytes，写 == 输出 nbytes",
          r2 == 2 * np.zeros((M, N), dtype=np.float32).nbytes
          and w2 == np.zeros((M, N), dtype=np.float32).nbytes)

    print("== C. 链账本一致性 ==")
    ok_sum = ok_close = ok_inter = True
    for _ in range(20):
        M = rng.randint(1, 64)
        K = rng.randint(1, 64)
        N = rng.randint(1, 64)
        led = chain_ledger(M, K, N, 4)
        if led["total_bytes"] != sum(o[2] + o[3] for o in led["ops"]):
            ok_sum = False
        if led["io_bytes"] + led["inter_bytes"] != led["total_bytes"]:
            ok_close = False
        if led["inter_bytes"] != 2 * (M * N * 4) * 2:
            ok_inter = False
    check("C1 20 组随机链：总流量 == 逐算子读+写之和", ok_sum)
    check("C2 20 组随机链：io + 中间 == 总（拆账闭合）", ok_close)
    check("C3 20 组随机链：中间流量 == 2 个中间 × 字节 × 写+读两遍", ok_inter)
    led = chain_ledger(2, 3, 2, 4)
    check("C4 贯穿示例回归：144 B / 中间 64 B / io 80 B",
          led["total_bytes"] == 144 and led["inter_bytes"] == 64
          and led["io_bytes"] == 80)

    print("== D. 算术强度性质 ==")
    check("D1 方阵 AI = n/6（n = 3/17/64/257/1000）",
          all(abs(ai(matmul_flops(n, n, n), sum(matmul_rw(n, n, n, 4)))
                  - n / 6) < 1e-9 for n in (3, 17, 64, 257, 1000)))
    gemv_ai = ai(matmul_flops(1, 1024, 1024), sum(matmul_rw(1, 1024, 1024, 4)))
    check(f"D2 GEMV M=1,K=N=1024：AI = {gemv_ai:.4g} < 0.51（访存受限）",
          gemv_ai < 0.51 and abs(gemv_ai - 2 * 1024 * 1024
                                 / (4 * (1024 + 1024 * 1024 + 1024))) < 1e-9)
    a64 = ai(matmul_flops(8, 8, 64), sum(matmul_rw(8, 8, 64, 4)))
    a128 = ai(matmul_flops(8, 8, 128), sum(matmul_rw(8, 8, 128, 4)))
    a512 = ai(matmul_flops(8, 8, 512), sum(matmul_rw(8, 8, 512, 4)))
    limit = 8 * 8 / (2 * (8 + 8))
    check(f"D3 AI 随 K 单调升且有上界 M·N/(2(M+N)) = {limit:g}"
          f"（实测 {a64:.4g} < {a128:.4g} < {a512:.4g} < {limit:g}）",
          a64 < a128 < a512 < limit)
    check("D4 逐元素 AI 与 Shape 无关（Add 1/12，Relu 1/8）",
          ai(add_flops(3, 5), sum(add_rw(3, 5, 4))) == 1 / 12
          and ai(relu_flops(1024, 1), sum(relu_rw(1024, 1, 4))) == 1 / 8)

    print("== E. dtype 缩放 ==")
    ok_byte = ok_flop = ok_ai = True
    base = chain_ledger(16, 16, 16, 4)
    for dt in ("fp16", "bf16", "int8"):
        isz = ITEMSIZE[dt]
        l2 = chain_ledger(16, 16, 16, isz)
        if l2["total_bytes"] * 4 != base["total_bytes"] * isz:
            ok_byte = False
        if l2["total_flops"] != base["total_flops"]:
            ok_flop = False
        if abs(ai(matmul_flops(16, 16, 16), sum(matmul_rw(16, 16, 16, isz)))
               - 16 / 6 * (4 / isz)) > 1e-9:
            ok_ai = False
    check("E1 链字节 ∝ itemsize（fp16/bf16/int8 × 3 组）", ok_byte)
    check("E2 链 FLOPs 与 dtype 无关", ok_flop)
    check("E3 MatMul AI ∝ 1/itemsize（fp16 AI = 2× fp32）", ok_ai)
    check("E4 贯穿示例 fp16 = 72 B、int8 = 36 B",
          chain_ledger(2, 3, 2, 2)["total_bytes"] == 72
          and chain_ledger(2, 3, 2, 1)["total_bytes"] == 36)

    print("== F. 临界规模公式 ==")
    for balance in (1.0, 4.0, BALANCE_A100_FP32):
        n_crit = math.ceil(6 * balance)
        if not (ai(matmul_flops(n_crit, n_crit, n_crit),
                   sum(matmul_rw(n_crit, n_crit, n_crit, 4))) >= balance
                and ai(matmul_flops(n_crit - 1, n_crit - 1, n_crit - 1),
                       sum(matmul_rw(n_crit - 1, n_crit - 1, n_crit - 1, 4)))
                < balance):
            check(f"F* balance={balance:.2f} 临界律失败", False)
    check(f"F1 三个阈值（1/4/{BALANCE_A100_FP32:.2f}）均满足"
          f" AI(n_crit) ≥ 阈值 > AI(n_crit-1)", True)
    check("F2 A100 FP32 口径 n_crit = 76",
          math.ceil(6 * BALANCE_A100_FP32) == 76)
    check("F3 阈值口径标注：A100 数字为 datasheet 峰值，非实测",
          abs(BALANCE_A100_FP32 - 19.5e12 / 1555e9) < 1e-9)

    print(f"\n== 汇总：{PASS} PASS / {FAIL} FAIL ==")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
