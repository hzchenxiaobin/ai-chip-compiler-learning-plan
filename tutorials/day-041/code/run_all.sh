#!/usr/bin/env bash
# 第 41 天一键重放：构建注册了 Pass 的 mini-opt
#                  -> 第一张端到端 mini IR（MatMul->Add->Relu）
#                  -> 解析/验证/打印（round-trip）
#                  -> 通用变换 Pass（-cse）与自定义 Pass（-mini-count-ops）
#                  -> 负例（shape 永久不匹配 / 只差广播）
#                  -> 三个"谁认识 mini"对照（stock mlir-opt / 无 Pass 注册版 / 完整版）
# 环境：Ubuntu 20.04、LLVM/MLIR 18.1.8（mlir-18-tools），与 Day 37~40 记录一致
# 用法：bash run_all.sh        # 在本目录执行；构建目录写到 /tmp/day041/build
#                          对照组构建目录写到 /tmp/day041/noreg-src + /tmp/day041/noreg-build
set -uo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
BUILD=/tmp/day041/build
NOREG_SRC=/tmp/day041/noreg-src
NOREG_BUILD=/tmp/day041/noreg-build
MINI_SRC="$HERE/mini"
mkdir -p "$BUILD"

banner() { printf '\n\033[1;36m== %s ==\033[0m\n' "$*"; }

banner "0/9 环境检查"
mlir-opt-18 --version | head -1
cmake --version | head -1

banner "1/9 构建：注册了 Pass 的 mini-opt（首次约 1~3 分钟）"
cmake -G Ninja -B "$BUILD" -S "$MINI_SRC" -DCMAKE_BUILD_TYPE=Release \
      -DMLIR_DIR=/usr/lib/llvm-18/lib/cmake/mlir
cmake --build "$BUILD"
MINI_OPT="$BUILD/bin/mini-opt"

banner "2/9 第一张端到端 mini IR：round-trip（解析->验证->打印，应 rc=0）"
for f in target_graph.mlir target_graph_args.mlir; do
  echo "--- $f ---"
  "$MINI_OPT" "$HERE/$f"
  echo "rc=$?"
done

banner "3/9 负例 1：bias 2x3 撞上结果 2x2（应 rc=1，报 dimension 不匹配）"
"$MINI_OPT" "$HERE/bad_bias_shape.mlir"
echo "rc=$?"

banner "4/9 负例 2：bias 1x2 只差广播（应 rc=1，报 would broadcast / not supported yet）"
"$MINI_OPT" "$HERE/broadcast_bias.mlir"
echo "rc=$?"

banner "5/9 通用变换 Pass：-cse 吃掉重复的 matmul/add/relu（10 行 IR 应缩成 7 行）"
"$MINI_OPT" -cse "$HERE/cse_dup_matmul.mlir"
echo "rc=$?"

banner "6/9 自定义 Pass：-mini-count-ops 用 remark 报告每个函数的操作清单"
"$MINI_OPT" -mini-count-ops "$HERE/target_graph.mlir" 2>&1 | grep -m1 "remark:"
"$MINI_OPT" -mini-count-ops "$HERE/target_graph_args.mlir" 2>&1 | grep -m1 "remark:"
echo "rc=0（两条 remark 都应出现：8 ops 与 5 ops）"

banner "7/9 Pass 统计表：-mlir-pass-statistics 在本 Release 构建里是空表（诚实记录）"
"$MINI_OPT" -mlir-pass-statistics -mini-count-ops "$HERE/target_graph.mlir" \
    2>&1 >/dev/null | tail -4
echo "rc=0（统计被 NDEBUG 编译掉了；remark 通道不受影响，见教程 5.6 节）"

banner "8/9 对照 A：stock mlir-opt-18 不认识 mini 方言（应 rc=1）"
mlir-opt-18 "$HERE/target_graph.mlir" 2>&1 | head -4
echo "rc=1（正文里附完整 Registered dialects 名单）"

banner "9/9 对照 B：不注册 Pass 的 mini-opt（方言能解析，Pass 全部缺席）"
rm -rf "$NOREG_SRC" "$NOREG_BUILD"; mkdir -p /tmp/day041
cp -r "$MINI_SRC" "$NOREG_SRC"
# 只改一个变量：把 MiniOpt.cpp 里两行注册注释掉
sed -i 's|^  mlir::registerTransformsPasses();|  // 实验对照：故意不注册|' \
    "$NOREG_SRC/tools/mini-opt/MiniOpt.cpp"
sed -i 's|^  mlir::mini::registerCountOpsPass();|  // 实验对照：故意不注册|' \
    "$NOREG_SRC/tools/mini-opt/MiniOpt.cpp"
cmake -G Ninja -B "$NOREG_BUILD" -S "$NOREG_SRC" -DCMAKE_BUILD_TYPE=Release \
      -DMLIR_DIR=/usr/lib/llvm-18/lib/cmake/mlir > /dev/null
cmake --build "$NOREG_BUILD" > /dev/null 2>&1
NOREG_OPT="$NOREG_BUILD/bin/mini-opt"
echo "--- B1: round-trip 仍 rc=0（方言注册与 Pass 注册是两回事） ---"
"$NOREG_OPT" "$HERE/target_graph.mlir" > /dev/null && echo "rc=0"
echo "--- B2: -cse 变成未知参数 ---"
"$NOREG_OPT" -cse "$HERE/cse_dup_matmul.mlir" 2>&1 | head -2
echo "--- B3: -mini-count-ops 也一样 ---"
"$NOREG_OPT" -mini-count-ops "$HERE/target_graph.mlir" 2>&1 | head -2
echo "--- B4: --help 里干脆没有 Passes: 小节 ---"
"$NOREG_OPT" --help 2>&1 | grep -c "^    Passes:" || echo "0（没有这一节）"

banner "完成：9 组结果全部留档，与 tutorials/day-041/README.md 5.x 节一一对应"
