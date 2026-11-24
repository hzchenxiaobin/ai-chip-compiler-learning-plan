#!/usr/bin/env python3
"""第 22 天演练场：Pass 接口与 PassManager——优化流水线的调度台。

用法：
    python3 pass_manager.py               # 演示主流程：空 Pass、两种执行顺序、四类失败处理
    python3 pass_manager.py --self-test   # 运行测试，全部通过退出码 0

Day 20 把“算事实”做成了组件（UnusedAnalysis / LastUseAnalysis），并用
AnalysisManager＋epoch 管住了缓存失效；Day 21 复盘收拢了全套家底。今天补上
优化流水线的最后一块地基：变换怎么被组织起来——

    Pass        最小编译步骤：name ＋ requires ＋ run(graph, am) → True / False
    PassManager 调度台：按加入顺序执行；每个 Pass 跑完依次过四道关卡——
                ① 查返回值 ② 绊线（语句数变了 epoch 却没动 → 有人绕过修改方法）
                ③ Verifier ④ 打印 IR ＋ 记账；任何一道不过 → 拉闸停线

失败共五种，全部立即停止、指认肇事 Pass、列出被跳过的 Pass、返回 False：
    entry   进管线前图就不合法（Day 12 说的“验证失败”，压根不让开工）
    return  Pass 明确返回 False（“这活我干不了”）
    raise   Pass 抛出 PassFailure / GraphError（跑到一半发现前提不成立）
    bypass  绕过修改方法直接改表（记账绊线抓住：epoch 没动）
    verify  Pass 把图改坏，Verifier 当场拒绝

今天的两个“真优化”（fold-add-zero / dce-preview）分别是 Day 23 常量折叠和
Day 25 DCE 的预演，只为让管线有东西可跑；今天的主角是接口和管理器本身。

对应到 MLIR / LLVM 的同构设计：
    * Pass::runOnOperation() 返回 LogicalResult，failure() 会中断整条管线；
    * mlir-opt --mlir-print-ir-after-all 在每个 Pass 之后打印 IR（我们的 print_ir）；
    * mlir-opt 默认在每个 Pass 之后运行 Verifier（--mlir-disable-verifier 可关）；
    * LLVM 的 -print-after-all / -time-passes 是同一类“可观测性”服务。
"""

from __future__ import annotations

import argparse

PURE_OPS = {"matmul", "add", "relu", "mul"}   # 无副作用算子（Day 20 同款口径）

# 贯穿全文的例子：一张 6 条语句的小图。
#   %z 天生死代码（DCE 自己的活）；add(%a, %zero) 是 Day 23 折叠的活——
#   折叠之后 %zero 才变死值，这个“先后手”就是今天顺序实验的全部戏份。
PIPELINE_GRAPH = [
    ("input",   "%a",    [],              (2, 3)),
    ("const 0", "%zero", [],              (2, 3)),
    ("add",     "%d",    ["%a", "%zero"], (2, 3)),
    ("relu",    "%e",    ["%d"],          (2, 3)),
    ("relu",    "%z",    ["%e"],          (2, 3)),   # 从未被使用：天生死代码
    ("output",  None,    ["%e"],          None),
]


class GraphError(Exception):
    """图不合法，或违反“改图走方法”的契约。"""


class PassFailure(Exception):
    """Pass 主动上报的失败（对应 MLIR 的 failure()）。"""


# ---------- 图：Day 20 同款，可变更的正式外壳 ----------


class Graph:
    """语句序列表示的线性计算图（Day 20 同款契约）。

      * 只读查询（labels / used_at / validate）不改图；
      * 修改必须走 remove_statement / replace_all_uses，每次修改 epoch + 1
        并写改动日志——直接改 self.statements 属于调用方 bug，
        今天 PassManager 的记账绊线能抓到其中一类（数量变了版本没动）。
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


# ---------- 分析：Day 20 的组件原样搬来（今天只用到 unused）----------


class Analysis:
    name = "analysis"

    def run(self, graph):
        raise NotImplementedError


class UnusedResult:
    def __init__(self, dead, where):
        self.dead = frozenset(dead)
        self.where = dict(where)

    def is_dead(self, name):
        return name in self.dead


class UnusedAnalysis(Analysis):
    """未使用分析：哪些值从未被任何语句（含图输出）使用。只报告，不决策。"""

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


ANALYSES = {"unused": UnusedAnalysis}   # 依赖名 → 分析类（挂载 Pass 时对照检查）


class AnalysisManager:
    """分析缓存管理器（Day 20 同款）：epoch 对账，图一变旧结果作废。"""

    def __init__(self, graph):
        self.graph = graph
        self._cache = {}   # name -> (诞生时的 epoch, result)
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
            raise GraphError(f"分析 {analysis.name} 在 run 期间修改了图：分析 Pass 只读")
        self._cache[analysis.name] = (self.graph.epoch, result)
        self.stats["recomputed"] += 1
        return result

    def describe(self):
        lines = [f"分析管理器对账（图当前 epoch = {self.graph.epoch}）："]
        if not self._cache:
            lines.append("  （还没有任何缓存条目）")
        for name, (epoch, _) in sorted(self._cache.items()):
            state = "有效" if epoch == self.graph.epoch else "已失效"
            lines.append(f"  {name:<10}缓存于 epoch {epoch} → {state}")
        s = self.stats
        lines.append(f"  统计：查询 {s['queries']} 次，重算 {s['recomputed']} 次，"
                     f"失效丢弃 {s['invalidated']} 次")
        return "\n".join(lines)


# ---------- Pass 接口：今天的主角一 ----------


class Pass:
    """最小 Pass 接口——一份给调度台的“求职简历”。

      name      名字（进日志、进失败报告、进管线清单）；
      requires  声明依赖的分析名（挂载时就对照 ANALYSES 检查，写错当场拒绝）；
      run       干活：输入 graph（就地修改，只准走修改方法）和 am（拿事实），
                成功必须返回 True；干不了返回 False 或抛 PassFailure。
    """

    name = "pass"
    requires = ()

    def run(self, graph, am):
        raise NotImplementedError

    def __repr__(self):
        return f"<Pass {self.name}>"


class PassManager:
    """流水线调度台：按加入顺序执行 Pass，并提供四件配套服务。

      ① 顺序：add() 的顺序就是执行顺序——今天的顺序实验证明这是语义的一部分；
      ② 验证：入口验一次，每个 Pass 之后再验一次（Verifier，Day 12 的闸门）；
      ③ 观测：print_ir = "all" / "change" / "none"，对应 mlir-opt 的 IR 打印开关；
      ④ 记账：每个 Pass 的修改次数（epoch 差）、语句数变化、是否打印、依赖查询数。
      失败处理：五种失败（entry/return/raise/bypass/verify）一律立即停止，
      指认肇事 Pass、列出被跳过的 Pass、返回 False——不回滚、不静默。
    """

    def __init__(self, print_ir="all", verify=True, verbose=True, title="PassManager"):
        self.print_ir = print_ir     # "all" / "change" / "none"
        self.verify = verify
        self.verbose = verbose
        self.title = title
        self.passes = []
        self.log = []
        self.failure = None
        self.skipped = []
        self.am = None

    def add(self, *passes):
        """把 Pass 挂上管线（顺序即执行顺序）。依赖名写错在这里就炸，不等到运行。"""
        for p in passes:
            if not isinstance(p, Pass):
                raise TypeError(f"add 只收 Pass，收到 {type(p).__name__}")
            for dep in p.requires:
                if dep not in ANALYSES:
                    raise ValueError(f"Pass {p.name} 声明了未知分析依赖 {dep!r}（可用：{sorted(ANALYSES)}）")
            self.passes.append(p)
        return self

    def pipeline(self):
        return " → ".join(p.name for p in self.passes) if self.passes else "（空管线）"

    def _say(self, text):
        if self.verbose:
            for line in text.split("\n"):
                print(line)

    def run(self, graph):
        self.log, self.failure, self.skipped = [], None, []
        self.am = AnalysisManager(graph)
        self._say(f"== {self.title}：管线 [{self.pipeline()}] ==")

        # 入口验证：坏图根本不让开工（对应“验证失败”而不是“运行失败”）
        try:
            graph.validate()
        except GraphError as exc:
            self.failure = {"kind": "entry", "pass": "（入口）", "reason": f"进管线前图就不合法：{exc}"}
            self.skipped = [p.name for p in self.passes]
            self._say(f"*** 管线未启动：{self.failure['reason']}")
            if self.skipped:
                self._say(f"    全部跳过：{'、'.join(self.skipped)}")
            return False

        total = len(self.passes)
        for i, p in enumerate(self.passes):
            deps = "、".join(p.requires)
            self._say(f"--- [{i + 1}/{total}] {p.name}" + (f"（声明依赖：{deps}）" if deps else ""))
            epoch_before = graph.epoch
            n_before = len(graph.statements)
            q_before = self.am.stats["queries"]

            # ② 运行 Pass（① 快照已取：epoch_before / n_before / q_before）
            try:
                ok = p.run(graph, self.am)
            except (GraphError, PassFailure) as exc:
                return self._stop(graph, i, p, "raise",
                                  f"{p.name} 抛出 {type(exc).__name__}：{exc}",
                                  epoch_before, n_before, q_before)

            # ③ 查返回值：契约要求成功返回 True
            if ok is not True:
                extra = getattr(p, "reason", "")
                why = f"：{extra}" if extra else ""
                return self._stop(graph, i, p, "return",
                                  f"{p.name} 返回 {ok!r}，不是 True{why}",
                                  epoch_before, n_before, q_before)

            changes = graph.epoch - epoch_before
            n_after = len(graph.statements)

            # ④ 绊线：语句数变了 epoch 却没动 → 有人绕过了修改方法
            if n_after != n_before and changes == 0:
                return self._stop(graph, i, p, "bypass",
                                  f"{p.name} 之后语句数 {n_before}→{n_after}，但 epoch 没动"
                                  f"——绕过了修改方法，change_log 里不会有这条改动的记录",
                                  epoch_before, n_before, q_before)

            # ⑤ Verifier：Pass 可以改图，但改出来的必须是合法的图
            if self.verify:
                try:
                    graph.validate()
                except GraphError as exc:
                    return self._stop(graph, i, p, "verify",
                                      f"{p.name} 之后图不合法：{exc}",
                                      epoch_before, n_before, q_before)

            # ⑥ 打印 IR ＋ 记账
            printed = self.print_ir == "all" or (self.print_ir == "change" and changes > 0)
            entry = {"name": p.name, "deps": list(p.requires), "changes": changes,
                     "before": n_before, "after": n_after,
                     "deps_queried": self.am.stats["queries"] - q_before, "printed": printed}
            self.log.append(entry)
            if printed:
                self._say(f"// IR after {p.name}（修改 {changes} 次，语句 {n_before}→{n_after}，epoch {graph.epoch}）")
                self._say(ir_dump(graph))
            if p.requires and entry["deps_queried"] == 0:
                self._say(f"    （提醒：{p.name} 声明了依赖 {deps}，但一次分析都没查询——死声明？）")

        self._say(f"== 管线完成：{total} 个 Pass 全部成功，图停在 epoch {graph.epoch} ==")
        return True

    def _stop(self, graph, i, p, kind, reason, epoch_before, n_before, q_before):
        """拉闸：记录失败、列出跳过清单、返回 False。不做回滚——真实编译器同样如此。"""
        changes = graph.epoch - epoch_before
        self.failure = {"kind": kind, "pass": p.name, "reason": reason}
        self.log.append({"name": p.name, "deps": list(p.requires), "changes": changes,
                         "before": n_before, "after": len(graph.statements),
                         "deps_queried": self.am.stats["queries"] - q_before,
                         "printed": False, "failed": True})
        self.skipped = [q.name for q in self.passes[i + 1:]]
        self._say(f"*** 管线停止：[{i + 1}/{len(self.passes)}] {p.name} 失败（{kind}）")
        self._say(f"    {reason}")
        if self.skipped:
            self._say(f"    已跳过：{'、'.join(self.skipped)}")
        self._say(f"    图停留在失败那一刻：epoch {graph.epoch}，{len(graph.statements)} 条语句（不做回滚）")
        return False

    def describe(self):
        lines = [f"管线记录（{len(self.log)} 条，共挂 {len(self.passes)} 个 Pass）："]
        if not self.log:
            lines.append("  （一个 Pass 都没跑）")
        for e in self.log:
            mark = "  ← 失败" if e.get("failed") else ""
            lines.append(f"  {e['name']:<16}修改 {e['changes']:>2} 次   语句 {e['before']}→{e['after']}{mark}")
        if self.failure:
            lines.append(f"  失败：{self.failure['pass']}（kind = {self.failure['kind']}）")
        if self.skipped:
            lines.append(f"  跳过：{'、'.join(self.skipped)}")
        return "\n".join(lines)


# ---------- 工具 ----------


def ir_dump(g):
    lines = []
    for i, (op, res, uses, _) in enumerate(g.statements):
        lhs = f"{res:<6}= " if res else "  →   "
        rhs = f"{op}({', '.join(uses)})" if uses else op
        lines.append(f"  S{i + 1:<4}{lhs}{rhs}")
    return "\n".join(lines)


def removable(stmt):
    """结果无人使用且无副作用时可删；input 代表外部输入，不删（Day 25 再正式化）。"""
    op, res = stmt[0], stmt[1]
    return res is not None and (op in PURE_OPS or op.startswith("const"))


def fmt_names(names):
    return "、".join(sorted(names)) if names else "（无）"


# ---------- 今天的四个“演员” Pass ----------


class NoOpPass(Pass):
    """空 Pass：什么都不做，必定成功。

    用途：① 验证调度台本身能转（今天的第一个实验）；
          ② 开发期占位（先把管线骨架搭好，Pass 以后再写）；
          ③ 隔离测量（空 Pass 的耗时 ≈ 管理器自身的开销）。
    """

    name = "noop"

    def run(self, graph, am):
        return True


class FoldAddZeroPass(Pass):
    """Day 23 常量折叠的预演：add(x, 0) → x。

    动作：把 %d 的所有使用者改读 %x（replace_all_uses，epoch +1），
    再删掉 add 语句（epoch 再 +1）。%zero 从此变死值——但清不清理是后面
    DCE 的事，这就是“顺序”要出场的地方。
    """

    name = "fold-add-zero"

    def run(self, graph, am):
        zeros = {res for op, res, _, _ in graph.statements
                 if res and op.startswith("const") and _const_is_zero(op)}
        i = 0
        while i < len(graph.statements):
            op, res, inputs, _ = graph.statements[i]
            if op == "add" and res is not None and len(inputs) == 2:
                if inputs[1] in zeros:
                    other = inputs[0]
                elif inputs[0] in zeros:
                    other = inputs[1]
                else:
                    other = None
                if other is not None:
                    if res in graph.used_at():
                        graph.replace_all_uses(res, other)
                    graph.remove_statement(i)
                    continue     # 删完一条，后面的语句滑到当前位置，i 不动
            i += 1
        return True


def _const_is_zero(op):
    try:
        return float(op.split()[1]) == 0.0
    except (IndexError, ValueError):
        return False


class DcePreviewPass(Pass):
    """Day 25 DCE 的预演：删掉“无使用者且无副作用”的语句。

    依赖声明 requires = ("unused",)：事实由 Day 20 的 UnusedAnalysis 提供。
    每删一条 epoch 就变，循环里必须回到管理器重新查询（Day 20 的铁律）。
    """

    name = "dce-preview"
    requires = ("unused",)

    def run(self, graph, am):
        while True:
            unused = am.get(UnusedAnalysis())
            target = None
            for i, stmt in enumerate(graph.statements):
                if unused.is_dead(stmt[1]) and removable(stmt):
                    target = i
                    break
            if target is None:
                return True
            graph.remove_statement(target)


# ---------- 三个反面教材（失败处理的实验材料）----------


class FailPass(Pass):
    """声明式失败：不干活，直接返回 False。reason 会被写进失败报告。"""

    def __init__(self, name="fail", reason=""):
        self.name = name
        self.reason = reason

    def run(self, graph, am):
        return False


class CorruptInsertPass(Pass):
    """反面教材一：绕过修改方法直接插语句。绊线会抓住它——epoch 没动。"""

    name = "corrupt-insert"

    def run(self, graph, am):
        graph.statements.insert(0, ["add", "%junk", ["%nope"], (2, 3)])
        return True


class CorruptRewritePass(Pass):
    """反面教材二：原地改写输入。语句数不变、epoch 不动，绊线瞎了——只剩 Verifier 抓得住。"""

    name = "corrupt-rewrite"

    def run(self, graph, am):
        for stmt in graph.statements:
            if stmt[0] == "relu":
                stmt[2] = ["%nope"]
                break
        return True


# ---------- 演示 ----------


def demo():
    print("== [1] 空管线热身：一个空 Pass，先把调度台转起来 ==")
    g = Graph(PIPELINE_GRAPH)
    pm = PassManager(title="PM-0")
    pm.add(NoOpPass())
    ok = pm.run(g)
    print(f"run() 返回 {ok}；epoch = {g.epoch}，{len(g.statements)} 条语句——空 Pass 一根手指都没动")
    print(pm.describe())

    print("\n== [2] 顺序一：noop → fold → dce（先折叠，再清扫） ==")
    g1 = Graph(PIPELINE_GRAPH)
    pm1 = PassManager(title="PM-A")
    pm1.add(NoOpPass(), FoldAddZeroPass(), DcePreviewPass())
    ok1 = pm1.run(g1)
    print(f"run() 返回 {ok1}；最终 {len(g1.statements)} 条语句")
    print(pm1.describe())
    print(pm1.am.describe())
    print("改动日志：")
    for entry in g1.change_log:
        print("  " + entry)

    print("\n== [3] 顺序二：noop → dce → fold（先清扫，再折叠） ==")
    g2 = Graph(PIPELINE_GRAPH)
    pm2 = PassManager(title="PM-B")
    pm2.add(NoOpPass(), DcePreviewPass(), FoldAddZeroPass())
    ok2 = pm2.run(g2)
    unused = pm2.am.get(UnusedAnalysis())
    print(f"run() 返回 {ok2}；最终 {len(g2.statements)} 条语句")
    print(f"死值：{fmt_names(unused.dead)} ← %zero 留下来了！dce 走的时候它还不死，fold 走完才变死")
    print("同一张输入图，顺序一得 3 条、顺序二得 4 条——顺序是管线语义的一部分（Day 27 补救）")

    print("\n== [4] 失败一：Pass 明确返回 False ==")
    g3 = Graph(PIPELINE_GRAPH)
    pm3 = PassManager(title="PM-F1")
    pm3.add(NoOpPass(), FailPass("no-support", "场景不支持：演示用的假原因"), FoldAddZeroPass())
    ok3 = pm3.run(g3)
    print(f"run() 返回 {ok3}；图 epoch = {g3.epoch}，{len(g3.statements)} 条语句——fold 根本没跑")
    print(pm3.describe())

    print("\n顺手看入口检查：直接塞一张非法图——")
    bad = Graph(PIPELINE_GRAPH)
    bad.statements.append(["add", "%bad", ["%missing"], (2, 3)])   # %missing 从未定义
    pm_e = PassManager(title="PM-entry", print_ir="none")
    pm_e.add(NoOpPass())
    ok_e = pm_e.run(bad)
    print(f"run() 返回 {ok_e}；失败种类 = {pm_e.failure['kind']}，跑了 {len(pm_e.log)} 个 Pass——压根没让开工")

    print("\n== [5] 失败二：绕过修改方法（记账绊线当场抓住） ==")
    g4 = Graph(PIPELINE_GRAPH)
    pm4 = PassManager(title="PM-F2")
    pm4.add(CorruptInsertPass(), FoldAddZeroPass())
    ok4 = pm4.run(g4)
    print(f"run() 返回 {ok4}；失败种类 = {pm4.failure['kind']}；"
          f"epoch = {g4.epoch}，change_log {len(g4.change_log)} 条——插语句的人没留任何记录，证据确凿")

    print("\n== [6] 失败三：改坏图（Verifier 抓住） ==")
    g5 = Graph(PIPELINE_GRAPH)
    pm5 = PassManager(title="PM-F3")
    pm5.add(CorruptRewritePass(), FoldAddZeroPass())
    ok5 = pm5.run(g5)
    print(f"run() 返回 {ok5}；失败种类 = {pm5.failure['kind']}——绊线瞎了（语句数没变），Verifier 顶住了")

    print("\n== [7] 可观测性开关：print_ir='change'（只打印真正改了图的 Pass） ==")
    g6 = Graph(PIPELINE_GRAPH)
    pm6 = PassManager(title="PM-C", print_ir="change")
    pm6.add(NoOpPass(), FoldAddZeroPass(), DcePreviewPass())
    ok6 = pm6.run(g6)
    print(f"run() 返回 {ok6}；注意 noop 没改图，IR 一行没打——大图上这个开关省掉九成刷屏")

    print("\n== [8] Pass 作者契约（完整版见教程 5.5 节） ==")
    print("  1. 改图只走 graph 的修改方法；要事实就 am.get()——别把分析结果攥在手里过夜；")
    print("  2. 成功返回 True；干不了 / 前提不成立，返回 False 或抛 PassFailure——别硬撑；")
    print("  3. 需要什么分析，写进 requires——挂载时就检查，别等运行到一半才炸。")
    return 0


# ---------- 自测 ----------


def self_test():
    results = []

    def check(name, cond):
        results.append((name, bool(cond)))
        print(f"  {'✓' if cond else '✗'} {name}")

    print("== 自测：Pass 接口与 PassManager ==")

    # A. 空 Pass 与空管线
    g = Graph(PIPELINE_GRAPH)
    pm = PassManager(print_ir="none", verbose=False)
    pm.add(NoOpPass())
    check("空 Pass：run 返回 True", pm.run(g) is True)
    check("空 Pass：图纹丝不动（epoch 0、6 条语句）", g.epoch == 0 and len(g.statements) == 6)
    check("空 Pass：日志记了修改 0 次、语句 6→6", pm.log[0]["changes"] == 0 and pm.log[0]["after"] == 6)
    pm_empty = PassManager(verbose=False)
    check("空管线：一个 Pass 都不挂也能跑，返回 True", pm_empty.run(Graph(PIPELINE_GRAPH)) is True)

    # B. 顺序一：noop → fold → dce
    g1 = Graph(PIPELINE_GRAPH)
    pm1 = PassManager(print_ir="none", verbose=False)
    pm1.add(NoOpPass(), FoldAddZeroPass(), DcePreviewPass())
    check("顺序一：整条管线成功", pm1.run(g1) is True)
    check("顺序一：最终 3 条语句", len(g1.statements) == 3)
    check("顺序一：只剩 input %a / relu %e / output",
          [s[0] for s in g1.statements] == ["input", "relu", "output"])
    check("顺序一：relu 的输入已改读 %a", g1.statements[1][2] == ["%a"])
    check("顺序一：change_log 四条（fold 换边+删除，dce 删 %zero、%z）", len(g1.change_log) == 4)
    q = pm1.am.stats
    check("依赖由管理器供给：dce 查询 unused ≥3 次且全部重算（每删一条 epoch 就变）",
          q["queries"] >= 3 and q["recomputed"] == q["queries"])
    check("执行顺序就是加入顺序", [e["name"] for e in pm1.log] == ["noop", "fold-add-zero", "dce-preview"])

    # C. 顺序二：noop → dce → fold
    g2 = Graph(PIPELINE_GRAPH)
    pm2 = PassManager(print_ir="none", verbose=False)
    pm2.add(NoOpPass(), DcePreviewPass(), FoldAddZeroPass())
    check("顺序二：整条管线成功", pm2.run(g2) is True)
    check("顺序二：最终 4 条语句", len(g2.statements) == 4)
    check("顺序二：%zero 成了死值（dce 走过之后 fold 才让它变死）",
          pm2.am.get(UnusedAnalysis()).is_dead("%zero"))
    check("顺序对照：同一输入两种顺序，3 条 vs 4 条——顺序是语义的一部分",
          len(g1.statements) == 3 and len(g2.statements) == 4)

    # D. 失败：return
    g3 = Graph(PIPELINE_GRAPH)
    pm3 = PassManager(print_ir="none", verbose=False)
    pm3.add(NoOpPass(), FailPass("no-support", "假原因"), FoldAddZeroPass())
    check("失败一：run 返回 False", pm3.run(g3) is False)
    check("失败一：指认肇事 Pass（no-support，kind = return）",
          pm3.failure["kind"] == "return" and pm3.failure["pass"] == "no-support")
    check("失败一：原因带进报告", "假原因" in pm3.failure["reason"])
    check("失败一：后续 fold 被跳过", pm3.skipped == ["fold-add-zero"])
    check("失败一：图停在最后一次合法状态（epoch 0、6 条语句）",
          g3.epoch == 0 and len(g3.statements) == 6)

    # E. 失败：entry
    bad = Graph(PIPELINE_GRAPH)
    bad.statements.append(["add", "%bad", ["%missing"], (2, 3)])
    pm_e = PassManager(verbose=False)
    pm_e.add(NoOpPass())
    check("入口检查：非法图不让开工（kind = entry，一个 Pass 都没跑）",
          pm_e.run(bad) is False and pm_e.failure["kind"] == "entry" and len(pm_e.log) == 0)

    # F. 失败：bypass
    g4 = Graph(PIPELINE_GRAPH)
    pm4 = PassManager(print_ir="none", verbose=False)
    pm4.add(CorruptInsertPass(), FoldAddZeroPass())
    check("失败二：绕过修改方法被绊线抓住（kind = bypass）",
          pm4.run(g4) is False and pm4.failure["kind"] == "bypass")
    check("失败二：epoch 没动、change_log 为空——绕过者不留记录",
          g4.epoch == 0 and len(g4.change_log) == 0)

    # G. 失败：verify
    g5 = Graph(PIPELINE_GRAPH)
    pm5 = PassManager(print_ir="none", verbose=False)
    pm5.add(CorruptRewritePass(), FoldAddZeroPass())
    check("失败三：改坏图被 Verifier 抓住（kind = verify）",
          pm5.run(g5) is False and pm5.failure["kind"] == "verify")
    check("失败三：后续 Pass 被跳过", pm5.skipped == ["fold-add-zero"])

    # H. 失败：raise
    class BoomPass(Pass):
        name = "boom"

        def run(self, graph, am):
            raise PassFailure("演示：跑到一半发现前提不成立")

    g6 = Graph(PIPELINE_GRAPH)
    pm6 = PassManager(print_ir="none", verbose=False)
    pm6.add(NoOpPass(), BoomPass(), DcePreviewPass())
    check("失败四：抛 PassFailure 同样被拦下（kind = raise）",
          pm6.run(g6) is False and pm6.failure["kind"] == "raise")
    check("失败四：跳过 dce-preview", pm6.skipped == ["dce-preview"])

    # I. print_ir 模式
    g7 = Graph(PIPELINE_GRAPH)
    pm7 = PassManager(print_ir="change", verbose=False)
    pm7.add(NoOpPass(), FoldAddZeroPass())
    pm7.run(g7)
    check("print_ir='change'：noop 不打印 IR，fold 打印",
          pm7.log[0]["printed"] is False and pm7.log[1]["printed"] is True)
    g8 = Graph(PIPELINE_GRAPH)
    pm8 = PassManager(print_ir="all", verbose=False)
    pm8.add(NoOpPass())
    pm8.run(g8)
    check("print_ir='all'：空 Pass 也打印（IR 原样，用于确认管线确实经过）", pm8.log[0]["printed"] is True)

    # J. 依赖声明在挂载时检查
    class GhostDepPass(Pass):
        name = "ghost"
        requires = ("no-such-analysis",)

        def run(self, graph, am):
            return True

    try:
        PassManager(verbose=False).add(GhostDepPass())
        check("依赖声明：未知分析在挂载时就被拒绝", False)
    except ValueError:
        check("依赖声明：未知分析在挂载时就被拒绝", True)
    check("dce-preview 声明依赖 unused", DcePreviewPass().requires == ("unused",))

    # K. 死声明提醒（声明了依赖却一次都不查询）
    class LazyPass(Pass):
        name = "lazy-deps"
        requires = ("unused",)

        def run(self, graph, am):
            return True

    import io
    import contextlib
    g9 = Graph(PIPELINE_GRAPH)
    pm9 = PassManager(print_ir="none", verbose=True, title="PM-L")
    pm9.add(LazyPass())
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        pm9.run(g9)
    check("死声明提醒：声明了 unused 却没查询，日志里有提醒", "死声明" in buf.getvalue())
    check("死声明不拉闸：run 仍返回 True", pm9.log[-1].get("failed") is None)

    passed = sum(1 for _, ok in results if ok)
    print(f"\n{passed}/{len(results)} 项通过")
    return 0 if passed == len(results) else 1


def main():
    ap = argparse.ArgumentParser(description="第 22 天演练场：Pass 接口与 PassManager")
    ap.add_argument("--self-test", action="store_true", help="运行自测")
    args = ap.parse_args()
    return self_test() if args.self_test else demo()


if __name__ == "__main__":
    raise SystemExit(main())
