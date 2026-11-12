#!/usr/bin/env python3
"""第 28 天演练场（第 4 周复盘 · 第一阶段收官）：四层串联＋三连问＋15 分钟讲解。

用法：
    python3 week4_review.py               # 演示主流程：[1]～[9]
    python3 week4_review.py --self-test   # 运行复盘测试，全部通过退出码 0

学习计划第 28 天三行——
    学习：回顾从 Tensor 到图 IR、程序分析和优化 Pass 的完整关系；
    实践：用 15 分钟口头讲解自己的最小编译器，记录讲不清楚的地方；
    产出：阶段总结；能回答“一个优化 Pass 为什么合法、如何测试、何时失效”。

四层关系（今天的主线，也是讲解提纲的前四站）：
    L0 数据底座（Day 1–7）  Tensor 元信息：shape／dtype／字节——每条语句
                           自带一份 TensorDesc，回答“数据长什么样”
    L1 表达层（Day 8–14）   图 IR：SSA 唯一定义、Use-Def 双向账本、
                           Verifier 闸门——回答“计算是什么结构、谁依赖谁”
    L2 事实层（Day 15–21）  分析只读＋epoch 对账：死值名单、使用位置——
                           回答“这张图当下的事实是什么”
    L3 变换层（Day 22–27）  四个 Pass＝三类动作（换边／变身／删除），
                           FixpointRunner 跑到不动点——回答“怎么安全地改图”

今天的新增组件（图外壳、分析、PassManager、四个 Pass、FixpointRunner、
解释器全部原样搬自 Day 22–27，契约一字未改）：
    tensor_bill / use_def_rows    前两层的账本：类型字节表、Use-Def 对照表
    strict_same_behavior          严格语义对照：浮点输出按位级（bit pattern）
                                  比较——== 认为 0.0 == -0.0，位级不这么认为
    TALK_OUTLINE                  15 分钟讲解的六站提纲（数据结构化，可检查）
    FAILURE_MODES / PYRAMID       五类失效现场与四层测试金字塔
    SIGNED_ZERO_GRAPH             -0.0 破坏性实验的考卷：关掉浮点门卫，
                                  看合法性怎么破洞、位级对照怎么抓住它

压轴三连问的一句话答案（详细论证见演示 [7]～[9]）：
    为什么合法：可观察行为（输出＋副作用打印）不变——三类动作各有一条论证；
    如何测试：  正例（该折的折了）→ 反例（不该动的不动）→ 严格语义对照
                （位级）→ 集成回归（老积木没坏）——四层金字塔；
    何时失效：  规则的适用条件被踩出界——浮点符号零、整数溢出、副作用、
                等价判据过宽、事实过期，五类现场各有门卫。
"""

from __future__ import annotations

import argparse
import math
import re
import struct

PURE_OPS = {"matmul", "add", "relu", "mul"}   # 无副作用算子（Day 20 同款口径）
SIDE_EFFECT_OPS = {"debug"}                   # 副作用算子：执行时打印（可观察）
COMMUTATIVE_OPS = {"add", "mul"}              # 交换律：输入顺序不影响结果

INT_DTYPES = {"i8", "i16", "i32", "i64"}
FLOAT_DTYPES = {"f16", "bf16", "f32", "f64"}
KNOWN_DTYPES = INT_DTYPES | FLOAT_DTYPES

DTYPE_BYTES = {"i8": 1, "i16": 2, "i32": 4, "i64": 8,
               "f16": 2, "bf16": 2, "f32": 4, "f64": 8}   # Week 1 的口径

IDENTITY = {"add": 0, "mul": 1}   # 算子 → 单位元（Day 23）
FLOAT_UNSAFE = {"add"}            # 浮点下默认不安全的规则（-0.0 问题）

EVAL_OPS = {"add", "mul"}         # const-eval 求值的算子（Day 24）
OP_SYMBOL = {"add": "+", "mul": "×"}
OP_FUNCS = {"add": lambda a, b: a + b, "mul": lambda a, b: a * b}

INT_RANGE = {                     # dtype → (min, max)，补码范围（Day 24）
    "i8": (-(2 ** 7), 2 ** 7 - 1),
    "i16": (-(2 ** 15), 2 ** 15 - 1),
    "i32": (-(2 ** 31), 2 ** 31 - 1),
    "i64": (-(2 ** 63), 2 ** 63 - 1),
}
FLOAT_CODES = {"f16": "<e", "f32": "<f", "f64": "<d"}   # bf16 无 struct 码


# ---------- 图：Day 22～25 同款外壳，契约一字未改 ----------

class GraphError(Exception):
    """图不合法，或违反“改图走方法”的契约。"""


class PassFailure(Exception):
    """Pass 主动上报的失败（对应 MLIR 的 failure()）。"""


class Graph:
    """语句序列表示的线性计算图（Day 23 同款契约）。

      * 只读查询（labels / used_at / validate）不改图；
      * 修改必须走 remove_statement / replace_all_uses / rewrite_statement，
        每次修改 epoch + 1 并写改动日志——收敛判断、分析对账都靠它；
      * validate 是 SSA 闸门：唯一定义、使用先于定义。
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
        """把所有读 old 的语句改成读 new（simplify/cse 换边的核心动作）。"""
        rewired = 0
        for stmt in self.statements:
            if old in stmt[2]:
                stmt[2] = [new if u == old else u for u in stmt[2]]
                rewired += 1
        if rewired == 0:
            raise GraphError(f"没有任何语句使用 {old}，无事可换")
        self._commit(f"换边：{rewired} 条语句改读 {new}（原来读 {old}）——位置没变，Use-Def 变了")
        return rewired

    def rewrite_statement(self, index, new_stmt):
        """把第 index 条语句原地改写成 new_stmt——const-eval 变身的核心动作。

        add %d1 变 const 5：结果名不变、使用者一行都不用改；但 defs 表里
        %d1 还指着旧语句——缓存的事实过期了，调用方必须重建（Day 20 铁律）。
        """
        old = self.statements[index]
        self.statements[index] = list(new_stmt)
        self._commit(f"改写 S{index + 1}（{old[0]} {old[1] or ''} → {new_stmt[0]} {new_stmt[1] or ''}）"
                     f"——语句数不变，定义的名字没变")


# ---------- 分析：Day 20 的组件原样搬来 ----------

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
    """分析缓存管理器（Day 20 同款）：epoch 对账，图一变旧结果作废。

    stats 三项：queries（问了几次）、recomputed（真算了几次）、
    invalidated（旧答案作废几次）——“事实过期”的全部账本。
    """

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

    run() 每次调用都新建 AnalysisManager——FixpointRunner 一轮调一次 run，
    上一轮的分析缓存绝无可能漏进下一轮（最朴素的失效策略：跨轮全作废）。
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


# ---------- 工具（Day 23/24/25 同款）----------

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
    """白名单判定：只有声明纯的算子（PURE_OPS＋const）才算无副作用（Day 25）。"""
    return op in PURE_OPS or is_const(op)


def const_value(op, dtype):
    """按 dtype 解析常量数值；类型不合法（或未知 dtype）返回 None。"""
    try:
        text = op.split(" ", 1)[1].strip()
    except IndexError:
        return None
    if dtype in INT_DTYPES:
        return int(text) if re.fullmatch(r"[+-]?\d+", text) else None
    if dtype in FLOAT_DTYPES:
        try:
            return float(text)
        except ValueError:
            return None
    return None


def round_float(value, dtype):
    """把 value 舍入到 dtype 精度（f16/f32/f64）；不支持或无法表示返回 None/inf。"""
    code = FLOAT_CODES.get(dtype)
    if code is None:
        return None
    try:
        return struct.unpack(code, struct.pack(code, value))[0]
    except OverflowError:
        return math.inf if value > 0 else -math.inf


def fmt_const(value, dtype):
    """新常量的文本：整数用 str，浮点用 repr（'inf' 也能被 float() 解析回来）。"""
    if dtype in INT_DTYPES:
        return str(value)
    return repr(value)


# ---------- Day 23 的 Pass：代数化简（原样搬来）----------

class AlgebraicSimplifyPass(Pass):
    """add(x, 0) → x、mul(x, 1) → x——换边＋删除，级联在一趟内完成。

    五道门（Day 23）：纯算子 / 值恰为单位元 / 类型对齐 / shape 对齐 /
    浮点特判（allow_signed_zero_fp 就是第五道门上的钥匙——今天 [8] 要
    亲手转动它，看 -0.0 怎么让“恒等式”破洞）。
    """

    name = "algebraic-simplify"

    def __init__(self, allow_signed_zero_fp=False):
        self.allow_signed_zero_fp = allow_signed_zero_fp
        self.decisions = []

    def run(self, graph, am):
        self.decisions = []
        defs = self._defs(graph)
        i = 0
        while i < len(graph.statements):
            verdict = self._examine(graph, i, defs)
            if verdict is None:            # 不是 add/mul 目标，不进日志
                i += 1
                continue
            kind, other, reason = verdict
            op, res, inputs, info = graph.statements[i]
            if kind == "skip":
                self.decisions.append({"verdict": "skip", "op": op, "res": res, "reason": reason})
                i += 1
                continue
            note = ""
            if res in graph.used_at():
                graph.replace_all_uses(res, other)   # 使用者全部改读另一输入
            else:
                note = "（结果无人使用，无需换边）"
            self.decisions.append({"verdict": "fold", "op": op, "res": res,
                                   "to": other, "reason": reason + note})
            graph.remove_statement(i)
            defs = self._defs(graph)        # 图变了，def 表重建——事实会过期
            # i 不动：下一条语句滑到当前位置，级联在一趟内完成
        return True

    @staticmethod
    def _defs(graph):
        return {stmt[1]: stmt for stmt in graph.statements if stmt[1] is not None}

    def _examine(self, graph, i, defs):
        """检查第 i 条语句：返回 None（非目标）/ ('skip', None, 原因) / ('fold', 替换目标, 原因)。"""
        op, res, inputs, info = graph.statements[i]
        if op not in IDENTITY or res is None:
            return None
        if len(inputs) != 2:
            return ("skip", None, f"输入数量 {len(inputs)} ≠ 2——先不碰")

        shape, dtype = info
        if dtype not in KNOWN_DTYPES:
            return ("skip", None, f"结果 dtype {dtype} 不认识——未知类型一律不碰")

        for k in (0, 1):
            name, other = inputs[k], inputs[1 - k]
            dstmt = defs.get(name)
            if dstmt is None or not is_const(dstmt[0]):
                continue
            cshape, cdtype = dstmt[3]

            if cdtype not in KNOWN_DTYPES:
                return ("skip", None, f"常量 {name} 的 dtype {cdtype} 不认识——未知类型一律不碰")
            val = const_value(dstmt[0], cdtype)
            if val is None:
                return ("skip", None, f"常量 {name}（{dstmt[0]}）的值在 {cdtype} 下不合法——绕开，不碰也不崩")
            if val != IDENTITY[op]:
                continue                    # 值不是单位元，看看另一个输入

            ostmt = defs.get(other)
            if ostmt is None:
                return ("skip", None, f"输入 {other} 没有定义——图有问题，交给 Verifier")
            oshape, odtype = ostmt[3]
            if cdtype != dtype or odtype != dtype:
                return ("skip", None,
                        f"类型提升未建模：另一输入 {odtype}、常量 {cdtype}、结果 {dtype} 三方不一致")

            if cshape != shape or oshape != shape:
                return ("skip", None,
                        f"shape 不一致：{oshape} / {cshape} vs 结果 {shape}——广播是 Day 60 的事")

            if dtype in FLOAT_DTYPES and op in FLOAT_UNSAFE and not self.allow_signed_zero_fp:
                return ("skip", None,
                        f"{dtype} 的 {op}(x, {val}) 不恒等：-0.0 + 0.0 = +0.0，符号会丢"
                        f"（未开 allow_signed_zero_fp）")

            return ("fold", other,
                    f"{dtype} splat {shape}，值 {val} 是 {op} 的单位元，五道门全过")
        return ("skip", None, "没有值为单位元的常量输入")


# ---------- Day 24 的 Pass：常量求值（原样搬来）----------

class ConstEvalPass(Pass):
    """const + const → 新 const——编译期求值，五道门（Day 24）。

    折叠动作是原地改写（rewrite_statement）：add %d1 变身 const 5，名字
    不变、使用者不动、语句数不变。defs 表每次改写后重建——级联靠它完成。
    """

    name = "const-eval"

    def __init__(self):
        self.decisions = []
        self._folded_names = set()

    def run(self, graph, am):
        self.decisions = []
        self._folded_names = set()
        defs = self._defs(graph)
        i = 0
        while i < len(graph.statements):
            verdict = self._examine(graph, i, defs)
            if verdict is None:            # 不是 add/mul 目标，不进日志
                i += 1
                continue
            kind, payload, reason = verdict
            op, res, inputs, info = graph.statements[i]
            if kind == "skip":
                self.decisions.append({"verdict": "skip", "op": op, "res": res, "reason": reason})
                i += 1
                continue
            text = payload                 # 新常量的文本，如 "5"
            self.decisions.append({"verdict": "fold", "op": op, "res": res,
                                   "to": f"const {text}", "reason": reason})
            graph.rewrite_statement(i, (f"const {text}", res, [], info))
            self._folded_names.add(res)
            defs = self._defs(graph)       # 原地改写后 def 表同样过期——重建
            i += 1                         # 语句数不变，前进一格；级联靠 defs 刷新
        return True

    @staticmethod
    def _defs(graph):
        return {stmt[1]: stmt for stmt in graph.statements if stmt[1] is not None}

    def _examine(self, graph, i, defs):
        """检查第 i 条语句：返回 None / ('skip', None, 原因) / ('fold', 常量文本, 原因)。"""
        op, res, inputs, info = graph.statements[i]
        if op not in EVAL_OPS or res is None:
            return None
        if len(inputs) != 2:
            return ("skip", None, f"输入数量 {len(inputs)} ≠ 2——先不碰")

        shape, dtype = info
        if dtype not in KNOWN_DTYPES:
            return ("skip", None, f"结果 dtype {dtype} 不认识——未知类型一律不碰")

        values = []
        for name in inputs:
            dstmt = defs.get(name)
            if dstmt is None:
                return ("skip", None, f"输入 {name} 没有定义——图有问题，交给 Verifier")
            if not is_const(dstmt[0]):
                return ("skip", None,
                        f"输入 {name} 不是编译期常量（{dstmt[0]}）——边界外，留给运行期")
            cshape, cdtype = dstmt[3]
            if cdtype not in KNOWN_DTYPES:
                return ("skip", None, f"常量 {name} 的 dtype {cdtype} 不认识——未知类型一律不碰")
            val = const_value(dstmt[0], cdtype)
            if val is None:
                return ("skip", None,
                        f"常量 {name}（{dstmt[0]}）的值在 {cdtype} 下不合法——绕开，不碰也不崩")
            values.append((name, val, cshape, cdtype))

        (n1, v1, s1, t1), (n2, v2, s2, t2) = values

        if not (t1 == t2 == dtype):
            return ("skip", None,
                    f"类型提升未建模：{t1} / {t2} vs 结果 {dtype} 三方不一致")

        if not (s1 == s2 == shape):
            return ("skip", None,
                    f"shape 不一致：{s1} / {s2} vs 结果 {shape}——广播是 Day 60 的事")
        if shape != ():
            return ("skip", None,
                    f"shape {shape} 是 splat 张量——今天只求值标量（大张量编译期展开是 Day 47 的事）")

        sym = OP_SYMBOL[op]
        if dtype in INT_DTYPES:
            lo, hi = INT_RANGE[dtype]
            for n, v, _, _ in values:
                if not (lo <= v <= hi):
                    return ("skip", None,
                            f"常量 {n} 的值 {v} 超出 {dtype} 范围 [{lo}, {hi}]"
                            f"——写着 {dtype} 却装不下的谎言常量")
            result = OP_FUNCS[op](v1, v2)          # Python int 精确算，无限宽
            if not (lo <= result <= hi):           # 结果可表示
                return ("skip", None,
                        f"结果 {v1} {sym} {v2} = {result} 超出 {dtype} 范围 [{lo}, {hi}]"
                        f"——回绕语义未定义，门卫不猜语义")
            note = f"（级联：{n1} 本趟刚变身常量）" if n1 in self._folded_names else ""
            return ("fold", fmt_const(result, dtype),
                    f"{dtype} 标量，{v1} {sym} {v2} = {result}，精确可表示，原地变身{note}")

        if dtype not in FLOAT_CODES:
            return ("skip", None,
                    f"{dtype} 求值暂不支持：struct 没有对应舍入码（选做挑战：手写 bf16 舍入）")
        a, b = round_float(v1, dtype), round_float(v2, dtype)
        for n, v, r in ((n1, v1, a), (n2, v2, b)):
            if math.isfinite(v) and not math.isfinite(r):
                return ("skip", None,
                        f"常量 {n} 的值 {v} 超出 {dtype} 范围——round 后变 {r}，名不副实的谎言常量")
        exact = OP_FUNCS[op](a, b)                 # f64 域计算
        result = round_float(exact, dtype)         # 结果 round 回 dtype
        if math.isfinite(a) and math.isfinite(b) and not math.isfinite(result):
            return ("skip", None,
                    f"结果 {a} {sym} {b} 在 {dtype} 下溢出为 {result}"
                    f"——浮点溢出语义没写进 IR，不猜（输入本身非有限则允许传播）")
        note = f"（级联：{n1} 本趟刚变身常量）" if n1 in self._folded_names else ""
        return ("fold", fmt_const(result, dtype),
                f"{dtype} 标量，round({v1}) {sym} round({v2}) = {result}，"
                f"round 到 {dtype} 名实相符，原地变身{note}")


# ---------- Day 25 的 Pass：死代码消除（原样搬来）----------

class DcePass(Pass):
    """反向一趟清扫死值：判定表＋使用计数的减法维护（Day 25）。

    三条保留规则：图输出（契约）、副作用节点（打印可观察）、图输入（签名）。
    本 Pass 是管线的清扫车——cse 换边留下的、simplify/const-eval 制造的
    死值，都等它统一收走。
    """

    name = "dce"

    def __init__(self):
        self.decisions = []

    def run(self, graph, am):
        self.decisions = []
        use_count, users = self._use_tables(graph)
        i = len(graph.statements) - 1
        while i >= 0:
            op, res, inputs, info = graph.statements[i]
            kind, reason = self._judge(op, res, use_count, users)
            self.decisions.append({"verdict": kind, "op": op, "res": res or "(output)", "reason": reason})
            if kind == "delete":
                graph.remove_statement(i)     # 走方法：epoch +1，改动进日志
                for u in inputs:              # 减法维护：消费者的死讯通知到生产者
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


# ---------- Day 26 的 Pass：公共子表达式消除（原样搬来）----------

class CsePass(Pass):
    """合并完全相同的纯算子：后来的并入先来的，语句留给 dce 清扫。

    等价的判据是结构键（Day 26 的三要素——结构等价、属性等价、输入顺序）：
      * 算子相同 ＋ 输入相同 ＋ 结果 (shape, dtype) 相同 → 键相同；
      * add/mul 满足交换律：输入排序后进键；matmul/relu 保序；
      * 常量：值 ＋ 类型进键（const 5 i32 ≠ const 5 i64）；
      * 副作用算子（debug）和未知算子不参与合并——门卫不猜语义。
    """

    name = "cse"

    def __init__(self, commutative=True):
        self.commutative = commutative
        self.merges = []

    def run(self, graph, am):
        self.merges = []
        seen = {}                           # 键 → 首个出现者的结果名
        used = graph.used_at()              # 进场快照：谁还有使用者
        for stmt in graph.statements:
            op, res, inputs, info = stmt
            if res is None:                 # output 语句：没有结果，不参与
                continue
            key = self._key(stmt)
            if key is None:                 # 副作用/未知算子/解析不了的常量
                continue
            if key in seen:
                first = seen[key]
                if res in used:             # 有使用者才需要换边；死值归 dce
                    graph.replace_all_uses(res, first)
                    self.merges.append({"later": res, "first": first, "op": op})
            else:
                seen[key] = res
        return True

    def _key(self, stmt):
        op, res, inputs, info = stmt
        shape, dtype = info
        if is_const(op):
            val = const_value(op, dtype)
            if val is None:
                return None                 # 值解析不了的常量：不合并，最安全
            return ("const", val, dtype, shape)
        if op in SIDE_EFFECT_OPS or op not in PURE_OPS:
            return None
        if self.commutative and op in COMMUTATIVE_OPS:
            ins = tuple(sorted(inputs))     # 交换律：顺序无关
        else:
            ins = tuple(inputs)             # matmul 等：顺序就是语义
        return (op, ins, dtype, shape)


# ---------- Day 27 的主角：把管线跑到不动点（原样搬来）----------

class FixpointRunner:
    """把一条 Pass 管线反复跑到不动点。

    一轮 = 按给定顺序完整跑一遍管线；轮与轮之间唯一的通信介质是图本身。
    收敛判据：某一轮从头到尾 epoch 零改动。max_rounds 是保险丝。
    """

    def __init__(self, passes, max_rounds=10, title="fixpoint"):
        self.passes = list(passes)
        self.max_rounds = max_rounds
        self.title = title
        self.rounds = []
        self.converged = False

    def run(self, graph):
        self.rounds, self.converged = [], False
        pm = PassManager(print_ir="none", verbose=False, title=self.title)
        pm.add(*self.passes)                # 每轮 run 都新建 AnalysisManager
        for r in range(1, self.max_rounds + 1):
            epoch_before = graph.epoch
            stmts_before = len(graph.statements)
            ok = pm.run(graph)
            if ok is not True:              # 管线失败：原样上抛
                return False
            changes = graph.epoch - epoch_before
            self.rounds.append({"round": r, "changes": changes,
                                "before": stmts_before, "after": len(graph.statements),
                                "per_pass": [(e["name"], e["changes"]) for e in pm.log],
                                "ir": ir_dump(graph)})
            if changes == 0:
                self.converged = True       # 整轮零改动：不动点
                return True
        return True                         # 跑满上限——调用方看 self.converged

    def total_changes(self):
        return sum(r["changes"] for r in self.rounds)

    def round_table(self):
        """轮次表：每轮的改动数、语句数和各 Pass 的动作量。"""
        lines = [f"  {self.title}：{' → '.join(p.name for p in self.passes)}"]
        for r in self.rounds:
            who = "  ".join(f"{name}×{n}" for name, n in r["per_pass"] if n > 0) or "四个 Pass 全部空手而归"
            mark = "  ← 收敛：整轮 epoch 零改动" if r["changes"] == 0 else ""
            lines.append(f"  第 {r['round']} 轮：改动 {r['changes']:>2}，语句 {r['before']} → {r['after']}"
                         f"（{who}）{mark}")
        if not self.converged:
            lines.append(f"  *** 跑满 {self.max_rounds} 轮仍未收敛——保险丝熔断，图停在 {self.rounds[-1]['after']} 条")
        return "\n".join(lines)


# ---------- 语义对照（Day 25 原样搬来 ＋ 今天的严格版）----------

def interp(graph, feed):
    """最小解释器：按语句顺序执行图，返回（输出值列表， debug 打印行列表）。

    “可观察行为”的模型就这两样：图输出 ＋ debug 打印。优化前后各跑一遍，
    两者完全一致才叫语义不变。
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
            env[res] = v                    # debug 值穿透：结果就是输入
        elif op == "output":
            outputs = [env[u] for u in uses]
        else:
            raise GraphError(f"解释器不认识算子 {op!r}")
    return outputs, debug_lines


def same_behavior(g1, g2, feed):
    """宽松语义对照：输出用 ==、打印逐行比（Day 25 同款）。"""
    o1, d1 = interp(g1, feed)
    o2, d2 = interp(g2, feed)
    ok = (o1 == o2 and d1 == d2)
    return ok, (o1, d1), (o2, d2)


def f64_bits(value):
    """浮点值的位级表示（f64 位模式，16 个十六进制字符，大端显示）。

    用大端（">d"）是因为它和手写十六进制一致：-0.0 的符号位在最高位，
    显示为 8000000000000000；+0.0 显示为 0000000000000000。
    """
    return struct.pack(">d", value).hex()


def strict_key(value):
    """严格比较键：浮点按位模式、整数按值。

    为什么浮点要看位级：Python（IEEE 754）认为 0.0 == -0.0 为 True，
    但两者的符号位不同——签名零（signed zero）是可观察差异。宽松的 ==
    会放过它，位级不会。
    """
    if isinstance(value, float):
        return ("f", f64_bits(value))
    return ("i", value)


def strict_same_behavior(g1, g2, feed):
    """严格语义对照：输出按 strict_key 逐项比、打印逐行比。

    返回 (严格结论, 宽松结论, 原图结果, 改写图结果)。两个结论都给，
    是为了让“宽松对照放过 -0.0”这件事可演示、可自测。
    """
    o1, d1 = interp(g1, feed)
    o2, d2 = interp(g2, feed)
    strict = ([strict_key(v) for v in o1] == [strict_key(v) for v in o2]) and d1 == d2
    loose = (o1 == o2 and d1 == d2)
    return strict, loose, (o1, d1), (o2, d2)


# ---------- 今天的四层账本 ----------

def tensor_bill(graph):
    """数据底座账单：每个值的类型、元素数、字节数（Week 1 的 TensorDesc 视角）。

    返回 (行列表, 朴素分配总字节)。朴素分配 = 每个值独占一块
    （Day 19 的口径；真实的复用要等 Day 99–100 的内存规划）。
    """
    rows, total = [], 0
    for op, res, uses, info in graph.statements:
        if res is None:
            continue
        shape, dtype = info
        n = 1
        for d in shape:
            n *= d
        b = n * DTYPE_BYTES[dtype]
        total += b
        rows.append((res, fmt_type(info), n, b))
    return rows, total


def use_def_rows(graph):
    """表达层账本：每个值的定义位置、使用位置、使用次数（Day 17/19 的视角）。"""
    used = graph.used_at()
    rows = []
    for i, (op, res, uses, info) in enumerate(graph.statements):
        if res is None:
            continue
        pos = used.get(res, [])
        rows.append((res, op, i + 1, [f"S{p + 1}" for p in pos], len(pos)))
    return rows


# ---------- 今天的讲解提纲与三连问材料 ----------

# 15 分钟讲解的六站路线：站名 / 分钟 / 必讲点 / 卡壳回看
TALK_OUTLINE = [
    ("第①站 数据底座", 2, "Tensor 元信息：shape／dtype／字节——每条语句自带一份 TensorDesc", "Day 4–6"),
    ("第②站 表达层", 3, "图 IR：SSA 唯一定义、Use-Def 双向账本、Verifier 闸门", "Day 8–14、17"),
    ("第③站 事实层", 2, "分析只读＋epoch 对账：死值名单、使用位置——分析报事实，决策靠规则", "Day 19–20"),
    ("第④站 变换层", 4, "四个 Pass＝三类动作（换边／变身／删除）；五道门；跑到不动点", "Day 22–27"),
    ("第⑤站 三连问", 3, "为什么合法（可观察行为不变）／如何测试（四层金字塔）／何时失效（五类现场）", "今天 [7]–[9]"),
    ("第⑥站 行李清单", 1, "讲不清楚的地方＝第二阶段（MLIR）要带走的行李", "Day 29 起"),
]

# 三类动作 × 语义保持论证（三连问①的材料）
ACTION_TABLE = [
    ("换边", "algebraic-simplify / cse",
     "使用者改读等价的另一个值：add(x,0)→读 x、重复计算→读首次出现者。"
     "Use-Def 重定向，不新增也不遗漏任何计算"),
    ("变身", "const-eval",
     "add(const,const)→const 结果：五道门保证编译期求值＝运行期求值"
     "（类型／shape／溢出／精度全对齐，原地改写，名字不变）"),
    ("删除", "dce",
     "结果无人使用＋算子纯：不进输出、不打印——删了等于从没执行过"
     "（副作用节点和图输出永远不删）"),
]

# 五类失效现场（三连问②的材料）：名称 / 症状 / 门卫 / 出处
FAILURE_MODES = [
    ("浮点符号零", "add(x, 0)→x 在浮点下不恒等：-0.0 + 0.0 = +0.0，符号位会丢",
     "Day 23 门⑤（allow_signed_zero_fp 默认关）", "今天 [8] 现场演示"),
    ("整数溢出", "i32 下 2147483647+1 结果不可表示，回绕语义未定义",
     "Day 24 溢出门（结果可表示才折）", "self-test C 组"),
    ("副作用", "debug 删了／合了都会少打印一行，可观察行为变了",
     "Day 25 判定表＋Day 26 结构键排除", "self-test C 组"),
    ("等价判据过宽", "matmul 保序、常量类型进键、交换律只给 add/mul——判据宽一点就改错图",
     "Day 26 结构键（值＋类型＋顺序）", "self-test D 组"),
    ("事实过期", "缓存的分析答案随图改动作废；单轮管线会错过本轮中段才成形的机会",
     "Day 20 epoch 对账＋Day 27 FixpointRunner", "self-test E 组"),
]

# 四层测试金字塔（三连问③的材料）：层名 / 测什么 / 今天的活样本
PYRAMID = [
    ("L1 正例", "该折的折了、结果精确", "add(x,0)→x、2+3→const 5（毕业图 4 类冗余全蒸发）"),
    ("L2 反例", "不该动的坚决不动", "debug／matmul 保序／溢出／类型不匹配，合并与折叠都是 0 次"),
    ("L3 严格语义对照", "输出＋打印，浮点看位级", "-0.0 教训：== 放过符号位，位级对照抓住它（[8]）"),
    ("L4 集成回归", "老积木没被新组装碰坏", "Day 27 的 47 项＋今天新增 33 项，全部通过"),
]

# 行李清单：讲不清楚的地方（复盘要诚实，这正是第二阶段的输入）
UNCLEAR_LIST = [
    ("支配边界（dominance frontier）怎么系统性地决定 φ 插入位置", "Day 21 复盘遗留，Day 31 讲 Region／Block 时补"),
    ("bf16 的常量求值（struct 没有对应舍入码）", "Day 24 选做挑战，第二阶段做数值实验时补"),
    ("order D 顺序实验与随机图收敛性扫描还没跑", "Day 27 练习，学 MLIR Canonicalization 前补"),
]


# ---------- 毕业考卷与实验用图 ----------

# 第一阶段的毕业考卷：Day 27 的 18 条收官图原样搬来（四类冗余＋副作用＋迟到的 0）。
GRADUATION_GRAPH = [
    ("input",    "%x",   [],               ((), "i32")),
    ("const 0",  "%c0",  [],               ((), "i32")),
    ("const 1",  "%c1",  [],               ((), "i32")),
    ("const 2",  "%c2",  [],               ((), "i32")),
    ("const 3",  "%c3",  [],               ((), "i32")),
    ("const -2", "%cm2", [],               ((), "i32")),
    ("add",      "%a1",  ["%x", "%c0"],    ((), "i32")),   # 恒等冗余：add(x,0)
    ("relu",     "%z",   ["%a1"],          ((), "i32")),
    ("add",      "%t2",  ["%c2", "%c3"],   ((), "i32")),   # 常量计算：2+3
    ("add",      "%w",   ["%c2", "%cm2"],  ((), "i32")),   # 2+(-2) → 0
    ("add",      "%u",   ["%x", "%w"],     ((), "i32")),   # 迟到的 0
    ("add",      "%k1",  ["%x", "%c1"],    ((), "i32")),
    ("relu",     "%k2",  ["%k1"],          ((), "i32")),
    ("debug",    "%p",   ["%k2"],          ((), "i32")),   # 副作用：必须活
    ("add",      "%y",   ["%c1", "%x"],    ((), "i32")),   # 交换律重复
    ("relu",     "%q1",  ["%c3"],          ((), "i32")),   # 死链头
    ("relu",     "%q2",  ["%q1"],          ((), "i32")),   # 死链尾
    ("output",   None,   ["%y", "%z", "%u", "%t2"], None),
]

# -0.0 破坏性实验的考卷：add(x, 0.0) 在 f32 下恒等吗？
SIGNED_ZERO_GRAPH = [
    ("input",     "%x",  [],             ((), "f32")),
    ("const 0.0", "%c0", [],             ((), "f32")),
    ("add",       "%d",  ["%x", "%c0"],  ((), "f32")),
    ("output",    None,  ["%d"],         None),
]

# 分析失效实验的图：const-eval 变身 %d 之后，%c2/%c3 变成新的死值（Day 27 同款）
INVAL_GRAPH = [
    ("input",    "%x",  [],              ((), "i32")),
    ("const 2",  "%c2", [],              ((), "i32")),
    ("const 3",  "%c3", [],              ((), "i32")),
    ("add",      "%d",  ["%c2", "%c3"],  ((), "i32")),   # const-eval → const 5
    ("relu",     "%e",  ["%d"],          ((), "i32")),   # 死值：无人使用
    ("output",   None,  ["%x"],          None),
]

# 回归用的小图（Day 26/27 同款）
CSE_COMMUTED_GRAPH = [
    ("input",   "%x",   [],              ((), "i32")),
    ("const 1", "%c1",  [],              ((), "i32")),
    ("add",     "%k1",  ["%x", "%c1"],   ((), "i32")),
    ("add",     "%y",   ["%c1", "%x"],   ((), "i32")),   # 交换律重复
    ("output",  None,   ["%k1", "%y"],   None),
]

CSE_DEBUG_PAIR_GRAPH = [
    ("input",   "%x",   [],              ((), "i32")),
    ("relu",    "%k2",  ["%x"],          ((), "i32")),
    ("debug",   "%p1",  ["%k2"],         ((), "i32")),   # 两次打印：合并会少一行
    ("debug",   "%p2",  ["%k2"],         ((), "i32")),
    ("output",  None,   ["%x"],          None),
]

CSE_MATMUL_GRAPH = [
    ("input",   "%a",   [],              ((2, 2), "i32")),
    ("input",   "%b",   [],              ((2, 2), "i32")),
    ("matmul",  "%m1",  ["%a", "%b"],    ((2, 2), "i32")),
    ("matmul",  "%m2",  ["%b", "%a"],    ((2, 2), "i32")),   # 顺序就是语义
    ("output",  None,   ["%m1", "%m2"],  None),
]

CSE_CONST_DTYPE_GRAPH = [
    ("const 5", "%c32", [],              ((), "i32")),
    ("const 5", "%c64", [],              ((), "i64")),   # 同值不同型：不等价
    ("add",     "%d32", ["%c32", "%c32"], ((), "i32")),
    ("add",     "%d64", ["%c64", "%c64"], ((), "i64")),
    ("output",  None,   ["%d32", "%d64"], None),
]


ORDER_A = [AlgebraicSimplifyPass(), ConstEvalPass(), CsePass(), DcePass()]   # 常规序：清扫车压轴


def fresh_order(order):
    """每个实验用独立的 Pass 实例——决策日志互不污染。"""
    return [type(p)() for p in order]


# ---------- 演示 ----------

def demo():
    print("== [1] 15 分钟讲解提纲：六站路线（今天实践的主线） ==")
    total = 0
    for name, minutes, points, back in TALK_OUTLINE:
        print(f"  {name}（{minutes} 分钟）：{points}")
        print(f"      卡壳回看：{back}")
        total += minutes
    print(f"  合计 {total} 分钟。规则：脱稿讲、对着墙或录音讲；讲不顺的地方")
    print("  当场记下来——那是第二阶段（MLIR）要带走的行李（清单见 [9]）。")
    print("  下面 [3]～[6] 是前四站的机器佐证（讲解时照着这张图讲），")
    print("  [7]～[9] 是第⑤站三连问的证据。")

    g0 = Graph(GRADUATION_GRAPH)

    print("\n== [2] 毕业考卷：18 条图 ＋ 基线语义 ==")
    print(ir_dump(g0))
    base_out, base_dbg = interp(g0, {"%x": 7})
    print(f"语义基线（喂 %x=7）：输出 {base_out}，打印 {base_dbg}")
    print("四类冗余齐聚（恒等／常量计算／交换律重复／死链）＋ 副作用 %p ＋ 迟到的 0——")
    print("Day 27 用它验收了不动点，今天用它把四层各看一遍。")

    print("\n== [3] 第①站 数据底座：每条语句自带一份 TensorDesc ==")
    rows, total_bytes = tensor_bill(g0)
    for res, ty, n, b in rows:
        print(f"    {res:<6}{ty:<14}{n} 元素 × 4B = {b}B")
    print(f"  朴素分配（每值一块）：{len(rows)} 个值，合计 {total_bytes}B")
    print("  Week 1 的 (shape, stride, dtype) 没有白学——它就活在每条语句的 info 里；")
    print("  优化要省的内存最后都落在这张账单上（[6] 看它怎么缩水）。")

    print("\n== [4] 第②站 表达层：SSA ＋ Use-Def ＋ Verifier ==")
    print(f"  SSA 闸门：validate() = {g0.validate()}")
    print(f"    {'值':<6}{'定义':<7}{'使用位置':<30}{'次数':<5}状态")
    for res, op, defpos, uses, n in use_def_rows(g0):
        status = "活" if n else "死（无人使用）"
        print(f"    {res:<6}S{defpos:<6}{('、'.join(uses) or '（无）'):<30}{n:<5}{status}")
    print("  讲三个点：%x 被 4 处使用（S7/S11/S12/S15——它是全图最忙的值）；")
    print("  %q1 只有 S17 一个使用者（死链要两刀才清完：%q2 死了 %q1 才死）；")
    print("  %p 无人使用——但它是 debug，第③站的分析只会“报告”，第④站的 dce 才“决策”。")

    print("\n== [5] 第③站 事实层：分析只读 ＋ epoch 对账 ==")
    am = AnalysisManager(g0)
    dead = am.get(UnusedAnalysis())
    print(f"  unused 分析的死值名单：{sorted(dead.dead)}")
    print(f"  stats = {am.stats}（问 1 次、真算 1 次、作废 0 次——图还没被改过）")
    print("  注意 %p 在名单里（无人读它），但 dce 的判定表会保留它——分析只报事实，")
    print("  删不删由变换层的规则决定（副作用规则）。这就是 Day 20 定下的分工：")
    print("  分析不改图（epoch 不动），变换不自建缓存就自建事实。")

    print("\n== [6] 第④站 变换层：四个 Pass 跑到不动点 ==")
    g5 = Graph(GRADUATION_GRAPH)
    runner = FixpointRunner(fresh_order(ORDER_A), max_rounds=10, title="order A")
    ok = runner.run(g5)
    print(runner.round_table())
    print(f"run() 返回 {ok}；converged = {runner.converged}，总改动 {runner.total_changes()} 次")
    print(ir_dump(g5))
    rows5, total5 = tensor_bill(g5)
    print(f"  优化后账单：{len(rows5)} 个值，合计 {total5}B（{total_bytes}B → {total5}B）")
    print("  output 改读 [%k1, %z, %x, %t2]——%u 换边到 %x、%y 并入 %k1，")
    print("  死链／死常量全被 dce 扫走，%p 因副作用幸存。")

    print("\n== [7] 三连问① 为什么合法：三类动作各有一条论证 ==")
    print("  判据：可观察行为不变——图输出 ＋ debug 打印，两样都不变才叫合法。")
    for action, who, arg in ACTION_TABLE:
        print(f"    {action}（{who}）：{arg}")
    print("  机器验证（same_behavior，喂 %x=-3/0/7 三组）：")
    all_green = True
    for feed in (-3, 0, 7):
        ok_s, (o1, d1), (o2, d2) = same_behavior(Graph(GRADUATION_GRAPH), g5, {"%x": feed})
        all_green = all_green and ok_s
        print(f"    喂 %x={feed}：输出 {o1} == {o2}，打印 {d1} == {d2} → {'一致 ✓' if ok_s else '不一致 ✗'}")
    print(f"  三组全绿：{all_green}——论证（人）＋对照（机器）双保险。")

    print("\n== [8] 三连问② 何时失效：亲手关掉浮点门卫 ==")
    print("  考卷 SIGNED_ZERO_GRAPH（f32）：add(x, 0.0) 在浮点下恒等吗？")
    g_on = Graph(SIGNED_ZERO_GRAPH)
    print(ir_dump(g_on))
    p_on = AlgebraicSimplifyPass()
    PassManager(print_ir="none", verbose=False).add(p_on).run(g_on)
    print("  门卫开着（默认，Day 23 的第五道门）：")
    for d_ in p_on.decisions:
        print(f"    判定 {d_['verdict']}：{d_['reason']}")
    g_off = Graph(SIGNED_ZERO_GRAPH)
    p_off = AlgebraicSimplifyPass(allow_signed_zero_fp=True)
    PassManager(print_ir="none", verbose=False).add(p_off).run(g_off)
    print("  门卫关掉（allow_signed_zero_fp=True）：")
    for d_ in p_off.decisions:
        print(f"    判定 {d_['verdict']}：add(%x, %c0) → {d_['to']}（{d_['reason']}）")
    print(ir_dump(g_off))
    feed = {"%x": -0.0}
    strict, loose, (o1, d1), (o2, d2) = strict_same_behavior(
        Graph(SIGNED_ZERO_GRAPH), g_off, feed)
    print("  喂 %x = -0.0（IEEE 754：-0.0 + 0.0 = +0.0，符号位丢失）：")
    print(f"    原图（不折）：      %d = -0.0 + 0.0 = {o1[0]:+}，位级 {f64_bits(o1[0])}")
    print(f"    改写图（折成 %x）：output = {o2[0]:+}，位级 {f64_bits(o2[0])}")
    print(f"    严格对照（位级）：{'一致 ✓' if strict else '不一致 ✗——符号位丢了，这次优化非法'}")
    print(f"    宽松对照（==）：{o1[0]} == {o2[0]} → {o1[0] == o2[0]}——放过了它！（对照器自己的盲区）")
    print("  再补两组对照（失败恰好只发生在 -0.0 这个点上）：")
    for fv in (0.0, 5.0):
        s2, _, (a1, _), (a2, _) = strict_same_behavior(
            Graph(SIGNED_ZERO_GRAPH), g_off, {"%x": fv})
        print(f"    喂 %x={fv:+}：原图 {a1[0]:+} vs 改写 {a2[0]:+}，严格对照{'一致 ✓' if s2 else '不一致 ✗'}")
    print("  失效不是“优化错了”，是“规则的适用条件被踩出界”。五类现场：")
    for i, (name, symptom, guard, src) in enumerate(FAILURE_MODES, 1):
        print(f"    {i}. {name}：{symptom}")
        print(f"       门卫：{guard}（{src}）")

    print("\n== [9] 三连问③ 如何测试：四层金字塔 ＋ 行李清单 ==")
    print("  金字塔（自下而上，每层防一种事故）：")
    for name, what, note in PYRAMID:
        print(f"    {name}：{what}")
        print(f"      活样本：{note}")
    print("  三个活样本的真实运行：")
    gd = Graph(CSE_DEBUG_PAIR_GRAPH)
    pd_ = CsePass()
    PassManager(print_ir="none", verbose=False).add(pd_).run(gd)
    print(f"    L2 反例：两个 debug(%k2) → cse 合并 {len(pd_.merges)} 次（副作用不动）")
    gi = Graph([("const 2147483647", "%a", [], ((), "i32")),
                ("const 1", "%b", [], ((), "i32")),
                ("add", "%d", ["%a", "%b"], ((), "i32")),
                ("output", None, ["%d"], None)])
    pi = ConstEvalPass()
    PassManager(print_ir="none", verbose=False).add(pi).run(gi)
    verdict = "拒折" if gi.statements[2][0] == "add" else "折了"
    print(f"    L2 反例：i32 2147483647+1 → const-eval {verdict}（溢出门）")
    gp = Graph([("input", "%x", [], ((), "i32")),
                ("const 0", "%z", [], ((), "i32")),
                ("add", "%d", ["%x", "%z"], ((), "i32")),
                ("output", None, ["%d"], None)])
    pp = AlgebraicSimplifyPass()
    PassManager(print_ir="none", verbose=False).add(pp).run(gp)
    print(f"    L1 正例：i32 add(x,0) → output 改读 %x：{gp.statements[-1][2] == ['%x']}（该折的折了）")
    print("  完整清单：python3 week4_review.py --self-test——今天 33 项（C 组 7 项")
    print("  全部对着五类失效现场）；连同 Day 27 的 47 项，第一阶段测试收官。")
    print("\n  讲解第⑥站 行李清单（讲不清楚的地方，第二阶段带走）：")
    for item, where in UNCLEAR_LIST:
        print(f"    · {item}（{where}）")
    print("\n  一页复盘速览（完整版见教程第 8 节）：")
    print("  本周目标：四个优化 Pass＋组合到不动点，完成第一阶段集成")
    print("  最重要的技术问题：一个优化 Pass 为什么合法、如何测试、何时失效")
    print("  答案：合法＝可观察行为不变（三类动作各有论证）；测试＝四层金字塔；")
    print("        失效＝适用条件被踩出界（五类现场，各有门卫）")
    print("  验证：毕业图 18 → 8 条（3 轮 13/3/0）；68B → 28B；语义对照三组全绿；")
    print("        47 ＋ 33 项测试通过")
    return 0


# ---------- 自测：第 4 周复盘 ----------

def self_test():
    results = []

    def check(name, cond):
        results.append((name, bool(cond)))
        print(f"  {'✓' if cond else '✗'} {name}")

    print("== 自测：第 4 周复盘（四层串联 ＋ 三连问 ＋ 毕业考卷） ==")

    # A. 四层串联（数据底座 → 表达层 → 事实层 → 变换层）
    g0 = Graph(GRADUATION_GRAPH)
    rows, total = tensor_bill(g0)
    check("A：数据底座——毕业图 17 个值、全部 tensor<i32> 标量、朴素分配 68B",
          len(rows) == 17 and total == 68 and all(t == "tensor<i32>" for _, t, _, _ in rows))
    ud = {r[0]: r for r in use_def_rows(g0)}
    check("A：Use-Def——%x 被 4 处使用（S7/S11/S12/S15，全图最忙的值）",
          ud["%x"][4] == 4 and ud["%x"][3] == ["S7", "S11", "S12", "S15"])
    check("A：Use-Def——%q1 只有 S17 一个使用者（死链要两刀才清完）",
          ud["%q1"][3] == ["S17"] and ud["%q1"][4] == 1)
    check("A：Use-Def——%p 无人使用（它有副作用，dce 的判定表要保留它）",
          ud["%p"][4] == 0)
    am = AnalysisManager(g0)
    dead0 = am.get(UnusedAnalysis())
    check("A：事实层——unused 名单 = {%p, %q2}（%q1 此刻还有使用者）",
          set(dead0.dead) == {"%p", "%q2"})
    check("A：事实层只读——分析之后 epoch 仍是 0、stats 1/1/0",
          g0.epoch == 0 and am.stats == {"queries": 1, "recomputed": 1, "invalidated": 0})
    gA = Graph(GRADUATION_GRAPH)
    rA = FixpointRunner(fresh_order(ORDER_A), max_rounds=10, title="A")
    check("A：变换层——order A 收敛：3 轮（改动 13/3/0），18 → 8 条",
          rA.run(gA) is True and rA.converged and len(rA.rounds) == 3
          and [r["changes"] for r in rA.rounds] == [13, 3, 0] and len(gA.statements) == 8)
    rowsA, totalA = tensor_bill(gA)
    check("A：优化后账单——7 个值、28B（68B → 28B）",
          len(rowsA) == 7 and totalA == 28)
    check("A：优化后 output 改读 [%k1, %z, %x, %t2]（换边的结果）",
          gA.statements[-1][2] == ["%k1", "%z", "%x", "%t2"])
    check("A：优化后图仍过 SSA 闸门（validate）", gA.validate() is True)

    # B. 三连问①：为什么合法（三类动作 × 语义保持）
    g = Graph([("input", "%x", [], ((), "i32")),
               ("const 0", "%z", [], ((), "i32")),
               ("add", "%d", ["%x", "%z"], ((), "i32")),
               ("output", None, ["%d"], None)])
    p = AlgebraicSimplifyPass()
    PassManager(print_ir="none", verbose=False).add(p).run(g)
    check("B：simplify 的动作＝换边＋删除（output 改读 %x，%d 消失）",
          g.statements[-1][2] == ["%x"] and len(g.statements) == 3
          and any(d["verdict"] == "fold" and d["to"] == "%x" for d in p.decisions))
    g = Graph([("const 2", "%a", [], ((), "i32")),
               ("const 3", "%b", [], ((), "i32")),
               ("add", "%d", ["%a", "%b"], ((), "i32")),
               ("output", None, ["%d"], None)])
    n_before = len(g.statements)
    p = ConstEvalPass()
    PassManager(print_ir="none", verbose=False).add(p).run(g)
    check("B：const-eval 的动作＝原地变身（add → const 5，语句数不变）",
          g.statements[2][0] == "const 5" and len(g.statements) == n_before)
    g = Graph(CSE_COMMUTED_GRAPH)
    p = CsePass()
    PassManager(print_ir="none", verbose=False).add(p).run(g)
    check("B：cse 的动作＝只换边（%y 并入 %k1，语句留给 dce 清扫）",
          len(p.merges) == 1 and p.merges[0] == {"later": "%y", "first": "%k1", "op": "add"}
          and any(s[1] == "%y" for s in g.statements))
    gd = Graph(GRADUATION_GRAPH)
    pd = DcePass()
    PassManager(print_ir="none", verbose=False).add(pd).run(gd)
    kept = [s[1] for s in gd.statements]
    check("B：dce 判定表——%p 无人使用仍保留（副作用），死链 %q1/%q2 扫走",
          "%p" in kept and "%q1" not in kept and "%q2" not in kept)
    all_green = True
    for feed in (-3, 0, 7):
        ok_s, _, _ = same_behavior(Graph(GRADUATION_GRAPH), gA, {"%x": feed})
        all_green = all_green and ok_s
    check("B：语义对照——三组喂入（%x=-3/0/7）输出＋打印全绿", all_green)

    # C. 三连问②：何时失效（-0.0 现场 ＋ 溢出 ＋ 副作用）
    g_on = Graph(SIGNED_ZERO_GRAPH)
    p_on = AlgebraicSimplifyPass()
    PassManager(print_ir="none", verbose=False).add(p_on).run(g_on)
    check("C：门卫开着——f32 的 add(x, 0.0) 被 skip（理由点名 -0.0），图原样 4 条",
          len(p_on.decisions) == 1 and p_on.decisions[0]["verdict"] == "skip"
          and "-0.0" in p_on.decisions[0]["reason"] and len(g_on.statements) == 4)
    g_off = Graph(SIGNED_ZERO_GRAPH)
    p_off = AlgebraicSimplifyPass(allow_signed_zero_fp=True)
    PassManager(print_ir="none", verbose=False).add(p_off).run(g_off)
    check("C：门卫关掉——折成 %x（output 直读 %x，%d 消失）",
          g_off.statements[-1][2] == ["%x"] and len(g_off.statements) == 3)
    strict, loose, (o1, d1), (o2, d2) = strict_same_behavior(
        Graph(SIGNED_ZERO_GRAPH), g_off, {"%x": -0.0})
    check("C：喂 %x=-0.0——原图输出 +0.0（-0.0+0.0=+0.0），改写图输出 -0.0",
          o1 == [0.0] and o2 == [-0.0])
    check("C：位级对照抓住差异（0x0000000000000000 ≠ 0x8000000000000000）",
          not strict and f64_bits(o1[0]) == "0" * 16 and f64_bits(o2[0]) == "8" + "0" * 15)
    check("C：宽松 == 放过差异（0.0 == -0.0 为 True）——对照器自己的盲区",
          loose and math.copysign(1, o1[0]) != math.copysign(1, o2[0]))
    g = Graph([("const 2147483647", "%a", [], ((), "i32")),
               ("const 1", "%b", [], ((), "i32")),
               ("add", "%d", ["%a", "%b"], ((), "i32")),
               ("output", None, ["%d"], None)])
    p = ConstEvalPass()
    PassManager(print_ir="none", verbose=False).add(p).run(g)
    check("C：整数溢出——i32 2147483647+1 拒折（回绕语义未定义，门卫不猜）",
          g.statements[2][0] == "add" and any(d["verdict"] == "skip" for d in p.decisions))
    g = Graph(CSE_DEBUG_PAIR_GRAPH)
    p = CsePass()
    PassManager(print_ir="none", verbose=False).add(p).run(g)
    check("C：副作用——两个 debug(%k2) 合并 0 次（合并会少打印一行）",
          len(p.merges) == 0)

    # D. 三连问③：如何测试（金字塔的活样本）
    g = Graph(CSE_MATMUL_GRAPH)
    p = CsePass()
    PassManager(print_ir="none", verbose=False).add(p).run(g)
    check("D：反例——matmul(%a,%b) 与 matmul(%b,%a) 合并 0 次（顺序就是语义）",
          len(p.merges) == 0)
    g = Graph(CSE_CONST_DTYPE_GRAPH)
    p = CsePass()
    PassManager(print_ir="none", verbose=False).add(p).run(g)
    check("D：反例——const 5 i32 与 const 5 i64 合并 0 次（类型进键）",
          len(p.merges) == 0)
    namesA = [s[1] for s in gA.statements]
    check("D：正例——毕业图 4 类冗余全部蒸发（%a1 %w %u %y %q1 %q2 都不在）",
          not any(n in namesA for n in ["%a1", "%w", "%u", "%y", "%q1", "%q2"]))
    _, dbg_final = interp(gA, {"%x": 7})
    check("D：副作用打印幸存且不变（[debug] %p(%k2) = 8）",
          dbg_final == ["[debug] %p(%k2) = 8"])

    # E. 事实过期（第五类失效现场的账本）
    g = Graph(INVAL_GRAPH)
    am = AnalysisManager(g)
    d1 = am.get(UnusedAnalysis())
    ConstEvalPass().run(g, am)
    d2 = am.get(UnusedAnalysis())
    check("E：事实过期——stats 1/1/0 → 2/2/1（invalidated +1，epoch 对账）",
          am.stats == {"queries": 2, "recomputed": 2, "invalidated": 1})
    check("E：死值名单随图变化（{%e} → {%c2, %c3, %e}）",
          set(d1.dead) == {"%e"} and set(d2.dead) == {"%c2", "%c3", "%e"})

    # F. 讲解提纲与行李清单
    check("F：六站提纲齐全，总时长恰为 15 分钟",
          len(TALK_OUTLINE) == 6 and abs(sum(t[1] for t in TALK_OUTLINE) - 15.0) < 1e-9)
    check("F：每站都标注了卡壳回看的出处（衔接前几周）",
          all(t[3].startswith(("Day", "今天")) for t in TALK_OUTLINE))
    check("F：行李清单非空——复盘要诚实记录讲不清楚的地方",
          len(UNCLEAR_LIST) >= 3 and all(where for _, where in UNCLEAR_LIST))

    # G. 收官
    ok_strict, _, _, _ = strict_same_behavior(Graph(GRADUATION_GRAPH), gA, {"%x": 7})
    check("G：严格对照在整数图上不误报（毕业图喂 %x=7 仍判一致）", ok_strict)
    check("G：五类失效现场名单完整（每类带症状、门卫和出处）",
          len(FAILURE_MODES) == 5 and all(len(m) == 4 and all(m) for m in FAILURE_MODES))

    passed = sum(1 for _, ok in results if ok)
    print(f"\n{passed}/{len(results)} 项通过")
    return 0 if passed == len(results) else 1


def main():
    ap = argparse.ArgumentParser(description="第 28 天演练场：第 4 周复盘与第一阶段收官")
    ap.add_argument("--self-test", action="store_true", help="运行复盘测试")
    args = ap.parse_args()
    return self_test() if args.self_test else demo()


if __name__ == "__main__":
    raise SystemExit(main())
