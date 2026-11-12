#!/usr/bin/env python3
"""第 26 天演练场：公共子表达式消除（CSE）——合并完全相同的纯算子。

用法：
    python3 cse.py               # 演示主流程：昨天遗留、贯穿图、事故重演、正戏、负例清单
    python3 cse.py --self-test   # 运行自测，全部通过退出码 0

Day 25 [6b] 留了一条尾巴：%k1 和 %y 是同一笔计算 add(%x, %c1)——DCE 只能删
没人要的，合并重复的活归今天。学习计划的三行——

    学习：结构等价、属性等价、输入顺序和副作用对 CSE 的影响；
    实践：合并完全相同的纯算子，并正确迁移所有使用者；
    产出：CSE Pass、等价和不等价测试。

合并的判据是一张“键表”（哈希表）：
    键相同 ⇔ 同一笔计算 ⇔ 任何输入下结果必然相同 ⇔ 可合并。
    * 结构等价：算子相同 ＋ 输入相同 ＋ 结果 (shape, dtype) 相同；
    * 属性等价：常量按“值＋类型＋shape”进键——const 5 的 i32 和 i64 不是
      一回事，键比的是属性，不是名字（%c1b 和 %c1 名字不同也能等价）；
    * 输入顺序：add/mul 满足交换律，排序后进键；matmul 保序——顺序就是
      语义，matmul(a,b) ≠ matmul(b,a)；
    * 副作用：debug 执行时打印，合并两个 debug = 少打印一行 = 可观察行为
      变了——副作用算子、未知算子、图输入一律不进键表（门卫不猜语义，
      Day 23/24/25 同一原则；input 合并还会改函数签名）。

合并动作只换边：replace_all_uses(后来的, 先来的)，语句本身不删——清扫是
Day 25 dce 的活（分工与 Day 25 [6b] 的约定一致）。“后来的并入先来的”不是
风格偏好，是 SSA 硬要求：先来者的用户可能卡在两条语句之间，反向合并会
制造“使用先于定义”的非法图——Day 17 的 SSA 闸门当场拉闸（[6a] 实验演示）。

正向一趟能扫干净整条级联链：合并在扫到的瞬间就换边，而消费者永远排在
生产者后面（SSA 闸门保证拓扑序）——扫到消费者时，它的输入已经被前面的
合并改好了。const 并入 const 让 add 同键、add 并入 add 让 relu 同键……
四级级联在一趟里全部兑现，第二趟合并 0 次（Day 25 反向一趟的镜像对称）。
"""

from __future__ import annotations

import argparse
import re

PURE_OPS = {"matmul", "add", "relu", "mul"}   # 纯算子白名单（Day 20/25 同款口径）
SIDE_EFFECT_OPS = {"debug"}                   # 副作用算子：执行时打印（可观察）
COMMUTATIVE_OPS = {"add", "mul"}              # 交换律：输入顺序不影响结果


# ---------- 图：Day 22～25 同款外壳（契约一字未改） ----------

class GraphError(Exception):
    """图不合法，或违反“改图走方法”的契约。"""


class PassFailure(Exception):
    """Pass 主动上报的失败（对应 MLIR 的 failure()）。"""


class Graph:
    """语句序列表示的线性计算图（Day 23～25 同款契约）。

      * 只读查询（labels / used_at / validate）不改图；
      * 修改必须走 remove_statement / replace_all_uses，每次修改 epoch + 1
        并写改动日志——绕过方法直接改 statements 会让缓存的分析结果变成
        过期事实（Day 20 的铁律），也会被 Day 22 的 bypass 检查抓住；
      * validate 是 Day 17/18 的 SSA 闸门：唯一定义、使用先于定义。
        “使用先于定义”同时保证语句列表是拓扑序——今天正向一趟的根基，
        也是“后来的并入先来的”这条合并方向的硬约束（[6a] 演示反例）。
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
        """把所有读 old 的语句改成读 new（Day 23/24/25 的换边动作，今天的主角）。

        迁移的正是“所有使用者”：普通算子语句、图输出语句，一个不漏——
        Day 10 的 Use-Def 同步在这里兑现。漏迁一个使用者，那个消费者就读
        一个死值，Day 22 的 verify 会以“被使用但从未定义”拉闸。
        """
        rewired = 0
        for stmt in self.statements:
            if old in stmt[2]:
                stmt[2] = [new if u == old else u for u in stmt[2]]
                rewired += 1
        if rewired == 0:
            raise GraphError(f"没有任何语句使用 {old}，无事可换")
        self._commit(f"换边：{rewired} 条语句改读 {new}（原来读 {old}）——位置没变，Use-Def 变了")
        return rewired


# ---------- 分析：Day 20 的组件原样搬来（PassManager 契约需要） ----------

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
    """流水线调度台（Day 22 同款）：顺序执行、逐 Pass 验证、打印 IR、记账。

    今天要盯两处：verify 在每个 Pass 之后跑 SSA 闸门——[6a] 的反向合并
    版正是在这里被“在定义之前被使用”当场抓住；bypass 检查盯的是“条数变
    了 epoch 没动”——今天 cse 只换边不删语句，条数不变、epoch 每次换边 +1，
    两边都对得上账。
    """

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

            try:
                ok = p.run(graph, self.am)
            except (GraphError, PassFailure) as exc:
                return self._stop(graph, i, p, "raise",
                                  f"{p.name} 抛出 {type(exc).__name__}：{exc}",
                                  epoch_before, n_before)

            if ok is not True:
                return self._stop(graph, i, p, "return",
                                  f"{p.name} 返回 {ok!r}，不是 True",
                                  epoch_before, n_before)

            changes = graph.epoch - epoch_before
            n_after = len(graph.statements)

            if n_after != n_before and changes == 0:
                return self._stop(graph, i, p, "bypass",
                                  f"{p.name} 之后语句数 {n_before}→{n_after}，但 epoch 没动",
                                  epoch_before, n_before)

            if self.verify:
                try:
                    graph.validate()
                except GraphError as exc:
                    return self._stop(graph, i, p, "verify",
                                      f"{p.name} 之后图不合法：{exc}",
                                      epoch_before, n_before)

            printed = self.print_ir == "all" or (self.print_ir == "change" and changes > 0)
            self.log.append({"name": p.name, "changes": changes,
                             "before": n_before, "after": n_after, "printed": printed})
            if printed:
                self._say(f"// IR after {p.name}（修改 {changes} 次，语句 {n_before}→{n_after}，epoch {graph.epoch}）")
                self._say(ir_dump(graph))

        self._say(f"== 管线完成：{total} 个 Pass 全部成功，图停在 epoch {graph.epoch} ==")
        return True

    def _stop(self, graph, i, p, kind, reason, epoch_before, n_before):
        changes = graph.epoch - epoch_before
        self.failure = {"kind": kind, "pass": p.name, "reason": reason}
        self.log.append({"name": p.name, "changes": changes,
                         "before": n_before, "after": len(graph.statements),
                         "printed": False, "failed": True})
        self.skipped = [q.name for q in self.passes[i + 1:]]
        self._say(f"*** 管线停止：[{i + 1}/{len(self.passes)}] {p.name} 失败（{kind}）")
        self._say(f"    {reason}")
        return False


# ---------- 工具（Day 24/25 同款） ----------

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


def const_value(op, dtype):
    """按 dtype 解析常量数值；类型不合法返回 None（Day 24/25 同款）。"""
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

    Day 25 同款口径，外加 matmul 分支（负例清单要证明 a·b ≠ b·a）。
    “可观察行为”就两样：图输出 ＋ debug 打印。优化前后各跑一遍，两者
    完全一致才叫语义不变——学习计划执行原则 3 的“如何验证”。
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
        elif op == "matmul":
            a, b = env[uses[0]], env[uses[1]]
            inner, cols = len(b), len(b[0])
            env[res] = [[sum(a[i][k] * b[k][j] for k in range(inner)) for j in range(cols)]
                        for i in range(len(a))]
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

# 贯穿图：14 条语句，四类重复齐聚一堂——
#   S3  const 1 ×2               属性等价（值＋类型全同，名字不同）
#   S5  add(%x,%c1b)             结构等价（S3 并入 %c1 后与 S4 同键）——级联第二级
#   S7  relu(%p2)                级联第三级（S5 并入 %p1 后与 S6 同键）
#   S10 add(%x,%q2)              交换律等价 ＋ 级联第四级（S7 并入 %q1 后，排序比较）
#   S11/S12 debug(%x) ×2         结构全同也不并——副作用：合并 = 少打印一行
#   S13 add(%x,%c1) 无使用者      死重复：换边无事可做，归 dce 收走
#   S8  mul(%p2,%c1)             %p2 的第二个使用者：一次换边迁两个用户
#   output 读 %m2                 图输出也是使用者：S10 合并时跟着迁走
MAIN_GRAPH = [
    ("input",   "%x",   [],             ((), "i32")),
    ("const 1", "%c1",  [],             ((), "i32")),
    ("const 1", "%c1b", [],             ((), "i32")),   # 属性等价 → 并入 %c1
    ("add",     "%p1",  ["%x", "%c1"],  ((), "i32")),    # 首个 add(x,c1)
    ("add",     "%p2",  ["%x", "%c1b"], ((), "i32")),   # 级联并入 %p1（迁 2 个使用者）
    ("relu",    "%q1",  ["%p1"],        ((), "i32")),
    ("relu",    "%q2",  ["%p2"],        ((), "i32")),   # 级联并入 %q1
    ("mul",     "%t",   ["%p2", "%c1"], ((), "i32")),   # %p2 的第二个使用者
    ("add",     "%m1",  ["%q1", "%x"],  ((), "i32")),
    ("add",     "%m2",  ["%x", "%q2"],  ((), "i32")),   # 交换律并入 %m1（output 跟着迁）
    ("debug",   "%d1",  ["%x"],         ((), "i32")),   # 副作用 ×1
    ("debug",   "%d2",  ["%x"],         ((), "i32")),   # 副作用 ×2：结构全同，不并
    ("add",     "%dead", ["%x", "%c1"], ((), "i32")),   # 死重复：无人使用，归 dce
    ("output",  None,   ["%m2", "%t", "%d1", "%d2"], None),
]

# Day 25 [6b] 的遗留现场：拿掉 debug 之后的 10 条——%k1 和 %y 是同一笔计算
DAY25_LEFTOVER_GRAPH = [
    ("input",   "%x",   [],             ((), "i32")),
    ("const 1", "%c1",  [],             ((), "i32")),
    ("const 9", "%c9",  [],             ((), "i32")),
    ("add",     "%d1",  ["%c1", "%c9"], ((), "i32")),    # 死链第一层
    ("relu",    "%d2",  ["%d1"],        ((), "i32")),   # 死链第二层
    ("relu",    "%d3",  ["%d2"],        ((), "i32")),   # 死链第三层，无人读
    ("add",     "%k1",  ["%x", "%c1"],  ((), "i32")),   # 与 %y 同一笔计算（先出现）
    ("relu",    "%k2",  ["%k1"],        ((), "i32")),   # debug 没了 → 死
    ("add",     "%y",   ["%x", "%c1"],  ((), "i32")),   # 与 %k1 同一笔计算（后出现）
    ("output",  None,   ["%y"],          None),
]

# 负例：交换律的边界——matmul 的输入顺序就是语义
MATMUL_ORDER_GRAPH = [
    ("input",   "%a",   [],              ((2, 2), "i32")),
    ("input",   "%b",   [],              ((2, 2), "i32")),
    ("matmul",  "%m1",  ["%a", "%b"],    ((2, 2), "i32")),
    ("matmul",  "%m2",  ["%b", "%a"],    ((2, 2), "i32")),   # 不许并
    ("output",  None,   ["%m1", "%m2"],  None),
]

# 负例：常量的类型是键的一部分——同值不同型
CONST_DTYPE_GRAPH = [
    ("const 5", "%c32", [],               ((), "i32")),
    ("const 5", "%c64", [],               ((), "i64")),   # 值同型不同：不许并
    ("add",     "%d32", ["%c32", "%c32"], ((), "i32")),
    ("add",     "%d64", ["%c64", "%c64"], ((), "i64")),
    ("output",  None,   ["%d32", "%d64"],  None),
]

# 负例：图输入定义函数签名——两个同型 input 不许并
INPUT_PAIR_GRAPH = [
    ("input",  "%x", [],            ((), "i32")),
    ("input",  "%w", [],            ((), "i32")),   # 同型：不许并
    ("mul",    "%p", ["%x", "%w"], ((), "i32")),
    ("output", None, ["%x", "%w"],  None),
]

# [6a] 反向合并的演示图：先来者 %p1 的用户 %u 卡在重复者 %p2 之前
REVERSE_MERGE_GRAPH = [
    ("input",   "%x",  [],            ((), "i32")),
    ("const 1", "%c1", [],            ((), "i32")),
    ("add",     "%p1", ["%x", "%c1"], ((), "i32")),   # 先来者
    ("relu",    "%u",  ["%p1"],        ((), "i32")),   # %p1 的用户：在 %p2 之前！
    ("add",     "%p2", ["%x", "%c1"], ((), "i32")),   # 重复者（后出现）
    ("output",  None,  ["%u"],         None),
]


# ---------- 今天的主角：公共子表达式消除 ----------

class CsePass(Pass):
    """合并完全相同的纯算子：单趟正向扫描，后来的并入先来的，只换边不删语句。

    等价的判据全部落在 _key 里（四要素）：
      * 结构等价：键 =（算子, 规范化输入, 结果 dtype, 结果 shape）；
      * 属性等价：常量键 =（值, dtype, shape）——比属性不比名字；
      * 输入顺序：add/mul 排序后进键（交换律），其余算子保序；
      * 副作用：debug / 未知算子 / 图输入 / 解析不了的常量一律返回 None
        ——不进键表就永远不可能被合并，门卫不猜语义。

    正向一趟能扫干净级联：合并在扫到的瞬间就换边（replace_all_uses），
    而 SSA 闸门保证消费者排在生产者后面——扫到消费者时，它的输入已被
    前面的合并改好，键当场对上。Day 25 的 DCE 靠反向一趟扫死链，今天
    的 CSE 靠正向一趟扫重复，方向相反，根基是同一个拓扑序。
    """

    name = "cse"

    def __init__(self, commutative=True):
        self.commutative = commutative      # [6b] 实验：交换律关掉会怎样
        self.merges = []
        self.decisions = []

    def run(self, graph, am):
        self.merges = []
        self.decisions = []
        seen = {}                           # 键 → (首个出现者的结果名, 它的输入)
        used = graph.used_at()              # 进场快照：谁有使用者
        # 快照为什么够用：本 Pass 只换边不删语句，位置不变；换边的 old 永远
        # 是“当前正被访问的语句”的结果——此前换掉的只可能是已访问语句的
        # 使用边，当前和未来语句“有没有使用者”这一事实不会被改动。
        for i, stmt in enumerate(graph.statements):
            op, res, inputs, info = stmt
            if res is None:
                self.decisions.append(self._decision("skip", op, "(output)",
                                                      "图输出语句没有结果值——不参与合并"))
                continue
            key = self._key(stmt)
            if key is None:
                self.decisions.append(self._decision("skip", op, res, self._skip_reason(op)))
                continue
            if key in seen:
                first, first_inputs = seen[key]
                if res not in used:
                    self.decisions.append(self._decision(
                        "dead-dup", op, res,
                        f"与 %first 同键但结果无人使用——换边无事可做，死值归 dce".replace("%first", first)))
                    continue
                if is_const(op):
                    how = "属性等价：值＋类型＋shape 全同（键比属性不比名字）"
                elif tuple(inputs) == tuple(first_inputs):
                    how = "结构等价：算子＋输入顺序＋结果类型全同"
                else:
                    how = f"交换律等价：{op} 满足交换律，输入排序后与 %first 同键".replace("%first", first)
                n = graph.replace_all_uses(res, first)     # 迁移所有使用者
                self.merges.append({"later": res, "first": first, "op": op, "users": n})
                self.decisions.append(self._decision(
                    "merge", op, res,
                    f"{how}——{n} 个使用者全部改读 %first（后来的并入先来的）".replace("%first", first)))
            else:
                seen[key] = (res, tuple(inputs))
                self.decisions.append(self._decision("first", op, res, "键首次出现——登记进键表当代表"))
        return True

    def _key(self, stmt):
        op, res, inputs, info = stmt
        shape, dtype = info
        if is_const(op):
            val = const_value(op, dtype)
            if val is None:
                return None                 # 值解析不了的常量：不进键表，最安全
            return ("const", val, dtype, shape)          # 属性等价：值＋类型＋shape
        if op in SIDE_EFFECT_OPS or op not in PURE_OPS:
            return None                     # 副作用/未知算子/图输入：门卫不猜语义
        if self.commutative and op in COMMUTATIVE_OPS:
            ins = tuple(sorted(inputs))     # 交换律：顺序无关
        else:
            ins = tuple(inputs)             # matmul 等：顺序就是语义
        return (op, ins, dtype, shape)      # 结构等价：算子＋输入＋结果类型

    @staticmethod
    def _decision(verdict, op, res, reason):
        return {"verdict": verdict, "op": op, "res": res, "reason": reason}

    @staticmethod
    def _skip_reason(op):
        if op == "input":
            return "图输入定义函数签名——两个 input 合并，调用方少喂一个参数"
        if op in SIDE_EFFECT_OPS:
            return f"副作用算子（{op} 执行时打印）——合并 = 少执行一次 = 可观察行为变了"
        return f"算子 {op} 不在纯算子白名单——语义未知，不进键表"


class BuggyCsePass(Pass):
    """事故重演：照真实 CSE 的做法合并后当场删除重复语句，却忘了副作用。

    与正确版的两处差别，凑齐才有事故：
      1. debug 也进键表（真正的 bug）：两个 debug(%x) 结构全同 → 键相同；
      2. 合并后当场 remove_statement（MLIR 等真实 CSE 的做法）：重复语句
         从图里消失。纯算子删了没人看见；debug 删了，那行打印永远不发生。
    对照正确版：只换边、不删语句——即便哪天键错了，被换边的副作用语句
    还躺在图里，Day 25 的副作用规则会让 dce 留着它继续执行。只换边＋清扫
    归 dce，等于给事故上了双保险。
    """

    name = "cse-buggy"

    def __init__(self):
        self.merges = []

    def run(self, graph, am):
        self.merges = []
        seen, used = {}, graph.used_at()
        i = 0
        while i < len(graph.statements):
            op, res, inputs, info = graph.statements[i]
            if (res is None or op == "input"
                    or (op not in PURE_OPS and op not in SIDE_EFFECT_OPS and not is_const(op))):
                i += 1
                continue
            if is_const(op):
                val = const_value(op, info[1])
                if val is None:
                    i += 1
                    continue
                key = ("const", val, info[1], info[0])
            else:
                key = (op, tuple(sorted(inputs)) if op in COMMUTATIVE_OPS else tuple(inputs),
                       info[1], info[0])
            if key in seen:
                if res in used:
                    graph.replace_all_uses(res, seen[key])
                    self.merges.append({"later": res, "first": seen[key], "op": op})
                    graph.remove_statement(i)     # 真实 CSE 的做法：当场删除重复者
                    continue                      # 位置 i 现在是下一条，不推进
                i += 1
                continue
            seen[key] = res
            i += 1
        return True


class ReverseMergeCsePass(Pass):
    """[6a] 反例：把合并方向反过来——先来的并入后来的。

    同样的键、同样的正向扫描，撞键时却执行 replace_all_uses(first, later)。
    先来者的用户可能卡在两条语句之间（本图里 %u 在 %p1 和 %p2 之间），
    换边后 %u 读到“还没定义”的 %p2——Day 17 的 SSA 闸门当场拉闸，
    Day 22 的 PassManager 在 verify 步骤抓住它。“后来的并入先来的”
    不是风格偏好，是“使用必须先于定义”的硬要求。
    """

    name = "cse-reverse"

    def run(self, graph, am):
        seen = {}
        for stmt in graph.statements:
            op, res, inputs, info = stmt
            if res is None or is_const(op) or op in SIDE_EFFECT_OPS or op not in PURE_OPS:
                continue
            key = (op, tuple(sorted(inputs)) if op in COMMUTATIVE_OPS else tuple(inputs),
                   info[1], info[0])
            if key in seen:
                graph.replace_all_uses(seen[key], res)   # 反方向：先来者并入后来者
            else:
                seen[key] = res
        return True


# ---------- Day 25 的 Pass：死代码消除（原样搬来，负责清扫） ----------

class DcePass(Pass):
    """反向一趟清扫死值（Day 25）：合并掏空的语句，统一归它收走。"""

    name = "dce"

    def run(self, graph, am):
        use_count, users = self._use_tables(graph)
        i = len(graph.statements) - 1
        while i >= 0:
            op, res, inputs, info = graph.statements[i]
            kind, _ = self._judge(op, res, use_count, users)
            if kind == "delete":
                graph.remove_statement(i)
                for u in inputs:
                    use_count[u] -= 1
                    if op in users[u]:
                        users[u].remove(op)
            i -= 1
        return True

    @staticmethod
    def _use_tables(graph):
        use_count, users = {}, {}
        for op, res, uses, _ in graph.statements:
            for u in uses:
                use_count[u] = use_count.get(u, 0) + 1
                users.setdefault(u, []).append(op)
        return use_count, users

    @staticmethod
    def _judge(op, res, use_count, users):
        if op == "output":
            return ("keep", "图输出语句——契约")
        if op == "input":
            return ("keep", "图输入——签名")
        n = use_count.get(res, 0)
        if n > 0:
            return ("keep", "被幸存使用")
        if op in SIDE_EFFECT_OPS:
            return ("keep", "副作用")
        if op in PURE_OPS or is_const(op):
            return ("delete", "无人使用＋纯")
        return ("keep", "未知算子")


# ---------- 演示 ----------

def run_quiet(graph, passes):
    """安静地跑一组 Pass（用于对照实验），返回 (ok, pm)。"""
    pm = PassManager(print_ir="none", verbose=False, title="PM-quiet")
    pm.add(*passes)
    return pm.run(graph), pm


def print_decisions(p):
    counts = {}
    for d in p.decisions:
        counts[d["verdict"]] = counts.get(d["verdict"], 0) + 1
    print(f"判决日志（按扫描顺序，从第一条往后）：检查 {len(p.decisions)} 条——"
          f"首登 {counts.get('first', 0)}，合并 {counts.get('merge', 0)}，"
          f"死重复 {counts.get('dead-dup', 0)}，不参与 {counts.get('skip', 0)}")
    marks = {"first": "○ 首登", "merge": "➤ 合并", "dead-dup": "· 死重复", "skip": "— 不参与"}
    for d in p.decisions:
        print(f"  {marks[d['verdict']]}  {d['op']:<9}{d['res']:<7}{d['reason']}")


def demo():
    print("== [1] 昨天的遗留：Day 25 [6b] 那对重复的 add ==")
    g1 = Graph(DAY25_LEFTOVER_GRAPH)
    print("// 优化前（10 条，%k1 与 %y 是同一笔计算 add(%x, %c1)）：")
    print(ir_dump(g1))
    c1 = CsePass()
    ok1, _ = run_quiet(g1, [c1])
    print(f"cse：run() 返回 {ok1}；{len(c1.merges)} 次合并："
          + "；".join(f"{m['later']} 并入 {m['first']}（迁 {m['users']} 个使用者）" for m in c1.merges))
    print("output 是使用者之一：%y 被并入 %k1，图输出改读 %k1——使用者迁移一个不漏")
    d1p = DcePass()
    ok1b, _ = run_quiet(g1, [d1p])
    print(f"dce：run() 返回 {ok1b}；10 条 → {len(g1.statements)} 条（清扫 cse 掏空的 %y 和死链）")
    print("// cse → dce 之后：")
    print(ir_dump(g1))
    ok_sem, (o_b, dbg_b), (o_a, dbg_a) = same_behavior(Graph(DAY25_LEFTOVER_GRAPH), g1, {"%x": 3})
    print(f"语义对照（喂 %x=3）：输出 {o_b} == {o_a}，打印 {dbg_b} == {dbg_a} → {'一致 ✓' if ok_sem else '不一致 ✗'}")
    print("对比 Day 25 [6b]：dce 先跑 → %k1 死了被删、%y 幸存；cse 先跑 → %y 被并入、%k1 幸存")
    print("两种顺序条数相同、幸存者名字不同——“先出现者当代表”决定的，语义完全一样")

    print("\n== [2] 贯穿图登场：14 条语句，四类重复齐聚 ==")
    g2 = Graph(MAIN_GRAPH)
    print(ir_dump(g2))
    o_base, dbg_base = interp(g2, {"%x": 3})
    print(f"可观察行为基线（喂 %x=3）：输出 {o_base}，打印 {dbg_base}")
    print("埋了四类重复：常量属性等价（%c1b）、结构等价（%p2）、级联（%q2）、交换律（%m2）")
    print("外加副作用对（%d1/%d2 结构全同，必须不并）、死重复（%dead）、双使用者（%p2 喂 %q2 和 %t）")

    print("\n== [3] 事故重演：忘掉副作用的合并器 ==")
    g3 = Graph(MAIN_GRAPH)
    buggy = BuggyCsePass()
    ok3a, _ = run_quiet(g3, [buggy])
    n_mid = len(g3.statements)
    ok3b, _ = run_quiet(g3, [DcePass()])
    print(f"cse-buggy：run() 返回 {ok3a}；{len(buggy.merges)} 次合并（比正确版多一次：%d2 并入 %d1），")
    print(f"          且照真实 CSE 的做法当场删除重复语句：{len(MAIN_GRAPH)} 条 → {n_mid} 条")
    print(f"dce：run() 返回 {ok3b}；收走无人使用的 %dead → {len(g3.statements)} 条（比正确版少一条）")
    o_bug, dbg_bug = interp(g3, {"%x": 3})
    print(f"事故现场（喂 %x=3）：输出 {o_bug}，打印 {dbg_bug}")
    print(f"输出值还是 {o_base}——只对照输出根本发现不了；打印从 {len(dbg_base)} 行变成 {len(dbg_bug)} 行")
    ok_bug, _, _ = same_behavior(Graph(MAIN_GRAPH), g3, {"%x": 3})
    print(f"same_behavior：{'一致（没抓住就麻烦了）' if ok_bug else '不一致 ✗（当场抓住）'}"
          f"——两个 debug(%x) 键相同被合并删除，第二行的打印永远不发生")
    print("教训一：副作用是“执行次数”的一部分——合并纯算子少算一次没人看见，合并 debug 少打印一行立刻穿帮")
    print("教训二：正确版只换边、不删语句，等于双保险——即便哪天键错了，被换边的 debug 还躺在图里，")
    print("        Day 25 的副作用规则会让 dce 留着它继续打印。事故要凑齐“键收了 debug”和“删得干脆”两件事")

    print("\n== [4] 正戏：cse 一趟正向扫描的完整判决 ==")
    g4 = Graph(MAIN_GRAPH)
    cse = CsePass()
    pm4 = PassManager(print_ir="none", verbose=True, title="PM-A")
    pm4.add(cse)
    ok4 = pm4.run(g4)
    print_decisions(cse)
    print(f"run() 返回 {ok4}；{len(MAIN_GRAPH)} 条 → {len(g4.statements)} 条（只换边不删语句），"
          f"epoch = {g4.epoch}（{len(cse.merges)} 次换边过账）")
    print("// cse 之后（5 条死值躺着，等 dce）：")
    print(ir_dump(g4))
    n_before_dce = len(g4.statements)
    d4 = DcePass()
    ok4b, _ = run_quiet(g4, [d4])
    print(f"dce：run() 返回 {ok4b}；{n_before_dce} 条 → {len(g4.statements)} 条——清扫合并掏空的 5 条")
    print("// 最终的图：")
    print(ir_dump(g4))
    for feed in (-2, 0, 3):
        ok_s, (o_b, dbg_b), (o_a, dbg_a) = same_behavior(Graph(MAIN_GRAPH), g4, {"%x": feed})
        print(f"语义对照（喂 %x={feed}）：输出 {o_b} == {o_a}，打印 {dbg_b} == {dbg_a} → {'一致 ✓' if ok_s else '不一致 ✗'}")
    cse2 = CsePass()
    ok_second, _ = run_quiet(g4, [cse2])
    print(f"级联验证：对清扫后的图再跑一遍 cse——合并 {len(cse2.merges)} 次（0 次＝四级级联第一趟就全兑现了）")
    print("级联的原理：合并在扫到的瞬间就换边；消费者排在生产者后面（SSA 闸门保证拓扑序）")
    print("——扫到消费者时输入已经改好，键当场对上。const 并入让 add 同键、add 并入让 relu 同键……")

    print("\n== [5] 等价与不等价清单：正例与负例 ==")
    gm = Graph(MATMUL_ORDER_GRAPH)
    pm_ = CsePass()
    ok_m, _ = run_quiet(gm, [pm_])
    o_m, _ = interp(gm, {"%a": [[1, 2], [3, 4]], "%b": [[5, 6], [7, 8]]})
    print(f"matmul(%a,%b) 与 matmul(%b,%a)：合并 {len(pm_.merges)} 次——顺序就是语义；")
    print(f"  执行对照：a·b = {o_m[0]}，b·a = {o_m[1]}——结果不同，合并就是错")
    gd = Graph(CONST_DTYPE_GRAPH)
    pc = CsePass()
    ok_d, _ = run_quiet(gd, [pc])
    print(f"const 5 i32 与 const 5 i64：合并 {len(pc.merges)} 次——值同型不同，类型是键的一部分")
    gi = Graph(INPUT_PAIR_GRAPH)
    pi = CsePass()
    ok_i, _ = run_quiet(gi, [pi])
    print(f"两个同型 input（%x、%w）：合并 {len(pi.merges)} 次——合并会改函数签名")
    gi2 = Graph(INPUT_PAIR_GRAPH)
    gi2.replace_all_uses("%w", "%x")          # 模拟“如果合并了”的后果
    o_before, _ = interp(Graph(INPUT_PAIR_GRAPH), {"%x": 3, "%w": 5})
    o_after, _ = interp(gi2, {"%x": 3, "%w": 5})
    print(f"  模拟事故：强行把 %w 并入 %x → 喂 (3, 5) 时输出 {o_before} 变 {o_after}——第二个参数被吞了")
    gd2 = Graph(MAIN_GRAPH)
    pd = CsePass()
    run_quiet(gd2, [pd])
    _, dbg_pair = interp(gd2, {"%x": 5})
    n_debug_merge = sum(1 for m in pd.merges if m["op"] == "debug")
    print(f"两个 debug(%x)（结构全同）：合并 {n_debug_merge} 次——执行时打印 {len(dbg_pair)} 行，一行不能少")
    gm2 = Graph([
        ("input",   "%x", [],        ((), "i32")),
        ("mystery", "%u1", ["%x"],    ((), "i32")),
        ("mystery", "%u2", ["%x"],    ((), "i32")),
        ("output",  None, ["%u1", "%u2"], None),
    ])
    pmr = CsePass()
    run_quiet(gm2, [pmr])
    print(f"两个 mystery(%x)（未知算子）：合并 {len(pmr.merges)} 次——语义未知，门卫不猜（Day 23/24/25 同款原则）")

    print("\n== [6] 参数实验：先预测，再看结果 ==")
    print("[6a] 反向合并：先来的并入后来的——预测：SSA 闸门拉闸")
    gr = Graph(REVERSE_MERGE_GRAPH)
    pmr2 = PassManager(print_ir="none", verbose=True, title="PM-reverse")
    pmr2.add(ReverseMergeCsePass())
    okr = pmr2.run(gr)
    print(f"结果：run() 返回 {okr}；失败类型 = {pmr2.failure['kind']}，原因：{pmr2.failure['reason']}")
    print("  %u（%p1 的用户）卡在 %p1 和 %p2 之间——换边后它读到还没定义的 %p2")
    print("  “后来的并入先来的”不是风格偏好：先来者定义在所有被迁移用户之前，SSA 才守得住")
    print("[6b] 关掉交换律（commutative=False）——预测：%m2 不再并入 %m1，少一次合并")
    gb = Graph(MAIN_GRAPH)
    cno = CsePass(commutative=False)
    okb, _ = run_quiet(gb, [cno, DcePass()])
    merges_no = "；".join(f"{m['later']}→{m['first']}" for m in cno.merges)
    print(f"结果：run() 返回 {okb}；合并 {len(cno.merges)} 次（{merges_no}），最终 {len(gb.statements)} 条")
    print("  %m2 = add(%x,%q1) 与 %m1 = add(%q1,%x) 顺序不同、保序比较 → 键不同，不合并")
    print("  连带 %m1 的命运也变了：output 读的是 %m2，%m1 无人使用——交换律开着时它靠")
    print("  合并获得使用者；关掉后它成了死值，dce 顺手收走（合并救活了 %m1，对应 [1] 里两种顺序的幸存者之争）")
    print("  对比 [4]：交换律开着 4 次合并、终点 9 条（幸存 %m1）；关掉 3 次合并、终点也是 9 条（幸存 %m2）")
    ok_sem_b, _, _ = same_behavior(Graph(MAIN_GRAPH), gb, {"%x": 3})
    print(f"  语义对照仍然{'一致 ✓' if ok_sem_b else '不一致 ✗'}——合并判据放宽/收紧改变图的大小，不改变语义")
    return 0


# ---------- 自测 ----------

def self_test():
    results = []

    def check(name, cond):
        results.append((name, bool(cond)))
        print(f"  {'✓' if cond else '✗'} {name}")

    print("== 自测：公共子表达式消除 Pass ==")

    # A. 键的构成：四要素各自落进键里
    s_a = ("add", "%r", ["%x", "%c1"], ((), "i32"))
    s_b = ("add", "%r2", ["%c1", "%x"], ((), "i32"))
    s_c = ("add", "%r3", ["%x", "%c1"], ((), "i64"))
    check("键：add(x,c1) 与 add(c1,x) 交换律下同键", CsePass()._key(s_a) == CsePass()._key(s_b))
    check("键：结果 dtype 不同 → 键不同（类型是键的一部分）",
          CsePass()._key(s_a) != CsePass()._key(s_c))
    check("键：关掉交换律后顺序就是键", CsePass(commutative=False)._key(s_a) != CsePass(commutative=False)._key(s_b))
    s_m1 = ("matmul", "%m1", ["%a", "%b"], ((2, 2), "i32"))
    s_m2 = ("matmul", "%m2", ["%b", "%a"], ((2, 2), "i32"))
    check("键：matmul(a,b) ≠ matmul(b,a)（保序）", CsePass()._key(s_m1) != CsePass()._key(s_m2))
    check("键：const 5 i32 ≠ const 5 i64（属性等价比类型）",
          CsePass()._key(("const 5", "%r", [], ((), "i32"))) != CsePass()._key(("const 5", "%r", [], ((), "i64"))))
    check("键：const 1 与 const 1 同键（比属性不比名字）",
          CsePass()._key(("const 1", "%r", [], ((), "i32"))) == CsePass()._key(("const 1", "%r2", [], ((), "i32"))))
    check("键：debug / input / 未知算子 / 坏常量 → None（不进键表）",
          CsePass()._key(("debug", "%p", ["%x"], ((), "i32"))) is None
          and CsePass()._key(("input", "%x", [], ((), "i32"))) is None
          and CsePass()._key(("mystery", "%m", ["%x"], ((), "i32"))) is None
          and CsePass()._key(("const ?", "%r", [], ((), "i32"))) is None)

    # B. 主图：一趟正向扫描
    g = Graph(MAIN_GRAPH)
    p = CsePass()
    pm = PassManager(print_ir="none", verbose=False)
    pm.add(p)
    check("主图：run 返回 True", pm.run(g) is True)
    check("主图：4 次合并，顺序 %c1b %p2 %q2 %m2",
          [m["later"] for m in p.merges] == ["%c1b", "%p2", "%q2", "%m2"])
    check("主图：合并对象全是先来者 %c1 %p1 %q1 %m1",
          [m["first"] for m in p.merges] == ["%c1", "%p1", "%q1", "%m1"])
    check("主图：只换边不删语句（14 → 14）", len(g.statements) == 14)
    check("主图：epoch = 4（4 次换边都走方法过账）", g.epoch == 4 and len(g.change_log) == 4)
    check("主图：%p2 一次换边迁走 2 个使用者（%q2 和 %t）",
          p.merges[1]["users"] == 2)
    reads = {u for _, _, uses, _ in g.statements for u in uses}
    check("主图：合并后图里没有任何语句读 %c1b/%p2/%q2/%m2",
          not ({"%c1b", "%p2", "%q2", "%m2"} & reads))
    check("主图：output 改读 %m1（图输出也是使用者，迁移不漏）",
          g.statements[-1][2][0] == "%m1")
    check("主图：%t 改读 %p1（第二个使用者同步迁移）",
          any(s[1] == "%t" and s[2] == ["%p1", "%c1"] for s in g.statements))
    check("主图：判决 14 条（每条语句一个判决）", len(p.decisions) == 14)
    check("主图：S1 input 不参与，原因提到签名",
          p.decisions[0]["verdict"] == "skip" and "签名" in p.decisions[0]["reason"])
    check("主图：%d1 %d2 不参与，原因提到副作用（打印）",
          all(d["verdict"] == "skip" and "副作用" in d["reason"]
              for d in p.decisions if d["res"] in ("%d1", "%d2")))
    check("主图：%dead 是死重复（verdict = dead-dup）",
          any(d["res"] == "%dead" and d["verdict"] == "dead-dup" for d in p.decisions))
    check("主图：%m2 的合并理由提到交换律",
          any(d["res"] == "%m2" and "交换律" in d["reason"] for d in p.decisions))
    check("主图：%p2 结构等价、%c1b 属性等价——判决理由可审计",
          any(d["res"] == "%p2" and "结构等价" in d["reason"] for d in p.decisions)
          and any(d["res"] == "%c1b" and "属性等价" in d["reason"] for d in p.decisions))
    check("主图：图仍合法（SSA 闸门通过）", g.validate() is True)

    # C. 级联：一趟全兑现
    g2nd = Graph(MAIN_GRAPH)
    p1st = CsePass()
    run_quiet(g2nd, [p1st])
    p2nd = CsePass()
    run_quiet(g2nd, [p2nd])
    check("级联：第二趟 cse 合并 0 次（四级级联第一趟全兑现）", len(p2nd.merges) == 0)
    check("级联：%q2 合并时读的已是 %p1（键当场对上）",
          any(d["res"] == "%q2" and d["verdict"] == "merge" for d in p1st.decisions))

    # D. cse → dce 管线与语义不变
    g3 = Graph(MAIN_GRAPH)
    run_quiet(g3, [CsePass(), DcePass()])
    check("管线：cse → dce：14 → 9 条", len(g3.statements) == 9)
    check("管线：幸存者 %x %c1 %p1 %q1 %t %m1 %d1 %d2 output",
          [s[1] for s in g3.statements] == ["%x", "%c1", "%p1", "%q1", "%t", "%m1", "%d1", "%d2", None])
    check("管线：两条 debug 都活、都读 %x（副作用不合并的活证）",
          sum(1 for s in g3.statements if s[0] == "debug") == 2
          and all(s[2] == ["%x"] for s in g3.statements if s[0] == "debug"))
    ok_feed = True
    for feed in (-2, 0, 3):
        ok_f, _, _ = same_behavior(Graph(MAIN_GRAPH), g3, {"%x": feed})
        ok_feed = ok_feed and ok_f
    check("语义：三组喂入输出＋打印全部一致", ok_feed)
    o3, dbg3 = interp(g3, {"%x": 3})
    check("语义：喂 %x=3 输出 [7, 4, 3, 3]，打印 2 行",
          o3 == [7, 4, 3, 3] and len(dbg3) == 2)

    # E. 事故重演：忘掉副作用的合并器
    g_bug = Graph(MAIN_GRAPH)
    buggy = BuggyCsePass()
    ok_e, _ = run_quiet(g_bug, [buggy])
    check("事故：cse-buggy 合并 5 次（比正确版多一次 debug：%d2 并入 %d1）",
          len(buggy.merges) == 5 and any(m["op"] == "debug" for m in buggy.merges))
    check("事故：合并后当场删除重复语句 → 14 → 9 条", ok_e and len(g_bug.statements) == 9)
    run_quiet(g_bug, [DcePass()])
    check("事故：dce 收走 %dead → 8 条（比正确版少一条）", len(g_bug.statements) == 8)
    o_bug, dbg_bug = interp(g_bug, {"%x": 3})
    check("事故：输出值不变（[7, 4, 3, 3]，事故藏得深）", o_bug == [7, 4, 3, 3])
    check("事故：打印从 2 行变 1 行（可观察行为被改变）", len(dbg_bug) == 1)
    check("事故：same_behavior 抓得住它",
          same_behavior(Graph(MAIN_GRAPH), g_bug, {"%x": 3})[0] is False)

    # F. Day 25 遗留现场：cse 在前 vs dce 在前
    g_cse_first = Graph(DAY25_LEFTOVER_GRAPH)
    p_cf = CsePass()
    run_quiet(g_cse_first, [p_cf, DcePass()])
    check("遗留：cse → dce：10 → 4 条，%y 并入 %k1（幸存者 %k1）",
          len(p_cf.merges) == 1 and p_cf.merges[0] == {"later": "%y", "first": "%k1", "op": "add", "users": 1}
          and [s[1] for s in g_cse_first.statements] == ["%x", "%c1", "%k1", None])
    g_dce_first = Graph(DAY25_LEFTOVER_GRAPH)
    run_quiet(g_dce_first, [DcePass()])
    check("遗留：dce 单独跑（Day 25 [6b] 重放）：10 → 4 条，幸存者 %y",
          [s[1] for s in g_dce_first.statements] == ["%x", "%c1", "%y", None])
    check("遗留：两种顺序条数相同、幸存者不同，语义都一致",
          same_behavior(Graph(DAY25_LEFTOVER_GRAPH), g_cse_first, {"%x": 3})[0]
          and same_behavior(Graph(DAY25_LEFTOVER_GRAPH), g_dce_first, {"%x": 3})[0])

    # G. 负例回归：等价与不等价测试
    g_m = Graph(MATMUL_ORDER_GRAPH)
    p_m = CsePass()
    run_quiet(g_m, [p_m])
    o_m, _ = interp(g_m, {"%a": [[1, 2], [3, 4]], "%b": [[5, 6], [7, 8]]})
    check("负例：matmul 换序不合并，且 a·b ≠ b·a 有真值为证",
          len(p_m.merges) == 0 and o_m[0] != o_m[1] and o_m[0] == [[19, 22], [43, 50]])
    g_dt = Graph(CONST_DTYPE_GRAPH)
    p_dt = CsePass()
    run_quiet(g_dt, [p_dt])
    check("负例：const 5 i32 与 const 5 i64 不合并（类型是键的一部分）", len(p_dt.merges) == 0)
    check("负例：该图语义照常（喂空 → 输出 [10, 10]）", interp(g_dt, {})[0] == [10, 10])
    g_in = Graph(INPUT_PAIR_GRAPH)
    p_in = CsePass()
    run_quiet(g_in, [p_in])
    check("负例：两个同型 input 不合并（函数签名是对外契约）", len(p_in.merges) == 0)
    g_in_bug = Graph(INPUT_PAIR_GRAPH)
    g_in_bug.replace_all_uses("%w", "%x")
    check("负例：模拟强行合并的后果——喂 (3,5) 输出从 [3, 5] 变 [3, 3]",
          interp(Graph(INPUT_PAIR_GRAPH), {"%x": 3, "%w": 5})[0] == [3, 5]
          and interp(g_in_bug, {"%x": 3, "%w": 5})[0] == [3, 3])
    g_my = Graph([
        ("input",   "%x", [],            ((), "i32")),
        ("mystery", "%u1", ["%x"],        ((), "i32")),
        ("mystery", "%u2", ["%x"],        ((), "i32")),
        ("output",  None, ["%u1", "%u2"],  None),
    ])
    p_my = CsePass()
    run_quiet(g_my, [p_my])
    check("负例：两个未知算子 mystery 不合并（门卫不猜语义）", len(p_my.merges) == 0)
    g_bad = Graph([
        ("const ?", "%c1", [],           ((), "i32")),
        ("const ?", "%c2", [],           ((), "i32")),
        ("output",  None,  ["%c1", "%c2"], None),
    ])
    p_bad = CsePass()
    run_quiet(g_bad, [p_bad])
    check("负例：值解析不了的常量不进键表", len(p_bad.merges) == 0)

    # H. 参数实验 a：反向合并被 SSA 闸门拉闸
    g_rev = Graph(REVERSE_MERGE_GRAPH)
    pm_rev = PassManager(print_ir="none", verbose=False)
    pm_rev.add(ReverseMergeCsePass())
    ok_rev = pm_rev.run(g_rev)
    check("反向合并：先来者并入后来者 → 管线失败（verify 拉闸）",
          ok_rev is False and pm_rev.failure["kind"] == "verify")
    check("反向合并：失败原因是“在定义之前被使用”",
          "在定义之前被使用" in pm_rev.failure["reason"])

    # I. 参数实验 b：关掉交换律
    g_no = Graph(MAIN_GRAPH)
    p_no = CsePass(commutative=False)
    run_quiet(g_no, [p_no, DcePass()])
    check("无交换律：3 次合并，%m2 幸存、%m1 因无人使用被 dce 收走，终点 9 条",
          len(p_no.merges) == 3 and len(g_no.statements) == 9
          and any(s[1] == "%m2" for s in g_no.statements)
          and not any(s[1] == "%m1" for s in g_no.statements))
    check("无交换律：语义仍然一致",
          same_behavior(Graph(MAIN_GRAPH), g_no, {"%x": 3})[0] is True)

    passed = sum(1 for _, ok in results if ok)
    print(f"\n{passed}/{len(results)} 项通过")
    return 0 if passed == len(results) else 1


def main():
    ap = argparse.ArgumentParser(description="第 26 天演练场：公共子表达式消除（CSE）")
    ap.add_argument("--self-test", action="store_true", help="运行自测")
    args = ap.parse_args()
    return self_test() if args.self_test else demo()


if __name__ == "__main__":
    raise SystemExit(main())
