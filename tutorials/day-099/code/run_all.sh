#!/bin/bash
# 第 99 天一键复现：两种执行顺序的区间表 → 全部合法拓扑序的峰值分布 → 捷径加宽对照 → 校验
set -euo pipefail
cd "$(dirname "$0")"

mkdir -p outputs

python3 lifetime.py --order main-first --svg-prefix outputs/timeline > outputs/main-first.txt
python3 lifetime.py --order skip-first --svg-prefix outputs/timeline > outputs/skip-first.txt
python3 lifetime.py --order all                                  > outputs/all-orders.txt
python3 lifetime.py --order main-first --skip-width 256          > outputs/skip-width-256-main.txt
python3 lifetime.py --order skip-first --skip-width 256          > outputs/skip-width-256-skip.txt

python3 --version > outputs/env.txt
uname -m >> outputs/env.txt

echo "=== 全部完成，真实输出在 outputs/ ==="
ls -la outputs/
