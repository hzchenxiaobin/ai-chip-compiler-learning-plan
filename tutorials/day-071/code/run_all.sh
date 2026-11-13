#!/usr/bin/env bash
# run_all.sh —— 第 71 天一键复跑：主实验 → 验收测试 → 重新生成 4 张 SVG
set -euo pipefail
cd "$(dirname "$0")"

echo "== 1/3 主实验 flops_bytes_lab.py =="
python3 flops_bytes_lab.py | tee outputs/flops_bytes_lab.txt

echo ""
echo "== 2/3 验收测试 test_flops_bytes.py =="
python3 test_flops_bytes.py | tee outputs/test_flops_bytes.txt

echo ""
echo "== 3/3 重新生成 4 张 SVG =="
python3 make_images.py

echo ""
echo "全部完成：主实验 + 测试 + 图片。输出存于 outputs/。"
