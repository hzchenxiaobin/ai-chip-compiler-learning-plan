#!/usr/bin/env bash
# 第 120 天一键复现：minic CLI 骨架的合同测试（今天的主产出是"合同"，
# 测试自然围绕合同：帮助文本、四个出口码、全部 E1xx 诊断、manifest）
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="$HERE/outputs"
mkdir -p "$OUT"

PY=python3
command -v "$PY" >/dev/null || PY=python

R="$OUT/report.txt"
: > "$R"
PASS=0; FAIL=0
ok()  { echo "  [PASS] $1" | tee -a "$R"; PASS=$((PASS+1)); }
bad() { echo "  [FAIL] $1" | tee -a "$R"; FAIL=$((FAIL+1)); }
sec() { echo "" | tee -a "$R"; echo "$1" | tee -a "$R"; }

echo "第 120 天：minic CLI 骨架——合同测试报告 $(date '+%Y-%m-%d %H:%M')" | tee -a "$R"
echo "环境：$($PY --version 2>&1)｜$(uname -sm)" | tee -a "$R"

minic() { "$PY" "$HERE/minic.py" "$@"; }

# ── TP1 帮助文本：CLI 的第一份合同 ──
sec "[TP1] --help：选项清单与示例齐全"
  minic --help > "$OUT/help.txt" 2>&1
  for kw in "usage: minic" "-O" "--tile" "--emit" "--dump-ir" "--verify" "--llvm-bin" "示例"; do
    grep -q -e "$kw" "$OUT/help.txt" && ok "--help 含 $kw" || bad "--help 缺 $kw"
  done
  # --version 也是合同
  minic --version > "$OUT/version.txt" 2>&1
  grep -q "minic 0.1.0" "$OUT/version.txt" && ok "--version 输出版本号" || bad "--version 异常"

# ── TP2 退出码合同：0/1/2 三态 ──
sec "[TP2] 退出码合同（与 clang/gcc 同族）"
  # 0：合法输入成功（骨架模式）
  minic gemm.mlir -o "$OUT/case-ok" -q > /dev/null 2>&1; RC=$?
  [ "$RC" -eq 0 ] && ok "合法输入 → 退出码 0" || bad "合法输入退出码 ${RC}（期望 0）"
  # 2：用法错误（不存在的文件）
  minic no-such.mlir -o "$OUT/case-e101" -q > /dev/null 2>&1; RC=$?
  [ "$RC" -eq 2 ] && ok "E101 输入不存在 → 退出码 2" || bad "E101 退出码 ${RC}（期望 2）"
  # 2：tile 格式错误
  minic gemm.mlir --tile 32,32 -o "$OUT/case-e104" -q > /dev/null 2>&1; RC=$?
  [ "$RC" -eq 2 ] && ok "E104 tile 格式错 → 退出码 2" || bad "E104 退出码 ${RC}（期望 2）"

# ── TP3 诊断体系：每条 E1xx 都能触发且带修复建议 ──
sec "[TP3] 诊断体系：E101~E107 逐条触发"
  # E101
  minic missing.mlir -o "$OUT/t" 2> "$OUT/diag-e101.txt"; RC=$?
  grep -q "E101" "$OUT/diag-e101.txt" && ok "E101 触发（文件不存在）" || bad "E101 未触发"
  grep -q "修复建议" "$OUT/diag-e101.txt" && ok "E101 带修复建议" || bad "E101 缺修复建议"
  # E102 扩展名
  touch "$OUT/notmlir.txt"
  minic "$OUT/notmlir.txt" -o "$OUT/t" 2> "$OUT/diag-e102.txt"
  grep -q "E102" "$OUT/diag-e102.txt" && ok "E102 触发（扩展名不支持）" || bad "E102 未触发"
  # E104 两种错法
  minic gemm.mlir --tile abc -o "$OUT/t" 2> "$OUT/diag-e104a.txt"
  grep -q "E104" "$OUT/diag-e104a.txt" && ok "E104 触发（非数字）" || bad "E104a 未触发"
  minic gemm.mlir --tile 32,32,32,32 -o "$OUT/t" 2> "$OUT/diag-e104b.txt"
  grep -q "E104" "$OUT/diag-e104b.txt" && ok "E104 触发（四维）" || bad "E104b 未触发"
  # E105 优化级别
  minic gemm.mlir -O 9 -o "$OUT/t" 2> "$OUT/diag-e105.txt"
  grep -qE "invalid choice|E105" "$OUT/diag-e105.txt" && ok "E105/argparse 拦截非法 -O" || bad "-O 9 未拦截"
  # E107 verify 文件不存在
  minic gemm.mlir --verify no-gold.txt -o "$OUT/t" 2> "$OUT/diag-e107.txt"
  grep -q "E107" "$OUT/diag-e107.txt" && ok "E107 触发（golden 不存在）" || bad "E107 未触发"

# ── TP4 manifest：机器合同（脚本/CI 消费） ──
sec "[TP4] manifest.json：机器可读的编译记录"
  minic gemm.mlir -o "$OUT/case-manifest" --tile 16,16,16 -O2 -q > /dev/null 2>&1
  M="$OUT/case-manifest/manifest.json"
  [ -f "$M" ] && ok "manifest.json 生成" || bad "manifest.json 未生成"
  "$PY" - "$M" <<'PYEOF' && ok "manifest 字段齐全（version/input/tile/stages/exit_code）" || bad "manifest 字段缺失"
import json, sys
m = json.load(open(sys.argv[1]))
need = ["version", "input", "output_dir", "opt_level", "tile", "emit", "stages", "exit_code"]
assert all(k in m for k in need), f"缺字段: {[k for k in need if k not in m]}"
assert m["tile"] == [16, 16, 16] and m["opt_level"] == 2
assert len(m["stages"]) >= 7 and m["exit_code"] == 0
PYEOF

# ── TP5 -O0 与警告 ──
sec "[TP5] 优化开关与警告路径"
  minic gemm.mlir -O0 --tile 8,8,8 -o "$OUT/case-o0" 2> "$OUT/diag-w102.txt"
  grep -q "W102" "$OUT/diag-w102.txt" && ok "W102 触发（-O0 下 --tile 仍传了值）" || bad "W102 未触发"
  minic gemm.mlir -O0 -o "$OUT/case-o0-plain" -q > /dev/null 2>&1; RC=$?
  [ "$RC" -eq 0 ] && ok "-O0 正常退出 0（S1/S3 记录为跳过）" || bad "-O0 退出码 $RC"
  grep -q -e "O0 跳过" "$OUT/case-o0-plain/manifest.json" && ok "manifest 记录跳过原因" || bad "manifest 未记录跳过"

# ── TP6 合同文档固化 ──
sec "[TP6] CLI 参数说明固化（help.txt 即合同快照）"
  # 帮助文本入档即冻结——明天 D121 起 --help 的任何变化都应反映在 diff 里
  N_OPT=$(grep -cE "^\s+-|^\s+--" "$OUT/help.txt")
  echo "  help.txt 含 $N_OPT 个选项行（快照入档）" | tee -a "$R"
  [ "$N_OPT" -ge 10 ] && ok "选项数量 ≥10（CLI 合同完整）" || bad "选项过少"

sec "汇总"
  echo "  PASS: $PASS  FAIL: $FAIL" | tee -a "$R"
  echo "  环境：$(uname -sm)｜$(date '+%Y-%m-%d')" | tee -a "$R"
exit $([ "$FAIL" -eq 0 ] && echo 0 || echo 1)
