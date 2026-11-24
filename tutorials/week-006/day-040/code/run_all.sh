#!/usr/bin/env bash
# 第 40 天一键重放：构建 add/relu 手写 Verifier 版 mini-opt
#                  -> 5 个正例 -> 8 个负例（广播拒绝 / 永久不匹配 / 结果侧错误）
#                  -> 回归 -> （可选）与 Day 39 trait 版报错对照
# 环境：Ubuntu 20.04、LLVM/MLIR 18.1.8（mlir-18-tools），与 Day 29/37/38/39 记录一致
# 用法：bash run_all.sh        # 在本目录执行；构建目录写到 /tmp/day040/build
set -uo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
BUILD=/tmp/day040/build
MINI_SRC="$HERE/mini"
mkdir -p "$BUILD"

banner() { printf '\n\033[1;36m== %s ==\033[0m\n' "$*"; }

banner "0/7 环境检查"
mlir-opt-18 --version | head -1
cmake --version | head -1

banner "1/7 构建：摘掉 trait、挂上手写 verify() 的 mini-opt（首次约 1~3 分钟）"
cmake -G Ninja -B "$BUILD" -S "$MINI_SRC" -DCMAKE_BUILD_TYPE=Release \
      -DMLIR_DIR=/usr/lib/llvm-18/lib/cmake/mlir
cmake --build "$BUILD"
MINI_OPT="$BUILD/bin/mini-opt"

banner "2/7 正例：一致 shape、不限秩、动态细化（各应 rc=0）"
for f in add_ok.mlir relu_ok.mlir add_dynamic_refine.mlir relu_dynamic_refine.mlir; do
  echo "--- $f ---"
  "$MINI_OPT" "$HERE/$f"
  echo "rc=$?"
done

banner "3/7 广播拒绝：bias 1x2 / 秩不同 1x2x3+2x3 / 右对齐探针 3x2x4+2x4（各应 rc=1，报 not supported yet）"
for f in add_broadcast_bias.mlir add_rank_broadcast.mlir add_align_probe.mlir; do
  echo "--- $f ---"
  "$MINI_OPT" "$HERE/$f"
  echo "rc=$?"
done

banner "4/7 永久不匹配：2x2+2x3 / ?x3+2x4 / relu 2x3->3x3（各应 rc=1，报 not broadcast-compatible）"
for f in add_mismatch.mlir add_dynamic_bad.mlir relu_bad_result.mlir; do
  echo "--- $f ---"
  "$MINI_OPT" "$HERE/$f"
  echo "rc=$?"
done

banner "5/7 结果侧检查：add 2x2->2x3 / relu 2x3->1x3（各应 rc=1）"
for f in add_bad_result.mlir relu_broadcast_result.mlir; do
  echo "--- $f ---"
  "$MINI_OPT" "$HERE/$f"
  echo "rc=$?"
done

banner "6/7 回归：Day 38/39 完整目标图 MatMul->Add->Relu 必须原样通过（应 rc=0）"
"$MINI_OPT" "$HERE/pipeline_regression.mlir"
echo "rc=$?"

banner "7/7 彩蛋（可选）：Day 39 trait 版 mini-opt 还在的话，看同一个 bias 文件的新老报错对照"
if [ -x /tmp/day039/build/bin/mini-opt ]; then
  echo "--- Day 39（trait：SameOperandsAndResultType）---"
  /tmp/day039/build/bin/mini-opt "$HERE/add_broadcast_bias.mlir"
  echo "rc=$?"
  echo "--- Day 40（手写 Verifier）---"
  "$MINI_OPT" "$HERE/add_broadcast_bias.mlir"
  echo "rc=$?"
else
  echo "跳过：/tmp/day039/build/bin/mini-opt 不存在（先跑 Day 39 的 run_all.sh 可复现）"
fi
