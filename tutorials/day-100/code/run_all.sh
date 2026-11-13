#!/usr/bin/env bash
# 一键复现第 100 天的全部运行记录（写入 outputs/）
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p outputs

{
  python3 --version
  uname -m
} > outputs/env.txt

python3 planner.py --order main-first --svg outputs/offset-chart-main-first > outputs/main-first.txt
python3 planner.py --order skip-first --svg outputs/offset-chart-skip-first > outputs/skip-first.txt
python3 planner.py --order-sweep > outputs/order-sweep.txt
python3 planner.py --align-sweep > outputs/align-sweep.txt
python3 planner.py --alias-demo > outputs/alias-demo.txt
python3 planner.py --hazard-demo > outputs/hazard-demo.txt
python3 planner.py --test > outputs/test-all.txt

echo "全部输出已写入 outputs/："
ls outputs/
