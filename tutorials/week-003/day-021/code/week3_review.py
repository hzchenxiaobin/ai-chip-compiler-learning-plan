#!/usr/bin/env python3
"""第 21 天演练场（第 3 周复盘）：CFG、SSA、支配、活跃区间，画进同一张图。

用法：
    python3 week3_review.py               # 演示主流程：菱形 CFG 全套分析 + 回边对照 + DCE 账单
    python3 week3_review.py --self-test   # 运行测试，全部通过退出码 0

第 3 周六天各留了一件工具：CFG（Day 15）、拓扑排序（Day 16）、SSA（Day 17）、
支配关系（Day 18）、活跃区间（Day 19）、分析组件（Day 20）。今天把它们串在
同一个含分支的菱形例子上，外加补上 Day 19 明确留下的一块缺口——
带分支的一般 CFG 上，活跃变量要靠反向数据流方程：

    live_out(B) = ∪ ( live_in(S) ∪ φ操作数(S, 来自 B) )    对 B 的每个后继 S
    live_in(B)  = 块内先使用后定义的值 ∪ ( live_out(B) − 块内定义的值 )

主流程八幕：
  [1] 菱形 CFG：基本块、边、前驱 / 后继
  [2] SSA 与 Use-Def：每个值只出生一次；φ 的使用发生在“边”上
  [3] 支配集 / 支配树：Day 18 的迭代求交集复刻 + φ 的边规则（定义支配前驱）
  [4] 活跃性：反向数据流方程（今天的缺口补全）
  [5] 对照一：线性区间在 φ 汇合处过度报告 → 缓冲区共享泡汤（4 槽 vs 3 槽）
  [6] 对照二：回边让线性方法崩溃（使用在定义之前），数据流方程照常收敛
  [7] 压轴题账单：SSA 式 DCE 一行判定死值 %d，但峰值活跃纹丝不动
  [8] 一页复盘速览

手画验收：先在纸上画出菱形（标基本块、SSA 值、支配树、live-in / live-out），
再运行本脚本对答案——[1]～[4] 就是标准答案。
"""

from __future__ import annotations

import argparse

PURE_OPS = {"add", "sub", "mul", "relu", "lt"}   # 无副作用算子（Day 20 同款口径）
ELEM_BYTES = 4                                    # 标量 4 字节（i32 / f32，与 Day 19 口径一致）

# 语句 stmt = (op, result, operands)；operands 是值名（% 开头）或字面量数字
# φ 语句 = ("phi", result, {前驱块名: 操作数})
# 终结符 term = ("jmp", None, [后继]) / ("br", cond, [真后继, 假后继]) / ("ret", [输出值])
#   cond = ("gt"/"lt"/"nz", 值名, 字面量或 None)

# 菱形：Day 18 那个“汇合点读未定义 t”的 bug，今天用 φ 修成合法 SSA
DIAMOND = {
    "entry": "B0",
    "blocks": [
        ("B0", [("input", "%x", [])], ("jmp", None, ["B1"])),
        ("B1", [("add", "%a", ["%x", "1"])], ("br", ("gt", "%a", 2), ["B2", "B3"])),
        ("B2", [("mul", "%t", ["%a", "%a"])], ("jmp", None, ["B4"])),
        ("B3", [("sub", "%b", ["%x", "1"]),
                ("mul", "%d", ["%b", "%b"])], ("jmp", None, ["B4"])),   # %d：死值（从未被使用）
        ("B4", [("phi", "%m", {"B2": "%t", "B3": "%b"}),
                ("add", "%u", ["%m", "%a"])], ("ret", None, ["%u"])),
    ],
}

# 反例：B3 使用 %t——%t 定义在 B2，B2 不支配 B3（走 else 路时 %t 还没出生）
BAD_DIAMOND = {
    "entry": "B0",
    "blocks": [
        ("B0", [("input", "%x", [])], ("jmp", None, ["B1"])),
        ("B1", [("add", "%a", ["%x", "1"])], ("br", ("gt", "%a", 2), ["B2", "B3"])),
        ("B2", [("mul", "%t", ["%a", "%a"])], ("jmp", None, ["B4"])),
        ("B3", [("sub", "%b", ["%x", "1"]),
                ("add", "%q", ["%t", "1"])], ("jmp", None, ["B4"])),
        ("B4", [("phi", "%m", {"B2": "%t", "B3": "%b"}),
                ("add", "%u", ["%m", "%a"])], ("ret", None, ["%u"])),
    ],
}

# 回边实验：累加循环（x=10, n=3 → r = 0+1+2+10 = 13）
LOOP = {
    "entry": "B0",
    "blocks": [
        ("B0", [("input", "%x", []),
                ("const", "%c0", ["0"]),
                ("const", "%c1", ["1"]),
                ("const", "%n", ["3"])], ("jmp", None, ["B1"])),
        ("B1", [("phi", "%i", {"B0": "%c0", "B2": "%i2"}),
                ("phi", "%acc", {"B0": "%c0", "B2": "%s"}),
                ("lt", "%cont", ["%i", "%n"])], ("br", ("nz", "%cont", None), ["B2", "B3"])),
        ("B2", [("add", "%s", ["%acc", "%i"]),
                ("add", "%i2", ["%i", "%c1"])], ("jmp", None, ["B1"])),   # 回边 B2 → B1
        ("B3", [("add", "%r", ["%acc", "%x"])], ("ret", None, ["%r"])),
    ],
}


class CfgError(Exception):
    """CFG 不合法，或违反本演练场的契约。"""


def is_value(x):
    return isinstance(x, str) and x.startswith("%")


def cond_values(cond):
    return [cond[1]] if cond is not None else []


class Cfg:
    """块表表示的最小 CFG（Day 15 的四件套瘦身版）。"""

    def __init__(self, spec):
        self.entry = spec["entry"]
        self.order = [name for name, _, _ in spec["blocks"]]
        self.blocks = {name: {"stmts": [tuple(s) for s in stmts], "term": tuple(term)}
                       for name, stmts, term in spec["blocks"]}
        if self.entry not in self.blocks:
            raise CfgError(f"入口 {self.entry} 不存在")
        self._preds = {b: [] for b in self.order}
        for name in self.order:
            for s in self.succs(name):
                if s not in self.blocks:
                    raise CfgError(f"{name} 的后继 {s} 不存在")
                self._preds[s].append(name)
        for name in self.order:
            phi_keys = set()
            for op, _, args in self.stmts(name):
                if op == "phi":
                    phi_keys |= set(args.keys())
            if phi_keys and phi_keys != set(self.preds(name)):
                raise CfgError(
                    f"{name} 的 φ 来源 {sorted(phi_keys)} 与真实前驱 {sorted(self.preds(name))} 不一致")

    def succs(self, name):
        kind, _, ss = self.blocks[name]["term"]
        return list(ss) if kind in ("jmp", "br") else []

    def preds(self, name):
        return list(self._preds[name])

    def stmts(self, name):
        return self.blocks[name]["stmts"]

    def term(self, name):
        return self.blocks[name]["term"]

    def spec(self):
        return {"entry": self.entry,
                "blocks": [(n, list(self.blocks[n]["stmts"]), tuple(self.blocks[n]["term"]))
                           for n in self.order]}


# ---------- 打印 ----------


def fmt_stmt(stmt):
    op, res, args = stmt
    if op == "phi":
        inner = ", ".join(f"{v} : {p}" for p, v in args.items())
        return f"{res} = φ({inner})"
    return f"{res} = {op}({', '.join(str(a) for a in args)})"


def fmt_cond(cond):
    op, v, lit = cond
    if op == "gt":
        return f"{v} > {lit}"
    if op == "lt":
        return f"{v} < {lit}"
    return f"{v} ≠ 0"


def fmt_term(term):
    kind, cond, ss = term
    if kind == "jmp":
        return f"jmp {ss[0]}"
    if kind == "br":
        return f"br {fmt_cond(cond)} → {ss[0]} / {ss[1]}"
    return "ret " + ", ".join(ss)


def print_cfg(cfg):
    for name in cfg.order:
        print(f"{name}:")
        for stmt in cfg.stmts(name):
            print(f"  {fmt_stmt(stmt)}")
        print(f"  {fmt_term(cfg.term(name))}")
    print("前驱 / 后继：")
    for name in cfg.order:
        ps = "、".join(cfg.preds(name)) or "（入口）"
        ss = "、".join(cfg.succs(name)) or "（返回）"
        print(f"  {name}  前驱 {ps}   后继 {ss}")


def fmt_set(names):
    if not names:
        return "（无）"
    return "、".join(sorted(names))


# ---------- SSA 与 Use-Def（Day 17 收拢，φ 的使用记在边上）----------


def use_def(cfg):
    """每个值：定义点 + 使用点列表。

    使用点三种：
      ("stmt", 块, 语句序号)   —— 普通语句里的操作数；
      ("term", 块)             —— 终结符里的条件 / 返回值；
      ("edge", 前驱, 汇合块)   —— φ 的操作数：使用发生在“前驱 → 汇合块”的边上。
    φ 的使用记在边上（而不是 φ 所在块内），是今天全篇最重要的一个细节。
    """
    info = {}
    for name in cfg.order:
        for i, (op, res, _) in enumerate(cfg.stmts(name)):
            if res is None:
                continue
            if res in info:
                raise CfgError(f"{res} 定义了两次（违反 SSA）")
            info[res] = {"def": (name, i, op), "uses": []}
    for name in cfg.order:
        for i, (op, _, args) in enumerate(cfg.stmts(name)):
            if op == "phi":
                for p, v in args.items():
                    if is_value(v):
                        info[v]["uses"].append(("edge", p, name))
            else:
                for v in args:
                    if is_value(v):
                        info[v]["uses"].append(("stmt", name, i))
        kind, cond, ss = cfg.term(name)
        for v in cond_values(cond):
            info[v]["uses"].append(("term", name))
        if kind == "ret":
            for v in ss:
                info[v]["uses"].append(("term", name))
    for v, d in info.items():
        for use in d["uses"]:
            if use[0] == "edge":
                if use[1] not in cfg.preds(use[2]):
                    raise CfgError(f"{v} 的 φ 使用边 {use[1]}→{use[2]} 不是真实前驱边")
    return info


def fmt_use(use):
    kind = use[0]
    if kind == "edge":
        return f"边 {use[1]}→{use[2]}（φ）"
    if kind == "term":
        return f"{use[1]}（终结符）"
    return f"{use[1]}（语句 {use[2] + 1}）"


def fmt_use_list(uses):
    """同一使用点读多次（如 mul(%a, %a)）合并显示为 ×N。"""
    seen, order = {}, []
    for u in uses:
        if u not in seen:
            seen[u] = 0
            order.append(u)
        seen[u] += 1
    return "、".join(fmt_use(u) + (f" ×{seen[u]}" if seen[u] > 1 else "") for u in order)


# ---------- 支配（Day 18 收拢：迭代求交集 + idom + 支配树）----------


def dominators(cfg):
    """迭代求交集：dom(入口)={入口}，其余初始化为全集，
    反复 dom(b) = {b} ∪ ∩ dom(p)（对 b 的所有前驱 p）直到不动点。"""
    all_blocks = set(cfg.order)
    dom = {cfg.entry: {cfg.entry}}
    for b in cfg.order:
        if b != cfg.entry:
            dom[b] = set(all_blocks)
    rounds = 0
    changed = True
    while changed:
        changed = False
        rounds += 1
        for b in cfg.order:
            if b == cfg.entry:
                continue
            new = set(all_blocks)
            for p in cfg.preds(b):
                new &= dom[p]
            new.add(b)
            if new != dom[b]:
                dom[b] = new
                changed = True
    idom = {}
    for b in cfg.order:
        if b == cfg.entry:
            continue
        strict = dom[b] - {b}
        # 严格支配者是一条链：离 b 最近的就是支配集最大的那个
        idom[b] = max(strict, key=lambda d: len(dom[d]))
    return dom, idom, rounds


def dom_tree_lines(cfg, idom):
    children = {b: [] for b in cfg.order}
    for b, d in idom.items():
        children[d].append(b)
    for b in children:
        children[b].sort()
    lines = []

    def rec(b, depth):
        lines.append(("    " * depth) + ("" if depth == 0 else "└── ") + b)
        for c in children[b]:
            rec(c, depth + 1)

    rec(cfg.entry, 0)
    return lines


def check_domination(cfg, dom, ud):
    """Day 18 的规则 + φ 的边规则：
    普通使用：定义块必须支配使用块；
    φ 操作数（边 P→M）：定义块必须支配前驱 P——值要在 P 执行完时还活着，被边带走。
    返回 (检查次数, 问题列表)。"""
    problems = []
    checks = 0
    for v, d in ud.items():
        defb = d["def"][0]
        for use in d["uses"]:
            if use[0] == "edge":
                ok = defb in dom[use[1]]
            else:
                ok = defb in dom[use[1]]
            checks += 1
            if not ok:
                problems.append((v, defb, use))
    return checks, problems


# ---------- 活跃性（今天补的缺口：反向数据流方程）----------


def block_defs(cfg, name):
    return {res for _, res, _ in cfg.stmts(name) if res is not None}


def phi_args(cfg, name):
    """{前驱: 操作数集合}——φ 的使用发生在前驱块的出口（边上）。"""
    out = {}
    for op, _, args in cfg.stmts(name):
        if op == "phi":
            for p, v in args.items():
                if is_value(v):
                    out.setdefault(p, set()).add(v)
    return out


def upward_uses(cfg, name):
    """块内“先使用、后定义”的值（SSA 下：使用点早于本块定义点，或根本不在本块定义）。
    φ 的操作数不算——它们的使用在边上。"""
    b = cfg.blocks[name]
    defs = {}
    for i, (_, res, _) in enumerate(b["stmts"]):
        if res is not None:
            defs[res] = i
    used = set()

    def note(v, pos):
        if is_value(v) and (v not in defs or defs[v] > pos):
            used.add(v)

    for i, (op, _, args) in enumerate(b["stmts"]):
        if op == "phi":
            continue
        for v in args:
            note(v, i)
    kind, cond, ss = b["term"]
    for v in cond_values(cond):
        note(v, len(b["stmts"]))
    if kind == "ret":
        for v in ss:
            note(v, len(b["stmts"]))
    return used


def liveness(cfg, ud):
    """反向数据流方程，迭代到不动点：
    live_out(B) = ∪ ( live_in(S) ∪ φ操作数(S, 来自 B) )   对 B 的每个后继 S
    live_in(B)  = 先使用后定义的值 ∪ ( live_out(B) − 块内定义 )
    返回 (live_in, live_out, 收敛轮数)。"""
    live_in = {b: set() for b in cfg.order}
    live_out = {b: set() for b in cfg.order}
    rounds = 0
    changed = True
    while changed:
        changed = False
        rounds += 1
        for b in reversed(cfg.order):
            out = set()
            for s in cfg.succs(b):
                out |= live_in[s]
                out |= phi_args(cfg, s).get(b, set())
            inn = upward_uses(cfg, b) | (out - block_defs(cfg, b))
            if out != live_out[b] or inn != live_in[b]:
                live_out[b], live_in[b] = out, inn
                changed = True
    return live_in, live_out, rounds


def live_shapes(cfg, ud, live_in, live_out):
    """每个值的活跃形态（给手画对答案用）。"""
    shapes = {}
    for v, d in ud.items():
        at = []
        for b in cfg.order:
            marks = []
            if v in live_in[b]:
                marks.append("入")
            if v in live_out[b]:
                marks.append("出")
            if marks:
                at.append(f"{b}({'/'.join(marks)})")
        if at:
            shapes[v] = "、".join(at)
        elif not d["uses"]:
            shapes[v] = "从不活跃（死值）"
        else:
            blocks = sorted({d["def"][0]} | {u[1] for u in d["uses"]})
            shapes[v] = "只活在 " + "、".join(blocks) + " 块内"
    return shapes


# ---------- 线性方法（Day 19）硬套在块序上：暴露两处失效 ----------


def linear_view(cfg, order):
    """Day 19 的线性方法套在给定块序上：语句全局编号，区间 = [定义, 最后使用]。
    φ 的使用按最天真的处理记在 φ 语句的位置上——这正是要暴露的问题。
    返回 (intervals, pos_block, 总语句数)；intervals[v] = (kind, def位置, 最后使用位置, 使用列表, 末次使用是不是 φ)。"""
    pos = 0
    block_end = {}
    defb = {}
    uses = {}
    edge_uses = set()
    pos_block = []
    for b in order:
        stmts = cfg.stmts(b)
        for i, (op, res, args) in enumerate(stmts):
            pos += 1
            pos_block.append(b)
            if res is not None:
                defb[res] = pos
            if op == "phi":
                for v in args.values():
                    if is_value(v):
                        uses.setdefault(v, []).append(pos)
                        edge_uses.add((v, pos))
            else:
                for v in args:
                    if is_value(v):
                        uses.setdefault(v, []).append(pos)
        block_end[b] = pos
        kind, cond, ss = cfg.term(b)
        for v in cond_values(cond) + (list(ss) if kind == "ret" else []):
            if is_value(v):
                uses.setdefault(v, []).append(block_end[b])
    n = pos
    intervals = {}
    for v, d in defb.items():
        us = uses.get(v, [])
        if not us:
            intervals[v] = ("dead", d, None, us, False)
        else:
            last = max(us)
            if last < d:
                intervals[v] = ("broken", d, last, us, False)
            else:
                intervals[v] = ("ok", d, last, us, (v, last) in edge_uses)
    return intervals, pos_block, n


def linear_slots(intervals):
    """Day 19 的保守分配：区间有重叠就不许共享（上一任最后使用 < 下一任定义）。"""
    alive = [(v, s, e) for v, (kind, s, e, _, _) in intervals.items() if kind == "ok"]
    alive.sort(key=lambda x: (x[1], x[2], x[0]))
    slot_end = []
    assign = {}
    for v, s, e in alive:
        placed = False
        for sid in range(len(slot_end)):
            if slot_end[sid] < s:
                slot_end[sid] = e
                assign[v] = sid
                placed = True
                break
        if not placed:
            slot_end.append(e)
            assign[v] = len(slot_end) - 1
    return assign


def cfg_slots(cfg, live_in, live_out):
    """CFG 真值的保守分配：两个值只要在某个程序点共存过就不许共享。
    程序点 = 每块的入口 / 出口活跃集 + 块内逐语句回推的活跃集（读入与写出共存算冲突）。"""
    conflict = set()

    def clique(s):
        s = sorted(s)
        for i in range(len(s)):
            for j in range(i + 1, len(s)):
                conflict.add((s[i], s[j]))

    alive_blocks = {v: set() for v in live_all_values(cfg)}
    for b in cfg.order:
        for s in (live_in[b], live_out[b]):
            clique(s)
            for v in s:
                alive_blocks[v].add(b)
        live = set(live_out[b])
        for i in range(len(cfg.stmts(b)) - 1, -1, -1):
            op, res, args = cfg.stmts(b)[i]
            if op == "phi":
                live = live - {res}
            else:
                live = (live - {res}) | {v for v in args if is_value(v)}
            for v in live:
                alive_blocks[v].add(b)
            clique(live | ({res} if res else set()))
    order_vals = [v for v in alive_blocks if alive_blocks[v]]
    order_vals.sort(key=lambda v: (min(alive_blocks[v]), v))
    slot_vals = []
    assign = {}
    for v in order_vals:
        for sid in range(len(slot_vals)):
            if all((min(v, w), max(v, w)) not in conflict for w in slot_vals[sid]):
                slot_vals[sid].append(v)
                assign[v] = sid
                break
        else:
            slot_vals.append([v])
            assign[v] = len(slot_vals) - 1
    return assign


def live_all_values(cfg):
    vals = set()
    for b in cfg.order:
        for _, res, _ in cfg.stmts(b):
            if res is not None:
                vals.add(res)
    return vals


# ---------- 解释器（Day 15 复刻：沿控制流执行 + 流量记账）----------


def eval_op(op, vals):
    if op == "add":
        return vals[0] + vals[1]
    if op == "sub":
        return vals[0] - vals[1]
    if op == "mul":
        return vals[0] * vals[1]
    if op == "lt":
        return 1 if vals[0] < vals[1] else 0
    if op == "relu":
        return max(vals[0], 0)
    raise CfgError(f"不认识的算子 {op}")


def run(cfg, inputs):
    """沿控制流执行；φ 按来路在前驱出口取值；统计流量。
    口径：值操作数每次读取 4B，每个结果写出 4B（input / const 也算一次写出）；
    立即数不走内存，不计流量。返回 (返回值, 读字节, 写字节, 路径)。"""
    env = {}
    reads = writes = 0
    path = []
    cur, pred = cfg.entry, None
    fuel = 10000
    while True:
        fuel -= 1
        if fuel <= 0:
            raise CfgError("燃料耗尽（死循环？）")
        path.append(cur)
        b = cfg.blocks[cur]
        phi_new = {}
        for op, res, args in b["stmts"]:
            if op == "phi":
                if pred is None:
                    raise CfgError(f"{cur} 是入口块却带 φ")
                phi_new[res] = env[args[pred]]
                reads += ELEM_BYTES
        for res, val in phi_new.items():
            env[res] = val
        for op, res, args in b["stmts"]:
            if op == "phi":
                continue
            if op == "input":
                if res not in inputs:
                    raise CfgError(f"输入 {res} 未绑定")
                env[res] = inputs[res]
            elif op == "const":
                env[res] = int(args[0])
            else:
                vals = []
                for a in args:
                    if is_value(a):
                        vals.append(env[a])
                        reads += ELEM_BYTES
                    else:
                        vals.append(int(a))
                env[res] = eval_op(op, vals)
            writes += ELEM_BYTES
        kind, cond, ss = b["term"]
        if kind == "jmp":
            pred, cur = cur, ss[0]
        elif kind == "br":
            v = env[cond[1]]
            reads += ELEM_BYTES
            op, _, lit = cond
            if op == "gt":
                taken = v > int(lit)
            elif op == "lt":
                taken = v < int(lit)
            else:
                taken = v != 0
            pred, cur = cur, ss[0] if taken else ss[1]
        else:
            outs = [env[v] for v in ss]
            reads += ELEM_BYTES * len(ss)
            return outs, reads, writes, path


# ---------- SSA 式 DCE（Day 25 预演，今天只做“一行判定”展示）----------


def dead_values(ud):
    """使用数为 0 且无副作用的语句结果。input 不删（Day 20 同款口径）。"""
    out = []
    for v, d in ud.items():
        name, _, op = d["def"]
        if not d["uses"] and (op in PURE_OPS or op == "const"):
            out.append((v, name, op))
    return sorted(out)


def remove_values(cfg, names):
    spec = cfg.spec()
    for blk in spec["blocks"]:
        blk[1][:] = [s for s in blk[1] if s[1] not in names]
    return Cfg(spec)


def peak_live(live_in, live_out):
    return max(max((len(s) for s in live_in.values()), default=0),
               max((len(s) for s in live_out.values()), default=0))


# ---------- 演示 ----------


def demo():
    cfg = Cfg(DIAMOND)
    ud = use_def(cfg)

    print("== [1] 菱形 CFG：第 3 周六天家底，一张图验收 ==")
    print_cfg(cfg)
    print("看四样东西：5 个基本块、4 条普通边 + 1 个分支（B1 有两个后继）、"
          "B4 的 φ 按来路选版本、B3 的 %d 谁也不理它（Day 20 的死值）。")

    print("\n== [2] SSA 与 Use-Def：每个值只出生一次 ==")
    for v in sorted(ud, key=lambda n: ud[n]["def"]):
        d = ud[v]
        where, idx, op = d["def"]
        uses = fmt_use_list(d["uses"]) if d["uses"] else "（无使用 —— 死值）"
        print(f"  {v:<5} 定义于 {where}（{op}）   使用于 {uses}")
    print("φ 的使用记在“边”上：%t 的使用是边 B2→B4，不是 B4 块内——这个细节下面反复用。")

    print("\n== [3] 支配关系：Day 18 的迭代求交集复刻 ==")
    dom, idom, rounds = dominators(cfg)
    for b in cfg.order:
        print(f"  Dom({b}) = {{ {', '.join(sorted(dom[b]))} }}   ({rounds} 轮迭代收敛)")
    print("  直接支配者 idom：" + "、".join(f"{b} ← {idom[b]}" for b in cfg.order if b != cfg.entry))
    print("  支配树：")
    for line in dom_tree_lines(cfg, idom):
        print("    " + line)
    checks, problems = check_domination(cfg, dom, ud)
    print(f"  “定义支配使用”检查：{checks} 处使用全部通过" if not problems
          else f"  “定义支配使用”检查：{len(problems)} 处不通过")
    print("  φ 的边规则：%t 定义在 B2、被边 B2→B4 带走 —— 要求 B2 支配 B2（前驱自己）✓；"
          "普通使用仍要求定义块支配使用块（Day 18 原规则）。")

    print("\n== [4] 活跃性：反向数据流方程（Day 19 留下的缺口，今天补上） ==")
    print("  live_out(B) = ∪ ( live_in(S) ∪ φ操作数(S, 来自 B) )   对 B 的每个后继 S")
    print("  live_in(B)  = 块内先使用后定义的值 ∪ ( live_out(B) − 块内定义 )")
    live_in, live_out, lrounds = liveness(cfg, ud)
    for b in cfg.order:
        print(f"  {b}   live_in  = {fmt_set(live_in[b]):<14} live_out = {fmt_set(live_out[b])}")
    print(f"  （反向迭代 {lrounds} 轮收敛；φ 操作数落在前驱出口：live_out(B2) 里的 %t、live_out(B3) 里的 %b）")
    print("  每个值的活跃形态：")
    shapes = live_shapes(cfg, ud, live_in, live_out)
    for v in sorted(shapes, key=lambda n: ud[n]["def"]):
        print(f"    {v:<5} {shapes[v]}")

    print("\n== [5] 对照一：线性区间在 φ 汇合处过度报告 ==")
    order = list(cfg.order)
    intervals, pos_block, n = linear_view(cfg, order)
    shapes = live_shapes(cfg, ud, live_in, live_out)
    print(f"  把块按 {'→'.join(order)} 拉直（Day 19 的做法），语句全局编号 S1–S{n}：")
    for v in sorted(intervals, key=lambda v2: intervals[v2][1]):
        kind, d, last, _, last_is_edge = intervals[v]
        if kind == "dead":
            print(f"    {v:<5} 死值（无使用）")
            continue
        covered = sorted(set(pos_block[d - 1:last]))
        if kind == "broken":
            print(f"    {v:<5} 定义 S{d}，使用 S{last} → 使用在定义之前（回边世界的警报）")
            continue
        boundary = [b for b in cfg.order if v in live_in[b] or v in live_out[b]]
        truth = boundary if boundary else sorted({ud[v]["def"][0]} | {u[1] for u in ud[v]["uses"]})
        extra = sorted(set(covered) - set(truth))
        if extra:
            why = "φ 的使用被记在 φ 所在块，区间末端被撑大" if last_is_edge else "两条路各自需要，区间只能取并集"
            print(f"    {v:<5} 定义 S{d}  最后使用 S{last}  区间 [S{d}, S{last}] 覆盖 {'、'.join(covered)}"
                  f"  ← 多算了 {'、'.join(extra)}（{why}；真值：{shapes[v]}）")
        else:
            print(f"    {v:<5} 定义 S{d}  最后使用 S{last}  区间 [S{d}, S{last}] 覆盖 {'、'.join(covered)}（与真值一致）")
    lin_assign = linear_slots(intervals)
    n_lin = 1 + max(lin_assign.values()) if lin_assign else 0
    print(f"  线性区间的缓冲区分配（Day 19 规则：区间重叠不许共享）：{n_lin} 个槽")
    print("    " + "   ".join(
        f"槽{sid}={fmt_set([v for v, s in sorted(lin_assign.items()) if s == sid])}"
        for sid in range(n_lin)))
    cfg_assign = cfg_slots(cfg, live_in, live_out)
    n_cfg = 1 + max(cfg_assign.values()) if cfg_assign else 0
    print(f"  CFG 活跃集的缓冲区分配（同一保守规则，用真值活跃集）：{n_cfg} 个槽")
    print("    " + "   ".join(
        f"槽{sid}={fmt_set([v for v, s in sorted(cfg_assign.items()) if s == sid])}"
        for sid in range(n_cfg)))
    print("  结论：线性区间让 %t 和 %b 假重叠（真值：一个只在 B2 出口、一个只在 B3 出口——互斥的两条路），"
          "又让 %t 和 %x 脱不开身（真值：%x 在 B2 根本不活）；CFG 活跃集把两条都看得清——"
          f"3 个槽干完 {n_lin} 个槽的活。标量只差 {ELEM_BYTES}B；换成真 Tensor，这就是 Day 99–100 内存规划的整个游戏。")

    print("\n== [6] 对照二：回边让线性方法彻底崩溃 ==")
    lcfg = Cfg(LOOP)
    print_cfg(lcfg)
    lud = use_def(lcfg)
    lorder = list(lcfg.order)
    lintervals, lpos_block, ln = linear_view(lcfg, lorder)
    print(f"  线性方法硬套块序 {'→'.join(lorder)}（S1–S{ln}）：")
    for v in sorted(lintervals, key=lambda v2: lintervals[v2][1]):
        kind, d, last, _, _ = lintervals[v]
        if kind == "dead":
            print(f"    {v:<6} 死值（无使用）")
        elif kind == "broken":
            print(f"    {v:<6} 定义于 S{d}，使用于 S{last} → 使用在定义之前——合法程序被判死刑")
        elif lud[v]["def"][2] == "phi":
            print(f"    {v:<6} 区间 [S{d}, S{last}] 看似正常，但它是 φ：每圈都是新值，区间表达不了“活一整圈”")
        else:
            print(f"    {v:<6} 区间 [S{d}, S{last}]（%x 活过整个循环，这个倒算对了）" if v == "%x"
                  else f"    {v:<6} 区间 [S{d}, S{last}]")
    llive_in, llive_out, llrounds = liveness(lcfg, lud)
    print(f"  数据流方程（反向迭代 {llrounds} 轮收敛）：")
    for b in lcfg.order:
        print(f"    {b}   live_in  = {fmt_set(llive_in[b]):<22} live_out = {fmt_set(llive_out[b])}")
    print("  读三行：回边上的 %s、%i2 活在 B2 出口（被 B1 的 φ 在边上吃掉）；"
          "%x、%c1 活过整个循环（B3 / B2 要用）；%c0 只活在 B0 出口——第一圈之后 φ 吃的是 B2 来的新值。")
    outs, lr, lw, lpath = run(lcfg, {"%x": 10})
    print(f"  解释器验证：x=10、n=3 → 返回 {outs[0]}；路径 {' → '.join(lpath)}"
          f"（B2 走了 {lpath.count('B2')} 次 = 循环 3 圈）")

    print("\n== [7] 压轴题账单：SSA 让优化容易，但不等于高性能 ==")
    dead = dead_values(ud)
    print("  SSA 式死代码判定：使用数为 0 的纯算子 → " +
          ("、".join(f"{v}（{blk} 的 {op}）" for v, blk, op in dead) or "（无）"))
    print("  对比：名字可重复赋值的世界里“名字被用过”≠“这次赋值被用过”——"
          "得先做到达定义分析才敢删（Day 17 的 S1–S7 里 a 被赋值 3 次就是例子）。")
    names = {v for v, _, _ in dead}
    cfg2 = remove_values(cfg, names)
    ud2 = use_def(cfg2)
    li2, lo2, _ = liveness(cfg2, ud2)
    naive_before = ELEM_BYTES * len(ud)
    naive_after = ELEM_BYTES * len(ud2)
    peak_before = peak_live(live_in, live_out)
    peak_after = peak_live(li2, lo2)
    print(f"  删除 {fmt_set(names)} 前后的账单（标量 {ELEM_BYTES}B；流量按执行路径计）：")
    print(f"    {'':<18}{'删前':>8}{'删后':>9}   说明")
    print(f"    {'朴素分配（每值一块）':<18}{naive_before:>7}B{naive_after:>8}B   死值也要占一块 → 省它自己那块")
    print(f"    {'峰值活跃（最多同时活）':<18}{peak_before:>7} 个{peak_after:>8} 个   死值从来不在活跃集里：峰值纹丝不动")
    flows = {}
    for label, xv in (("then", 4), ("else", 1)):
        o1, r1, w1, _ = run(cfg, {"%x": xv})
        o2, r2, w2, _ = run(cfg2, {"%x": xv})
        flows[label] = (r1 + w1, r2 + w2)
        print(f"    {f'{label} 路（x={xv}）':<18}{r1 + w1:>7}B{r2 + w2:>8}B   返回值 {o1[0]} → {o2[0]}（语义不变）")
    print(f"  then 路省 {flows['then'][0] - flows['then'][1]}B（%d 在 else 路，then 路根本不执行它）；"
          f"else 路省 {flows['else'][0] - flows['else'][1]}B（死代码自己那次读 8B + 写 4B）")
    print("  结论：SSA 把“找出死代码”变成查一次使用数——这是“容易”；"
          "但删掉它省的是边角料，峰值活跃没动、大头流量没动——性能的大头在访存结构和循环结构"
          "（Day 50+ 的融合、Day 94+ 的 Tiling），都不在 SSA 的职责清单上。")

    print("\n== [8] 一页复盘速览（完整版见教程第 8 节） ==")
    print("  本周目标：给计算图配上控制流、SSA 和程序分析")
    print("  最重要的一个技术问题：线性世界天经地义的“区间”，到分支 / 循环世界为什么失效")
    print("  根因：区间假设存在全序；CFG 只有偏序——φ 的使用发生在边上、回边让使用先于定义")
    print("  验证：反向数据流方程 + 两个反例（%t 过度报告、回边判死刑）")
    print("  压轴题：SSA 让优化更容易（使用数即事实），但不直接等于高性能（见上面账单）")
    return 0


# ---------- 自测 ----------


def self_test():
    results = []

    def check(name, cond):
        results.append((name, bool(cond)))
        print(f"  {'✓' if cond else '✗'} {name}")

    print("== 自测：第 3 周复盘（CFG + SSA + 支配 + 活跃 + 回边 + DCE 账单） ==")

    cfg = Cfg(DIAMOND)
    ud = use_def(cfg)
    dom, idom, _ = dominators(cfg)
    live_in, live_out, lrounds = liveness(cfg, ud)

    check("菱形：B1 的后继是 B2、B3（一个分支两个出口）", cfg.succs("B1") == ["B2", "B3"])
    check("菱形：B4 的前驱是 B2、B3", set(cfg.preds("B4")) == {"B2", "B3"})
    check("Use-Def：%a 的使用覆盖 3 个位置（B1 条件、B2、B4；mul 读它两次）",
          len(ud["%a"]["uses"]) == 4 and len(set(ud["%a"]["uses"])) == 3)
    check("Use-Def：%d 使用数为 0（死值）", not ud["%d"]["uses"])
    check("φ 的使用记在边上：%t 的使用是边 B2→B4", ud["%t"]["uses"] == [("edge", "B2", "B4")])
    check("支配集：Dom(B4) = {B0, B1, B4}", dom["B4"] == {"B0", "B1", "B4"})
    check("idom：B2、B3、B4 的直接支配者都是 B1",
          all(idom[b] == "B1" for b in ("B2", "B3", "B4")))
    _, problems = check_domination(cfg, dom, ud)
    check("“定义支配使用”检查：菱形全部使用通过（含 φ 边规则）", not problems)

    bad = Cfg(BAD_DIAMOND)
    bad_ud = use_def(bad)
    bad_dom, _, _ = dominators(bad)
    _, bad_problems = check_domination(bad, bad_dom, bad_ud)
    check("反例：B3 使用 %t（定义在 B2）被支配检查拒绝", any(v == "%t" for v, _, _ in bad_problems))

    check("活跃：live_out(B1) = {%x, %a}", live_out["B1"] == {"%x", "%a"})
    check("活跃：live_in(B4) = {%a}（φ 操作数不进块入口）", live_in["B4"] == {"%a"})
    check("活跃：live_out(B2) = {%a, %t}（φ 边使用落在前驱出口）", live_out["B2"] == {"%a", "%t"})
    check("活跃：死值 %d 不出现在任何活跃集里",
          all("%d" not in live_in[b] and "%d" not in live_out[b] for b in cfg.order))
    check("活跃：菱形反向迭代 2~3 轮收敛", 2 <= lrounds <= 3)

    intervals, pos_block, _ = linear_view(cfg, list(cfg.order))
    covered_t = set(pos_block[intervals["%t"][1] - 1:intervals["%t"][2]])
    check("线性过度报告：%t 的区间覆盖 B3，但 %t 在 B3 根本不活",
          "B3" in covered_t and "%t" not in live_in["B3"] and "%t" not in live_out["B3"])
    lin_assign = linear_slots(intervals)
    cfg_assign = cfg_slots(cfg, live_in, live_out)
    n_lin = 1 + max(lin_assign.values())
    n_cfg = 1 + max(cfg_assign.values())
    check("缓冲区：线性区间要 4 槽，CFG 活跃只要 3 槽", n_lin == 4 and n_cfg == 3)
    check("缓冲区：%t 在 CFG 方案里顶替 %x 的槽（%x 在 B2 不活），线性方案却因假重叠拆开它们",
          cfg_assign["%t"] == cfg_assign["%x"] and lin_assign["%t"] != lin_assign["%x"])

    lcfg = Cfg(LOOP)
    lud = use_def(lcfg)
    lintervals, _, _ = linear_view(lcfg, list(lcfg.order))
    check("回边：线性方法把 %s、%i2 判成“使用在定义之前”",
          lintervals["%s"][0] == "broken" and lintervals["%i2"][0] == "broken")
    llive_in, llive_out, _ = liveness(lcfg, lud)
    check("回边：%s 活在 B2 出口（绕回 B1 的 φ）", "%s" in llive_out["B2"])
    check("回边：%x、%c1 活过整个循环（live_in(B1)）",
          {"%x", "%c1"} <= llive_in["B1"])
    check("回边：%c0 只活在 B0 出口（第一圈之后 φ 吃 B2 的新值）",
          "%c0" in llive_out["B0"] and all("%c0" not in llive_in[b] for b in lcfg.order if b != "B0"))

    outs, _, _, _ = run(lcfg, {"%x": 10})
    check("解释器：循环 x=10、n=3 → 返回 13（0+1+2+10）", outs == [13])
    o4, _, _, _ = run(cfg, {"%x": 4})
    o1, _, _, _ = run(cfg, {"%x": 1})
    check("解释器：菱形 x=4 → 30；x=1 → 2（φ 按来路选对版本）", o4 == [30] and o1 == [2])

    dead = dead_values(ud)
    check("DCE：死值只有 %d 一条", [v for v, _, _ in dead] == ["%d"])
    cfg2 = remove_values(cfg, {"%d"})
    ud2 = use_def(cfg2)
    li2, lo2, _ = liveness(cfg2, ud2)
    o4b, _, _, _ = run(cfg2, {"%x": 4})
    o1b, r1b, w1b, _ = run(cfg2, {"%x": 1})
    _, r1, w1, _ = run(cfg, {"%x": 1})
    check("DCE：删后两路结果不变（语义不变）", o4b == [30] and o1b == [2])
    check("DCE：else 路流量省 12B（死代码自己那次读 8B + 写 4B）", (r1 + w1) - (r1b + w1b) == 12)
    check("DCE：峰值活跃删前删后都是 2 个（死值从来不在活跃集里）",
          peak_live(live_in, live_out) == peak_live(li2, lo2) == 2)

    passed = sum(1 for _, ok in results if ok)
    print(f"\n{passed}/{len(results)} 项通过")
    return 0 if passed == len(results) else 1


def main():
    ap = argparse.ArgumentParser(description="第 3 周复盘演练场：CFG + SSA + 支配 + 活跃区间")
    ap.add_argument("--self-test", action="store_true", help="运行测试而不是演示")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    return demo()


if __name__ == "__main__":
    raise SystemExit(main())
