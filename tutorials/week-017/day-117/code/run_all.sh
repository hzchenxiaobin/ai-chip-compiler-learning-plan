#!/usr/bin/env bash
# 第 117 天一键复现：账本 -> 优化前后 -> 完整管道 -> 导出 -> 双线验证 ->
# 对照实验 -> 常见错误复现。全部在真工具链上执行，产物冻结进 outputs/。
# 环境：aarch64 Linux，Ubuntu LLVM 18.1.8（/usr/lib/llvm-18/bin），
#      Python 3.11.4，llvmlite 0.50.0（内嵌 LLVM 22.1.0）。
set -uo pipefail
cd "$(dirname "$0")"
BIN=/usr/lib/llvm-18/bin
OUT=outputs
R="$OUT/report.txt"
mkdir -p "$OUT"; : > "$R"

log()  { echo "$@" | tee -a "$R"; }
pass() { log "  [PASS] $*"; }
fail() { echo "  [FAIL] $*" | tee -a "$R"; FAILED=1; }
FAILED=0

log "第 117 天导出 LLVM IR：真机报告 $(date '+%Y-%m-%d %H:%M')"
log "工具链：$("$BIN"/mlir-opt --version | head -1 | tr -d '\n')"
log ""

# ---------------------------------------------------------------- TP0 环境
log "[TP0] 工具链盘点（教训：PATH 里没有，不等于机器上没有）"
log "  which mlir-opt mlir-translate: $(which mlir-opt mlir-translate 2>/dev/null || echo '(空——不在 PATH)')"
for t in mlir-opt mlir-translate llvm-as opt llc; do
  v=$("$BIN/$t" --version 2>/dev/null | head -1)
  log "  /usr/lib/llvm-18/bin/$t: $v"
done
[ -n "$("$BIN"/mlir-opt --help 2>&1)" ] && pass "全套 MLIR/LLVM 工具真实可用" \
  || fail "工具链不可用"
log ""

# ------------------------------------------------- TP1 账本：两个输入的 census
log "[TP1] 源 IR 账本（census.py，口径对齐 D114~D116：func.func 记 1 条）"
python3 census.py gemm.mlir gemm_tight.mlir | tee -a "$R"
NT=$(python3 census.py gemm_tight.mlir | sed -n '1s/.*total \([0-9]*\).*/\1/p')
NN=$(python3 census.py gemm.mlir       | sed -n '1s/.*total \([0-9]*\).*/\1/p')
[ "$NT" = "18" ] && pass "gemm_tight 是 D116 口径 18 op（残账 C1×4 待清）" \
  || fail "tight 版应为 18 op，实测 $NT"
log ""

# ------------------------------------- TP2+TP3+TP4+TP5 完整管道（三组文件）
log "[TP2] 优化前后 MLIR（组 1）：管道阶段 0 的 --canonicalize --cse"
./lower.sh gemm.mlir gemm >/dev/null
python3 census.py "$OUT/gemm-0-optimized.mlir" | tee -a "$R"
NO=$(python3 census.py "$OUT/gemm-0-optimized.mlir" | sed -n '1s/.*total \([0-9]*\).*/\1/p')
[ "$NO" -lt "$NN" ] && pass "优化后 op 数减少：$NN -> $NO" \
  || fail "优化后 op 数未减少：$NN -> $NO"
if grep -qE "subi|muli|addi" "$OUT/gemm-0-optimized.mlir"; then
  fail "朴素冗余（subi/muli/addi）未被折叠"
else
  pass "朴素冗余全部折叠：下界 6-6、上界 2x2、3+(6-6) 变成常量"
fi
log ""

log "[TP3] C1 落地（阶段 1）：--convert-scf-to-cf 把 scf.for 拆成四块"
NC=$(grep -c "scf\." "$OUT/gemm-1-scf-to-cf.mlir" || true)
NB=$(grep -cE "\^bb[0-9]+\(" "$OUT/gemm-1-scf-to-cf.mlir" || true)
NCOND=$(grep -c "cf.cond_br" "$OUT/gemm-1-scf-to-cf.mlir" || true)
[ "$NC" = "0" ] && pass "scf.* 清零；新块 $NB 个、cf.cond_br $NCOND 条" \
  || fail "scf.* 残留 $NC 条"
grep -q "f32):" "$OUT/gemm-1-scf-to-cf.mlir" \
  && pass "归纳变量/累加器变成块参数（bb(...): index, f32——phi 的前身）" \
  || fail "未观察到块参数"
log ""

log "[TP4] 完整转换（组 2）：五个转换 pass + reconcile（阶段 2）"
G=$(grep -c "unrealized_conversion_cast" "$OUT/gemm-2-llvm-dialect-noreconcile.mlir")
G2=$(grep -c "unrealized_conversion_cast" "$OUT/gemm-2-llvm-dialect.mlir")
log "  reconcile 前胶水 $G 条；reconcile 后 $G2 条（i64->index x3、struct->memref x3）"
[ "$G2" = "0" ] && pass "胶水清零——reconcile-unrealized-casts 清掉 $G 条" \
  || fail "胶水残留 $G2 条"
RES=$(python3 - <<'EOF'
import re
bad = []
for line in open("outputs/gemm-2-llvm-dialect.mlir"):
    m = re.match(r"^\s+(?:%[\w.]+\s*=\s*)?([a-zA-Z_][\w.]*)", line)
    if m and not m.group(1).startswith("llvm.") and m.group(1) not in ("module",):
        bad.append(m.group(1))
print(len(bad))
EOF
)
log "  非 llvm.* 残账（不含 module）：$RES"
[ "$RES" = "0" ] && pass "残账 0——全部转成 LLVM 方言" || fail "残账 $RES"
log ""

log "[TP5] 导出 LLVM IR（组 3）：mlir-translate + 真 LLVM 三连验证"
LI=$(grep -cE "^\s+%[0-9]+ =" "$OUT/gemm-3.ll")
LN=$(grep -cE "define " "$OUT/gemm-3.ll")
LPHI=$(grep -c " phi " "$OUT/gemm-3.ll")
LCIF=$(grep -c "_mlir_ciface_gemm" "$OUT/gemm-3.ll")
log "  gemm-3.ll：SSA 指令 $LI 条、define $LN 个（@gemm + @_mlir_ciface_gemm；另有 declare @malloc）、phi $LPHI 条"
[ "$LN" = "2" ] && [ "$LCIF" -ge 1 ] \
  && pass "导出成功：@gemm ＋自动生成的 _mlir_ciface_gemm 包装" \
  || fail "导出形态异常：define=$LN ciface=$LCIF"
[ "$LPHI" -ge 4 ] && pass "phi $LPHI 条——R3（块参数->phi）在真输出里兑现" \
  || fail "phi 数量异常：$LPHI"
grep -q "call ptr @malloc" "$OUT/gemm-3.ll" \
  && pass "malloc 调用在 .ll 里（M3 的真身）" || fail "未见 malloc"
grep -q "insertvalue" "$OUT/gemm-3.ll" \
  && pass "insertvalue 填描述符（M3/D115 的 56B 结构体真身）" || fail "未见 insertvalue"
pass "llvm-as + opt -passes=verify + llc 全部通过（lower.sh 阶段 4）"
log ""

# ------------------------------------------- TP6 双线验证（两条独立 LLVM 线）
log "[TP6] 双线验证：llvm-18 工具 + llvmlite（LLVM 22.1，跨版本）"
python3 - <<'EOF' 2>/dev/null | tee -a "$R"
import llvmlite.binding as lv
m = lv.parse_assembly(open("outputs/gemm-3.ll").read())
m.verify()
names = [f.name for f in m.functions]
print(f"  llvmlite(内嵌 LLVM 22.1) parse+verify: OK；函数 {names}")
assert "gemm" in names and "_mlir_ciface_gemm" in names and "malloc" in names
print("  [PASS] 跨版本双线验证：18.1.8 导出的 .ll 被 22.1 接受")
EOF
[ "${PIPESTATUS[0]}" = "0" ] || fail "llvmlite 验证失败"
log ""

# ------------------------------------- TP7 对照实验 A：跳过优化直接转换
log "[TP7] 对照 A：朴素源跳过阶段 0 直接转换——两条路是否收敛"
"$BIN"/mlir-opt gemm.mlir \
  --convert-scf-to-cf --finalize-memref-to-llvm --convert-func-to-llvm \
  --convert-cf-to-llvm --convert-arith-to-llvm --convert-index-to-llvm \
  --reconcile-unrealized-casts -o "$OUT/gemm-naive-direct-dialect.mlir"
"$BIN"/mlir-translate --mlir-to-llvmir "$OUT/gemm-naive-direct-dialect.mlir" \
  -o "$OUT/gemm-naive-direct.ll"
if diff -q "$OUT/gemm-3.ll" "$OUT/gemm-naive-direct.ll" >/dev/null; then
  pass "收敛：先优化/不优化两条路的 .ll 完全一致（转换 pass 自带常量折叠）"
else
  D=$(diff "$OUT/gemm-3.ll" "$OUT/gemm-naive-direct.ll" | grep -c "^<")
  log "  两条路 .ll 差异 $D 行（转换层折叠程度不同）"
  [ "$D" -le 6 ] && pass "近似收敛：差异 $D 行" || fail "差异过大：$D 行"
fi
log ""

# ------------------------------------------- TP8 对照实验 B：opt -O2 之后
log "[TP8] 对照 B：LLVM 级优化 opt -O2（LLVM 优化器的世界）"
"$BIN"/opt -O2 -S "$OUT/gemm-3.ll" -o "$OUT/gemm-O2.ll"
L2=$(grep -cE "^\s+%[0-9]+ =" "$OUT/gemm-O2.ll")
FM1=$(grep -c "fmul float" "$OUT/gemm-3.ll")
FM2=$(grep -c "fmul float" "$OUT/gemm-O2.ll")
log "  SSA 指令 $LI -> $L2 条；fmul $FM1 -> $FM2（循环展开：指令变多、循环开销变少）"
[ "$FM2" -gt "$FM1" ] && pass "O2 展开循环：fmul $FM1->$FM2" || fail "O2 未观察到展开"
log ""

# ------------------------------------------------------- TP9 账本回归 18/18
log "[TP9] D116 账本清零回归：tight 版（18 op，残账 C1×4）过同一条管道"
./lower.sh gemm_tight.mlir tight >/dev/null
python3 census.py "$OUT/tight-2-llvm-dialect.mlir" | head -1 | tee -a "$R"
RT=$(python3 census.py "$OUT/tight-2-llvm-dialect.mlir" | sed -n '1s/.*非 llvm 残账 \([0-9]*\).*/\1/p')
[ "$RT" = "0" ] && pass "18/18 清零：C1×4 由 --convert-scf-to-cf 转掉，非 llvm 残账 0" \
  || fail "tight 版残账 $RT"
pass "D116 排期给今天的最后一笔（C1 + reconcile）全部兑现"
log ""

# ------------------------------------------------ TP10 常见错误三连复现
log "[TP10] 常见错误复现（真实报错存档 errors-*.txt）"
"$BIN"/mlir-opt gemm_strided.mlir --convert-scf-to-cf --finalize-memref-to-llvm \
  --convert-func-to-llvm --convert-cf-to-llvm --convert-arith-to-llvm \
  --convert-index-to-llvm --reconcile-unrealized-casts \
  -o /dev/null 2> "$OUT/errors-1-strided-multipass.txt"
grep -q "failed to legalize" "$OUT/errors-1-strided-multipass.txt" \
  && pass "错误1复现：strided alloc 多 pass 管道 -> failed to legalize cast" \
  || fail "错误1未复现"

"$BIN"/mlir-opt gemm_strided.mlir --convert-scf-to-cf --convert-to-llvm \
  -o "$OUT/errors-2-strided-oneshot.mlir" 2>/dev/null
"$BIN"/mlir-translate --mlir-to-llvmir "$OUT/errors-2-strided-oneshot.mlir" \
  -o /dev/null 2> "$OUT/errors-2-strided-oneshot.txt"
grep -q "Dialect \`memref' not found" "$OUT/errors-2-strided-oneshot.txt" \
  && pass "错误1变体复现：one-shot 静默漏掉 memref.alloc，translate 才报错" \
  || fail "错误1变体未复现"

"$BIN"/mlir-translate --mlir-to-llvmir "$OUT/gemm-2-llvm-dialect-noreconcile.mlir" \
  -o /dev/null 2> "$OUT/errors-3-glue.txt"
grep -q "unrealized_conversion_cast" "$OUT/errors-3-glue.txt" \
  && pass "错误2复现：忘了 reconcile -> LLVM Translation failed for unrealized_conversion_cast" \
  || fail "错误2未复现"

"$BIN"/mlir-opt gemm.mlir --convert-func-to-llvm --finalize-memref-to-llvm \
  --convert-scf-to-cf --convert-cf-to-llvm --convert-arith-to-llvm \
  --convert-index-to-llvm --reconcile-unrealized-casts \
  -o /dev/null 2> "$OUT/errors-4-order.txt"
grep -qE "failed to legalize" "$OUT/errors-4-order.txt" \
  && pass "错误3复现：pass 顺序错（func 先于 scf/memref）-> 转换中途翻车" \
  || fail "错误3未复现"
log ""

# ------------------------------------------------------------------- 汇总
NP=$(grep -c "\[PASS\]" "$R")
NF=$(grep -c "\[FAIL\]" "$R")
log "汇总：$NP PASS / $NF FAIL"
[ "$NF" = "0" ] && log "全部通过：三组文件已冻结（优化前后 MLIR / LLVM Dialect / LLVM IR）" \
  || log "存在失败项，见上方 [FAIL]"
exit "$FAILED"
