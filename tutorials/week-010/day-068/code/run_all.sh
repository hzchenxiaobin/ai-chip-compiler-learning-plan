#!/usr/bin/env bash
# run_all.sh —— 第 68 天（Layout 转换传播）一键复跑。
#
# 流程：
#   1  环境
#   2  layout_prop_lab.py：主实验——手工推导 + 受限 Pattern + 三明治收益
#      + 语义约束说明 + 300 组压力对拍 + MLIR 对表
#   3  test_layout_prop.py：独立验收测试（A–G 七段）
#   4  静态 IR 文件裁决（5 个探针的直接 mlir-opt 实测）
#
# 用法：bash run_all.sh   （在 day-068/code/ 目录下）

set -u
cd "$(dirname "$0")"
OUT=outputs
mkdir -p "$OUT"

echo "== 环境 =="
python3 --version
python3 -c "import numpy; print('numpy', numpy.__version__)"
if command -v mlir-opt >/dev/null 2>&1; then
  MLIR=mlir-opt
elif [ -x /usr/lib/llvm-18/bin/mlir-opt ]; then
  MLIR=/usr/lib/llvm-18/bin/mlir-opt
else
  MLIR=""
fi
if [ -n "$MLIR" ]; then
  "$MLIR" --version | head -1
else
  echo "mlir-opt 不可用（IR 裁决相关步骤将降级）"
fi
uname -m
echo

echo "== 1. layout_prop_lab.py：推导 + 受限 Pattern + 收益 + 约束 + MLIR 对表 =="
python3 layout_prop_lab.py | tee "$OUT/layout_prop_lab.txt"
echo "exit=$?"
echo

echo "== 2. test_layout_prop.py：验收测试（A–G 七段）=="
python3 test_layout_prop.py | tee "$OUT/test_layout_prop.txt"
echo "exit=$?"
echo

echo "== 3. 静态 IR 文件实测 =="
if [ -n "$MLIR" ]; then
  "$MLIR" push_probe.mlir --canonicalize -o "$OUT/push_probe.canon.mlir"
  echo "push_probe.mlir --canonicalize exit=$?"
  echo "  linalg.transpose 个数：$(grep -c 'linalg.transpose' "$OUT/push_probe.canon.mlir")（预期 1：不推）"
  echo "  linalg.generic  个数：$(grep -c 'linalg.generic' "$OUT/push_probe.canon.mlir")（预期 1）"
  echo

  "$MLIR" sandwich_probe.mlir --canonicalize -o "$OUT/sandwich_probe.canon.mlir"
  echo "sandwich_probe.mlir --canonicalize exit=$?"
  echo "  linalg.transpose 个数：$(grep -c 'linalg.transpose' "$OUT/sandwich_probe.canon.mlir")（预期 2：不相消）"
  echo "  linalg.generic  个数：$(grep -c 'linalg.generic' "$OUT/sandwich_probe.canon.mlir")（预期 1）"
  echo

  "$MLIR" sandwich_memref.mlir --convert-linalg-to-loops -o "$OUT/sandwich_memref.loops.mlir"
  echo "sandwich_memref.mlir --convert-linalg-to-loops exit=$?"
  echo "  scf.for      层数：$(grep -c 'scf.for' "$OUT/sandwich_memref.loops.mlir")（预期 6）"
  echo "  memref.load  行数：$(grep -c 'memref.load' "$OUT/sandwich_memref.loops.mlir")（预期 3）"
  echo "  memref.store 行数：$(grep -c 'memref.store' "$OUT/sandwich_memref.loops.mlir")（预期 3）"
  echo

  "$MLIR" sandwich_after.mlir --convert-linalg-to-loops -o "$OUT/sandwich_after.loops.mlir"
  echo "sandwich_after.mlir --convert-linalg-to-loops exit=$?"
  echo "  scf.for      层数：$(grep -c 'scf.for' "$OUT/sandwich_after.loops.mlir")（预期 2）"
  echo "  memref.load  行数：$(grep -c 'memref.load' "$OUT/sandwich_after.loops.mlir")（预期 1）"
  echo "  memref.store 行数：$(grep -c 'memref.store' "$OUT/sandwich_after.loops.mlir")（预期 1）"
  echo

  "$MLIR" tosa_const_probe.mlir --tosa-layerwise-constant-fold -o "$OUT/tosa_const_probe.fold.mlir"
  echo "tosa_const_probe.mlir --tosa-layerwise-constant-fold exit=$?"
  echo "  tosa.transpose 个数：$(grep -c 'tosa.transpose' "$OUT/tosa_const_probe.fold.mlir")（预期 0：折掉）"
  echo "  tosa.const     个数：$(grep -c 'tosa.const' "$OUT/tosa_const_probe.fold.mlir")（预期 1：转置后的常量）"
else
  echo "mlir-opt 不可用，跳过"
fi
echo

echo "run_all: 全部完成"
