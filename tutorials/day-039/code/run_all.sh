#!/usr/bin/env bash
# 第 39 天一键重放：构建带手写 Verifier 的 mini-opt → 2 个正例 → 7 个负例
#                  → 动态维度 4 连测 → 双错探针 → Day 38 回归
# 环境：Ubuntu 20.04、LLVM/MLIR 18.1.8（mlir-18-tools），与 Day 29/37/38 记录一致
# 用法：bash run_all.sh        # 在本目录执行；构建目录写到 /tmp/day039/build
set -uo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
BUILD=/tmp/day039/build
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

banner "2/7 静态正例：2x3·3x2->2x2 与 batch 版 2x2x3·2x3x4->2x2x4（各应 rc=0）"
for f in matmul_ok_2d.mlir matmul_ok_batched.mlir; do
  echo "--- $f ---"
  "$MINI_OPT" "$HERE/$f"
  echo "rc=$?"
done

banner "3/7 静态负例：Day37 探针终于被拦 + 输出/秩/batch 三类错误（各应 rc=1）"
for f in matmul_inner_dim.mlir matmul_bad_result_shape.mlir matmul_rank_mismatch.mlir matmul_batch_mismatch.mlir; do
  echo "--- $f ---"
  "$MINI_OPT" "$HERE/$f"
  echo "rc=$?"
done

banner "4/7 动态维度四连测：合法放行 / 合法细化 / 静态可查仍拦 / 输出 N 错"
for f in matmul_dynamic_ok.mlir matmul_dynamic_refine.mlir matmul_dynamic_bad_inner.mlir matmul_dynamic_bad_result.mlir; do
  echo "--- $f ---"
  "$MINI_OPT" "$HERE/$f"
  echo "rc=$?"
done

banner "5/7 诊断质量探针：双错只报第一个 + 哨兵值已修复为 ? （各应 rc=1）"
for f in matmul_two_errors.mlir matmul_sentinel_probe.mlir; do
  echo "--- $f ---"
  "$MINI_OPT" "$HERE/$f"
  echo "rc=$?"
done

banner "6/7 回归：Day 38 完整目标图必须原样通过（应 rc=0）"
"$MINI_OPT" "$HERE/pipeline_regression.mlir"
echo "rc=$?"

banner "7/7 揭底牌：正例的泛型形式（verify 通过后才能打印）"
"$MINI_OPT" "$HERE/pipeline_regression.mlir" --mlir-print-op-generic | head -8
echo "rc=$?"
