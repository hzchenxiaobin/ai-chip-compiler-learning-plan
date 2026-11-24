#!/usr/bin/env bash
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$HERE/outputs"
python3 pass_bisect.py 2>&1 | tee "$HERE/outputs/report.txt"
