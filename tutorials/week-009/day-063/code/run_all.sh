#!/usr/bin/env bash
# run_all.sh —— 第 63 天（第 9 周复盘）一键复跑。
#
# 流程：
#   1  环境
#   2  review_lab.py：主实验——一个张量的六种身份 + 一条公式 + 三房间裁决
#   3  test_review.py：今天自己的验收测试（A–D 四段）
#   4  run_week_tests.sh：第 9 周全部测试（Day 57–62 + 今天，共 7 套）
#
# 用法：bash run_all.sh   （在 day-063/code/ 目录下）

set -u
cd "$(dirname "$0")"
OUT=outputs
mkdir -p "$OUT"

echo "== 环境 =="
python3 --version
python3 -c "import numpy; print('numpy', numpy.__version__)"
if command -v mlir-opt >/dev/null 2>&1; then
  mlir-opt --version | head -1
elif [ -x /usr/lib/llvm-18/bin/mlir-opt ]; then
  /usr/lib/llvm-18/bin/mlir-opt --version | head -1
else
  echo "mlir-opt 不可用（IR 裁决相关步骤将降级）"
fi
uname -m
echo

echo "== 1. review_lab.py：一个张量的六种身份（全真实运行）=="
python3 review_lab.py | tee "$OUT/review_lab.txt"
echo "exit=$?"
echo

echo "== 2. test_review.py：复盘验收测试（A–D 四段）=="
python3 test_review.py | tee "$OUT/test_review.txt"
echo "exit=$?"
echo

echo "== 3. run_week_tests.sh：第 9 周全部测试（Day 57–63，共 7 套）=="
mkdir -p "$OUT/week_tests"
bash run_week_tests.sh | tee "$OUT/week_tests/summary.txt"
echo "exit=$?"
echo

echo "run_all: 全部完成"
