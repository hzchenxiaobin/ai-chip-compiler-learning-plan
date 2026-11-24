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

echo "第 130 天：通用实现回退——真机报告 $(date '+%Y-%m-%d %H:%M')" | tee -a "$R"
echo "环境：$($PY --version 2>&1)｜$(uname -sm)" | tee -a "$R"

sec "[TP1~TP4] 四条路径：正常/校验/回退/上抛"
  "$PY" fallback.py 2>&1 | tee -a "$R"
  grep -q "4x6x3 命中特化: PASS" "$R" && ok "E1 正常路径（命中特化）" || bad "E1 失败"
  grep -q "3x5x2 miss 动态: PASS" "$R" && ok "E1 正常路径（miss 动态）" || bad "E1 miss 失败"
  grep -q "四种非法输入全部 fail-fast" "$R" && ok "E2 校验路径（4 种 E301 拒收）" || bad "E2 校验缺失"
  grep -q "特化崩溃→动态重试: PASS" "$R" && ok "E3 回退路径（E302→W301 降级重试）" || bad "E3 回退失败"
  grep -q "两层全崩→上抛 E303" "$R" && ok "E4 不可恢复路径（E303 上抛）" || bad "E4 上抛失败"
  grep -q "三件套齐了" "$R" && ok "三件套完整性断言" || bad "三件套缺失"

sec "汇总"
  echo "  PASS: $PASS  FAIL: $FAIL" | tee -a "$R"
exit $([ "$FAIL" -eq 0 ] && echo 0 || echo 1)
