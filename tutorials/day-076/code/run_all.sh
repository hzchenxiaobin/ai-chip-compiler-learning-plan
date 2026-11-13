#!/usr/bin/env bash
# run_all.sh —— 第 76 天一键复跑：主实验 → 独立验收 → 重新生成图片
set -euo pipefail
cd "$(dirname "$0")"

echo "== 第 76 天：简单 Cost Model 集成（Cost Model v0.1）=="
python3 cost_model.py 2>&1 | tee outputs/cost_model.txt
echo
python3 test_cost_model.py 2>&1 | tee outputs/test_cost_model.txt
echo
python3 make_images.py
echo
echo "完成：outputs/ 存有真实运行输出，../images/ 存有 4 张 SVG。"
