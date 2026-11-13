#!/usr/bin/env bash
# run_all.sh —— 第 75 天一键复跑：主实验 → 独立验收 → 重新生成图片
set -euo pipefail
cd "$(dirname "$0")"

echo "== 第 75 天：构造不融合案例（负收益案例库）=="
python3 negative_case_lab.py 2>&1 | tee outputs/negative_case_lab.txt
echo
python3 test_negative_cases.py 2>&1 | tee outputs/test_negative_cases.txt
echo
python3 make_images.py
echo
echo "完成：outputs/ 存有真实运行输出，../images/ 存有 4 张 SVG。"
