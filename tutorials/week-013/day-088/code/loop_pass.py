#!/usr/bin/env python3
"""第 88 天：生成三重循环——上界、下界、步长与归纳变量的准确语义。

本机未安装 MLIR。与 Day 57~87 的做法一致：用 Python 复刻 MLIR DialectConversion
的 Pattern / Rewriter / 驱动器语义（仿真），并在 Day 87 解释执行器上新增两个探针：
IV 轨迹（归纳变量实际取值）与按维越界检测。不伪造 MLIR 本身的行为。
与真实 MLIR 的对应关系（依据 mlir.llvm.org 官方文档《Dialect Conversion》
《scf dialect》，2026-11 核对）：

    MLIR scf.for 的官方语义                                       仿真里的对应
    ------------------------------------------------------------------------------
    半开区间 [lb, ub)：含下界、不含上界                            exec_for 用 range(lb, ub, st)
    trip = max(0, ceil((ub - lb) / step))，iv 取 lb + j·step        LoopSpec + trip_count()
    step 必须严格为正（官方要求）                                   exec_for 的 st <= 0 防御
    iv 是循环区域的第一个参数（BlockArgument），iter_args 跟随其后    attrs["iv_value"] + attrs["iter_args"]
    体外使用 iv 由 verifier 的支配性检查拒绝                         BT3 用结构断言（体外无引用）
    循环体单个 block 以 scf.yield 结尾；无结果时可隐式插入终止器       k 循环显式 yield；中外层隐式
    动态 shape：边界无法物化为常量 → 保守拒绝                        match 检测 '?'（Day 87 机制沿用）

诚实声明（与真实 MLIR 的差异）：
  1. 真实 scf.for 的 iv/iter_args 是区域入口块参数（BlockArgument）；
     本仿真用 attrs 里预建的 Value 对象模拟（Day 87 起的做法）。
  2. 真实 MLIR 对「体外使用 iv」由支配性检查在 verifier 阶段拒绝；
     本仿真的 env 是平铺字典，不做运行期支配检查——BT3 改用结构断言。
  3. 按维越界检测是本仿真新增的探针（真实工程里对应运行期边界检查 /
     sanitizer 一类工具）：线性地址仍在缓冲区内 ≠ 下标合法——这是
     stride 类 bug 的共性（Day 85 探针 P1 同款教训）。

用法：
    python3 loop_pass.py                # 运行 BT1~BT7 检查测试，生成 outputs/
    python3 loop_pass.py --shape 2 3 2  # 换形状：打印规格表＋IR＋IV 轨迹（练习用）
    python3 loop_pass.py --debug        # 额外打印主图与各案例的调试树

产出：
    outputs/loop-ir.txt        循环 IR（带循环规格表与四要素注释；13 op，访存留给 Day 89）
    outputs/boundary-table.txt 边界测试：7 组 shape 的 trip/IV 实测表 ＋ K=0 零趟特写
    outputs/test-report.txt    BT1~BT7 检查测试报告（真实运行）
    outputs/debug-log.txt      调试树（主图 + 动态拒绝 + 回滚案例）
"""

from __future__ import annotations

import argparse
import platform
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

OUT = Path(__file__).resolve().parent / "outputs"

SEED = 87          # 输入数据随机种子（A/B 矩阵），保证可复现
GARBAGE_BASE = 777.0   # alloc 内存「垃圾值」基址（确定性公式，见 Interp.alloc）


# ============================================================ 类型工具

def row_major_strides(shape):
    """行主序 strides：最后一维为 1，往前逐维乘 shape；遇到动态维 '?' 则传递 '?'。"""
    s = [1] * len(shape)
    for d in range(len(shape) - 2, -1, -1):
        if shape[d + 1] == "?" or s[d + 1] == "?":
            s[d] = "?"
        else:
            s[d] = s[d + 1] * shape[d + 1]
    return tuple(s)


def make_memref(shape, strides=None):
    strides = tuple(strides) if strides else row_major_strides(shape)
    return (f"memref<{'x'.join(map(str, shape))}xf32, "
            f"strided<[{', '.join(map(str, strides))}]>>")


# shape 段允许数字或 '?'（动态维度）；Day 87 起支持动态 shape 的解析与保守拒绝
_SHAPE = r"(?:(?:\d+|\?)x)*(?:\d+|\?)"
_TENSOR_RE = re.compile(rf"^tensor<({_SHAPE})xf32>$")
_MEMREF_RE = re.compile(rf"^memref<({_SHAPE})xf32, strided<\[[\d?, ]+\]>>$")
_MEMREF_STRIDES_RE = re.compile(r"^memref<[\dx?]+xf32, strided<\[([\d, ]+)\]>>$")


def _parse_shape(s):
    return tuple(int(x) if x.isdigit() else "?" for x in s.split("x"))


def tensor_shape(t):
    m = _TENSOR_RE.match(t)
    return _parse_shape(m.group(1)) if m else None


def memref_shape(t):
    m = _MEMREF_RE.match(t)
    return _parse_shape(m.group(1)) if m else None


def memref_strides(t):
    m = _MEMREF_STRIDES_RE.match(t)
    return tuple(int(x) for x in m.group(1).split(",")) if m else None


def is_static(shape):
    return all(x != "?" for x in shape)


# ============================================================ 最小 SSA IR

class Value:
    """SSA 值：名字 + 类型；身份用对象 id。"""
    __slots__ = ("name", "type")

    def __init__(self, name, type):
        self.name, self.type = name, type

    def __repr__(self):
        return f"{self.name}: {self.type}"


class Op:
    """操作：名字 + 操作数 + 结果 + 属性 + region（body）+ 注释。

    scf.for 的约定（Day 87 建立，Day 88 沿用）：
      operands = [lb, ub, step, *iter_args 初值]
      attrs    = {"iv": "%k", "iv_value": Value,        # 归纳变量（区域第一个参数）
                  "iter_names": ["%acc"],                # iter_args 显示名
                  "iter_args": [Value, ...]}             # iter_args 区域参数（跟在 iv 后）
      results  = [Value, ...]                            # 循环结束后的循环携带值
    """

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
    if op.name == "memref.load" and op.operands:
        m = op.operands[0]
        idx = ", ".join(v.name for v in op.operands[1:])
        return f"{op.results[0].name} = memref.load {m.name}[{idx}]"
    if op.name == "memref.store" and len(op.operands) >= 3:
        m = op.operands[1]
        idx = ", ".join(v.name for v in op.operands[2:])
        return f"memref.store {op.operands[0].name}, {m.name}[{idx}]"
    if op.name == "memref.fill" and len(op.operands) == 2:
        return f"memref.fill {op.operands[0].name}, {op.operands[1].name}"
    if op.name == "scf.for" and len(op.operands) >= 3:
        lo, up, st = [v.name for v in op.operands[:3]]
        head = (f"{op.results[0].name} = " if op.results else "")
        head += f"scf.for {op.attrs.get('iv', '?')} = {lo} to {up} step {st}"
        if len(op.operands) > 3:
            ia = ", ".join(f"{n} = {v.name}" for n, v in
                           zip(op.attrs.get("iter_names", []), op.operands[3:]))
            head += f" iter_args({ia})"
        return head
    if op.name == "scf.yield" and op.operands:
        return "scf.yield " + ", ".join(v.name for v in op.operands)
    if op.results:
        res = ", ".join(r.name for r in op.results)
        ops = ", ".join(v.name for v in op.operands)
        return f"{res} = {op.name}({ops})"
    if op.operands:
        return f"{op.name} " + ", ".join(v.name for v in op.operands)
    return op.name


def print_module(func, header_lines=()):
    """把 func 树打印成 MLIR 风格文本（Day 87 版打印机原样沿用）。"""

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
            lhs = f"{op.results[0].name} = " if op.results else ""
            if len(op.operands) > 3:
                ia = ", ".join(f"{n} = {v.name}" for n, v in
                               zip(op.attrs.get("iter_names", []), op.operands[3:]))
                rts = ", ".join(r.type for r in op.results)
                lines.append(f"{pad}{lhs}scf.for {op.attrs['iv']} = {lo} to {up} step {st}")
                lines.append(f"{pad}        iter_args({ia}) -> ({rts}) {{")
            else:
                lines.append(f"{pad}{lhs}scf.for {op.attrs['iv']} = {lo} to {up} step {st} {{")
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
        elif op.name == "memref.load":
            m = op.operands[0]
            idx = ", ".join(v.name for v in op.operands[1:])
            lines.append(f"{pad}{op.results[0].name} = memref.load {m.name}[{idx}]"
                         f" : {m.type}")
        elif op.name == "memref.store":
            m = op.operands[1]
            idx = ", ".join(v.name for v in op.operands[2:])
            lines.append(f"{pad}memref.store {op.operands[0].name}, {m.name}[{idx}]"
                         f" : {m.type}")
        elif op.name == "memref.fill":
            lines.append(f"{pad}memref.fill {op.operands[0].name}, {op.operands[1].name}"
                         f" : {op.operands[1].type}")
        elif op.name == "scf.yield":
            if op.operands:
                lines.append(f"{pad}scf.yield {', '.join(v.name for v in op.operands)}"
                             f" : {', '.join(v.type for v in op.operands)}")
            else:
                lines.append(pad + "scf.yield")
        else:
            lines.append(pad + op_headline(op))
        for cm in op.comments:
            lines.append(f"{pad}// {cm}")

    lines = list(header_lines)
    rec(func, 0, lines)
    return "\n".join(lines) + "\n"


class TypeConverter:
    """tensor → memref（行主序 strides，动态维 '?' 原样传递）；其余类型原样通过。"""

    def convertType(self, t):
        shape = tensor_shape(t)
        if shape is not None:
            return make_memref(shape)
        return t


# ============================================================ Pattern / Rewriter
# （与 Day 86/87 相同的三段式事务：create/replaceOp 暂存 → commit / rollback）

class PatternContractError(Exception):
    """违反 Pattern 契约（改 IR 不走 rewriter / root 未处置 / 失败留痕）。"""


class _ContractFatal(Exception):
    """契约违反升级为整个转换的硬失败（携带诊断信息）。"""


@dataclass
class Adaptor:
    """ConversionPattern 拿到的操作数：已经是「最近一次替换后的值」（类型已合法化）。"""
    operands: list


class ConversionPattern:
    """翻译规则基类。子类实现 matchAndRewrite，返回 True=成功（IR 已改），False=失败。"""
    root_name: str = ""
    benefit: int = 1
    debug_name: str = "ConversionPattern"

    def matchAndRewrite(self, op, adaptor, rewriter):
        raise NotImplementedError


class _Txn:
    """一次 Pattern 应用的事务暂存区：create/replace 先记在这里。"""

    def __init__(self):
        self.created = []
        self.replacements = {}
        self.disposed = None


class ConversionPatternRewriter:
    """事务性改写器：所有修改先暂存，Pattern 成功才 commit，失败 rollback（不留痕）。"""

    def __init__(self, driver):
        self.driver = driver
        self.global_replacements = {}
        self._txn = None
        self._pattern_name = "?"
        self.last_created = []

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
            body = self.driver.body_of(root_op)
            body.remove(root_op)
        self.last_created = list(txn.created)
        self._txn = None

    def rollback(self):
        self._txn = None

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
        self._txn.disposed = op

    def notifyMatchFailure(self, op, reason):
        self.driver.match_failures.append((op, reason))
        return False

    def getRemappedValue(self, v):
        seen = set()
        while v in self.global_replacements and id(v) not in seen:
            seen.add(id(v))
            v = self.global_replacements[v]
        return v

    def finalize(self, func):
        for op in func.walk():
            op.operands = [self.getRemappedValue(v) for v in op.operands]
            if op.name == "func.func":
                op.attrs["args"] = [self.getRemappedValue(a) for a in op.attrs["args"]]


# ============================================================ 合法性目标与驱动器

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
    log: list
    debug_lines: list


class ConversionDriver:
    """驱动器仿真：先序遍历 → 非法 op 逐条试 Pattern → 收敛或失败。"""

    def __init__(self, patterns, type_converter, debug=False):
        self.patterns = sorted(patterns, key=lambda p: -p.benefit)
        self.tc = type_converter
        self.rewriter = ConversionPatternRewriter(self)
        self.debug = debug
        self.debug_lines = []
        self.match_failures = []
        self.legalization_log = []
        self.mode = "full"
        self._failure_msg = ""
        self._func = None

    def dbg(self, line):
        if self.debug:
            self.debug_lines.append(line)

    def body_of(self, op):
        for cand in self._func.walk():
            for c in cand.body:
                if c is op:
                    return cand.body
        raise RuntimeError(f"op {op.name} 不在任何 body 里（IR 已损坏？）")

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
        if residue is None:
            return ConversionResult(False, mode, self._failure_msg, [],
                                    self.legalization_log, self.debug_lines)
        if self.mode == "full" and residue:
            return ConversionResult(False, mode, self._failure_msg, sorted(set(residue)),
                                    self.legalization_log, self.debug_lines)
        if residue:
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
                continue
            if self.mode == "full":
                return None
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
            self.rewriter.rollback()
            reason = (self.match_failures[-1][1] if self.match_failures
                      else "（静默 return failure，无诊断）")
            self.dbg(f"  }} -> FAILURE : {reason}")
        self._failure_msg = (f"无法合法化 '{op.name}'：已注册的 Pattern 都拒绝了这次匹配"
                             f"（拒绝原因默认只在 --debug 调试树里；模式={self.mode}，整体失败）")
        self.dbg(f"}} -> FAILURE : {self._failure_msg}")
        return "none"


# ============================================================ Day 88：LoopSpec 与三重循环 Pattern

@dataclass
class LoopSpec:
    """一条循环的出生证明：四要素 ＋ 上界来源（今天的主角，单一事实来源）。

    语义依据（官方 scf.for，mlir.llvm.org，2026-11 核对）：
      · 半开区间 [lb, ub)：含下界、不含上界；
      · trip = max(0, ceil((ub - lb) / step))，iv 取 lb + j·step（j = 0..trip-1）；
      · step 必须严格为正；iv 是循环区域的第一个参数（index 类型，体外不可见）。
    """
    iv: str          # 归纳变量名（区域参数）
    lb: int          # 下界（含端点）
    ub: int          # 上界（不含端点——半开区间）
    step: int        # 步长（scf.for 要求严格为正）
    ub_source: str   # 上界的配对依据（从哪来）


def trip_count(spec):
    """官方语义的 trip 公式：max(0, ceil((ub - lb) / step))；step 必须严格为正。"""
    if spec.step <= 0:
        raise ValueError(f"scf.for 的 step 必须严格为正（官方语义），拿到 {spec.step}")
    return max(0, -((spec.lb - spec.ub) // spec.step))   # 整数 ceil 除法


def matmul_specs(M, K, N):
    """MatMul 三重循环的三条规格：i 套 j 套 k，归约（k）在最内层。"""
    return [
        LoopSpec("%i", 0, M, 1, f"M = A.shape[0] = {M}"),
        LoopSpec("%j", 0, N, 1, f"N = B.shape[1] = {N}"),
        LoopSpec("%k", 0, K, 1, f"K = 内维契约 A.shape[1] == B.shape[0] = {K}"),
    ]


class MatMulLoopPattern(ConversionPattern):
    """Day 88 版 mini.matmul → 循环表示：三重循环从「抄来的数字」升级为
    「有出生证明（LoopSpec）＋有边界测试（BT1~BT7）」的构件。

    相对 Day 87 的变化：
      · op 产出不变（13 op：alloc＋%zero＋5 常量＋三重循环＋yield 占位＋return）
        ——访存与累加（load×2 / mulf / addf / store）按计划是 Day 89 的填空；
      · 三条循环改由 LoopSpec（iv / lb / ub / step / ub_source）驱动生成——
        单一事实来源，规格表随 IR 一起输出（loop-ir.txt 头部）；
      · match 的动态拒绝理由聚焦今天的主题：四要素的 lb/ub 要物化成
        arith.constant 常量，动态 '?' 做不到——先支持静态 Shape。

    match 五连问沿用 Day 87：2 操作数？memref？2 维？内维契约？静态 shape？
    """

    root_name = "mini.matmul"
    benefit = 1
    debug_name = "MatMulLoopPattern"

    def __init__(self):
        self.specs = []

    def matchAndRewrite(self, op, adaptor, rewriter):
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
        if not (is_static(sa) and is_static(sb)):
            return rewriter.notifyMatchFailure(
                op, f"动态维度（A{sa} @ B{sb}）：循环四要素的 lb/ub 要物化成 "
                    f"arith.constant 常量，动态 '?' 做不到——本 Pattern 先支持静态 Shape"
                    f"（今日计划），宁拒不猜（动态版 Pattern 走 memref.dim ＋动态 alloc，"
                    f"后续专题）")
        if sa[1] != sb[0]:
            return rewriter.notifyMatchFailure(
                op, f"内维不匹配：A.shape[1]={sa[1]} ≠ B.shape[0]={sb[0]}，"
                    f"k 循环上界无从确定")
        M, K = sa
        N = sb[1]

        # ---------- rewrite：一切修改走 rewriter，先暂存 ----------
        specs = matmul_specs(M, K, N)
        self.specs = specs

        used = set()

        def cname(v):
            n = f"%c{v}"
            while n in used:
                n += "'"
            used.add(n)
            return n

        # ① 输出缓冲（Day 85 任务清单①；Day 87 已讲清：alloc 不清零，零起点靠 %zero）
        alloc = rewriter.create(
            "memref.alloc", result_names=["%c"], result_types=[make_memref((M, N))],
            comments=[f"任务① 输出缓冲 {M * N * 4} B：memref.alloc 不清零——零起点是 %zero（D87）"])

        # ② 零起点（Day 87 的成果，原样保留）
        zero = rewriter.create(
            "arith.constant", result_names=["%zero"], result_types=["f32"],
            attrs={"value": 0.0},
            comments=["任务③(D87) 零起点：SSA 值，不写内存——C 每元素只写不读"])

        # ③ 5 个 index 常量——四要素的物化形态
        consts = [rewriter.create("arith.constant", result_names=[cname(v)],
                                  result_types=["index"], attrs={"value": v})
                  for v in (0, 1, M, N, K)]
        for c, note in zip(consts, ["下界 0（含端点；memref 下标从 0 开始）",
                                    "步长 1（scf.for 要求 step 严格为正）",
                                    f"M ← A.shape[0]：i 的上界（不含端点）",
                                    f"N ← B.shape[1]：j 的上界（不含端点）",
                                    f"K ← 内维契约：k 的上界（不含端点）"]):
            c.comments.append(note)
        lo, st, bm, bn, bk = [c.results[0] for c in consts]

        # ④ 最内层循环体：yield 占位回传初值（Day 89 换成 %s = addf %acc, %p）
        yld = rewriter.create(
            "scf.yield", operands=[zero.results[0]],
            comments=["占位：恒等循环（%acc ≡ %zero）；Day 89 把 %zero 换成 %s = addf %acc, %p",
                      "预留(Day 89 填): load %a[%i,%k] · load %b[%k,%j] · mulf · addf · store %c[%i,%j]"])

        def loop_comments(s):
            return [f"四要素：lb={s.lb}（含）· ub={s.ub}（不含——半开区间 [{s.lb},{s.ub})）"
                    f"· step={s.step} · trip = max(0, ceil((ub-lb)/step)) = {trip_count(s)}",
                    f"ub 来源：{s.ub_source}；{s.iv} 是本循环的区域参数"
                    f"（index 类型，体内可见、体外不可见）"]

        # ⑤ 三重循环：从 LoopSpec 生成，从内向外创建；%acc（iter_args）挂在 k 上
        fk = rewriter.create(
            "scf.for", operands=[lo, bk, st, zero.results[0]],
            result_names=["%acc"], result_types=["f32"],
            attrs={"iv": "%k", "iv_value": Value("%k", "index"),
                   "iter_names": ["%acc"],
                   "iter_args": [Value("%acc", "f32")]},
            body=[yld],
            comments=[*loop_comments(specs[2]),
                      "iter_args(%acc = %zero)：归约在最内层——%acc 挂在 k 循环上（D87）",
                      "体内 %acc（区域参数）≠ 体外 %acc（循环结果）；带 iter_args 必须显式 yield"])
        fj = rewriter.create("scf.for", operands=[lo, bn, st],
                             attrs={"iv": "%j", "iv_value": Value("%j", "index")},
                             body=[fk], comments=loop_comments(specs[1]))
        fi = rewriter.create("scf.for", operands=[lo, bm, st],
                             attrs={"iv": "%i", "iv_value": Value("%i", "index")},
                             body=[fj], comments=loop_comments(specs[0]))
        # ---------- 处置 root：%mm(tensor) → %c(memref)；uses 延迟到 finalize 替换 ----------
        rewriter.replaceOp(op, [alloc.results[0]])
        return True


class HalfDoneLoopPattern(ConversionPattern):
    """反面教材（BT1 回归用）：先 create alloc＋常量＋一条循环再放弃——
    验证升级后的 Pattern 仍满足「失败不留痕」（Day 86 DT6 / Day 87 IT5 的延续）。"""

    root_name = "mini.matmul"
    benefit = 2
    debug_name = "HalfDoneLoopPattern"

    def matchAndRewrite(self, op, adaptor, rewriter):
        bad = rewriter.create("memref.alloc", result_names=["%bad"],
                              result_types=["memref<4x3xf32, strided<[3, 1]>>"])
        c = rewriter.create("arith.constant", result_names=["%bad0"],
                            result_types=["index"], attrs={"value": 0})
        rewriter.create("scf.for", operands=[c.results[0], c.results[0], c.results[0]],
                        attrs={"iv": "%bad_i", "iv_value": Value("%bad_i", "index")})
        return rewriter.notifyMatchFailure(
            op, "故意半途而废：先 create 了 alloc＋常量＋循环再放弃（回归测试：回滚必须不留痕）")


# ============================================================ 测试图构造

def build_main_graph(M=4, K=6, N=3):
    """S0 源图：Day 83 终图 GEMM 的形状（Day 85~88 贯穿例子）。"""
    x = Value("%x", f"tensor<{M}x{K}xf32>")
    w = Value("%w", f"tensor<{K}x{N}xf32>")
    mm = Value("%mm", f"tensor<{M}x{N}xf32>")
    matmul = Op("mini.matmul", [x, w], [mm])
    ret = Op("func.return", [mm])
    return Op("func.func", body=[matmul, ret],
              attrs={"sym_name": "main", "args": [x, w],
                     "result_types": [f"tensor<{M}x{N}xf32>"]})


def build_dynamic_graph(dyn="M"):
    """动态维度变体：M 或 N 为 '?'——测保守拒绝路径（BT6）。"""
    m = "?" if dyn == "M" else 4
    n = 3 if dyn == "M" else "?"
    k = 6
    x = Value("%x", f"tensor<{m}x{k}xf32>")
    w = Value("%w", f"tensor<{k}x{n}xf32>")
    mm = Value("%mm", f"tensor<{m}x{n}xf32>")
    matmul = Op("mini.matmul", [x, w], [mm])
    ret = Op("func.return", [mm])
    return Op("func.func", body=[matmul, ret],
              attrs={"sym_name": "main", "args": [x, w],
                     "result_types": [f"tensor<{m}x{n}xf32>"]})


def run_pass(func, mode="full", extra=(), debug=False):
    """跑一次 Day 88 版 MatMul Lowering Pass。返回 (pattern, result)。"""
    pat = MatMulLoopPattern()
    driver = ConversionDriver([pat, *extra], TypeConverter(), debug=debug)
    res = driver.apply(func, mode)
    return pat, res


EXPECTED_LOOP = (["func.func", "memref.alloc"]
                 + ["arith.constant"] * 6       # %zero(f32) ＋ 5 个 index 常量
                 + ["scf.for"] * 3 + ["scf.yield", "func.return"])


# ============================================================ 解释执行器
# （Day 87 的内存语义验证器 ＋ Day 88 的两个新探针：IV 轨迹、按维越界检测）

class MemRefOOBError(RuntimeError):
    """按维下标越界（Day 88 新探针）：线性地址仍在缓冲区内 ≠ 下标合法。"""


class Interp:
    """最小解释执行器：跑通 alloc/fill/load/store/scf.for(iter_args)/yield/mulf/addf。

    内存模型（Day 87）：每块 memref 是 list[[state, value]]，state ∈ {"uninit", "written"}；
    垃圾值是确定性公式 garbage(addr) = 777 + 7·addr（真实语义是未定义行为）。

    Day 88 新增的两个探针：
      · iv_trace：归纳变量的执行轨迹——进入次数、每趟迭代数、实际取值集合；
      · 按维越界检测：load/store 前逐维检查下标 ∈ [0, dim)，
        违规抛 MemRefOOBError（含「线性地址甚至仍在缓冲区内」的提示）。
    """

    def __init__(self, args_data):
        self.env = {}      # id(Value) -> int | np.float32
        self.mem = {}      # id(Value) -> list[[state, np.float32]]
        self.stats = {"uninit_reads": [], "loads": 0, "stores": 0, "fills": 0, "allocs": 0}
        self.iv_trace = {}  # iv 名 -> {"activations", "per_act", "values"}
        self.args_data = args_data
        self.ret = None

    # ---- 工具 ----
    @staticmethod
    def garbage(addr):
        return np.float32(GARBAGE_BASE + 7.0 * addr)

    def val(self, v):
        return self.env[id(v)]

    def _check_bounds(self, op):
        """按维检查下标合法（Day 88 探针）；返回线性地址。"""
        is_load = op.name == "memref.load"
        m = op.operands[0] if is_load else op.operands[1]
        idxs = op.operands[1:] if is_load else op.operands[2:]
        shape = memref_shape(m.type)
        vals = [int(self.val(i)) for i in idxs]
        for d, (v, dim) in enumerate(zip(vals, shape)):
            if dim != "?" and not (0 <= v < dim):
                strides = memref_strides(m.type) or ()
                addr = sum(s * x for s, x in zip(strides, vals))
                cells = self.mem.get(id(m))
                extra = ""
                if cells is not None and 0 <= addr < len(cells):
                    extra = (f"；线性地址 {addr} 甚至仍在缓冲区（{len(cells)} 格）内——"
                             f"只查线性地址抓不住这类逻辑越界")
                raise MemRefOOBError(
                    f"{'memref.load' if is_load else 'memref.store'} {m.name}{tuple(vals)}："
                    f"第 {d} 维下标 {v} ∉ [0, {dim})（shape {shape}）{extra}")
        return sum(s * v for s, v in zip(memref_strides(m.type), vals))

    # ---- 入口 ----
    def run(self, func):
        for a in func.attrs["args"]:
            data = self.args_data[a.name]
            if isinstance(data, np.ndarray):
                self.mem[id(a)] = [["written", np.float32(x)] for x in data.reshape(-1)]
            else:
                self.env[id(a)] = data
        for op in func.body:
            self.exec_op(op)
        return self.ret

    def exec_op(self, op):
        n = op.name
        if n == "arith.constant":
            self.env[id(op.results[0])] = (int(op.attrs["value"])
                                           if op.results[0].type == "index"
                                           else np.float32(op.attrs["value"]))
        elif n == "memref.alloc":
            shape = memref_shape(op.results[0].type)
            cells = [["uninit", self.garbage(a)] for a in range(shape[0] * shape[1])]
            self.mem[id(op.results[0])] = cells
            self.stats["allocs"] += 1
        elif n == "memref.fill":
            value, m = self.val(op.operands[0]), op.operands[1]
            for cell in self.mem[id(m)]:
                cell[0], cell[1] = "written", np.float32(value)
            self.stats["fills"] += 1
        elif n == "memref.load":
            m = op.operands[0]
            addr = self._check_bounds(op)
            cell = self.mem[id(m)][addr]
            if cell[0] == "uninit":
                idxs = tuple(int(self.val(i)) for i in op.operands[1:])
                self.stats["uninit_reads"].append((m.name, idxs, addr))
            self.env[id(op.results[0])] = np.float32(cell[1])
            self.stats["loads"] += 1
        elif n == "memref.store":
            m = op.operands[1]
            addr = self._check_bounds(op)
            self.mem[id(m)][addr] = ["written", np.float32(self.val(op.operands[0]))]
            self.stats["stores"] += 1
        elif n == "arith.mulf":
            self.env[id(op.results[0])] = np.float32(self.val(op.operands[0])
                                                     * self.val(op.operands[1]))
        elif n == "arith.addf":
            self.env[id(op.results[0])] = np.float32(self.val(op.operands[0])
                                                     + self.val(op.operands[1]))
        elif n == "scf.for":
            self.exec_for(op)
        elif n == "scf.yield":
            pass    # 由 exec_body 处理，不会走到这里
        elif n == "func.return":
            self.ret = id(op.operands[0]) if op.operands else None
        else:
            raise RuntimeError(f"Interp：不支持的 op '{n}'")

    def exec_for(self, op):
        """执行 scf.for（官方语义：半开区间、step 严格为正、iv 区域参数）。

        Day 88 探针：iv_trace 记录进入次数 / 每趟迭代数 / 取值集合。
        """
        lb, ub, st = (int(self.val(v)) for v in op.operands[:3])
        if st <= 0:
            raise RuntimeError(f"scf.for 的 step 必须严格为正（官方语义），拿到 step={st}")
        cur = [self.val(v) for v in op.operands[3:]]     # iter_args 初值
        region_args = op.attrs.get("iter_args", [])
        iv = op.attrs["iv_value"]
        tr = self.iv_trace.setdefault(iv.name,
                                      {"activations": 0, "per_act": [], "values": set()})
        tr["activations"] += 1
        n_iter = 0
        for it in range(lb, ub, st):     # 半开区间：含 lb、不含 ub（st > 0）
            self.env[id(iv)] = it        # iv：每次迭代重新绑定的区域参数
            tr["values"].add(it)
            n_iter += 1
            for rarg, v in zip(region_args, cur):
                self.env[id(rarg)] = v   # 体内 iter_args ← 当前值
            yv = self.exec_body(op.body)
            if yv is not None:
                cur = yv                 # yield 回传 → 下一轮
        tr["per_act"].append(n_iter)
        for r, v in zip(op.results, cur):
            self.env[id(r)] = v          # 终值出门：循环结果

    def exec_body(self, body):
        """执行循环体直到 yield：返回 yield 的操作数值列表（无操作数 → None）。"""
        for op in body:
            if op.name == "scf.yield":
                return [self.val(v) for v in op.operands] if op.operands else None
            self.exec_op(op)
        return None    # 空体（无 yield）：保持 iter_args 不变（官方：无结果时可隐式终止器）


def reference_matmul(A, B):
    """同序参考实现：与循环 IR 完全相同的 i/j/k 顺序＋float32 舍入 → 可验证位等价。"""
    M, K = A.shape
    _, N = B.shape
    C = np.zeros((M, N), dtype=np.float32)
    for i in range(M):
        for j in range(N):
            acc = np.float32(0.0)
            for k in range(K):
                acc = np.float32(acc + np.float32(A[i, k] * B[k, j]))
            C[i, j] = acc
    return C


# ============================================================ 预演器（Day 87 三策略预演器的 Day 88 版）
# 固定方案 B（iter_args = %zero），参数化四要素用于探针注入（BT7）。
# 循环体里的 load/mulf/addf/store 是 Day 89 才由 Pattern 产出的 op——预演器
# 用来给循环语义做执行级验证（Day 87 IT3 同款做法）。

def build_full_ir(M=4, K=6, N=3, i_ub=None, j_ub=None, k_step=1, swap=False):
    """构造「访存也填好」的完整循环 IR（方案 B），四要素可注入错误：

      i_ub / j_ub ：覆盖 i/j 的上界（off-by-one、边界交换探针）
      k_step      ：覆盖 k 的步长（漏元素探针）
      swap        ：i/j 上界对调（配对错误探针：i 界=N、j 界=M）
    """
    ub_i, ub_j = (N, M) if swap else (M, N)
    if i_ub is not None:
        ub_i = i_ub
    if j_ub is not None:
        ub_j = j_ub
    probe_notes = []
    if i_ub is not None:
        probe_notes.append(f"探针 P1(off-by-one)：i 的上界写成 {i_ub}（正确值 M={M}）")
    if k_step != 1:
        probe_notes.append(f"探针 P2(step)：k 的步长写成 {k_step}（每 {k_step} 个取 1 个）")
    if swap:
        probe_notes.append(f"探针 P3(配对)：i/j 上界交换（i 界={ub_i}=N，j 界={ub_j}=M）")

    ta, tb, tc = make_memref((M, K)), make_memref((K, N)), make_memref((M, N))
    a, b = Value("%a", ta), Value("%b", tb)
    body = []
    c = Op("memref.alloc", results=[Value("%c", tc)],
           comments=["任务① 输出缓冲（alloc 不清零）"])
    body.append(c)
    zero = Op("arith.constant", results=[Value("%zero", "f32")], attrs={"value": 0.0},
              comments=["方案 B：零起点（SSA 常量，Day 87 选定）"])
    body.append(zero)

    used = set()

    def cname(v):
        n = f"%c{v}"
        while n in used:
            n += "'"
        used.add(n)
        return n

    cops = {}
    for v, note in ((0, "下界 0"), (1, "步长 1"), (ub_i, f"i 上界 {ub_i}"),
                    (ub_j, f"j 上界 {ub_j}"), (K, f"k 上界 {K}"), (k_step, f"k 步长 {k_step}")):
        if v in cops:
            cops[v].comments.append(note)
        else:
            cops[v] = Op("arith.constant", results=[Value(cname(v), "index")],
                         attrs={"value": v}, comments=[note])
            body.append(cops[v])
    lo = cops[0].results[0]
    st = cops[1].results[0]
    bi, bj, bk = cops[ub_i].results[0], cops[ub_j].results[0], cops[K].results[0]
    stk = cops[k_step].results[0]
    iv = {"%i": Value("%i", "index"), "%j": Value("%j", "index"), "%k": Value("%k", "index")}
    acc_arg = Value("%acc", "f32")        # 循环体内可见的 iter_args 区域参数
    acc_res = Value("%acc", "f32")        # 循环结果（体外可见）——同名不同值

    # ---- 最内层 %k 循环体：load ×2 · mulf · addf · yield %s（Day 89 的完整形态）----
    xa = Op("memref.load", operands=[a, iv["%i"], iv["%k"]], results=[Value("%xa", "f32")])
    xb = Op("memref.load", operands=[b, iv["%k"], iv["%j"]], results=[Value("%xb", "f32")])
    p = Op("arith.mulf", operands=[xa.results[0], xb.results[0]], results=[Value("%p", "f32")])
    s = Op("arith.addf", operands=[acc_arg, p.results[0]], results=[Value("%s", "f32")])
    yld = Op("scf.yield", operands=[s.results[0]])
    fk = Op("scf.for", operands=[lo, bk, stk, zero.results[0]],
            results=[acc_res],
            attrs={"iv": "%k", "iv_value": iv["%k"], "iter_names": ["%acc"],
                   "iter_args": [acc_arg]},
            body=[xa, xb, p, s, yld],
            comments=["iter_args(%acc = %zero)：方案 B（Day 87 选定）", *probe_notes])
    st_op = Op("memref.store", operands=[acc_res, c.results[0], iv["%i"], iv["%j"]],
               comments=["C 每元素只写一次（最终值）"])
    fj = Op("scf.for", operands=[lo, bj, st],
            attrs={"iv": "%j", "iv_value": iv["%j"]}, body=[fk, st_op])
    fi = Op("scf.for", operands=[lo, bi, st],
            attrs={"iv": "%i", "iv_value": iv["%i"]}, body=[fj])
    body.append(fi)
    ret = Op("func.return", operands=[c.results[0]])
    return Op("func.func", body=body + [ret],
              attrs={"sym_name": "main", "args": [a, b], "result_types": [tc]})


def run_full(M=4, K=6, N=3, **kw):
    """预演器执行：构造完整 IR → 解释执行 → (C, interp, func, 错误信息或 None)。"""
    A, B = make_inputs(M, K, N)
    func = build_full_ir(M=M, K=K, N=N, **kw)
    interp = Interp({"%a": A, "%b": B})
    try:
        interp.run(func)
    except MemRefOOBError as exc:
        return None, interp, func, str(exc)
    C = np.array([cell[1] for cell in interp.mem[interp.ret]],
                 dtype=np.float32).reshape(M, N)
    return C, interp, func, None


def make_inputs(M=4, K=6, N=3, seed=SEED):
    """固定种子的输入矩阵（可复现）。"""
    rng = np.random.RandomState(seed)
    return (rng.randn(M, K).astype(np.float32),
            rng.randn(K, N).astype(np.float32))


# ============================================================ 检查测试 BT1~BT7

def _loops(func):
    """主图（转换后）的三重循环与最内层 yield。"""
    fi = func.body[7]
    fj = fi.body[0]
    fk = fj.body[0]
    yld = fk.body[0]
    return fi, fj, fk, yld


def _const_vals(func):
    """id(Value) → 常量值（用于把循环操作数解析回数字）。"""
    m = {}
    for op in func.walk():
        if op.name == "arith.constant":
            m[id(op.results[0])] = op.attrs["value"]
    return m


def bt1_spec_pairing(func, res, pattern, before_names):
    """BT1 四要素与配对（结构）：13 op；三条循环的 (lb,ub,step)=(0,M/N/K,1)；
    LoopSpec 出生证明与 ub 来源；Day 87 栏目回归；回滚不留痕回归。"""
    after = [op.name for op in func.walk()]
    body = func.body
    alloc, zero, consts, fi = body[0], body[1], body[2:7], body[7]
    fj, fk, yld = fi.body[0], fi.body[0].body[0], fi.body[0].body[0].body[0]
    seq_ok = after == EXPECTED_LOOP
    cv = _const_vals(func)

    def trip3(loop):
        return tuple(int(cv[id(v)]) for v in loop.operands[:3])

    i_ok = trip3(fi) == (0, 4, 1) and fi.attrs["iv"] == "%i"
    j_ok = trip3(fj) == (0, 3, 1) and fj.attrs["iv"] == "%j"
    k_ok = trip3(fk) == (0, 6, 1) and fk.attrs["iv"] == "%k"
    specs_ok = ([(s.iv, s.lb, s.ub, s.step) for s in pattern.specs]
                == [("%i", 0, 4, 1), ("%j", 0, 3, 1), ("%k", 0, 6, 1)])
    trips_ok = [trip_count(s) for s in pattern.specs] == [4, 3, 6]
    src_ok = ("A.shape[0]" in pattern.specs[0].ub_source
              and "B.shape[1]" in pattern.specs[1].ub_source
              and "内维契约" in pattern.specs[2].ub_source)
    reg_ok = (fk.operands[3].name == "%zero" and fk.attrs["iter_names"] == ["%acc"]
              and len(yld.operands) == 1 and yld.operands[0].name == "%zero"
              and alloc.results[0].type == make_memref((4, 3))
              and sorted(int(c.attrs["value"]) for c in consts) == [0, 1, 3, 4, 6])
    fa = build_main_graph()
    _, ra = run_pass(fa, "full", extra=[HalfDoneLoopPattern()])
    fb = build_main_graph()
    run_pass(fb, "full")
    roll_ok = ra.ok and print_module(fa) == print_module(fb)
    ok = (res.ok and seq_ok and i_ok and j_ok and k_ok and specs_ok
          and trips_ok and src_ok and reg_ok and roll_ok)
    lines = [
        f"  转换前 {len(before_names)} op → 转换后 {len(after)} op（与 Day 87 相同的 13 op："
        f"func＋alloc＋constant×6＋for×3＋yield＋return）",
        f"  三条循环的 (lb, ub, step)：i{trip3(fi)} · j{trip3(fj)} · k{trip3(fk)}"
        f"——lb=0（含）、ub=M/N/K（不含）、step=1（{i_ok and j_ok and k_ok}）",
        f"  LoopSpec 出生证明：{[(s.iv, s.lb, s.ub, s.step) for s in pattern.specs]}"
        f"（{specs_ok}），trip 公式 = {[trip_count(s) for s in pattern.specs]}（{trips_ok}）",
        f"  ub 来源配对：i ← A.shape[0] · j ← B.shape[1] · k ← 内维契约（{src_ok}）",
        f"  Day 87 栏目回归：iter_args(%acc=%zero)、yield %zero 占位、alloc 4x3、"
        f"常量 {{0,1,3,4,6}}（{reg_ok}）",
        f"  回滚回归：HalfDone(先 create 再拒绝) 回滚后，终图与只用 Loop 的结果"
        f"逐字相同（{roll_ok}）",
        f"  mini 方言残留：{[n for n in after if n.startswith('mini.')] or '无'}",
    ]
    return ok, lines


def bt2_halfopen_trace(func):
    """BT2 半开区间与 IV 轨迹（解释执行）：值域不含 ub、每趟迭代数=trip 公式、
    总迭代 M×N×K、%acc 占位回归、C 零访问。"""
    A, B = make_inputs()
    interp = Interp({"%a": A, "%b": B})
    interp.run(func)
    fi, fj, fk, _ = _loops(func)
    tr = interp.iv_trace
    i_ok = tr["%i"]["per_act"] == [4] and sorted(tr["%i"]["values"]) == [0, 1, 2, 3]
    j_ok = tr["%j"]["per_act"] == [3] * 4 and sorted(tr["%j"]["values"]) == [0, 1, 2]
    k_ok = (tr["%k"]["per_act"] == [6] * 12
            and sorted(tr["%k"]["values"]) == [0, 1, 2, 3, 4, 5])
    halfopen_ok = (max(tr["%i"]["values"]) == 3 and max(tr["%j"]["values"]) == 2
                   and max(tr["%k"]["values"]) == 5)
    acc_final = interp.env[id(fk.results[0])]
    acc_ok = float(acc_final) == 0.0
    quiet_ok = (interp.stats["loads"] == 0 and interp.stats["stores"] == 0
                and interp.stats["fills"] == 0)
    uninit_ok = not interp.stats["uninit_reads"]
    total_ok = sum(tr["%k"]["per_act"]) == 72
    ok = all([i_ok, j_ok, k_ok, halfopen_ok, acc_ok, quiet_ok, uninit_ok, total_ok])
    lines = [
        f"  IV 轨迹（解释执行真实记录，A/B 为种子 {SEED} 的数据）：",
        f"    %i：进入 1 次 · 每趟 4 次迭代 · 取值 {{0,1,2,3}}——最大值 3 = ub−step"
        f"（ub=4 不含，半开区间的执行证据）",
        f"    %j：进入 4 次（=M）· 每趟 3 次迭代 · 取值 {{0,1,2}}——最大值 2 = ub−step",
        f"    %k：进入 12 次（=M×N）· 每趟 6 次迭代 · 取值 {{0,…,5}}——最大值 5 = ub−step",
        f"  每趟迭代数与 trip 公式一致：4/3/6 = max(0, ceil((ub-lb)/step))"
        f"（{i_ok and j_ok and k_ok}）；k 体总执行 {sum(tr['%k']['per_act'])} 次"
        f"= M×N×K = 4×3×6（{total_ok}）",
        f"  %acc 终值 = {float(acc_final):.1f}（≡ %zero，{acc_ok}）——Day 87 占位语义回归",
        f"  对 C 的访问：load 0 · store 0 · fill 0 · 未初始化读 0（{quiet_ok and uninit_ok}）"
        f"——访存是 Day 89 的填空",
    ]
    return ok, lines


def bt3_iv_scope(func):
    """BT3 归纳变量的身份与作用域：index 类型；不是常量；体外无引用（支配性
    的结构断言）；体内/嵌套区域可见（预演 IR 正向验证）；终止器显隐规则。"""
    fi, fj, fk, yld = _loops(func)
    type_ok = all(l.attrs["iv_value"].type == "index" for l in (fi, fj, fk))
    # 体外不可见：对每条循环，检查其 region 子树之外的 op 都不引用它的 iv
    scope_ok = True
    for loop in (fi, fj, fk):
        ins = {id(o) for o in loop.walk()}
        ivv = loop.attrs["iv_value"]
        for op in func.walk():
            if id(op) in ins:
                continue
            if any(v is ivv for v in op.operands):
                scope_ok = False
    # %i 不是常量：与任何 arith.constant 的结果都不是同一个 Value 对象
    const_results = [r for op in func.walk()
                     if op.name == "arith.constant" for r in op.results]
    notconst_ok = all(fi.attrs["iv_value"] is not r for r in const_results)
    # 正向：预演完整 IR 里，k 循环体里的 load 用到 %k 和 %i（嵌套可见）
    pf = build_full_ir()
    ploops = [op for op in pf.walk() if op.name == "scf.for"]
    pfi, pfk = ploops[0], ploops[-1]
    loads = [op for op in pfk.body if op.name == "memref.load"]
    use_k = any(v is pfk.attrs["iv_value"] for ld in loads for v in ld.operands)
    use_i = any(v is pfi.attrs["iv_value"] for ld in loads for v in ld.operands)
    store = [op for op in pf.walk() if op.name == "memref.store"][0]
    use_ij = (any(v is pfi.attrs["iv_value"] for v in store.operands)
              and any(v is ploops[1].attrs["iv_value"] for v in store.operands))
    visible_ok = use_k and use_i and use_ij
    # 终止器规则：带 iter_args 必须显式 yield；无结果可隐式（官方规则）
    term_ok = (fk.body[-1].name == "scf.yield" and len(fk.body[-1].operands) == 1)
    implicit_ok = fj.body[-1].name == "scf.for" and fi.body[-1].name == "scf.for"
    ok = all([type_ok, scope_ok, notconst_ok, visible_ok, term_ok, implicit_ok])
    lines = [
        f"  三个 iv 都是 index 类型（{type_ok}）——MLIR 专用于下标/尺寸的整数类型，"
        f"Day 89 的地址计算（6·i+k 等）乘的就是它",
        f"  %i 不是常量：与 5 个 arith.constant 的结果均为不同 Value（{notconst_ok}）"
        f"——区域参数每次迭代重新绑定，%c4 才是常量",
        f"  体外不可见（支配性结构断言）：三条循环的 region 子树之外，没有任何 op "
        f"引用它们的 iv（{scope_ok}）——真实 MLIR 由 verifier 强制；仿真 env 平铺，"
        f"故用结构断言（诚实边界）",
        f"  体内/嵌套可见（预演 IR 正向验证）：k 体里 load %a[%i,%k]、load %b[%k,%j]、"
        f"store %c[%i,%j] 全部合法引用外层 iv（{visible_ok}）",
        f"  终止器规则（官方）：带 iter_args 必须显式 scf.yield——k 循环有（{term_ok}）；"
        f"无结果可隐式——i/j 循环体末尾就是嵌套 for（{implicit_ok}）",
    ]
    return ok, lines


def bt4_nesting(func):
    """BT4 嵌套结构：深度 3、i→j→k 顺序、归约最内（%acc 挂 k）、iv 互不重用。"""
    fi, fj, fk, yld = _loops(func)
    chain_ok = (fi.body == [fj] and fj.body == [fk] and fk.body == [yld])
    ivs = [fi.attrs["iv_value"], fj.attrs["iv_value"], fk.attrs["iv_value"]]
    distinct_ok = len({id(v) for v in ivs}) == 3
    inner_ok = len(fk.operands) == 4 and fk.attrs.get("iter_names") == ["%acc"]
    outer_ok = len(fi.operands) == 3 and len(fj.operands) == 3
    order_note = ("i 外 · j 中 · k 内" if (fi.body[0] is fj and fj.body[0] is fk)
                  else "顺序错误")
    ok = chain_ok and distinct_ok and inner_ok and outer_ok
    lines = [
        f"  嵌套链：fi.body=[fj] · fj.body=[fk] · fk.body=[yield]（{chain_ok}）——"
        f"深度 3，{order_note}",
        f"  归约在最内层：%acc 的 iter_args 挂在 k 循环上（{inner_ok}）——i/j 循环"
        f"不携带值（{outer_ok}）",
        f"  三个 iv 互不重用（{distinct_ok}）：每层循环定义自己的区域参数",
        f"  i/j/k 的顺序今天固定（局部性与排列是 Day 92 的专题；参数化是 Day 93）",
    ]
    return ok, lines


SHAPES = [(1, 1, 1), (1, 5, 3), (5, 1, 3), (2, 3, 2), (3, 2, 7), (4, 6, 3), (4, 0, 3)]


def _fmt_set(vals):
    vs = sorted(vals)
    if not vs:
        return "∅（零趟）"
    s = "{" + ",".join(map(str, vs[:6])) + (",…" if len(vs) > 6 else "") + "}"
    return s


def bt5_boundary_shapes():
    """BT5 边界 shape 全家福：7 组形状的 trip/IV 实测 ＋ K=0 零趟特写。"""
    lines, table, ok = [], [], True
    for (M, K, N) in SHAPES:
        func = build_main_graph(M, K, N)
        _, res = run_pass(func, "full")
        A, B = make_inputs(M, K, N)
        interp = Interp({"%a": A, "%b": B})
        interp.run(func)
        fk = func.body[7].body[0].body[0]
        tr = interp.iv_trace
        got = (tr["%i"]["per_act"][0], tr["%j"]["per_act"][0], tr["%k"]["per_act"][0])
        exp = (M, N, K)
        acts = (tr["%i"]["activations"], tr["%j"]["activations"], tr["%k"]["activations"])
        acts_ok = acts == (1, M, M * N)
        tot_k = sum(tr["%k"]["per_act"])
        vals_ok = (sorted(tr["%i"]["values"]) == list(range(M))
                   and sorted(tr["%j"]["values"]) == list(range(N))
                   and sorted(tr["%k"]["values"]) == list(range(K)))
        acc0 = float(interp.env[id(fk.results[0])]) == 0.0
        good = (res.ok and got == exp and acts_ok and vals_ok
                and tot_k == M * N * K and acc0)
        ok &= good
        table.append(
            f"  A({M},{K}) @ B({K},{N}) → C({M},{N})：trips(i,j,k) = {got}"
            f"（预期 {exp}）· 进入次数 {acts} · k 体总执行 {tot_k} = M×N×K"
            f" · iv 值域 i{_fmt_set(tr['%i']['values'])} j{_fmt_set(tr['%j']['values'])}"
            f" k{_fmt_set(tr['%k']['values'])} · %acc 终值 0.0"
            f" · {'PASS' if good else 'FAIL'}")
    # K=0 零趟特写：空归约 = 单位元（Day 87 初值的数学身份）
    A, B = make_inputs(4, 0, 3)
    ref = reference_matmul(A, B)
    npm = np.matmul(A, B)
    C, stx, _, err = run_full(4, 0, 3)
    k0_ok = (err is None and C is not None and C.shape == (4, 3)
             and float(np.max(np.abs(C))) == 0.0
             and np.array_equal(ref, np.zeros((4, 3), np.float32))
             and np.array_equal(npm, ref)
             and stx.stats["stores"] == 12 and stx.stats["loads"] == 0)
    ok &= k0_ok
    lines.append("  7 组形状全部通过（明细见 boundary-table.txt）：trips 实测 = (M,N,K)，"
                 "IV 值域 = [0,ub)（不含 ub），k 体总执行 = M×N×K")
    lines.append("  边界成员：最小 (1,1,1) · 行向量 (1,5,3) · 内维 1 (5,1,3) · 非方形 "
                 "(2,3,2)/(3,2,7) · 贯穿例 (4,6,3) · 零趟 (4,0,3)")
    lines.append(f"  零趟特写 K=0（A(4,0) @ B(0,3)）：k 循环每趟 0 次迭代 → %acc 终值 = "
                 f"初值 0.0；预演完整 IR 执行：store 12 次（写 0.0）· load 0 次（{k0_ok}）")
    lines.append(f"    数学佐证：空和 = 0（归约单位元）——np.matmul((4,0),(0,3)) = "
                 f"4×3 零矩阵，与同序参考实现逐位相同；Day 87 的「零次迭代时结果 = 初值」"
                 f"在今天拿到了数学身份")
    lines.append("  分工说明：端到端数值对照（≥8 组 shape）是 Day 90 的验收；"
                 "今天只测循环结构与 IV 语义（体仍为空）")
    return ok, lines, table


def bt6_dynamic_conservative():
    """BT6 静态前提：动态 '?' → 四要素无法物化为常量 → 保守拒绝。"""
    lines, ok = [], True
    f1 = build_dynamic_graph("M")
    _, r1 = run_pass(f1, "full", debug=True)
    good1 = (not r1.ok and "无法合法化 'mini.matmul'" in r1.message
             and "都拒绝了这次匹配" in r1.message)
    ok &= good1
    lines.append(f"  A(?x6) @ B(6x3)（M 动态），full 模式：{'按预期失败' if not r1.ok else '意外成功'}")
    lines.append("  拒绝的焦点（今天视角）：lb/ub 要物化成 arith.constant，"
                 "动态 '?' 下 %cM 无从产生——四要素缺了两个")
    dbg_text = "\n".join(r1.debug_lines)
    in_debug = "循环四要素" in dbg_text and "宁拒不猜" in dbg_text
    ok &= in_debug
    lines.append(f"  拒绝原因（只在 --debug 调试树，真实文本）：动态维度（A('?', 6) @ B(6, 3)）："
                 f"循环四要素的 lb/ub 要物化成 arith.constant 常量，动态 '?' 做不到…"
                 f"宁拒不猜（{in_debug}）")
    f2 = build_dynamic_graph("N")
    _, r2 = run_pass(f2, "partial")
    good2 = r2.ok and r2.residue == ["mini.matmul"]
    ok &= good2
    lines.append(f"  N 动态（A(4x6) @ B(6x?)），partial 模式：成功，显式残留 {r2.residue}"
                 f"（交给后续 Pass——动态版 Pattern 走 memref.dim ＋动态 alloc）")
    lines.append("  保守路径的意义：不生成边界靠猜的循环——「宁拒不猜」与 Day 87 同一立场，"
                 "今天换了个聚焦点")
    return ok, lines, r1.debug_lines


def bt7_probe_controls():
    """BT7 反面控制组：三个故意注入的边界 bug，全部被结构/执行探针拦下。"""
    lines, ok = [], True
    A, B = make_inputs()
    ref = reference_matmul(A, B)

    # ---- P1 off-by-one：i 的上界写成 M+1 ----
    bad = LoopSpec("%i", 0, 5, 1, "M = A.shape[0] = 4（被写错成 5）")
    p1_struct = trip_count(bad) == 5
    C1, it1, _, err1 = run_full(i_ub=5)
    p1_exec = (C1 is None and "第 0 维下标 4 ∉ [0, 4)" in err1 and "%a" in err1)
    ok &= p1_struct and p1_exec
    lines.append(f"  P1 off-by-one（i 上界 = M+1 = 5）：结构探针红——trip = 5 ≠ M = 4"
                 f"（{p1_struct}）；执行探针红——i=4 时 load %a[4,k] 按维越界"
                 f"（{p1_exec}）")
    lines.append(f"    真实报错：{err1}")

    # ---- P2 step=2：k 的步长写成 2 ----
    C2, it2, _, err2 = run_full(k_step=2)
    tr2 = it2.iv_trace
    diff2 = float(np.max(np.abs(C2 - ref))) if C2 is not None else float("nan")
    p2_ok = (err2 is None and sorted(tr2["%k"]["values"]) == [0, 2, 4]
             and tr2["%k"]["per_act"][0] == 3 and it2.stats["loads"] == 72)
    p2_red = diff2 > 0.0
    ok &= p2_ok and p2_red
    lines.append(f"  P2 step=2（k 步长 = 2）：不越界、安静地错——k 取值 {{0,2,4}}，"
                 f"每趟 3 次迭代（ceil(6/2)），load A/B 共 72 次（正确的 144 的一半）"
                 f"（{p2_ok}）")
    lines.append(f"    数值探针红：max|C-ref| = {diff2:.3e}（漏加全部奇数 k 项，{p2_red}）"
                 f"——step 不是「精度」参数，MatMul 的点循环必须逐步覆盖")

    # ---- P3 配对错误：i/j 上界交换 ----
    # 算术事实：交换不改变迭代总数（3×4×6 = 4×3×6 = 72）；执行被按维越界拦下时，
    # 在飞的循环不会记录 per_act（轨迹只记完成的趟）——断言只对已记录的部分做。
    C3, it3, _, err3 = run_full(swap=True)
    tr3 = it3.iv_trace
    p3_arith = (trip_count(LoopSpec("%i", 0, 3, 1, "")) * trip_count(LoopSpec("%j", 0, 4, 1, ""))
                * 6 == 4 * 3 * 6)
    p3_trace = (tr3["%i"]["values"] == {0} and tr3["%j"]["values"] == {0, 1, 2, 3}
                and tr3["%k"]["per_act"] == [6, 6, 6])
    p3_exec = (C3 is None and "第 1 维下标 3 ∉ [0, 3)" in err3 and "%b" in err3)
    ok &= p3_arith and p3_trace and p3_exec
    lines.append(f"  P3 配对错误（i 界=N=3、j 界=M=4）：迭代总数纹丝不动——3×4×6 = 72 = "
                 f"M×N×K（{p3_arith}），地址空间已经全错")
    lines.append(f"    执行轨迹：i 只跑到 0、j 跑到 3（正是 B 的列界外）就被拦下，"
                 f"此前 k 完整跑完 3 趟（[6,6,6]，{p3_trace}）")
    lines.append(f"    执行探针红：j=3 时 load %b[k,3] 第 1 维越界（{p3_exec}）；"
                 f"真实报错：{err3}")
    lines.append("    注意：这次越界的线性地址 3·k+3 大多仍在 B 的 18 格缓冲区内——"
                 "只查线性地址抓不住，按维检查才能抓住（stride 类 bug 的共性）")
    lines.append("  —— 三个探针全红：边界测试咬得住人，才配当 Day 89 填空时的护栏")
    return ok, lines


# ============================================================ 报告与产出

def env_line():
    return (f"Linux {platform.machine()}, Python {platform.python_version()}, "
            f"numpy {np.__version__}; 本机未安装 MLIR（DialectConversion 语义仿真＋"
            f"IV 轨迹/按维越界解释执行，不伪造 MLIR 行为）")


def loop_header(pattern):
    lines = [
        "// 生成自 loop_pass.py（Day 88）——三重循环生成＋循环规格表",
        "// 相对 Day 87：op 产出不变（13 op），循环改由 LoopSpec 驱动（单一事实来源）；",
        "// 访存与累加（load×2/mulf/addf/store）按计划留给 Day 89。",
        "//",
        "// 循环规格表（LoopSpec——四要素＋上界来源）：",
        "//   iv   lb  ub  step  trip = max(0, ceil((ub-lb)/step))   ub 来源",
    ]
    for s in pattern.specs:
        lines.append(f"//   {s.iv:<4} {s.lb:>2}  {s.ub:>2}  {s.step:>4}  "
                     f"max(0, ceil(({s.ub}-{s.lb})/{s.step})) = {trip_count(s):<3}     "
                     f"{s.ub_source}")
    lines += [
        "//",
        "// 语义依据（官方 scf.for，mlir.llvm.org，2026-11 核对）：",
        "//   半开区间 [lb, ub)：含下界、不含上界；iv 取 lb + j·step（j = 0..trip-1）；",
        "//   step 必须严格为正；iv 是循环区域的第一个参数（index 类型，体外不可见）。",
    ]
    return lines


def build_report(results):
    lines = ["Day 88 生成三重循环·检查测试报告（真实运行）",
             f"环境：{env_line()}", ""]
    for name, ok, detail in results:
        lines.append(f"[{'PASS' if ok else 'FAIL'}] {name}")
        lines.extend(detail)
        lines.append("")
    n_pass = sum(1 for _, ok, _ in results if ok)
    lines.append(f"—— 检查测试 {n_pass}/{len(results)} PASS ——")
    lines.append("")
    lines.append("口径附注：")
    lines.append("  1. op 计数沿用 Day 86/87 口径：主图 3 op → 13 op；完整目标 = 11 目标 op ＋")
    lines.append("     Day 89 待填 5（load×2、mulf、addf、store）= 16 目标 op。")
    lines.append("  2. BT5 边界表测的是循环结构与 IV 语义（循环体仍为空）；端到端数值对照")
    lines.append("     （≥8 组 shape）是 Day 90 的验收。")
    lines.append("  3. BT7 反面控制用预演器 build_full_ir（Day 87 三策略预演器的参数化版，")
    lines.append("     方案 B）注入三个 bug；按维越界检测是今天新增的仿真探针。")
    lines.append("  4. scf.for 语义描述依据官方文档（2026-11 核对）：半开区间、")
    lines.append("     trip = max(0, ceil((ub-lb)/step))、step 严格为正、iv 为区域参数；")
    lines.append("     垃圾值是确定性公式（真实语义为未定义行为）。")
    return "\n".join(lines)


def build_boundary_table(bt5_table, k0_lines):
    head = [
        "Day 88 边界测试：7 组 shape 的循环四要素实测（真实运行）",
        f"环境：{env_line()}",
        "",
        "口径：trips(i,j,k) 为解释执行记录的每趟迭代数（i 循环进入 1 次、j 进入 M 次、",
        "      k 进入 M×N 次）；k 体总执行 = M×N×K；IV 值域 = 归纳变量实际取过的值",
        "      （半开区间，不含 ub）；%acc 终值 = yield %zero 占位下的恒等结果。",
        "",
        "—— 7 组 shape 的 trip / IV 轨迹 ——",
    ]
    tail = [
        "",
        "—— 零趟特写（K=0，A(4,0) @ B(0,3)）——",
        *k0_lines,
        "",
        "—— 分工说明 ——",
        "端到端数值对照（≥8 组 shape ＋参考结果）是 Day 90 的验收；",
        "今天只验收循环结构与 IV 语义（循环体仍为空，无访存）。",
    ]
    return "\n".join(head + bt5_table + tail)


def build_debug_log(cases):
    out = ["Day 88 调试树汇总（--debug，对应 MLIR -debug-only=dialect-conversion 的格式）", ""]
    for title, lines_ in cases:
        out.append(f"—— {title} ——")
        out.extend(lines_)
        out.append("")
    return "\n".join(out)


def run_all():
    # 主运行：一次转换，BT1~BT4 共享同一个 func / pattern / result
    func = build_main_graph()
    before_names = [op.name for op in func.walk()]
    pattern = MatMulLoopPattern()
    driver = ConversionDriver([pattern], TypeConverter(), debug=True)
    res = driver.apply(func, "full")

    results = []
    ok, lines = bt1_spec_pairing(func, res, pattern, before_names)
    results.append(("BT1 四要素与配对", ok, lines))
    ok, lines = bt2_halfopen_trace(func)
    results.append(("BT2 半开区间与 IV 轨迹", ok, lines))
    ok, lines = bt3_iv_scope(func)
    results.append(("BT3 归纳变量身份与作用域", ok, lines))
    ok, lines = bt4_nesting(func)
    results.append(("BT4 嵌套结构", ok, lines))
    ok, lines, table = bt5_boundary_shapes()
    results.append(("BT5 边界 shape 全家福", ok, lines))
    ok, lines, dbg6 = bt6_dynamic_conservative()
    results.append(("BT6 静态前提（动态拒绝）", ok, lines))
    ok, lines = bt7_probe_controls()
    results.append(("BT7 反面控制组（探针）", ok, lines))

    loop_ir = print_module(func, loop_header(pattern))
    k0 = [
        "k 循环：lb=0, ub=K=0 → trip = max(0, ceil((0-0)/1)) = 0——循环体一次都不执行；",
        "  %acc 终值 = iter_args 初值 %zero = 0.0（Day 87：零次迭代时结果 = 初值）；",
        "预演完整 IR（方案 B）执行：store 12 次（每个 (i,j) 写 0.0）· load 0 次 ·",
        "  未初始化读 0 次；C = 4×3 全零。",
        "数学佐证：空和 = 0（加法单位元）——np.matmul((4,0),(0,3)) 与同序参考实现",
        "  均为 4×3 零矩阵，逐位相同：Day 87 的初值 %zero 正是归约的单位元。",
    ]
    boundary = build_boundary_table(table, k0)

    # 调试树案例 3：只注册 HalfDone → 失败 + 回滚（预期）
    f3 = build_main_graph()
    d3 = ConversionDriver([HalfDoneLoopPattern()], TypeConverter(), debug=True)
    d3.apply(f3, "full")

    debug_log = build_debug_log([
        ("案例 1：主图正常路径（LoopSpec 驱动的三重循环落地）", driver.debug_lines),
        ("案例 2：动态维度 M='?'，保守拒绝（BT6）", dbg6),
        ("案例 3：半途而废 Pattern，回滚（BT1 回归项）", d3.debug_lines),
    ])
    return results, loop_ir, boundary, debug_log


def practice_mode(M, K, N):
    func = build_main_graph(M, K, N)
    pattern, res = run_pass(func, "full")
    print(f"形状 A({M},{K}) @ B({K},{N}) -> C({M},{N})")
    print(f"转换：{'成功' if res.ok else '失败'}——{res.message}")
    print()
    print("循环规格表（LoopSpec）：")
    print(f"  {'iv':<4} {'lb':>3} {'ub':>3} {'step':>4}  trip   ub 来源")
    for s in pattern.specs:
        print(f"  {s.iv:<4} {s.lb:>3} {s.ub:>3} {s.step:>4}  {trip_count(s):<5}  {s.ub_source}")
    A, B = make_inputs(M, K, N)
    interp = Interp({"%a": A, "%b": B})
    interp.run(func)
    tr = interp.iv_trace
    print()
    print("IV 轨迹（解释执行实测）：")
    for nm in ("%i", "%j", "%k"):
        t = tr[nm]
        vs = _fmt_set(t["values"])
        print(f"  {nm}：进入 {t['activations']} 次 · 每趟 {t['per_act'][0]} 次迭代 · "
              f"取值 {vs}")
    print()
    print(print_module(func, [
        f"// 练习模式：A({M},{K}) @ B({K},{N}) -> C({M},{N}) 的循环 IR（真实运行输出）"]))
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

    results, loop_ir, boundary, debug_log = run_all()
    report = build_report(results)

    OUT.mkdir(exist_ok=True)
    (OUT / "loop-ir.txt").write_text(loop_ir, encoding="utf-8")
    (OUT / "boundary-table.txt").write_text(boundary + "\n", encoding="utf-8")
    (OUT / "test-report.txt").write_text(report + "\n", encoding="utf-8")
    (OUT / "debug-log.txt").write_text(debug_log + "\n", encoding="utf-8")

    print(report)
    if args.debug:
        print()
        print(debug_log)
    print()
    print("loop-ir.txt / boundary-table.txt / test-report.txt / debug-log.txt 已写入 outputs/")
    all_ok = all(ok for _, ok, _ in results)
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
