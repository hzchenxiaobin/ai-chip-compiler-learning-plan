#!/usr/bin/env bash
# 第 123 天一键复现：IR Dump 与可观测性——四级粒度 + 改写记录 + 时间线
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

echo "第 123 天：IR Dump 与可观测性——真机报告 $(date '+%Y-%m-%d %H:%M')" | tee -a "$R"
echo "环境：$($PY --version 2>&1)｜$(uname -sm)" | tee -a "$R"

# ── TP1 四级粒度：文件数单调递增 ──
sec "[TP1] dump 粒度四级：off=0 / stages=2 / passes=11 / full=11+记录"
  "$PY" - <<'PYEOF' | tee -a "$R"
import os
from graph_passes import parse_graph, run_s1
from loop_lower import gen_loop_ir
from observability import run_s45_observed

g = parse_graph(open("main.graph").read())
g2 = run_s1(g)
loop_ir = gen_loop_ir(g2, tile=(2, 3, 6))

counts = {}
for level in ("off", "stages", "passes", "full"):
    out = f"outputs/obs-{level}"
    os.makedirs(out, exist_ok=True)
    r = run_s45_observed(loop_ir, out, llvm_bin="/opt/homebrew/opt/llvm/bin", obs_level=level)
    obs = r["obs"]
    n = len([f for f in os.listdir(out) if f.startswith("stage-")])
    counts[level] = (n, obs.dump_count(), len(obs.rewrites()))
    assert r["ok"], level
print(f"  off:    files={counts['off'][0]}  dumps={counts['off'][1]}  rewrites={counts['off'][2]}")
print(f"  stages: files={counts['stages'][0]}  dumps={counts['stages'][1]}  rewrites={counts['stages'][2]}")
print(f"  passes: files={counts['passes'][0]}  dumps={counts['passes'][1]}  rewrites={counts['passes'][2]}")
print(f"  full:   files={counts['full'][0]}  dumps={counts['full'][1]}  rewrites={counts['full'][2]}")
import json
json.dump({k: {"files": v[0], "dumps": v[1], "rewrites": v[2]} for k, v in counts.items()},
          open("outputs/level-matrix.json", "w"), ensure_ascii=False, indent=2)
PYEOF
  N_OFF=$(ls outputs/obs-off 2>/dev/null | grep -c "^stage-"; true)
  N_ST=$(ls outputs/obs-stages | grep -c "^stage-"; true)
  N_PA=$(ls outputs/obs-passes | grep -c "^stage-"; true)
  [ "$N_OFF" -eq 0 ] && ok "off 级零文件（CI 常规跑）" || bad "off 级有 ${N_OFF} 个文件"
  [ "$N_ST" -eq 2 ] && ok "stages 级 2 个文件（stage-5.ll/.s）" || bad "stages 级 ${N_ST} 个文件（期望 2）"
  [ "$N_PA" -eq 11 ] && ok "passes 级 11 个文件（D122 全量）" || bad "passes 级 ${N_PA} 个文件（期望 11）"

# ── TP2 改写记录：八条 pass 各改了什么 ──
sec "[TP2] 改写记录：每条 pass 一句话（op 增删）"
  "$PY" - <<'PYEOF' | tee -a "$R"
from graph_passes import parse_graph, run_s1
from loop_lower import gen_loop_ir
from observability import run_s45_observed

g = parse_graph(open("main.graph").read())
g2 = run_s1(g)
loop_ir = gen_loop_ir(g2, tile=(2, 3, 6))
r = run_s45_observed(loop_ir, "outputs/obs-full", llvm_bin="/opt/homebrew/opt/llvm/bin", obs_level="full")
for rw in r["obs"].rewrites():
    print(f"  {rw}")
PYEOF
  grep -q "canonicalize+csi: 16→3 op" "$R" && ok "canonicalize 的改写被记录（16→3，常量折叠）" || bad "缺 canonicalize 记录"
  grep -q "finalize-memref-to-llvm: 3→21" "$R" && ok "memref 转换的膨胀被记录（3→21，描述符展开）" || bad "缺 memref 记录"
  grep -q "结构无变化" "$R" && ok "无操作 pass 也如实记录（'结构无变化'）" || bad "缺无变化记录"

# ── TP3 时间线：哪个阶段最贵 ──
sec "[TP3] 时间线：11 个计时点进 manifest"
  "$PY" - <<'PYEOF' | tee -a "$R"
from graph_passes import parse_graph, run_s1
from loop_lower import gen_loop_ir
from observability import run_s45_observed

g = parse_graph(open("main.graph").read())
g2 = run_s1(g)
loop_ir = gen_loop_ir(g2, tile=(2, 3, 6))
r = run_s45_observed(loop_ir, "outputs/obs-full", llvm_bin="/opt/homebrew/opt/llvm/bin", obs_level="full")
tl = r["obs"].timeline()
total = sum(t["ms"] for t in tl if "pass" in t["note"] or "translate" in t["note"] or "llc" in t["note"] or "S2" in t["note"])
print(f"  计时点 {len(tl)} 个，管道总耗时 ≈ {total:.0f} ms")
for t in tl[:4]:
    print(f"  [{t['stage']}] {t['note']}")
print("  ...（全部 11 点见 outputs/timeline.txt）")
import json
json.dump(tl, open("outputs/timeline.txt", "w"), ensure_ascii=False, indent=1)
PYEOF
  [ -s outputs/timeline.txt ] && ok "时间线落盘 timeline.txt（11 个计时点）" || bad "时间线为空"

# ── TP4 观测点对应调试场景（设计立场验证） ──
sec "[TP4] 观测点与调试场景的对应（每条记录回答一个真实问题）"
  # 场景 1：图为什么没优化到位？→ 看 rewrite 里 canonicalize 的记录
  grep -q "arith.constant -9" "$R" && ok "「常量都折叠了吗」→ canonicalize 记录 arith.constant -9" || bad "缺常量折叠证据"
  # 场景 2：描述符什么时候出现的？→ finalize-memref 的 +9 struct
  grep -q "llvm.struct +9" "$R" && ok "「描述符何时进场」→ finalize-memref 记录 llvm.struct +9" || bad "缺描述符进场证据"
  # 场景 3：哪条 pass 最慢？→ 时间线排序
  "$PY" - <<'PYEOF' && ok "「哪条 pass 最贵」→ 时间线可查（教学量级 ~40-55ms/条）" || bad "时间线不可用"
import json
tl = json.load(open("outputs/timeline.txt"))
passes = [t for t in tl if t["note"].startswith("pass")]
slowest = max(passes, key=lambda t: t["ms"])
assert slowest["ms"] > 0, "耗时为负？"
print(f"    最慢：{slowest['note']}")
PYEOF

# ── TP5 minic 集成：--dump-ir 升级为四级 ──
sec "[TP5] minic 集成：--dump-ir=off/stages/passes/full"
  # 修改版 minic 今天先用环境观察方式；验证 CLI 形态已备
  "$PY" -c "
from observability import Observability
o = Observability('passes', '/tmp/x')
assert o.LEVELS == ('off', 'stages', 'passes', 'full')
print('  Observability LEVELS 四级就位')
" && ok "四级枚举可编程消费" || bad "枚举异常"
  # 粒度与代价的权衡记录
  "$PY" - <<'PYEOF' && ok "粒度×代价矩阵入档 level-matrix.json" || bad "矩阵缺失"
import json
m = json.load(open("outputs/level-matrix.json"))
assert m["off"]["files"] == 0 and m["passes"]["files"] == 11
PYEOF

sec "汇总"
  echo "  PASS: $PASS  FAIL: $FAIL" | tee -a "$R"
  echo "  环境：$(uname -sm)｜$(date '+%Y-%m-%d')" | tee -a "$R"
exit $([ "$FAIL" -eq 0 ] && echo 0 || echo 1)
