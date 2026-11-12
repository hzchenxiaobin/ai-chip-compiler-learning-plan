#!/usr/bin/env python3
"""第 25 天演练场：死代码消除（DCE）——反向遍历删除无使用者的纯算子。

用法：
    python3 dce.py               # 演示主流程：昨天现场、事故重演、正戏、成本对照、参数实验
    python3 dce.py --self-test   # 运行自测，全部通过退出码 0

Day 23 换边、Day 24 变身，都在制造死值：add(x,0) 换成 x 之后，原来的 add
没了使用者；const-eval 把 add 变身成 const 之后，原来的输入常量没人读了。
死值躺在图里有三重代价：运行期白算一遍、Day 99/100 的内存规划会给它们分
配缓冲区、Day 26 的 CSE 要对着更多语句做匹配。今天写正式的清扫工 DCE：

    学习计划的三行——
    学习：无副作用、有使用者和图输出之间的关系；
    实践：实现反向遍历删除无使用者的纯算子，保留图输出和有副作用节点；
    产出：DCE Pass、多层死代码和副作用反例。

判定的核心是一张三方关系表（结果有没有人用 × 算子纯不纯）：
    有使用者               → 活——下游（含图输出）还要它；
    无使用者 ＋ 纯算子      → 死——删掉不改变任何可观察行为；
    无使用者 ＋ 有副作用    → 活——debug 执行时打印，删了打印就消失；
    图输出语句              → 活——它是图对调用方的契约；
    图输入                  → 活——它定义函数签名，删了签名就变了。

三条保留规则背后是同一个词：可观察行为（observable behavior）——运行期
外界能看到的一切，今天模型化为"图输出 ＋ 副作用节点的效果"。删除纯算子
不碰它们；删除副作用节点会。所以安全性来自白名单：只有声明纯的算子
（PURE_OPS ＋ const）才可能被删，不认识的算子副作用未知，一律按有副作用
处理（Day 23/24"门卫不猜语义"的重演）。

反向遍历为什么一趟就够：我们的语句列表满足拓扑序（Day 17 SSA 闸门保证
使用先于定义），任何消费者都排在生产者后面。从最后一条往前扫，消费者先
受审——消费者死掉时，顺手把生产者的使用计数减一——等扫描走到生产者时，
它看到的就是"幸存世界"的真实使用情况。三层死链 relu(relu(add(c,c)))
一趟全灭，不用回头。Day 24 的 dce-preview 是正向＋重启：每删一条从头再
扫（还要重算 unused 分析——Day 20 的 epoch 对账每次都作废），今天给它
记账做对照：11 条的图，正向重启扫 25 条次，反向一趟 11 条次。

怎么证明"语义不变"：光说不够，本文件带一个最小解释器 interp——按语句
顺序执行图，收集输出值和 debug 打印行。DCE 前后各跑一遍，两者完全一致
才叫语义不变（学习计划的执行原则 3：每个优化都要回答为什么语义不变、
如何验证）。BuggyDcePass 故意忘掉副作用，删掉 debug——输出值没变、
打印消失，只有"输出＋打印"一起对照才抓得住这种事故。
"""

from __future__ import annotations

import argparse
import re

PURE_OPS = {"matmul", "add", "relu", "mul"}   # 纯算子白名单（Day 20 同款口径）
SIDE_EFFECT_OPS = {"debug"}                   # 副作用算子：执行时打印（可观察）


# ---------- 图：Day 24 同款外壳（契约不变） ----------


class GraphError(Exception):
    """图不合法，或违反“改图走方法”的契约。"""


class PassFailure(Exception):
    """Pass 主动上报的失败（对应 MLIR 的 failure()）。"""


class Graph:
    """语句序列表示的线性计算图（Day 23/24 同款契约）。

      * 只读查询（labels / used_at / validate）不改图；
      * 修改必须走 remove_statement / replace_all_uses，每次修改 epoch + 1
        并写改动日志——AnalysisManager 靠 epoch 对账，绕过方法直接改
        statements 会让缓存的分析结果变成过期事实（Day 20 的铁律）；
      * validate 是 Day 17/18 的 SSA 闸门：唯一定义、使用先于定义。
        “使用先于定义”同时保证了语句列表是拓扑序——今天反向一趟的根基。
    """

    def __init__(self, statements):
        self.statements = [list(s) for s in statements]
        self.epoch = 0
        self.change_log = []

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

    def _commit(self, note):
        self.epoch += 1
        self.change_log.append(f"epoch {self.epoch}：{note}")

    def remove_statement(self, index):
        stmt = self.statements[index]
        del self.statements[index]
        self._commit(f"删除 S{index + 1}（{stmt[0]} {stmt[1] or ''}）——后面所有语句位置前移")

    def replace_all_uses(self, old, new):
        """把所有读 old 的语句改成读 new（Day 23/24 的换边动作，今天备用）。"""
        rewired = 0
        for stmt in self.statements:
            if old in stmt[2]:
                stmt[2] = [new if u == old else u for u in stmt[2]]
                rewired += 1
        if rewired == 0:
            raise GraphError(f"没有任何语句使用 {old}，无事可换")
        self._commit(f"换边：{rewired} 条语句改读 {new}（原来读 {old}）——位置没变，Use-Def 变了")
        return rewired


# ---------- 分析：Day 20 的组件原样搬来（正向对照法要用） ----------


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
    """未使用分析：哪些值从未被任何语句（含图输出）使用。只报告，不决策。

    注意它报告的是“当前图的快照”——删除任何一条语句都会让结果过期
    （epoch 对账作废）。DcePass 反向一趟根本不查它：它用减法自己维护
    使用计数，O(1) 一减，不用重算；ForwardDcePass 每删一条重启一轮，
    每轮都要重算一次——对照实验的账就记在这里。
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


ANALYSES = {"unused": UnusedAnalysis}


class AnalysisManager:
    """分析缓存管理器（Day 20 同款）：epoch 对账，图一变旧结果作废。"""

    def __init__(self, graph):
        self.graph = graph
        self._cache = {}
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


# ---------- Pass 接口与 PassManager：Day 22 原样搬来 ----------


class Pass:
    """最小 Pass 接口（Day 22 契约）：name ＋ requires ＋ run(graph, am) → True/False。"""

    name = "pass"
    requires = ()

    def run(self, graph, am):
        raise NotImplementedError

    def __repr__(self):
        return f"<Pass {self.name}>"


class PassManager:
    """流水线调度台（Day 22 同款）：顺序执行、逐 Pass 验证、打印 IR、记账。"""

    def __init__(self, print_ir="all", verify=True, verbose=True, title="PassManager"):
        self.print_ir = print_ir
        self.verify = verify
        self.verbose = verbose
        self.title = title
        self.passes = []
        self.log = []
        self.failure = None
        self.skipped = []
        self.am = None

    def add(self, *passes):
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

        try:
            graph.validate()
        except GraphError as exc:
            self.failure = {"kind": "entry", "pass": "（入口）", "reason": f"进管线前图就不合法：{exc}"}
            self.skipped = [p.name for p in self.passes]
            self._say(f"*** 管线未启动：{self.failure['reason']}")
            return False

        total = len(self.passes)
        for i, p in enumerate(self.passes):
            self._say(f"--- [{i + 1}/{total}] {p.name}")
            epoch_before = graph.epoch
            n_before = len(graph.statements)
            q_before = self.am.stats["queries"]

            try:
                ok = p.run(graph, self.am)
            except (GraphError, PassFailure) as exc:
                return self._stop(graph, i, p, "raise",
                                  f"{p.name} 抛出 {type(exc).__name__}：{exc}",
                                  epoch_before, n_before, q_before)

            if ok is not True:
                return self._stop(graph, i, p, "return",
                                  f"{p.name} 返回 {ok!r}，不是 True",
                                  epoch_before, n_before, q_before)

            changes = graph.epoch - epoch_before
            n_after = len(graph.statements)

            if n_after != n_before and changes == 0:
                return self._stop(graph, i, p, "bypass",
                                  f"{p.name} 之后语句数 {n_before}→{n_after}，但 epoch 没动",
                                  epoch_before, n_before, q_before)

            if self.verify:
                try:
                    graph.validate()
                except GraphError as exc:
                    return self._stop(graph, i, p, "verify",
                                      f"{p.name} 之后图不合法：{exc}",
                                      epoch_before, n_before, q_before)

            printed = self.print_ir == "all" or (self.print_ir == "change" and changes > 0)
            self.log.append({"name": p.name, "changes": changes,
                             "before": n_before, "after": n_after, "printed": printed})
            if printed:
                self._say(f"// IR after {p.name}（修改 {changes} 次，语句 {n_before}→{n_after}，epoch {graph.epoch}）")
                self._say(ir_dump(graph))

        self._say(f"== 管线完成：{total} 个 Pass 全部成功，图停在 epoch {graph.epoch} ==")
        return True

    def _stop(self, graph, i, p, kind, reason, epoch_before, n_before, q_before):
        changes = graph.epoch - epoch_before
        self.failure = {"kind": kind, "pass": p.name, "reason": reason}
        self.log.append({"name": p.name, "changes": changes,
                         "before": n_before, "after": len(graph.statements),
                         "printed": False, "failed": True})
        self.skipped = [q.name for q in self.passes[i + 1:]]
        self._say(f"*** 管线停止：[{i + 1}/{len(self.passes)}] {p.name} 失败（{kind}）")
        self._say(f"    {reason}")
        return False


# ---------- 工具（Day 24 同款） ----------


def fmt_type(info):
    """(shape, dtype) → MLIR 风格类型文本：(() ,'i32') → tensor<i32>。"""
    if info is None:
        return ""
    shape, dtype = info
    dims = "x".join(str(d) for d in shape)
    return f"tensor<{dims + 'x' if dims else ''}{dtype}>"


def ir_dump(g):
    lines = []
    for i, (op, res, uses, info) in enumerate(g.statements):
        lhs = f"{res:<6}= " if res else "  →   "
        rhs = f"{op}({', '.join(uses)})" if uses else op
        ty = f"    : {fmt_type(info)}" if info else ""
        lines.append(f"  S{i + 1:<4}{lhs}{rhs}{ty}")
    return "\n".join(lines)


def is_const(op):
    return op.startswith("const ")


def is_pure(op):
    """白名单判定：只有声明纯的算子（PURE_OPS ＋ const）才可能被删。

    不在名单里的算子（debug、input、output、任何不认识的）副作用未知，
    一律按有副作用处理——默认拒绝，和 Day 23/24 的门卫同一个原则。
    """
    return op in PURE_OPS or is_const(op)


def const_value(op, dtype):
    """按 dtype 解析常量数值；类型不合法返回 None（Day 24 同款）。"""
    try:
        text = op.split(" ", 1)[1].strip()
    except IndexError:
        return None
    if dtype.startswith("i"):
        return int(text) if re.fullmatch(r"[+-]?\d+", text) else None
    try:
        return float(text)
    except ValueError:
        return None


def interp(graph, feed):
    """最小解释器：按语句顺序执行图，返回（输出值列表， debug 打印行列表）。

    今天“可观察行为”的模型就这两样：图输出 ＋ debug 打印。DCE 前后各跑
    一遍，两者完全一致才叫语义不变——这是学习计划执行原则 3 的“如何验证”。
    """
    env, debug_lines, outputs = {}, [], None
    for op, res, uses, info in graph.statements:
        if op == "input":
            env[res] = feed[res]
        elif is_const(op):
            env[res] = const_value(op, info[1])
        elif op == "add":
            env[res] = env[uses[0]] + env[uses[1]]
        elif op == "mul":
            env[res] = env[uses[0]] * env[uses[1]]
        elif op == "relu":
            env[res] = max(0, env[uses[0]])
        elif op == "debug":
            v = env[uses[0]]
            debug_lines.append(f"[debug] {res}({uses[0]}) = {v}")
            env[res] = v          # debug 值穿透：结果就是输入，方便继续算
        elif op == "output":
            outputs = [env[u] for u in uses]
        else:
            raise GraphError(f"解释器不认识算子 {op!r}")
    return outputs, debug_lines


def same_behavior(g1, g2, feed):
    """语义对照：两张图在同一份输入下，输出和打印是否完全一致。"""
    o1, d1 = interp(g1, feed)
    o2, d2 = interp(g2, feed)
    ok = (o1 == o2 and d1 == d2)
    return ok, (o1, d1), (o2, d2)


# ---------- 贯穿全文的图 ----------


# 主角图：三股势力同台——左边一条三层死链，中间一条被 debug 喂着的活链，右边通往图输出
MAIN_GRAPH = [
    ("input",   "%x",   [],              ((), "i32")),
    ("const 1", "%c1",  [],              ((), "i32")),
    ("const 9", "%c9",  [],              ((), "i32")),
    ("add",     "%d1",  ["%c1", "%c9"],  ((), "i32")),   # 死链第一层：10，无人读
    ("relu",    "%d2",  ["%d1"],         ((), "i32")),   # 死链第二层：10，无人读
    ("relu",    "%d3",  ["%d2"],         ((), "i32")),   # 死链第三层：10，无人读
    ("add",     "%k1",  ["%x", "%c1"],   ((), "i32")),   # 活链：被 debug 间接需要
    ("relu",    "%k2",  ["%k1"],         ((), "i32")),   # 活链：被 debug 直接需要
    ("debug",   "%p",   ["%k2"],         ((), "i32")),   # 副作用：结果没人读，但执行时打印
    ("add",     "%y",   ["%x", "%c1"],   ((), "i32")),   # 活：图输出读它
    ("output",  None,   ["%y"],          None),
]

# Day 24 的现场：const-eval 变身之后（%d1 add→const 5、%d2 add→const 45），
# %c3、%c40、%d1 变成死值——昨天 [3] 用 dce-preview 扫，今天用正式的 dce 扫
DAY24_FOLDED_GRAPH = [
    ("input",    "%x",   [],             ((), "i32")),
    ("const 2",  "%c2",  [],             ((), "i32")),
    ("const 3",  "%c3",  [],             ((), "i32")),
    ("const 40", "%c40", [],             ((), "i32")),
    ("const 5",  "%d1",  [],             ((), "i32")),   # 昨天变身出来的
    ("const 45", "%d2",  [],             ((), "i32")),   # 昨天级联折出来的
    ("add",      "%d3",  ["%x", "%c2"],  ((), "i32")),
    ("output",   None,   ["%d2", "%d3"], None),
]


# ---------- 今天的主角：反向遍历的 DCE ----------


class DcePass(Pass):
    """死代码消除：从最后一条语句往前扫，删除“结果无人使用＋算子纯”的语句。

    三条保留规则（判定的另一半）：
      1. 图输出语句不删——它是图对调用方的契约；
      2. 有副作用的算子不删——结果没人读，可观察效果还在（debug 会打印）；
      3. 图输入不删——它定义函数签名，运行期由调用方喂数据。

    反向一趟能扫干净多层死链的原理：语句列表是拓扑序（使用先于定义，
    Day 17 的 SSA 闸门保证），消费者都排在生产者后面。从后往前扫，消费
    者先受审；消费者死掉时把生产者的 use_count 减一；等扫描走到生产者，
    它看到的就是幸存世界的真实使用情况——不用回头，不用重算分析。

    use_count／users 两张表在进 Pass 时建一次，之后全靠删除时的减法维护
    ——“事实会过期”的另一种解法：不是重算，而是把维护摊到每次删除里。
    """

    name = "dce"

    def __init__(self):
        self.decisions = []
        self.stats = {"visited": 0, "deleted": 0, "analysis_queries": 0}

    def run(self, graph, am):
        self.decisions = []
        self.stats = {"visited": 0, "deleted": 0, "analysis_queries": am.stats["queries"]}
        use_count, users = self._use_tables(graph)
        i = len(graph.statements) - 1
        while i >= 0:
            op, res, inputs, info = graph.statements[i]
            self.stats["visited"] += 1
            kind, reason = self._judge(op, res, use_count, users)
            self.decisions.append({"verdict": kind, "op": op, "res": res or "(output)", "reason": reason})
            if kind == "delete":
                graph.remove_statement(i)     # 走方法：epoch +1，改动进日志
                self.stats["deleted"] += 1
                for u in inputs:              # 减法维护：消费者的死讯通知到生产者
                    use_count[u] -= 1
                    if op in users[u]:
                        users[u].remove(op)
            i -= 1
        self.stats["analysis_queries"] = am.stats["queries"] - self.stats["analysis_queries"]
        return True

    @staticmethod
    def _use_tables(graph):
        """两张初始事实表：每个值的使用次数 ＋ 使用它的算子名单。"""
        use_count, users = {}, {}
        for op, res, uses, _ in graph.statements:
            for u in uses:
                use_count[u] = use_count.get(u, 0) + 1
                users.setdefault(u, []).append(op)
        return use_count, users

    @staticmethod
    def _judge(op, res, use_count, users):
        """三方关系表的代码版：返回 ('keep'|'delete', 原因)。"""
        if op == "output":
            return ("keep", "图输出语句——删除会改变图的返回值（对外契约）")
        if op == "input":
            return ("keep", "图输入——定义函数签名，无人读也保留")
        n = use_count.get(res, 0)
        if n > 0:
            who = "、".join(sorted(set(users.get(res, []))))
            return ("keep", f"结果被 {n} 处幸存使用（{who}）——下游还要它")
        if op in SIDE_EFFECT_OPS:
            return ("keep", f"算子有副作用（{op} 执行时打印）——结果没人读也不能删")
        if is_pure(op):
            return ("delete", "结果无人使用＋算子纯——删除不改变可观察行为")
        return ("keep", f"算子 {op} 不在纯算子白名单——副作用未知，按有副作用处理")


class ForwardDcePass(Pass):
    """正向＋重启的 DCE（Day 24 dce-preview 的记账版）：同样的安全规则。

    差别只在遍历方向：从头找第一条死语句，删掉，从头再来。死链要扫
    多少轮、unused 分析要重算多少次，全部记进 stats——和反向一趟对照。
    """

    name = "dce-forward"

    def __init__(self):
        self.stats = {"rounds": 0, "scanned": 0, "deleted": 0, "analysis_runs": 0}

    def run(self, graph, am):
        self.stats = {"rounds": 0, "scanned": 0, "deleted": 0, "analysis_runs": 0}
        while True:
            self.stats["rounds"] += 1
            unused = am.get(UnusedAnalysis())      # epoch 变过就重算（Day 20 对账）
            self.stats["analysis_runs"] += 1
            target = None
            for i, stmt in enumerate(graph.statements):
                self.stats["scanned"] += 1
                if stmt[1] is not None and is_pure(stmt[0]) and unused.is_dead(stmt[1]):
                    target = i
                    break
            if target is None:
                return True
            graph.remove_statement(target)
            self.stats["deleted"] += 1


class BuggyDcePass(Pass):
    """事故重演：只问“结果有没有人用”，不问“删了有没有人发现”。

    它同样反向遍历、同样维护 use_count，规则却少了白名单：结果没人用
    就删（只放过了 input 和 output）。于是 debug(%k2) 被扫走——输出值
    不变、打印消失，语义事故只有“输出＋打印”一起对照才抓得住。
    """

    name = "dce-buggy"

    def __init__(self):
        self.deleted = []

    def run(self, graph, am):
        self.deleted = []
        use_count, _ = DcePass._use_tables(graph)
        i = len(graph.statements) - 1
        while i >= 0:
            op, res, inputs, info = graph.statements[i]
            if res is not None and op != "input" and use_count.get(res, 0) == 0:
                self.deleted.append(res)
                graph.remove_statement(i)
                for u in inputs:
                    use_count[u] -= 1
            i -= 1
        return True


# ---------- 演示 ----------


def run_quiet(graph, passes):
    """安静地跑一组 Pass（用于对照实验），返回 (ok, pm)。"""
    pm = PassManager(print_ir="none", verbose=False, title="PM-quiet")
    pm.add(*passes)
    return pm.run(graph), pm


def print_decisions(p):
    keeps = [d for d in p.decisions if d["verdict"] == "keep"]
    dels = [d for d in p.decisions if d["verdict"] == "delete"]
    print(f"判决日志（按扫描顺序，从最后一条往前）：检查 {len(p.decisions)} 条——留 {len(keeps)} 条，删 {len(dels)} 条")
    for d in p.decisions:
        mark = "✓ 留" if d["verdict"] == "keep" else "✗ 删"
        print(f"  {mark}  {d['op']:<8}{d['res']:<10}{d['reason']}")


def demo():
    print("== [1] 昨天的现场：const-eval 变身出 3 个死值，今天一趟扫走 ==")
    g1 = Graph(DAY24_FOLDED_GRAPH)
    print("// DCE 之前（8 条，%c3、%c40、%d1 已无人读）：")
    print(ir_dump(g1))
    d1pass = DcePass()
    ok, _ = run_quiet(g1, [d1pass])
    print(f"run() 返回 {ok}；{len(DAY24_FOLDED_GRAPH)} 条 → {len(g1.statements)} 条，epoch = {g1.epoch}（3 次删除）")
    print("被扫走：%c3、%c40、%d1——全是昨天的变身副产物；%c2 留下（%d3 还在用）")
    ok_sem, (o_b, dbg_b), (o_a, dbg_a) = same_behavior(Graph(DAY24_FOLDED_GRAPH), g1, {"%x": 7})
    print(f"语义对照（喂 %x=7）：输出 {o_b} == {o_a}，打印 {dbg_b} == {dbg_a} → {'一致 ✓' if ok_sem else '不一致 ✗'}")
    print("昨天的 dce-preview 今天转正：名字里的 preview 去掉，规则、遍历、记账全部正式化")

    print("\n== [2] 贯穿图登场：11 条语句，三股势力 ==")
    g2 = Graph(MAIN_GRAPH)
    print(ir_dump(g2))
    print("三股势力：%d1→%d2→%d3 死链（无人读）｜%k1→%k2 被 debug 喂着 ｜%y 通往图输出")
    print("%c9 只喂死链，%c1 同时喂死链和活链，%x 喂活链和输出——它们仨命运不同，见 [4]")
    o_base, dbg_base = interp(g2, {"%x": 3})
    print(f"可观察行为基线（喂 %x=3）：输出 {o_base}，打印 {dbg_base}")
    print("“可观察行为”今天只有两样：图输出 ＋ debug 打印——DCE 的合法性就押在这两样不变上")

    print("\n== [3] 事故重演：只问“有没有人用”的清扫工 ==")
    g3 = Graph(MAIN_GRAPH)
    buggy = BuggyDcePass()
    ok3, _ = run_quiet(g3, [buggy])
    print(f"dce-buggy：run() 返回 {ok3}；11 条 → {len(g3.statements)} 条，删了 {buggy.deleted}")
    o_bug, dbg_bug = interp(g3, {"%x": 3})
    print(f"事故现场（喂 %x=3）：输出 {o_bug}，打印 {dbg_bug}")
    print(f"输出值还是 {o_base}——只对照输出根本发现不了；但打印行 {dbg_base} 消失了")
    print("更糟的是级联：debug 一倒，%k2、%k1 的使用计数跟着归零——正确版留 7 条，它只剩 4 条")
    print("教训：安全性来自白名单——只有“声明纯”的算子才可能被删，不认识的当有副作用（默认拒绝）")

    print("\n== [4] 正戏：dce 一趟反向扫描的完整判决 ==")
    g4 = Graph(MAIN_GRAPH)
    dce = DcePass()
    pm4 = PassManager(print_ir="none", verbose=True, title="PM-A")
    pm4.add(dce)
    ok4 = pm4.run(g4)
    print_decisions(dce)
    print(f"run() 返回 {ok4}；11 条 → {len(g4.statements)} 条，epoch = {g4.epoch}（4 次删除）")
    print("// DCE 之后：")
    print(ir_dump(g4))
    print("改动日志：")
    for entry in g4.change_log:
        print("  " + entry)
    print("四连删全在一趟里：S6 死讯让 %d2 计数归零，轮到 S5 正好判死——反向一趟的级联")
    ok_sem, (o_b, dbg_b), (o_a, dbg_a) = same_behavior(Graph(MAIN_GRAPH), g4, {"%x": 3})
    print(f"语义对照（喂 %x=3）：输出 {o_b} == {o_a}，打印 {dbg_b} == {dbg_a} → {'一致 ✓' if ok_sem else '不一致 ✗'}")
    print("debug 活下来了（副作用规则），%k2、%k1 跟着活（被幸存语句使用），%x、%c1 活（%y 还要用）")

    print("\n== [5] 成本对照：正向重启 vs 反向一趟 ==")
    g5 = Graph(MAIN_GRAPH)
    fwd = ForwardDcePass()
    ok5, pm5 = run_quiet(g5, [fwd])
    print(f"dce-forward：run() 返回 {ok5}；{len(MAIN_GRAPH)} 条 → {len(g5.statements)} 条")
    print(f"  扫描 {fwd.stats['scanned']} 条次，{fwd.stats['rounds']} 轮，删 {fwd.stats['deleted']} 条，"
          f"unused 分析重算 {pm5.am.stats['recomputed']} 次（作废 {pm5.am.stats['invalidated']} 次）")
    g5b = Graph(MAIN_GRAPH)
    rev = DcePass()
    ok5b, pm5b = run_quiet(g5b, [rev])
    print(f"dce（反向）：run() 返回 {ok5b}；{len(MAIN_GRAPH)} 条 → {len(g5b.statements)} 条")
    print(f"  扫描 {rev.stats['visited']} 条次，删 {rev.stats['deleted']} 条，分析查询 {rev.stats['analysis_queries']} 次")
    print(f"  （PM 记账：queries={pm5b.am.stats['queries']}，recomputed={pm5b.am.stats['recomputed']}——一趟零分析）")
    same = [s[:3] for s in g5.statements] == [s[:3] for s in g5b.statements]
    print(f"两种遍历的最终图完全相同：{same}——差别只在成本：{fwd.stats['scanned']} 条次 vs {rev.stats['visited']} 条次")
    print("死链越长差距越大：正向每删一条都要从头再扫一遍（还要重算分析）；反向把维护摊进删除的减法里")

    print("\n== [6] 参数实验：改一处，先预测再看结果 ==")
    print("[6a] 把 output(%y) 改成 output(%y, %d3)——预测：死链整条被救活，0 删除")
    g6a = Graph([s for s in MAIN_GRAPH])
    g6a.statements[-1][2] = ["%y", "%d3"]
    d6a = DcePass()
    ok6a, _ = run_quiet(g6a, [d6a])
    print(f"结果：run() 返回 {ok6a}；11 条 → {len(g6a.statements)} 条，删 {d6a.stats['deleted']} 条，epoch = {g6a.epoch}")
    print("图输出是最强的根：它读 %d3，活性沿 %d3→%d2→%d1→%c9 一路传染回生产者")
    print("[6b] 把 debug 语句拿掉——预测：右链 %k2、%k1 失去唯一的根，跟着死链一起被扫走")
    g6b = Graph([s for s in MAIN_GRAPH if s[0] != "debug"])
    d6b = DcePass()
    ok6b, _ = run_quiet(g6b, [d6b])
    print(f"结果：run() 返回 {ok6b}；10 条 → {len(g6b.statements)} 条，删 {d6b.stats['deleted']} 条")
    print("只剩 %x、%c1、%y、output——%k1 和 %y 是同一笔计算（add(%x,%c1)），合并它们是 Day 26 CSE 的活")
    print("活性的方向：从根（图输出＋副作用节点）逆向流向生产者——根没了，子树全死；根加一个，死链复活")
    return 0


# ---------- 自测 ----------


def self_test():
    results = []

    def check(name, cond):
        results.append((name, bool(cond)))
        print(f"  {'✓' if cond else '✗'} {name}")

    print("== 自测：死代码消除 Pass ==")

    # A. 初始事实表
    uc, us = DcePass._use_tables(Graph(MAIN_GRAPH))
    check("事实表：%x 被使用 2 次", uc["%x"] == 2)
    check("事实表：%c1 被使用 3 次（死链、活链、输出链各一）", uc["%c1"] == 3)
    check("事实表：%c9 只被死链使用 1 次", uc["%c9"] == 1)
    check("事实表：%d3、%p 无人使用", uc.get("%d3", 0) == 0 and uc.get("%p", 0) == 0)
    check("事实表：%y 被图输出使用", "output" in us["%y"])

    # B. 主图：一趟反向扫描
    g = Graph(MAIN_GRAPH)
    p = DcePass()
    pm = PassManager(print_ir="none", verbose=False)
    pm.add(p)
    check("主图：run 返回 True", pm.run(g) is True)
    check("主图：11 → 7 条", len(g.statements) == 7)
    deleted = {d["res"] for d in p.decisions if d["verdict"] == "delete"}
    check("主图：删的恰好是 %d3 %d2 %d1 %c9（多层死链＋死常量）",
          deleted == {"%d3", "%d2", "%d1", "%c9"})
    check("主图：epoch = 4（4 次删除，每次都走方法过账）", g.epoch == 4 and len(g.change_log) == 4)
    check("主图：判决 11 条（每条语句一个判决）", len(p.decisions) == 11)
    check("主图：访问顺序从最后一条开始（第一个判决是 output）", p.decisions[0]["op"] == "output")
    check("主图：最后一个判决是图输入 %x", p.decisions[-1]["op"] == "input")
    check("主图：图仍合法（SSA 闸门通过）", g.validate() is True)
    check("主图：debug %p 被留，原因提到副作用",
          any(d["res"] == "%p" and d["verdict"] == "keep" and "副作用" in d["reason"] for d in p.decisions))
    check("主图：%k2 被留，原因提到幸存使用",
          any(d["res"] == "%k2" and d["verdict"] == "keep" and "使用" in d["reason"] for d in p.decisions))
    check("主图：%x 被留，原因提到签名",
          any(d["res"] == "%x" and "签名" in d["reason"] for d in p.decisions))
    check("主图：output 被留，原因提到契约",
          any(d["op"] == "output" and "契约" in d["reason"] for d in p.decisions))
    check("主图：stats 一趟 11 次访问、4 次删除", p.stats["visited"] == 11 and p.stats["deleted"] == 4)
    check("主图：零分析查询（减法维护，不靠 UnusedAnalysis）", p.stats["analysis_queries"] == 0)

    # C. 语义不变（学习计划执行原则 3 的“如何验证”）
    ok_sem, (o_b, dbg_b), (o_a, dbg_a) = same_behavior(Graph(MAIN_GRAPH), g, {"%x": 3})
    check("语义：DCE 前后输出一致（[4]）", ok_sem and o_a == [4])
    check("语义：DCE 前后打印一致", dbg_a == ["[debug] %p(%k2) = 4"] and dbg_b == dbg_a)
    g_neg = Graph([
        ("const -5", "%c", [], ((), "i32")),
        ("relu", "%r", ["%c"], ((), "i32")),
        ("output", None, ["%r"], None),
    ])
    check("解释器事实：relu(-5) = 0", interp(g_neg, {}) == ([0], []))

    # D. 事故重演：忘掉副作用的清扫工
    g_bug = Graph(MAIN_GRAPH)
    buggy = BuggyDcePass()
    ok_bug, _ = run_quiet(g_bug, [buggy])
    check("事故：dce-buggy 删了 %p（debug），还级联错删了 %k2、%k1",
          set(buggy.deleted) == {"%p", "%k2", "%k1", "%d3", "%d2", "%d1", "%c9"})
    check("事故：11 → 4 条（正确版留 7 条——错删会级联放大）", len(g_bug.statements) == 4)
    o_bug, dbg_bug = interp(g_bug, {"%x": 3})
    check("事故：输出值不变（事故藏得深）", o_bug == [4])
    check("事故：打印行消失（可观察行为被改变）", dbg_bug == [] )
    check("事故：same_behavior 抓得住它",
          same_behavior(Graph(MAIN_GRAPH), g_bug, {"%x": 3})[0] is False)

    # E. 白名单：不认识的算子默认不删
    g_m = Graph([
        ("const 3", "%c3", [], ((), "i32")),
        ("mystery", "%m", ["%c3"], ((), "i32")),
        ("output", None, ["%c3"], None),
    ])
    p_m = DcePass()
    ok_m, _ = run_quiet(g_m, [p_m])
    check("白名单：%m 无人使用但 mystery 不认识 → 留（默认拒绝）",
          ok_m and len(g_m.statements) == 3
          and any(d["res"] == "%m" and "白名单" in d["reason"] for d in p_m.decisions))

    # F. 正向对照：同样安全、同样结果、更高成本
    g_f = Graph(MAIN_GRAPH)
    fwd = ForwardDcePass()
    ok_f, pm_f = run_quiet(g_f, [fwd])
    check("正向：run 返回 True，11 → 7 条", ok_f and len(g_f.statements) == 7)
    check("正向：与反向最终图完全相同",
          [s[:3] for s in g_f.statements] == [s[:3] for s in g.statements])
    check("正向：5 轮、扫 25 条次、删 4 条",
          fwd.stats["rounds"] == 5 and fwd.stats["scanned"] == 25 and fwd.stats["deleted"] == 4)
    check("正向：unused 分析重算 5 次、作废 4 次（Day 20 epoch 对账）",
          pm_f.am.stats["recomputed"] == 5 and pm_f.am.stats["invalidated"] == 4)

    # G. 参数实验 a：图输出救活死链
    g_a = Graph([list(s) for s in MAIN_GRAPH])
    g_a.statements[-1][2] = ["%y", "%d3"]
    p_a = DcePass()
    ok_a, pm_a = run_quiet(g_a, [p_a])
    check("救活：output 读 %d3 → 0 删除、epoch 不动",
          ok_a and len(g_a.statements) == 11 and g_a.epoch == 0 and p_a.stats["deleted"] == 0)
    check("救活：epoch 不动 → 分析零查询零重算（Day 20 对账）",
          pm_a.am.stats == {"queries": 0, "recomputed": 0, "invalidated": 0})

    # H. 参数实验 b：拿掉 debug，右链跟着死
    g_b = Graph([s for s in MAIN_GRAPH if s[0] != "debug"])
    p_b = DcePass()
    ok_b, _ = run_quiet(g_b, [p_b])
    deleted_b = {d["res"] for d in p_b.decisions if d["verdict"] == "delete"}
    check("拔根：10 → 4 条，删 %d3 %d2 %d1 %c9 %k2 %k1",
          ok_b and len(g_b.statements) == 4
          and deleted_b == {"%d3", "%d2", "%d1", "%c9", "%k2", "%k1"})
    check("拔根：剩下的恰好是 %x %c1 %y output",
          [s[1] for s in g_b.statements] == ["%x", "%c1", "%y", None])
    check("拔根：语义不变（输入图本来就没有 debug 行）",
          same_behavior(Graph([s for s in MAIN_GRAPH if s[0] != "debug"]), g_b, {"%x": 3})[0] is True)

    # I. Day 24 现场重放
    g_d24 = Graph(DAY24_FOLDED_GRAPH)
    p_d24 = DcePass()
    ok_d24, _ = run_quiet(g_d24, [p_d24])
    check("重放：8 → 5 条，删 %c3 %c40 %d1",
          ok_d24 and len(g_d24.statements) == 5
          and {d["res"] for d in p_d24.decisions if d["verdict"] == "delete"} == {"%c3", "%c40", "%d1"})
    check("重放：%c2 留下（%d3 还在用）", any(s[1] == "%c2" for s in g_d24.statements))
    check("重放：语义不变（喂 %x=7 → 输出 [45, 9]）",
          same_behavior(Graph(DAY24_FOLDED_GRAPH), g_d24, {"%x": 7}) == (True, ([45, 9], []), ([45, 9], [])))

    # J. 部分使用者：一半用户死了，值还活
    g_s = Graph([
        ("const 5", "%c5", [], ((), "i32")),
        ("const 7", "%c7", [], ((), "i32")),
        ("add", "%a", ["%c5", "%c7"], ((), "i32")),    # 死：无人读
        ("mul", "%b", ["%c5", "%c7"], ((), "i32")),    # 活：output 读
        ("output", None, ["%b"], None),
    ])
    p_s = DcePass()
    ok_s, _ = run_quiet(g_s, [p_s])
    check("部分使用者：5 → 4 条，只删 %a", ok_s and len(g_s.statements) == 4)
    check("部分使用者：%c5 被留（减法从 2 减到 1，没归零）",
          any(s[1] == "%c5" for s in g_s.statements))

    # K. 无人读的图输入：签名规则
    g_i = Graph([
        ("input", "%x", [], ((), "i32")),
        ("input", "%w", [], ((), "i32")),              # 无人读
        ("const 2", "%c2", [], ((), "i32")),
        ("add", "%y", ["%x", "%c2"], ((), "i32")),
        ("output", None, ["%y"], None),
    ])
    p_i = DcePass()
    ok_i, _ = run_quiet(g_i, [p_i])
    check("签名：无人读的 %w 被留，原因提到签名",
          ok_i and len(g_i.statements) == 5
          and any(d["res"] == "%w" and "签名" in d["reason"] for d in p_i.decisions))

    # L. 长死链：反向一趟 vs 正向重启的成本差
    long_graph = [("input", "%x", [], ((), "i32"))]
    long_graph.append(("const 1", "%c1", [], ((), "i32")))
    prev = "%c1"
    for k in range(40):
        name = f"%t{k}"
        long_graph.append(("relu", name, [prev], ((), "i32")))
        prev = name
    long_graph.append(("add", "%y", ["%x", "%c1"], ((), "i32")))
    long_graph.append(("output", None, ["%y"], None))
    g_l1, g_l2 = Graph(long_graph), Graph(long_graph)
    p_l = DcePass()
    ok_l1, _ = run_quiet(g_l1, [p_l])
    f_l = ForwardDcePass()
    ok_l2, pm_l = run_quiet(g_l2, [f_l])
    check("长链：44 条 → 4 条（40 层 relu 全死，%x %c1 %y output 留下）",
          ok_l1 and len(g_l1.statements) == 4)
    check("长链：反向一趟 44 次访问、零分析",
          p_l.stats["visited"] == 44 and p_l.stats["analysis_queries"] == 0)
    check("长链：正向 41 轮、分析重算 41 次", f_l.stats["rounds"] == 41 and pm_l.am.stats["recomputed"] == 41)
    check("长链：正向扫描条次远大于反向（差距随链长增长）",
          f_l.stats["scanned"] > 4 * p_l.stats["visited"])
    check("长链：两种遍历最终图相同", [s[:3] for s in g_l1.statements] == [s[:3] for s in g_l2.statements])

    passed = sum(1 for _, ok in results if ok)
    print(f"\n{passed}/{len(results)} 项通过")
    return 0 if passed == len(results) else 1


def main():
    ap = argparse.ArgumentParser(description="第 25 天演练场：死代码消除（DCE）")
    ap.add_argument("--self-test", action="store_true", help="运行自测")
    args = ap.parse_args()
    return self_test() if args.self_test else demo()


if __name__ == "__main__":
    raise SystemExit(main())
