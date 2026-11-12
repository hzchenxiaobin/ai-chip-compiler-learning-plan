#!/usr/bin/env bash
# 第 12 天对照实验：跳过 verify 的三种代价，与 verify 先行的安全网。
# 做四件事，全部真实执行、全程留日志（cost-of-skipping-verify.log）：
#   1) err_silent_fake_kind：假 kind 一路绿灯（第 11 天遗留现场）；
#   2) err_oob_read：跳过 verify 直接跑解释器 → ASan 越界读；
#   3) err_print_on_invalid：先 verify（安全报告）再直接打印（段错误）；
#   4) 对照：同一个内维错误走工厂（当场抛）与走 Verifier（一次列全），
#      由 mini-graph-v5 的第二幕演示。
set -uo pipefail
cd "$(dirname "$0")"
LOG=cost-of-skipping-verify.log

build_and_run() {
    local name="$1"
    echo "===== [$name] g++ -std=c++17 -g -fsanitize=address -static-libasan =====" | tee -a "$LOG"
    if g++ -std=c++17 -g -fsanitize=address -static-libasan \
        -I ../src ../src/Graph.cpp ../src/Interpreter.cpp "../bugs/$name.cpp" \
        -o "/tmp/opencode/$name" 2>&1 | tee -a "$LOG"; then
        echo "----- 运行 ./$name -----" | tee -a "$LOG"
        "/tmp/opencode/$name" 2>&1 | tee -a "$LOG"
        echo "（退出码 ${PIPESTATUS[0]}）" | tee -a "$LOG"
    else
        echo "编译失败" | tee -a "$LOG"
    fi
    echo | tee -a "$LOG"
}

: > "$LOG"
mkdir -p /tmp/opencode
echo "第 12 天实验：跳过 verify 的代价（$(date '+%Y-%m-%d %H:%M:%S')）" | tee -a "$LOG"
echo "环境：$(g++ --version | head -1) · $(uname -m)" | tee -a "$LOG"

build_and_run err_silent_fake_kind
build_and_run err_oob_read

# err_print_on_invalid 不需要 Interpreter.cpp，单独编。
echo "===== [err_print_on_invalid] g++ -std=c++17 -g -fsanitize=address -static-libasan =====" | tee -a "$LOG"
if g++ -std=c++17 -g -fsanitize=address -static-libasan \
    -I ../src ../src/Graph.cpp ../src/Verifier.cpp ../bugs/err_print_on_invalid.cpp \
    -o /tmp/opencode/err_print_on_invalid 2>&1 | tee -a "$LOG"; then
    echo "----- 运行 ./err_print_on_invalid -----" | tee -a "$LOG"
    /tmp/opencode/err_print_on_invalid 2>&1 | tee -a "$LOG"
    echo "（退出码 ${PIPESTATUS[0]}）" | tee -a "$LOG"
fi
echo | tee -a "$LOG"

echo "===== 对照：同一错误的两种拦截（mini-graph-v5 第二幕） =====" | tee -a "$LOG"
if [ -x ../build/src/mini-graph-v5 ]; then
    ../build/src/mini-graph-v5 2>&1 | sed -n '/第二幕/,$p' | tee -a "$LOG"
else
    echo "（先构建主工程：cmake -S . -B build -G Ninja && cmake --build build）" | tee -a "$LOG"
fi
echo "日志已写入 $LOG"
