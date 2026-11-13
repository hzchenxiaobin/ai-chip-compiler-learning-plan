#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tilegen.py —— 第 95 天：把"尾部处理"写成真正的边界 IR（MLIR scf 方言）。

用法：  python3 tilegen.py 5 7 3 2 4 2 [--out ir]
输出（写入 --out 目录，默认 ir/）：
  matmul_min_bounds.mlir            min 钳制版（策略 2 的 IR 形态，MLIR/linalg 同款思路）
  matmul_mask.mlir                  掩码版（策略 1 的 IR 形态，scf.if 逐元素判定）
  matmul_danger.mlir                无保护版（能通过解析，但运行期越界——教训素材）
  matmul_min_bounds_divisible.mlir  6x8x4 整除配置的 min 钳制版（min 仍在，恒不生效）

生成的 IR 用上游 mlir-opt 做解析/round-trip 验证（见 run_all.sh）。
"""

import argparse
import os
import sys


def ceil_div(a, b):
    return (a + b - 1) // b


def gen(M, N, K, TM, TN, TK, variant):
    """按 variant 生成一个 func.func @tiled_matmul 的 MLIR 文本。"""
    tA = f"memref<{M}x{K}xf32>"
    tB = f"memref<{K}x{N}xf32>"
    tC = f"memref<{M}x{N}xf32>"
    lines = []

    def add(indent, text):
        lines.append("  " * indent + text)

    ntiles = (ceil_div(M, TM) * ceil_div(N, TN) * ceil_div(K, TK))
    add(0, f"// 由 tilegen.py 生成：M={M} N={N} K={K}, tile {TM}x{TN}x{TK}, "
           f"variant={variant}")
    add(0, f"// tile 网格：{ceil_div(M, TM)} x {ceil_div(N, TN)} x "
           f"{ceil_div(K, TK)} = {ntiles} 个 tile；"
           f"有效计算 M*N*K = {M * N * K} 步")
    add(0, "module {")
    add(1, f"func.func @tiled_matmul(%argA: {tA}, %argB: {tB}, %argC: {tC}) {{")
    for name, val in [("c0", 0), ("c1", 1), ("cM", M), ("cN", N), ("cK", K),
                      ("cTM", TM), ("cTN", TN), ("cTK", TK)]:
        add(2, f"%{name} = arith.constant {val} : index")
    add(2, "%cf0 = arith.constant 0.0 : f32")

    add(2, "// 第 0 步：清零 C。这个循环用精确边界 0..M / 0..N，不需要保护，")
    add(2, "// 因为它不受 tile 网格约束——保护只加在会越界的地方。")
    add(2, "scf.for %zi = %c0 to %cM step %c1 {")
    add(3, "scf.for %zj = %c0 to %cN step %c1 {")
    add(4, f"memref.store %cf0, %argC[%zi, %zj] : {tC}")
    add(3, "}")
    add(2, "}")

    notes = {
        "min_bounds": "尾部 tile 的点循环上界被 min(tile起点+Tile, 维度) 钳制，"
                      "自动变短：静态 3 条 min，动态执行 3+6+12=21 次",
        "mask": "点循环按完整 tile 宽度展开，循环体用 scf.if 逐元素判定；"
                "掩码不改变循环次数，只改变做不做",
        "danger": "没有任何保护：IR 语法完全合法、能通过 mlir-opt 解析，"
                  "但运行时索引会越过 M/N/K——合法 ≠ 访存安全",
    }
    if variant == "min_bounds" and M % TM == 0 and N % TN == 0 and K % TK == 0:
        note = "min 仍然存在，但所有 tile 都是整 tile，min 永远不生效"
    else:
        note = notes[variant]
    add(2, f"// 第 1 步：tile 循环（外层）。{note}")

    add(2, "scf.for %i0 = %c0 to %cM step %cTM {")
    add(3, "%i1 = arith.addi %i0, %cTM : index")
    if variant == "min_bounds":
        add(3, "%ihi = arith.minsi %i1, %cM : index")
    add(3, "scf.for %j0 = %c0 to %cN step %cTN {")
    add(4, "%j1 = arith.addi %j0, %cTN : index")
    if variant == "min_bounds":
        add(4, "%jhi = arith.minsi %j1, %cN : index")
    add(4, "scf.for %k0 = %c0 to %cK step %cTK {")
    add(5, "%k1 = arith.addi %k0, %cTK : index")
    if variant == "min_bounds":
        add(5, "%khi = arith.minsi %k1, %cK : index")

    hi = {"min_bounds": "ihi", "mask": "i1", "danger": "i1"}[variant]
    hj = {"min_bounds": "jhi", "mask": "j1", "danger": "j1"}[variant]
    hk = {"min_bounds": "khi", "mask": "k1", "danger": "k1"}[variant]
    add(5, f"scf.for %i = %i0 to %{hi} step %c1 {{")
    add(6, f"scf.for %j = %j0 to %{hj} step %c1 {{")
    add(7, f"scf.for %k = %k0 to %{hk} step %c1 {{")
    if variant == "mask":
        add(8, "%pi = arith.cmpi slt, %i, %cM : index")
        add(8, "%pj = arith.cmpi slt, %j, %cN : index")
        add(8, "%pk = arith.cmpi slt, %k, %cK : index")
        add(8, "%pij = arith.andi %pi, %pj : i1")
        add(8, "%msk = arith.andi %pij, %pk : i1")
        add(8, "scf.if %msk {")
    bi = 9 if variant == "mask" else 8
    add(bi, f"%a = memref.load %argA[%i, %k] : {tA}")
    add(bi, f"%b = memref.load %argB[%k, %j] : {tB}")
    add(bi, f"%c = memref.load %argC[%i, %j] : {tC}")
    add(bi, "%mul = arith.mulf %a, %b : f32")
    add(bi, "%sum = arith.addf %c, %mul : f32")
    add(bi, f"memref.store %sum, %argC[%i, %j] : {tC}")
    if variant == "mask":
        add(8, "}")
    add(7, "}")
    add(6, "}")
    add(5, "}")
    add(4, "}")
    add(3, "}")
    add(2, "}")
    add(2, "return")
    add(1, "}")
    add(0, "}")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("M", nargs="?", type=int, default=5)
    ap.add_argument("N", nargs="?", type=int, default=7)
    ap.add_argument("K", nargs="?", type=int, default=3)
    ap.add_argument("TM", nargs="?", type=int, default=2)
    ap.add_argument("TN", nargs="?", type=int, default=4)
    ap.add_argument("TK", nargs="?", type=int, default=2)
    ap.add_argument("--out", default=os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "ir"))
    args = ap.parse_args()

    if min(args.M, args.N, args.K, args.TM, args.TN, args.TK) <= 0:
        sys.exit("M/N/K/Tile 必须为正整数")

    os.makedirs(args.out, exist_ok=True)
    plan = [
        ("matmul_min_bounds.mlir", (args.M, args.N, args.K,
                                    args.TM, args.TN, args.TK), "min_bounds"),
        ("matmul_mask.mlir", (args.M, args.N, args.K,
                              args.TM, args.TN, args.TK), "mask"),
        ("matmul_danger.mlir", (args.M, args.N, args.K,
                                args.TM, args.TN, args.TK), "danger"),
        ("matmul_min_bounds_divisible.mlir", (6, 8, 4, 2, 4, 2), "min_bounds"),
    ]
    for name, dims, variant in plan:
        text = gen(*dims, variant)
        path = os.path.join(args.out, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"wrote {path} ({os.path.getsize(path)} bytes, "
              f"{text.count(chr(10))} lines)")


if __name__ == "__main__":
    main()
