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

echo "第 131 天：内存分配与复用——真机报告 $(date '+%Y-%m-%d %H:%M')" | tee -a "$R"
echo "环境：$($PY --version 2>&1)｜$(uname -sm)" | tee -a "$R"

sec "[TP1~TP3] 三实验：泄漏实测/池化/生命周期"
  "$PY" allocator.py 2>&1 | tee -a "$R"
  grep -q "理论泄漏：2000×48B" "$R" && ok "E1 泄漏机制确认（2000 次 94KB——真实服务 48MB/s）" || bad "E1 缺失"
  grep -q "hit=99 miss=1" "$R" && ok "E2 池化复用 99%（100 次只分配 1 次）" || bad "E2 池化失败"
  grep -q "48 B（裸模式 = 100×48=4800B）" "$R" && ok "E2 分配量对比：48B vs 4800B（100 倍）" || bad "对比缺失"
  grep -q "混合 shape 5 次：hit=3 miss=2" "$R" && ok "E2 混合 shape 分桶命中" || bad "混合缺失"
  grep -q "destroy 后池内：0" "$R" && ok "E3 生命周期完整（destroy 全清）" || bad "生命周期缺失"
  grep -q "债务状态：已结清" "$R" && ok "D118 malloc 债务结清声明" || bad "结账缺失"

sec "汇总"
  echo "  PASS: $PASS  FAIL: $FAIL" | tee -a "$R"
exit $([ "$FAIL" -eq 0 ] && echo 0 || echo 1)
