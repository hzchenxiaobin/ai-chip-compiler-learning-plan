#!/usr/bin/env bash
# run_all.sh —— 第 73 天一键复跑：主实验 → 独立验收 → 重新生成图片
set -euo pipefail
cd "$(dirname "$0")"

echo "== 第 73 天：融合的资源代价 =="
python3 fusion_resource_lab.py 2>&1 | tee outputs/fusion_resource_lab.txt
echo
python3 test_fusion_resource.py 2>&1 | tee outputs/test_fusion_resource.txt
echo
python3 make_images.py
echo
echo "完成：outputs/ 存有真实运行输出，../images/ 存有 4 张 SVG。"
