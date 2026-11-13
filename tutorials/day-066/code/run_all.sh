#!/usr/bin/env bash
# run_all.sh —— 第 66 天（连续 Reshape 合并）一键复跑。
#
# 流程：
#   1  环境
#   2  reshape_merge_lab.py：主实验——numel 守恒 + 两个 Pattern + 激进版 + MLIR 对表
#   3  test_reshape_merge.py：验收测试（A–G 七段）
#   4  静态 IR 文件裁决（reshape_chain.mlir / reassociative_chain.mlir 的 canonicalize 实测）
#
# 用法：bash run_all.sh   （在 day-066/code/ 目录下）

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

echo "== 1. reshape_merge_lab.py：numel 守恒 + 两个 RewritePattern + 激进版 + MLIR 对表 =="
python3 reshape_merge_lab.py | tee "$OUT/reshape_merge_lab.txt"
echo "exit=$?"
echo

echo "== 2. test_reshape_merge.py：验收测试（A–G 七段）=="
python3 test_reshape_merge.py | tee "$OUT/test_reshape_merge.txt"
echo "exit=$?"
echo

echo "== 3. 静态 IR 文件实测 =="
if [ -n "$MLIR" ]; then
  "$MLIR" reshape_chain.mlir --canonicalize -o "$OUT/reshape_chain.canon2.mlir"
  echo "reshape_chain.mlir --canonicalize exit=$?（预期 0，IR 原样保留）"
  echo "  输出中 tensor.reshape 个数：$(grep -c 'tensor.reshape' "$OUT/reshape_chain.canon2.mlir")（预期 2）"
  "$MLIR" reassociative_chain.mlir --canonicalize -o "$OUT/reassociative_chain.canon2.mlir"
  echo "reassociative_chain.mlir --canonicalize exit=$?"
  echo "  输出中 collapse 个数：$(grep -c 'tensor.collapse_shape' "$OUT/reassociative_chain.canon2.mlir")（预期 2：@cc 合并后 1 个 + @ce 的 1 个）"
  echo "  输出中 expand 个数：$(grep -c 'tensor.expand_shape' "$OUT/reassociative_chain.canon2.mlir")（预期 2：@ee 合并后的 1 个 + @ce 的 1 个；@ec 已消除）"
  echo "  return %arg0 个数：$(grep -c 'return %arg0' "$OUT/reassociative_chain.canon2.mlir")（预期 1：@ec 整体消除）"
else
  echo "mlir-opt 不可用，跳过"
fi
echo

echo "run_all: 全部完成"
