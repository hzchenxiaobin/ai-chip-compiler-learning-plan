#!/usr/bin/env bash
# 第 14 天对照实验的一键脚本：编译并运行 mask 位置实验，
# 把两个变体的 IR 逐行 diff 一起保存进 mask-position.log。
set -euo pipefail
cd "$(dirname "$0")"

mkdir -p build-experiment
g++ -std=c++17 -g -Wall -Wextra -I ../src mask_position_ab.cpp \
    ../src/Graph.cpp ../src/Verifier.cpp ../src/Interpreter.cpp \
    ../src/Frontend.cpp -o build-experiment/mask_position_ab

LOG=mask-position.log
TMP_A=build-experiment/ir_a.txt
TMP_B=build-experiment/ir_b.txt
{
    echo "== 环境 =="
    echo "$(g++ --version | head -1) · $(uname -m)"
    echo
    ./build-experiment/mask_position_ab
    echo "== 两个变体 IR 的逐行 diff（< 变体 A  > 变体 B）=="
    ./build-experiment/mask_position_ab | sed -n '/graph "A-mask-last"/,/^}$/p' > "$TMP_A"
    ./build-experiment/mask_position_ab | sed -n '/graph "B-mask-first"/,/^}$/p' > "$TMP_B"
    diff "$TMP_A" "$TMP_B" || true
    rm -f "$TMP_A" "$TMP_B"
} > "$LOG" 2>&1

echo "日志已写入 $LOG"
