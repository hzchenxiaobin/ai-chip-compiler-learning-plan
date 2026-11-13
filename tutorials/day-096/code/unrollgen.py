#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""unrollgen.py —— 第 96 天：把“循环展开”写成真正的 MLIR scf 方言 IR。

用法：  python3 unrollgen.py 5 7 3 2 [--out ir]
输出（写入 --out 目录，默认 ir/）：
  matmul_before.mlir             展开前：i/j/k 三重点循环（第 88~89 天的形态）
  matmul_unroll_k2.mlir          K 展开两份＋尾部循环（主例 5x7x3：k 循环 3 步，
                                 主循环盖住 k0/k1，尾部循环盖住 k2）
  matmul_unroll_k4_divisible.mlir K 展开四份（8x8x8 整除：主循环两步、尾部循环
                                 8 到 8 是空循环）

生成的 IR 用上游 mlir-opt 做解析验证（见 run_all.sh），
并统计 bytes / scf.for / memref.load / arith.mulf 的数量，
给出“展开前后 IR 大小”的真实对照（代码膨胀的 IR 级证据）。
"""

import argparse
import os
import sys


def gen(M, N, K, U, variant):
    """生成 func.func @matmul 的 MLIR 文本；variant ∈ {before, unroll_k}。"""
    tA = f"memref<{M}x{K}xf32>"
    tB = f"memref<{K}x{N}xf32>"
    tC = f"memref<{M}x{N}xf32>"
    lines = []

    def add(indent, text):
        lines.append("  " * indent + text)

    k_main_end = K // U * U  # 主循环上界：floor(K/U)*U

    add(0, f"// 由 unrollgen.py 生成：M={M} N={N} K={K} U={U} variant={variant}")
    add(0, f"// 有效计算 M*N*K = {M * N * K} 步；"
           f"K= floor部分 {k_main_end} 步走主循环、余 {K - k_main_end} 步走尾部")
    add(0, "module {")
    add(1, f"func.func @matmul(%argA: {tA}, %argB: {tB}, %argC: {tC}) {{")
    consts = [("c0", 0), ("c1", 1), ("cM", M), ("cN", N), ("cK", K)]
    if variant == "unroll_k":
        consts += [("cU", U), ("cMain", k_main_end)]
        for u in range(1, U):  # 展开体内要用的 k 偏移常量（d=delta）
            consts.append((f"d{u}", u))
    for name, val in consts:
        add(2, f"%{name} = arith.constant {val} : index")
    add(2, "%cf0 = arith.constant 0.0 : f32")

    add(2, "// 清零 C：精确边界 0..M × 0..N，与展开无关")
    add(2, "scf.for %zi = %c0 to %cM step %c1 {")
    add(3, "scf.for %zj = %c0 to %cN step %c1 {")
    add(4, f"memref.store %cf0, %argC[%zi, %zj] : {tC}")
    add(3, "}")
    add(2, "}")

    add(2, "scf.for %i = %c0 to %cM step %c1 {")
    add(3, "scf.for %j = %c0 to %cN step %c1 {")
    if variant == "before":
        add(4, "scf.for %k = %c0 to %cK step %c1 {")
        add(5, f"%a = memref.load %argA[%i, %k] : {tA}")
        add(5, f"%b = memref.load %argB[%k, %j] : {tB}")
        add(5, f"%c = memref.load %argC[%i, %j] : {tC}")
        add(5, "%mul = arith.mulf %a, %b : f32")
        add(5, "%sum = arith.addf %c, %mul : f32")
        add(5, f"memref.store %sum, %argC[%i, %j] : {tC}")
        add(4, "}")
    else:
        add(4, f"// 主循环：0 到 floor(K/U)*U={k_main_end}，步长 U，"
               f"体内 {U} 份 MAC（k, k+1, …, k+{U - 1}）")
        add(4, "scf.for %k = %c0 to %cMain step %cU {")
        for u in range(U):
            ki = "%k" if u == 0 else f"%ku{u}"
            if u > 0:
                add(5, f"%ku{u} = arith.addi %k, %d{u} : index")
            add(5, f"%a{u} = memref.load %argA[%i, {ki}] : {tA}")
            add(5, f"%b{u} = memref.load %argB[{ki}, %j] : {tB}")
            add(5, f"%acc{u} = memref.load %argC[%i, %j] : {tC}")
            add(5, f"%mul{u} = arith.mulf %a{u}, %b{u} : f32")
            add(5, f"%sum{u} = arith.addf %acc{u}, %mul{u} : f32")
            add(5, f"memref.store %sum{u}, %argC[%i, %j] : {tC}")
        add(4, "}")
        add(4, f"// 尾部循环：{k_main_end} 到 K={K}，步长 1，体内 1 份 MAC")
        add(4, "scf.for %kt = %cMain to %cK step %c1 {")
        add(5, f"%at = memref.load %argA[%i, %kt] : {tA}")
        add(5, f"%bt = memref.load %argB[%kt, %j] : {tB}")
        add(5, f"%ct = memref.load %argC[%i, %j] : {tC}")
        add(5, "%mult = arith.mulf %at, %bt : f32")
        add(5, "%sumt = arith.addf %ct, %mult : f32")
        add(5, f"memref.store %sumt, %argC[%i, %j] : {tC}")
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
    ap.add_argument("U", nargs="?", type=int, default=2)
    ap.add_argument("--out", default=os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "ir"))
    args = ap.parse_args()

    if min(args.M, args.N, args.K, args.U) <= 0:
        sys.exit("M/N/K/U 必须为正整数")

    os.makedirs(args.out, exist_ok=True)
    plan = [
        ("matmul_before.mlir", (args.M, args.N, args.K), 2, "before"),
        ("matmul_unroll_k2.mlir", (args.M, args.N, args.K), 2, "unroll_k"),
        ("matmul_unroll_k4_divisible.mlir", (8, 8, 8), 4, "unroll_k"),
    ]
    for name, dims, U, variant in plan:
        text = gen(dims[0], dims[1], dims[2], U, variant)
        path = os.path.join(args.out, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"wrote {path}: {os.path.getsize(path)} bytes, "
              f"scf.for x{text.count('scf.for')}, "
              f"load x{text.count('memref.load')}, "
              f"MAC(arith.mulf) x{text.count('arith.mulf')}")


if __name__ == "__main__":
    main()
