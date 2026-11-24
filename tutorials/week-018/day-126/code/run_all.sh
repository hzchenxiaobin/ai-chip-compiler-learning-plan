#!/usr/bin/env bash
# 第 126 天一键复现：第 18 周复盘——干净重建 + 周账本
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
PY=python3
R="$HERE/outputs/report.txt"
mkdir -p "$HERE/outputs"
: > "$R"
echo "第 126 天：第 18 周复盘——真机报告 $(date '+%Y-%m-%d %H:%M')" | tee -a "$R"
echo "环境：$($PY --version 2>&1)｜$(uname -sm)" | tee -a "$R"
"$PY" week18_review.py 2>&1 | tee -a "$R"
