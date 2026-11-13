#!/usr/bin/env bash
# run_all.sh —— 第 77 天一键复跑：主实验 → 独立验收 → 图片
set -euo pipefail
cd "$(dirname "$0")"

mkdir -p outputs
python3 week11_review.py 2>&1 | tee outputs/week11_review.txt
python3 test_week11_review.py 2>&1 | tee outputs/test_week11_review.txt
python3 make_images.py

echo
echo "第 77 天全部完成：主实验与独立验收输出在 outputs/，4 张 SVG 在 ../images/。"
