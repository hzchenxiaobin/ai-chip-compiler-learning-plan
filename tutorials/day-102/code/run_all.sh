#!/usr/bin/env bash
# 第 102 天：一键复现全部输出记录
set -euo pipefail
cd "$(dirname "$0")"
python3 timeline.py
echo
echo "全部输出已在 code/outputs/ 下生成："
ls outputs/
