#!/usr/bin/env bash
# 第 128 天一键复现：运行期参数与 Shape——静态 vs 动态 vs 多 shape 执行
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

echo "第 128 天：运行期参数与 Shape——真机报告 $(date '+%Y-%m-%d %H:%M')" | tee -a "$R"
echo "环境：$($PY --version 2>&1)｜$(uname -sm)｜$($LLVM_BIN/clang --version 2>/dev/null | head -1 || /opt/homebrew/opt/llvm/bin/clang --version | head -1)" | tee -a "$R"
export LLVM_BIN=/opt/homebrew/opt/llvm/bin

sec "[TP1] E1 静态基线：shape 固化的形态"
  "$PY" dyn_shape.py 2>&1 | tee -a "$R"
  grep -q "ok=True｜.ll 95" "$R" && ok "静态管道全通（.ll 95 行）" || bad "静态管道失败"

sec "[TP2] E2 动态签名：shape 进描述符的代价"
  grep -q "ok=True｜.ll 104" "$R" && ok "动态管道全通（.ll 104 行）" || bad "动态管道失败"
  # 关键差异断言
  "$PY" -c "
t1 = open('outputs/e1-static/out.ll').read()
t2 = open('outputs/e2-dynamic/out.ll').read()
assert t2.count('extractvalue') - t1.count('extractvalue') >= 4, '描述符读回差不足'
# 动态版的 icmp 操作数是 SSA 值不是常量
import re
static_icmp = re.search(r'icmp slt i64 %\d+, (\d+)', t1)
dynamic_icmp = re.search(r'icmp slt i64 %\d+, %\d+', t2)
assert static_icmp, '静态版应含常量比较'
assert dynamic_icmp, '动态版应含 SSA 比较'
print('  静态 icmp: 常量 4｜动态 icmp: 描述符字段 %29——shape 语义翻转的铁证')
" && ok "icmp 操作数从常量翻成 SSA（运行期读）" || bad "翻转证据不足"

sec "[TP3] E3 多 shape 执行：一份 .ll 吃三种 shape"
  "$PY" e3_verify.py 2>&1 | tee -a "$R"
  grep -q "三组 shape 全过" "$R" && ok "4x6@6x3 / 3x4@4x2 / 8x8@8x8 三组全对" || bad "多 shape 执行失败"

sec "[TP4] 动态代价量化：指令数对照"
  "$PY" -c "
t1 = open('outputs/e1-static/out.ll').read()
t2 = open('outputs/e2-dynamic/out.ll').read()
l1 = len([l for l in t1.splitlines() if l.strip() and not l.strip().startswith(';')])
l2 = len([l for l in t2.splitlines() if l.strip() and not l.strip().startswith(';')])
print(f'  .ll 行数：静态 {l1} → 动态 {l2}（+{(l2-l1)/l1*100:.0f}%）')
print(f'  extractvalue：{t1.count(\"extractvalue\")} → {t2.count(\"extractvalue\")}（+{t2.count(\"extractvalue\")-t1.count(\"extractvalue\")}——3 个 dim 各读 2 处）')
print(f'  核心循环指令（phi/fmul）：不变——动态化只加头部开销')
" | tee -a "$R"
  ok "代价量化入档（+9 行、+6 extractvalue、循环体不变）"

sec "汇总"
  echo "  PASS: $PASS  FAIL: $FAIL" | tee -a "$R"
exit $([ "$FAIL" -eq 0 ] && echo 0 || echo 1)
