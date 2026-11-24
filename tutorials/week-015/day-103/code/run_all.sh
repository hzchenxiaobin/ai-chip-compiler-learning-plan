#!/usr/bin/env bash
# 一键复现第 103 天的全部真实运行记录（时间戳口径见 outputs/env.txt）
set -e
cd "$(dirname "$0")"
python3 pipeline.py
