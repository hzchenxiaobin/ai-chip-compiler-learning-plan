#!/usr/bin/env bash
# 第 115 天一键复现：主运行（8 项检查＋探针）＋换形状对照，本机实测 1 秒内（2026-11-13）。
set -euo pipefail
cd "$(dirname "$0")"

echo "== 校验输入 IR 与生成器一致 =="
python3 func_lowering.py --emit-src | diff -q - loop_ir.mlir && echo "loop_ir.mlir 与生成器输出一致"

echo
echo "== 主运行（GEMM 4×6×3）=="
python3 func_lowering.py | tee outputs/run-all-log.txt

echo
echo "== 对照运行（--shape 2 3 2）=="
python3 func_lowering.py --shape 2 3 2 --tag s232 | tee outputs/run-all-log-s232.txt

echo
echo "== 产出清单 =="
ls -la outputs/
