#!/usr/bin/env python3
"""第 123 天核心模块：observability.py——minic 的可观测性层。

D122 落盘了 11 个 stage 文件，但"有文件"≠"可观测"。今天补三件事：

  1. dump 粒度控制：--dump-ir=full|passes|stages|off
       off    零文件（CI 常规跑：只留 manifest）
       stages 每阶段末尾一份（D122 行为：11 个文件）
       passes 每条 pass 一份（D122 的 stage-4-NN 已是；再加 S1 审计）
       full   passes + pass 前后 diff 统计 + 时间线
  2. pass 改写记录：每条 pass 跑完对比前后 IR——op 数、增删行数、
     census 口径的 op 分布差（"这条 pass 到底改了什么"一句话可答）
  3. 时间线：每阶段/每条 pass 的耗时进 manifest——「哪个阶段最贵」
     查表可得（真实编译器 mlir-opt --mlir-timing 的教学版）

设计立场（README 3.x 展开）：
  · 可观测性不是"多打日志"，是"给问题定位提供最短路径"——
    每个观测点都要对应一个真实调试场景；
  · 粒度分层是因为代价不同：stages 免费、passes 便宜、full 的
    diff 统计要读两份文件——默认给 stages，按需升级；
  · 时间线的第一用户是 D125（对照实验要报各阶段开销）。
"""
from __future__ import annotations

import os
import re
import subprocess
import time
from dataclasses import dataclass, field

# ──────────────────────────────────────────────────────────
# census：op 级统计（D117 census.py 口径的教学版内联）
# ──────────────────────────────────────────────────────────

_OP_RE = re.compile(r"^\s+%?\w+(?:\.\w+)*\s*(?:=|:)", re.M)


def count_ops(ir_text: str) -> int:
    """粗粒度 op 计数：非空、非注释、非纯标签行。"""
    n = 0
    for line in ir_text.splitlines():
        s = line.strip()
        if not s or s.startswith("//") or s.startswith("^") or s.startswith("}"):
            continue
        if s.startswith("%") or "=" in s or s.startswith("memref.") or \
           s.startswith("arith.") or s.startswith("scf.") or s.startswith("func.") \
           or s.startswith("cf.") or s.startswith("llvm.") or s.startswith("module"):
            n += 1
    return n


def op_distribution(ir_text: str) -> dict:
    """op 名 → 出现次数（方言级：memref.load → memref.* 细分到 op）。"""
    dist = {}
    for m in re.finditer(r"\b((?:memref|arith|scf|func|cf|llvm|index)\.[\w.]+)\b", ir_text):
        name = m.group(1)
        dist[name] = dist.get(name, 0) + 1
    return dist


def diff_dist(before: dict, after: dict) -> list:
    """两份分布的差：返回 [(op, +Δ/-Δ), ...] 按绝对值降序。"""
    keys = set(before) | set(after)
    deltas = []
    for k in keys:
        d = after.get(k, 0) - before.get(k, 0)
        if d != 0:
            deltas.append((k, d))
    deltas.sort(key=lambda x: -abs(x[1]))
    return deltas


# ──────────────────────────────────────────────────────────
# 观测记录：每个观测点一条
# ──────────────────────────────────────────────────────────

@dataclass
class Observation:
    stage: str            # S1 / S4:pass名 / S5
    kind: str             # dump / rewrite / timing
    note: str             # 人话一句话
    detail: dict = field(default_factory=dict)   # 机器可读细节


class Observability:
    """可观测性层：挂在管道上，按粒度收集记录。"""

    LEVELS = ("off", "stages", "passes", "full")

    def __init__(self, level: str = "stages", out_dir: str = "out"):
        assert level in self.LEVELS, f"level 应为 {self.LEVELS}，得到 {level}"
        self.level = level
        self.out_dir = out_dir
        self.records: list = []
        os.makedirs(out_dir, exist_ok=True)

    # ── dump：落盘一个阶段产物 ──
    def dump(self, stage: str, filename: str, content: str):
        if self.level == "off":
            return
        # stages 级：只收"阶段末尾"文件（调用方约定：文件名不带 pass 序号即阶段级）
        is_stage_level = "-" not in filename.replace("stage-", "").replace(".mlir", "").replace(".graph", "").replace(".ll", "").replace(".s", "") \
                         or filename.count("-") <= 1
        if self.level in ("stages",) and not is_stage_level:
            return
        path = os.path.join(self.out_dir, filename)
        open(path, "w").write(content)
        self.records.append(Observation(stage, "dump", f"落盘 {filename}（{len(content.splitlines())} 行）"))

    # ── rewrite：一条 pass 的改写记录 ──
    def rewrite(self, stage: str, pass_name: str, before_text: str, after_text: str):
        if self.level in ("off", "stages"):
            return
        b_ops, a_ops = count_ops(before_text), count_ops(after_text)
        delta = diff_dist(op_distribution(before_text), op_distribution(after_text))
        parts = [f"{k} {'+' if d>0 else ''}{d}" for k, d in delta[:4]]
        note = f"{pass_name}: {b_ops}→{a_ops} op" + (f"（{', '.join(parts)}）" if parts else "（结构无变化）")
        self.records.append(Observation(stage, "rewrite", note,
                                        {"pass": pass_name, "before_ops": b_ops,
                                         "after_ops": a_ops, "delta": delta}))

    # ── timing：一个阶段/一条 pass 的耗时 ──
    def timing(self, stage: str, what: str, seconds: float):
        if self.level == "off":
            return
        ms = seconds * 1000
        self.records.append(Observation(stage, "timing", f"{what}: {ms:.1f} ms",
                                        {"what": what, "ms": round(ms, 1)}))

    # ── 汇总：时间线表 + manifest 注入 ──
    def timeline(self) -> list:
        return [{"stage": r.stage, "kind": r.kind, "note": r.note, **r.detail}
                for r in self.records if r.kind == "timing"]

    def rewrites(self) -> list:
        return [r.note for r in self.records if r.kind == "rewrite"]

    def dump_count(self) -> int:
        return sum(1 for r in self.records if r.kind == "dump")

    def manifest_section(self) -> dict:
        return {
            "dump_level": self.level,
            "dump_files": self.dump_count(),
            "rewrites": [r.note for r in self.records if r.kind == "rewrite"],
            "timeline_ms": {r.detail["what"]: r.detail["ms"]
                            for r in self.records if r.kind == "timing"},
        }


# ──────────────────────────────────────────────────────────
# 可观测版管道：在 run_s45 外面包观测层（不改 loop_lower 的逻辑——
# 观测是横切面，不该侵入业务管道；这是 AOP 的教学版）
# ──────────────────────────────────────────────────────────

def run_s45_observed(loop_ir: str, out_dir: str, llvm_bin: str = "",
                     obs_level: str = "stages") -> dict:
    """loop_lower.run_s45 的观测版：同逻辑，但每步记录 dump/rewrite/timing。"""
    from loop_lower import find_tool, PASSES

    obs = Observability(obs_level, out_dir)
    stages = []
    mlir_opt = find_tool("mlir-opt", llvm_bin)
    if not mlir_opt:
        return {"ok": False, "error": "E205 mlir-opt 未找到", "stages": stages, "obs": obs}

    # 清旧（off 模式额外全清——不留任何 stage 文件）
    for f in os.listdir(out_dir):
        if f.startswith("stage-") or f == "pipeline-error.txt" or obs_level == "off":
            if obs_level == "off" and not f.startswith("stage-") and f != "pipeline-error.txt":
                continue
            try:
                os.remove(os.path.join(out_dir, f))
            except OSError:
                pass

    t0 = time.perf_counter()
    import tempfile
    # 文件策略：off=全临时；stages=pass 链临时+阶段文件落盘；passes/full=全部落盘
    keep_files = obs_level in ("passes", "full")
    tmpdir = tempfile.mkdtemp(prefix="minic-obs-") if not keep_files else ""
    workdir = out_dir if keep_files else tmpdir
    cur_path = os.path.join(workdir, "stage-2-loop.mlir")
    open(cur_path, "w").write(loop_ir + "\n")
    obs.dump("S2", "stage-2-loop.mlir", loop_ir)
    obs.timing("S2", "S2 循环生成", time.perf_counter() - t0)
    stages.append(("S2", "循环 IR 落盘"))
    cur_text = loop_ir

    pass_idx = 3
    for name, flags in PASSES:
        nxt = os.path.join(workdir, f"stage-4-{pass_idx:02d}-{name}.mlir")
        t1 = time.perf_counter()
        r = subprocess.run([mlir_opt, cur_path] + flags + ["-o", nxt],
                           capture_output=True, text=True)
        dt = time.perf_counter() - t1
        if r.returncode != 0:
            open(os.path.join(out_dir, "pipeline-error.txt"), "w").write(
                f"失败的 pass：{name}\n\n{r.stderr}")
            return {"ok": False, "error": f"E204 pass {name} 失败", "stages": stages, "obs": obs}
        new_text = open(nxt).read()
        obs.rewrite("S4", name, cur_text, new_text)
        obs.timing("S4", f"pass {name}", dt)
        if obs_level in ("passes", "full"):
            obs.dump("S4", os.path.basename(nxt), new_text)
        cur_path, cur_text = nxt, new_text
        stages.append(("S4", f"pass {name} ✓"))
        pass_idx += 1

    # S5
    mlir_tr = find_tool("mlir-translate", llvm_bin)
    ll_path = os.path.join(workdir, "stage-5.ll")
    t2 = time.perf_counter()
    r = subprocess.run([mlir_tr, cur_path, "--mlir-to-llvmir", "-o", ll_path],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return {"ok": False, "error": "E205 translate 失败", "stages": stages, "obs": obs}
    obs.timing("S5", "mlir-translate", time.perf_counter() - t2)
    obs.dump("S5", "stage-5.ll", open(ll_path).read())

    llc = find_tool("llc", llvm_bin)
    if llc:
        s_path = os.path.join(workdir, "stage-5.s")
        t3 = time.perf_counter()
        r = subprocess.run([llc, ll_path, "-o", s_path], capture_output=True, text=True)
        if r.returncode == 0:
            obs.timing("S5", "llc", time.perf_counter() - t3)
            obs.dump("S5", "stage-5.s", open(s_path).read())
            stages.append(("S5", "llc ✓"))

    glue = cur_text.count("unrealized_conversion_cast")
    stages.append(("S4", f"胶水 {glue} 条"))
    return {"ok": True, "stages": stages, "obs": obs, "ll": ll_path}
