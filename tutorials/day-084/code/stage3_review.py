#!/usr/bin/env python3
"""stage3_review.py —— 第 84 天（第 12 周复盘 · 第三阶段收官）主实验。

学习计划给今天点名的三件事：
  学习：总结图编译器不仅做模式匹配，还要管理布局、资源和数值语义；
  实践：用 20 分钟讲解当前项目，补充讲不清楚的 Layout 或量化问题；
  产出：第三阶段总结和一份「优化正确性检查清单」。

本脚本把「产出」做成能跑的，把「补讲」做成能验证的：

  Part 1  优化正确性检查清单 v1.0（五组 16 项）
          —— 不是给人背的备忘录，是套在 Day 83 管道上的测试套件。
          两个全绿场景：主图（11→5，该融就融）、多使用者图（11→7，该拒就拒）。
  Part 2  负例探针 ×3：只在好图上全绿过的清单等于没测过
          —— P1 数值破坏（手痒删掉尾部 QDQ，Day 82 R06 拒绝的不安全规则）
             P2 结构破坏（忘记单使用者检查的断链融合，Day 52 边界）
             P3 资源破坏（1024³ 工作集 12 MB 顶爆 256 KiB 还要强融）
          预期：三个探针分别被 D 数值列 / A 结构列 / C 资源列拦下。
  Part 3  补讲 1（Layout 缺口）：终图剩下的那个 reshape 到底贵不贵？
          —— 同一块 24 元素存储的三种身份：连续 (2,12) 缓冲、(4,6) 视图、
             stride 描述符（第四阶段 Lowering 的预演）；非连续输入的反例。
  Part 4  补讲 2（量化缺口）：非 2 幂 scale 为什么让 fp32/fp64 的 round 分叉？
          —— 半格（k+0.5）分叉的实测计数、单点解剖、两个修正的实测效果。
  Part 5  第三阶段数字复跑（主图 11→5、运行时算子 8→2、两层验证）

运行：python3 stage3_review.py   （在 code/ 目录下；依赖 ../day-083/code/pipeline_lab.py）
输出：终端打印 + outputs/report.txt 归档。
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / "day-083" / "code"))

import pipeline_lab as pl   # noqa: E402  （Day 83 的管道——今天只取不改）
from pipeline_lab import (  # noqa: E402
    EPS32, Graph, Machine, Op, fusion_cost, matmul_atol, run_cleanup,
    verify_bit_exact, X_FLAT,
)

OUT = HERE / "outputs"
OUT.mkdir(exist_ok=True)
REPORT = OUT / "report.txt"

PASS = 0
FAIL = 0
LINES: list[str] = []


def say(s: str = "") -> None:
    print(s)
    LINES.append(s)


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        say(f"[PASS] {name}" + (f"（{detail}）" if detail else ""))
    else:
        FAIL += 1
        say(f"[FAIL] {name}" + (f"（{detail}）" if detail else ""))


def hr(title: str) -> None:
    say("\n" + "=" * 72)
    say(title)
    say("=" * 72)


def fmt_b(n: float) -> str:
    if n >= 2**20:
        return f"{n / 2**20:.2f} MiB"
    if n >= 2**10:
        return f"{n / 2**10:.1f} KiB"
    return f"{int(n)} B"


# ============================================================
# 检查清单 v1.0 的上下文与检查项
# ============================================================

class Ctx:
    """一次优化结果 + 它的对照材料。检查项只读这个上下文。"""

    def __init__(self, name, g_orig, g_opt, audit, feeds,
                 ir_before=None, extra_reports=()):
        self.name = name
        self.g_orig = g_orig        # 优化前原图（对照基准，E1 保证它没被动过）
        self.g_opt = g_opt          # 优化后终图
        self.audit = audit          # 审计日志（先于动作写下的每一行）
        self.feeds = feeds          # 位等价输入组（固定 + 随机）
        self.ir_before = ir_before  # 优化前原图的 IR 快照（E1 用）
        self.extra_reports = list(extra_reports)   # 额外决策记录（探针可伪造）
        self.machine = Machine()


def run_env(g: Graph, feed: dict, dtype=np.float32) -> dict:
    """带环境返回的执行：拿到每个节点的值（D2 的账本要读 matmul 操作数）。"""
    env: dict[str, np.ndarray] = {}
    for op in g.ops:
        if op.kind == "arg":
            v32 = np.asarray(feed[op.name], dtype=np.float32)
            env[op.name] = v32 if dtype is np.float32 else v32.astype(dtype)
        elif op.kind == "const":
            env[op.name] = op.value.astype(dtype)
        elif op.kind == "quantize":
            env[op.name] = pl.v_quantize(env[op.inputs[0]], op.scale, op.zp, dtype)
        elif op.kind == "dequantize":
            env[op.name] = pl.v_dequantize(env[op.inputs[0]], op.scale, op.zp, dtype)
        elif op.kind == "transpose":
            env[op.name] = np.transpose(env[op.inputs[0]], op.perm)
        elif op.kind == "reshape":
            env[op.name] = np.reshape(env[op.inputs[0]], op.new_shape)
        elif op.kind == "matmul":
            env[op.name] = np.matmul(env[op.inputs[0]], env[op.inputs[1]])
        elif op.kind == "add":
            env[op.name] = env[op.inputs[0]] + env[op.inputs[1]]
        elif op.kind == "relu":
            env[op.name] = np.maximum(env[op.inputs[0]], dtype(0))
        elif op.kind == "fused_matmul_bias_relu":
            a, b, bias = (env[op.inputs[0]], env[op.inputs[1]], env[op.inputs[2]])
            env[op.name] = np.maximum(np.matmul(a, b) + bias, dtype(0))
        else:
            raise ValueError(op.kind)
    return env


def is_pow2(x: float) -> bool:
    if x <= 0:
        return False
    r = math.frexp(x)[0]
    return abs(r - 0.5) < 1e-12


def ancestors_compile_time(g: Graph, name: str) -> bool:
    """name 的祖先链是否全部由编译期节点（const/Q/DQ）组成。"""
    producers = g.producers()
    cur = name
    seen = set()
    while True:
        op = producers[cur]
        if op.kind == "const":
            return True
        if op.kind in ("quantize", "dequantize"):
            cur = op.inputs[0]
            if cur in seen:
                return False
            seen.add(cur)
            continue
        return False          # arg / 任何运行时算子：不是纯编译期数据


# ---------- 五组 16 项：每项 (组, 编号, 标题, 出处, 函数) ----------

def ck_a1(c: Ctx):
    errs = c.g_opt.verify()
    return (not errs,
            f"Verifier 通过：{len(c.g_opt.ops)} 节点 Shape 全部可推导、引用无悬空"
            if not errs else "；".join(errs[:2]))


def ck_a2(c: Ctx):
    removed = {o.name for o in c.g_orig.ops} - {o.name for o in c.g_opt.ops}
    referenced = set()
    for o in c.g_opt.ops:
        referenced |= set(o.inputs)
    referenced |= set(c.g_opt.returns)
    bad = removed & referenced
    return (not bad,
            f"删除 {len(removed)} 个节点，无一残留引用（rewire 纪律）" if not bad
            else f"被删节点仍被引用：{sorted(bad)}")


def ck_a3(c: Ctx):
    g2 = c.g_opt.copy()
    audit2, _ = run_cleanup(g2)
    rewrote = [a for a in audit2 if any(k in a for k in ("折叠", "合并", "消除"))]
    return (len(g2.ops) == len(c.g_opt.ops) and not rewrote,
            "清理闸复跑零改写（不动点已收敛）" if not rewrote and len(g2.ops) == len(c.g_opt.ops)
            else f"还能继续改写（{len(g2.ops)} 节点，{len(rewrote)} 条改写）——未到不动点")


def ck_b1(c: Ctx):
    producers = c.g_opt.producers()
    bad = [o.name for o in c.g_opt.ops
           if o.kind == "reshape" and producers[o.inputs[0]].kind == "transpose"]
    return (not bad,
            "无 reshape 消费非连续生产者（transpose 输出）——元信息改写的连续性前提成立"
            if not bad else f"reshape 吃了 transpose 输出：{bad}（元信息改写退化为物理搬运）")


def ck_b2(c: Ctx):
    bad = [o.name for o in c.g_opt.ops
           if o.kind == "transpose" and ancestors_compile_time(c.g_opt, o.inputs[0])]
    return (not bad,
            f"终图残留 transpose {sum(1 for o in c.g_opt.ops if o.kind == 'transpose')} 个，"
            "祖先链均含运行时输入（无漏折的编译期数据移动）" if not bad
            else f"纯编译期数据仍挂着 transpose：{bad}（本可折叠进常量）")


def ck_b3(c: Ctx):
    producers = c.g_opt.producers()
    bad = [o.name for o in c.g_opt.ops
           if o.kind == "reshape" and producers[o.inputs[0]].kind == "reshape"]
    return (not bad,
            "reshape 链深度 ≤ 1（Day 66 合并已完成）" if not bad
            else f"仍有 reshape 链：{bad}（漏合并）")


def ck_c1(c: Ctx):
    n_fused = sum(1 for o in c.g_opt.ops if o.kind == "fused_matmul_bias_relu")
    if n_fused == 0:
        return True, "终图无融合算子（无候选或被拒），无需收益账"
    ledger = [a for a in c.audit if "ΔB" in a]
    return (len(ledger) >= n_fused,
            f"{n_fused} 个融合算子，审计有 {len(ledger)} 行收益账（ΔB + 工作集）" if ledger
            else "融合发生了，审计里没有 ΔB 账——先动手后算账")


def decision_consistent(rep) -> bool:
    if rep.decision.startswith("融合"):
        return (not rep.spill) and rep.delta_b > 0
    return True


def ck_c2(c: Ctx):
    shapes, _ = c.g_opt.infer_shapes()
    reports = []
    for o in c.g_opt.ops:
        if o.kind == "fused_matmul_bias_relu":
            reports.append(fusion_cost(shapes[o.inputs[0]], shapes[o.inputs[1]], c.machine))
    reports += c.extra_reports
    bad = [r for r in reports if not decision_consistent(r)]
    detail = (f"终图融合核 {len(reports) - len(c.extra_reports)} 个复算全部一致"
              + (f"；另核 {len(c.extra_reports)} 份决策记录"
                 if c.extra_reports else ""))
    return (not bad, detail if not bad
            else f"决策与资源矛盾：spill={bad[0].spill} 仍判「{bad[0].decision}」")


def ck_c3(c: Ctx):
    rep = fusion_cost((1024, 1024), (1024, 1024), c.machine)
    ok = rep.spill and not rep.decision.startswith("融合")
    return (ok, f"1024³ 复核：工作集 {fmt_b(rep.workset)} > 片上 "
            f"{fmt_b(c.machine.onchip_bytes)}，Cost Model 判「{rep.decision[:14]}…」"
            if ok else "资源红线失效：spill 形状被判为融合")


def ck_d1(c: Ctx):
    try:
        ok, d = verify_bit_exact(c.g_orig, c.g_opt, c.feeds)
    except Exception as exc:                      # 悬空引用之类：图根本跑不起来
        return False, f"优化图无法执行（{type(exc).__name__}: {exc}）"
    return (ok, f"位等价（容差=0）：{len(c.feeds)} 组输入全部逐位相等" if ok
            else f"位等价被打破：max|diff| = {d:.4g}（改写引入了数值变化）")


def ck_d2(c: Ctx):
    try:
        env32 = run_env(c.g_opt, c.feeds[0], np.float32)
        env64 = run_env(c.g_opt, c.feeds[0], np.float64)
        out32 = np.asarray([env32[r] for r in c.g_opt.returns][0], dtype=np.float64)
        out64 = np.asarray([env64[r] for r in c.g_opt.returns][0], dtype=np.float64)
    except Exception as exc:
        return False, f"golden 无法执行（{type(exc).__name__}: {exc}）"
    mm = next((o for o in c.g_opt.ops
               if o.kind in ("matmul", "fused_matmul_bias_relu")), None)
    if mm is None:
        return True, "终图无 matmul 类算子，golden 无账可记"
    a64, b64 = env64[mm.inputs[0]], env64[mm.inputs[1]]
    atol = matmul_atol(a64, b64)
    out32 = np.asarray([env32[r] for r in c.g_opt.returns][0], dtype=np.float64)
    out64 = np.asarray([env64[r] for r in c.g_opt.returns][0], dtype=np.float64)
    ok, max_abs, _ = pl.check_close(out32, out64, 1e-5, atol)
    return (ok, f"fp32 vs fp64：max|diff| = {max_abs:.3g} ≤ 账本 atol = {atol:.3g}"
            if ok else f"golden 出账：max|diff| = {max_abs:.3g} > atol = {atol:.3g}")


def ck_d3(c: Ctx):
    scales = [o.scale for o in list(c.g_orig.ops) + list(c.g_opt.ops)
              if o.kind in ("quantize", "dequantize")]
    bad = [s for s in scales if not is_pow2(s)]
    return (not bad,
            f"图内 Q/DQ scale 共 {len(set(scales))} 个，全部为 2 的幂"
            + ("" if scales else "（终图已无量化节点，按原图声明核验）")
            if not bad else f"非 2 幂 scale：{bad[:3]}（golden 须同精度并放宽一个 scale）")


def ck_d4(c: Ctx):
    shapes, _ = c.g_opt.infer_shapes()
    bad = []
    for o in c.g_opt.ops:
        if o.kind == "fused_matmul_bias_relu":
            out = shapes[o.name]
            bs = shapes[o.inputs[2]]
            n = out[-1] if out else None
            if bs not in ((), (n,), (1, n)):
                bad.append((o.name, bs))
    return (not bad,
            "融合核 bias 形状全部在支持集 {(), (N,), (1,N)} 内（结构门复核）" if not bad
            else f"bias 形状越界：{bad}（融合核只实现了列广播）")


def ck_e1(c: Ctx):
    if c.ir_before is None:
        return True, "（该场景无快照约定，跳过）"
    same = c.g_orig.dump_ir() == c.ir_before
    return (same, "优化在副本上执行，原图 IR 逐字未动（对照基准保住了）" if same
            else "原图被就地改写——对照对象消失，位等价会变成自己和自己比")


def ck_e2(c: Ctx):
    rewrites = len(c.g_orig.ops) - len(c.g_opt.ops)
    ok = len(c.audit) >= max(rewrites, 1)
    return (ok, f"改写 {rewrites} 步，审计 {len(c.audit)} 行（先记账后动手）" if ok
            else f"改写 {rewrites} 步，审计只有 {len(c.audit)} 行——有动作没记账")


def ck_e3(c: Ctx):
    hit = [a for a in c.audit if any(k in a for k in ("融合", "拒绝", "登记", "报警"))]
    return (bool(hit), f"审计含 {len(hit)} 行候选决策（融合/拒绝/登记/报警）——拒绝也是决策"
            if hit else "审计里找不到任何候选决策行")


CHECKLIST = [
    ("A 结构", "A1", "终图过 Verifier（Shape 可推导、引用无悬空）", "D12/39/59/60/64", ck_a1),
    ("A 结构", "A2", "被删节点无残留引用（rewire 纪律）", "D45/51/52", ck_a2),
    ("A 结构", "A3", "清理不动点已收敛", "D69", ck_a3),
    ("B 布局", "B1", "reshape 不吃非连续生产者（元信息前提）", "D57/59/66", ck_b1),
    ("B 布局", "B2", "无漏折的编译期数据移动（transpose 祖先须含运行时输入）", "D64/65/83", ck_b2),
    ("B 布局", "B3", "reshape 链深度 ≤ 1（合并完成）", "D66", ck_b3),
    ("C 资源", "C1", "融合有账：候选有 ΔB 与工作集记录", "D72/73/76", ck_c1),
    ("C 资源", "C2", "决策一致：判融合 ⇒ 无 spill 且 ΔB>0", "D74/76", ck_c2),
    ("C 资源", "C3", "资源红线复核：1024³ 必须判拒绝", "D73/76", ck_c3),
    ("D 数值", "D1", "位等价：优化 vs 原图，容差 = 0", "D79/83", ck_d1),
    ("D 数值", "D2", "golden：fp32 vs fp64 在账本 atol 内", "D78/79", ck_d2),
    ("D 数值", "D3", "量化声明：Q/DQ scale 为 2 的幂", "D81/82/83", ck_d3),
    ("D 数值", "D4", "融合核 bias 形状在支持集内（结构门复核）", "D74/83", ck_d4),
    ("E 流程", "E1", "原图不动：优化在副本上执行", "D82/83", ck_e1),
    ("E 流程", "E2", "审计先于动作：改写步数 ≤ 审计行数", "D82/83", ck_e2),
    ("E 流程", "E3", "拒绝也是决策：候选决策在审计中可查", "D75/82/83", ck_e3),
]


def run_checklist(c: Ctx, verbose=True) -> dict[str, bool]:
    """跑整套清单，返回 {编号: 通过?}。探针的命中列就从这里读。"""
    results = {}
    if verbose:
        say(f"\n◆ 场景：{c.name}（原图 {len(c.g_orig.ops)} 节点 → 终图 {len(c.g_opt.ops)} 节点）")
    for group, cid, title, src, fn in CHECKLIST:
        ok, detail = fn(c)
        results[cid] = ok
        if verbose:
            mark = "PASS" if ok else "FAIL"
            say(f"  [{mark}] {cid} {title} —— {detail}")
    n_ok = sum(results.values())
    if verbose:
        say(f"  小计：{n_ok}/{len(CHECKLIST)} 通过"
            + ("（全绿）" if n_ok == len(CHECKLIST) else "（有红项——清单拦下了它）"))
    return results


# ============================================================
# 场景与探针的构造
# ============================================================

def feed_fixed() -> dict:
    return {"%x": np.array(X_FLAT, dtype=np.float32).reshape(2, 12)}


def feeds_random(n_rnd=2, seed=84) -> list[dict]:
    rng = np.random.default_rng(seed)
    out = [feed_fixed()]
    for _ in range(n_rnd):
        out.append({"%x": rng.uniform(-2.0, 2.0, size=(2, 12)).astype(np.float32)})
    return out


def ctx_main() -> Ctx:
    """场景 1：主图（11→5）。优化前后各留快照，E1 检查原图未动。"""
    g = pl.build_main_graph()
    ir_before = g.dump_ir()
    res = pl.optimize(g)
    return Ctx("主图：该融就融（11→5）", g, res["graph"], res["audit"],
               feeds_random(), ir_before)


def ctx_multiuser() -> Ctx:
    """场景 2：matmul 输出同时也是图输出（多使用者）——正确结局是拒绝融合。"""
    g = pl.build_main_graph()
    mm = [o for o in g.ops if o.kind == "matmul"][0]
    ru = [o for o in g.ops if o.kind == "relu"][0]
    g.returns = [ru.name, mm.name]
    ir_before = g.dump_ir()
    res = pl.optimize(g)
    return Ctx("多使用者图：该拒就拒（11→7）", g, res["graph"], res["audit"],
               feeds_random(), ir_before)


def probe_p1() -> Ctx:
    """探针 P1（数值破坏）：变体图正常优化后，手痒删掉尾部 Q→DQ。
    这正是 Day 82 规则表里 R06 拒绝实现的不安全规则——「删掉=悄悄取消该边量化」。"""
    gv = pl.build_variant_graph()
    ir_before = gv.dump_ir()
    res = pl.optimize(gv)                       # 正常管道：13 → 7
    g = res["graph"]
    q = [o for o in g.ops if o.kind == "quantize"][0]
    dq = [o for o in g.ops if o.kind == "dequantize"][0]
    src = g.producers()[q.inputs[0]]            # 尾对的生产者（融合核输出）
    g.returns = [src.name]                      # 不安全改写：返回未量化的值
    g.remove(dq.name)
    g.remove(q.name)
    audit = res["audit"] + [f"[探针P1] 手痒规则：删除尾部 Q→DQ（R06 明确拒绝的不安全改写）"]
    return Ctx("P1 数值破坏：删尾部 QDQ（13→5）", gv, g, audit,
               feeds_random(seed=85), ir_before)


def probe_p2() -> Ctx:
    """探针 P2（结构破坏）：多使用者图清理后，忘记单使用者检查强行融合，
    rewire 只迁移 relu 的使用者，matmul 的图输出引用成了悬空。"""
    g = pl.build_main_graph()
    mm = [o for o in g.ops if o.kind == "matmul"][0]
    ru = [o for o in g.ops if o.kind == "relu"][0]
    g.returns = [ru.name, mm.name]
    ir_before = g.dump_ir()
    g_orig = g.copy()
    audit, rounds = run_cleanup(g)              # 清理正常：11 → 7
    audit = [f"[闸0] 合法性检查通过（11 个节点）"] + audit
    mm = [o for o in g.ops if o.kind == "matmul"][0]
    ad = next(o for o in g.ops if o.kind == "add" and o.inputs[0] == mm.name)
    ru = next(o for o in g.ops if o.kind == "relu" and o.inputs[0] == ad.name)
    fused = g.add("fused_matmul_bias_relu", [mm.inputs[0], mm.inputs[1], ad.inputs[1]])
    g.rewire(ru.name, fused)                    # bug：只迁移了 relu 的使用者
    g.remove(ru.name)
    g.remove(ad.name)
    g.remove(mm.name)                           # mm 还被 returns 引用着——断链
    audit.append(f"[探针P2] 断链融合：未查单使用者，%{mm.name[1:]} 的图输出引用悬空")
    return Ctx("P2 结构破坏：断链融合（11→?）", g_orig, g, audit,
               feeds_random(seed=86), ir_before)


def probe_p3() -> Ctx:
    """探针 P3（资源破坏）：主图正常优化，但决策记录里伪造一份 1024³ 强融。"""
    base = ctx_main()
    big = fusion_cost((1024, 1024), (1024, 1024), Machine())
    forged = pl.CostReport(big.m, big.k, big.n, big.delta_b, big.workset,
                           big.spill, "融合（手痒：无视 spill）", "伪造决策")
    return Ctx("P3 资源破坏：1024³ 强融（决策伪造）", base.g_orig, base.g_opt,
               base.audit + ["[探针P3] 伪造决策记录：工作集 12 MiB 顶爆片上 256 KiB 仍判融合"],
               base.feeds, base.ir_before, extra_reports=[forged])


# ============================================================
# Part 1 + Part 2：清单 × 场景 × 探针
# ============================================================

def part1_and_2() -> dict[str, dict[str, bool]]:
    hr("Part 1  优化正确性检查清单 v1.0 —— 两个全绿场景")
    say("清单不是给人背的备忘录：每一项都是一个能跑的函数，套在优化结果上。")
    say(f"五组 {len(CHECKLIST)} 项：A 结构（合法）/ B 布局 / C 资源 / D 数值 / E 流程")
    r_main = run_checklist(ctx_main())
    r_multi = run_checklist(ctx_multiuser())

    hr("Part 2  负例探针 ×3 —— 只在好图上全绿过的清单等于没测过")
    say("三个探针各破坏一个语义维度，看清单的哪一列把它拦下来：")
    r_p1 = run_checklist(probe_p1())
    r_p2 = run_checklist(probe_p2())
    r_p3 = run_checklist(probe_p3())

    say("\n探针 × 清单组 矩阵（✓=该组全过，✗=该组有红项）：")
    header = f"{'场景/探针':<26}{'A结构':>7}{'B布局':>7}{'C资源':>7}{'D数值':>7}{'E流程':>7}"
    say(header)

    def row(label, r):
        cells = ""
        for grp in ("A", "B", "C", "D", "E"):
            ids = [cid for g, cid, *_ in CHECKLIST if g.startswith(grp)]
            bad = [cid for cid in ids if not r[cid]]
            cells += f"{('✗' + ','.join(bad)) if bad else '✓':>7}"
        say(f"{label:<26}{cells}")

    row("主图 11→5（全绿）", r_main)
    row("多使用者 11→7（全绿）", r_multi)
    row("P1 删尾部QDQ", r_p1)
    row("P2 断链融合", r_p2)
    row("P3 1024³强融", r_p3)

    say("\n读法：P1 只有 D 数值列变红（结构全过、图能跑、就是数不对——")
    say("      印证 Day 82 的判断：这类改写只有位等价能抓住）；")
    say("      P2 第一时间红在 A 结构列（引用悬空），断链的融合还顺手跳过了收益账")
    say("      （C1）和审计纪律（E2），D1/D2 只能报「无法执行」——结构坏了，")
    say("      数值连出场的机会都没有；")
    say("      P3 只红 C 资源列（图本身没坏，坏的是决策记录的一致性）。")
    say("      列与列互不代劳——Day 77 的三张 certificate，在阶段收官长成了五组清单。")
    return {"main": r_main, "multi": r_multi, "p1": r_p1, "p2": r_p2, "p3": r_p3}


# ============================================================
# Part 3  补讲 1（Layout 缺口）：剩下的 reshape 贵不贵？
# ============================================================

def part3_layout() -> dict:
    hr("Part 3  补讲 1（Layout）：终图剩下的 reshape(2,12 → 4,6) 到底贵不贵？")
    say("Day 83 收官时留了一句话：「剩下的 reshape 不能删」。讲稿排练时这里最容易卡壳——")
    say("它到底是一个运行时开销，还是一个纸面符号？用同一块存储做三种读法：")

    buf = np.array(X_FLAT, dtype=np.float32).reshape(2, 12)   # x 的物理存储（连续）
    say(f"\n物理存储 buf：shape={buf.shape}，C 连续={buf.flags['C_CONTIGUOUS']}，"
        f"共 {buf.size} 个 fp32")

    say("\n读法一：reshape 成 (4,6) 当作视图（numpy 自动做的事）")
    v = buf.reshape(4, 6)
    say(f"  v = buf.reshape(4,6)：shares_memory = {np.shares_memory(buf, v)}"
        f"，strides = {v.strides} 字节 → 零拷贝，纯元信息")

    say("\n读法二：stride 描述符（第四阶段 Lowering 的预演）——不给数据搬家，")
    say("  只告诉硬件「按 (6,1) 的步长把这块 (2,12) 缓冲当 (4,6) 读」")
    sv = np.lib.stride_tricks.as_strided(
        buf, shape=(4, 6), strides=(6 * buf.itemsize, 1 * buf.itemsize))
    say(f"  as_strided(buf, (4,6), strides=(24,4)B)：shares_memory = "
        f"{np.shares_memory(buf, sv)}")

    say("\n读法三：老老实实物化一份新拷贝（数据真的搬了家）")
    cv = v.copy()
    say(f"  v.copy()：shares_memory = {np.shares_memory(buf, cv)}"
        f"（新分配了一块 {cv.nbytes} B）")

    say("\n偏移公式对照：两种逻辑形状读的是同一条线性序——")
    off_212 = [12 * i + j for i in range(2) for j in range(12)]
    off_46 = [6 * p + q for p in range(4) for q in range(6)]
    say(f"  (i,j)→12i+j 的 24 个偏移 == (p,q)→6p+q 的 24 个偏移：{off_212 == off_46}")

    say("\n反例（连续性前提不是免费的）：转置视图上做 reshape，元信息改写退化为物理搬运")
    t = buf.T                                       # (12,2)，非连续
    c2 = t.reshape(2, 12)                           # numpy 被迫拷贝
    say(f"  t = buf.T（非连续），t.reshape(2,12)：shares_memory = "
        f"{np.shares_memory(t, c2)} → 发生了真实的数据移动")

    say("\n三种读法喂进同一个 GEMM，位等价核验（用的是终图里折叠好的常量 Ŵᵀ）：")
    res = pl.optimize(pl.build_main_graph())
    gopt = res["graph"]
    wst = next(o for o in gopt.ops
               if o.kind == "const" and o.value.shape == (6, 3)).value
    r_view = np.matmul(v, wst)
    r_stride = np.matmul(sv, wst)
    r_copy = np.matmul(cv, wst)
    say(f"  view   @ Ŵᵀ == stride描述符 @ Ŵᵀ：{np.array_equal(r_view, r_stride)}")
    say(f"  view   @ Ŵᵀ == 物化拷贝  @ Ŵᵀ：{np.array_equal(r_view, r_copy)}")

    say("\n结论（补讲 1 的标准答案，三句话）：")
    say("  ① 图层面它必须保留：matmul 的 Shape 契约要求 (M,K) 输入，删掉 reshape")
    say("     图就不合法；「按任意 stride 读缓冲」是 Lowering 的能力，图优化器不越权；")
    say("  ② 物理层面它免费：x 连续，(2,12)→(4,6) 是同一条线性序的两种记法，")
    say(f"     零拷贝（shares_memory=True 实测），Lowering 用 stride 描述符即可吸收；")
    say("  ③ 前提要写进清单：B1 之所以检查「reshape 不吃非连续生产者」，就是因为")
    say("     转置视图上的 reshape 会退化成真实搬运（反例实测 shares_memory=False）。")
    return {"view_is_stride": bool(np.array_equal(r_view, r_stride)),
            "view_is_copy": bool(np.array_equal(r_view, r_copy)),
            "offsets_equal": off_212 == off_46}


# ============================================================
# Part 4  补讲 2（量化缺口）：非 2 幂 scale 的半格分叉
# ============================================================

def codes_fp32(w32: np.ndarray, s: float) -> np.ndarray:
    """执行器口径：fp32 数组除以 scale（结果落 fp32），再 round。"""
    return np.round(w32 / np.float32(s))


def codes_fp64(w32: np.ndarray, s: float) -> np.ndarray:
    """golden 口径：同一批 fp32 值升到 fp64 再除、再 round。"""
    return np.round(w32.astype(np.float64) / np.float64(s))


def half_grid_scan(s: float, steps: int = 4) -> list[tuple[int, float]]:
    """沿每条半格 (k+0.5)·s 的 fp32 邻域定向扫描，收集 fp32/fp64 分叉点。"""
    hits = []
    for k in range(1, 128):
        w0 = np.float32((k + 0.5) * s)
        cands = [w0]
        for _ in range(steps):
            cands.append(np.nextafter(cands[-1], np.float32(np.inf)))
            cands.append(np.nextafter(cands[-1], np.float32(-np.inf)))
        for cand in dict.fromkeys(cands):
            if codes_fp32(np.array([cand]), s)[0] != codes_fp64(np.array([cand]), s)[0]:
                hits.append((k, float(cand)))
    return hits


def part4_quant() -> dict:
    hr("Part 4  补讲 2（量化）：s = max|W|/127 时，fp32 和 fp64 为何各舍各的？")
    say("Day 83 错误 4 留下的坑：常规校准 scale 不是 2 的幂，golden 对比会「无缘无故」")
    say("差出一个码。复盘排练时这句话最难讲清楚——今天把它解剖开：")

    s_cal = 0.7 / 127.0
    say(f"\n常规校准：s = max|W|/127 = 0.7/127 = {s_cal:.10g}（不是 2 的幂）")

    rng = np.random.default_rng(84)
    n = 2_000_000
    w32 = rng.uniform(-0.7, 0.7, size=n).astype(np.float32)
    q32, q64 = codes_fp32(w32, s_cal), codes_fp64(w32, s_cal)
    n_div = int((q32 != q64).sum())
    say(f"随机压测：{n:,} 个 fp32 权重，fp32/fp64 取整分叉 {n_div} 个"
        f"（{n_div / n:.6%}——半格是道窄门，随机数据很难正中）")

    hits = half_grid_scan(s_cal)
    say(f"定向扫描：沿 k=1..127 每条半格 (k+0.5)·s 的 fp32 邻域逐点检查，"
        f"命中 {len(hits)} 个分叉点——分叉不是都市传说，是窄概率事件")

    say("\n分叉点解剖（半格机制）：真商贴着 k+0.5 时，两种精度看到的商不一致，")
    say("  round 一个向下 一个向上，码差 1，反量化后差整整一个 scale：")
    k, wv = hits[0]
    w_arr = np.array([wv], dtype=np.float32)
    d32 = float(w_arr[0] / np.float32(s_cal))
    d64 = float(w_arr[0].astype(np.float64) / s_cal)
    c32 = int(codes_fp32(w_arr, s_cal)[0])
    c64 = int(codes_fp64(w_arr, s_cal)[0])
    say(f"  实弹（定向扫描第一发）：w = {wv!r}（目标半格 k={k}，w ≈ (k+0.5)·s）")
    say(f"    fp32 商 w/s = {d32!r}")
    say(f"    fp64 商 w/s = {d64!r}")
    say(f"    半格 = {k + 0.5}（fp32 商距半格 {d32 - (k + 0.5):+.3e}，"
        f"fp64 商距半格 {d64 - (k + 0.5):+.3e}）")
    say(f"    → fp32 的除法把商舍到了半格上，round-half-even 进到 {c32}；")
    say(f"      fp64 看到的商在半格下方，退回 {c64}——码差 1")
    say(f"    → 反量化值差 = |s·{c32} − s·{c64}| = {abs(s_cal * (c32 - c64)):.6g}"
        f" = 一个 scale（s = {s_cal:.6g}）")

    say("\n修正 A：scale 取 2 的幂（Day 83 主图的纪律，s = 2^-7 = 1/128）")
    s_pow2 = 2.0 ** -7
    q32b, q64b = codes_fp32(w32, s_pow2), codes_fp64(w32, s_pow2)
    n_div_b = int((q32b != q64b).sum())
    hits_b = half_grid_scan(s_pow2)
    say(f"  同一批 {n:,} 个权重换 s = 1/128：随机分叉 {n_div_b} 个，定向扫描 {len(hits_b)} 个")
    say(f"  ——除以 2 的幂是精确操作，两种精度看到同一个商，round 永远落在同一格")

    say("\n修正 B：golden 的量化步骤与被测实现同精度（fp32）——分叉被构造性消灭，")
    say("  账本只需覆盖执行误差；若必须保留非 2 幂 scale，atol 放宽一个 scale 并写明理由")
    q32c = codes_fp32(w32, s_cal)
    q64c = codes_fp32(w32, s_cal)      # 参考也用 fp32 口径做量化
    n_div_c = int((q32c != q64c).sum())
    say(f"  同精度复核：分叉 {n_div_c} 个（对照 D3 检查项的「否则」分支）")
    return {"div_cal": n_div, "div_cal_scan": len(hits), "div_pow2": n_div_b,
            "div_pow2_scan": len(hits_b), "div_sameprec": n_div_c,
            "dissect": (k, wv, d32, d64, c32, c64)}


# ============================================================
# Part 5  第三阶段数字复跑 + 阶段地图
# ============================================================

def part5_stage_numbers() -> dict:
    hr("Part 5  第三阶段数字复跑（今天的「阶段总结」底稿，全部当场重算）")
    g = pl.build_main_graph()
    ir_before = g.dump_ir()
    res = pl.optimize(g)
    gopt = res["graph"]
    n0, n1, n2 = 11, res["n_cleanup"], len(gopt.ops)

    def runtime_ops(gr):
        return sum(1 for o in gr.ops if o.kind not in ("arg", "const"))

    say(f"节点数：{n0} → {n1}（清理不动点）→ {n2}（融合后）")
    say(f"运行时算子：{runtime_ops(g)} → {runtime_ops(gopt)}"
        "（Q/DQ/转置/一次 reshape/matmul/add/relu → reshape + fused）")

    feeds = [feed_fixed()]
    rng = np.random.default_rng(84)
    for _ in range(3):
        feeds.append({"%x": rng.uniform(-2.0, 2.0, size=(2, 12)).astype(np.float32)})
    ok_bit, _ = verify_bit_exact(g, gopt, feeds)
    say(f"位等价（容差=0）：固定输入 + 3×1 随机输入 → {ok_bit}")

    env32 = run_env(gopt, feeds[0], np.float32)
    env64 = run_env(gopt, feeds[0], np.float64)
    mm = next(o for o in gopt.ops if o.kind == "fused_matmul_bias_relu")
    atol = matmul_atol(env64[mm.inputs[0]], env64[mm.inputs[1]])
    out32 = env32[gopt.returns[0]].astype(np.float64)
    out64 = env64[gopt.returns[0]].astype(np.float64)
    ok_gold, max_abs, _ = pl.check_close(out32, out64, 1e-5, atol)
    say(f"golden：max|diff| = {max_abs:.3g}，账本 atol = (2K+2)·eps32·maxΣ|a·b| = "
        f"{atol:.3g} → {'通过' if ok_gold else '出账'}（K=6）")

    rep = fusion_cost((4, 6), (6, 3), Machine())
    say(f"融合账：ΔB = 16·M·N = {rep.delta_b} B，工作集 {rep.workset} B ≤ 片上 "
        f"{fmt_b(Machine().onchip_bytes)} → {rep.decision}")
    rep1k = fusion_cost((1024, 1024), (1024, 1024), Machine())
    say(f"红线复核：1024³ 时 ΔB = {fmt_b(rep1k.delta_b)}，工作集 {fmt_b(rep1k.workset)} "
        f"> 片上 → {rep1k.decision}")

    say("\n第三阶段地图（28 天 → 4 周 → 1 句话）：")
    say("  W9（D57~63） Shape/Stride/Layout 地基——「Shape 相同 ≠ 内存布局相同」")
    say("  W10（D64~70）布局与冗余消除——「图结构相同 ≠ 内存语义相同」")
    say("  W11（D71~77）融合收益与代价——「合法/正确/更快是三张不同的 certificate」")
    say("  W12（D78~84）数值精度与量化——「位等价与 golden 是两本账」")
    say("  一句话：图编译器不仅做模式匹配，还要管理布局、资源和数值语义。")
    return {"bit": ok_bit, "gold": ok_gold}


# ============================================================
# 汇总与 main
# ============================================================

def summarize(results, lay, qnt, stage) -> None:
    hr("汇总")
    n_items = len(CHECKLIST)
    greens = sum(1 for r in (results["main"], results["multi"])
                 if all(r.values()))
    caught = {p: [cid for cid, ok in results[p].items() if not ok]
              for p in ("p1", "p2", "p3")}
    check("清单在两个正例场景全绿（16 项 × 2 场景）",
          greens == 2 and n_items == 16, f"{greens}/2 场景全绿")
    check("P1 数值探针被 D1 位等价拦下", "D1" in caught["p1"],
          f"红项 {caught['p1']}")
    check("P2 结构探针被 A 组拦下", any(c.startswith("A") for c in caught["p2"]),
          f"红项 {caught['p2']}")
    check("P3 资源探针被 C2 决策一致性拦下", "C2" in caught["p3"],
          f"红项 {caught['p3']}")
    check("补讲1：视图 == stride 描述符 == 物化拷贝（位等价）",
          lay["view_is_stride"] and lay["view_is_copy"] and lay["offsets_equal"])
    check("补讲2：常规校准 scale 分叉 > 0，2 幂 scale 分叉 = 0",
          qnt["div_cal"] + qnt["div_cal_scan"] > 0
          and qnt["div_pow2"] == 0 and qnt["div_pow2_scan"] == 0,
          f"常规校准：随机 {qnt['div_cal']} + 定向 {qnt['div_cal_scan']}；"
          f"2 幂：随机 {qnt['div_pow2']} + 定向 {qnt['div_pow2_scan']}")
    check("补讲2：同精度 golden 分叉为 0", qnt["div_sameprec"] == 0)
    check("阶段数字复跑：位等价 + golden 双通过",
          stage["bit"] and stage["gold"])
    say(f"\n检查项合计：{PASS}/{PASS + FAIL} 通过")
    say("产出：优化正确性检查清单 v1.0（五组 16 项，可执行）+ 补讲 ×2 + 阶段总结底稿")


def main() -> int:
    say("第 84 天：第 12 周复盘 · 第三阶段收官 —— 检查清单 v1.0")
    say(f"环境：Python {sys.version.split()[0]}，numpy {np.__version__}，"
        f"{sys.platform}")
    say(f"复用：../day-083/code/pipeline_lab.py（只取不改）")
    results = part1_and_2()
    lay = part3_layout()
    qnt = part4_quant()
    stage = part5_stage_numbers()
    summarize(results, lay, qnt, stage)
    REPORT.write_text("\n".join(LINES) + "\n", encoding="utf-8")
    say(f"\n完整报告已归档：{REPORT.relative_to(HERE)}")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
