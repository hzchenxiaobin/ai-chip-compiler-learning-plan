#!/usr/bin/env bash
# 第 121 天一键复现：minic S1 图优化接入——开关对照矩阵＋审计日志＋合同回归
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

minic() { "$PY" "$HERE/minic.py" "$@"; }

echo "第 121 天：minic S1 图优化——真机报告 $(date '+%Y-%m-%d %H:%M')" | tee -a "$R"
echo "环境：$($PY --version 2>&1)｜$(uname -sm)" | tee -a "$R"

# ── TP1 主线：11→5 全管道（D83 口径对账） ──
sec "[TP1] 主线：贯穿图 11 → 5 节点（与 D83 集成验收对账）"
  minic main.graph -o "$OUT/main" --dump-ir -q > /dev/null 2>&1; RC=$?
  [ "${RC}" -eq 0 ] && ok "minic main.graph 退出码 0" || bad "退出码 ${RC}"
  N=$(grep -c "^  %" "$OUT/main/stage-1-graph-opt.graph" 2>/dev/null || echo 0)
  N=$((N))  # 节点行数（arg/const/算子）
  [ "$N" -eq 5 ] && ok "S1 终图 5 节点（11→5，与 D83 report.txt 一致）" || bad "终图 ${N} 节点（期望 5）"
  grep -q "fused_matmul_bias_relu" "$OUT/main/stage-1-graph-opt.graph" \
    && ok "融合算子 in place（fused_matmul_bias_relu）" || bad "缺融合算子"
  grep -q "quantize\|dequantize" "$OUT/main/stage-1-graph-opt.graph" \
    && bad "QDQ 残留（应被闸1 清掉）" || ok "QDQ 已清（R04 折叠生效）"

# ── TP2 开关矩阵：五组对照 ──
sec "[TP2] 开关对照矩阵：关一个 Pass，看图退化成什么样"
  declare -a CASES=(
    "all-on:-X-DUMMY:5"
    "no-fuse:--no-fuse:7"
    "no-qdq:--no-qdq-clean:8"
    "no-layout:--no-layout-simp:6"
    "no-reshape:--no-reshape-merge:6"
    "O0:-O0:11"
  )
  for c in "${CASES[@]}"; do
    IFS=':' read -r name flags expect <<< "$c"
    FLAGS=""; [ "$flags" != "-X-DUMMY" ] && FLAGS="$flags"; minic main.graph -o "$OUT/sw-$name" $FLAGS --dump-ir -q > /dev/null 2>&1
    N=$(grep -c "^  %" "$OUT/sw-$name/stage-1-graph-opt.graph" 2>/dev/null || echo 0)
    N=$((N))
    [ "$N" -eq "$expect" ] && ok "$name → ${N} 节点（期望 ${expect}）" \
      || bad "$name → ${N} 节点（期望 ${expect}）"
  done

# ── TP3 开关语义验证：关掉的 Pass 确实没跑 ──
sec "[TP3] 开关语义：审计日志逐条核对"
  # no-fuse：不该出现 [闸4]
  grep -q "闸4" "$OUT/sw-no-fuse/manifest.json" && bad "no-fuse 下闸4 仍执行" \
    || ok "no-fuse：闸4 未执行（manifest 审计无闸4）"
  # no-qdq：终图应含 quantize
  grep -q "quantize" "$OUT/sw-no-qdq/stage-1-graph-opt.graph" \
    && ok "no-qdq：QDQ 保留在终图" || bad "no-qdq：QDQ 仍被清"
  # O0：终图应等于原图节点数
  N0=$(grep -c "^  %" "$OUT/sw-O0/stage-1-graph-opt.graph")
  [ "$N0" -eq 11 ] && ok "-O0：11 节点原样（全部 Pass 关闭）" || bad "-O0：${N0} 节点（期望 11）"

# ── TP4 不动点轮数开关 ──
sec "[TP4] 不动点轮数：--fixpoint-max 1 vs 8"
  minic main.graph -o "$OUT/fp1" --fixpoint-max 1 --dump-ir -q > /dev/null 2>&1
  N=$(grep -c "^  %" "$OUT/fp1/stage-1-graph-opt.graph")
  # 单轮：闸1→2→3 各跑一次——QDQ 折叠+转置折叠能做，但 reshape 合并机会与收敛差异
  echo "  fixpoint-max=1 → ${N} 节点" | tee -a "$R"
  [ "$N" -ge 5 ] && [ "$N" -le 7 ] && ok "单轮结果在 5~7 区间（机会可能未挖尽）" || bad "单轮结果异常 ${N}"

# ── TP5 D120 合同回归：CLI 骨架测试不退化 ──
sec "[TP5] 合同回归：D120 的四份合同仍然成立"
  minic --help > "$OUT/help.txt" 2>&1
  for kw in "usage: minic" "--tile" "--emit" "--verify" "示例"; do
    grep -q -e "$kw" "$OUT/help.txt" && ok "--help 含 $kw" || bad "--help 缺 $kw"
  done
  # 新开关入档
  for kw in "--no-qdq-clean" "--no-fuse" "--fixpoint-max"; do
    grep -q -e "$kw" "$OUT/help.txt" && ok "新开关 $kw 在帮助文本" || bad "缺 $kw"
  done
  minic no-such.graph -o /tmp/x -q > /dev/null 2>&1; RC=$?
  [ "${RC}" -eq 2 ] && ok "E101 退出码 2（合同不退化）" || bad "退出码 ${RC}"
  minic main.graph -o "$OUT/contract-m" --tile 16,16,16 -q > /dev/null 2>&1
  "$PY" - "$OUT/contract-m/manifest.json" <<'PYEOF' && ok "manifest 新字段 s1_switches 就位" || bad "manifest 缺 s1_switches"
import json, sys
m = json.load(open(sys.argv[1]))
assert "s1_switches" in m and m["s1_switches"]["fuse"] is True
assert m["tile"] == [16, 16, 16]
PYEOF

# ── TP6 数值等价：优化不改语义（位等价，容差 0） ──
sec "[TP6] 位等价：S1 优化前后随机输入逐位一致（numpy 验证）"
  "$PY" - <<'PYEOF' && ok "3×10000 随机输入位等价（容差=0）" || bad "位等价失败"
import numpy as np
from graph_passes import parse_graph, run_s1

g0 = parse_graph(open("main.graph").read())
g1 = parse_graph(open("main.graph").read())
run_s1(g1)

def eval_graph(g, x):
    vals = {}
    for n in g.nodes.values():
        if n.op == "arg":
            vals[n.nid] = x
        elif n.op == "const":
            vals[n.nid] = np.array(n.attrs["values"], dtype=np.float32).reshape(n.attrs["shape"])
        elif n.op == "reshape":
            vals[n.nid] = vals[n.inputs[0]].reshape(n.attrs["new_shape"])
        elif n.op == "transpose":
            vals[n.nid] = vals[n.inputs[0]].transpose(n.attrs["perm"])
        elif n.op == "matmul":
            vals[n.nid] = vals[n.inputs[0]] @ vals[n.inputs[1]]
        elif n.op == "add":
            vals[n.nid] = vals[n.inputs[0]] + vals[n.inputs[1]]
        elif n.op == "relu":
            vals[n.nid] = np.maximum(vals[n.inputs[0]], 0)
        elif n.op == "quantize":
            s, z = n.attrs["scale"], n.attrs["zp"]
            vals[n.nid] = np.clip(np.round(vals[n.inputs[0]] / s + z), -128, 127)
        elif n.op == "dequantize":
            s, z = n.attrs["scale"], n.attrs["zp"]
            vals[n.nid] = (vals[n.inputs[0]] - z) * s
        elif n.op == "fused_matmul_bias_relu":
            a, b, bias = (vals[i] for i in n.inputs)
            vals[n.nid] = np.maximum(a @ b + bias, 0)
    return vals[g.ret]

rng = np.random.default_rng(20261114)
for batch in range(3):
    for i in range(10000):
        x = rng.standard_normal(24).astype(np.float32).reshape(2, 12)
        r0, r1 = eval_graph(g0, x), eval_graph(g1, x)
        assert np.array_equal(r0, r1), f"批{batch}#{i} 不一致: {r0} vs {r1}"
print("  3×10000 全部位等价")
PYEOF

sec "汇总"
  echo "  PASS: $PASS  FAIL: $FAIL" | tee -a "$R"
  echo "  环境：$(uname -sm)｜$(date '+%Y-%m-%d')" | tee -a "$R"
exit $([ "$FAIL" -eq 0 ] && echo 0 || echo 1)
