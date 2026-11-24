#!/usr/bin/env bash
# 第 36 天一键重放：构建 mini-opt → --show-dialects → round-trip → 探针 → 改名对照实验
# 环境：Ubuntu 20.04 (aarch64)、LLVM/MLIR 18.1.8（mlir-18-tools + libmlir-18-dev）
# 用法：bash run_all.sh        # 在本目录执行；构建目录写到 /tmp/day036/build
set -uo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
BUILD="${DAY036_BUILD:-/tmp/day036/build}"
MINI_SRC="$HERE/mini"
MLIR_DIR=/usr/lib/llvm-18/lib/cmake/mlir
mkdir -p "$BUILD"

banner() { printf '\n\033[1;36m== %s ==\033[0m\n' "$*"; }

banner "0/6 环境检查"
mlir-opt-18 --version | head -1
cmake --version | head -1
test -f "$MLIR_DIR/MLIRConfig.cmake" || { echo "缺少 $MLIR_DIR（先安装 libmlir-18-dev llvm-18-dev）"; exit 1; }

banner "1/6 构建：mlir-tblgen 生成 MiniOpsDialect.*.inc + 编译 mini-opt（首次约 1～3 分钟）"
cmake -G Ninja -B "$BUILD" -S "$MINI_SRC" -DCMAKE_BUILD_TYPE=Release -DMLIR_DIR="$MLIR_DIR"
cmake --build "$BUILD"
MINI_OPT="$BUILD/bin/mini-opt"

banner "2/6 户口本验收：mini-opt --show-dialects"
"$MINI_OPT" --show-dialects

banner "3/6 round-trip：mini_smoke.mlir 解析→验证→打印（应原样返回，rc=0）"
"$MINI_OPT" "$HERE/mini_smoke.mlir"
echo "rc=$?"

banner "4/6 探针：mini.foo 问两个工具"
echo "-- mini-opt（mini 已注册：报 op 未知，rc=1）--"
"$MINI_OPT" "$HERE/mini_ghost_op.mlir" 2>&1 | head -2
echo "rc=${PIPESTATUS[0]}"
echo "-- mlir-opt-18（mini 未注册：报 Dialect not found，rc=1）--"
mlir-opt-18 "$HERE/mini_ghost_op.mlir" 2>&1 | head -2
echo "rc=${PIPESTATUS[0]}"

banner "5/6 对照实验：方言改名 mini→miniv2（先只改 .td 看失败，再补 CMake 看成功）"
TD="$MINI_SRC/include/mini/MiniDialect.td"
CM="$MINI_SRC/include/mini/CMakeLists.txt"
cp "$TD" "$TD.bak"; cp "$CM" "$CM.bak"
restore() { cp "$TD.bak" "$TD"; cp "$CM.bak" "$CM"; rm -f "$TD.bak" "$CM.bak"; cmake --build "$BUILD" >/dev/null 2>&1; }
trap restore EXIT
echo "-- 5a 只改 .td 的 let name，-dialect=mini 没跟着改 → mlir-tblgen 报错 --"
sed -i 's/let name = "mini";/let name = "miniv2";/' "$TD"
build_log=$(cmake --build "$BUILD" 2>&1)
echo "$build_log" | grep -m1 "selected dialect" || echo "（没有复现？检查 -dialect 是否被误改）"
echo "-- 5b CMakeLists 里的 -dialect=mini 也改成 -dialect=miniv2 → 构建成功 --"
sed -i 's/-dialect=mini/-dialect=miniv2/g' "$CM"
cmake --build "$BUILD" >/dev/null
"$MINI_OPT" --show-dialects 2>&1 | head -1
echo "-- 5c 改名后 mini.foo 探针（mini 没了，报错口径和 mlir-opt-18 一样）--"
"$MINI_OPT" "$HERE/mini_ghost_op.mlir" 2>&1 | head -1
restore; trap - EXIT
echo "-- 还原后 --show-dialects --"
"$MINI_OPT" --show-dialects 2>&1 | head -1

banner "6/6 结束：手写代码行数统计"
wc -l "$MINI_SRC/include/mini/MiniDialect.td" \
      "$MINI_SRC/lib/MiniDialect.cpp" \
      "$MINI_SRC/tools/mini-opt/MiniOpt.cpp" | tail -4

banner "重放完成"
