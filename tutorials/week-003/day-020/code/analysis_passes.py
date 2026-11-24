#!/usr/bin/env python3
"""第 20 天演练场：分析 Pass 与变换 Pass 的分离，以及分析结果失效。

用法：
    python3 analysis_passes.py              # 演示主流程（含失效与事故演示）
    python3 analysis_passes.py --self-test  # 运行测试，全部通过退出码 0

Day 19 在“演练场脚本”里顺手算的活跃区间，今天升级成两个正式的分析组件：
  1. UnusedAnalysis   未使用分析   —— 哪些值从未被使用（死值），Day 25 的 DCE 要用；
  2. LastUseAnalysis  最后使用分析 —— 每个值最后一次被读的位置，Day 99–100 内存规划要用。
再配一个 AnalysisManager：用“图版本号 epoch”管理缓存——
图一变（删语句、换边），旧结果作废，下次查询自动重算。

设计契约（对应 MLIR 的 AnalysisManager / Pass 分离）：
  * 分析 Pass 只读图、只报告事实，不改图（管理器会当场检查）；
  * 变换 Pass 改图，一律通过 Graph 的修改方法，每次修改 epoch + 1；
  * 分析结果只在“诞生时的图版本”下有效，改图后必须重新查询；
  * “能不能删、要不要删”这类决策写在变换 Pass 里，分析只供事实。
"""

from __future__ import annotations

import argparse

PURE_OPS = {"matmul", "add", "relu", "mul"}  # 无副作用的算子（Day 19 同款口径）

# (op, 结果值, 使用的值, shape)；None 表示 output 语句不定义值（Day 19 同款）
BASE_GRAPH = [
    ("input",     "%a",   [],           (2, 3)),
    ("input",     "%b",   [],           (3, 2)),
    ("input",     "%w",   [],           (2, 2)),
    ("const 0.5", "%s",   [],           (2, 2)),
    ("matmul",    "%c",   ["%a", "%b"], (2, 2)),
    ("add",       "%d",   ["%c", "%w"], (2, 2)),
    ("relu",      "%e",   ["%d"],       (2, 2)),
    ("mul",       "%f",   ["%e", "%s"], (2, 2)),
    ("add",       "%h",   ["%e", "%s"], (2, 2)),
    ("relu",      "%z",   ["%e"],       (2, 2)),   # %z 从未被使用：死值
    ("add",       "%out", ["%f", "%h"], (2, 2)),
    ("output",    None,   ["%out"],     None),
]

# 预演 Day 23 的 add(x, 0) → x 折叠：换边（replace_all_uses）专用小图
FOLD_GRAPH = [
    ("input",   "%x",    [],             (2, 2)),
    ("const 0", "%zero", [],             (2, 2)),
    ("add",     "%d",    ["%x", "%zero"], (2, 2)),
    ("relu",    "%e",    ["%d"],         (2, 2)),
    ("output",  None,    ["%e"],         None),
]


class GraphError(Exception):
    """图不合法，或违反“分析只读 / 改图走方法”的契约。"""


class Graph:
    """语句序列表示的线性计算图（Day 19 同款数据，套上“可变更”的正式外壳）。

    契约：
      * 只读查询（labels / used_at / validate / find_statement）不改图；
      * 修改必须走 remove_statement / replace_all_uses，每次修改 epoch + 1
        并写改动日志——直接改 self.statements 会绕过 epoch，属于调用方 bug；
      * epoch 是“图版本号”：分析结果记录自己诞生时的 epoch，对不上就作废。
    """

    def __init__(self, statements):
        self.statements = [list(s) for s in statements]
        self.epoch = 0
        self.change_log = []

    # ---------- 只读查询 ----------

    def labels(self):
        return [f"S{i + 1}" for i in range(len(self.statements))]

    def used_at(self):
        """每个值被使用的位置列表。图输出语句的输入也算使用（Day 19 教训三）。"""
        used = {}
        for i, (_, _, uses, _) in enumerate(self.statements):
            for u in uses:
                used.setdefault(u, []).append(i)
        return used

    def validate(self):
        """Day 17/18 的合法性闸门：SSA 唯一定义、使用必须先于定义。"""
        defined = {}
        for i, (_, res, _, _) in enumerate(self.statements):
            if res is None:
                continue
            if res in defined:
                raise GraphError(f"{res} 被定义两次（违反 SSA）：S{defined[res] + 1} 和 S{i + 1}")
            defined[res] = i
        for i, (_, _, uses, _) in enumerate(self.statements):
            for u in uses:
                if u not in defined:
                    raise GraphError(f"{u} 被使用但从未定义（S{i + 1}）")
                if defined[u] >= i:
                    raise GraphError(f"{u} 在定义之前被使用（S{i + 1}）")
        return True

    def find_statement(self, result):
        """返回定义 result 的语句下标。"""
        for i, (_, res, _, _) in enumerate(self.statements):
            if res == result:
                return i
        raise KeyError(f"图中没有定义 {result} 的语句")

    # ---------- 修改接口（每个都会 bump epoch）----------

    def _commit(self, note):
        self.epoch += 1
        self.change_log.append(f"epoch {self.epoch}：{note}")

    def remove_statement(self, index):
        stmt = self.statements[index]
        del self.statements[index]
        self._commit(f"删除 S{index + 1}（{stmt[0]} {stmt[1] or ''}）——后面所有语句位置前移")

    def replace_all_uses(self, old, new):
        """把所有读 old 的语句改成读 new（Day 23 折叠 Pass 的核心动作）。"""
        rewired = 0
        for stmt in self.statements:
            if old in stmt[2]:
                stmt[2] = [new if u == old else u for u in stmt[2]]
                rewired += 1
        if rewired == 0:
            raise GraphError(f"没有任何语句使用 {old}，无事可换")
        self._commit(f"换边：{rewired} 条语句改读 {new}（原来读 {old}）——位置没变，Use-Def 变了")
        return rewired


# ---------- 分析 Pass：只读图、报告事实 ----------


class Analysis:
    """分析 Pass 基类。契约：run 期间不许改图，违反会被管理器当场抓住。"""

    name = "analysis"

    def run(self, graph):
        raise NotImplementedError


class UnusedResult:
    """未使用分析的结果：死值集合 + 定义位置。"""

    def __init__(self, dead, where):
        self.dead = frozenset(dead)   # 从未被任何语句（含图输出）使用的值
        self.where = dict(where)      # 值 → 定义位置（打印用）

    def is_dead(self, name):
        return name in self.dead

    def format(self, labels):
        if not self.dead:
            return "（无死值：每个定义的值都至少被使用一次）"
        lines = []
        for name in sorted(self.dead, key=lambda n: self.where[n]):
            lines.append(f"  {name:<6}定义于 {labels[self.where[name]]}，从未被任何语句使用 ← 死值")
        return "\n".join(lines)


class UnusedAnalysis(Analysis):
    """未使用分析：找出“定义了但从未被使用”的值。

    只报告事实：哪些值死、定义在哪。哪些能删（纯算子/常量）、要不要删，
    是变换 Pass（Day 25 的 DCE）的决策，不在这里做。
    """

    name = "unused"

    def run(self, graph):
        used = graph.used_at()
        dead, where = [], {}
        for i, (_, res, _, _) in enumerate(graph.statements):
            if res is None:
                continue
            where[res] = i
            if res not in used:
                dead.append(res)
        return UnusedResult(dead, where)


class LastUseResult:
    """最后使用分析的结果：值 → 最后一次被读的位置（0 基）。"""

    def __init__(self, def_at, last_use, n_stmts):
        self.def_at = dict(def_at)
        self.last_use = dict(last_use)
        self.n_stmts = n_stmts

    def at(self, name):
        """最后使用位置；死值返回 None（归 UnusedAnalysis 管）。"""
        return self.last_use.get(name)

    def dies_after(self, index):
        """语句 index 执行完就可以回收内存的值（最后使用恰好在 index）。"""
        return sorted(n for n, p in self.last_use.items() if p == index)

    def format(self, labels):
        lines = []
        for name in sorted(self.def_at, key=lambda n: self.def_at[n]):
            if name not in self.last_use:
                continue
            d, last = self.def_at[name], self.last_use[name]
            lines.append(f"  {name:<6}定义 {labels[d]:<6}最后使用 {labels[last]:<6}区间 [{labels[d]}, {labels[last]}]")
        return "\n".join(lines)


class LastUseAnalysis(Analysis):
    """最后使用分析：每个值最后一次被读的位置。

    供 Day 99–100 的内存规划调用：dies_after(i) 就是 Day 19 说的“退房时刻”。
    死值没有“最后使用”，不进这张表。
    """

    name = "last-use"

    def run(self, graph):
        used = graph.used_at()
        def_at = {res: i for i, (_, res, _, _) in enumerate(graph.statements) if res is not None}
        last = {name: max(pos) for name, pos in used.items()}
        return LastUseResult(def_at, last, len(graph.statements))


# ---------- 管理器：缓存 + epoch 对账 ----------


class AnalysisManager:
    """分析缓存管理器：分析结果与图版本（epoch）对账。

    get(analysis) 的契约：
      * 图自上次计算以来没变（epoch 相同）→ 直接返回缓存；
      * 图变了（epoch 不同）→ 旧结果作废，重算后再返回；
      * 分析在 run 期间改图 → 当场抛 GraphError（分析只读）；
      * 调用方改图后继续使用手里的旧结果对象，属于调用方 bug（见演示 [7]）。
    """

    def __init__(self, graph):
        self.graph = graph
        self._cache = {}  # name -> (诞生时的 epoch, result)
        self.stats = {"queries": 0, "recomputed": 0, "invalidated": 0}

    def get(self, analysis):
        self.stats["queries"] += 1
        entry = self._cache.get(analysis.name)
        if entry is not None and entry[0] == self.graph.epoch:
            return entry[1]
        if entry is not None:
            self.stats["invalidated"] += 1
        epoch_before = self.graph.epoch
        result = analysis.run(self.graph)
        if self.graph.epoch != epoch_before:
            raise GraphError(
                f"分析 {analysis.name} 在 run 期间修改了图"
                f"（epoch {epoch_before} → {self.graph.epoch}）：分析 Pass 只读，改图请写成变换 Pass")
        self._cache[analysis.name] = (self.graph.epoch, result)
        self.stats["recomputed"] += 1
        return result

    def describe(self):
        lines = [f"缓存对账（图当前 epoch = {self.graph.epoch}）："]
        if not self._cache:
            lines.append("  （还没有任何缓存条目）")
        for name, (epoch, _) in sorted(self._cache.items()):
            state = "有效" if epoch == self.graph.epoch else "已失效"
            lines.append(f"  {name:<10}缓存于 epoch {epoch} → {state}")
        s = self.stats
        lines.append(f"  统计：查询 {s['queries']} 次，重算 {s['recomputed']} 次，"
                     f"失效丢弃 {s['invalidated']} 次")
        return "\n".join(lines)


# ---------- 变换 Pass：改图 + 决策（今天的两个“消费者”预演）----------


def removable(stmt):
    """这条语句的结果若无人使用，是否可以安全删除？

    纯算子和常量没有副作用，可删；input 语句代表外部输入，今天先不删
    （副作用边界的正式化是 Day 25 的事）。
    """
    op, res = stmt[0], stmt[1]
    return res is not None and (op in PURE_OPS or op.startswith("const"))


def run_dce_preview(graph, mgr):
    """最小 DCE（Day 25 的预演）：反复“查未使用 → 删一条”，直到干净。

    每删一条 epoch 就变，下一轮 mgr.get() 自动拿到重算的新结果——
    连锁死代码（删掉一层才露出下一层）就是这样被逐层剥掉的。
    """
    removed = []
    while True:
        unused = mgr.get(UnusedAnalysis())
        target = None
        for i, stmt in enumerate(graph.statements):
            if unused.is_dead(stmt[1]) and removable(stmt):
                target = i
                break
        if target is None:
            return removed
        removed.append(graph.statements[target])
        graph.remove_statement(target)


def recycle_points(graph, mgr):
    """回收点表（Day 99–100 内存规划的预演）：每条语句执行完，谁的内存可回收。"""
    lu = mgr.get(LastUseAnalysis())
    rows = []
    for i, lbl in enumerate(graph.labels()):
        dying = lu.dies_after(i)
        if dying:
            rows.append((lbl, dying))
    return rows


# ---------- 工具 ----------


def fmt_names(names):
    if not names:
        return "（无）"
    return "、".join(sorted(names))


def print_graph(g):
    labels = g.labels()
    for i, (op, res, uses, _) in enumerate(g.statements):
        lhs = f"{res:<6}= " if res else "  →   "
        rhs = f"{op}({', '.join(uses)})" if uses else op
        print(f"{labels[i]:<5}{lhs}{rhs}")


# ---------- 演示 ----------


def demo():
    g = Graph(BASE_GRAPH)
    g.validate()
    mgr = AnalysisManager(g)
    unused_a, lastuse_a = UnusedAnalysis(), LastUseAnalysis()

    print("== [1] 图 G1：Day 19 同款 12 条语句，epoch = 0 ==")
    print_graph(g)
    print(f"图版本号 epoch = {g.epoch}（还没被修改过）；合法性与 Use-Def 由 validate() 把关")

    print("\n== [2] 分析组件一：UnusedAnalysis —— 谁从未被使用 ==")
    unused = mgr.get(unused_a)
    print(unused.format(g.labels()))
    print("契约：只报告事实（哪些值没人读、定义在哪）。能不能删、要不要删，是变换 Pass 的决策。")

    print("\n== [3] 分析组件二：LastUseAnalysis —— 每个值最后被读的位置 ==")
    lu = mgr.get(lastuse_a)
    print(lu.format(g.labels()))
    print("死值 %z 不进这张表：没有“最后使用”可言，归 UnusedAnalysis 管。")
    print("\n回收点表（Day 99–100 内存规划的输入，即 Day 19 的“退房时刻”）：")
    for lbl, dying in recycle_points(g, mgr):
        print(f"  {lbl} 执行完：{fmt_names(dying)} 的缓冲区可回收")
    print("与 Day 19 的严格复用规则严丝合缝：S5 执行完回收 %a，S6 起定义的值才能进那块内存。")

    print("\n== [4] AnalysisManager：缓存与命中（epoch 对账） ==")
    print(mgr.describe())
    print("图没变，再各查一次（应当命中缓存、不重算）：")
    mgr.get(unused_a)
    mgr.get(lastuse_a)
    print(mgr.describe())

    print("\n== [5] 失效第一例：删除语句（DCE 预演，Day 25） ==")
    old_e, old_out = lu.at("%e"), lu.at("%out")
    removed = run_dce_preview(g, mgr)
    print("DCE 预演删除了：")
    for stmt in removed:
        print(f"  {stmt[0]} {stmt[1]}（结果从未被使用，且是无副作用的纯算子）")
    print("改动日志：")
    for entry in g.change_log:
        print("  " + entry)
    fresh_lu = mgr.get(lastuse_a)
    print("重算后对照（两行都变了，但原因不同）：")
    print(f"  %e    最后使用 S{old_e + 1} → S{fresh_lu.at('%e') + 1}   真变了：S10 的 relu(%e) 没了")
    print(f"  %out  最后使用 S{old_out + 1} → S{fresh_lu.at('%out') + 1}   只是挪了编号：还是那条 output 语句")
    print("死值重算：" + fmt_names(mgr.get(unused_a).dead))
    print(mgr.describe())

    print("\n== [6] 失效第二例：换边（折叠预演，Day 23 的 replace_all_uses） ==")
    g2 = Graph(FOLD_GRAPH)
    g2.validate()
    mgr2 = AnalysisManager(g2)
    print("小图 G2：预演 Day 23 的 add(x, 0) → x 折叠")
    print_graph(g2)
    print("初始死值：" + fmt_names(mgr2.get(UnusedAnalysis()).dead))
    n = g2.replace_all_uses("%d", "%x")
    print(f"换边完成：改写 {n} 条语句的输入（relu 的输入从 %d 改成 %x）")
    print("换边后死值：" + fmt_names(mgr2.get(UnusedAnalysis()).dead)
          + " —— 位置一个没动，Use-Def 关系变了，epoch 对账照样抓住")
    removed2 = run_dce_preview(g2, mgr2)
    print("DCE 预演连锁删除：")
    for stmt in removed2:
        print(f"  {stmt[0]} {stmt[1]}")
    print("改动日志：")
    for entry in g2.change_log:
        print("  " + entry)
    print("最终 G2：")
    print_graph(g2)
    print("这就是 Day 23＋Day 25 的完整剧本：折叠换边 → DCE 清扫 → 中间算子消失。")
    print(mgr2.describe())

    print("\n== [7] 事故演示：绕过管理器，直接用旧结果 ==")
    g3 = Graph(BASE_GRAPH)
    mgr3 = AnalysisManager(g3)
    stale_lu = mgr3.get(LastUseAnalysis())
    stale_unused = mgr3.get(UnusedAnalysis())
    print("复制一份 G3（epoch 0），把两份结果取走放在手里，然后删掉死值 %z：")
    g3.remove_statement(g3.find_statement("%z"))
    labels3 = g3.labels()
    fresh_lu3 = mgr3.get(LastUseAnalysis())
    print(f"{'值':<6}{'旧表（epoch 0）':<15}{'重算（epoch 1）':<15}后果")
    for name in ("%e", "%out"):
        old_pos, new_pos = stale_lu.at(name), fresh_lu3.at(name)
        if old_pos >= len(labels3):
            print(f"{name:<6}S{old_pos + 1:<14}S{new_pos + 1:<14}越界：图只剩 {len(labels3)} 条（下标 0..{len(labels3) - 1}）")
        else:
            verdict = "碰巧没撞上（这次）" if old_pos == new_pos else "悄悄错：拿着旧位置当新事实"
            print(f"{name:<6}S{old_pos + 1:<14}S{new_pos + 1:<14}{verdict}")
    try:
        labels3[stale_lu.at("%out")]
    except IndexError as exc:
        print(f"直接拿旧位置当下标：labels[{stale_lu.at('%out')}] → IndexError: {exc}")
    print(f"旧表还认为 %z 是死值：{stale_unused.is_dead('%z')} —— 但它已经不在图里了")
    print("旧答案没崩 ≠ 旧答案正确。结论：改图之后，必须回到管理器重新查询。")
    print(mgr3.describe())

    print("\n== [8] 接口契约（给后续 Pass 作者，详见教程 5.5 节） ==")
    print("  分析只读；改图只走 Graph 的修改方法；分析结果不过夜——改图后重新 get()。")
    return 0


# ---------- 自测 ----------


def self_test():
    results = []

    def check(name, cond):
        results.append((name, bool(cond)))
        print(f"  {'✓' if cond else '✗'} {name}")

    print("== 自测：两个分析组件 + 缓存与失效 ==")

    g = Graph(BASE_GRAPH)
    g.validate()
    mgr = AnalysisManager(g)

    unused = mgr.get(UnusedAnalysis())
    check("未使用分析：基图死值只有 %z", unused.dead == {"%z"})
    check("图输出算使用：%out 不是死值", not unused.is_dead("%out"))

    lu = mgr.get(LastUseAnalysis())
    expect = {"%a": 4, "%b": 4, "%w": 5, "%s": 8, "%c": 5, "%d": 6,
              "%e": 9, "%f": 10, "%h": 10, "%out": 11}
    check("最后使用：与 Day 19 手工表逐项一致", all(lu.at(k) == v for k, v in expect.items()))
    check("死值 %z 不在最后使用表里", lu.at("%z") is None)
    check("S5 执行完可回收 %a、%b", lu.dies_after(4) == ["%a", "%b"])

    recomputed_before = mgr.stats["recomputed"]
    mgr.get(UnusedAnalysis())
    check("图没变时第二次查询命中缓存（不重算）", mgr.stats["recomputed"] == recomputed_before)

    g.remove_statement(g.find_statement("%z"))
    check("删除语句后 epoch 加一", g.epoch == 1)
    lu2 = mgr.get(LastUseAnalysis())
    check("失效重算：%e 最后使用前移到 S9", lu2.at("%e") == 8)
    check("失效重算：%out 最后使用前移到 S11", lu2.at("%out") == 10)
    check("这次查询触发了重算", mgr.stats["recomputed"] == recomputed_before + 1)

    g2 = Graph(FOLD_GRAPH)
    g2.validate()
    mgr2 = AnalysisManager(g2)
    check("折叠图初始没有死值", mgr2.get(UnusedAnalysis()).dead == set())
    g2.replace_all_uses("%d", "%x")
    check("换边后 %d 变成死值（位置没变，关系变了）", mgr2.get(UnusedAnalysis()).dead == {"%d"})

    removed = run_dce_preview(g2, mgr2)
    check("DCE 连锁删掉 %d 和 %zero 两条", [s[1] for s in removed] == ["%d", "%zero"])
    check("删完之后 G2 只剩 3 条语句", len(g2.statements) == 3)
    check("删完之后没有死值", mgr2.get(UnusedAnalysis()).dead == set())

    g1 = Graph(BASE_GRAPH)
    m1 = AnalysisManager(g1)
    removed1 = run_dce_preview(g1, m1)
    check("基图 DCE 预演只删掉 %z 一条", [s[1] for s in removed1] == ["%z"])

    class BadAnalysis(Analysis):
        name = "bad"

        def run(self, graph):
            graph.remove_statement(graph.find_statement("%z"))
            return None

    g4 = Graph(BASE_GRAPH)
    m4 = AnalysisManager(g4)
    try:
        m4.get(BadAnalysis())
        check("改图的分析被管理器当场拒绝", False)
    except GraphError:
        check("改图的分析被管理器当场拒绝（分析只读）", True)

    g3 = Graph(BASE_GRAPH)
    m3 = AnalysisManager(g3)
    stale = m3.get(LastUseAnalysis())
    g3.remove_statement(g3.find_statement("%z"))
    fresh = m3.get(LastUseAnalysis())
    check("旧结果与新结果不是同一份对象", stale is not fresh)
    check("旧结果里 %out 的位置已经越界", stale.at("%out") >= len(g3.statements))

    passed = sum(1 for _, ok in results if ok)
    print(f"\n{passed}/{len(results)} 项通过")
    return 0 if passed == len(results) else 1


def main():
    ap = argparse.ArgumentParser(description="分析组件与分析失效演练场")
    ap.add_argument("--self-test", action="store_true", help="运行测试而不是演示")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    return demo()


if __name__ == "__main__":
    raise SystemExit(main())
