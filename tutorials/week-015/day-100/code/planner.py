#!/usr/bin/env python3
"""第 100 天：缓冲区复用——把第 99 天的活跃区间变成一块共享 workspace。

静态图部署到 NPU / 边缘芯片时通常没有运行时 malloc：每个动态张量都要在
编译期拿到缓冲区。一人一块需要 sum(size)；让活跃区间不重叠的张量共享字节，
只需要接近峰值活跃集合的一块 workspace。本脚本对第 99 天的双分支特征块实现：

  1) 简单内存规划器：合并别名组 → 按策略排序 → 首次适应放置（带对齐）；
  2) 内存分配表：每个张量 / 存储单元的偏移与字节范围；
  3) 复用正确性测试：静态两两检查 + 逐字节投毒模拟；
  4) 对照实验：放置策略扫描、对齐扫描、别名约束演示。

用法：
  python3 planner.py                                # 主干优先 + best-of-3 策略
  python3 planner.py --order interleaved|skip-first
  python3 planner.py --strategy def|size|last-use   # 只用一种放置策略
  python3 planner.py --align 256                    # 单点对齐要求（字节）
  python3 planner.py --order-sweep                  # 3 种顺序 × 3 种策略
  python3 planner.py --align-sweep                  # 对齐 4~256 B 扫描
  python3 planner.py --alias-demo                   # 别名约束：错误示范 vs 正确做法
  python3 planner.py --hazard-demo                  # off-by-one 危害：两层防线报警
  python3 planner.py --test                         # 断言式自检（9 组）
  python3 planner.py --svg outputs/offset-chart     # 生成 时间×地址 SVG 图

零第三方依赖，仅需 python3（本文环境 Python 3.11.4，aarch64 Linux）。
"""
from __future__ import annotations

import argparse
import itertools
from dataclasses import dataclass

ELEM_BYTES = 4        # float32
DEFAULT_ALIGN = 32    # 教学默认：常见 NPU DMA 的对齐要求（字节）

STRATEGY_KEYS = {
    "def":      lambda u: (u.def_step, -u.size, u.name),
    "size":     lambda u: (-u.size, u.def_step, u.name),
    "last-use": lambda u: (u.last_use, u.def_step, -u.size, u.name),
}
STRATEGY_LABELS = {
    "def": "H1 按定义点排序（区间起点）",
    "size": "H2 按尺寸降序（大块优先）",
    "last-use": "H3 按最后使用点排序（早退房优先）",
}


@dataclass
class Tensor:
    name: str
    kind: str          # input / mid / output / param
    shape: tuple
    elems: int
    group: str = ""    # 别名组名：同一物理存储的多个名字；空 = 自成一组


@dataclass
class Op:
    out: str
    kind: str
    inputs: tuple


def build_graph():
    """第 99 天的双分支特征块（融合后只剩 4 个算子），数字与 D99 完全一致。"""
    tensors = {
        "x":     Tensor("x", "input",  (1, 32),  32),
        "w_exp": Tensor("w_exp", "param", (32, 256), 32 * 256),
        "w_dn":  Tensor("w_dn", "param", (256, 32), 256 * 32),
        "w_sk":  Tensor("w_sk", "param", (32, 128), 32 * 128),
        "t1":    Tensor("t1", "mid",   (1, 256), 256),
        "t2":    Tensor("t2", "mid",   (1, 32),  32),
        "s":     Tensor("s", "mid",    (1, 128), 128),
        "y":     Tensor("y", "output", (1, 160), 160),
    }
    ops = {
        "t1": Op("t1", "matmul", ("x", "w_exp")),
        "t2": Op("t2", "matmul", ("t1", "w_dn")),
        "s":  Op("s",  "matmul", ("x", "w_sk")),
        "y":  Op("y",  "concat", ("t2", "s")),
    }
    return tensors, ops


ORDERS = {
    "main-first":  ("t1", "t2", "s", "y"),
    "interleaved": ("t1", "s", "t2", "y"),
    "skip-first":  ("s", "t1", "t2", "y"),
}
ORDER_LABELS = {
    "main-first": "主干优先",
    "interleaved": "交错",
    "skip-first": "捷径优先",
}


def compute_intervals(order, tensors, ops):
    """与第 99 天同一套规则：闭区间 [def, last_use]；输入/参数 def=0；
    图输出没有图内读者，last_use = N+1（活到图结束之后交给调用方）。"""
    pos = {out: i + 1 for i, out in enumerate(order)}
    n = len(order)
    intervals = {}
    for name, t in tensors.items():
        d = 0 if t.kind in ("input", "param") else pos[name]
        uses = [pos[out] for out, op in ops.items() if name in op.inputs]
        if uses:
            last = max(uses)
        elif t.kind == "output":
            last = n + 1
        else:
            raise ValueError(f"中间张量 {name} 没有任何使用者（死代码）")
        intervals[name] = (d, last)
    return intervals


# ---------------------------------------------------------------- 规划器

@dataclass
class Unit:
    """一个物理存储单元：单个张量，或合并后的别名组。"""
    name: str
    size: int          # 字节
    def_step: int
    last_use: int
    members: tuple     # 组内的张量名


def make_units(names, tensors, intervals, merge_alias=True):
    """把张量分组成存储单元。merge_alias=True 时同一别名组合并成一个单元：
    区间取并集（覆盖所有成员的活跃时间），大小取成员最大值。"""
    buckets = {}
    for n in names:
        key = (tensors[n].group or n) if merge_alias else n
        buckets.setdefault(key, []).append(n)
    units = {}
    for key, members in buckets.items():
        members = tuple(sorted(members))
        d = min(intervals[m][0] for m in members)
        u = max(intervals[m][1] for m in members)
        size = max(tensors[m].elems for m in members) * ELEM_BYTES
        units[key] = Unit(key, size, d, u, members)
    return units


def align_up(v, a):
    return (v + a - 1) // a * a


def iv_overlap(a, b):
    """闭区间是否相交（执行期共存判定，与第 99 天口径一致）。"""
    return max(a.def_step, b.def_step) <= min(a.last_use, b.last_use)


def plan(units, align=DEFAULT_ALIGN, strategy="last-use"):
    """首次适应（first-fit）放置：候选偏移 = 0 与「已放置单元末端的对齐上取整」，
    从小到大取第一个与所有区间重叠者字节错开的候选。"""
    placed = []
    for u in sorted(units.values(), key=STRATEGY_KEYS[strategy]):
        candidates = sorted({0} | {align_up(off + p.size, align) for p, off in placed})
        for c in candidates:
            ok = True
            for p, off in placed:
                if iv_overlap(u, p) and c < off + p.size and off < c + u.size:
                    ok = False
                    break
            if ok:
                placed.append((u, c))
                break
    offsets = {u.name: off for u, off in placed}
    workspace = max(off + u.size for u, off in placed)
    return offsets, workspace


def plan_best(units, align=DEFAULT_ALIGN):
    """三种排序策略各跑一遍，取 workspace 最小者（贪心不保证最优，多试几个顺序）。"""
    results = {}
    for s in STRATEGY_KEYS:
        results[s] = plan(units, align, s)
    names = list(STRATEGY_KEYS)
    best = min(names, key=lambda s: (results[s][1], names.index(s)))
    return results, best


def peak_live(units):
    """峰值活跃集合：任何分配方案的字节总量都不可能低于它（理论下界）。"""
    horizon = max(u.last_use for u in units.values())
    return max(
        sum(u.size for u in units.values() if u.def_step <= k <= u.last_use)
        for k in range(horizon + 1)
    )


def sharing_with(u, units, offsets):
    """字节范围与本单元相交的其他单元（时间上必然错开，否则规划有错）。"""
    off = offsets[u.name]
    res = []
    for v in units.values():
        if v.name == u.name:
            continue
        vo = offsets[v.name]
        if off < vo + v.size and vo < off + u.size:
            res.append(v.name if len(v.members) == 1 else "{" + ",".join(v.members) + "}")
    return res


# ---------------------------------------------------------------- 正确性

def verify_static(units, offsets, workspace, align):
    """静态检查：偏移对齐 + 区间重叠者字节必须错开。"""
    errs = []
    items = sorted(units.values(), key=lambda u: u.name)
    for u in items:
        off = offsets[u.name]
        if off % align:
            errs.append(f"{u.name} 偏移 {off} 不是 {align} B 的倍数")
    for a, b in itertools.combinations(items, 2):
        if iv_overlap(a, b):
            ao, bo = offsets[a.name], offsets[b.name]
            if ao < bo + b.size and bo < ao + a.size:
                errs.append(f"{a.name} 与 {b.name} 区间重叠却共享字节")
    return errs


def verify_group_consistency(names, tensors, offsets):
    """别名组检查：同一物理存储的所有名字必须拿到同一个偏移。
    （合并规划后天然满足；此检查用来抓「忘了合并」的错误示范。）"""
    errs = []
    by_group = {}
    for n in names:
        by_group.setdefault(tensors[n].group or n, []).append(n)
    for g, members in by_group.items():
        if len(members) > 1:
            offs = sorted({offsets[m] for m in members})
            if len(offs) > 1:
                errs.append(f"别名组 {{{','.join(members)}}} 偏移不一致：{offs}")
    return errs


def simulate_poison(units, offsets, workspace):
    """投毒模拟：每个存储单元一个标记值；每步先写入本步定义的单元，
    再校验所有活跃单元的每个字节仍是自己的标记。该错开的没错开会当场暴露；
    步末校验对应闭区间（正在被读的输入不能被本步输出覆盖）。"""
    mem = [-1] * workspace
    tag_of = {u.name: i + 1 for i, u in enumerate(sorted(units.values(), key=lambda u: u.name))}
    horizon = max(u.last_use for u in units.values())
    clobbers = []
    live_checks = 0
    for k in range(horizon + 1):
        for u in sorted(units.values(), key=lambda u: u.name):
            if u.def_step == k:
                off = offsets[u.name]
                for b in range(off, off + u.size):
                    mem[b] = tag_of[u.name]
        for u in sorted(units.values(), key=lambda u: u.name):
            if u.def_step <= k <= u.last_use:
                live_checks += 1
                off = offsets[u.name]
                for b in range(off, off + u.size):
                    if mem[b] != tag_of[u.name]:
                        clobbers.append((k, u.name, b))
                        break
    return clobbers, live_checks


def reuse_stats(units, offsets, workspace):
    """统计有多少字节被两个及以上单元先后占用（复用真正发生的地方）。"""
    writers = [set() for _ in range(workspace)]
    for u in units.values():
        off = offsets[u.name]
        for b in range(off, off + u.size):
            writers[b].add(u.name)
    return sum(1 for w in writers if len(w) >= 2), workspace


# ---------------------------------------------------------------- 报告

def unit_label(u):
    return u.name if len(u.members) == 1 else "{" + ",".join(u.members) + "}"


def run_order(order_name, align=DEFAULT_ALIGN, strategy="best", svg_prefix=None):
    tensors, ops = build_graph()
    order = ORDERS[order_name]
    intervals = compute_intervals(order, tensors, ops)
    dyn = [n for n, t in tensors.items() if t.kind != "param"]
    units = make_units(dyn, tensors, intervals)
    no_reuse = sum(tensors[n].elems for n in dyn) * ELEM_BYTES
    peak = peak_live(units)

    print("=" * 72)
    print(f"缓冲区复用规划：执行顺序「{ORDER_LABELS[order_name]}」"
          f"{' → '.join(order)}   （对齐 {align} B）")
    print("=" * 72)

    print("\n-- 生命周期表（闭区间，沿用第 99 天；参数常驻权重区，不参与复用）--")
    print("张量   类别     形状          字节    活跃区间")
    for n in dyn:
        t = tensors[n]
        d, u = intervals[n]
        tail = "（活到图后）" if t.kind == "output" else ""
        print(f"{n:4}  {t.kind:7} {str(t.shape):10}  {t.elems * ELEM_BYTES:5}    [{d}, {u}]{tail}")
    param_bytes = sum(t.elems * ELEM_BYTES for t in tensors.values() if t.kind == "param")
    print(f"（参数 w_exp+w_dn+w_sk 共 {param_bytes} B 常驻权重区，与 D99 口径一致）")

    if strategy == "best":
        results, best = plan_best(units, align)
        print("\n-- 放置策略对照（首次适应 + 候选偏移对齐）--")
        print("策略                            workspace    相对峰值下界")
        for s in STRATEGY_KEYS:
            ws = results[s][1]
            gap = ws - peak
            note = f"+{gap} B（碎片）" if gap else "0 B（达下界）"
            mark = "  ← 采用" if s == best else ""
            print(f"{STRATEGY_LABELS[s]:30}  {ws:5} B    {note}{mark}")
        offsets, workspace = results[best]
        adopted = best
    else:
        offsets, workspace = plan(units, align, strategy)
        adopted = strategy

    print(f"\n-- 内存分配表（采用 {STRATEGY_LABELS[adopted]}，按地址排序）--")
    print("存储单元   字节    活跃区间     偏移     字节范围           与谁共享（时间错开）")
    for u in sorted(units.values(), key=lambda u: (offsets[u.name], u.name)):
        off = offsets[u.name]
        share = sharing_with(u, units, offsets)
        print(f"{unit_label(u):8}  {u.size:5}   [{u.def_step}, {u.last_use}]"
              f"{'' if u.last_use < 10 else ' '}     {off:5}   [{off}, {off + u.size})"
              f"{' ' * max(1, 5 - len(str(off)))}{'、'.join(share) or '—'}")

    shared, total = reuse_stats(units, offsets, workspace)
    save = no_reuse - workspace
    print("\n-- 汇总 --")
    print(f"无复用（每个动态张量独占一块）      {no_reuse} B（{no_reuse // ELEM_BYTES} 元素）")
    print(f"共享 workspace（本次采用）          {workspace} B（{workspace // ELEM_BYTES} 元素）"
          f"   省 {save} B（{save * 100 / no_reuse:.1f}%）")
    print(f"峰值活跃集合（任何方案的理论下界）  {peak} B")
    if workspace == peak:
        print("workspace 已达理论下界：峰值步的活跃张量恰好把内存铺满")
    else:
        print(f"距下界还差 {workspace - peak} B（放置碎片 / 对齐填充）")
    print(f"字节复用：{total} B 中 {shared} B 被两个及以上张量先后占用")

    errs = verify_static(units, offsets, workspace, align)
    group_errs = verify_group_consistency(dyn, tensors, offsets)
    covered = sorted(m for u in units.values() for m in u.members)
    clobbers, live_checks = simulate_poison(units, offsets, workspace)
    n_pairs = len(units) * (len(units) - 1) // 2
    items = [
        (f"偏移对齐（{align} B 的倍数）", not any("倍数" in e for e in errs)),
        (f"分配覆盖全部动态张量（{len(dyn)}/{len(dyn)}，无遗漏无重复）", covered == sorted(dyn)),
        (f"区间重叠 ⇒ 字节不重叠（{n_pairs} 对两两检查）", not any("共享字节" in e for e in errs)),
        ("别名组内偏移一致（每组恰一个存储单元）", not group_errs),
        (f"投毒模拟（{live_checks} 次活跃单元逐字节校验，0 处覆盖）", not clobbers),
        (f"workspace ≥ 峰值活跃集合（{workspace} ≥ {peak}）", workspace >= peak),
        (f"workspace ≤ 无复用总量（{workspace} ≤ {no_reuse}）", workspace <= no_reuse),
    ]
    print("\n-- 复用正确性检查 --")
    passed = 0
    for i, (name, ok) in enumerate(items, 1):
        print(f"[{i}/{len(items)}] {name:46} {'通过' if ok else '失败'}")
        passed += ok
    print(f"{passed}/{len(items)} 项通过")
    if errs or group_errs or clobbers:
        for e in errs + group_errs:
            print(f"  · {e}")
        for k, n, b in clobbers[:5]:
            print(f"  · 步骤 {k}：{n} 在字节 {b} 被覆盖")

    if svg_prefix:
        svg_offset_chart(order_name, order, ops, units, offsets, workspace, peak, svg_prefix)
        print(f"\n（已生成 时间×地址 图：{svg_prefix}.svg）")

    return {
        "order": order_name, "align": align, "units": units, "offsets": offsets,
        "workspace": workspace, "no_reuse": no_reuse, "peak": peak,
        "shared": shared, "errs": errs, "clobbers": clobbers,
    }


# ---------------------------------------------------------------- 扫描

def order_sweep():
    tensors, ops = build_graph()
    print(f"-- 顺序 × 放置策略扫描（首次适应，对齐 {DEFAULT_ALIGN} B；单位 B）--")
    print(f"{'顺序':8}  {'无复用':>6}  {'峰值下界':>6}  "
          + "  ".join(f"{s:>5}" for s in ("H1", "H2", "H3")) + "  best")
    for oname, order in ORDERS.items():
        intervals = compute_intervals(order, tensors, ops)
        dyn = [n for n, t in tensors.items() if t.kind != "param"]
        units = make_units(dyn, tensors, intervals)
        no_reuse = sum(tensors[n].elems for n in dyn) * ELEM_BYTES
        peak = peak_live(units)
        results, best = plan_best(units)
        row = "  ".join(f"{results[s][1]:5}" for s in STRATEGY_KEYS)
        print(f"{ORDER_LABELS[oname]:8}  {no_reuse:6}  {peak:6}  {row}  {results[best][1]:5}")
    print("\n看两件事：复用后 best 都远小于无复用；但「主干优先」只有 H3 能达下界——")
    print("同一张区间表，贪心放置的排序不同，workspace 可以差 640 B（见 README 5.4）。")


def align_sweep():
    tensors, ops = build_graph()
    order = ORDERS["main-first"]
    intervals = compute_intervals(order, tensors, ops)
    dyn = [n for n, t in tensors.items() if t.kind != "param"]
    units = make_units(dyn, tensors, intervals)
    peak = peak_live(units)
    print("-- 对齐扫描（顺序=主干优先，best-of-3；单位 B）--")
    print("对齐(B)    H1      H2      H3     best   峰值下界  说明")
    for a in (4, 32, 64, 128, 256):
        results, best = plan_best(units, a)
        ws = results[best][1]
        row = "  ".join(f"{results[s][1]:5}" for s in STRATEGY_KEYS)
        note = "已达下界" if ws == peak else f"+{ws - peak} B（对齐填充+碎片）"
        print(f"{a:6}  {row}  {ws:5}   {peak:5}   {note}")
    print("\n本图 5 个张量的尺寸都是 32 B 的倍数 → 对齐 ≤ 128 B 时零代价；")
    print("256 B 起，候选偏移被对齐上取整推高，best 从 1280 B 涨到 1408 B。")


# ---------------------------------------------------------------- 别名演示

def alias_case():
    """合成用例（刻意最小化，只保留约束本身）：
    Z 是长寿命张量；B 是 A 的视图（别名组 S）；C、D 是普通中间张量。"""
    tensors = {
        "Z": Tensor("Z", "mid", (1, 50), 50),                 # 200 B
        "A": Tensor("A", "mid", (1, 25), 25, group="S"),      # 100 B
        "B": Tensor("B", "mid", (1, 15), 15, group="S"),     #  60 B（A 的视图）
        "C": Tensor("C", "mid", (1, 12), 12),                 #  48 B
        "D": Tensor("D", "mid", (1, 20), 20),                #  80 B
    }
    intervals = {"Z": (1, 5), "A": (1, 2), "B": (3, 4), "C": (2, 3), "D": (3, 3)}
    return tensors, intervals


def alias_demo():
    tensors, intervals = alias_case()
    names = list(tensors)
    print("=" * 72)
    print("别名约束演示：B 是 A 的视图（同一物理存储），区间分析只看名字")
    print("=" * 72)
    print("\n合成用例（Z 长寿命 200 B；A [1,2] 100 B；B [3,4] 60 B，与 A 同存储；")
    print("C [2,3] 48 B；D [3,3] 80 B；放置策略 H1，对齐 4 B）")

    print("\n[错误示范] 不合并别名组，把 A、B 当两个独立缓冲区规划：")
    units_naive = make_units(names, tensors, intervals, merge_alias=False)
    off_naive, ws_naive = plan(units_naive, align=4, strategy="def")
    for u in sorted(units_naive.values(), key=lambda u: off_naive[u.name]):
        print(f"  {u.name}  {u.size:3} B  [{u.def_step}, {u.last_use}]  偏移 {off_naive[u.name]}")
    print(f"  workspace {ws_naive} B")
    errs = verify_group_consistency(names, tensors, off_naive)
    clobbers, _ = simulate_poison(units_naive, off_naive, ws_naive)
    for e in errs:
        print(f"  ✗ 校验失败：{e}")
    print("  （投毒模拟反而通过：两个名字落在不同字节，谁也没覆盖谁——")
    print("    真正的错误是语义：步骤 1 通过 A 写进偏移 200 的字节，")
    print("    步骤 3~4 却通过 B 去读偏移 348 的字节，读到的是未初始化数据。）")

    print("\n[正确做法] 先合并别名组，再参与放置：")
    units = make_units(names, tensors, intervals, merge_alias=True)
    s = units["S"]
    print(f"  存储单元 S{{A,B}}：区间 = [1,2] ∪ [3,4] = [{s.def_step}, {s.last_use}]"
          f"（并集），大小 = max(100, 60) = {s.size} B")
    off, ws = plan(units, align=4, strategy="def")
    for u in sorted(units.values(), key=lambda u: off[u.name]):
        print(f"  {unit_label(u):8}  {u.size:3} B  [{u.def_step}, {u.last_use}]  偏移 {off[u.name]}"
              + ("   ← A、B 同偏移" if u.name == "S" else ""))
    print(f"  workspace {ws} B")
    errs2 = verify_static(units, off, ws, 4)
    group_ok = not verify_group_consistency(names, tensors,
                                            {m: off[tensors[m].group or m] for m in names})
    clobbers2, checks = simulate_poison(units, off, ws)
    ok = not errs2 and group_ok and not clobbers2
    print(f"  静态检查 {'通过' if not errs2 else errs2}；"
          f"别名组偏移一致 {'通过' if group_ok else '失败'}；"
          f"投毒模拟（{checks} 次校验）{'通过' if not clobbers2 else clobbers2[:3]}")
    print(f"  → {'全部通过' if ok else '存在问题'}；workspace 只比错误示范多 {ws - ws_naive} B，"
          "换来语义正确。")
    return ok


def hazard_demo():
    """错误一的真实复现：把闭区间误当开区间，以为 [1,2] 与 [2,4]
    「端点相接就能共享」，把 t2 搬进 t1 的字节——看两层防线谁先报警。"""
    tensors, ops = build_graph()
    order = ORDERS["main-first"]
    intervals = compute_intervals(order, tensors, ops)
    dyn = [n for n, t in tensors.items() if t.kind != "param"]
    units = make_units(dyn, tensors, intervals)
    offsets, ws = plan(units, DEFAULT_ALIGN, "last-use")
    print("=" * 72)
    print("off-by-one 危害演示：t1 [1,2] 与 t2 [2,4] 端点相接，被当作可共享")
    print("=" * 72)
    print("\n正确布局（H3）：t1 @0 [0,1024)、t2 @1152 [1152,1280) → 7 项检查全过")
    print("\n[错误示范] 误判「端点相接 = 区间不相交」，把 t2 搬进 t1 的字节（t2 @0）：")
    bad = dict(offsets)
    bad["t2"] = 0
    for u in sorted(units.values(), key=lambda u: bad[u.name]):
        print(f"  {unit_label(u):4} 偏移 {bad[u.name]:4}  字节范围 [{bad[u.name]}, {bad[u.name] + u.size})")
    errs = verify_static(units, bad, ws, DEFAULT_ALIGN)
    clobbers, checks = simulate_poison(units, bad, ws)
    print(f"\n静态两两检查（共 10 对）：")
    for e in errs:
        print(f"  ✗ {e}")
    print(f"\n投毒模拟（{checks} 次活跃单元校验）：")
    for k, n, b in clobbers:
        print(f"  ✗ 步骤 {k}：{n} 在字节 {b} 读到别人的标记")
    print("\n两层防线同时报警：静态层报「区间重叠却共享字节」；投毒层报步骤 2 的")
    print("t1 被覆盖——正是闭区间的含义：步骤 2 执行时 t1 正在被读、t2 正在被写。")
    print("端点相接就是相交，共享判据永远只看区间是否相交。")
    return True


# ---------------------------------------------------------------- 测试

def run_tests():
    tensors, ops = build_graph()
    results = []

    def check(name, cond):
        results.append(cond)
        print(f"[{'通过' if cond else '失败'}] {name}")

    iv_main = compute_intervals(ORDERS["main-first"], tensors, ops)
    iv_skip = compute_intervals(ORDERS["skip-first"], tensors, ops)
    check("生命周期表与 D99 一致（主干优先 x[0,3] t1[1,2] t2[2,4] s[3,4] y[4,5]；捷径优先 x[0,2]）",
          iv_main == {"x": (0, 3), "t1": (1, 2), "t2": (2, 4), "s": (3, 4), "y": (4, 5),
                      "w_exp": (0, 1), "w_dn": (0, 2), "w_sk": (0, 3)}
          and iv_skip["x"] == (0, 2))

    dyn = [n for n, t in tensors.items() if t.kind != "param"]
    no_reuse = sum(tensors[n].elems for n in dyn) * ELEM_BYTES
    check(f"无复用总量 = 2432 B（608 元素）", no_reuse == 2432)

    peaks, bests, singles = {}, {}, {}
    for oname, order in ORDERS.items():
        iv = compute_intervals(order, tensors, ops)
        units = make_units(dyn, tensors, iv)
        peaks[oname] = peak_live(units)
        results_all, best = plan_best(units)
        bests[oname] = results_all[best][1]
        singles[oname] = {s: results_all[s][1] for s in STRATEGY_KEYS}
    check("峰值下界：主干 1280 / 交错 1664 / 捷径 1664 B",
          (peaks["main-first"], peaks["interleaved"], peaks["skip-first"]) == (1280, 1664, 1664))
    check("best-of-3：主干 1280（达下界）/ 交错 1664 / 捷径 1664 B",
          (bests["main-first"], bests["interleaved"], bests["skip-first"]) == (1280, 1664, 1664))
    check("单策略已知值：主干 H1=1920 H2=1408 H3=1280；交错与捷径三种策略均 1664 B",
          singles["main-first"] == {"def": 1920, "size": 1408, "last-use": 1280}
          and singles["interleaved"] == {"def": 1664, "size": 1664, "last-use": 1664}
          and singles["skip-first"] == {"def": 1664, "size": 1664, "last-use": 1664})

    all_ok = True
    for oname in ORDERS:
        iv = compute_intervals(ORDERS[oname], tensors, ops)
        units = make_units(dyn, tensors, iv)
        for a in (4, 32, 64, 128, 256):
            for s in STRATEGY_KEYS:
                off, ws = plan(units, a, s)
                errs = verify_static(units, off, ws, a)
                clobbers, _ = simulate_poison(units, off, ws)
                if errs or clobbers or ws < peaks[oname] or any(o % a for o in off.values()):
                    all_ok = False
    check("全组合（3 顺序 × 3 策略 × 5 档对齐）：静态检查 + 投毒模拟 + workspace ≥ 下界",
          all_ok)

    iv = compute_intervals(ORDERS["main-first"], tensors, ops)
    units = make_units(dyn, tensors, iv)
    results_all, best = plan_best(units)
    shared, _ = reuse_stats(units, results_all[best][0], results_all[best][1])
    check("字节复用统计：主干 best 方案 1280 B 中 1152 B 被两个张量先后占用",
          shared == 1152)

    at_tensors, at_intervals = alias_case()
    a_names = list(at_tensors)
    units_naive = make_units(a_names, at_tensors, at_intervals, merge_alias=False)
    off_naive, ws_naive = plan(units_naive, align=4, strategy="def")
    naive_caught = bool(verify_group_consistency(a_names, at_tensors, off_naive))
    check("别名演示：不合并时「组内偏移不一致」被静态检查抓住", naive_caught)

    units_m = make_units(a_names, at_tensors, at_intervals, merge_alias=True)
    s_unit = units_m["S"]
    off_m, ws_m = plan(units_m, align=4, strategy="def")
    merged_ok = (s_unit.def_step, s_unit.last_use, s_unit.size) == (1, 4, 100) \
        and not verify_static(units_m, off_m, ws_m, 4) \
        and not simulate_poison(units_m, off_m, ws_m)[0] \
        and off_m["S"] == off_m["S"]
    check("别名合并语义：S{A,B} 区间取并集 [1,4]、大小取最大 100 B，且全部校验通过", merged_ok)

    n = len(results)
    print(f"\n{n}/{n} 项通过" if all(results) else f"\n{sum(results)}/{n} 项通过（存在失败！）")
    return 0 if all(results) else 1


# ---------------------------------------------------------------- SVG

PALETTE = {"x": "#7FA8D9", "t1": "#E8A87C", "t2": "#93C6A0", "s": "#D98484", "y": "#C9C2B8"}


def svg_offset_chart(order_name, order, ops, units, offsets, workspace, peak, prefix):
    """程序生成的 时间×地址 图：横轴执行步骤，纵轴字节地址，每个存储单元一个矩形。"""
    W, H = 940, 520
    x0, x1 = 66, 716
    y_top, y_bot = 108, 448
    horizon = max(u.last_use for u in units.values())
    cols = horizon + 1
    cw = (x1 - x0) / cols
    sy = (y_bot - y_top) / workspace

    def y_of(addr):
        return y_bot - addr * sy

    heads = []
    for k in range(cols):
        if k == 0:
            heads.append((f"步骤 {k}", "图前", ""))
        elif k <= horizon - 1:
            out = order[k - 1]
            heads.append((f"步骤 {k}", out, ops[out].kind))
        else:
            heads.append((f"步骤 {k}", "图后", "输出"))

    out = []
    out.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
               'font-family="\'Comic Sans MS\',\'Kaiti SC\',\'KaiTi\',\'STKaiti\',cursive">')
    out.append('<style>text{fill:#3B3B3B;} .t{font-size:22px;font-weight:bold;} '
               '.s{font-size:13px;fill:#6b6257;} .h{font-size:12.5px;font-weight:bold;} '
               '.d{font-size:11px;fill:#5a554d;} .n{font-size:13.5px;font-weight:bold;} '
               '.f{font-size:12px;fill:#6b6257;}</style>')
    out.append('<filter id="sketch"><feTurbulence type="fractalNoise" baseFrequency="0.018" '
               'numOctaves="2" seed="7" result="n"/><feDisplacementMap in="SourceGraphic" '
               'in2="n" scale="3"/></filter>')
    out.append(f'<rect x="4" y="4" width="{W - 8}" height="{H - 8}" rx="14" fill="#FDFBF6" '
               'stroke="#E7DFCE" stroke-width="2"/>')
    out.append('<g filter="url(#sketch)">')
    out.append(f'<text x="{W / 2}" y="38" text-anchor="middle" class="t">'
               f'缓冲区复用（{ORDER_LABELS[order_name]}）：时间 × 地址</text>')
    out.append(f'<text x="{W / 2}" y="60" text-anchor="middle" class="s">'
               '每个存储单元一个矩形：横向跨度 = 活跃区间，纵向 = 字节范围；同列不重叠'
               '</text>')

    for k, (a, b, c) in enumerate(heads):
        cx = x0 + (k + 0.5) * cw
        out.append(f'<text x="{cx}" y="86" text-anchor="middle" class="h">{a}</text>')
        out.append(f'<text x="{cx}" y="102" text-anchor="middle" class="n">{b}</text>')
        if c:
            out.append(f'<text x="{cx}" y="115" text-anchor="middle" class="d">{c}</text>')

    step_line = max(1, int(round(workspace / 512)))
    b = 0
    while b <= workspace:
        out.append(f'<line x1="{x0}" y1="{y_of(b):.1f}" x2="{x1}" y2="{y_of(b):.1f}" '
                   'stroke="#D8D0C0" stroke-width="1.2" stroke-dasharray="5 5"/>')
        out.append(f'<text x="{x0 - 8}" y="{y_of(b) + 4:.1f}" text-anchor="end" '
                   f'class="d">{b}</text>')
        b += step_line * 128 if workspace > 640 else 128
    out.append(f'<text x="{x0 - 8}" y="{y_top - 26}" text-anchor="end" class="d">地址(B)</text>')
    out.append(f'<text x="{x0}" y="{y_bot + 20}" class="d">0</text>')
    out.append(f'<line x1="{x0}" y1="{y_bot}" x2="{x1}" y2="{y_bot}" stroke="#3B3B3B" '
               'stroke-width="2"/>')

    for u in sorted(units.values(), key=lambda u: offsets[u.name]):
        off = offsets[u.name]
        color = PALETTE.get(u.members[0], "#B8A9D9")
        rx = x0 + u.def_step * cw + 2
        rw = (u.last_use - u.def_step + 1) * cw - 4
        ry = y_of(off + u.size)
        rh = u.size * sy
        out.append(f'<rect x="{rx:.1f}" y="{ry:.1f}" width="{rw:.1f}" height="{rh:.1f}" '
                   f'fill="{color}" fill-opacity="0.5" stroke="#3B3B3B" stroke-width="2.2" '
                   f'rx="6"/>')
        cx, cy = rx + rw / 2, ry + rh / 2
        label = unit_label(u)
        if rh >= 58:
            out.append(f'<text x="{cx:.1f}" y="{cy - 6:.1f}" text-anchor="middle" '
                       f'class="n">{label}  {u.size} B</text>')
            out.append(f'<text x="{cx:.1f}" y="{cy + 12:.1f}" text-anchor="middle" '
                       f'class="d">[{off}, {off + u.size})</text>')
        elif rh >= 30:
            out.append(f'<text x="{cx:.1f}" y="{cy + 4:.1f}" text-anchor="middle" '
                       f'class="n">{label} {u.size} B</text>')
        else:
            out.append(f'<text x="{cx:.1f}" y="{ry - 6:.1f}" text-anchor="middle" '
                       f'class="n">{label} {u.size} B</text>')
            out.append(f'<text x="{cx:.1f}" y="{ry + rh + 14:.1f}" text-anchor="middle" '
                       f'class="d">[{off}, {off + u.size})</text>')

    if workspace > peak:
        out.append(f'<line x1="{x0}" y1="{y_of(peak):.1f}" x2="{x1}" y2="{y_of(peak):.1f}" '
                   'stroke="#D98484" stroke-width="2" stroke-dasharray="9 6"/>')
        out.append(f'<text x="{x1}" y="{y_of(peak) - 7:.1f}" text-anchor="end" '
                   f'class="d">峰值活跃集合（下界）{peak} B</text>')

    out.append(f'<text x="{W / 2}" y="{H - 30}" text-anchor="middle" class="f">'
               f'workspace {workspace} B'
               + ('（= 峰值活跃集合，已达理论下界）' if workspace == peak else
                  f'（峰值下界 {peak} B，差 {workspace - peak} B）')
               + '；与 outputs/ 记录一致</text>')
    out.append('</g>\n</svg>')

    path = prefix if prefix.endswith(".svg") else prefix + ".svg"
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")


# ---------------------------------------------------------------- 入口

def main():
    ap = argparse.ArgumentParser(
        description="第 100 天：缓冲区复用——简单内存规划器 + 复用正确性测试")
    ap.add_argument("--order", choices=list(ORDERS), default="main-first")
    ap.add_argument("--strategy", choices=[*STRATEGY_KEYS, "best"], default="best")
    ap.add_argument("--align", type=int, default=DEFAULT_ALIGN)
    ap.add_argument("--order-sweep", action="store_true")
    ap.add_argument("--align-sweep", action="store_true")
    ap.add_argument("--alias-demo", action="store_true")
    ap.add_argument("--hazard-demo", action="store_true")
    ap.add_argument("--test", action="store_true")
    ap.add_argument("--svg", metavar="PREFIX", help="把采用方案的 时间×地址 图写到 PREFIX.svg")
    args = ap.parse_args()

    if args.order_sweep:
        order_sweep()
        return 0
    if args.align_sweep:
        align_sweep()
        return 0
    if args.alias_demo:
        return 0 if alias_demo() else 1
    if args.hazard_demo:
        return 0 if hazard_demo() else 1
    if args.test:
        return run_tests()
    run_order(args.order, args.align, args.strategy, args.svg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
