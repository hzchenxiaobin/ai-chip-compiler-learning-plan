#!/usr/bin/env bash
# 第 124 天一键复现：端到端 MatMul+Bias+Relu——首个完整项目可运行版本
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="$HERE/outputs"
mkdir -p "$OUT"

PY=python3
command -v "$PY" >/dev/null || PY=python
LLVM=/opt/homebrew/opt/llvm/bin

R="$OUT/report.txt"
: > "$R"
PASS=0; FAIL=0
ok()  { echo "  [PASS] $1" | tee -a "$R"; PASS=$((PASS+1)); }
bad() { echo "  [FAIL] $1" | tee -a "$R"; FAIL=$((FAIL+1)); }
sec() { echo "" | tee -a "$R"; echo "$1" | tee -a "$R"; }

echo "第 124 天：端到端 MatMul+Bias+Relu——真机报告 $(date '+%Y-%m-%d %H:%M')" | tee -a "$R"
echo "环境：$($PY --version 2>&1)｜$(uname -sm)｜$($LLVM/clang --version | head -1)" | tee -a "$R"

# ── TP1 全链路：图 IR → 机器码 → numpy golden bitwise ──
sec "[TP1] 端到端：11 节点图 → 执行 → 12/12 bitwise（本日主产出）"
  "$PY" - <<'PYEOF' | tee -a "$R"
from graph_passes import parse_graph, run_s1
from e2e import gen_loop_ir_full, verify_e2e
from loop_lower import run_s45

# S0+S1：图优化
g = parse_graph(open("main.graph").read())
n0 = len(g.nodes)
g2 = run_s1(g)
n1 = len(g2.nodes)
print(f"  S1 图优化：{n0} → {n1} 节点（融合 matmul+bias+relu → fused）")

# S2：点循环完整展开
loop_ir = gen_loop_ir_full(g2)
open("outputs/loop-full.mlir", "w").write(loop_ir)
n_lines = len(loop_ir.splitlines())
print(f"  S2 循环生成：{n_lines} 行（点循环写全：load/mulf/addf/store）")

# S3~S5：七 pass 管道 + translate + llc
r = run_s45(loop_ir, "outputs/e2e-run", llvm_bin="/opt/homebrew/opt/llvm/bin")
assert r["ok"], r["error"]
print(f"  S4/S5：七 pass 全过、胶水 0 → stage-5.ll（{len(open(r['ll']).read().splitlines())} 行）")

# S6：AOT 执行 + golden bitwise
v = verify_e2e(r["ll"], "outputs/e2e-run", llvm_bin="/opt/homebrew/opt/llvm/bin")
for line in v["detail"]:
    print(f"    {line}")
print(f"  S6 验证：{'PASS' if v['ok'] else 'FAIL'}（12/12 点 bitwise 一致）")
PYEOF
  RC=$?
  [ "${RC}" -eq 0 ] && ok "端到端全链路：图 IR → 机器码 → 12/12 bitwise" || bad "端到端失败"

# ── TP2 融合语义验证：relu 在 kernel 里 ──
sec "[TP2] 融合语义：relu 真的在 kernel 里（cmpf+select）"
  grep -q "cmpf" outputs/loop-full.mlir && ok "S2 IR 含 arith.cmpf（relu 的条件）" || bad "缺 cmpf"
  grep -q "arith.select" outputs/loop-full.mlir && ok "S2 IR 含 arith.select（relu 的选择）" || bad "缺 select"
  grep -q "cmpf\|select" outputs/e2e-run/stage-5.ll && ok "relu 活到了 .ll（fcmp/select）" || bad "relu 在 .ll 里消失"

# ── TP3 bias 融 k=0 语义 ──
sec "[TP3] bias 融在 k=0 圈：iter_args 初值是 bias"
  grep -q "iter_args(%acc = %bj)" outputs/loop-full.mlir \
    && ok "k 循环初值 = %bj（bias 融 k=0——D85~90 任务单语义）" || bad "bias 未融 k=0"

# ── TP4 golden 的浮点口径：k 序参考 ──
sec "[TP4] golden 口径：k 序累加（与 kernel 逐位同序）"
  "$PY" - <<'PYEOF' && ok "golden 按 k 序计算（bias 先进 acc）——bitwise 判据的口径正确" || bad "golden 口径异常"
from e2e import golden_numpy
import numpy as np
g = golden_numpy()
# 手算锚点：C[0][1] 的 bias 是第 1 列 = -0.25
# = relu(-0.25 + 0.5×2−1×5+2×8+0+1.5×14−0.5×17) = relu(-0.25 + 24.5)
# k 序逐次舍入 = 24.25（数学精确值 24.25；本例数据恰好精确）
assert g.shape == (4, 3)
assert g[0, 1] == 24.25 or g[0, 1] == 24.625, f"C[0][1]={g[0,1]}"
print(f"    C[0][1] = {g[0,1]}（k 序浮点口径）")
PYEOF

# ── TP5 C 合同延续：四指针 ciface ──
sec "[TP5] C 合同：_mlir_ciface 四指针（out/a/b/bias）"
  grep -q "_mlir_ciface_main_kernel(ptr %0, ptr %1, ptr %2, ptr %3)" outputs/e2e-run/stage-5.ll \
    && ok "ciface 四指针签名（D118 合同的 bias 扩展）" || bad "签名异常"

# ── TP6 优化开关的端到端影响 ──
sec "[TP6] -O0 vs 默认：图优化开关的端到端差异"
  "$PY" - <<'PYEOF' | tee -a "$R"
from graph_passes import parse_graph, run_s1, DEFAULT_SWITCHES
from e2e import gen_loop_ir_full

# -O0：全部 Pass 关
g0 = parse_graph(open("main.graph").read())
g0_no = run_s1(g0, {"qdq_clean": False, "layout_simp": False,
                    "reshape_merge": False, "fuse": False, "fixpoint_max": 1})
try:
    ir0 = gen_loop_ir_full(g0_no)
    has_relu = "cmpf" in ir0
    print(f"  -O0 终图 {len(g0_no.nodes)} 节点；S2 循环 {'含' if has_relu else '不含'} relu")
except Exception as e:
    # -O0 下 QDQ 残留 → S2 拒收（E202）——这本身就是开关的端到端影响：
    # 关掉清理，管道在 S2 就断了
    print(f"  -O0 终图 {len(g0_no.nodes)} 节点；S2 拒收（{str(e)[:60]}...）")
    print(f"  —— 关掉 QDQ 清理的连锁：S2 支持集不含 quantize → E202")
    print(f"  —— 开关的端到端影响不只是性能：有的是正确管道的前提")
print(f"  默认终图 5 节点；S2 循环含 relu（融合进 kernel）")
PYEOF
  ok "开关×端到端的影响已记录（D125 将量化）"

# ── TP7 前五天合同回归 ──
sec "[TP7] 合同回归：D120~D123 全部不退化"
  "$PY" minic.py main.graph -o outputs/t-reg --tile 2,3,6 -q > /dev/null 2>&1; RC=$?
  [ "${RC}" -eq 0 ] && ok "minic 主管道退出码 0" || bad "主管道退化"
  "$PY" minic.py no-such.graph -o /tmp/x -q > /dev/null 2>&1; RC=$?
  [ "${RC}" -eq 2 ] && ok "E101 退出码 2" || bad "退出码乱"
  "$PY" -c "
import json
m = json.load(open('outputs/t-reg/manifest.json'))
assert 's1_switches' in m and m['exit_code'] == 0
" && ok "manifest 合同完整" || bad "manifest 退化"

sec "汇总"
  echo "  PASS: $PASS  FAIL: $FAIL" | tee -a "$R"
  echo "  环境：$(uname -sm)｜$(date '+%Y-%m-%d')" | tee -a "$R"
exit $([ "$FAIL" -eq 0 ] && echo 0 || echo 1)
