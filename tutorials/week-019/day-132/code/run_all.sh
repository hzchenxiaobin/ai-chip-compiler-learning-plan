#!/usr/bin/env bash
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
PY=python3
R="$HERE/outputs/report.txt"
mkdir -p "$HERE/outputs"
: > "$R"
PASS=0; FAIL=0
ok()  { echo "  [PASS] $1" | tee -a "$R"; PASS=$((PASS+1)); }
bad()  { echo "  [FAIL] $1" | tee -a "$R"; FAIL=$((FAIL+1)); }

echo "第 132 天：异步与同步模型——真机报告 $(date '+%Y-%m-%d %H:%M')" | tee -a "$R"
python3 async_model.py 2>&1 | tee -a "$R"
grep -q "总 60ms（调用方全程阻塞）" "$R" && ok "E1 同步基线（60ms 阻塞）" || bad "E1 缺失"
grep -q "0.01ms（入队即返回" "$R" && ok "E2 launch 立即返回（0.01ms）" || bad "E2 launch 失败"
grep -q "双 stream 并行" "$R" && ok "E2 双 stream 并行验证" || bad "E2 并行失败"
grep -q "场景 C（池化内存的交互" "$R" && ok "E3 依赖与同步点分析（含 D131 伏笔）" || bad "E3 缺失"
grep -q "Compiler/Runtime 分工（异步版）" "$R" && ok "分工说明产出（计划条目）" || bad "分工缺失"
grep -q "加速比：1.4x" "$R" && ok "双 stream 加速比 1.4x 实测" || bad "加速比缺失"
echo "" | tee -a "$R"; echo "汇总：PASS $PASS / FAIL $FAIL" | tee -a "$R"
exit $([ "$FAIL" -eq 0 ] && echo 0 || echo 1)
