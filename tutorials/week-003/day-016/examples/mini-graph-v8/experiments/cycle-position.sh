#!/usr/bin/env bash
# 第 16 天对照实验：一键编译并运行 cycle_position，日志写进 cycle-position.log。
# 用法：bash experiments/cycle-position.sh   （在 mini-graph-v8 目录下执行）
set -euo pipefail
cd "$(dirname "$0")"

g++ -std=c++17 -Wall -Wextra -I ../src \
  ../src/Graph.cpp ../src/Interpreter.cpp ../src/Verifier.cpp \
  ../src/Frontend.cpp ../src/TopoSort.cpp cycle_position.cpp -o cycle_position

./cycle_position | tee cycle-position.log
