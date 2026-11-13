#!/usr/bin/env python3
"""第 89 天：生成 Load、Mul、Add、Store——完成 MatMul 循环体，13 op → 18 op。

本机未安装 MLIR。与 Day 57~88 的做法一致：用 Python 复刻 MLIR DialectConversion
的 Pattern / Rewriter / 驱动器语义（仿真），不伪造 MLIR 本身的行为。
与真实 MLIR 的对应关系（依据 mlir.llvm.org 官方文档《Dialect Conversion》
《MemRef dialect》《SCF dialect》，2026-11 核对）：

    真实 MLIR 的语义                                             仿真里的对应
    ------------------------------------------------------------------------------
    memref.load/store 收多维下标，线性地址映射在                 Interp._check_bounds 用类型里的
      memref 类型（strided<[6,1]>）——IR 里看不到乘加               strides 算 addr = Σ stride·idx
    memref.alloc 不清零（垃圾值是 UB）                           garbage(addr) = 777 + 7·addr
    scf.for iter_args：区域参数=读取通道，yield=写回通道           exec_for + exec_body（D87）
    带 iter_args 的循环必须显式 scf.yield                          k 体末尾显式 yield %s
    iv 是 index 型区域参数，体外不可见（支配性）                   结构断言（D88 BT3 同款）
    动态 shape：strides/alloc 尺寸无法物化 → 保守拒绝              match 检测 '?'（D87~88 机制沿用）

今天新增的三个执行探针（解释执行器上）：
  · 访存日志：记录每一次 load/store 的 (memref, 下标, 线性地址, 值)；
  · 地址核对：每条日志用 np.ravel_multi_index 独立重算地址（Day 85 TP2 的全量版）；
  · 覆盖统计：A 每格读 N 次、B 每格读 M 次、C 每格写 1 次——Day 88 §3.2 的
    理论断言今天在执行级对账。

诚实声明（与真实 MLIR 的差异）：
  1. 真实 scf.for 的 iv/iter_args 是区域入口块参数（BlockArgument）；
     本仿真用 attrs 里预建的 Value 对象模拟（Day 87 起的做法）。
  2. 按维越界检测 / 访存日志是本仿真新增的探针（真实工程里对应运行期边界
     检查、sanitizer、模拟器 trace 一类工具）。
  3. 位等价的参考实现是「同序 i/j/k ＋ float32 逐步舍入」；np.matmul 的
     舍入顺序可能不同——它的对照差值单独报告，不当作失败。

用法：
    python3 body_pass.py                # 运行 AT1~AT6 检查测试，生成 outputs/
    python3 body_pass.py --shape 2 3 2  # 换形状：打印 IR＋访存统计＋位等价（练习用）
    python3 body_pass.py --trace        # 额外打印首个 (i,j)=(0,0) 格子的逐条访存轨迹
    python3 body_pass.py --debug        # 额外打印主图与各案例的调试树

产出：
    outputs/body-ir.txt        完整 MatMul Lowering IR（18 op；头部：地址公式表＋位置法则）
    outputs/access-table.txt   156 次访存的逐条地址核对＋覆盖统计＋(0,0) 轨迹＋完整日志
    outputs/test-report.txt    AT1~AT6 检查测试报告（真实运行）
    outputs/debug-log.txt      调试树（主图 + 动态拒绝 + 回滚案例）
"""

from __future__ import annotations

import argparse
import platform
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import numpy as np

OUT = Path(__file__).resolve().parent / "outputs"

SEED = 89          # 输入数据随机种子（A/B 矩阵），保证可复现
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


def linear_addr(strides, idxs):
    """多维下标 → 线性地址：addr = Σ stride_d · idx_d（行主序映射的核心公式）。"""
    return sum(s * v for s, v in zip(strides, idxs))


def addr_formula(strides, idxs):
    """把一次访存的地址算式写成 6·1+2 这种可读形式。"""
    parts = []
    for s, v in zip(strides, idxs):
        parts.append(f"{v}" if s == 1 else f"{s}·{v}")
    return "+".join(parts)


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

    scf.for 的约定（Day 87 建立，D88/89 沿用）：
      operands = [lb, ub, step, *iter_args 初值]
      attrs    = {"iv": "%k", "iv_value": Value,        # 归纳变量（区域第一个参数）
                  "iter_names": ["%acc"],               # iter_args 显示名
                  "iter_args": [Value, ...]}             # iter_args 区域参数（跟在 iv 后）
      results  = [Value, ...]                             # 循环结束后的循环携带值
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
    if op.name in ("arith.mulf", "arith.addf") and op.results:
        return (f"{op.results[0].name} = {op.name} {op.operands[0].name}, "
                f"{op.operands[1].name} : {op.results[0].type}")
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
    """把 func 树打印成 MLIR 风格文本（Day 87 版打印机＋D89 新增 mulf/addf 分支）。"""

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
        elif op.name in ("arith.mulf", "arith.addf"):
            lines.append(f"{pad}{op.results[0].name} = {op.name} "
                         f"{op.operands[0].name}, {op.operands[1].name}"
                         f" : {op.results[0].type}")
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
# （与 Day 86~88 相同的三段式事务：create/replaceOp 暂存 → commit / rollback）

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


# ============================================================ Day 88：LoopSpec（原样沿用）

@dataclass
class LoopSpec:
    """一条循环的出生证明：四要素 ＋ 上界来源（Day 88 的成果，单一事实来源）。

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


# ============================================================ Day 89：循环体完整版 Pattern

class MatMulBodyPattern(ConversionPattern):
    """Day 89 版 mini.matmul → 循环表示：把 Day 88 留空的循环体填满。

    相对 Day 88 的变化（op 产出 13 → 18）：
      · k 体：yield %zero 占位 → load %a[%i,%k] ＋ load %b[%k,%j] ＋ mulf ＋
        addf %acc, %p ＋ yield %s（五块肉里的四块）；
      · j 体：k 循环之后新增 store %acc, %c[%i,%j]（第五块肉——写回的终点）；
      · 其余 op（alloc/%zero/5 常量/三重循环）与 Day 88 完全相同。

    位置法则（作用域交集的最内层，见 README §3.4）：
      · %xa/%xb/%p/%s 依赖 %k（或依赖需要 %k 的值）→ 只能进 k 体；
      · store 依赖 %acc（k 循环结果，k 体外才存在）＋ %i ＋ %j → k 外、j 内；
      · 「只写最终值」再把它从 j 体内推到 k 体外：C 每格恰好写 1 次。

    注入旋钮（AT6 反面控制组用，默认全关＝正确形态）：
      · a_swap     ：load %a 的下标写成 [%k,%i]（配对错误探针 P1）
      · store_in_k ：store 放进 k 体、写 %s（位置错误探针 P2——写放大 6×）
      · yield_p    ：yield %p 丢失累加（写回通道断开探针 P3）
      · init_from_c：累加器初值 = load %c[%i,%j]（初值来源错误探针 P4——读未初始化）
    """

    root_name = "mini.matmul"
    benefit = 1
    debug_name = "MatMulBodyPattern"

    def __init__(self, a_swap=False, store_in_k=False, yield_p=False, init_from_c=False):
        self.specs = []
        self.a_swap = a_swap
        self.store_in_k = store_in_k
        self.yield_p = yield_p
        self.init_from_c = init_from_c

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
                op, f"动态维度（A{sa} @ B{sb}）：循环体访存的地址映射依赖 memref 类型里的"
                    f"静态 strides 与 alloc 尺寸（strided<[6, 1]> 的 6 就是 K），"
                    f"动态 '?' 下无从物化——本 Pattern 先支持静态 Shape（计划），宁拒不猜"
                    f"（动态版 Pattern 走 memref.dim ＋动态 alloc，后续专题）")
        if sa[1] != sb[0]:
            return rewriter.notifyMatchFailure(
                op, f"内维不匹配：A.shape[1]={sa[1]} ≠ B.shape[0]={sb[0]}，"
                    f"k 循环上界无从确定")
        M, K = sa
        N = sb[1]
        a, b = adaptor.operands[0], adaptor.operands[1]

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

        # ① 输出缓冲（Day 85 任务清单①；Day 87：alloc 不清零，零起点靠 %zero）
        alloc = rewriter.create(
            "memref.alloc", result_names=["%c"], result_types=[make_memref((M, N))],
            comments=[f"任务① 输出缓冲 {M * N * 4} B：alloc 不清零——零起点是 %zero（D87）"])

        # ② 零起点（Day 87 的成果，原样保留——今天它是 iter_args 的初值）
        zero = rewriter.create(
            "arith.constant", result_names=["%zero"], result_types=["f32"],
            attrs={"value": 0.0},
            comments=["任务③(D87) 零起点：累加器的初值（归约单位元），不写内存"])

        # ③ 5 个 index 常量——四要素的物化形态（Day 88）
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

        # 三个 iv（区域参数）——循环与循环体的访存共用同一批 Value 对象
        iv = {"%i": Value("%i", "index"), "%j": Value("%j", "index"),
              "%k": Value("%k", "index")}
        acc_arg = Value("%acc", "f32")   # iter_args 区域参数（体内 %acc＝读取通道）

        # ④ k 体五块肉（Day 89 的主角）
        xa = rewriter.create(
            "memref.load",
            operands=[a, iv["%k"], iv["%i"]] if self.a_swap else [a, iv["%i"], iv["%k"]],
            result_names=["%xa"], result_types=["f32"],
            comments=[f"任务② 读 A：A[i,k] → {K}·i+k（strides [{K},1] 在 %a 的类型里；"
                      f"i←行号，k←归约下标）" +
                      ("【探针 P1：下标配对写反——读成 A[k,i]】" if self.a_swap else "")])
        xb = rewriter.create(
            "memref.load", operands=[b, iv["%k"], iv["%j"]],
            result_names=["%xb"], result_types=["f32"],
            comments=[f"任务② 读 B：B[k,j] → {N}·k+j（strides [{N},1]；k←行号，j←列号）"])
        p = rewriter.create(
            "arith.mulf", operands=[xa.results[0], xb.results[0]],
            result_names=["%p"], result_types=["f32"],
            comments=[f"一块肉：%p = A[i,k]·B[k,j]（f32 逐步舍入）"])
        s = rewriter.create(
            "arith.addf", operands=[acc_arg, p.results[0]],
            result_names=["%s"], result_types=["f32"],
            comments=["累加值读取与写回：%acc（区域参数，读取通道）＋ %p → %s"
                      "（下一趟经 yield 回到 %acc）"])
        yield_val = p.results[0] if self.yield_p else s.results[0]
        yld = rewriter.create(
            "scf.yield", operands=[yield_val],
            comments=["写回通道：yield 把本趟结果交给下一趟的 %acc；"
                      "循环结束时成为循环结果 %acc（体外同名不同身份）"
                      + ("【探针 P3：yield %p——丢掉累加，只留最后一项乘积】"
                         if self.yield_p else "（Day 88 的 yield %zero 占位今天换成 %s）")])

        k_body = [xa, xb, p, s]
        store_comment = (f"任务② 写 C：C[i,j] → {N}·i+j——每格恰好写 1 次（最终值）")
        if self.store_in_k:
            st_in_k = rewriter.create(
                "memref.store", operands=[s.results[0], alloc.results[0],
                                          iv["%i"], iv["%j"]],
                comments=[store_comment + "【探针 P2：位置错进 k 体——写部分和，"
                          "6× 写放大（K=6 趟都写一遍）】"])
            k_body.append(st_in_k)
        k_body.append(yld)

        # ⑤ 初始化值：正确形态用 %zero；探针 P4 改成读未初始化的 C
        init_value = zero.results[0]
        j_body_pre = []
        if self.init_from_c:
            xc = rewriter.create(
                "memref.load", operands=[alloc.results[0], iv["%i"], iv["%j"]],
                result_names=["%xc"], result_types=["f32"],
                comments=["【探针 P4：累加器初值 = load %c[i,j]——读未初始化的输出缓冲，"
                          "垃圾值混进结果；正确形态见 %zero（D87 方案 B）】"])
            j_body_pre.append(xc)
            init_value = xc.results[0]

        def loop_comments(sp):
            return [f"四要素：lb={sp.lb}（含）· ub={sp.ub}（不含——半开区间 [{sp.lb},{sp.ub})）"
                    f"· step={sp.step} · trip = max(0, ceil((ub-lb)/step)) = {trip_count(sp)}",
                    f"ub 来源：{sp.ub_source}；{sp.iv} 是本循环的区域参数"
                    f"（index 类型，体内可见、体外不可见）"]

        # ⑥ 三重循环：从内向外创建；%acc（iter_args）挂在 k 上（Day 87/88）
        fk = rewriter.create(
            "scf.for", operands=[lo, bk, st, init_value],
            result_names=["%acc"], result_types=["f32"],
            attrs={"iv": "%k", "iv_value": iv["%k"],
                   "iter_names": ["%acc"], "iter_args": [acc_arg]},
            body=k_body,
            comments=[*loop_comments(specs[2]),
                      "iter_args(%acc = " + init_value.name + ")：归约在最内层（D87/88）",
                      "体内 %acc（区域参数）≠ 体外 %acc（循环结果）；带 iter_args 必须显式 yield"])

        j_body = j_body_pre + [fk]
        if not self.store_in_k:
            st_op = rewriter.create(
                "memref.store", operands=[fk.results[0], alloc.results[0],
                                          iv["%i"], iv["%j"]],
                comments=[store_comment + "；位置在 k 外、j 内——作用域交集的最内层"
                          "（%acc 出了 k 才有、%j 出了 j 就没）"])
            j_body.append(st_op)

        fj = rewriter.create("scf.for", operands=[lo, bn, st],
                             attrs={"iv": "%j", "iv_value": iv["%j"]},
                             body=j_body, comments=loop_comments(specs[1]))
        fi = rewriter.create("scf.for", operands=[lo, bm, st],
                             attrs={"iv": "%i", "iv_value": iv["%i"]},
                             body=[fj], comments=loop_comments(specs[0]))
        # ---------- 处置 root：%mm(tensor) → %c(memref)；uses 延迟到 finalize 替换 ----------
        rewriter.replaceOp(op, [alloc.results[0]])
        return True


class HalfDoneBodyPattern(ConversionPattern):
    """反面教材（AT1 回归用）：先 create alloc＋load＋mulf 再放弃——
    验证 Pattern 仍满足「失败不留痕」（Day 86 DT6 / Day 87 IT5 / Day 88 BT1 的延续）。"""

    root_name = "mini.matmul"
    benefit = 2
    debug_name = "HalfDoneBodyPattern"

    def matchAndRewrite(self, op, adaptor, rewriter):
        bad = rewriter.create("memref.alloc", result_names=["%bad"],
                              result_types=["memref<4x3xf32, strided<[3, 1]>>"])
        c = rewriter.create("arith.constant", result_names=["%bad0"],
                            result_types=["index"], attrs={"value": 0})
        v = Value("%badv", "f32")
        ld = rewriter.create("memref.load", operands=[bad.results[0], c.results[0], c.results[0]],
                             result_names=["%badl"], result_types=["f32"])
        rewriter.create("arith.mulf", operands=[ld.results[0], v],
                        result_names=["%badp"], result_types=["f32"])
        return rewriter.notifyMatchFailure(
            op, "故意半途而废：先 create 了 alloc＋常量＋load＋mulf 再放弃"
                "（回归测试：回滚必须不留痕）")


# ============================================================ 测试图构造

def build_main_graph(M=4, K=6, N=3):
    """S0 源图：Day 83 终图 GEMM 的形状（Day 85~89 贯穿例子）。"""
    x = Value("%x", f"tensor<{M}x{K}xf32>")
    w = Value("%w", f"tensor<{K}x{N}xf32>")
    mm = Value("%mm", f"tensor<{M}x{N}xf32>")
    matmul = Op("mini.matmul", [x, w], [mm])
    ret = Op("func.return", [mm])
    return Op("func.func", body=[matmul, ret],
              attrs={"sym_name": "main", "args": [x, w],
                     "result_types": [f"tensor<{M}x{N}xf32>"]})


def build_dynamic_graph(dyn="M"):
    """动态维度变体：M 或 N 为 '?'——测保守拒绝路径（AT5）。"""
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


def run_pass(func, mode="full", patterns=None, debug=False):
    """跑一次 Day 89 版 MatMul Lowering Pass。返回 (pattern, result)。"""
    pats = patterns if patterns is not None else [MatMulBodyPattern()]
    pattern = pats[0]
    driver = ConversionDriver(pats, TypeConverter(), debug=debug)
    res = driver.apply(func, mode)
    return pattern, res


# walk 先序：func, alloc, zero, c×5, for×3, load×2, mulf, addf, yield, store, return
EXPECTED_BODY = (["func.func", "memref.alloc"]
                 + ["arith.constant"] * 6       # %zero(f32) ＋ 5 个 index 常量
                 + ["scf.for"] * 3
                 + ["memref.load"] * 2 + ["arith.mulf", "arith.addf", "scf.yield",
                                         "memref.store", "func.return"])   # 合计 18 op


# ============================================================ 解释执行器
# （Day 87 的内存语义验证器 ＋ Day 88 的 IV 轨迹/按维越界探针
#   ＋ Day 89 的访存日志探针）

class MemRefOOBError(RuntimeError):
    """按维下标越界（Day 88 探针）：线性地址仍在缓冲区内 ≠ 下标合法。"""


class Interp:
    """最小解释执行器：跑通 alloc/fill/load/store/scf.for(iter_args)/yield/mulf/addf。

    内存模型（Day 87）：每块 memref 是 list[[state, value]]，state ∈ {"uninit", "written"}；
    垃圾值是确定性公式 garbage(addr) = 777 + 7·addr（真实语义是未定义行为）。

    Day 89 新增探针：
      · access_log：每次 load/store 记录 (kind, mem 名, 下标元组, 线性地址, 值)——
        地址核对（AT2）与覆盖统计（AT2/AT4）的数据来源。
    Day 88 探针（原样沿用）：
      · iv_trace：归纳变量的执行轨迹；
      · 按维越界检测：load/store 前逐维检查下标 ∈ [0, dim)，违规抛 MemRefOOBError。
    """

    def __init__(self, args_data):
        self.env = {}      # id(Value) -> int | np.float32
        self.mem = {}      # id(Value) -> list[[state, np.float32]]
        self.stats = {"uninit_reads": [], "loads": 0, "stores": 0, "fills": 0, "allocs": 0}
        self.iv_trace = {}  # iv 名 -> {"activations", "per_act", "values"}
        self.access_log = []  # Day 89：(kind, mem 名, 下标元组, 线性地址, 值)
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
            idxs = tuple(int(self.val(i)) for i in op.operands[1:])
            if cell[0] == "uninit":
                self.stats["uninit_reads"].append((m.name, idxs, addr))
            self.env[id(op.results[0])] = np.float32(cell[1])
            self.stats["loads"] += 1
            self.access_log.append(("load", m.name, idxs, addr, np.float32(cell[1])))
        elif n == "memref.store":
            m = op.operands[1]
            addr = self._check_bounds(op)
            val = np.float32(self.val(op.operands[0]))
            self.mem[id(m)][addr] = ["written", val]
            self.stats["stores"] += 1
            idxs = tuple(int(self.val(i)) for i in op.operands[2:])
            self.access_log.append(("store", m.name, idxs, addr, val))
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
        """执行 scf.for（官方语义：半开区间、step 严格为正、iv 区域参数）。"""
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
                self.env[id(rarg)] = v   # 体内 iter_args ← 当前值（读取通道）
            yv = self.exec_body(op.body)
            if yv is not None:
                cur = yv                 # yield 回传 → 下一轮（写回通道）
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


def make_inputs(M=4, K=6, N=3, seed=SEED):
    """固定种子的输入矩阵（可复现）。"""
    rng = np.random.RandomState(seed)
    return (rng.randn(M, K).astype(np.float32),
            rng.randn(K, N).astype(np.float32))


# ============================================================ 通用运行工具

def run_case(patterns, M=4, K=6, N=3, seed=SEED):
    """跑一次「转换＋解释执行」：返回 (res, interp, func, C, err)。

    err 为 MemRefOOBError 的文本（执行被探针拦下时 C 为 None）。
    """
    func = build_main_graph(M, K, N)
    _, res = run_pass(func, "full", patterns=patterns)
    if not res.ok:
        return res, None, func, None, None
    A, B = make_inputs(M, K, N, seed)
    interp = Interp({"%a": A, "%b": B})
    err = None
    try:
        interp.run(func)
    except MemRefOOBError as exc:
        err = str(exc)
    C = None
    if err is None and interp.ret is not None:
        C = np.array([cell[1] for cell in interp.mem[interp.ret]],
                     dtype=np.float32).reshape(M, N)
    return res, interp, func, C, err


def mem_shapes(func):
    """名字 → shape：函数入参 ＋ alloc 结果（地址核对时用）。"""
    m = {}
    for a in func.attrs["args"]:
        m[a.name] = memref_shape(a.type)
    for op in func.walk():
        if op.name == "memref.alloc":
            m[op.results[0].name] = memref_shape(op.results[0].type)
    return m


def mem_strides_of(func):
    """名字 → strides（来自 memref 类型——「映射声明在类型里」的直接证据）。"""
    m = {}
    for a in func.attrs["args"]:
        m[a.name] = memref_strides(a.type)
    for op in func.walk():
        if op.name == "memref.alloc":
            m[op.results[0].name] = memref_strides(op.results[0].type)
    return m


def coverage(interp, func):
    """覆盖统计：mem 名 → Counter(addr -> 次数)。"""
    cov = {"%a": Counter(), "%b": Counter(), "%c": Counter()}
    for kind, mem, idx, addr, val in interp.access_log:
        cov[mem][addr] += 1
    return cov


# ============================================================ 检查测试 AT1~AT6

def _layout(func):
    """主图（正确形态转换后）的关键位置：三条循环、两个 load、mulf/addf/yield、store。"""
    fi = func.body[7]
    fj = fi.body[0]
    fk = fj.body[0]
    loads = [o for o in fk.body if o.name == "memref.load"]
    mulf = [o for o in fk.body if o.name == "arith.mulf"][0]
    addf = [o for o in fk.body if o.name == "arith.addf"][0]
    yld = fk.body[-1]
    store = fj.body[-1]
    return fi, fj, fk, loads, mulf, addf, yld, store


def at1_structure_position(func, res, pattern, before_names):
    """AT1 结构与位置：18 op；五块肉的层次与操作数；Day 87/88 栏目回归；回滚不留痕。"""
    after = [op.name for op in func.walk()]
    body = func.body
    alloc, zero, consts, fi = body[0], body[1], body[2:7], body[7]
    fi2, fj, fk, loads, mulf, addf, yld, store = _layout(func)
    seq_ok = after == EXPECTED_BODY
    cv = {}   # 常量值对账用
    for op in func.walk():
        if op.name == "arith.constant":
            cv[id(op.results[0])] = op.attrs["value"]

    # ---- 五块肉的层次与顺序 ----
    k_names = [o.name for o in fk.body]
    body_ok = (k_names == ["memref.load", "memref.load", "arith.mulf",
                           "arith.addf", "scf.yield"]
               and fj.body == [fk, store] and len(fi.body) == 1)
    # yield %s（写回通道）而不是 Day 88 的 %zero
    yield_ok = (yld.operands[0] is addf.results[0]
                and addf.operands[0] is fk.attrs["iter_args"][0]
                and addf.operands[1] is mulf.results[0]
                and mulf.operands == [loads[0].results[0], loads[1].results[0]])
    # store：值=%acc（k 循环结果），缓冲=%c，下标=[%i,%j]；不在 k 体、也不在 i 体
    all_stores = [o for o in func.walk() if o.name == "memref.store"]
    all_loads = [o for o in func.walk() if o.name == "memref.load"]
    store_ok = (len(all_stores) == 1 and all_stores[0] is store
                and store.operands[0] is fk.results[0]
                and store.operands[1] is alloc.results[0]
                and store.operands[2] is fi.attrs["iv_value"]
                and store.operands[3] is fj.attrs["iv_value"]
                and len(all_loads) == 2 and all(o in fk.body for o in all_loads))
    # 初始化：%zero 在三重循环之前；iter_args 初值 = %zero
    init_ok = (fk.operands[3] is zero.results[0]
               and fk.attrs["iter_names"] == ["%acc"]
               and body.index(fi) > body.index(zero))
    # Day 87/88 栏目回归
    reg_ok = (alloc.results[0].type == make_memref((4, 3))
              and sorted(int(c.attrs["value"]) for c in consts) == [0, 1, 3, 4, 6]
              and zero.attrs["value"] == 0.0
              and [(s.iv, s.lb, s.ub, s.step) for s in pattern.specs]
              == [("%i", 0, 4, 1), ("%j", 0, 3, 1), ("%k", 0, 6, 1)])
    # 回滚回归：HalfDone（先 create 五类 op 再拒绝）不留痕
    fa = build_main_graph()
    _, ra = run_pass(fa, "full", patterns=[MatMulBodyPattern(), HalfDoneBodyPattern()])
    fb = build_main_graph()
    run_pass(fb, "full")
    roll_ok = ra.ok and print_module(fa) == print_module(fb)
    # 13 → 18：恰好比 Day 88 多 5 个 op
    delta_ok = len(after) == 18 and len(before_names) == 3
    ok = (res.ok and seq_ok and body_ok and yield_ok and store_ok
          and init_ok and reg_ok and roll_ok and delta_ok)
    lines = [
        f"  转换前 {len(before_names)} op → 转换后 {len(after)} op（Day 88 的 13 ＋ 今日 5："
        f"load×2/mulf/addf/store；walk 序列与 EXPECTED_BODY 逐项相同（{seq_ok}））",
        f"  k 体（最内层）：{k_names}——%xa/%xb/%p/%s/yield 依次排列（{body_ok}）；"
        f"yield 的操作数是 %s（addf 结果），不再是 Day 88 的 %zero（{yield_ok}）",
        f"  addf 的两个操作数：%acc（iter_args 区域参数，读取通道）＋ %p（mulf 结果）——"
        f"累加值「读」自区域参数（同 yield_ok）",
        f"  store 位置：fj.body = [fk, store]——k 外、j 内；值 = %acc（k 循环结果）、"
        f"缓冲 = %c、下标 = [%i,%j]（{store_ok}）；load 只出现在 k 体（2 个）",
        f"  初始化位置：%zero 在三重循环之前、iter_args 初值 = %zero（{init_ok}）——"
        f"Day 87 的方案 B 原样落地",
        f"  Day 87/88 栏目回归：alloc 4x3、index 常量 {{0,1,3,4,6}}、LoopSpec 三条、"
        f"iter_names %acc（{reg_ok}）",
        f"  回滚回归：HalfDone(先 create alloc+load+mulf 再拒绝) 回滚后，终图与只用"
        f"Body Pattern 的结果逐字相同（{roll_ok}）",
        f"  mini 方言残留：{[n for n in after if n.startswith('mini.')] or '无'}",
    ]
    return ok, lines


def at2_address_mapping(interp, func):
    """AT2 地址映射与覆盖：下标配对（结构）＋ 156 条访存逐条地址核对（执行）＋
    覆盖统计（A 每格 N 次、B 每格 M 次、C 每格 1 次）。"""
    fi, fj, fk, loads, mulf, addf, yld, store = _layout(func)
    # ---- 结构：下标配对（谁在哪个位置）----
    pair_a = (loads[0].operands[0].name == "%a"
              and loads[0].operands[1] is fi.attrs["iv_value"]
              and loads[0].operands[2] is fk.attrs["iv_value"])
    pair_b = (loads[1].operands[0].name == "%b"
              and loads[1].operands[1] is fk.attrs["iv_value"]
              and loads[1].operands[2] is fj.attrs["iv_value"])
    pair_c = (store.operands[2] is fi.attrs["iv_value"]
              and store.operands[3] is fj.attrs["iv_value"])
    pair_ok = pair_a and pair_b and pair_c
    # ---- 执行：逐条地址核对（independent：np.ravel_multi_index）----
    shapes = mem_shapes(func)
    strides = mem_strides_of(func)
    formula_ok, n_checked, samples = True, 0, []
    for kind, mem, idx, addr, val in interp.access_log:
        expect = int(np.ravel_multi_index(idx, shapes[mem], order="C"))
        mine = linear_addr(strides[mem], idx)
        if not (addr == expect == mine):
            formula_ok = False
        n_checked += 1
        if len(samples) < 4:
            samples.append(f"{mem}{list(idx)} → {addr_formula(strides[mem], idx)} = {addr}")
    # ---- 执行：覆盖统计 ----
    cov = coverage(interp, func)
    cov_a_ok = (set(cov["%a"]) == set(range(24))
                and all(c == 3 for c in cov["%a"].values()))
    cov_b_ok = (set(cov["%b"]) == set(range(18))
                and all(c == 4 for c in cov["%b"].values()))
    cov_c_ok = (set(cov["%c"]) == set(range(12))
                and all(c == 1 for c in cov["%c"].values()))
    n_loads = interp.stats["loads"]
    n_stores = interp.stats["stores"]
    counts_ok = n_loads == 144 and n_stores == 12
    # ---- 下标取值域：A 的 (i,k) 落在 [0,4)×[0,6)，B 的 (k,j) 落在 [0,6)×[0,3) ----
    dom_ok = (all(0 <= e[2][0] < 4 and 0 <= e[2][1] < 6
                  for e in interp.access_log if e[1] == "%a")
              and all(0 <= e[2][0] < 6 and 0 <= e[2][1] < 3
                      for e in interp.access_log if e[1] == "%b")
              and all(0 <= e[2][0] < 4 and 0 <= e[2][1] < 3
                      for e in interp.access_log if e[1] == "%c"))
    ok = (pair_ok and formula_ok and cov_a_ok and cov_b_ok and cov_c_ok
          and counts_ok and dom_ok and n_checked == 156)
    lines = [
        f"  下标配对（结构）：A[%i,%k]、B[%k,%j]、C[%i,%j]——i←行号、k←归约下标、"
        f"j←列号；三个 iv 都用对了循环（{pair_ok}）",
        f"  地址公式（执行，{n_checked} 条访存逐条核对）：addr = Σ stride·idx，与"
        f"np.ravel_multi_index 独立重算全部相等（{formula_ok}）；strides 取自"
        f"memref 类型：A{strides['%a']} · B{strides['%b']} · C{strides['%c']}",
        f"    样例：{' ； '.join(samples)}",
        f"  覆盖统计（执行）：A 的 24 格每格恰好读 {3} 次（72 loads）· B 的 18 格每格"
        f"恰好读 {4} 次（72）· C 的 12 格每格恰好写 {1} 次（12 stores）"
        f"（{cov_a_ok and cov_b_ok and cov_c_ok}）——Day 88 §3.2 的理论断言今日对账",
        f"  访存总数：load {n_loads} = 2·M·N·K = 2·4·3·6 · store {n_stores} = M·N = 12"
        f"（{counts_ok}）；下标取值域全部合法（{dom_ok}）",
    ]
    return ok, lines


def at3_bit_equivalence(interp, func, C):
    """AT3 数值与访存统计：与同序参考实现位等价；np.matmul 差值单独报告（不算失败）。"""
    A, B = make_inputs()
    ref = reference_matmul(A, B)
    bit_ok = np.array_equal(C, ref)
    npm = np.matmul(A, B)
    npm_diff = float(np.max(np.abs(C - npm))) if C.shape == npm.shape else float("nan")
    np_equal = bool(np.array_equal(C, npm))
    st = interp.stats
    stats_ok = (st["loads"] == 144 and st["stores"] == 12
                and st["uninit_reads"] == [] and st["allocs"] == 1 and st["fills"] == 0)
    # 首格手算对账：C[0,0] = ((A[0,0]·B[0,0] + A[0,1]·B[1,0]) + …) 同序逐步舍入
    acc = np.float32(0.0)
    for k in range(6):
        acc = np.float32(acc + np.float32(A[0, k] * B[k, 0]))
    first_ok = float(C[0, 0]) == float(acc)
    # 垃圾值探针回归：alloc 之后、store 之前，C 的格子必须没有被读过（无 uninit_reads
    # 已在 stats_ok 里）；再验证终态全部 written
    all_written = all(c[0] == "written" for c in interp.mem[interp.ret])
    ok = bit_ok and stats_ok and first_ok and all_written
    lines = [
        f"  位等价（执行）：C 与同序参考实现（i/j/k ＋ float32 逐步舍入）逐位相等："
        f"np.array_equal = {bit_ok}",
        f"  np.matmul 对照：逐位相等 = {np_equal}，max|C − np.matmul| = {npm_diff:.3e}"
        f"（单独报告，不算失败——舍入顺序可能不同）",
        f"  访存统计：load 144（= 2·M·N·K）· store 12（= M·N）· alloc 1 · fill 0 ·"
        f"未初始化读 0（{stats_ok}）",
        f"  首格手算对账：C[0,0] = {float(C[0, 0]):+.6f} 与手算逐步舍入的"
        f"{float(acc):+.6f} 相等（{first_ok}）；C 的 12 格终态全部 written（{all_written}）"
        f"——alloc 的垃圾值被 12 次 store 全部覆盖",
    ]
    return ok, lines, npm_diff, np_equal


SHAPES = [(1, 1, 1), (1, 5, 3), (5, 1, 3), (2, 3, 2), (3, 2, 7), (4, 6, 3), (4, 0, 3)]


def at4_shapes_end_to_end():
    """AT4 边界 shape 端到端：7 组形状转换＋执行＋位等价＋覆盖（Day 90 前的预飞）。"""
    lines, table, ok = [], [], True
    for (M, K, N) in SHAPES:
        res, interp, func, C, err = run_case([MatMulBodyPattern()], M, K, N)
        A, B = make_inputs(M, K, N)
        ref = reference_matmul(A, B)
        good = (res.ok and err is None and C is not None and np.array_equal(C, ref))
        note = ""
        if K == 0:
            npm = np.matmul(A, B)
            good = good and float(np.max(np.abs(C))) == 0.0 and np.array_equal(npm, ref)
            note = "（K=0：load 0 次、store 12 次写 0.0——空归约单位元，D87/88 的伏笔）"
        if good:
            cov = coverage(interp, func)
            n_a, n_b, n_c = M * K, K * N, M * N
            good = (set(cov["%a"]) == set(range(n_a))
                    and all(c == N for c in cov["%a"].values())
                    and set(cov["%b"]) == set(range(n_b))
                    and all(c == M for c in cov["%b"].values())
                    and set(cov["%c"]) == set(range(n_c))
                    and all(c == 1 for c in cov["%c"].values())
                    and interp.stats["loads"] == 2 * M * N * K
                    and interp.stats["stores"] == M * N
                    and interp.stats["uninit_reads"] == [])
        ok &= good
        cov_note = (f"A 每格读 {N} 次 · B 每格读 {M} 次 · C 每格写 1 次" if K > 0
                    else "A/B 无访问（k 零趟）· C 每格写 1 次")
        table.append(
            f"  A({M},{K}) @ B({K},{N}) → C({M},{N})：load {interp.stats['loads'] if interp else '—'}"
            f"（=2·{M}·{N}·{K}）· store {interp.stats['stores'] if interp else '—'}"
            f"（={M}·{N}）· {cov_note} ·"
            f" 位等价 {'✓' if good else '✗'} {note}")
    lines.append(f"  7 组形状全部端到端通过（明细见 access-table.txt）：与同序参考实现逐位"
                 f"相等，覆盖统计与 shape 参数一致（{ok}）")
    lines.append("  成员：最小 (1,1,1) · 行向量 (1,5,3) · 内维 1 (5,1,3) · 非方形 (2,3,2)/"
                 "(3,2,7) · 贯穿例 (4,6,3) · 零趟 (4,0,3)")
    lines.append("  分工：这是「循环体正确性」预飞；Day 90 按计划做 ≥8 组边界 shape 的"
                 "系统对照（1×N、M×1、小 K、维度 1）与修复")
    return ok, lines, table


def at5_dynamic_conservative():
    """AT5 静态前提回归：动态 '?' → strides/alloc 尺寸无法物化 → 保守拒绝。"""
    lines, ok = [], True
    f1 = build_dynamic_graph("M")
    _, r1 = run_pass(f1, "full", debug=True)
    good1 = (not r1.ok and "无法合法化 'mini.matmul'" in r1.message
             and "都拒绝了这次匹配" in r1.message)
    ok &= good1
    lines.append(f"  A(?x6) @ B(6x3)（M 动态），full 模式：{'按预期失败' if not r1.ok else '意外成功'}")
    lines.append("  拒绝的焦点（今天视角）：访存的地址映射依赖 memref 类型里的静态 strides"
                 "（strided<[6,1]> 的 6 就是 K）与 alloc 尺寸——动态 '?' 下无从物化")
    dbg_text = "\n".join(r1.debug_lines)
    in_debug = "静态 strides" in dbg_text and "宁拒不猜" in dbg_text
    ok &= in_debug
    lines.append(f"  拒绝原因（只在 --debug 调试树，真实文本）：…循环体访存的地址映射依赖"
                 f"memref 类型里的静态 strides 与 alloc 尺寸…宁拒不猜（{in_debug}）")
    f2 = build_dynamic_graph("N")
    _, r2 = run_pass(f2, "partial")
    good2 = r2.ok and r2.residue == ["mini.matmul"]
    ok &= good2
    lines.append(f"  N 动态（A(4x6) @ B(6x?)），partial 模式：成功，显式残留 {r2.residue}"
                 f"（交给后续 Pass——动态版 Pattern 走 memref.dim ＋动态 alloc）")
    return ok, lines, r1.debug_lines


def at6_probe_controls():
    """AT6 反面控制组：四个故意注入的访存 bug，全部被结构/执行探针拦下。"""
    lines, ok = [], True
    A, B = make_inputs()
    ref = reference_matmul(A, B)

    # ---- P1 下标配对写反：load %a[%k,%i] ----
    res1, it1, func1, C1, err1 = run_case([MatMulBodyPattern(a_swap=True)])
    a_loads = [e for e in it1.access_log if e[1] == "%a"] if it1 else []
    p1_struct = (res1.ok and len(a_loads) == 4
                 and [e[2] for e in a_loads] == [(0, 0), (1, 0), (2, 0), (3, 0)]
                 and it1 is not None and it1.stats["loads"] == 8)
    p1_exec = (C1 is None and err1 is not None
               and "第 0 维下标 4 ∉ [0, 4)" in err1 and "%a" in err1)
    ok &= p1_struct and p1_exec
    lines.append(f"  P1 配对写反（load %a[%k,%i]，A(4,6) 被当成 6×4 用）：转换成功"
                 f"（结构上完全合法——这正是它阴险的地方），执行探针红（{p1_exec}）")
    lines.append(f"    执行证据：拦截前读了 A 的 {(0, 0), (1, 0), (2, 0), (3, 0)} ——"
                  f"读的是 A 的第 0 列而不是第 0 行（{p1_struct}）；"
                  f"真实报错：{err1 if err1 else '（未执行）'}")

    # ---- P2 store 位置错进 k 体：写部分和 ----
    res2, it2, func2, C2, err2 = run_case([MatMulBodyPattern(store_in_k=True)])
    fk2 = func2.body[7].body[0].body[0] if res2.ok else None
    st_in_k = [o for o in fk2.body if o.name == "memref.store"] if fk2 else []
    p2_struct = (res2.ok and len(st_in_k) == 1
                 and func2.body[7].body[0].body == [fk2])
    p2_num = (err2 is None and C2 is not None and np.array_equal(C2, ref))
    p2_traffic = (it2 is not None and it2.stats["stores"] == 72
                  and it2.stats["loads"] == 144)
    ok &= p2_struct and p2_num and p2_traffic
    lines.append(f"  P2 位置错误（store 放进 k 体、写 %s）：数值**恰好**还对——最后一趟"
                 f"写覆盖前面的部分和，位等价仍成立（{p2_num}）；但 store {it2.stats['stores']}"
                 f" 次 = 正确形态 12 次的 6 倍（K=6，每格写 6 遍）（{p2_traffic}）"
                 f"——写放大不算正确性 bug，但一旦有别的读者/并发就是错")
    lines.append(f"    结构证据：k 体里出现 store（{len(st_in_k)} 个），j 体只剩 k 循环"
                 f"（{p2_struct}）；正确位置见 AT1——k 外、j 内")

    # ---- P3 写回通道断开：yield %p ----
    res3, it3, func3, C3, err3 = run_case([MatMulBodyPattern(yield_p=True)])
    diff3 = float(np.max(np.abs(C3 - ref))) if C3 is not None else float("nan")
    last_products = np.outer(A[:, -1], B[-1, :]).astype(np.float32)
    p3_struct = (res3.ok and err3 is None and C3 is not None
                 and np.array_equal(C3, last_products))
    p3_quiet = (it3 is not None and it3.stats["loads"] == 144
                and it3.stats["stores"] == 12
                and it3.stats["uninit_reads"] == [])
    ok &= p3_struct and p3_quiet and diff3 > 0.0
    lines.append(f"  P3 写回通道断开（yield %p，丢掉累加）：C[i,j] = 最后一项乘积"
                 f"A[i,5]·B[5,j]（与 np.outer 逐位相等，{p3_struct}）——访存计数"
                 f"144/12 全部正常（{p3_quiet}），只有数值对照抓得住：")
    lines.append(f"    max|C − ref| = {diff3:.3e}（{diff3 > 0.0}）——Day 88 的"
                  f"yield %zero 占位如果忘了换，症状是全零（恒等循环）；忘的是 %s"
                  f"则是「只留最后一项」")

    # ---- P4 累加器初值读未初始化的 C ----
    res4, it4, func4, C4, err4 = run_case([MatMulBodyPattern(init_from_c=True)])
    fj4 = func4.body[7].body[0] if res4.ok else None
    xc = [o for o in fj4.body if o.name == "memref.load"] if fj4 else []
    diff4 = float(np.max(np.abs(C4 - ref))) if C4 is not None else float("nan")
    p4_struct = (res4.ok and err4 is None and len(xc) == 1
                 and xc[0].operands[0].name == "%c"
                 and fj4.body[0] is xc[0])
    p4_uninit = (it4 is not None and len(it4.stats["uninit_reads"]) == 12
                 and all(u[0] == "%c" for u in it4.stats["uninit_reads"]))
    p4_loads = it4 is not None and it4.stats["loads"] == 156   # 144 ＋ 12 次对 C 的读
    ok &= p4_struct and p4_uninit and p4_loads and diff4 > 0.0
    lines.append(f"  P4 初值来源错误（累加器初值 = load %c[%i,%j]）：结构完全合法，"
                 f"但 12 次**未初始化读**全被 Day 87 的探针记录在案（{p4_uninit}），"
                 f"load 总数 {it4.stats['loads']} = 144＋12（{p4_loads}）")
    lines.append(f"    垃圾值公式 777＋7·addr 混进结果：max|C − ref| = {diff4:.3e}"
                 f"（{diff4 > 0.0}）；正确形态是 %zero（D87 方案 B）——read-modify-write"
                 f"只在 C 已有语义值时才合法（GEMM 的 beta≠0 场景）")
    lines.append("  —— 四个探针全红：配对、位置、写回、初值——今天讲的四件事，"
                 "每一件都有真实报错作证")
    return ok, lines


# ============================================================ 报告与产出

def env_line():
    return (f"Linux {platform.machine()}, Python {platform.python_version()}, "
            f"numpy {np.__version__}; 本机未安装 MLIR（DialectConversion 语义仿真＋"
            f"访存日志解释执行，不伪造 MLIR 行为）")


def body_header(pattern):
    """body-ir.txt 头部：地址公式表（D85 清单②落地）＋ 位置法则 ＋ LoopSpec 表。"""
    lines = [
        "// 生成自 body_pass.py（Day 89）——循环体收官：load×2＋mulf＋addf＋store",
        "// 相对 Day 88：13 op → 18 op（新增 5 块肉）；yield %zero 占位换成 yield %s；",
        "// 输出第一次有真实数值：与同序参考实现位等价（test-report.txt AT3）。",
        "//",
        "// 访存清单（Day 85 任务清单② 的落地；strides 声明在 memref 类型里）：",
        "//   访问     多下标      线性地址公式     strides（来自 memref 类型）",
        "//   A[i,k]   (%i, %k)   6·i + 1·k       %a: strided<[6, 1]>（6 = K）",
        "//   B[k,j]   (%k, %j)   3·k + 1·j       %b: strided<[3, 1]>（3 = N）",
        "//   C[i,j]   (%i, %j)   3·i + 1·j       %c: strided<[3, 1]>（3 = N）",
        "//",
        "// 位置法则（依赖作用域交集的最内层）：",
        "//   %xa/%xb/%p/%s 依赖 %k（或依赖需要 %k 的值） → k 体内",
        "//   store 依赖 %acc（k 循环结果）＋ %i ＋ %j      → k 外、j 内",
        "//   「只写最终值」：C 每格恰好写 1 次（AT2 覆盖统计）",
        "//   累加值读取 = iter_args 区域参数 %acc；写回 = yield %s（不是 store！）",
        "//",
        "// 循环规格表（LoopSpec——Day 88 成果原样沿用）：",
        "//   iv   lb  ub  step  trip = max(0, ceil((ub-lb)/step))   ub 来源",
    ]
    for s in pattern.specs:
        lines.append(f"//   {s.iv:<4} {s.lb:>2}  {s.ub:>2}  {s.step:>4}  "
                     f"max(0, ceil(({s.ub}-{s.lb})/{s.step})) = {trip_count(s):<3}     "
                     f"{s.ub_source}")
    lines += [
        "//",
        "// 语义依据（官方文档，mlir.llvm.org，2026-11 核对）：memref.load/store 收",
        "// 多维下标，线性地址映射 addr = Σ stride·idx 由 memref 类型的 strides 完成；",
        "// scf.for 半开区间 [lb,ub)，iv 为 index 型区域参数；带 iter_args 必须显式 yield。",
    ]
    return lines


def trace_lines(interp, func, limit=None):
    """(i,j)=(0,0) 这个格子的完整访存轨迹（直到第一条 store，含）。"""
    strides = mem_strides_of(func)
    out = []
    for i, (kind, mem, idx, addr, val) in enumerate(interp.access_log):
        out.append(f"  {i + 1:>3}. {kind:<5} {mem}[{idx[0]},{idx[1]}] → "
                   f"{addr_formula(strides[mem], idx)} = {addr:<2}  值 {float(val):+.6f}")
        if kind == "store":
            break
        if limit and len(out) >= limit:
            break
    return out


def build_access_table(interp, func, C, ref, shapes_table, npm_diff, np_equal):
    shapes = mem_shapes(func)
    strides = mem_strides_of(func)
    cov = coverage(interp, func)
    lines = [
        "Day 89 访存日志：逐条地址核对＋覆盖统计（真实运行）",
        f"环境：{env_line()}",
        "",
        "口径：每条 load/store 记录 (memref, 多维下标, 线性地址, 值)；",
        "      地址独立重算：np.ravel_multi_index(idx, shape, order='C')（Day 85 TP2 的全量版）；",
        "      覆盖统计 = 每个线性地址被访问的次数（A 读 N 次/格、B 读 M 次/格、C 写 1 次/格）。",
        "",
        "—— 地址公式（strides 声明在 memref 类型里）——",
        f"  A{shapes['%a']} strides {strides['%a']}：addr = 6·i + k",
        f"  B{shapes['%b']} strides {strides['%b']}：addr = 3·k + j",
        f"  C{shapes['%c']} strides {strides['%c']}：addr = 3·i + j",
        "",
        f"—— 逐条地址核对：{len(interp.access_log)} 条访存全部与独立重算相等 ——",
        f"  load {interp.stats['loads']} 条（%a 72 ＋ %b 72）· store {interp.stats['stores']} 条"
        f"（%c 12）· 未初始化读 {len(interp.stats['uninit_reads'])} 条",
        "",
        "—— 覆盖统计（每个线性地址的访问次数）——",
        f"  %a：{len(cov['%a'])} 格，每格读 {N_REP} 次 → 共 {sum(cov['%a'].values())} 次"
        f"（N = {N_REP}：A 的元素在所有 j 上被复用）",
        f"  %b：{len(cov['%b'])} 格，每格读 {M_REP} 次 → 共 {sum(cov['%b'].values())} 次"
        f"（M = {M_REP}：B 的元素在所有 i 上被复用）",
        f"  %c：{len(cov['%c'])} 格，每格写 1 次 → 共 {sum(cov['%c'].values())} 次"
        f"（只写最终值——store 在 k 外、j 内）",
        "",
        "—— 端到端数值 ——",
        f"  C 与同序参考实现逐位相等：{np.array_equal(C, ref)}",
        f"  C 与 np.matmul：逐位相等 = {np_equal}，max|diff| = {npm_diff:.3e}"
        f"（舍入顺序可能不同，单独报告）",
        "",
        "—— 7 组 shape 端到端明细（AT4）——",
        *shapes_table,
        "",
        "—— 首个 (i,j)=(0,0) 格子的完整访存轨迹（直到第一条 store，含）——",
        *trace_lines(interp, func),
        "",
        f"—— 完整访存日志（{len(interp.access_log)} 条，解释执行真实记录）——",
    ]
    for i, (kind, mem, idx, addr, val) in enumerate(interp.access_log):
        lines.append(f"  {i + 1:>3}. {kind:<5} {mem}[{idx[0]},{idx[1]}] → "
                     f"{addr_formula(strides[mem], idx)} = {addr:<2}  "
                     f"值 {float(val):+.6f}")
    return "\n".join(lines)


def build_report(results, npm_diff, np_equal):
    lines = ["Day 89 生成 Load/Mul/Add/Store·检查测试报告（真实运行）",
             f"环境：{env_line()}", ""]
    for name, ok, detail in results:
        lines.append(f"[{'PASS' if ok else 'FAIL'}] {name}")
        lines.extend(detail)
        lines.append("")
    n_pass = sum(1 for _, ok, _ in results if ok)
    lines.append(f"—— 检查测试 {n_pass}/{len(results)} PASS ——")
    lines.append("")
    lines.append("口径附注：")
    lines.append("  1. op 计数：主图 3 op → 18 op（Day 88 的 13 ＋ 今日 5：load×2/mulf/addf/store）；")
    lines.append("     Day 88 口径的「目标 op」16 = 18 − func.func − func.return。")
    lines.append(f"  2. np.matmul 对照：逐位相等 = {np_equal}，max|diff| = {npm_diff:.3e}——")
    lines.append("     位等价的验收对象是「同序参考实现」（i/j/k ＋ float32 逐步舍入）。")
    lines.append("  3. AT4 的 7 组 shape 是循环体正确性预飞；Day 90 按计划做 ≥8 组边界")
    lines.append("     shape 的系统对照（1×N、M×1、小 K、维度 1）与修复。")
    lines.append("  4. 访存日志/地址核对/覆盖统计/按维越界是仿真探针（对应真实工程里的")
    lines.append("     sanitizer/模拟器 trace）；scf/memref 语义依据官方文档（2026-11 核对）；")
    lines.append("     垃圾值是确定性公式（真实语义为未定义行为）。")
    return "\n".join(lines)


def build_debug_log(cases):
    out = ["Day 89 调试树汇总（--debug，对应 MLIR -debug-only=dialect-conversion 的格式）", ""]
    for title, lines_ in cases:
        out.append(f"—— {title} ——")
        out.extend(lines_)
        out.append("")
    return "\n".join(out)


# ============================================================ 主流程

M_REP, N_REP = 4, 3   # 覆盖统计报告用（贯穿例子 M=4、N=3）


def run_all():
    # 主运行：一次转换，AT1~AT3 共享同一个 func / pattern / interp
    func = build_main_graph()
    before_names = [op.name for op in func.walk()]
    pattern = MatMulBodyPattern()
    driver = ConversionDriver([pattern], TypeConverter(), debug=True)
    res = driver.apply(func, "full")
    A, B = make_inputs()
    interp = Interp({"%a": A, "%b": B})
    interp.run(func)
    C = np.array([cell[1] for cell in interp.mem[interp.ret]],
                 dtype=np.float32).reshape(4, 3)
    ref = reference_matmul(A, B)

    results = []
    ok, lines = at1_structure_position(func, res, pattern, before_names)
    results.append(("AT1 结构与位置", ok, lines))
    ok, lines = at2_address_mapping(interp, func)
    results.append(("AT2 地址映射与覆盖", ok, lines))
    ok, lines, npm_diff, np_equal = at3_bit_equivalence(interp, func, C)
    results.append(("AT3 数值与访存统计", ok, lines))
    ok, lines, shapes_table = at4_shapes_end_to_end()
    results.append(("AT4 边界 shape 端到端", ok, lines))
    ok, lines, dbg5 = at5_dynamic_conservative()
    results.append(("AT5 静态前提（动态拒绝）", ok, lines))
    ok, lines = at6_probe_controls()
    results.append(("AT6 反面控制组（探针）", ok, lines))

    body_ir = print_module(func, body_header(pattern))
    access_table = build_access_table(interp, func, C, ref, shapes_table,
                                      npm_diff, np_equal)

    # 调试树案例 3：只注册 HalfDone → 失败 + 回滚（预期）
    f3 = build_main_graph()
    d3 = ConversionDriver([HalfDoneBodyPattern()], TypeConverter(), debug=True)
    d3.apply(f3, "full")

    debug_log = build_debug_log([
        ("案例 1：主图正常路径（循环体五块肉落地）", driver.debug_lines),
        ("案例 2：动态维度 M='?'，保守拒绝（AT5）", dbg5),
        ("案例 3：半途而废 Pattern，回滚（AT1 回归项）", d3.debug_lines),
    ])
    return results, body_ir, access_table, debug_log, npm_diff, np_equal


def practice_mode(shape, trace):
    M, K, N = shape if shape else (4, 6, 3)
    func = build_main_graph(M, K, N)
    pattern = MatMulBodyPattern()
    driver = ConversionDriver([pattern], TypeConverter())
    res = driver.apply(func, "full")
    print(f"形状 A({M},{K}) @ B({K},{N}) -> C({M},{N})")
    print(f"转换：{'成功' if res.ok else '失败'}——{res.message}")
    if not res.ok:
        return 1
    A, B = make_inputs(M, K, N)
    interp = Interp({"%a": A, "%b": B})
    err = None
    try:
        interp.run(func)
    except MemRefOOBError as exc:
        err = str(exc)
    if err is not None:
        print(f"执行被探针拦下：{err}")
        return 1
    C = np.array([cell[1] for cell in interp.mem[interp.ret]],
                 dtype=np.float32).reshape(M, N)
    ref = reference_matmul(A, B)
    cov = coverage(interp, func)
    strides = mem_strides_of(func)
    print()
    print("地址公式（strides 来自 memref 类型）：")
    print(f"  A strides{strides['%a']}：addr = {strides['%a'][0]}·i+k"
          f"（{strides['%a'][0]} = K = {K}）")
    print(f"  B strides{strides['%b']}：addr = {strides['%b'][0]}·k+j"
          f"（{strides['%b'][0]} = N = {N}）")
    print(f"  C strides{strides['%c']}：addr = {strides['%c'][0]}·i+j"
          f"（{strides['%c'][0]} = N = {N}）")
    print()
    print("访存统计（解释执行实测）：")
    print(f"  load {interp.stats['loads']}（= 2·M·N·K = {2 * M * N * K}）·"
          f" store {interp.stats['stores']}（= M·N = {M * N}）·"
          f" 未初始化读 {len(interp.stats['uninit_reads'])}")
    if cov["%a"]:
        print(f"  覆盖：A 每格读 {max(cov['%a'].values())} 次（应 = N = {N}）·"
              f" B 每格读 {max(cov['%b'].values())} 次（应 = M = {M}）·"
              f" C 每格写 {max(cov['%c'].values())} 次（应 = 1）")
    print(f"  位等价（同序参考实现）：{np.array_equal(C, ref)}；"
          f"np.matmul max|diff| = {float(np.max(np.abs(C - np.matmul(A, B)))):.3e}")
    if trace:
        print()
        print(f"访存轨迹——首个 (i,j)=(0,0) 格子的完整一生（真实记录）：")
        tr = trace_lines(interp, func)
        for ln in tr:
            print(ln)
        print(f"  …其余 {len(interp.access_log) - len(tr)} 条见完整运行"
              f"（共 {len(interp.access_log)} 条）")
    print()
    print(print_module(func, [
        f"// 练习模式：A({M},{K}) @ B({K},{N}) -> C({M},{N}) 的完整循环体 IR"
        f"（真实运行输出，{len(list(func.walk()))} op）"]))
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--shape", nargs=3, type=int, metavar=("M", "K", "N"),
                    help="改写贯穿例子的形状（默认 4 6 3）；练习模式只打印，不生成产出")
    ap.add_argument("--trace", action="store_true",
                    help="（与 --shape 搭配或单独用）打印首个格子的逐条访存轨迹")
    ap.add_argument("--debug", action="store_true",
                    help="额外把调试树汇总打印到 stdout")
    args = ap.parse_args()

    if args.shape or args.trace:
        return practice_mode(args.shape, args.trace)

    results, body_ir, access_table, debug_log, npm_diff, np_equal = run_all()
    report = build_report(results, npm_diff, np_equal)

    OUT.mkdir(exist_ok=True)
    (OUT / "body-ir.txt").write_text(body_ir, encoding="utf-8")
    (OUT / "access-table.txt").write_text(access_table + "\n", encoding="utf-8")
    (OUT / "test-report.txt").write_text(report + "\n", encoding="utf-8")
    (OUT / "debug-log.txt").write_text(debug_log + "\n", encoding="utf-8")

    print(report)
    if args.debug:
        print()
        print(debug_log)
    print()
    print("body-ir.txt / access-table.txt / test-report.txt / debug-log.txt 已写入 outputs/")
    all_ok = all(ok for _, ok, _ in results)
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
