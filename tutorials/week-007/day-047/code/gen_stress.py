#!/usr/bin/env python3
"""第 47 天编译期开销实验的压力用例生成器。

生成 nfuncs 个函数，每个函数一条"常量 + 常量"的 mini.add：
  --dim 32 → tensor<32x32xf32>，1024 个元素 == kMaxFoldElements，允许折叠；
  --dim 64 → tensor<64x64xf32>，4096 个元素 > 1024，被尺寸护栏拒绝。

两组用例只差一个维数，配合不同 kMaxFoldElements 的 mini-opt，
就能把"折叠一个大常量要花多少编译时间"量出来（教程 5.6 节）。

用法：
  python3 gen_stress.py --funcs 500 --dim 64 -o /tmp/day047/stress_big.mlir
  python3 gen_stress.py --funcs 500 --dim 32 -o /tmp/day047/stress_small.mlir
"""
import argparse


def gen(nfuncs: int, dim: int) -> str:
    lines = ["module {"]
    for i in range(nfuncs):
        lines.append(f"  func.func @f{i}() -> tensor<{dim}x{dim}xf32> {{")
        lines.append(f"    %a = mini.constant dense<1.0> : tensor<{dim}x{dim}xf32>")
        lines.append(f"    %b = mini.constant dense<2.0> : tensor<{dim}x{dim}xf32>")
        lines.append(f"    %s = mini.add %a, %b : tensor<{dim}x{dim}xf32>, "
                     f"tensor<{dim}x{dim}xf32> -> tensor<{dim}x{dim}xf32>")
        lines.append(f"    func.return %s : tensor<{dim}x{dim}xf32>")
        lines.append("  }")
    lines.append("}")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--funcs", type=int, default=500, help="函数个数")
    ap.add_argument("--dim", type=int, default=64, help="张量边长（dim x dim）")
    ap.add_argument("-o", "--output", required=True, help="输出 .mlir 路径")
    args = ap.parse_args()
    with open(args.output, "w") as f:
        f.write(gen(args.funcs, args.dim))
    print(f"{args.output}: {args.funcs} funcs x tensor<{args.dim}x{args.dim}xf32> "
          f"({args.dim * args.dim} elements per add)")
