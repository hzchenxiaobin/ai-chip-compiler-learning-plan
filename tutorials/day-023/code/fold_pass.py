#!/usr/bin/env python3
"""第 23 天演练场：代数化简 Pass——常量折叠的第一步。

用法：
    python3 fold_pass.py               # 演示主流程：浮点真相、正例、反例、开关对照、溢出演示
    python3 fold_pass.py --self-test   # 运行自测，全部通过退出码 0

Day 22 交付了调度台（Pass 接口＋PassManager）；今天第一个“真”优化 Pass 上岗：
algebraic-simplify。它只做两条恒等替换——

    add(x, 0) → x    整数下恒成立；浮点下默认不折（-0.0 + 0.0 = +0.0，符号会丢）
    mul(x, 1) → x    整数、浮点下都恒成立（IEEE 754 下 x * 1.0 逐位等于 x）

术语先对齐：学习计划标题写“常量折叠”（constant folding），但今天的实践是
“代数化简”（algebraic simplification）——把 x + 0 这样的式子替换成它的输入 x，
并不“计算”任何东西。真正的常量计算（const + const → 新 const）是明天 Day 24。
MLIR 把这类规则叫 canonicalization pattern（规范化模式）。

每条替换动身前要过五道门，任何一道不过就拒绝，并把原因写进决策日志：
    门① 算子纯净：add / mul 无副作用，替换后没人能察觉（Day 20 的 PURE_OPS 口径）；
    门② 值是单位元：常量按它自己的 dtype 解析，值必须恰为 0 / 1；
        “const 0.5” 配 i32 解析失败——不合法类型不碰、也不崩；
    门③ 类型对齐：dtype(常量) == dtype(另一输入) == dtype(结果)。
        类型提升（i32 × i64）本 IR 没有定义——没定义的语义一律不折；
    门④ Shape 对齐：三方 shape 相同（splat 常量）。标量配张量是广播，
        广播要等 Day 60；
    门⑤ 浮点特判：add 对浮点默认拒绝（带符号零问题），mul 对浮点放行。
        allow_signed_zero_fp=True 表示“我保证带符号零不重要”，
        对应 LLVM fast-math 的 nsz 标志——真实编译器同样如此。

为什么今天不碰 mul(x, 0) → 0：整数下它是恒等式，浮点下 Inf×0=NaN、
(-0.0)×0=-0.0——留给必做练习，亲手体会“看着能折其实不能”。

溢出风险（今天的学习目标）：恒等式不会溢出——x+0 和 x*1 的结果就是 x 本身，
天然可表示。会溢出的是“真算”：const 2147483647 + const 1 在 i32 下装不下，
那是 Day 24 编译期求值要处理的事——先检查可表示，再落笔。
"""

from __future__ import annotations

import argparse
import math
import re
import struct

PURE_OPS = {"matmul", "add", "relu", "mul"}   # 无副作用算子（Day 20 同款口径）

INT_DTYPES = {"i8", "i16", "i32", "i64"}
FLOAT_DTYPES = {"f16", "bf16", "f32", "f64"}
KNOWN_DTYPES = INT_DTYPES | FLOAT_DTYPES

IDENTITY = {"add": 0, "mul": 1}   # 算子 → 单位元（identity element）
FLOAT_UNSAFE = {"add"}            # 对浮点默认不安全的规则（-0.0 + 0.0 = +0.0）


# ---------- 图：Day 22 同款外壳，语句第 4 格从 shape 升级为 (shape, dtype) ----------

# 贯穿全文的例子（Day 22 的六语句图，本天起带 dtype）：
PIPELINE_GRAPH = [
    ("input",   "%a",    [],              ((2, 3), "i32")),
    ("const 0", "%zero", [],              ((2, 3), "i32")),   # splat：全 0 张量
    ("add",     "%d",    ["%a", "%zero"], ((2, 3), "i32")),   # add(x, 0) → x
    ("relu",    "%e",    ["%d"],          ((2, 3), "i32")),
    ("relu",    "%z",    ["%e"],          ((2, 3), "i32")),   # 从未被使用：天生死代码
    ("output",  None,    ["%e"],          None),
]

# 正例图：i32 世界——常量在左、在右、级联、mul 单位元，一网打尽
POSITIVE_GRAPH = [
    ("input",   "%a",    [],              ((2, 3), "i32")),
    ("const 0", "%z",    [],              ((2, 3), "i32")),
    ("const 1", "%o",    [],              ((2, 3), "i32")),
    ("add",     "%d1",   ["%z", "%a"],    ((2, 3), "i32")),   # 0 在左边：add(0, x) → x
    ("mul",     "%d2",   ["%d1", "%o"],   ((2, 3), "i32")),   # mul(x, 1) → x
    ("add",     "%d3",   ["%d2", "%z"],   ((2, 3), "i32")),   # 再 +0：级联
    ("relu",    "%e",    ["%d3"],         ((2, 3), "i32")),
    ("output",  None,    ["%e"],          None),
]

# 反例图一：浮点的两张面孔（add 拒、mul 折）
FLOAT_GRAPH = [
    ("input",   "%x",    [],               ((2, 3), "f32")),
    ("const 0", "%fz",   [],               ((2, 3), "f32")),
    ("const 1", "%fo",   [],               ((2, 3), "f32")),
    ("add",     "%s1",   ["%x", "%fz"],    ((2, 3), "f32")),   # 拒：-0.0 问题
    ("mul",     "%s2",   ["%x", "%fo"],    ((2, 3), "f32")),   # 折：×1 安全
    ("output",  None,    ["%s1", "%s2"],   None),
]

# 反例图二：类型提升（i32 结果 × i64 常量）
PROMO_GRAPH = [
    ("input",   "%x",   [],             ((2, 3), "i32")),
    ("const 0", "%w",   [],             ((2, 3), "i64")),
    ("add",     "%d",   ["%x", "%w"],   ((2, 3), "i32")),
    ("output",  None,   ["%d"],         None),
]

# 反例图三：shape 不一致（张量 × 标量 = 广播，未建模）
BCAST_GRAPH = [
    ("input",   "%x",   [],            ((2, 3), "i32")),
    ("const 0", "%s",   [],            ((), "i32")),
    ("add",     "%d",   ["%x", "%s"],  ((2, 3), "i32")),
    ("output",  None,   ["%d"],        None),
]

# 反例图四：值在 dtype 下不合法（“const 0.5” 配 i32）
BADVAL_GRAPH = [
    ("input",     "%x",   [],             ((2, 3), "i32")),
    ("const 0.5", "%h",   [],             ((2, 3), "i32")),
    ("add",       "%d",   ["%x", "%h"],   ((2, 3), "i32")),
    ("output",    None,   ["%d"],         None),
]

# 反例图五：未知 dtype（q42）——不认识的一律不碰
UNKNOWN_GRAPH = [
    ("input",   "%x",   [],            ((2, 3), "q42")),
    ("const 0", "%z",   [],            ((2, 3), "q42")),
    ("add",     "%d",   ["%x", "%z"],  ((2, 3), "q42")),
    ("output",  None,   ["%d"],        None),
]


class GraphError(Exception):
    """图不合法，或违反“改图走方法”的契约。"""


class PassFailure(Exception):
    """Pass 主动上报的失败（对应 MLIR 的 failure()）。"""


class Graph:
    """语句序列表示的线性计算图（Day 22 同款契约，info 升级为 (shape, dtype)）。

      * 只读查询（labels / used_at / validate）不改图；
      * 修改必须走 remove_statement / replace_all_uses，每次修改 epoch + 1
        并写改动日志；
      * validate 仍是 Day 17/18 的 SSA 闸门：唯一定义、使用先于定义。
        类型合法性（const 0.5 配 i32、i32 × i64）目前 Verifier 还不懂——
        Day 39 的 MLIR Verifier 才补上；在那之前，Pass 必须自己当心。
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
        """把所有读 old 的语句改成读 new（今天折叠 Pass 的核心动作）。"""
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


# ---------- 工具 ----------


def fmt_type(info):
    """(shape, dtype) → MLIR 风格类型文本：((2,3),'i32') → tensor<2x3xi32>。"""
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
    """按 dtype 解析常量数值；类型不合法（或未知 dtype）返回 None。

    范围检查（值是否真能装进 i32）是 Day 24 常量求值的事——今天的单位元
    判断用不到它：0 和 1 任何整型都装得下。
    """
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


def removable(stmt):
    """结果无人使用且无副作用时可删；input 代表外部输入，不删（Day 25 再正式化）。"""
    op, res = stmt[0], stmt[1]
    return res is not None and (op in PURE_OPS or op.startswith("const"))


# ---------- 今天的主角：代数化简 Pass ----------


class AlgebraicSimplifyPass(Pass):
    """add(x, 0) → x、mul(x, 1) → x——常量折叠的第一步。

    每条替换过五道门（见模块 docstring）；拒绝也要留下原因（决策日志），
    因为“为什么没折”和“折了什么”同样是需要审计的信息。

    def 表（值名 → 定义语句）在本 Pass 内部自建自弃：每折一条图就变，
    事实必须重建（Day 20 的铁律）。它今天还不是注册分析——Day 26 的 CSE
    需要结构等价时再把它升级进 ANALYSES。
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

            # 门②：值按常量自己的 dtype 解析，必须恰为单位元
            if cdtype not in KNOWN_DTYPES:
                return ("skip", None, f"常量 {name} 的 dtype {cdtype} 不认识——未知类型一律不碰")
            val = const_value(dstmt[0], cdtype)
            if val is None:
                return ("skip", None, f"常量 {name}（{dstmt[0]}）的值在 {cdtype} 下不合法——绕开，不碰也不崩")
            if val != IDENTITY[op]:
                continue                    # 值不是单位元，看看另一个输入

            # 门③：类型对齐——没有定义过的提升规则，一律不折
            ostmt = defs.get(other)
            if ostmt is None:
                return ("skip", None, f"输入 {other} 没有定义——图有问题，交给 Verifier")
            oshape, odtype = ostmt[3]
            if cdtype != dtype or odtype != dtype:
                return ("skip", None,
                        f"类型提升未建模：另一输入 {odtype}、常量 {cdtype}、结果 {dtype} 三方不一致")

            # 门④：shape 对齐——广播未建模
            if cshape != shape or oshape != shape:
                return ("skip", None,
                        f"shape 不一致：{oshape} / {cshape} vs 结果 {shape}——广播是 Day 60 的事")

            # 门⑤：浮点特判——add 的 0 在浮点下不是“无害”的单位元
            if dtype in FLOAT_DTYPES and op in FLOAT_UNSAFE and not self.allow_signed_zero_fp:
                return ("skip", None,
                        f"{dtype} 的 {op}(x, {val}) 不恒等：-0.0 + 0.0 = +0.0，符号会丢"
                        f"（未开 allow_signed_zero_fp）")

            return ("fold", other,
                    f"{dtype} splat {shape}，值 {val} 是 {op} 的单位元，五道门全过")
        return ("skip", None, "没有值为单位元的常量输入")


class DcePreviewPass(Pass):
    """Day 25 DCE 的预演：删掉“无使用者且无副作用”的语句（Day 22 同款）。"""

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


# ---------- 演示 ----------


def run_quiet(graph, **kw):
    """安静地跑一遍代数化简（用于反例/开关对照），返回 (ok, pass, manager)。"""
    p = AlgebraicSimplifyPass(**kw)
    pm = PassManager(print_ir="none", verbose=False, title="PM-quiet")
    pm.add(p)
    return pm.run(graph), p, pm


def print_decisions(p):
    folds = [d for d in p.decisions if d["verdict"] == "fold"]
    skips = [d for d in p.decisions if d["verdict"] == "skip"]
    print(f"决策日志：检查 {len(p.decisions)} 条 add/mul——折 {len(folds)} 条，拒 {len(skips)} 条")
    for d in p.decisions:
        if d["verdict"] == "fold":
            print(f"  ✓ 折  {d['op']:<4}{d['res']} → {d['to']}")
        else:
            print(f"  ✗ 拒  {d['op']:<4}{d['res']}")
        print(f"        {d['reason']}")


def demo():
    print("== [1] 先看真相：浮点数下，x + 0.0 真的等于 x 吗？ ==")

    def bits(x):
        return " ".join(f"{b:02x}" for b in struct.pack("<d", x))

    nz = -0.0
    print(f"  -0.0        的 64 位：{bits(nz)}")
    print(f"  -0.0 + 0.0  的 64 位：{bits(nz + 0.0)}   ← 符号位丢了（但 == 仍然是 True！）")
    print(f"  -0.0 * 1.0  的 64 位：{bits(nz * 1.0)}   ← 逐位不变")
    print(f"  copysign(1, -0.0) = {math.copysign(1.0, nz)}，copysign(1, -0.0 + 0.0) = {math.copysign(1.0, nz + 0.0)}   ← 符号差异可观察")
    print("  （注：Python 里 1 / -0.0 会直接抛 ZeroDivisionError，C/IEEE 里才是 ±inf——浮点水很深）")
    print(f"  inf * 0.0 = {float('inf') * 0.0}   ← 所以 mul(x, 0) → 0 对浮点是错的")
    print(f"  1e308 * 10 = {1e308 * 10}   ← 浮点“溢出”不报错，直接变 inf")

    print("\n== [2] 正例：i32 世界，五道门全过 ==")
    g = Graph(POSITIVE_GRAPH)
    print("// 折叠前：")
    print(ir_dump(g))
    p = AlgebraicSimplifyPass()
    pm = PassManager(print_ir="none", verbose=False, title="PM-A")
    pm.add(p)
    ok = pm.run(g)
    print_decisions(p)
    print(f"run() 返回 {ok}；epoch = {g.epoch}（3 次折叠 × 换边+删除 = 6 次修改），最终 {len(g.statements)} 条语句")
    print("// 折叠后：")
    print(ir_dump(g))
    print("三个中间值 %d1/%d2/%d3 全部蒸发，%e 直接读 %a——级联在一趟内完成（删除后下一条滑到当前位置）")
    print("注意：const %z、%o 留下来了——它们变成死值是 DCE 的活（Day 25），今天的 Pass 不越界")

    print("\n== [3] Day 22 同款图接进管线：algebraic-simplify → dce-preview ==")
    g2 = Graph(PIPELINE_GRAPH)
    pm2 = PassManager(title="PM-B")
    pm2.add(AlgebraicSimplifyPass(), DcePreviewPass())
    ok2 = pm2.run(g2)
    print(f"run() 返回 {ok2}；最终 {len(g2.statements)} 条语句，epoch = {g2.epoch}")
    print("改动日志：")
    for entry in g2.change_log:
        print("  " + entry)
    print("与 Day 22 的顺序一（fold→dce）逐字节一致：3 条语句、epoch 4——今天只是把预演转正并加上类型门卫")

    print("\n== [4] 反例集中营：每一条拒绝都有名字 ==")
    for title, graph, kw in [
        ("[4a] f32：add(x, 0.0) 拒（-0.0），mul(x, 1.0) 折（安全）", FLOAT_GRAPH, {}),
        ("[4b] 类型提升：i32 × i64，没有定义过的语义不折", PROMO_GRAPH, {}),
        ("[4c] shape 不一致：(2,3) × ()——广播未建模", BCAST_GRAPH, {}),
        ("[4d] 值不合法：const 0.5 配 i32——绕开，不碰也不崩", BADVAL_GRAPH, {}),
        ("[4e] 未知 dtype q42：不认识的一律不碰", UNKNOWN_GRAPH, {}),
    ]:
        print(title)
        gx = Graph(graph)
        ok, px, _ = run_quiet(gx, **kw)
        print_decisions(px)
        print(f"  run() 返回 {ok}；{len(graph)} 条语句 → {len(gx.statements)} 条\n")

    print("== [5] 参数对照：同一张 f32 图，打开 allow_signed_zero_fp ==")
    g5 = Graph(FLOAT_GRAPH)
    ok5, p5, _ = run_quiet(g5, allow_signed_zero_fp=True)
    print_decisions(p5)
    print(f"run() 返回 {ok5}；{len(FLOAT_GRAPH)} 条语句 → {len(g5.statements)} 条")
    print(ir_dump(g5))
    print("add(x, 0.0) 也折了——开关的含义是“我保证带符号零不重要”，对应 LLVM fast-math 的 nsz；默认关")

    print("\n== [6] 溢出风险：恒等式天然免疫，“真算”才会踩雷 ==")
    i32_max = 2 ** 31 - 1
    print(f"  Python：{i32_max} + 1 = {i32_max + 1}（int 无限宽，不会替你踩刹车）")
    wrapped = struct.unpack("<i", struct.pack("<I", (i32_max + 1) & 0xFFFFFFFF))[0]
    print(f"  硬塞回 i32：{wrapped}（补码回绕）——数值已经变了")
    print("  今天的两条规则不会溢出：x+0、x*1 的结果就是 x 本身，天然可表示；")
    print("  会溢出的是 const + const 这类“真算”——那是 Day 24 的活：先查可表示，再落笔。")
    return 0


# ---------- 自测 ----------


def self_test():
    results = []

    def check(name, cond):
        results.append((name, bool(cond)))
        print(f"  {'✓' if cond else '✗'} {name}")

    print("== 自测：代数化简 Pass ==")

    # A. 常量解析：值必须按 dtype 解析
    check("const_value：i32 解析 'const 0' → 0", const_value("const 0", "i32") == 0)
    check("const_value：i32 解析 'const -3' → -3", const_value("const -3", "i32") == -3)
    check("const_value：i32 解析 'const 0.5' → None（不是整数）", const_value("const 0.5", "i32") is None)
    check("const_value：f32 解析 'const 0' → 0.0", const_value("const 0", "f32") == 0.0)
    check("const_value：f32 解析 'const 1.5' → 1.5", const_value("const 1.5", "f32") == 1.5)
    check("const_value：f32 解析 'const abc' → None", const_value("const abc", "f32") is None)
    check("const_value：未知 dtype q42 → None", const_value("const 0", "q42") is None)
    check("const_value：没有值（'const'）→ None", const_value("const", "i32") is None)

    # B. 正例：i32 图，级联一趟完成
    g = Graph(POSITIVE_GRAPH)
    pm = PassManager(print_ir="none", verbose=False)
    p = AlgebraicSimplifyPass()
    pm.add(p)
    check("正例：run 返回 True", pm.run(g) is True)
    folds = [d for d in p.decisions if d["verdict"] == "fold"]
    check("正例：一趟折 3 条（级联）", len(folds) == 3 and len(p.decisions) == 3)
    check("正例：最终 5 条语句（const 留给 DCE）", len(g.statements) == 5)
    check("正例：relu 直接读 %a", g.statements[3][2] == ["%a"])
    check("正例：output 仍读 %e", g.statements[4][2] == ["%e"])
    check("正例：epoch = 6（3 折 × 换边+删除）", g.epoch == 6 and len(g.change_log) == 6)
    check("正例：图仍合法（SSA 闸门通过）", g.validate() is True)

    # C. Day 22 连续性：同款图 + 管线
    g2 = Graph(PIPELINE_GRAPH)
    pm2 = PassManager(print_ir="none", verbose=False)
    pm2.add(AlgebraicSimplifyPass(), DcePreviewPass())
    check("管线：run 返回 True", pm2.run(g2) is True)
    check("管线：最终 3 条语句（与 Day 22 顺序一一致）", len(g2.statements) == 3)
    check("管线：只剩 input %a / relu %e / output",
          [s[0] for s in g2.statements] == ["input", "relu", "output"])
    check("管线：epoch = 4", g2.epoch == 4)
    check("管线：dce 清掉了 %zero 和 %z", all("%z" != s[1] for s in g2.statements))

    # D. 浮点反例：add 拒、mul 折
    g3 = Graph(FLOAT_GRAPH)
    ok3, p3, _ = run_quiet(g3)
    verdicts = {d["res"]: d["verdict"] for d in p3.decisions}
    check("f32：run 返回 True（拒绝不是失败）", ok3 is True)
    check("f32：add(x, 0.0) 被拒绝", verdicts.get("%s1") == "skip")
    check("f32：mul(x, 1.0) 被折叠", verdicts.get("%s2") == "fold")
    reason = next(d["reason"] for d in p3.decisions if d["res"] == "%s1")
    check("f32：拒绝原因提到 -0.0", "-0.0" in reason)
    check("f32：最终 5 条语句（add 留下）", len(g3.statements) == 5)
    check("f32：output 改读 %x（只换了 mul 那条边）", g3.statements[-1][2] == ["%s1", "%x"])

    # E. 开关对照
    g4 = Graph(FLOAT_GRAPH)
    ok4, p4, _ = run_quiet(g4, allow_signed_zero_fp=True)
    verdicts4 = {d["res"]: d["verdict"] for d in p4.decisions}
    check("开关：allow_signed_zero_fp=True 时 add 也折", verdicts4.get("%s1") == "fold")
    check("开关：最终 4 条语句", len(g4.statements) == 4)

    # F. 其余反例
    for name, graph, keyword in [
        ("类型提升：i32 × i64 拒", PROMO_GRAPH, "类型提升"),
        ("shape 广播：拒", BCAST_GRAPH, "广播"),
        ("值不合法：const 0.5 配 i32 拒且不崩", BADVAL_GRAPH, "不合法"),
        ("未知 dtype：拒", UNKNOWN_GRAPH, "不认识"),
    ]:
        gx = Graph(graph)
        ok, px, _ = run_quiet(gx)
        skipped = [d for d in px.decisions if d["verdict"] == "skip"]
        check(f"{name}（原因提到“{keyword}”）",
              ok is True and len(skipped) == 1 and keyword in skipped[0]["reason"]
              and len(gx.statements) == len(graph))

    # G. 边界：结果无人使用 / 双零常量 / 值不是单位元
    dead = Graph([
        ("input", "%x", [], ((), "i32")),
        ("const 0", "%z", [], ((), "i32")),
        ("add", "%d", ["%x", "%z"], ((), "i32")),   # %d 无人使用
        ("output", None, ["%x"], None),
    ])
    okd, pd, _ = run_quiet(dead)
    check("死结果：add 被删除且没有换边崩溃", okd is True and len(dead.statements) == 3
          and any(d["res"] == "%d" and d["verdict"] == "fold" and "无需换边" in d["reason"]
                  for d in pd.decisions))

    both = Graph([
        ("const 0", "%z1", [], ((), "i32")),
        ("const 0", "%z2", [], ((), "i32")),
        ("add", "%d", ["%z1", "%z2"], ((), "i32")),
        ("output", None, ["%d"], None),
    ])
    okb, pb, _ = run_quiet(both)
    check("双零常量：add(%z1, %z2) 折成其中一个（add(0,0)=0）",
          okb is True and len(both.statements) == 3 and both.statements[-1][2] == ["%z2"])

    wrong = Graph([
        ("input", "%x", [], ((), "i32")),
        ("const 1", "%o", [], ((), "i32")),
        ("add", "%d", ["%x", "%o"], ((), "i32")),   # 1 不是 add 的单位元
        ("mul", "%e", ["%x", "%o"], ((), "i32")),   # 1 正是 mul 的单位元
        ("output", None, ["%d", "%e"], None),
    ])
    okw, pw, _ = run_quiet(wrong)
    vw = {d["res"]: d["verdict"] for d in pw.decisions}
    check("单位元配对：add(x,1) 不折，mul(x,1) 折", vw.get("%d") == "skip" and vw.get("%e") == "fold")

    mulz = Graph([
        ("input", "%x", [], ((), "i32")),
        ("const 0", "%z", [], ((), "i32")),
        ("mul", "%d", ["%x", "%z"], ((), "i32")),   # mul(x,0)：今天没有这条规则
        ("output", None, ["%d"], None),
    ])
    okm, pmz, _ = run_quiet(mulz)
    check("陷阱守门：mul(x, 0) 不在规则表里，保持原样", okm is True and len(mulz.statements) == 4)

    # H. 溢出事实（今天学习目标的原材料）
    i32_max = 2 ** 31 - 1
    wrapped = struct.unpack("<i", struct.pack("<I", (i32_max + 1) & 0xFFFFFFFF))[0]
    check("溢出事实：Python int 不回绕（2147483647+1 = 2147483648）", i32_max + 1 == 2147483648)
    check("溢出事实：硬塞回 i32 回绕成 -2147483648", wrapped == -2147483648)
    check("溢出事实：浮点上溢到 inf（1e308*10）", 1e308 * 10 == float("inf"))

    # I. 浮点语义事实（门⑤的依据）
    nz = -0.0
    check("浮点事实：-0.0 + 0.0 的符号位丢失（copysign 可观察）",
          nz == 0.0 and nz + 0.0 == nz and math.copysign(1.0, nz + 0.0) != math.copysign(1.0, nz))
    check("浮点事实：-0.0 * 1.0 逐位不变", struct.pack("<d", nz * 1.0) == struct.pack("<d", nz))
    check("浮点事实：inf * 0.0 = nan", float("inf") * 0.0 != float("inf") * 0.0)

    passed = sum(1 for _, ok in results if ok)
    print(f"\n{passed}/{len(results)} 项通过")
    return 0 if passed == len(results) else 1


def main():
    ap = argparse.ArgumentParser(description="第 23 天演练场：代数化简 Pass（常量折叠第一步）")
    ap.add_argument("--self-test", action="store_true", help="运行自测")
    args = ap.parse_args()
    return self_test() if args.self_test else demo()


if __name__ == "__main__":
    raise SystemExit(main())
