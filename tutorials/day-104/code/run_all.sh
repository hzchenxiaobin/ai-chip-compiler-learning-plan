#!/usr/bin/env bash
# D104 一键复现：重跑本文全部实验记录（outputs/）并重新生成 3 张手绘图。
set -euo pipefail
cd "$(dirname "$0")"

mkdir -p outputs
python3 resource_filter.py --exp all --outdir outputs

{
  echo "环境与口径"
  echo "----------"
  python3 --version
  uname -m
  uname -s
  date "+%Y-%m-%d"
  echo
  echo "命令：python3 resource_filter.py --exp all --outdir outputs"
  echo "预算：256 KiB（示例值，不代表任何具体芯片）；DMA 对齐 32 B"
} > outputs/env.txt

python3 gen_images.py

echo ""
echo "全部完成：outputs/ 下 5 份记录 + env.txt，images/ 下 3 张手绘图"
