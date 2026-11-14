#!/usr/bin/env bash
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="$HERE/outputs"
PY=python3
R="$OUT/report.txt"
: > "$R"
PASS=0; FAIL=0
ok()  { echo "  [PASS] $1" | tee -a "$R"; PASS=$((PASS+1)); }
bad() { echo "  [FAIL] $1" | tee -a "$R"; FAIL=$((FAIL+1)); }
sec() { echo "" | tee -a "$R"; echo "$1" | tee -a "$R"; }

echo "第 129 天：静态 Shape 特化——真机报告 $(date '+%Y-%m-%d %H:%M')" | tee -a "$R"
echo "环境：$($PY --version 2>&1)｜$(uname -sm)" | tee -a "$R"

sec "[TP1] E1 特化收益：同 shape 静态 O2 vs 动态 O2 的优化空间"
  "$PY" specialize.py 2>&1 | tee -a "$R"
  grep -q "fmul 2 → 18" "$R" && ok "特化给 O2 的展开空间：fmul 2→18（9 倍）" || bad "展开对比缺失"
  grep -q "静态+O2：fmul=18 phi=1" "$R" && ok "静态特化产物指标入档" || bad "静态指标缺失"

sec "[TP2] E2 两层分发：命中特化/miss 兜底"
  grep -q "4x6x3（命中特化）: PASS" "$R" && ok "特化层命中执行正确" || bad "特化层执行失败"
  grep -q "8x8x8（命中特化）: PASS" "$R" && ok "第二特化命中正确" || bad "第二特化失败"
  grep -q "5x7x2（miss→动态兜底）: PASS" "$R" && ok "未注册 shape 动态兜底正确" || bad "兜底失败"
  grep -q "hit': 2, 'miss': 1" "$R" && ok "分发统计正确（2 hit + 1 miss）" || bad "统计异常"

sec "[TP3] E3 缓存雏形：幂等与产物大小"
  grep -q "compiled 2 → 2（幂等）" "$R" && ok "重复 register 幂等（缓存语义）" || bad "不幂等"
  grep -q "spec-4x6x3" "$R" && ok "产物大小记录入档（计划条目要求）" || bad "大小缺失"

sec "汇总"
  echo "  PASS: $PASS  FAIL: $FAIL" | tee -a "$R"
exit $([ "$FAIL" -eq 0 ] && echo 0 || echo 1)
