#!/usr/bin/env bash
# 一键复现 D101 全部实验（环境：aarch64 Linux, Python 3.11.4）
set -euo pipefail
cd "$(dirname "$0")"

mkdir -p outputs

python3 --version > outputs/env.txt
uname -m >> outputs/env.txt
date +%F >> outputs/env.txt

python3 estimator.py                > outputs/main-config.txt      # 主例：128³ fp32 被拒 + 64³ 对照
python3 estimator.py --table        > outputs/space-table.txt      # 交付物：不同 Tile 的空间表
python3 estimator.py --dtype-sweep  > outputs/dtype-sweep.txt      # 固定 128³ 扫 dtype（acc 规则）
python3 estimator.py --budget-sweep > outputs/budget-sweep.txt     # 预算 → 最大立方 Tile
python3 estimator.py --reuse        > outputs/reuse.txt           # HBM 流量 vs Tile
python3 estimator.py --errors       > outputs/errors.txt          # 三个常见错误的估算对照
python3 estimator.py --chart outputs/space-chart.svg              # 程序绘制：空间条形图
python3 estimator.py --test         > outputs/test-all.txt        # 断言式自检

echo "== 全部完成 =="
cat outputs/test-all.txt
