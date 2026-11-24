#!/usr/bin/env bash
# 第 38 天一键重放：构建 mini-opt → 正例 round-trip → 泛型对照 → 四条负例
#                  → 秩 0 对照实验 → day-37 回归
# 环境：Ubuntu 20.04 (aarch64)、LLVM/MLIR 18.1.8（mlir-18-tools），与 Day 29/37 记录一致
# 用法：bash run_all.sh        # 在本目录执行；构建目录写到 /tmp/day038/build
set -uo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
BUILD=/tmp/day038/build
MINI_SRC="$HERE/mini"
mkdir -p "$BUILD"

banner() { printf '\n\033[1;36m== %s ==\033[0m\n' "$*"; }

banner "0/7 环境检查"
mlir-opt-18 --version | head -1
cmake --version | head -1

banner "1/7 构建：mlir-tblgen 生成代码 + 编译 mini-opt（首次约 1～3 分钟）"
cmake -G Ninja -B "$BUILD" -S "$MINI_SRC" -DCMAKE_BUILD_TYPE=Release \
      -DMLIR_DIR=/usr/lib/llvm-18/lib/cmake/mlir
cmake --build "$BUILD"
MINI_OPT="$BUILD/bin/mini-opt"

banner "2/7 正例：pipeline_ok.mlir round-trip（MatMul → Add → Relu 首次凑齐）"
"$MINI_OPT" "$HERE/pipeline_ok.mlir"
echo "rc=$?"

banner "3/7 揭底牌：--mlir-print-op-generic（pretty 之外的那层泛型形式）"
"$MINI_OPT" "$HERE/pipeline_ok.mlir" --mlir-print-op-generic
echo "rc=$?"

banner "4/7 四条负例：ODS 约束拒绝（各应 rc=1）"
for f in add_bad_shape.mlir relu_bad_result.mlir add_unranked.mlir constant_bad_shape.mlir; do
  echo "--- $f ---"
  "$MINI_OPT" "$HERE/$f"
  echo "rc=$?"
done

banner "5/7 对照实验上半场：秩 0 张量过 add/relu（应 rc=0）"
"$MINI_OPT" "$HERE/scalar_play.mlir"
echo "rc=$?"

banner "6/7 对照实验下半场：秩 0 张量接 matmul（应 rc=1，秩 >= 2 约束）"
"$MINI_OPT" "$HERE/scalar_matmul.mlir"
echo "rc=$?"

banner "7/7 回归：第 37 天的 matmul 正例必须原样通过（应 rc=0）"
"$MINI_OPT" "$HERE/matmul_regression.mlir"
echo "rc=$?"
