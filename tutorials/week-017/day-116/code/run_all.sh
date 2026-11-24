#!/usr/bin/env bash
# 第 116 天一键复现：源 IR 一致性校验 + 主运行（2×2，9 项检查）+ 形状对照（2×3，10 项），
# 本机实测 1 秒内跑完（2026-11-13，aarch64，Python 3.11.4 / numpy 1.26.4 / llvmlite 0.50.0）。
set -euo pipefail
cd "$(dirname "$0")"

echo "== 校验源 IR 与生成器一致 =="
python3 op_lowering.py --emit-src add | diff -q - add_ir.mlir && echo "add_ir.mlir 与生成器输出一致"
python3 op_lowering.py --emit-src relu | diff -q - relu_ir.mlir && echo "relu_ir.mlir 与生成器输出一致"
python3 op_lowering.py --emit-src step | diff -q - step_ir.mlir && echo "step_ir.mlir 与生成器输出一致"
python3 op_lowering.py --emit-src gemm | diff -q - gemm_ir.mlir && echo "gemm_ir.mlir 与生成器输出一致"

echo
echo "== 主运行（@add/@relu 2×2 + @step + GEMM 账本回归）=="
python3 op_lowering.py | tee outputs/run-all-log.txt

echo
echo "== 形状对照（--shape 2 3 --tag s23）=="
python3 op_lowering.py --shape 2 3 --tag s23 | tee outputs/run-all-log-s23.txt

echo
echo "== 产出清单 =="
ls -la outputs/
