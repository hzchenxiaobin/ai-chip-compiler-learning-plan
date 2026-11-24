#!/usr/bin/env python3
"""第 86 天：建立循环 Lowering 骨架——可运行的空 MatMul Lowering Pass ＋ 诊断测试。

本机未安装 MLIR。与 Day 57~85 的做法一致：用 Python 复刻 MLIR DialectConversion
的 **ConversionPattern / ConversionPatternRewriter / 转换失败处理** 语义（仿真），
不伪造 MLIR 本身的行为。与真实 MLIR 的对应关系（依据 mlir.llvm.org 官方文档
《Dialect Conversion》《Pattern Rewriting》，2026-11 核对）：

    MLIR 里的机制                                                     仿真里的对应
    ------------------------------------------------------------------------------
    ConversionPattern::matchAndRewrite(op, operands, rewriter)       ConversionPattern 基类
      operands/adaptor = 最近一次替换后的值（类型已合法化）              Adaptor + getRemappedValue
      失败：rewriter.notifyMatchFailure(op, reason)                   notifyMatchFailure → 调试树
    ConversionPatternRewriter（事务性：暂存 → 提交/回滚）               begin/commit/rollback 三段式
      replaceOp / replaceAllUsesWith（rollback 模式下延迟生效）          staged replacements（finalize 统一替换 uses）
      create（继承自 OpBuilder）                                        rewriter.create
    驱动器 applyFullConversion / applyPartialConversion               ConversionDriver.apply(mode)
    -debug-only=dialect-conversion 的树状调试日志                       --debug（同款格式）
    Pattern 契约（改 IR 必须走 rewriter；root 必须                        PatternContractError（仿真里
      replace/erase/in-place；失败不得留痕）                              硬失败；真实 MLIR 用
                                                                         -DMLIR_ENABLE_EXPENSIVE_PATTERN_API_CHECKS=ON 检查）

诚实声明（与真实 MLIR 的差异）：
  1. 真实 MLIR 的 rollback 模式把 replaceOp/eraseOp 延迟到**整个转换结束**才生效，
     还能回滚「已成功应用的 Pattern」（ConversionConfig::allowPatternRollback）；
     本仿真只做 Pattern 级事务（成功提交 / 失败丢弃），不模拟整条合法化路径的回溯。
  2. 真实 MLIR 的签名转换由 func 的 ConversionPattern 调 applySignatureConversion 完成；
     本仿真把它前置为驱动器的 S1 步骤（与 Day 85 的 S0→S4 路线一致）。
  3. 契约违反在真实 MLIR 默认构建里不检查（需 EXPENSIVE_PATTERN_API_CHECKS）；
     本仿真一律硬失败，方便教学。

用法：
    python3 lowering_pass.py                # 运行 DT1~DT6 诊断测试，生成 outputs/
    python3 lowering_pass.py --shape 2 3 2  # 换形状，只打印骨架与摘要（练习用）
    python3 lowering_pass.py --debug        # 额外打印主图与各案例的 dialect-conversion 风格调试树

产出：
    outputs/skeleton-ir.txt   骨架版 Lowering 后的 IR（结构就位、计算留白，预留标注 Day 87/88）
    outputs/pass-report.txt   DT1~DT6 诊断测试报告（真实运行）
    outputs/debug-log.txt     四个案例的调试树（-debug-only=dialect-conversion 风格）
"""

from __future__ import annotations

import argparse
import platform
import re
import sys
from dataclasses import dataclass
from pathlib import Path

OUT = Path(__file__).resolve().parent / "outputs"


# ============================================================ 类型工具

def row_major_strides(shape):
    """行主序 strides：最后一维为 1，往前逐维乘 shape。"""
    s = [1] * len(shape)
    for d in range(len(shape) - 2, -1, -1):
        s[d] = s[d + 1] * shape[d + 1]
    return tuple(s)


def make_memref(shape, strides=None):
    strides = tuple(strides) if strides else row_major_strides(shape)
    return (f"memref<{'x'.join(map(str, shape))}xf32, "
            f"strided<[{', '.join(map(str, strides))}]>>")


_TENSOR_RE = re.compile(r"^tensor<((?:\d+x)*\d+)xf32>$")
_MEMREF_RE = re.compile(r"^memref<((?:\d+x)*\d+)xf32, strided<\[[\d, ]+\]>>$")


def tensor_shape(t):
    m = _TENSOR_RE.match(t)
    return tuple(int(x) for x in m.group(1).split("x")) if m else None


def memref_shape(t):
    m = _MEMREF_RE.match(t)
    return tuple(int(x) for x in m.group(1).split("x")) if m else None


# ============================================================ 最小 SSA IR

class Value:
    """SSA 值：名字 + 类型；身份用对象 id。"""
    __slots__ = ("name", "type")

    def __init__(self, name, type):
        self.name, self.type = name, type

    def __repr__(self):
        return f"{self.name}: {self.type}"


class Op:
    """操作：名字 + 操作数 + 结果 + 属性 + region（body）+ 注释。"""

    def __init__(self, name, operands=(), results=(), attrs=None, body=None, comments=None):
        self.name = name
        self.operands = list(operands)
        self.results = list(results)
        self.attrs = dict(attrs or {})
        self.body = list(body or [])
        self.comments = list(comments or [])

    def walk(self):
        """先序遍历：先本 op，再进 region（与 MLIR 驱动器一致）。"""
        yield self
        for c in self.body:
            yield from c.walk()

    def descendants(self):
        for c in self.body:
            yield c
            yield from c.descendants()


def op_headline(op):
    """单行摘要（调试树里打印 op 用）。"""
    if op.name == "func.func":
        args = ", ".join(f"{v.name}: {v.type}" for v in op.attrs["args"])
        rets = ", ".join(op.attrs["result_types"])
        return f"func @{op.attrs['sym_name']}({args}) -> {rets}"
    if op.name == "func.return":
        if op.operands:
            return "return " + ", ".join(f"{v.name} : {v.type}" for v in op.operands)
        return "return"
    if op.name == "arith.constant":
        return (f"{op.results[0].name} = arith.constant {op.attrs.get('value', '?')}"
                f" : {op.results[0].type}")
    if op.name == "memref.alloc":
        return f"{op.results[0].name} = memref.alloc() : {op.results[0].type}"
    if op.name == "scf.for" and len(op.operands) >= 3:
        lo, up, st = [v.name for v in op.operands[:3]]
        return f"scf.for {op.attrs.get('iv', '?')} = {lo} to {up} step {st}"
    if op.results:
        res = ", ".join(r.name for r in op.results)
        ops = ", ".join(v.name for v in op.operands)
        return f"{res} = {op.name}({ops})"
    if op.operands:
        return f"{op.name} " + ", ".join(v.name for v in op.operands)
    return op.name


def print_module(func, header_lines=()):
    """把 func 树打印成 MLIR 风格文本。"""

    def rec(op, ind, lines):
        pad = "  " * ind
        if op.name == "func.func":
            args = ", ".join(f"{v.name}: {v.type}" for v in op.attrs["args"])
            rets = ", ".join(op.attrs["result_types"])
            lines.append(f"func @{op.attrs['sym_name']}({args}) -> {rets} {{")
            for c in op.body:
                rec(c, ind + 1, lines)
            lines.append(pad + "}")
            return
        if op.name == "scf.for":
            lo, up, st = [v.name for v in op.operands[:3]]
            lines.append(f"{pad}scf.for {op.attrs['iv']} = {lo} to {up} step {st} {{")
            for c in op.body:
                rec(c, ind + 1, lines)
            lines.append(pad + "}")
        elif op.name == "func.return":
            if op.operands:
                lines.append(f"{pad}return {op.operands[0].name} : {op.operands[0].type}")
            else:
                lines.append(pad + "return")
        elif op.name == "arith.constant":
            lines.append(f"{pad}{op.results[0].name} = arith.constant {op.attrs['value']}"
                         f" : {op.results[0].type}")
        elif op.name == "memref.alloc":
            lines.append(f"{pad}{op.results[0].name} = memref.alloc() : {op.results[0].type}")
        elif op.name == "scf.yield":
            lines.append(pad + "scf.yield")
        else:
            lines.append(pad + op_headline(op))
        for cm in op.comments:
            lines.append(f"{pad}// {cm}")

    lines = list(header_lines)
    rec(func, 0, lines)
    return "\n".join(lines) + "\n"


class TypeConverter:
    """tensor → memref（行主序 strides）；其余类型原样通过。"""

    def convertType(self, t):
        shape = tensor_shape(t)
        if shape is not None:
            return make_memref(shape)
        return t


# ============================================================ Pattern / Rewriter

class PatternContractError(Exception):
    """违反 Pattern 契约（改 IR 不走 rewriter / root 未处置 / 失败留痕）。"""


class _ContractFatal(Exception):
    """契约违反升级为整个转换的硬失败（携带诊断信息）。"""


@dataclass
class Adaptor:
    """ConversionPattern 拿到的操作数：已经是「最近一次替换后的值」。

    对应 MLIR 的 Remapped Operands / Adaptor：配了 TypeConverter 时，
    这些值的类型就是合法化之后的类型（比如已经是 memref）。
    """
    operands: list


class ConversionPattern:
    """翻译规则基类。子类实现 matchAndRewrite，返回 True=成功（IR 已改），False=失败。"""
    root_name: str = ""      # 匹配的根 op 名；空串相当于 MatchAnyOpTypeTag
    benefit: int = 1         # 同一 root 有多条 Pattern 时，benefit 大的先试
    debug_name: str = "ConversionPattern"

    def matchAndRewrite(self, op, adaptor, rewriter):
        raise NotImplementedError


class _Txn:
    """一次 Pattern 应用的事务暂存区：create/replace 先记在这里。"""

    def __init__(self):
        self.created = []          # 本次事务里 create 的 op（含嵌套在 body 里的）
        self.replacements = {}     # 旧 result Value -> 新 Value
        self.disposed = None       # 被 replaceOp/eraseOp 处置的 root op


class ConversionPatternRewriter:
    """事务性改写器：所有修改先暂存，Pattern 成功才 commit，失败 rollback（不留痕）。"""

    def __init__(self, driver):
        self.driver = driver
        self.global_replacements = {}   # 延迟替换映射：finalize 时统一改 uses
        self._txn = None
        self._pattern_name = "?"
        self.last_created = []          # 最近一次 commit 提交的 op（调试树用）

    # ---- 事务控制（驱动器调用；Pattern 不许碰） ----
    def begin(self):
        self._txn = _Txn()

    def commit(self, root_op):
        txn = self._txn
        if txn.disposed is not root_op:
            self.rollback()
            raise PatternContractError(
                f"Pattern '{self._pattern_name}' 返回成功，但 root op '{root_op.name}' "
                f"既未被 replaceOp 也未被 eraseOp（契约：root 必须 in-place 更新/替换/擦除）")
        if txn.replacements:
            # replaceOp 路径：新建 op 顶替 root 的位置（替换＋擦除一步完成）
            nested_ids = set()
            for o in txn.created:
                for d in o.descendants():
                    nested_ids.add(id(d))
            top = [o for o in txn.created if id(o) not in nested_ids]
            body = self.driver.body_of(root_op)
            idx = body.index(root_op)
            body[idx:idx + 1] = top
            self.global_replacements.update(txn.replacements)
        else:
            # eraseOp 路径：root 无结果或结果无使用，直接移除
            body = self.driver.body_of(root_op)
            body.remove(root_op)
        self.last_created = list(txn.created)
        self._txn = None

    def rollback(self):
        self._txn = None    # 暂存的 create/replace 全部丢弃 → 失败不留痕

    # ---- Pattern 使用的 API ----
    def create(self, name, operands=(), result_names=(), result_types=(),
               attrs=None, body=None, comments=None):
        if self._txn is None:
            raise PatternContractError("create 必须在 matchAndRewrite 事务内调用")
        results = [Value(n, t) for n, t in zip(result_names, result_types)]
        op = Op(name, list(operands), results, attrs, body, comments)
        self._txn.created.append(op)
        return op

    def replaceOp(self, op, new_values):
        if len(op.results) != len(new_values):
            raise PatternContractError(
                f"replaceOp：结果数不匹配（{len(op.results)} 个结果 vs {len(new_values)} 个新值）")
        for old, new in zip(op.results, new_values):
            self._txn.replacements[old] = new
        self._txn.disposed = op

    def eraseOp(self, op):
        """今天的主线用 replaceOp；eraseOp 作为契约里的另一条处置路径提供。"""
        self._txn.disposed = op

    def notifyMatchFailure(self, op, reason):
        """Pattern 级失败：记录原因，返回 False（对应 MLIR 返回 failure()）。

        展示方式由驱动器决定——dialect conversion 把它放进
        -debug-only=dialect-conversion 的调试树；普通运行默认不打印。
        """
        self.driver.match_failures.append((op, reason))
        return False

    def getRemappedValue(self, v):
        """取「最近一次替换后的值」（adaptor 机制的底座）。"""
        seen = set()
        while v in self.global_replacements and id(v) not in seen:
            seen.add(id(v))
            v = self.global_replacements[v]
        return v

    def finalize(self, func):
        """延迟替换：转换结束后统一更新所有 uses（对应 rollback 模式的 delayed replacement）。"""
        for op in func.walk():
            op.operands = [self.getRemappedValue(v) for v in op.operands]
            if op.name == "func.func":
                op.attrs["args"] = [self.getRemappedValue(a) for a in op.attrs["args"]]


# ============================================================ 合法性目标

TARGET_LEGAL = {
    "func.func", "func.return",
    "memref.alloc", "memref.fill", "memref.load", "memref.store",
    "scf.for", "scf.yield",
    "arith.constant", "arith.mulf", "arith.addf",
    "bufferization.to_tensor", "bufferization.to_memref",
}


@dataclass
class ConversionResult:
    ok: bool
    mode: str
    message: str
    residue: list
    log: list            # 普通运行可见的改写日志
    debug_lines: list    # --debug 调试树（对应 -debug-only=dialect-conversion）


class ConversionDriver:
    """驱动器仿真：先序遍历 → 非法 op 逐条试 Pattern → 收敛或失败。"""

    def __init__(self, patterns, type_converter, debug=False):
        self.patterns = sorted(patterns, key=lambda p: -p.benefit)  # benefit 大的先试
        self.tc = type_converter
        self.rewriter = ConversionPatternRewriter(self)
        self.debug = debug
        self.debug_lines = []
        self.match_failures = []
        self.legalization_log = []
        self.mode = "full"
        self._failure_msg = ""
        self._func = None

    # ---- 调试树 ----
    def dbg(self, line):
        if self.debug:
            self.debug_lines.append(line)

    def body_of(self, op):
        for cand in self._func.walk():
            for c in cand.body:
                if c is op:
                    return cand.body
        raise RuntimeError(f"op {op.name} 不在任何 body 里（IR 已损坏？）")

    # ---- 入口 ----
    def apply(self, func, mode="full"):
        self.mode = mode
        self._func = func
        self._convert_signature(func)
        self.dbg("//===-------------------------------------------===//")
        self.dbg("Legalizing operation : 'func.func' {")
        self.dbg(f"  {op_headline(func)}")
        self.dbg("} -> SUCCESS : operation marked legal by the target")
        try:
            residue = self._legalize(func.body)
        except _ContractFatal as exc:
            return ConversionResult(False, mode, str(exc), [],
                                    self.legalization_log, self.debug_lines)
        if residue is None:      # full 模式整体失败
            return ConversionResult(False, mode, self._failure_msg, [],
                                    self.legalization_log, self.debug_lines)
        if self.mode == "full" and residue:
            return ConversionResult(False, mode, self._failure_msg, sorted(set(residue)),
                                    self.legalization_log, self.debug_lines)
        if residue:
            # partial 成功：残留明示
            self.rewriter.finalize(func)
            final = list(func.walk())
            msg = (f"partial 模式完成：终图 {len(final)} op，"
                   f"显式残留 {sorted(set(residue))}（交给后续 Pass）")
            return ConversionResult(True, mode, msg, sorted(set(residue)),
                                    self.legalization_log, self.debug_lines)
        self.rewriter.finalize(func)
        final = list(func.walk())
        msg = f"转换完成（模式={self.mode}）：终图 {len(final)} op，残留非法 op = 无"
        return ConversionResult(True, mode, msg, [],
                                 self.legalization_log, self.debug_lines)

    def _convert_signature(self, func):
        """S1 签名转换（真实 MLIR 由 func 的 Pattern 调 applySignatureConversion）。"""
        letters = "abcdefgh"
        new_args = []
        for idx, old in enumerate(func.attrs["args"]):
            new_t = self.tc.convertType(old.type)
            if new_t == old.type:
                new_args.append(old)
                continue
            new_v = Value(f"%{letters[idx]}", new_t)
            self.rewriter.global_replacements[old] = new_v
            new_args.append(new_v)
        func.attrs["args"] = new_args
        func.attrs["result_types"] = [self.tc.convertType(t) for t in func.attrs["result_types"]]

    def _legalize(self, body):
        """先序处理一个 body。返回残留 op 名列表；full 模式失败时返回 None。"""
        residue = []
        i = 0
        while i < len(body):
            op = body[i]
            if op.name in TARGET_LEGAL:
                self.dbg("//===-------------------------------------------===//")
                self.dbg(f"Legalizing operation : '{op.name}' {{")
                self.dbg(f"  {op_headline(op)}")
                self.dbg("} -> SUCCESS : operation marked legal by the target")
                sub = self._legalize(op.body)
                if sub is None:
                    return None
                residue += sub
                i += 1
                continue
            status = self._try_patterns(op)
            if status == "applied":
                continue          # 新 op 已顶替原位置：i 不动，重新检查当前位置
            if self.mode == "full":
                return None       # 整体失败（信息已在 _try_patterns 里记下）
            residue.append(op.name)
            i += 1
        return residue

    def _try_patterns(self, op):
        self.dbg("//===-------------------------------------------===//")
        self.dbg(f"Legalizing operation : '{op.name}' {{")
        self.dbg(f"  {op_headline(op)}")
        self.dbg("")
        cands = [p for p in self.patterns if p.root_name in (op.name, "")]
        if not cands:
            self._failure_msg = (f"无法合法化 '{op.name}'：没有注册对应的 "
                                 f"ConversionPattern（模式={self.mode}，整体失败）")
            self.dbg(f"}} -> FAILURE : {self._failure_msg}")
            return "none"
        for pat in cands:
            self.dbg(f"  * Pattern : '{pat.debug_name}' {{")
            self.rewriter.begin()
            self.rewriter._pattern_name = pat.debug_name
            adaptor = Adaptor([self.rewriter.getRemappedValue(v) for v in op.operands])
            try:
                ok = pat.matchAndRewrite(op, adaptor, self.rewriter)
                if ok:
                    self.rewriter.commit(op)
            except PatternContractError as exc:
                self.rewriter.rollback()
                self.dbg("  } -> FAILURE : 契约违反")
                raise _ContractFatal(f"契约违反：{exc}") from exc
            if ok:
                for created in self.rewriter.last_created:
                    self.dbg(f"    ** Insert  : '{created.name}'")
                self.dbg(f"    ** Replace : '{op.name}'")
                self.dbg("  } -> SUCCESS : pattern applied successfully")
                self.dbg("} -> SUCCESS")
                self.legalization_log.append(
                    f"rewrite '{op.name}' -> {len(self.rewriter.last_created)} 个目标 op"
                    f"（{pat.debug_name}）")
                return "applied"
            # Pattern 拒绝：回滚，试下一条
            self.rewriter.rollback()
            reason = (self.match_failures[-1][1] if self.match_failures
                      else "（静默 return failure，无诊断）")
            self.dbg(f"  }} -> FAILURE : {reason}")
        self._failure_msg = (f"无法合法化 '{op.name}'：已注册的 Pattern 都拒绝了这次匹配"
                             f"（拒绝原因默认只在 --debug 调试树里；模式={self.mode}，整体失败）")
        self.dbg(f"}} -> FAILURE : {self._failure_msg}")
        return "none"


# ============================================================ 骨架 Pattern

class MatMulSkeletonPattern(ConversionPattern):
    """骨架版 mini.matmul → 循环表示：结构就位、计算留白（Day 87/88 再填肉）。

    match 阶段只做「能不能翻」的判断，不碰 IR；
    rewrite 阶段一切修改走 rewriter（暂存，成功才提交）。
    """

    root_name = "mini.matmul"
    benefit = 1
    debug_name = "MatMulSkeletonPattern"

    def __init__(self):
        self.seen_adaptor = None      # DT3 检查用：pattern 实际拿到的操作数

    def matchAndRewrite(self, op, adaptor, rewriter):
        self.seen_adaptor = list(adaptor.operands)
        # ---------- match：条件不满足就大声拒绝（notifyMatchFailure），不留痕 ----------
        if len(adaptor.operands) != 2:
            return rewriter.notifyMatchFailure(
                op, f"期望 2 个操作数，实际 {len(adaptor.operands)} 个")
        ta, tb = adaptor.operands[0].type, adaptor.operands[1].type
        sa, sb = memref_shape(ta), memref_shape(tb)
        if sa is None or sb is None:
            return rewriter.notifyMatchFailure(
                op, f"操作数还不是 memref（拿到 {ta} / {tb}）——检查签名转换/TypeConverter")
        if len(sa) != 2 or len(sb) != 2:
            return rewriter.notifyMatchFailure(
                op, f"只支持 2 维矩阵乘，拿到 A{sa} @ B{sb}")
        if sa[1] != sb[0]:
            return rewriter.notifyMatchFailure(
                op, f"内维不匹配：A.shape[1]={sa[1]} ≠ B.shape[0]={sb[0]}，k 循环边界无从确定")
        M, K = sa
        N = sb[1]

        # ---------- rewrite：一切修改走 rewriter，先暂存 ----------
        used = set()

        def cname(v):
            n = f"%c{v}"
            while n in used:
                n += "'"
            used.add(n)
            return n

        alloc = rewriter.create(
            "memref.alloc", result_names=["%c"], result_types=[make_memref((M, N))],
            comments=["骨架① 输出缓冲：Day 85 任务清单①的类型表"])
        consts = [rewriter.create("arith.constant", result_names=[cname(v)],
                                  result_types=["index"], attrs={"value": v})
                  for v in (0, 1, M, N, K)]
        for c, note in zip(consts, ["下界 0", "步长 1", "M ← A.shape[0]",
                                     "N ← B.shape[1]", "K ← 内维契约 A.shape[1]==B.shape[0]"]):
            c.comments.append(note)
        lo, st, bm, bn, bk = [c.results[0] for c in consts]
        yld = rewriter.create(
            "scf.yield",
            comments=["骨架占位：循环体留白",
                      "预留(Day 87 填): %zero = arith.constant 0.0 + iter_args(%acc = %zero)",
                      "预留(Day 88 填): load %a[%i,%k] · load %b[%k,%j] · mulf · addf · yield %s · store %c[%i,%j]"])
        # 从内向外创建（body 引用已创建的 op）——创建顺序 = 调试树 Insert 顺序
        fk = rewriter.create("scf.for", operands=[lo, bk, st], attrs={"iv": "%k"}, body=[yld])
        fj = rewriter.create("scf.for", operands=[lo, bn, st], attrs={"iv": "%j"}, body=[fk])
        fi = rewriter.create("scf.for", operands=[lo, bm, st], attrs={"iv": "%i"}, body=[fj])
        # ---------- 处置 root：结果 %mm(tensor) → %c(memref)；uses 延迟到 finalize 替换 ----------
        rewriter.replaceOp(op, [alloc.results[0]])
        return True


class HalfDoneMatMulPattern(ConversionPattern):
    """反面教材①：先 create 再放弃——验证「失败不留痕」的回滚（DT6）。"""

    root_name = "mini.matmul"
    benefit = 2
    debug_name = "HalfDoneMatMulPattern"

    def matchAndRewrite(self, op, adaptor, rewriter):
        rewriter.create("memref.alloc", result_names=["%bad"],
                        result_types=["memref<4x3xf32, strided<[3, 1]>>"])
        return rewriter.notifyMatchFailure(
            op, "故意半途而废：先 create 了 memref.alloc 再放弃（测试回滚：失败必须不留痕）")


class ForgetfulMatMulPattern(ConversionPattern):
    """反面教材②：返回成功却忘了 replaceOp——验证 root 处置契约（DT6）。"""

    root_name = "mini.matmul"
    benefit = 3
    debug_name = "ForgetfulMatMulPattern"

    def matchAndRewrite(self, op, adaptor, rewriter):
        rewriter.create("memref.alloc", result_names=["%bad"],
                        result_types=["memref<4x3xf32, strided<[3, 1]>>"])
        return True    # 忘了 rewriter.replaceOp(...)！


# ============================================================ 测试图构造

def build_main_graph(M=4, K=6, N=3):
    """S0 源图：Day 83 终图 GEMM 的形状（与 Day 85 贯穿例子一致）。"""
    x = Value("%x", f"tensor<{M}x{K}xf32>")
    w = Value("%w", f"tensor<{K}x{N}xf32>")
    mm = Value("%mm", f"tensor<{M}x{N}xf32>")
    matmul = Op("mini.matmul", [x, w], [mm])
    ret = Op("func.return", [mm])
    return Op("func.func", body=[matmul, ret],
              attrs={"sym_name": "main", "args": [x, w],
                     "result_types": [f"tensor<{M}x{N}xf32>"]})


def build_conv_graph(M=4, K=6, N=3):
    """含 mini.conv（没有 Pattern）的变体——测驱动器级失败（DT4）。"""
    x = Value("%x", f"tensor<{M}x{K}xf32>")
    w = Value("%w", f"tensor<{K}x{N}xf32>")
    r = Value("%r", f"tensor<{M}x{N}xf32>")
    mm = Value("%mm", f"tensor<{M}x{N}xf32>")
    conv = Op("mini.conv", [x, w], [r])
    matmul = Op("mini.matmul", [x, w], [mm])
    ret = Op("func.return", [mm])
    return Op("func.func", body=[conv, matmul, ret],
              attrs={"sym_name": "main", "args": [x, w],
                     "result_types": [f"tensor<{M}x{N}xf32>"]})


def build_bad_inner_graph(M=4, K=6, bad_k=3, bad_n=2):
    """前端没把好关的图：A(4,6) @ B(3,2)，内维 6≠3——测 Pattern 级失败（DT5）。"""
    x = Value("%x", f"tensor<{M}x{K}xf32>")
    w = Value("%w", f"tensor<{bad_k}x{bad_n}xf32>")
    mm = Value("%mm", f"tensor<{M}x{bad_n}xf32>")
    matmul = Op("mini.matmul", [x, w], [mm])
    ret = Op("func.return", [mm])
    return Op("func.func", body=[matmul, ret],
              attrs={"sym_name": "main", "args": [x, w],
                     "result_types": [f"tensor<{M}x{bad_n}xf32>"]})


def run_pass(func, mode="full", extra=(), debug=False):
    """跑一次骨架版 MatMul Lowering Pass。返回 (pattern, result)。"""
    pat = MatMulSkeletonPattern()
    driver = ConversionDriver([pat, *extra], TypeConverter(), debug=debug)
    res = driver.apply(func, mode)
    return pat, res


EXPECTED_SKELETON = (["func.func", "memref.alloc"] + ["arith.constant"] * 5
                     + ["scf.for"] * 3 + ["scf.yield", "func.return"])


# ============================================================ 诊断测试 DT1~DT6

def dt1_match_and_replace(func, res, before_names):
    """DT1 匹配与替换：主图转换成功，mini 方言清零，op 数 3 → 12。"""
    after = [op.name for op in func.walk()]
    ok = (res.ok and after == EXPECTED_SKELETON
          and not any(n.startswith("mini.") for n in after))
    lines = [f"  转换前 {len(before_names)} op：{', '.join(before_names)}",
             f"  full 模式：{'成功' if res.ok else '失败'}——{res.message}",
             f"  转换后 {len(after)} op：func.func + 骨架 10 op（alloc 1 ＋ constant 5 ＋ for 3 ＋ yield 1）＋ func.return",
             f"  op 序列与预期骨架完全一致：{after == EXPECTED_SKELETON}",
             f"  mini 方言残留：{[n for n in after if n.startswith('mini.')] or '无'}",
             f"  改写日志：{'；'.join(res.log)}"]
    return ok, lines


def dt2_skeleton_structure(func):
    """DT2 骨架结构：alloc 类型/strides、5 个常量、三重 for 的边界与嵌套、yield 占位。"""
    body = func.body
    alloc, consts, fi = body[0], body[1:6], body[6]
    fj, fk, yld = fi.body[0], fi.body[0].body[0], fi.body[0].body[0].body[0]
    val_of = {id(c.results[0]): c.attrs["value"] for c in consts}
    bounds = [val_of[id(f.operands[1])] for f in (fi, fj, fk)]
    cvals = sorted(c.attrs["value"] for c in consts)
    ok = (alloc.name == "memref.alloc"
          and alloc.results[0].type == make_memref((4, 3))
          and cvals == [0, 1, 3, 4, 6]
          and bounds == [4, 3, 6]
          and [f.attrs["iv"] for f in (fi, fj, fk)] == ["%i", "%j", "%k"]
          and all(f.operands[0].name == "%c0" and f.operands[2].name == "%c1"
                  for f in (fi, fj, fk))
          and yld.name == "scf.yield" and not yld.operands)
    lines = [f"  alloc：%c : {alloc.results[0].type}（48 B，strides 与 Day 85 任务清单①一致）",
             f"  常量值集合 = {cvals}（下界 0、步长 1、M=4←A.shape[0]、N=3←B.shape[1]、K=6←内维契约）",
             f"  循环边界：i ∈ [0,{bounds[0]})、j ∈ [0,{bounds[1]})、k ∈ [0,{bounds[2]})，全部编译期可知",
             f"  嵌套深度 3：for %i ⊃ for %j ⊃ for %k ⊃ scf.yield（占位，无操作数）",
             f"  三条循环共用下界 %c0 / 步长 %c1，上界分别是 %c4 / %c3 / %c6"]
    return ok, lines


def dt3_adaptor_and_types(func, pattern):
    """DT3 类型缝合：adaptor 拿到的是已转换的 memref 操作数；终图无 tensor、无悬空引用。"""
    seen = pattern.seen_adaptor
    adaptor_ok = (seen is not None and len(seen) == 2
                  and seen[0].name == "%a" and seen[1].name == "%b"
                  and seen[0].type == make_memref((4, 6))
                  and seen[1].type == make_memref((6, 3)))
    all_vals = list(func.attrs["args"])
    for op in func.walk():
        all_vals += op.results
    tensor_left = [v.name for v in all_vals if v.type.startswith("tensor<")]
    rets_tensor = [t for t in func.attrs["result_types"] if t.startswith("tensor<")]
    defined = {id(v) for v in func.attrs["args"]}
    for op in func.walk():
        defined |= {id(r) for r in op.results}
    dangling = [v.name for op in func.walk() for v in op.operands if id(v) not in defined]
    ret_op = func.body[-1]
    ret_ok = ret_op.name == "func.return" and ret_op.operands[0].name == "%c"
    ok = adaptor_ok and not tensor_left and not rets_tensor and not dangling and ret_ok
    lines = [f"  adaptor 给 Pattern 的操作数：{[f'{v.name}: {v.type}' for v in (seen or [])]}",
             f"  ——是签名转换后的 %a/%b（memref），不是原始的 %x/%w（tensor）：{adaptor_ok}",
             f"  终图残留 tensor 类型：{tensor_left or '无'}（函数结果类型 {func.attrs['result_types']}）",
             f"  悬空引用（uses 指向已消失的值）：{dangling or '无'}——延迟替换在 finalize 统一完成",
             f"  func.return 的操作数：{ret_op.operands[0].name}（{ret_op.operands[0].type}）"]
    return ok, lines


def dt4_driver_level_failure():
    """DT4 驱动器级失败：mini.conv 无 Pattern——full 大声点名，partial 显式残留。"""
    lines, ok = [], True
    f1 = build_conv_graph()
    _, r1 = run_pass(f1, "full")
    good = (not r1.ok and "无法合法化 'mini.conv'" in r1.message
            and "没有注册对应的 ConversionPattern" in r1.message)
    ok &= good
    lines.append(f"  full 模式：{'按预期整体失败' if good else '意外成功'} → {r1.message}")
    f2 = build_conv_graph()
    _, r2 = run_pass(f2, "partial")
    good2 = (r2.ok and r2.residue == ["mini.conv"]
             and not any(op.name == "mini.matmul" for op in f2.walk()))
    ok &= good2
    lines.append(f"  partial 模式：{'成功' if r2.ok else '失败'}，显式残留 {r2.residue}"
                 f"（mini.matmul 已被转换，conv 留给后续 Pass）")
    lines.append("  失败要大声：full 指名道姓，partial 把残留摆上台面——都不许悄悄吞掉")
    return ok, lines


def dt5_pattern_level_failure():
    """DT5 Pattern 级失败：内维不匹配 → notifyMatchFailure。

    拒绝原因默认只在调试树里（--debug），普通运行不打印；full 模式整体失败。
    """
    lines, ok = [], True
    f1 = build_bad_inner_graph()
    _, r1 = run_pass(f1, "full", debug=True)
    good = (not r1.ok and "无法合法化 'mini.matmul'" in r1.message
            and "都拒绝了这次匹配" in r1.message)
    ok &= good
    lines.append(f"  A(4,6) @ B(3,2)（内维 6≠3），full 模式：{'按预期失败' if not r1.ok else '意外成功'}")
    lines.append(f"  驱动器诊断：{r1.message}")
    dbg_text = "\n".join(r1.debug_lines)
    in_debug = "内维不匹配：A.shape[1]=6 ≠ B.shape[0]=3" in dbg_text
    ok &= in_debug
    lines.append(f"  --debug 调试树含拒绝原因（notifyMatchFailure 的 remark）：{in_debug}")
    f2 = build_bad_inner_graph()
    _, r2 = run_pass(f2, "full", debug=False)
    visible = r2.message + "\n".join(r2.log)
    silent = "内维不匹配" not in visible
    ok &= silent
    lines.append(f"  普通运行（不带 --debug）不打印拒绝原因：{silent}"
                 "（展示方式由驱动器决定——这是设计，不是丢消息）")
    return ok, lines, r1.debug_lines


def dt6_atomicity_and_contract():
    """DT6 原子性与契约：半途而废回滚无痕；忘 replaceOp 触发契约诊断。"""
    lines, ok = [], True
    # A. 坏 Pattern（benefit 高先试）失败回滚后，好 Pattern 接手 → 与只用好 Pattern 的结果逐字一致
    f1 = build_main_graph()
    _, r1 = run_pass(f1, "full", extra=[HalfDoneMatMulPattern()], debug=True)
    ir1 = print_module(f1)
    f2 = build_main_graph()
    run_pass(f2, "full")
    ir2 = print_module(f2)
    same = ir1 == ir2
    ok &= r1.ok and same
    lines.append(f"  A. [HalfDone(benefit=2) → 拒绝并回滚] ＋ [Skeleton(benefit=1) → 接手]："
                 f"{'成功' if r1.ok else '失败'}，终图与只用 Skeleton 的结果逐字相同：{same}")
    dbg_text = "\n".join(r1.debug_lines)
    has_remark = "半途而废" in dbg_text
    ok &= has_remark
    lines.append(f"     回滚证据：调试树里先见 FAILURE（{has_remark}），终图却无 %bad 半成品残留")
    # B. 只注册坏 Pattern：转换失败，且 body 一字不动（失败不留痕）
    f3 = build_main_graph()
    before_names = [op.name for op in f3.walk()]
    driver_b = ConversionDriver([HalfDoneMatMulPattern()], TypeConverter(), debug=True)
    r3 = driver_b.apply(f3, "full")
    after_names = [op.name for op in f3.walk()]
    stray = [n for n in after_names if n == "memref.alloc" or n.startswith("scf.")]
    body_ok = (not r3.ok and after_names == before_names and not stray)
    ok &= body_ok
    lines.append(f"  B. 只注册 HalfDone：full 模式失败 → {r3.message}")
    lines.append(f"     失败后 IR 的 op 序列 = {after_names}（与转换前相同：{after_names == before_names}），"
                 f"骨架半成品残留 = {stray or '无'}")
    # C. 忘 replaceOp：返回成功却没处置 root → 契约硬失败
    f4 = build_main_graph()
    driver_c = ConversionDriver([ForgetfulMatMulPattern(), MatMulSkeletonPattern()],
                                TypeConverter(), debug=True)
    r4 = driver_c.apply(f4, "full")
    good_c = (not r4.ok and "契约违反" in r4.message
              and "既未被 replaceOp 也未被 eraseOp" in r4.message)
    ok &= good_c
    lines.append(f"  C. Forgetful 返回成功但忘了 replaceOp：{'契约硬失败' if good_c else '未被抓住'}")
    lines.append(f"     诊断：{r4.message}")
    lines.append("     （真实 MLIR 默认构建不查这条契约，需 -DMLIR_ENABLE_EXPENSIVE_PATTERN_API_CHECKS=ON）")
    return ok, lines, driver_b.debug_lines, r4.debug_lines


# ============================================================ 报告与产出

def env_line():
    return (f"{platform.system()} {platform.machine()}, Python {platform.python_version()}; "
            f"本机未安装 MLIR（DialectConversion 语义仿真，不伪造 MLIR 行为）")


SKELETON_HEADER = [
    "// 生成自 lowering_pass.py（Day 86）——骨架版 MatMul Lowering Pass 的输出",
    "// 结构就位、计算留白：匹配 ✓、骨架 ✓、类型缝合 ✓；数值等价留给 Day 88 之后",
    "// 与 Day 85 ir-loop.txt 对照：完整目标 = 本骨架 10 op ＋ 待填 6 op（%zero、load×2、mulf、addf、store）",
]


def build_report(results):
    lines = ["Day 86 骨架版 MatMul Lowering Pass·诊断测试报告（真实运行）",
             f"环境：{env_line()}", ""]
    for name, ok, detail in results:
        lines.append(f"[{'PASS' if ok else 'FAIL'}] {name}")
        lines.extend(detail)
        lines.append("")
    n_pass = sum(1 for _, ok, _ in results if ok)
    lines.append(f"—— 诊断测试 {n_pass}/{len(results)} PASS ——")
    lines.append("")
    lines.append("口径附注：")
    lines.append("  1. op 计数按 SSA op 精确到每个常量：主图 3 op → 终图 12 op（骨架 10 目标 op）。")
    lines.append("     Day 85 的 op 名级仿真记 14 op（5 个 index 常量算 1 条、完整目标含 12 条目）；")
    lines.append("     换算到同一口径：完整目标 = 骨架 10 ＋ 待填 6 = 16 目标 op（全函数 18 op）。")
    lines.append("  2. 今天的验收是结构性的（匹配/骨架/类型/诊断）；骨架不做数值计算，")
    lines.append("     执行等价（TP 系列位等价检查）从 Day 87 起逐块补上。")
    lines.append("  3. 与真实 MLIR 的差异见脚本头部「诚实声明」：rollback 深度、签名转换前置、契约检查策略。")
    return "\n".join(lines)


def build_debug_log(cases):
    out = ["Day 86 调试树汇总（--debug，对应 MLIR -debug-only=dialect-conversion 的格式）", ""]
    for title, lines in cases:
        out.append(f"—— {title} ——")
        out.extend(lines)
        out.append("")
    return "\n".join(out)


def run_all():
    # 主运行：一次转换，DT1~DT3 共享同一个 func / pattern / result
    func = build_main_graph()
    before_names = [op.name for op in func.walk()]
    pattern = MatMulSkeletonPattern()
    driver = ConversionDriver([pattern], TypeConverter(), debug=True)
    res = driver.apply(func, "full")

    results = []
    ok, lines = dt1_match_and_replace(func, res, before_names)
    results.append(("DT1 匹配与替换", ok, lines))
    ok, lines = dt2_skeleton_structure(func)
    results.append(("DT2 骨架结构", ok, lines))
    ok, lines = dt3_adaptor_and_types(func, pattern)
    results.append(("DT3 类型缝合（adaptor）", ok, lines))

    ok, lines = dt4_driver_level_failure()
    results.append(("DT4 驱动器级失败", ok, lines))

    ok, lines, dbg5 = dt5_pattern_level_failure()
    results.append(("DT5 Pattern 级失败", ok, lines))

    ok, lines, dbg_b, dbg_c = dt6_atomicity_and_contract()
    results.append(("DT6 原子性与契约", ok, lines))

    skeleton_ir = print_module(func, SKELETON_HEADER)
    debug_log = build_debug_log([
        ("案例 1：主图正常路径（匹配 → 骨架落地）", driver.debug_lines),
        ("案例 2：内维不匹配，Pattern 拒绝（DT5）", dbg5),
        ("案例 3：半途而废 Pattern，回滚（DT6-B）", dbg_b),
        ("案例 4：忘 replaceOp，契约违反（DT6-C）", dbg_c),
    ])
    return results, skeleton_ir, debug_log


def practice_mode(M, K, N):
    func = build_main_graph(M, K, N)
    _, res = run_pass(func, "full")
    print(f"形状 A({M},{K}) @ B({K},{N}) -> C({M},{N})")
    print(f"转换：{'成功' if res.ok else '失败'}——{res.message}")
    print()
    print(print_module(func, [
        f"// 练习模式：A({M},{K}) @ B({K},{N}) -> C({M},{N}) 的骨架（真实运行输出）"]))
    walk = [op.name for op in func.walk()]
    print(f"op 序列（{len(walk)} op）：{', '.join(walk)}")
    return 0 if res.ok else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--shape", nargs=3, type=int, metavar=("M", "K", "N"),
                    help="改写贯穿例子的形状（默认 4 6 3）；练习模式只打印，不生成产出")
    ap.add_argument("--debug", action="store_true",
                    help="额外把调试树汇总打印到 stdout")
    args = ap.parse_args()

    if args.shape:
        return practice_mode(*args.shape)

    results, skeleton_ir, debug_log = run_all()
    report = build_report(results)

    OUT.mkdir(exist_ok=True)
    (OUT / "skeleton-ir.txt").write_text(skeleton_ir, encoding="utf-8")
    (OUT / "pass-report.txt").write_text(report + "\n", encoding="utf-8")
    (OUT / "debug-log.txt").write_text(debug_log + "\n", encoding="utf-8")

    print(report)
    if args.debug:
        print()
        print(debug_log)
    print()
    print("skeleton-ir.txt / pass-report.txt / debug-log.txt 已写入 outputs/")
    all_ok = all(ok for _, ok, _ in results)
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
