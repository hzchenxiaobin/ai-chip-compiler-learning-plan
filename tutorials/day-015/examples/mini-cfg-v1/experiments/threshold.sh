#!/usr/bin/env bash
# 第 15 天对照实验：一键编译并运行 threshold_ab，日志写进 threshold.log。
# 用法：bash experiments/threshold.sh   （在 mini-cfg-v1 目录下执行）
set -euo pipefail
cd "$(dirname "$0")"

g++ -std=c++17 -Wall -Wextra -I ../src ../src/Cfg.cpp ../src/Interpreter.cpp \
  threshold_ab.cpp -o threshold_ab

./threshold_ab | tee threshold.log
