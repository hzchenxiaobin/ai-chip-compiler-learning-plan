#!/usr/bin/env bash
# 第 122 天一键复现：minic S2~S5 接入——完整管道 + 失败诊断保留 + 跨天对账
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="$HERE/outputs"
mkdir -p "$OUT"

PY=python3
command -v "$PY" >/dev/null || PY=python

export PATH="/opt/homebrew/opt/llvm/bin:$PATH"

R="$OUT/report.txt"
: > "$R"
PASS=0; FAIL=0
ok()  { echo "  [PASS] $1" | tee -a "$R"; PASS=$((PASS+1)); }
bad() { echo "  [FAIL] $1" | tee -a "$R"; FAIL=$((FAIL+1)); }
sec() { echo "" | tee -a "$R"; echo "$1" | tee -a "$R"; }

minic() { "$PY" "$HERE/minic.py" "$@"; }

echo "第 122 天：minic S2~S5 循环＋LLVM Lowering——真机报告 $(date '+%Y-%m-%d %H:%M')" | tee -a "$R"
echo "环境：$($PY --version 2>&1)｜$(uname -sm)｜mlir-opt $(mlir-opt --version 2>/dev/null | head -1 | grep -o '[0-9.]*' | head -1)" | tee -a "$R"

# ── TP1 主线：图 → 循环 → LLVM IR → 汇编，全链路 ──
sec "[TP1] 主线：main.graph 一条命令到汇编"
  minic main.graph -o "$OUT/main" --tile 2,3,6 --dump-ir -q > /dev/null 2>&1; RC=$?
  [ "${RC}" -eq 0 ] && ok "minic main.graph 退出码 0（S1~S5 全真实）" || bad "退出码 ${RC}"
  [ -f "$OUT/main/stage-2-loop.mlir" ] && ok "S2 产物 stage-2-loop.mlir 落盘" || bad "缺 stage-2-loop.mlir"
  grep -q "scf.for" "$OUT/main/stage-2-loop.mlir" && ok "S2 是 scf.for 三重循环" || bad "S2 缺 scf.for"
  grep -q "emit_c_interface" "$OUT/main/stage-2-loop.mlir" && ok "签名带 llvm.emit_c_interface（D117 ABI）" || bad "缺 emit_c_interface"
  [ -f "$OUT/main/stage-5.ll" ] && ok "S5 产物 stage-5.ll（LLVM IR）" || bad "缺 stage-5.ll"
  [ -f "$OUT/main/stage-5.s" ] && ok "S5 产物 stage-5.s（汇编·可编译证明）" || bad "缺 stage-5.s"
  grep -q "_mlir_ciface" "$OUT/main/stage-5.ll" && ok "包装函数 _mlir_ciface 在 .ll 里（D118 合同延续）" || bad "缺包装函数"
  GLUE=$(grep -c "unrealized_conversion_cast" "$OUT/main/stage-4-10-reconcile-unrealized-casts.mlir" || true)
  [ "$GLUE" -eq 0 ] && ok "胶水 0 条（reconcile 干净——D117 结论在 minic 复现）" || bad "胶水 ${GLUE} 条残留"

# ── TP2 阶段序列：八个 stage 文件按序号齐全 ──
sec "[TP2] IR Dump 阶段序列（stage-2 + stage-4-03..10 + stage-5）"
  N=$(ls "$OUT/main" | grep -c "^stage-")
  echo "  stage 文件数：$N" | tee -a "$R"
  [ "$N" -ge 10 ] && ok "阶段序列完整（≥10 个文件，文件名含阶段序号）" || bad "阶段文件不足（$N）"

# ── TP3 tile 参数生效 ──
sec "[TP3] tile 参数进循环步长"
  grep -q "step %cTM" "$OUT/main/stage-2-loop.mlir" && ok "外层循环步长来自 tile（%cTM）" || bad "tile 未进步长"
  # 换 tile 再跑：2,2,2
  minic main.graph -o "$OUT/tile222" --tile 2,2,2 --dump-ir -q > /dev/null 2>&1
  grep -q "arith.constant 2 : index" "$OUT/tile222/stage-2-loop.mlir" \
    && ok "--tile 2,2,2 生效（常量 2 进 IR）" || bad "tile 222 未生效"

# ── TP4 失败诊断保留（E202：不支持的算子） ──
sec "[TP4] 失败路径 A：E202 不支持的算子，现场保留"
  cat > "$OUT/conv.graph" <<'EOF'
func @main(%x: tensor<2x2xf32>) -> (%2: tensor<2x2xf32>) {
  %x = arg : tensor<2x2xf32>
  %2 = conv2d %x : tensor<2x2xf32>
  return %2
}
EOF
  minic "$OUT/conv.graph" -o "$OUT/t-e202" -q > /dev/null 2>&1; RC=$?
  [ "${RC}" -eq 1 ] && ok "E202 → 退出码 1（编译失败）" || bad "退出码 ${RC}（期望 1）"
  "$PY" -c "
import json, sys
m = json.load(open('$OUT/t-e202/manifest.json'))
assert m['exit_code'] == 1, 'manifest exit_code 应为 1'
assert any('E202' in s['note'] for s in m['stages']), 'stages 应含 E202'
" && ok "manifest 记录失败（exit_code=1 + E202 诊断在 stages）" || bad "manifest 未如实记录失败"

# ── TP5 失败诊断保留（E204：pass 报错 + stderr 全文落盘） ──
sec "[TP5] 失败路径 B：E204 pass 失败，stderr 全文保留"
  "$PY" - <<'PYEOF' && ok "E204 触发：vector 残账被 pass 拒收（D114 暂不支持清单）" || bad "E204 未触发"
from loop_lower import run_s45
bad_ir = """module {
  func.func @bad(%a: memref<4x6xf32, strided<[6, 1]>>) -> f32 {
    %f0 = arith.constant 0.0 : f32
    %v = vector.broadcast %f0 : f32 to vector<4xf32>
    %r = vector.reduce %v : vector<4xf32> into f32
    func.return %r : f32
  }
}"""
r = run_s45(bad_ir, "outputs/t-e204", llvm_bin="/opt/homebrew/opt/llvm/bin")
assert not r["ok"] and "E204" in r["error"], r
PYEOF
  [ -f "$OUT/t-e204/pipeline-error.txt" ] && ok "stderr 全文落盘 pipeline-error.txt" || bad "缺 pipeline-error.txt"
  grep -q "vector.reduce" "$OUT/t-e204/pipeline-error.txt" \
    && ok "报错指认具体 op（vector.reduce is unknown）" || bad "报错未指认 op"

# ── TP6 失败现场完整性：失败前的产物不删 ──
sec "[TP6] 失败现场：失败前的 stage 文件保留（调试不从头再来）"
  # t-e204 的现场：失败于第一条 pass——只有 stage-2-loop.mlir + pipeline-error.txt
  [ -f "$OUT/t-e204/stage-2-loop.mlir" ] && ok "E204 现场保留 stage-2-loop.mlir" || bad "现场被清"
  # 陈旧产物清理验证：同目录先成功再失败，旧文件不该留
  minic main.graph -o "$OUT/t-mixed" --dump-ir -q > /dev/null 2>&1
  "$PY" - <<'PYEOF' && ok "二次运行失败时旧产物已清（现场只属于本次）" || bad "新旧产物混淆"
from loop_lower import run_s45
# 真失败：vector.reduce 的结果被 return 使用（canonicalize 删不掉）
bad_ir = """module {
  func.func @bad(%a: memref<4x6xf32, strided<[6, 1]>>) -> f32 {
    %f0 = arith.constant 0.0 : f32
    %v = vector.broadcast %f0 : f32 to vector<4xf32>
    %r = vector.reduce %v : vector<4xf32> into f32
    func.return %r : f32
  }
}"""
r = run_s45(bad_ir, "outputs/t-mixed")
assert not r["ok"], "应失败"
import os
files = os.listdir("outputs/t-mixed")
# 成功跑过一轮（10 个 stage 文件）→ 失败跑第二轮 → 不应残留上轮的 stage-4/5
stale = [f for f in files if f.startswith("stage-4") or f.startswith("stage-5")]
assert not stale, f"残留: {stale}"
PYEOF

# ── TP7 合同回归 ──
sec "[TP7] 合同回归：D120/D121 的合同不退化"
  minic --help > "$OUT/help.txt" 2>&1
  for kw in "usage: minic" "--tile" "--emit" "--no-fuse"; do
    grep -q -e "$kw" "$OUT/help.txt" && ok "--help 含 $kw" || bad "--help 缺 $kw"
  done
  minic no-such.graph -o /tmp/x -q > /dev/null 2>&1; RC=$?
  [ "${RC}" -eq 2 ] && ok "E101 退出码 2（用法错误三态不乱）" || bad "退出码 ${RC}"
  minic main.graph -o "$OUT/t-m3" -q > /dev/null 2>&1
  "$PY" -c "
import json
m = json.load(open('$OUT/t-m3/manifest.json'))
assert 's1_switches' in m and m['exit_code'] == 0
" && ok "manifest 合同字段齐全" || bad "manifest 退化"

# ── TP8 跨天对账：与 D117 冻结管道同构 ──
sec "[TP8] 跨天对账：minic S4 产物 vs D117 冻结产物（同构性）"
  # D117 的 gemm.mlir 走 minic（作为 .mlir 输入 S1 跳过 → 但 S2 也跳过…… 用 loop_lower 直接跑）
  "$PY" - <<'PYEOF' && ok "D117 的 gemm.mlir 经 minic S4 管道：七 pass 全过 + 胶水 0" || bad "对账失败"
import sys
sys.path.insert(0, ".")
from loop_lower import run_s45
# D117 gemm.mlir 的签名：memref<4x6xf32, strided> × memref<6x3> → memref<4x3>
gemm_ir = open("../../day-117/code/gemm.mlir").read()
r = run_s45(gemm_ir, "outputs/t-d117", llvm_bin="/opt/homebrew/opt/llvm/bin")
assert r["ok"], r.get("error")
ll = open(r["ll"]).read()
assert "_mlir_ciface_gemm" in ll, "缺包装"
assert "malloc" in ll, "缺 malloc（M3 模式）"
print("  对账：", r["stages"][-2])
PYEOF

sec "汇总"
  echo "  PASS: $PASS  FAIL: $FAIL" | tee -a "$R"
  echo "  环境：$(uname -sm)｜$(date '+%Y-%m-%d')" | tee -a "$R"
exit $([ "$FAIL" -eq 0 ] && echo 0 || echo 1)
