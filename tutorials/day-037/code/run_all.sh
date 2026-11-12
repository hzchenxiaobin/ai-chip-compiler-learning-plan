#!/usr/bin/env bash
# 第 37 天一键重放：构建 mini-opt → 正例 round-trip → 三条负例 → 内维探针 → 未注册方言探针
# 环境：Ubuntu 20.04 (aarch64)、LLVM/MLIR 18.1.8（mlir-18-tools），与 Day 29 记录一致
# 用法：bash run_all.sh        # 在本目录执行；构建目录写到 /tmp/day037/build
set -uo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
BUILD=/tmp/day037/build
MINI_SRC="$HERE/mini"
mkdir -p "$BUILD"

banner() { printf '\n\033[1;36m== %s ==\033[0m\n' "$*"; }

banner "0/6 环境检查"
mlir-opt-18 --version | head -1
cmake --version | head -1

banner "1/6 构建：mlir-tblgen 生成代码 + 编译 mini-opt（首次约 1～3 分钟）"
cmake -G Ninja -B "$BUILD" -S "$MINI_SRC" -DCMAKE_BUILD_TYPE=Release \
      -DMLIR_DIR=/usr/lib/llvm-18/lib/cmake/mlir
cmake --build "$BUILD"
MINI_OPT="$BUILD/bin/mini-opt"

banner "2/6 正例：matmul_ok.mlir round-trip（解析→验证→打印）"
"$MINI_OPT" "$HERE/matmul_ok.mlir"
echo "rc=$?"

banner "3/6 揭底牌：--mlir-print-op-generic（pretty 打印器生成的对照）"
"$MINI_OPT" "$HERE/matmul_ok.mlir" --mlir-print-op-generic
echo "rc=$?"

banner "4/6 三条负例：ODS 约束拒绝（各应 rc=1）"
for f in matmul_bad_result_type.mlir matmul_bad_rank.mlir matmul_bad_elem.mlir; do
  echo "--- $f ---"
  "$MINI_OPT" "$HERE/$f"
  echo "rc=$?"
done

banner "5/6 边界探针：内维不匹配 2x3·2x3 今天放行（Shape 检查是 Day 39 的工作）"
"$MINI_OPT" "$HERE/matmul_inner_dim.mlir"
echo "rc=$?"

banner "6/6 未注册方言探针：mlir-opt-18 不认识 mini（注册表决定谁能被解析）"
mlir-opt-18 "$HERE/matmul_ok.mlir" 2>&1 | head -3
echo "rc=${PIPESTATUS[0]}"
