#!/bin/bash
# run_all.sh —— 第 98 天一键复现：结构账本 → 维度隔离 → 行距探针 → 尾层单价 → 确认复跑
# tailcost 连跑 3 个独立进程：单格 GFLOPS 存在跨进程双峰（地址布局彩票），3 份记录如实保留
set -euo pipefail
cd "$(dirname "$0")"

g++ -std=c++17 -O3 -ffp-contract=off -o flip_lab flip_lab.cpp

mkdir -p outputs
./flip_lab env       > outputs/env.txt
./flip_lab ledger    > outputs/ledger.txt
./flip_lab isolate   > outputs/isolate.txt
./flip_lab pitch     > outputs/pitch.txt
for i in 1 2 3; do
  ./flip_lab tailcost > "outputs/tailcost-run$i.txt"
done
./flip_lab confirm   > outputs/confirm.txt

echo "=== 全部完成，真实输出在 outputs/ ==="
ls -la outputs/
