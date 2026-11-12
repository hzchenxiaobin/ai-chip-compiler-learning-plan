#!/usr/bin/env python3
"""第 27 天演练场：Pass 组合与第一阶段集成验收——把四个 Pass 排成管线，跑到不动点。

用法：
    python3 pipeline.py               # 演示主流程：贯穿图、一轮不够、不动点、顺序实验、分析失效
    python3 pipeline.py --self-test   # 运行第一阶段集成测试，全部通过退出码 0

前四天各交付了一块积木，今天把它们搭成一台完整的优化器：

    Day 22  PassManager        调度台：顺序执行、逐 Pass 验证、epoch 记账
    Day 23  algebraic-simplify  add(x,0) → x、mul(x,1) → x（换边＋删除）
    Day 24  const-eval          const+const → 新 const（原地变身，五道门）
    Day 25  dce                 反向一趟清扫死值（判定表＋减法维护）
    Day 26  cse                 合并完全相同的纯算子（本文件的最小实现）

学习计划第 27 天的三行——
    学习：分析结果失效、Pass 重复运行和不动点的基础概念；
    实践：依次运行常量折叠、CSE、DCE，比较不同顺序的 IR；完成第一阶段集成测试；
    产出：优化前后 IR、全部测试和第一阶段可运行代码。

今天新增的两个组件：
    CsePass         Day 26 规则的最小实现：单趟正向扫描，键 =（算子, 输入,
                    结果类型）；add/mul 按交换律排序输入，matmul/relu 保序；
                    副作用算子和未知算子不参与合并；合并动作只换边
                    （后来的并入先来的），语句本身留给 dce 清扫——分工与
                    Day 25 [6b] 的约定一致。
    FixpointRunner  今天的主角：把一条管线反复跑到不动点。一轮 = 完整跑一遍
                    管线；收敛判据 = 某一轮 epoch 零改动（不是“看起来没变”，
                    是改动日志一步都没走）。max_rounds 是保险丝：Pass 组合
                    不收敛时宁可报“未收敛”，不要无限循环。

为什么一轮可能不够：机会会“迟到”。贯穿图里 %u = add(%x, %w)——第 1 轮
algebraic-simplify 走过它时，%w 还是 add(%c2, %cm2)，不是常量，恒等式
不成立；本轮后半段 const-eval 才把 %w 变成 const 0、cse 才把它并入 %c0
——等 %u 真正成为 add(x, 0)，simplify 已经下班了。只能等第 2 轮。这就是
“Pass 重复运行”的必要性：一个 Pass 创造的机会，可能只有下一个轮次的
另一个 Pass 才能兑现。

为什么这套管线必然停（终止性）：四个 Pass 都只做三类动作——删语句
（dce）、把 add/mul 变身成 const（const-eval，变身不可逆：const 不会变回
add）、把一条使用边改指向“更早定义的值”（simplify/cse 的换边：替换目标
要么是语句的另一个输入，要么是同键的更早出现者）。语句数只减不增、
add/mul 数只减不增、每条边指向的定义位置只会前移——三个量都回不去，
所以循环必停。反过来，若两个 Pass 能互相改写（A→B 又 B→A），不动点
循环就不会停——这正是需要 max_rounds 保险丝的世界。

分析结果失效的现场：AnalysisManager 靠 epoch 对账（Day 20），同一份
缓存第二次查询之前图变了，旧答案必须作废重算。今天用一个小实验把
stats 打出来看：queries=2、recomputed=2、invalidated=1。而四个变换
Pass 干脆不查 am——它们进场自建事实（simplify/const-eval 的 defs 表、
cse 的键表、dce 的使用计数表），改图时 O(1) 维护或整表重建；缓存进
AnalysisManager 只会在变换中途反复作废。PassManager 每轮 run 都新建
AnalysisManager（Day 22 的设计），上一轮的缓存绝无可能漏进下一轮。
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
        每次修改 epoch + 1 并写改动日志——今天所有收敛判断都靠它对账；
      * validate 是 Day 17/18 的 SSA 闸门：唯一定义、使用先于定义。
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


# ---------- 分析：Day 20 的组件原样搬来（失效实验要用）----------

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

    stats 三项今天要盯紧：queries（问了几次）、recomputed（真算了几次）、
    invalidated（旧答案作废几次）——“分析结果失效”的全部账本。
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

    今天的关键细节：run() 每次调用都新建 AnalysisManager——FixpointRunner
    一轮调一次 run，上一轮的分析缓存绝无可能漏进下一轮（最朴素的失效
    策略：跨轮全作废；真实编译器会做更细粒度的失效跟踪）。
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
    浮点特判。defs 表在 Pass 内部自建自弃：每折一条图就变，事实必须重建。
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
    今天的重点角色：%w = add(%c2, %cm2) 变身 const 0 之后，%u 的恒等式
    才成形——机会是本 Pass 创造的，兑现却要等下一轮的 algebraic-simplify。
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
    死值，都等它统一收走。它排在哪个位置，决定了残骸要等多久才被扫走。
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


# ---------- Day 26 的 Pass：公共子表达式消除（今天的最小实现）----------

class CsePass(Pass):
    """合并完全相同的纯算子：后来的并入先来的，语句留给 dce 清扫。

    等价的判据是结构键（Day 26 的三要素——结构等价、属性等价、输入顺序）：
      * 算子相同 ＋ 输入相同 ＋ 结果 (shape, dtype) 相同 → 键相同；
      * add/mul 满足交换律：输入排序后进键（add(x,y) 与 add(y,x) 等价）；
        matmul/relu 保序——matmul(a,b) ≠ matmul(b,a)；
      * 常量：值 ＋ 类型进键（const 5 i32 ≠ const 5 i64）；
      * 副作用算子（debug）和未知算子不参与合并——合并 debug 会少打印一行，
        合并不认识的算子等于猜它的语义（门卫不猜，Day 23/24/25 同一原则）。

    合并动作只换边：replace_all_uses(后来的, 先来的)，语句本身不删——
    清扫是 dce 的活（分工与 Day 25 [6b] 的约定一致）。这带来一个工程后果：
    cse 之后图里留着“刚被掏空”的死语句，谁在后面扫，谁负责收走。
    """

    name = "cse"

    def __init__(self, commutative=True):
        self.commutative = commutative      # 5.4 实验二：交换律关掉会怎样
        self.merges = []

    def run(self, graph, am):
        self.merges = []
        seen = {}                           # 键 → 首个出现者的结果名
        used = graph.used_at()              # 进场快照：谁还有使用者
        # 本 Pass 只换边不删语句，位置不变；每条语句被访问前，它自己的
        # 使用者不会被换走（换边的 old 永远是“当前正被访问的语句”），
        # 所以进场快照对每条语句自己的判定始终准确。
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


# ---------- 今天的主角：把管线跑到不动点 ----------

class FixpointRunner:
    """把一条 Pass 管线反复跑到不动点。

    一轮 = 按给定顺序完整跑一遍管线；轮与轮之间唯一的通信介质是图本身
    ——上一轮的输出 IR 就是下一轮的输入 IR。收敛判据：某一轮从头到尾
    epoch 零改动。这不是“看起来没变”：epoch 由改图方法维护（Day 22 的
    bypass 检查靠它兜底），零改动意味着四个 Pass 谁都没找到任何机会。

    终止性（为什么敢循环）：见模块 docstring——语句数只减不增、add/mul
    变 const 不可逆、换边只会把使用边改指向更早的定义。反过来，若 Pass
    组合能互相改写（A→B 又 B→A），循环就不会停——所以 max_rounds 是
    保险丝：宁可报“未收敛”，不要无限循环。
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


# ---------- 语义对照（Day 25 原样搬来）----------

def interp(graph, feed):
    """最小解释器：按语句顺序执行图，返回（输出值列表， debug 打印行列表）。

    “可观察行为”的模型就这两样：图输出 ＋ debug 打印。优化前后各跑一遍，
    两者完全一致才叫语义不变——第一阶段集成测试的地基。
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
    """语义对照：两张图在同一份输入下，输出和打印是否完全一致。"""
    o1, d1 = interp(g1, feed)
    o2, d2 = interp(g2, feed)
    ok = (o1 == o2 and d1 == d2)
    return ok, (o1, d1), (o2, d2)


# ---------- 贯穿全文的图 ----------

# 第一阶段的收官图：18 条语句，四种冗余齐聚 + 一条“迟到的 0”。
#   %a1 = add(%x, %c0)        恒等冗余：simplify 第 1 轮就认出
#   %t2 = add(%c2, %c3)       常量计算：const-eval 第 1 轮折成 5
#   %w  = add(%c2, %cm2)      2+(-2)=0：const-eval 第 1 轮折成 0，
#                             但 %u = add(%x, %w) 的恒等式要到第 2 轮
#                             才被 simplify 认出——机会在本轮中途才出生
#   %k1 / %y                   交换律重复：cse 第 1 轮合并
#   %q1 → %q2                  死链：dce 的开胃菜
#   %p = debug(%k2)           副作用：谁都不能动它
INTEGRATION_GRAPH = [
    ("input",    "%x",   [],               ((), "i32")),
    ("const 0",  "%c0",  [],               ((), "i32")),
    ("const 1",  "%c1",  [],               ((), "i32")),
    ("const 2",  "%c2",  [],               ((), "i32")),
    ("const 3",  "%c3",  [],               ((), "i32")),
    ("const -2", "%cm2", [],               ((), "i32")),
    ("add",      "%a1",  ["%x", "%c0"],    ((), "i32")),   # add(x,0) → x
    ("relu",     "%z",   ["%a1"],          ((), "i32")),
    ("add",      "%t2",  ["%c2", "%c3"],   ((), "i32")),   # 2+3 → const 5
    ("add",      "%w",   ["%c2", "%cm2"],  ((), "i32")),   # 2+(-2) → const 0
    ("add",      "%u",   ["%x", "%w"],     ((), "i32")),   # 迟到的 0 → x（第 2 轮）
    ("add",      "%k1",  ["%x", "%c1"],    ((), "i32")),
    ("relu",     "%k2",  ["%k1"],          ((), "i32")),
    ("debug",    "%p",   ["%k2"],          ((), "i32")),   # 副作用：必须活
    ("add",      "%y",   ["%c1", "%x"],    ((), "i32")),   # add(c1,x)：并入 %k1
    ("relu",     "%q1",  ["%c3"],          ((), "i32")),   # 死链头
    ("relu",     "%q2",  ["%q1"],          ((), "i32")),   # 死链尾
    ("output",   None,   ["%y", "%z", "%u", "%t2"], None),
]

# 分析失效实验的图：const-eval 变身 %d 之后，%c2/%c3 变成新的死值
INVAL_GRAPH = [
    ("input",    "%x",  [],              ((), "i32")),
    ("const 2",  "%c2", [],              ((), "i32")),
    ("const 3",  "%c3", [],              ((), "i32")),
    ("add",      "%d",  ["%c2", "%c3"],  ((), "i32")),   # const-eval → const 5
    ("relu",     "%e",  ["%d"],          ((), "i32")),   # 死值：无人使用
    ("output",   None,  ["%x"],          None),
]

# CSE 单元测试的图
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

CSE_DEAD_DUP_GRAPH = [
    ("input",   "%x",   [],              ((), "i32")),
    ("const 1", "%c1",  [],              ((), "i32")),
    ("add",     "%k1",  ["%x", "%c1"],   ((), "i32")),
    ("add",     "%r",   ["%x", "%c1"],   ((), "i32")),   # 重复但无人使用
    ("output",  None,   ["%k1"],         None),
]


# ---------- 演示 ----------

ORDER_A = [AlgebraicSimplifyPass(), ConstEvalPass(), CsePass(), DcePass()]   # 常规序：清扫车压轴
ORDER_B = [DcePass(), CsePass(), ConstEvalPass(), AlgebraicSimplifyPass()]   # 完全倒序：清扫车打头
ORDER_C = [CsePass(), DcePass(), AlgebraicSimplifyPass(), ConstEvalPass()]   # 清扫车夹在中间


def fresh_order(order):
    """每个实验用独立的 Pass 实例——决策日志互不污染。"""
    return [type(p)() for p in order]


def demo():
    print("== [1] 第一阶段的收官图：18 条语句，四种冗余齐聚 ==")
    g0 = Graph(INTEGRATION_GRAPH)
    print("// 优化前：")
    print(ir_dump(g0))
    base_out, base_dbg = interp(g0, {"%x": 7})
    print(f"语义基线（喂 %x=7）：输出 {base_out}，打印 {base_dbg}")
    print("埋了四种冗余：恒等 add(%x,%c0)、常量 2+3 和 2+(-2)、交换律重复")
    print("add(%x,%c1)/add(%c1,%x)、死链 %q1→%q2；外加一条“迟到的 0”——见 [2]。")

    print("\n== [2] 一轮为什么不够：机会在本轮中途才出生 ==")
    g1 = Graph(INTEGRATION_GRAPH)
    pm1 = PassManager(print_ir="change", verbose=True, title="PM-round1")
    pm1.add(*fresh_order(ORDER_A))
    ok = pm1.run(g1)
    print(f"run() 返回 {ok}；一轮结束：{len(INTEGRATION_GRAPH)} 条 → {len(g1.statements)} 条，epoch = {g1.epoch}")
    print("// 第 1 轮结束的 IR（注意 %u 还在）：")
    print(ir_dump(g1))
    print("%u = add(%x, %c0) 现在是恒等式——但第 1 轮 simplify 经过它时，")
    print("%w 还是 add(%c2,%cm2) 不是常量，五道门的“值为单位元”过不去；")
    print("本轮后半段 const-eval 才把 %w 变成 const 0、cse 才把它并入 %c0——")
    print("恒等式是本轮中途才成形的，simplify 已经下班，只能等第 2 轮。")

    print("\n== [3] 正戏：FixpointRunner 把 order A 跑到不动点 ==")
    g2 = Graph(INTEGRATION_GRAPH)
    runner = FixpointRunner(fresh_order(ORDER_A), max_rounds=10, title="order A")
    ok = runner.run(g2)
    print(runner.round_table())
    print(f"run() 返回 {ok}；converged = {runner.converged}，"
          f"共 {len(runner.rounds)} 轮（前 {len(runner.rounds) - 1} 轮有改动），"
          f"总改动 {runner.total_changes()} 次")
    print(f"{len(INTEGRATION_GRAPH)} 条 → {len(g2.statements)} 条；最终 IR：")
    print(ir_dump(g2))
    for feed in (-3, 0, 7):
        ok_s, (o1, d1), (o2, d2) = same_behavior(Graph(INTEGRATION_GRAPH), g2, {"%x": feed})
        print(f"语义对照（喂 %x={feed}）：输出 {o1} == {o2}，打印 {d1} == {d2} → {'一致 ✓' if ok_s else '不一致 ✗'}")

    print("\n== [4] 顺序实验：三条管线，一条终点 ==")
    results = {}
    for tag, order in (("A", ORDER_A), ("B", ORDER_B), ("C", ORDER_C)):
        gx = Graph(INTEGRATION_GRAPH)
        rx = FixpointRunner(fresh_order(order), max_rounds=10, title=f"order {tag}")
        ok = rx.run(gx)
        results[tag] = (gx, rx, ok)
        print(rx.round_table())
        print(f"  order {tag}：run() 返回 {ok}，converged = {rx.converged}，"
              f"到达轮数 {len(rx.rounds)}，总改动 {rx.total_changes()} 次，"
              f"最终 {len(gx.statements)} 条\n")
    gA, rA, _ = results["A"]
    gB, rB, _ = results["B"]
    gC, rC, _ = results["C"]
    print(f"一轮后的条数：A={rA.rounds[0]['after']}，B={rB.rounds[0]['after']}，C={rC.rounds[0]['after']}")
    print(f"一轮后的 IR 两两不同：A≠B {rA.rounds[0]['ir'] != rB.rounds[0]['ir']}，"
          f"A≠C {rA.rounds[0]['ir'] != rC.rounds[0]['ir']}，B≠C {rB.rounds[0]['ir'] != rC.rounds[0]['ir']}")
    same_all = ir_dump(gA) == ir_dump(gB) == ir_dump(gC)
    print(f"不动点的 IR 逐字节相同：{same_all}——顺序改变的是路径（哪一轮谁干活），"
          f"不改变终点（同一张 {len(gA.statements)} 条的最简图）")
    print("\n// order B 第 1 轮结束的 IR（残骸现场：清扫车打头，没人收尾）：")
    gb1 = Graph(INTEGRATION_GRAPH)
    PassManager(print_ir="none", verbose=False).add(*fresh_order(ORDER_B)).run(gb1)
    print(ir_dump(gb1))
    print("死值 %y、%w、%c2、%c3、%cm2 躺在图里——dce 在本轮第一位，此后再没人扫；")
    print("它们要等第 2 轮开头的 dce。order A 一轮后 10 条、order B/C 一轮后 14 条。")

    print("\n== [5] 保险丝：max_rounds=2 的 order C——提前停就留残骸 ==")
    g3 = Graph(INTEGRATION_GRAPH)
    r3 = FixpointRunner(fresh_order(ORDER_C), max_rounds=2, title="order C（上限 2 轮）")
    ok = r3.run(g3)
    print(r3.round_table())
    print(f"run() 返回 {ok}；converged = {r3.converged}——图停在 {len(g3.statements)} 条，")
    names = [s[1] for s in g3.statements]
    print(f"残骸：{'、'.join(n for n in ['%c0', '%y', '%w', '%u', '%q1'] if n in names)}"
          f"（完整收敛要 {len(rC.rounds)} 轮）——未收敛不等于错误，但必须报告，不能沉默")

    print("\n== [6] 分析结果失效：同一份缓存，第二次问之前过期了 ==")
    g4 = Graph(INVAL_GRAPH)
    am = AnalysisManager(g4)
    d1 = am.get(UnusedAnalysis())
    print(f"第 1 次询问 unused：死值 {sorted(d1.dead)}，stats = {am.stats}，epoch = {g4.epoch}")
    ConstEvalPass().run(g4, am)            # 变身：%d → const 5（epoch +1）
    d2 = am.get(UnusedAnalysis())
    print(f"const-eval 之后第 2 次询问：死值 {sorted(d2.dead)}，stats = {am.stats}，epoch = {g4.epoch}")
    print("%d 变身 const 5 之后，%c2、%c3 的使用者没了——死值从 1 个长成 3 个。")
    print("缓存的旧答案还在，epoch 对账发现过期（invalidated +1），只能重算——")
    print("这就是 Day 20 的铁律在 Pass 组合里的样子。四个变换 Pass 干脆不查 am：")
    print("simplify/const-eval 自建 defs 表、cse 自建键表、dce 自建使用计数表——")
    print("变换中途的事实维护比缓存重算便宜。PassManager 每轮 run 新建 AnalysisManager，")
    print("上一轮的缓存绝无可能漏进下一轮。")

    print("\n== [7] 负例回归：合并与删除都不越界 ==")
    gd = Graph(CSE_DEBUG_PAIR_GRAPH)
    pd = CsePass()
    PassManager(print_ir="none", verbose=False).add(pd).run(gd)
    print(f"两个 debug(%k2)：cse 合并 {len(pd.merges)} 次（副作用不合并——合并会少打印一行）")
    _, dbg_lines = interp(gd, {"%x": 5})
    print(f"执行时打印 {len(dbg_lines)} 行：{dbg_lines}")
    gm = Graph(CSE_MATMUL_GRAPH)
    pmm = CsePass()
    PassManager(print_ir="none", verbose=False).add(pmm).run(gm)
    print(f"matmul(%a,%b) 与 matmul(%b,%a)：cse 合并 {len(pmm.merges)} 次（顺序就是语义）")
    gc = Graph(CSE_CONST_DTYPE_GRAPH)
    pc = CsePass()
    PassManager(print_ir="none", verbose=False).add(pc).run(gc)
    print(f"const 5 i32 与 const 5 i64：cse 合并 {len(pc.merges)} 次（类型是键的一部分）")
    print("第一阶段集成到此收口：优化前后 IR、语义对照、顺序实验、负例——都在 --self-test 里。")
    return 0


# ---------- 自测：第一阶段集成测试 ----------

def self_test():
    results = []

    def check(name, cond):
        results.append((name, bool(cond)))
        print(f"  {'✓' if cond else '✗'} {name}")

    print("== 自测：第 27 天 Pass 组合与第一阶段集成 ==")

    # A. 贯穿图与不动点（order A）
    gA = Graph(INTEGRATION_GRAPH)
    rA = FixpointRunner(fresh_order(ORDER_A), max_rounds=10, title="A")
    check("A：run 返回 True 且收敛", rA.run(gA) is True and rA.converged is True)
    check("A：3 轮到达不动点（2 轮干活＋1 轮确认）", len(rA.rounds) == 3)
    check("A：第 3 轮整轮零改动", rA.rounds[2]["changes"] == 0)
    check("A：第 1 轮后 10 条（%u 幸存——迟到的 0）", rA.rounds[0]["after"] == 10)
    check("A：最终 8 条", len(gA.statements) == 8)
    check("A：第 2 轮 simplify 有动作（兑现迟到的 0）",
          any(n == "algebraic-simplify" and c > 0 for n, c in rA.rounds[1]["per_pass"]))
    namesA = [s[1] or "(output)" for s in gA.statements]
    check("A：冗余全部蒸发（%a1 %w %u %y %q1 %q2 %c0 %c2 %c3 %cm2 不在）",
          not any(n in namesA for n in ["%a1", "%w", "%u", "%y", "%q1", "%q2", "%c0", "%c2", "%c3", "%cm2"]))
    check("A：活链与契约全部保留（%x %c1 %z %t2 %k1 %k2 %p output）",
          all(n in namesA for n in ["%x", "%c1", "%z", "%t2", "%k1", "%k2", "%p"]))
    check("A：%t2 变身 const 5", any(s[0] == "const 5" and s[1] == "%t2" for s in gA.statements))
    check("A：output 改读合并后的代表（%k1）与直通值（%x）",
          gA.statements[-1][2] == ["%k1", "%z", "%x", "%t2"])
    check("A：图仍合法（SSA 闸门通过）", gA.validate() is True)

    # B. 顺序实验
    finals, round1s, runners = {}, {}, {}
    for tag, order in (("A", ORDER_A), ("B", ORDER_B), ("C", ORDER_C)):
        gx = Graph(INTEGRATION_GRAPH)
        rx = FixpointRunner(fresh_order(order), max_rounds=10, title=tag)
        ok = rx.run(gx)
        finals[tag], round1s[tag], runners[tag] = ir_dump(gx), rx.rounds[0]["ir"], (gx, rx, ok)
    check("B：三条管线全部收敛", all(runners[t][1].converged for t in "ABC"))
    check("B：到达轮数 A=3、B=3、C=4",
          (len(runners["A"][1].rounds), len(runners["B"][1].rounds), len(runners["C"][1].rounds)) == (3, 3, 4))
    check("B：一轮后条数 A=10、B=14、C=14",
          (runners["A"][1].rounds[0]["after"], runners["B"][1].rounds[0]["after"],
           runners["C"][1].rounds[0]["after"]) == (10, 14, 14))
    check("B：一轮后的 IR 两两不同", round1s["A"] != round1s["B"] and round1s["A"] != round1s["C"]
          and round1s["B"] != round1s["C"])
    check("B：不动点的 IR 逐字节相同", finals["A"] == finals["B"] == finals["C"])
    check("B：B 第 1 轮的改动比 A 少（清扫车打头，首轮能干的活少）",
          runners["B"][1].rounds[0]["changes"] < rA.rounds[0]["changes"])
    namesB1 = [ln for ln in round1s["B"].splitlines() if "%y" in ln or "%u" in ln]
    check("B：B 第 1 轮 IR 含 %y 不含 %u（simplify 压轴兑现了迟到的 0）",
          any("%y" in l for l in namesB1) and not any("%u" in l for l in namesB1))
    namesC1 = [ln for ln in round1s["C"].splitlines() if "%y" in ln or "%u" in ln]
    check("B：C 第 1 轮 IR 含 %u 不含 %y（dce 夹中间，先扫了 %y）",
          any("%u" in l for l in namesC1) and not any("%y" in l for l in namesC1))

    # C. 语义不变（输出＋打印两样都对照）
    for feed, expect in ((-3, [-2, 0, -3, 5]), (0, [1, 0, 0, 5]), (7, [8, 7, 7, 5])):
        ok_s, (o1, d1), (o2, d2) = same_behavior(Graph(INTEGRATION_GRAPH), gA, {"%x": feed})
        check(f"C：喂 %x={feed} 输出 {expect} 且前后一致",
              ok_s and o1 == expect and d1 == d2)
    _, dbg_final = interp(gA, {"%x": 7})
    check("C：副作用打印幸存且内容不变", dbg_final == ["[debug] %p(%k2) = 8"])
    for tag in "BC":
        ok_s, _, _ = same_behavior(Graph(INTEGRATION_GRAPH), runners[tag][0], {"%x": 0})
        check(f"C：order {tag} 的终点语义不变", ok_s)

    # D. CSE 单元（Day 26 规则的回归）
    g = Graph(CSE_COMMUTED_GRAPH)
    p = CsePass()
    PassManager(print_ir="none", verbose=False).add(p).run(g)
    check("D：交换律合并 add(x,c1)/add(c1,x) → %y 并入 %k1",
          len(p.merges) == 1 and p.merges[0]["later"] == "%y" and g.statements[-1][2] == ["%k1", "%k1"])
    check("D：被合并的语句留给 dce（%y 仍在图中）", any(s[1] == "%y" for s in g.statements))
    pm2 = PassManager(print_ir="none", verbose=False)
    pm2.add(DcePass()).run(g)
    check("D：dce 收走 %y", not any(s[1] == "%y" for s in g.statements))
    g = Graph(CSE_DEBUG_PAIR_GRAPH)
    p = CsePass()
    PassManager(print_ir="none", verbose=False).add(p).run(g)
    check("D：两个 debug 不合并（副作用）", len(p.merges) == 0)
    g = Graph(CSE_MATMUL_GRAPH)
    p = CsePass()
    PassManager(print_ir="none", verbose=False).add(p).run(g)
    check("D：matmul(a,b) 与 matmul(b,a) 不合并（顺序就是语义）", len(p.merges) == 0)
    g = Graph(CSE_CONST_DTYPE_GRAPH)
    p = CsePass()
    PassManager(print_ir="none", verbose=False).add(p).run(g)
    check("D：const 5 i32 与 const 5 i64 不合并（类型进键）", len(p.merges) == 0)
    check("D：同型常量参与合并的通路仍在（%d32/%d64 因输入不同不合并）",
          all(s[1] in ("%c32", "%c64", "%d32", "%d64", None) for s in g.statements))
    g = Graph(CSE_DEAD_DUP_GRAPH)
    p = CsePass()
    PassManager(print_ir="none", verbose=False).add(p).run(g)
    check("D：无人使用的重复不合并（无事可换，死值归 dce）",
          len(p.merges) == 0 and any(s[1] == "%r" for s in g.statements))
    g = Graph(CSE_COMMUTED_GRAPH)
    p = CsePass(commutative=False)
    PassManager(print_ir="none", verbose=False).add(p).run(g)
    check("D：关掉交换律后 add(c1,x) 不再并入 add(x,c1)", len(p.merges) == 0)

    # E. 前几天 Pass 的回归（阶段集成：老积木没被今天的新组装碰坏）
    g = Graph([("input", "%x", [], ((), "i32")),
               ("const 0", "%z", [], ((), "i32")),
               ("add", "%d", ["%x", "%z"], ((), "i32")),
               ("output", None, ["%d"], None)])
    p = AlgebraicSimplifyPass()
    PassManager(print_ir="none", verbose=False).add(p).run(g)
    check("E：simplify 仍折 add(x,0)（output 直读 %x；死常量留给 dce）",
          g.statements[-1][2] == ["%x"] and len(g.statements) == 3
          and any(s[1] == "%z" for s in g.statements))
    g = Graph([("const 2147483647", "%a", [], ((), "i32")),
               ("const 1", "%b", [], ((), "i32")),
               ("add", "%d", ["%a", "%b"], ((), "i32")),
               ("output", None, ["%d"], None)])
    p = ConstEvalPass()
    PassManager(print_ir="none", verbose=False).add(p).run(g)
    check("E：const-eval 仍拒 i32 溢出（2147483647+1）",
          any(d["verdict"] == "skip" for d in p.decisions) and g.statements[2][0] == "add")
    g = Graph([("const 2", "%a", [], ((), "i32")),
               ("const 3", "%b", [], ((), "i32")),
               ("add", "%d", ["%a", "%b"], ((), "i32")),
               ("output", None, ["%d"], None)])
    p = ConstEvalPass()
    PassManager(print_ir="none", verbose=False).add(p).run(g)
    check("E：const-eval 仍折 2+3 → const 5", g.statements[2][0] == "const 5")
    g = Graph(INTEGRATION_GRAPH)
    pm = PassManager(print_ir="none", verbose=False)
    pd = DcePass()
    pm.add(pd).run(g)
    kept = [s[1] for s in g.statements]
    check("E：dce 单独跑仍保留 debug 与全部活链（只扫死链）",
          "%p" in kept and "%k1" in kept and "%y" in kept and "%q1" not in kept and "%q2" not in kept)
    check("E：dce 单独跑不越界删变换目标（%a1/%w/%u 都还有人用）",
          all(n in kept for n in ["%a1", "%w", "%u"]))
    g = Graph([("input", "%x", [], ((), "i32")),
               ("mystery", "%m", ["%x"], ((), "i32")),
               ("output", None, ["%m"], None)])
    pm = PassManager(print_ir="none", verbose=False)
    pd = DcePass()
    pm.add(pd).run(g)
    check("E：未知算子 mystery 仍按副作用未知保留", any(s[0] == "mystery" for s in g.statements))

    # F. 分析结果失效
    g = Graph(INVAL_GRAPH)
    am = AnalysisManager(g)
    d1 = am.get(UnusedAnalysis())
    stats1 = dict(am.stats)
    epoch1 = g.epoch
    ConstEvalPass().run(g, am)
    d2 = am.get(UnusedAnalysis())
    check("F：第一次查询后缓存命中口径（queries=1, recomputed=1, invalidated=0）",
          stats1 == {"queries": 1, "recomputed": 1, "invalidated": 0})
    check("F：变换之后旧答案作废重算（queries=2, recomputed=2, invalidated=1）",
          am.stats == {"queries": 2, "recomputed": 2, "invalidated": 1} and g.epoch > epoch1)
    check("F：死值集合随图变化（{%e} → {%c2, %c3, %e}）",
          set(d1.dead) == {"%e"} and set(d2.dead) == {"%c2", "%c3", "%e"})

    # G. FixpointRunner 机制
    g = Graph(INTEGRATION_GRAPH)
    r = FixpointRunner(fresh_order(ORDER_C), max_rounds=2, title="fuse")
    ok = r.run(g)
    check("G：max_rounds=2 的 order C 未收敛且停在第 2 轮",
          ok is True and r.converged is False and len(r.rounds) == 2)
    check("G：提前停留下残骸（%c0 还在图中）", any(s[1] == "%c0" for s in g.statements))
    g = Graph(INTEGRATION_GRAPH)
    r = FixpointRunner([], max_rounds=5, title="empty")
    r.run(g)
    check("G：空管线第 1 轮即收敛（零改动）", r.converged and len(r.rounds) == 1 and r.rounds[0]["changes"] == 0)
    g = Graph([("input", "%x", [], ((), "i32")), ("output", None, ["%x"], None)])
    r = FixpointRunner(fresh_order(ORDER_A), max_rounds=5, title="minimal")
    r.run(g)
    check("G：已是最简的图第 1 轮即收敛且语句数不变",
          r.converged and len(g.statements) == 2)

    passed = sum(1 for _, ok in results if ok)
    print(f"\n{passed}/{len(results)} 项通过")
    return 0 if passed == len(results) else 1


def main():
    ap = argparse.ArgumentParser(description="第 27 天演练场：Pass 组合与第一阶段集成验收")
    ap.add_argument("--self-test", action="store_true", help="运行第一阶段集成测试")
    args = ap.parse_args()
    return self_test() if args.self_test else demo()


if __name__ == "__main__":
    raise SystemExit(main())
