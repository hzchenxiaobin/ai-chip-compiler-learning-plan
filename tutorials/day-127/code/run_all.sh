#!/usr/bin/env bash
# 第 127 天一键复现：职责划分表 + 运行期行为实测
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="$HERE/outputs"
mkdir -p "$OUT"
PY=python3
R="$OUT/report.txt"
: > "$R"
PASS=0; FAIL=0
ok()  { echo "  [PASS] $1" | tee -a "$R"; PASS=$((PASS+1)); }
bad() { echo "  [FAIL] $1" | tee -a "$R"; FAIL=$((FAIL+1)); }
sec() { echo "" | tee -a "$R"; echo "$1" | tee -a "$R"; }

echo "第 127 天：Compiler/Runtime 职责——真机报告 $(date '+%Y-%m-%d %H:%M')" | tee -a "$R"
echo "环境：$($PY --version 2>&1)｜$(uname -sm)" | tee -a "$R"

sec "[TP1] 职责划分表：11 个决策点"
  "$PY" responsibility.py > /dev/null 2>&1; RC=$?
  [ "${RC}" -eq 0 ] && ok "职责表生成＋自检 5/5" || bad "职责表自检失败"
  grep -q "COMPILE" "$OUT/responsibility-table.txt" && ok "表含 COMPILE 归属" || bad "缺 COMPILE"
  grep -q "malloc 债务" "$OUT/responsibility-table.txt" && ok "malloc 债务条目在表" || bad "缺 malloc 条目"

sec "[TP2] 运行期行为实测：malloc 的证据（分配真在运行期发生）"
  # 从 D124/D126 的冻结产物里找证据——kernel 每次调用都 malloc
  LL=""
  for CAND in "$HERE/../../day-124/code/outputs/e2e-run/stage-5.ll" \
              "$HERE/../../day-126/code/outputs/e2e-rebuild/stage-5.ll"; do
    [ -f "$CAND" ] && LL="$CAND" && break
  done
  if [ -n "$LL" ]; then
    N_MALLOC=$(grep -c "call ptr @malloc" "$LL"; true)
    [ "${N_MALLOC}" -ge 1 ] && ok "stage-5.ll 含 ${N_MALLOC} 处 malloc（分配发生在 kernel 运行时）" || bad "无 malloc"
    N_FREE=$(grep -c "call void @free\|call void @llvm.free" "$LL"; true)
    [ "${N_FREE}" -eq 0 ] && ok "零处 free——「释放=NONE」的铁证" || bad "意外发现 free"
  else
    bad "找不到 stage-5.ll 证据"
  fi

sec "[TP3] 编译期证据：shape 固化在签名里（S2 的 MLIR 签名）"
  MLIR2="$HERE/../../day-126/code/outputs/e2e-rebuild/stage-2-loop.mlir"
  if [ -f "$MLIR2" ]; then
    grep -q "strided<\[6, 1\]>" "$MLIR2" && ok "stride 编译期固化（S2 签名 strided<[6,1]>）" || bad "stride 不在 S2 签名"
    grep -q "memref<4x3xf32>" "$MLIR2" && ok "输出 shape 编译期固化（memref<4x3>）" || bad "输出 shape 不固化"
    # .ll 侧：shape 变成循环边界常量（icmp slt i64 %38, 4 的 4 = M）
    if [ -n "$LL" ]; then
      grep -q "icmp slt i64" "$LL" && ok "shape 内联成 .ll 的循环边界常量（icmp slt）" || bad "边界常量缺失"
    fi
  else
    bad "无 stage-2-loop.mlir 证据"
  fi

sec "[TP4] 决策点与下周排期的对应"
  "$PY" -c "
table = open('$OUT/responsibility-table.txt').read()
targets = ['D128 运行期参数', 'D129 特化', 'D130 回退', 'D131 内存', 'D132 同步']
for t in targets:
    assert t in table, t
print('  五个下周主题与决策点一一对应')
" && ok "下周排期对应完整" || bad "排期对应缺失"

sec "汇总"
  echo "  PASS: $PASS  FAIL: $FAIL" | tee -a "$R"
exit $([ "$FAIL" -eq 0 ] && echo 0 || echo 1)
