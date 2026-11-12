#!/usr/bin/env bash
# Day 43 TDD 轨迹一键重放：同一张 15 行测试表，先后拷问三个版本的实现。
#   v0 stub   —— 实现缺席，15 行全红（EXC），证明测试真的在测东西；
#   v1 直觉版 —— 12/15，红在 T11/T14/T15（两条"想当然"被测试当场抓住）；
#   v2 最终版 —— 15/15（code/ 目录下的 matmul_infer.py，R0~R4 规则表）。
# 重放目录用 /tmp/day043/tdd（与 run_all.sh 的 /tmp/day043 同一片临时区）。
set -u
cd "$(dirname "$0")"

REPLAY=/tmp/day043/tdd
rm -rf "$REPLAY"
mkdir -p "$REPLAY/v0" "$REPLAY/v1"

for v in v0 v1; do
  cp test_matmul_infer.py "matmul_infer_${v}.py" "$REPLAY/$v/"
  mv "$REPLAY/$v/matmul_infer_${v}.py" "$REPLAY/$v/matmul_infer.py"
done

echo "== [1/3] v0 stub（测试先行，实现缺席）=="
(cd "$REPLAY/v0" && python3 test_matmul_infer.py)
echo "rc=$?"

echo
echo "== [2/3] v1 直觉版（batch 抄 lhs、不查前提）=="
(cd "$REPLAY/v1" && python3 test_matmul_infer.py)
echo "rc=$?"

echo
echo "== [3/3] v2 最终版（R0~R4 规则表）=="
python3 test_matmul_infer.py
echo "rc=$?"
