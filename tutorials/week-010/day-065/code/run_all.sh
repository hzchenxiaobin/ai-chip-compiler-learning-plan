#!/usr/bin/env bash
# run_all.sh —— 第 65 天（连续 Transpose 消除）一键复跑。
#
# 流程：
#   1  环境
#   2  transpose_elim_lab.py：主实验——组合排列 + 两个 Pattern + MLIR 对表
#   3  test_transpose_elim.py：验收测试（A–G 七段）
#   4  静态 IR 文件裁决（transpose_chain.mlir 的 canonicalize / loops 实测）
#
# 用法：bash run_all.sh   （在 day-065/code/ 目录下）

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

echo "== 1. transpose_elim_lab.py：组合排列 + 两个 RewritePattern + MLIR 对表 =="
python3 transpose_elim_lab.py | tee "$OUT/transpose_elim_lab.txt"
echo "exit=$?"
echo

echo "== 2. test_transpose_elim.py：验收测试（A–G 七段）=="
python3 test_transpose_elim.py | tee "$OUT/test_transpose_elim.txt"
echo "exit=$?"
echo

echo "== 3. 静态 IR 文件实测 =="
if [ -n "$MLIR" ]; then
  "$MLIR" transpose_chain.mlir --canonicalize -o "$OUT/transpose_chain.canon2.mlir"
  echo "transpose_chain.mlir --canonicalize exit=$?（预期 0，IR 原样保留）"
  echo "  输出中 linalg.transpose 个数：$(grep -c 'linalg.transpose' "$OUT/transpose_chain.canon2.mlir")（预期 2）"
  "$MLIR" transpose_chain.mlir --convert-linalg-to-loops -o "$OUT/transpose_chain.loops2.mlir"
  echo "transpose_chain.mlir --convert-linalg-to-loops exit=$?"
  echo "  scf.for 层数：$(grep -c 'scf.for' "$OUT/transpose_chain.loops2.mlir")（预期 6）"
else
  echo "mlir-opt 不可用，跳过"
fi
echo

echo "run_all: 全部完成"
