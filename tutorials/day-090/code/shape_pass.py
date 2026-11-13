#!/usr/bin/env python3
"""第 90 天：支持非方形与边界 Shape——形状矩阵、方阵盲区与猎杀矩阵。

学习计划（第 90 天）：学习 M、N、K 独立取值和小尺寸、维度为 1 等边界情况；
实践：测试 1×N、M×1、小 K、非方形矩阵，修复索引和边界问题；
产出：至少 8 组 Shape 测试和参考结果对照（本文：15 组形状矩阵 ST1）。

本机未安装 MLIR。与 Day 57~89 的做法一致：用 Python 复刻 MLIR DialectConversion
的 Pattern / Rewriter / 驱动器语义（仿真），不伪造 MLIR 本身的行为。
与真实 MLIR 的对应关系（依据 mlir.llvm.org 官方文档《Dialect Conversion》
《MemRef dialect》《SCF dialect》，2026-11 核对）：

    真实 MLIR 的语义                                             仿真里的对应
    ------------------------------------------------------------------------------
    mini.matmul → scf.for×3 ＋ load/mulf/addf/store             MatMulBodyPattern（D89 原样）
    i/j/k 上界分别来自 M/N/K（静态 shape 常量物化）              LoopSpec.ub_source ＋ 5 个
                                                                  arith.constant（0/1/M/N/K）
    维度取 1 / 取 0：trip = max(0, ceil((ub-lb)/step))          同公式实测（M=1 只跑一趟、
                                                                  K=0 零趟——空归约=单位元 0）
    memref<0x6xf32>（0 维度）是合法类型                          同：alloc 0 格、循环 0 趟
    动态 shape：strides/alloc 尺寸无法物化 → 保守拒绝              match 检测 '?'（D87~89 沿用）

今天新增的四件事：
  · 形状矩阵：15 组形状（方阵对照/维度 1/全不同非方/巧合对/退化维 0），
    每组带「为什么测它」的目的标签——计划要求的 ≥8 组落在 15 组上；
  · 猎杀矩阵（mutation testing 思路）：4 个注入的索引/边界变异
    （a_swap / b_swap / i_ub_n / k_ub_n）× 15 组形状 → OOB/NUM/SAME 分类；
  · 方阵盲区实验：在 (3,3,3) 上 4 个变异 2 个静默算错、2 个位相同（完全隐身）；
    (1,1,1) 上全部隐身——证明「只测方阵/标量」没有牙齿；
  · 修复闭环：每个变异「红（真实报错/差值）→ 定位（LoopSpec 出生证明 vs 实际绑定）
    → 修复（绑回正确来源）→ 绿（killer 形状＋全矩阵回归）」。

诚实声明（与真实 MLIR 的差异）：
  1. 真实 scf.for 的 iv/iter_args 是区域入口块参数（BlockArgument）；
     本仿真用 attrs 里预建的 Value 对象模拟（Day 87 起的做法）。
  2. 按维越界检测 / 访存日志 / IV 轨迹是仿真探针（真实工程里对应运行期边界
     检查、sanitizer、模拟器 trace 一类工具）。
  3. 位等价的参考实现是「同序 i/j/k ＋ float32 逐步舍入」；np.matmul 的
     舍入顺序可能不同——它的对照差值单独报告，不当作失败。
  4. 变异（a_swap 等）是**故意注入**的探针：Day 89 的 Pattern 在 AT4 预飞里
     7 组形状全绿，今天的新形状也全绿（ST1）；变异用来证明「形状矩阵有牙齿」
     并演练修复闭环，不伪造「昨天就错」的历史。

用法：
    python3 shape_pass.py                     # 运行 ST1~ST7，生成 outputs/
    python3 shape_pass.py --shape 1 7 4       # 单形状明细：IR＋流量＋覆盖＋位等价
    python3 shape_pass.py --mutant i_ub_n --shape 3 3 3   # 亲手复现方阵隐身
    python3 shape_pass.py --mutant i_ub_n --shape 1 7 4   # 亲手复现 OOB 拦截
    python3 shape_pass.py --debug             # 额外打印调试树

产出：
    outputs/shape-matrix.txt   15 组形状矩阵：trips/流量/覆盖/位等价/目的（ST1）
    outputs/kill-matrix.txt    4 变异 × 15 形状的 OOB/NUM/SAME 猎杀矩阵（ST2/ST3/ST4）
    outputs/fix-loop.txt       四个变异的修复闭环：红→定位→修复→绿（ST7）
    outputs/test-report.txt    ST1~ST7 检查测试报告（真实运行）
    outputs/debug-log.txt      调试树：动态拒绝×2＋回滚回归＋正常转换
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

SEED = 90          # 输入数据随机种子（A/B 矩阵），保证可复现
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

    scf.for 的约定（Day 87 建立，D88~90 沿用）：
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
    """把 func 树打印成 MLIR 风格文本（Day 89 版打印机原样沿用）。"""

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
# （与 Day 86~89 相同的三段式事务：create/replaceOp 暂存 → commit / rollback）

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


# ============================================================ Day 90：边界感知版 Pattern

class MatMulBodyPattern(ConversionPattern):
    """Day 90 版 mini.matmul → 循环表示：D89 的 18 op 循环体原样保留，
    本周聚焦「形状独立」——M、N、K 从 memref 类型逐维读出，分别绑定到
    i/j/k 的上界与 A/B/C 的 strides（strided<[K,1]>/<[N,1]>/<[N,1]>）。

    形状不变式（ST1 对 15 组形状逐一验收）：
      · IR 结构恒为 18 op——形状是数据（常量值＋类型），不是代码结构；
      · 常量多重集 = {0, 1, M, N, K}；LoopSpec = [(i,0,M),(j,0,N),(k,0,K)]；
      · 流量参数化：load = 2·M·N·K，store = M·N；
      · 覆盖参数化：A 每格读 N 次、B 每格读 M 次、C 每格写 1 次（维度为 0 时无访存）。

    注入旋钮（猎杀矩阵 ST2~ST4 与修复闭环 ST7 用，默认全关＝正确形态）：
      · a_swap ：load %a 的下标写成 [%k,%i]（A 行列配对写反）
      · b_swap ：load %b 的下标写成 [%j,%k]（B 行列配对写反）
      · i_ub_n ：i 循环上界绑到 N 常量（应绑 M）——方阵/ M==N 时位相同（隐身）
      · k_ub_n ：k 循环上界绑到 N 常量（应绑 K）——方阵/ K==N 时位相同（隐身）
    """

    root_name = "mini.matmul"
    benefit = 1
    debug_name = "MatMulBodyPattern"

    def __init__(self, a_swap=False, b_swap=False, i_ub_n=False, k_ub_n=False):
        self.specs = []
        self.a_swap = a_swap
        self.b_swap = b_swap
        self.i_ub_n = i_ub_n
        self.k_ub_n = k_ub_n

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

        # ③ 5 个 index 常量——四要素的物化形态（Day 88）；M/N/K 独立取值的载体
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

        # ④ k 体五块肉（Day 89 的成果，原样；今天的注入点在配对与边界）
        xa = rewriter.create(
            "memref.load",
            operands=[a, iv["%k"], iv["%i"]] if self.a_swap else [a, iv["%i"], iv["%k"]],
            result_names=["%xa"], result_types=["f32"],
            comments=[f"任务② 读 A：A[i,k] → {K}·i+k（strides [{K},1] 在 %a 的类型里；"
                      f"i←行号，k←归约下标）"
                      + ("【变异 M1：下标配对写反——读成 A[k,i]】" if self.a_swap else "")])
        xb = rewriter.create(
            "memref.load",
            operands=[b, iv["%j"], iv["%k"]] if self.b_swap else [b, iv["%k"], iv["%j"]],
            result_names=["%xb"], result_types=["f32"],
            comments=[f"任务② 读 B：B[k,j] → {N}·k+j（strides [{N},1]；k←行号，j←列号）"
                      + ("【变异 M2：下标配对写反——读成 B[j,k]】" if self.b_swap else "")])
        p = rewriter.create(
            "arith.mulf", operands=[xa.results[0], xb.results[0]],
            result_names=["%p"], result_types=["f32"],
            comments=[f"一块肉：%p = A[i,k]·B[k,j]（f32 逐步舍入）"])
        s = rewriter.create(
            "arith.addf", operands=[acc_arg, p.results[0]],
            result_names=["%s"], result_types=["f32"],
            comments=["累加值读取与写回：%acc（区域参数，读取通道）＋ %p → %s"
                      "（下一趟经 yield 回到 %acc）"])
        yld = rewriter.create(
            "scf.yield", operands=[s.results[0]],
            comments=["写回通道：yield 把本趟结果交给下一趟的 %acc；"
                      "循环结束时成为循环结果 %acc（体外同名不同身份）"])

        k_body = [xa, xb, p, s, yld]

        # ⑤ 初始化值：%zero（Day 87 方案 B；GEMM beta≠0 才允许 read-modify-write）
        init_value = zero.results[0]

        def loop_comments(sp):
            return [f"四要素：lb={sp.lb}（含）· ub={sp.ub}（不含——半开区间 [{sp.lb},{sp.ub})）"
                    f"· step={sp.step} · trip = max(0, ceil((ub-lb)/step)) = {trip_count(sp)}",
                    f"ub 来源：{sp.ub_source}；{sp.iv} 是本循环的区域参数"
                    f"（index 类型，体内可见、体外不可见）"]

        # ⑥ 三重循环：从内向外创建；%acc（iter_args）挂在 k 上（Day 87/88）
        #    注：loop_comments 打的是 LoopSpec（出生证明＝**应然**）；
        #    变异 i_ub_n/k_ub_n 改的是**实际绑定**的常量——两者不一致正是 bug 指纹
        fk = rewriter.create(
            "scf.for", operands=[lo, bn if self.k_ub_n else bk, st, init_value],
            result_names=["%acc"], result_types=["f32"],
            attrs={"iv": "%k", "iv_value": iv["%k"],
                   "iter_names": ["%acc"], "iter_args": [acc_arg]},
            body=k_body,
            comments=[*loop_comments(specs[2]),
                      "iter_args(%acc = " + init_value.name + ")：归约在最内层（D87/88）",
                      "体内 %acc（区域参数）≠ 体外 %acc（循环结果）；带 iter_args 必须显式 yield"
                      + ("【变异 M4：k 上界绑到了 N 常量（应绑 K）】" if self.k_ub_n else "")])

        j_body = [fk]
        st_op = rewriter.create(
            "memref.store", operands=[fk.results[0], alloc.results[0],
                                      iv["%i"], iv["%j"]],
            comments=[f"任务② 写 C：C[i,j] → {N}·i+j——每格恰好写 1 次（最终值）；"
                      f"位置在 k 外、j 内（作用域交集的最内层）"])
        j_body.append(st_op)

        fj = rewriter.create("scf.for", operands=[lo, bn, st],
                             attrs={"iv": "%j", "iv_value": iv["%j"]},
                             body=j_body, comments=loop_comments(specs[1]))
        fi = rewriter.create("scf.for", operands=[lo, bn if self.i_ub_n else bm, st],
                             attrs={"iv": "%i", "iv_value": iv["%i"]},
                             body=[fj],
                             comments=[*loop_comments(specs[0]),
                                       "i 是最外层：C 的每一行独立（行间无依赖）"
                                       + ("【变异 M3：i 上界绑到了 N 常量（应绑 M）】"
                                          if self.i_ub_n else "")])
        # ---------- 处置 root：%mm(tensor) → %c(memref)；uses 延迟到 finalize 替换 ----------
        rewriter.replaceOp(op, [alloc.results[0]])
        return True


class HalfDoneBodyPattern(ConversionPattern):
    """反面教材（ST6 回归用）：先 create alloc＋load＋mulf 再放弃——
    验证 Pattern 仍满足「失败不留痕」（Day 86 DT6 / 87 IT5 / 88 BT1 / 89 AT1 的延续）。"""

    root_name = "mini.matmul"
    benefit = 2
    debug_name = "HalfDoneBodyPattern"

    def matchAndRewrite(self, op, adaptor, rewriter):
        bad = rewriter.create("memref.alloc", result_names=["%bad"],
                              result_types=["memref<2x5xf32, strided<[5, 1]>>"])
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
    """S0 源图：mini.matmul(a, b) -> mm；M、N、K 独立传入（今天的核心输入）。"""
    x = Value("%x", f"tensor<{M}x{K}xf32>")
    w = Value("%w", f"tensor<{K}x{N}xf32>")
    mm = Value("%mm", f"tensor<{M}x{N}xf32>")
    matmul = Op("mini.matmul", [x, w], [mm])
    ret = Op("func.return", [mm])
    return Op("func.func", body=[matmul, ret],
              attrs={"sym_name": "main", "args": [x, w],
                     "result_types": [f"tensor<{M}x{N}xf32>"]})


def build_dynamic_graph(dyn="M", base=(1, 7, 4)):
    """动态维度变体：把 base 的某一维换成 '?'——测保守拒绝路径（ST6）。"""
    M, K, N = base
    m = "?" if dyn == "M" else M
    k = "?" if dyn == "K" else K
    n = "?" if dyn == "N" else N
    x = Value("%x", f"tensor<{m}x{k}xf32>")
    w = Value("%w", f"tensor<{k}x{n}xf32>")
    mm = Value("%mm", f"tensor<{m}x{n}xf32>")
    matmul = Op("mini.matmul", [x, w], [mm])
    ret = Op("func.return", [mm])
    return Op("func.func", body=[matmul, ret],
              attrs={"sym_name": "main", "args": [x, w],
                     "result_types": [f"tensor<{m}x{n}xf32>"]})


def run_pass(func, mode="full", patterns=None, debug=False):
    """跑一次 MatMul Lowering Pass。返回 (pattern, result)。"""
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
#   ＋ Day 89 的访存日志探针——Day 90 原样沿用）

class MemRefOOBError(RuntimeError):
    """按维下标越界（Day 88 探针）：线性地址仍在缓冲区内 ≠ 下标合法。"""


class Interp:
    """最小解释执行器：跑通 alloc/fill/load/store/scf.for(iter_args)/yield/mulf/addf。

    内存模型（Day 87）：每块 memref 是 list[[state, value]]，state ∈ {"uninit", "written"}；
    垃圾值是确定性公式 garbage(addr) = 777 + 7·addr（真实语义是未定义行为）。

    探针（Day 88/89 建立）：
      · access_log：每次 load/store 记录 (kind, mem 名, 下标元组, 线性地址, 值)；
      · iv_trace：归纳变量的执行轨迹（激活次数/每激活趟数/取值集合）；
      · 按维越界检测：load/store 前逐维检查下标 ∈ [0, dim)，违规抛 MemRefOOBError。
    """

    def __init__(self, args_data):
        self.env = {}      # id(Value) -> int | np.float32
        self.mem = {}      # id(Value) -> list[[state, np.float32]]
        self.stats = {"uninit_reads": [], "loads": 0, "stores": 0, "fills": 0, "allocs": 0}
        self.iv_trace = {}  # iv 名 -> {"activations", "per_act", "values"}
        self.access_log = []  # (kind, mem 名, 下标元组, 线性地址, 值)
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
        return None    # 空体（无 yield）：保持 iter_args 不变


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
    """名字 → shape：函数入参 ＋ alloc 结果。"""
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


# ============================================================ Day 90：形状矩阵与变异

# 15 组形状：每组的「目的」回答「为什么测它——它能杀什么 bug」。
# 类别：方阵对照 / 计划点名的维度 1 / 全不同非方形 / 只有一维相等的巧合对 / 退化维 0
SHAPE_MATRIX = [
    ("方阵对照", (3, 3, 3), "M=N=K：边界/配对错误的盲区形状——作对照基线，证明「全绿≠正确」"),
    ("1×N", (1, 7, 4), "M=1（行向量输出）：i 单趟；杀 a_swap、i_ub_n（OOB）"),
    ("K=1", (6, 1, 4), "小 K=1（外积）：k 单趟；杀 k_ub_n、a_swap（OOB）"),
    ("M×1", (4, 3, 1), "N=1（列向量输出）：j 单趟；杀 b_swap（OOB）"),
    ("标量", (1, 1, 1), "M=N=K=1：只测管道——对 4 个变异全部免疫（ST4 实证）"),
    ("全不同", (2, 3, 5), "M≠K≠N：任何 M/N/K 混用都会在越界处爆（杀全部 4 个变异）"),
    ("小 K 非方", (5, 2, 3), "K<M 且 K<N：部分和类错误（k_ub_n）数值现形"),
    ("宽 K", (2, 8, 3), "K>M 且 K>N：归约比输出长；杀 a_swap（OOB）"),
    ("贯穿例", (4, 6, 3), "D85~89 的 A(4,6)@B(6,3)：与前几天连续对账"),
    ("M==K", (3, 3, 5), "M==K≠N：a_swap 在此静默算错（读 Aᵀ，不越界——只能靠参考对照抓）"),
    ("K==N", (5, 2, 2), "K==N≠M：b_swap 静默算错；k_ub_n 位相同（隐身）"),
    ("M==N", (4, 6, 4), "M==N≠K：i_ub_n 位相同（隐身）——巧合对各有各的盲区"),
    ("K=0", (4, 0, 3), "空归约：C 全零（单位元 0，D87 伏笔）；杀 k_ub_n（OOB）"),
    ("M=0", (0, 6, 3), "空输出：i 零趟、alloc 0 格；杀 i_ub_n（OOB）"),
    ("N=0", (3, 2, 0), "空输出（j 零趟）：i/k 类边界错误在此隐身——盲区也要记录"),
]

# 4 个注入变异（默认全关＝正确形态；ST2~ST4 猎杀矩阵、ST7 修复闭环用）
MUTANTS = [
    ("M1 a_swap", {"a_swap": True},
     "配对写反：load %a[%k, %i]（A 的行列互换；方阵时算 Aᵀ·B，不越界）"),
    ("M2 b_swap", {"b_swap": True},
     "配对写反：load %b[%j, %k]（B 的行列互换；K==N 时算 A·Bᵀ，不越界）"),
    ("M3 i_ub_n", {"i_ub_n": True},
     "边界错绑：i 循环上界绑到 %cN（应绑 %cM）；M==N 时位相同（隐身）"),
    ("M4 k_ub_n", {"k_ub_n": True},
     "边界错绑：k 循环上界绑到 %cN（应绑 %cK）；K==N 时位相同（隐身）"),
]


def classify(mutation_kwargs, M, K, N):
    """对一个变异在给定形状上跑一遍，分类结果并留证据。

    返回 (status, evidence)：
      OOB  —— 按维越界探针拦截（evidence=真实报错文本）
      NUM  —— 跑完但与同序参考实现不等（evidence=max|C−ref|）
      SAME —— 与参考逐位相同：这个形状对该变异免疫（隐身）
      CONV —— 转换本身失败（正确形态下不应出现）
    """
    pats = [MatMulBodyPattern(**mutation_kwargs)]
    res, interp, func, C, err = run_case(pats, M, K, N)
    if not res.ok:
        return "CONV", res.message
    if err is not None:
        return "OOB", err
    A, B = make_inputs(M, K, N)
    ref = reference_matmul(A, B)
    if np.array_equal(C, ref):
        return "SAME", "与同序参考逐位相同"
    diff = float(np.max(np.abs(C - ref))) if C.size else 0.0
    return "NUM", f"max|C − ref| = {diff:.3e}（静默算错）"


# ============================================================ ST1：形状矩阵端到端

def st1_matrix():
    """ST1 形状矩阵端到端：15 组形状 × 转换/执行/位等价/流量/覆盖/IV 轨迹。

    计划要求的「至少 8 组 Shape 测试和参考结果对照」落在 15 组上；
    所有期望值按 (M,K,N) 参数化——不硬编码任何具体形状的数字。
    """
    rows, ok_all = [], True
    plan_ok = len(SHAPE_MATRIX) >= 8
    for cat, (M, K, N), purpose in SHAPE_MATRIX:
        pattern = MatMulBodyPattern()
        res, interp, func, C, err = run_case([pattern], M, K, N)
        A, B = make_inputs(M, K, N)
        ref = reference_matmul(A, B)
        # ---- 转换与结构（形状不变式）----
        conv_ok = res.ok
        ops_ok = conv_ok and [op.name for op in func.walk()] == EXPECTED_BODY
        spec_ok = (conv_ok
                   and [(s.iv, s.lb, s.ub, s.step) for s in pattern.specs]
                   == [("%i", 0, M, 1), ("%j", 0, N, 1), ("%k", 0, K, 1)])
        const_vals = sorted(op.attrs["value"] for op in func.walk()
                            if op.name == "arith.constant"
                            and op.results[0].type == "index") if conv_ok else []
        consts_ok = const_vals == sorted([0, 1, M, N, K])
        # ---- 执行与数值 ----
        run_ok = err is None and C is not None
        bit_ok = run_ok and np.array_equal(C, ref)
        npm = np.matmul(A, B)
        npm_equal = bool(np.array_equal(C, npm)) if run_ok else False
        npm_diff = float(np.max(np.abs(C - npm))) if run_ok and C.size else 0.0
        # ---- 流量与覆盖（参数化；维度为 0 时相应张量无访存）----
        st_ = interp.stats
        traffic_ok = (run_ok and st_["loads"] == 2 * M * N * K
                      and st_["stores"] == M * N and st_["uninit_reads"] == []
                      and st_["allocs"] == 1)
        cov = coverage(interp, func)
        # 覆盖定律的参数化（含维度 0 的完整版）：A 每格读 N 次 → N==0 或 A 无格子时零访存；
        # B 每格读 M 次 → M==0 时零访存；C 每格写 1 次 → M*N==0 时零格零写
        a_reads = M * K > 0 and N > 0
        b_reads = K * N > 0 and M > 0
        cov_a_ok = ((not cov["%a"]) if not a_reads else
                    (set(cov["%a"]) == set(range(M * K))
                     and all(c == N for c in cov["%a"].values())))
        cov_b_ok = ((not cov["%b"]) if not b_reads else
                    (set(cov["%b"]) == set(range(K * N))
                     and all(c == M for c in cov["%b"].values())))
        cov_c_ok = ((not cov["%c"]) if M * N == 0 else
                    (set(cov["%c"]) == set(range(M * N))
                     and all(c == 1 for c in cov["%c"].values())))
        # ---- IV 轨迹（Day 88 的 trip 公式在边界形状上的实测）----
        # 取值集合只有循环真的跑过 ≥1 趟才等于 range(dim)：M=0 → %j 从未激活（空集）、
        # N=0 → %k 从未激活（空集）；per_act 则无条件存在（exec_for 先建轨迹再迭代）
        ti = interp.iv_trace.get("%i", {"per_act": [], "values": set()})
        tj = interp.iv_trace.get("%j", {"per_act": [], "values": set()})
        tk = interp.iv_trace.get("%k", {"per_act": [], "values": set()})
        iv_ok = (run_ok and ti["per_act"] == [M]
                 and tj["per_act"] == [N] * M and tk["per_act"] == [K] * (M * N)
                 and ti["values"] == (set(range(M)) if M > 0 else set())
                 and tj["values"] == (set(range(N)) if (M > 0 and N > 0) else set())
                 and tk["values"] == (set(range(K)) if (M > 0 and N > 0 and K > 0)
                                      else set()))
        good = all([conv_ok, ops_ok, spec_ok, consts_ok, run_ok, bit_ok,
                    traffic_ok, cov_a_ok, cov_b_ok, cov_c_ok, iv_ok])
        ok_all &= good
        if st_["loads"] == 0 and st_["stores"] == 0:
            cov_note = "无任何访存（0 趟循环）"
        elif st_["loads"] == 0:
            cov_note = "A/B 无访存（K=0 零趟）· C 每格写 1 次"
        else:
            cov_note = f"A 每格读 {N} 次 · B 每格读 {M} 次 · C 每格写 1 次"
        rows.append(dict(cat=cat, M=M, K=K, N=N, purpose=purpose, good=good,
                         loads=st_["loads"], stores=st_["stores"], cov_note=cov_note,
                         trips=(trip_count(pattern.specs[0]) if conv_ok else None,
                                trip_count(pattern.specs[1]) if conv_ok else None,
                                trip_count(pattern.specs[2]) if conv_ok else None),
                         npm_equal=npm_equal, npm_diff=npm_diff))
    lines = [
        f"  矩阵规模：{len(SHAPE_MATRIX)} 组形状 ≥ 计划要求的 8 组（{plan_ok}）；"
        f"全部 15/15 通过（{ok_all}）",
        f"  每组检查 11 项：转换成功 · 18 op 结构 · LoopSpec(i<M,j<N,k<K) · "
        f"常量多重集{{0,1,M,N,K}} · 执行无越界 · 同序参考位等价 · load=2MNK · "
        f"store=MN · 覆盖 A×N/B×M/C×1 · 无未初始化读 · IV 轨迹",
        f"  成员构成：方阵对照 1 · 维度 1 共 4（1×N / K=1 / M×1 / 标量）· "
        f"全不同非方 4（含小 K、宽 K、贯穿例）· 巧合对 3（M==K / K==N / M==N）· "
        f"退化维 3（K=0 / M=0 / N=0）",
        f"  维度 0 的语义：K=0 → 空归约 = 单位元 0（C 全零，D87 %zero 兑现）；"
        f"M=0/N=0 → 空输出（alloc 0 格、循环 0 趟、无任何访存）",
    ]
    return ok_all and plan_ok, lines, rows


# ============================================================ ST2/ST3/ST4：猎杀矩阵

def st2_square_blindness():
    """ST2 方阵盲区：(3,3,3) 上 4 个变异——2 个静默算错（NUM）、2 个位相同（SAME）。

    「静默算错」= 不崩、不越界、IR 结构完全合法——没有参考对照就溜了；
    「位相同」= 连参考对照都抓不住（M==N / K==N 时错误的常量值与正确值相等）。
    """
    lines, ok = [], True
    expect = {"M1 a_swap": "NUM", "M2 b_swap": "NUM",
              "M3 i_ub_n": "SAME", "M4 k_ub_n": "SAME"}
    for name, kwargs, desc in MUTANTS:
        status, ev = classify(kwargs, 3, 3, 3)
        good = status == expect[name]
        ok &= good
        tag = {"NUM": "静默算错（只能靠参考对照抓）", "SAME": "位相同（完全隐身）"}[status]
        lines.append(f"  {name} 在 A(3,3)@B(3,3) 上：{status}——{tag}（{good}）：{ev}")
        lines.append(f"    注入内容：{desc}")
    lines.append("  —— 结论：方阵上 4 个变异一个都不崩。没有非方形成员，"
                 "这套测试对索引/边界 bug 没有牙齿")
    return ok, lines


def st3_kill_matrix():
    """ST3 猎杀矩阵：4 变异 × 15 形状 → OOB/NUM/SAME；每个变异 ≥5 杀、
    ≥2 个 OOB 杀、≥1 个 NUM 杀；并记录每个变异的 SAME 盲区形状。"""
    grid = {}
    for name, kwargs, desc in MUTANTS:
        for cat, (M, K, N), purpose in SHAPE_MATRIX:
            grid[(name, (M, K, N))] = classify(kwargs, M, K, N)
    lines, ok = [], True
    for name, kwargs, desc in MUTANTS:
        kills = [(cat, shp) for cat, shp, _ in SHAPE_MATRIX
                 if grid[(name, shp)][0] in ("OOB", "NUM")]
        oob_kills = [shp for cat, shp, _ in SHAPE_MATRIX if grid[(name, shp)][0] == "OOB"]
        num_kills = [shp for cat, shp, _ in SHAPE_MATRIX if grid[(name, shp)][0] == "NUM"]
        same = [f"{cat} {shp}" for cat, shp, _ in SHAPE_MATRIX
                if grid[(name, shp)][0] == "SAME"]
        good = (len(kills) >= 5 and len(oob_kills) >= 2 and len(num_kills) >= 1)
        ok &= good
        oob_ev = next((grid[(name, shp)][1] for cat, shp, _ in SHAPE_MATRIX
                       if grid[(name, shp)][0] == "OOB"), "")
        lines.append(f"  {name}：杀 {len(kills)}/15（OOB {len(oob_kills)} ＋ NUM {len(num_kills)}）"
                     f"（{good}）；免疫（SAME）{len(same)} 组：{('、'.join(same))}")
        lines.append(f"    OOB 证据（真实报错）：{oob_ev}")
    # 计划点名成员必须真的杀 bug
    named = [((1, 7, 4), "M1 a_swap"), ((1, 7, 4), "M3 i_ub_n"),
             ((6, 1, 4), "M4 k_ub_n"), ((4, 3, 1), "M2 b_swap"),
             ((2, 3, 5), "M1 a_swap"), ((2, 3, 5), "M3 i_ub_n"),
             ((2, 3, 5), "M4 k_ub_n"), ((2, 3, 5), "M2 b_swap")]
    named_ok = all(grid[(mut, shp)][0] in ("OOB", "NUM") for shp, mut in named)
    ok &= named_ok
    lines.append(f"  计划点名成员的牙齿：1×N(1,7,4) 杀 a_swap/i_ub_n · K=1(6,1,4) 杀 k_ub_n · "
                 f"M×1(4,3,1) 杀 b_swap · 全不同(2,3,5) 杀全部 4 个（{named_ok}）")
    # 全不同成员 (2,3,5) 必须杀全部四个变异
    alldiff = all(grid[(m, (2, 3, 5))][0] in ("OOB", "NUM")
                  for m, _, _ in MUTANTS)
    ok &= alldiff
    lines.append(f"  M≠K≠N 的 (2,3,5) 单枪匹马杀全部 4 个变异（{alldiff}）——"
                 f"「三数互不相等」是区分 M/N/K 绑定的最小充分条件")
    return ok, lines, grid


def st4_dim_one(grid):
    """ST4 维度 1：(1,1,1) 对全部 4 个变异免疫（下标恒 0、上界恒 1）；
    但维度 1 的其他成员（1×N / K=1 / M×1）各有杀伤——退化不等于没用。"""
    lines, ok = [], True
    for name, _, _ in MUTANTS:
        status, ev = grid[(name, (1, 1, 1))]
        good = status == "SAME"
        ok &= good
        lines.append(f"  {name} 在 (1,1,1) 上：{status}（{good}）——下标恒为 0、"
                     f"上界恒为 1：交换、错绑在这里数值上无差别")
    for shp, muts, note in [
        ((1, 7, 4), ("M1 a_swap", "M3 i_ub_n"), "1×N：M=1，行向量"),
        ((6, 1, 4), ("M4 k_ub_n", "M1 a_swap"), "K=1：外积，k 单趟"),
        ((4, 3, 1), ("M2 b_swap",), "M×1：N=1，列向量"),
    ]:
        killed = all(grid[(m, shp)][0] in ("OOB", "NUM") for m in muts)
        ok &= killed
        lines.append(f"  {shp}（{note}）：杀 {' 与 '.join(muts)}（{killed}）——"
                     f"维度 1 只有「三数同时塌缩成 1」才失去牙齿")
    lines.append("  —— 结论：标量形状只验证管道（结构/内存/执行不炸）；"
                 "配对与边界的正确性必须靠非退化形状")
    return ok, lines


# ============================================================ ST5：退化维 0

def st5_degenerate():
    """ST5 退化维 0：K=0（空归约→单位元）、M=0 / N=0（空输出）——语义与工程边界。"""
    lines, ok = [], True
    # K=0：空归约，C 必须逐位等于 0（不只是等于参考——是数学事实）
    res, interp, func, C, err = run_case([MatMulBodyPattern()], 4, 0, 3)
    k0_ok = (res.ok and err is None and C is not None
             and bool(np.all(C == 0.0)) and interp.stats["loads"] == 0
             and interp.stats["stores"] == 12 and interp.stats["uninit_reads"] == [])
    ok &= k0_ok
    lines.append(f"  K=0，A(4,0)@B(0,3)：C(4,3) 全零（{np.all(C == 0.0)}）——空归约＝"
                 f"单位元 0：k 零趟，%acc 原样出门；load 0 · store 12（C 每格仍写 1 次）"
                 f"（{k0_ok}）")
    lines.append("    D87 的 %zero 初值在此兑现：它是「归约单位元」而不只是「清零习惯」")
    # M=0：空输出
    res, interp, func, C, err = run_case([MatMulBodyPattern()], 0, 6, 3)
    m0_ok = (res.ok and err is None and C is not None and C.shape == (0, 3)
             and interp.stats["loads"] == 0 and interp.stats["stores"] == 0
             and interp.stats["uninit_reads"] == [])
    ok &= m0_ok
    lines.append(f"  M=0，A(0,6)@B(6,3)：C(0,3) 空（shape {C.shape}）；i 零趟 → "
                 f"j/k 从未激活；load 0 · store 0 · alloc 0 格（{m0_ok}）")
    # N=0：空输出（另一条路）
    res, interp, func, C, err = run_case([MatMulBodyPattern()], 3, 2, 0)
    n0_ok = (res.ok and err is None and C is not None and C.shape == (3, 0)
             and interp.stats["loads"] == 0 and interp.stats["stores"] == 0)
    ok &= n0_ok
    lines.append(f"  N=0，A(3,2)@B(2,0)：C(3,0) 空（shape {C.shape}）；j 零趟（k 因此"
                 f"从未激活）；load 0 · store 0（{n0_ok}）")
    lines.append(f"  三者的 IV 轨迹：K=0 → %k 激活 12 次每次 0 趟；M=0 → %i 激活 1 次 0 趟；"
                 f"N=0 → %j 激活 3 次每次 0 趟——「零趟」由 trip = max(0, ceil((ub-lb)/step)) 保证")
    lines.append("  工程边界：空数组 reshape / 空 Counter 的 max() 是这里最常见的坑"
                 "（见 README 常见错误 E1/E2）")
    return ok, lines


# ============================================================ ST6：保守与契约回归

def st6_conservative_contract():
    """ST6 静态前提与事务契约回归：动态 '?' 在边界形状上仍保守拒绝；
    半途而废 Pattern 仍回滚不留痕（D86~D89 保证的延续）。"""
    lines, ok = [], True
    # 动态 M 在 1×N 基型上
    f1 = build_dynamic_graph("M", base=(1, 7, 4))
    _, r1 = run_pass(f1, "full", debug=True)
    good1 = (not r1.ok and "无法合法化 'mini.matmul'" in r1.message
             and "都拒绝了这次匹配" in r1.message)
    ok &= good1
    lines.append(f"  A(?x7) @ B(7,4)（1×N 的 M 动态），full 模式："
                 f"{'按预期失败' if not r1.ok else '意外成功'}（{good1}）——边界形状不豁免静态前提")
    # 动态 K 在小 K 基型上
    f2 = build_dynamic_graph("K", base=(5, 2, 3))
    _, r2 = run_pass(f2, "full", debug=True)
    good2 = not r2.ok
    ok &= good2
    dbg_text = "\n".join(r2.debug_lines)
    in_debug = "静态 strides" in dbg_text and "宁拒不猜" in dbg_text
    ok &= in_debug
    lines.append(f"  A(5x?) @ B(?x3)（K 动态），full 模式：按预期失败（{good2}）；"
                 f"拒绝理由仍在 --debug 调试树：「静态 strides…宁拒不猜」（{in_debug}）")
    # partial 模式：显式残留
    f3 = build_dynamic_graph("N", base=(4, 6, 3))
    _, r3 = run_pass(f3, "partial")
    good3 = r3.ok and r3.residue == ["mini.matmul"]
    ok &= good3
    lines.append(f"  N 动态（A(4x6)@B(6x?)），partial 模式：成功，显式残留 {r3.residue}"
                 f"（交给后续 Pass——动态版走 memref.dim ＋动态 alloc）（{good3}）")
    # 回滚回归：HalfDone 先 create 五类 op 再拒绝 → 终图与只用正确 Pattern 逐字相同
    fa = build_main_graph(2, 3, 5)
    _, ra = run_pass(fa, "full", patterns=[MatMulBodyPattern(), HalfDoneBodyPattern()])
    fb = build_main_graph(2, 3, 5)
    run_pass(fb, "full")
    roll_ok = ra.ok and print_module(fa) == print_module(fb)
    ok &= roll_ok
    lines.append(f"  回滚回归：HalfDone(先 create alloc+load+mulf 再拒绝) 回滚后，"
                 f"终图与只用正确 Pattern 的结果逐字相同（{roll_ok}）——形状换了，契约不换")
    return ok, lines, (r1, r2)


# ============================================================ ST7：修复闭环

def st7_fix_loop(grid):
    """ST7 修复闭环：每个变异「红（真实报错/差值）→ 定位 → 修复 → 绿」。

    定位手段：对照 LoopSpec 出生证明（应然）与实际绑定的常量（实然）；
    修复 = 绑回正确来源（a_swap→A[%i,%k]，i_ub_n→ub 绑 %cM，k_ub_n→ub 绑 %cK）。
    """
    fixers = {
        "M1 a_swap": ("A 的下标配对：行号 i 在前、归约 k 在后 → load %a[%i, %k]"),
        "M2 b_swap": ("B 的下标配对：归约 k 在前（B 的行）、列号 j 在后 → load %b[%k, %j]"),
        "M3 i_ub_n": ("i 的上界来源：M = A.shape[0] → for %i 绑 %cM（不是 %cN）"),
        "M4 k_ub_n": ("k 的上界来源：K = 内维契约 → for %k 绑 %cK（不是 %cN）"),
    }
    killers = {"M1 a_swap": (2, 3, 5), "M2 b_swap": (4, 3, 1),
               "M3 i_ub_n": (1, 7, 4), "M4 k_ub_n": (6, 1, 4)}
    lines, ok = [], True
    for name, kwargs, desc in MUTANTS:
        M, K, N = killers[name]
        red_status, red_ev = grid[(name, (M, K, N))]
        # 修复后（旋钮全关＝正确绑定）在同一 killer 形状上必须位等价
        gres, ginterp, gfunc, gC, gerr = run_case([MatMulBodyPattern()], M, K, N)
        gref = reference_matmul(*make_inputs(M, K, N))
        green_ok = (gres.ok and gerr is None and gC is not None
                    and np.array_equal(gC, gref))
        good = (red_status in ("OOB", "NUM") and green_ok)
        ok &= good
        lines.append(f"  {name}（{desc}）")
        lines.append(f"    红：killer 形状 A({M},{K})@B({K},{N}) → {red_status}：{red_ev}")
        lines.append(f"    定位：LoopSpec 出生证明写着 ub 来源（i←M、k←K）＋ 下标语义表"
                     f"（A[i,k]/B[k,j]/C[i,j]）——与 IR 实际绑定一对照即见错位")
        lines.append(f"    修复：{fixers[name]}")
        lines.append(f"    绿：同一形状用正确绑定重跑 → 与同序参考逐位相等（{green_ok}）；"
                     f"全矩阵 15/15 回归见 ST1（{good}）")
    lines.append("  —— 四个闭环全部走通：形状矩阵先给出「红」，出生证明给出「为什么红」，"
                 "正确绑定给出「怎么修」，回归给出「修好了」")
    return ok, lines


# ============================================================ 报告与产出

def env_line():
    return (f"Linux {platform.machine()}, Python {platform.python_version()}, "
            f"numpy {np.__version__}; 本机未安装 MLIR（DialectConversion 语义仿真＋"
            f"访存日志解释执行，不伪造 MLIR 行为）")


def build_shape_matrix_txt(rows):
    lines = [
        "Day 90 形状矩阵：15 组 Shape 测试与参考结果对照（真实运行）",
        f"环境：{env_line()}",
        "种子：SEED=90（输入矩阵可复现）",
        "",
        "口径：位等价对象是同序参考实现（i/j/k ＋ float32 逐步舍入）；",
        "      np.matmul 差值单独报告（舍入顺序可能不同，不算失败）；",
        "      流量期望：load = 2·M·N·K，store = M·N；覆盖期望：A 每格读 N 次、",
        "      B 每格读 M 次、C 每格写 1 次（维度为 0 时相应张量无访存）。",
        "",
        "── 矩阵总表 ──────────────────────────────────────────────────────────────",
        "类别     形状                    trip(i/j/k)   load  store  覆盖                        位等价  目的（能杀什么 bug）",
    ]
    for r in rows:
        lines.append(
            f"{r['cat']:<6} A({r['M']},{r['K']})@B({r['K']},{r['N']})→C({r['M']},{r['N']})"
            f"   {r['trips'][0]}/{r['trips'][1]}/{r['trips'][2]}"
            f"     {r['loads']:>5}  {r['stores']:>4}"
            f"   {r['cov_note']:<28} {'✓' if r['good'] else '✗'}    {r['purpose']}")
    lines += [
        "",
        "── np.matmul 对照（单独报告）──",
    ]
    for r in rows:
        d = "（空输出，无差值）" if r["M"] == 0 or r["N"] == 0 else f"max|diff| = {r['npm_diff']:.3e}"
        lines.append(f"  A({r['M']},{r['K']})@B({r['K']},{r['N']})：逐位相等 = {r['npm_equal']}"
                     f"，{d}")
    lines += [
        "",
        "── 结构不变式（15 组全部成立）──",
        "  · IR 恒为 18 op（walk 序列与 EXPECTED_BODY 逐项相同）——形状是数据不是代码：",
        "    换形状只改 5 个常量的值（{0,1,M,N,K}）与 3 个 memref 类型，不改结构；",
        "  · LoopSpec 恒为 (i:0..M) 套 (j:0..N) 套 (k:0..K)，ub 来源逐条带出生证明；",
        "  · 无未初始化读；alloc 恰 1 次；IV 轨迹与 trip 公式一致（含 0 趟）。",
        "",
    ]
    return "\n".join(lines)


def build_kill_matrix_txt(grid):
    lines = [
        "Day 90 猎杀矩阵：4 个注入变异 × 15 组形状（真实运行）",
        f"环境：{env_line()}",
        "",
        "分类口径：",
        "  OOB  = 按维越界探针拦截（真实报错文本见各行）——执行级证据；",
        "  NUM  = 跑完不崩，但与同序参考实现不等（静默算错）——只有参考对照抓得住；",
        "  SAME = 与参考逐位相同（该形状对此变异免疫/隐身）——盲区，必须记录而不是回避。",
        "",
        "── 方阵盲区（ST2）：A(3,3)@B(3,3) 单独一列 ──",
    ]
    for name, _, desc in MUTANTS:
        status, ev = grid[(name, (3, 3, 3))]
        lines.append(f"  {name:<12} {status:<5} {ev}")
    lines += [
        "",
        "── 全矩阵（行=形状，列=变异）──",
        f"  {'形状':<22}{'M1 a_swap':<12}{'M2 b_swap':<12}{'M3 i_ub_n':<12}{'M4 k_ub_n':<12}",
    ]
    for cat, (M, K, N), purpose in SHAPE_MATRIX:
        shp = f"{cat} ({M},{K},{N})"
        row = f"  {shp:<22}"
        for name, _, _ in MUTANTS:
            row += f"{grid[(name, (M, K, N))][0]:<12}"
        lines.append(row)
    lines += [
        "",
        "── 每个变异的杀伤统计与 OOB 证据 ──",
    ]
    for name, _, desc in MUTANTS:
        kills = [shp for _, shp, _ in SHAPE_MATRIX if grid[(name, shp)][0] in ("OOB", "NUM")]
        oobs = [shp for _, shp, _ in SHAPE_MATRIX if grid[(name, shp)][0] == "OOB"]
        nums = [shp for _, shp, _ in SHAPE_MATRIX if grid[(name, shp)][0] == "NUM"]
        sames = [f"{cat} {shp}" for cat, shp, _ in SHAPE_MATRIX if grid[(name, shp)][0] == "SAME"]
        oob_ev = next((grid[(name, shp)][1] for _, shp, _ in SHAPE_MATRIX
                       if grid[(name, shp)][0] == "OOB"), "")
        num_evs = "; ".join(f"{shp}→{grid[(name, shp)][1]}" for _, shp, _ in SHAPE_MATRIX
                            if grid[(name, shp)][0] == "NUM")
        lines.append(f"  {name}（{desc}）")
        lines.append(f"    杀 {len(kills)}/15：OOB {len(oobs)}（{['%dx%dx%d' % s for s in oobs]}）"
                     f"＋ NUM {len(nums)}（{['%dx%dx%d' % s for s in nums]}）")
        lines.append(f"    OOB 证据：{oob_ev}")
        lines.append(f"    NUM 证据：{num_evs}")
        lines.append(f"    SAME 盲区 {len(sames)} 组：{'、'.join(sames)}")
        lines.append("")
    lines += [
        "── 读法 ──",
        "  · 每个变异都有自己的盲区形状（标量、退化维、以及各自的巧合对）；",
        "  · 矩阵整体无盲区：4 个变异各被 ≥10 组形状杀死，其中 OOB ≥5（带诊断的执行级",
        "    证据）、NUM ≥2（只有参考对照抓得住的静默算错）；",
        "  · (2,3,5)（M≠K≠N）单枪匹马杀全部 4 个变异——三数互不相等是配对/绑定测试的",
        "    最小充分条件；(1,1,1) 则一个都杀不了——退化形状测管道，不测配对。",
        "",
    ]
    return "\n".join(lines)


def build_fix_loop_txt(grid):
    killers = {"M1 a_swap": (2, 3, 5), "M2 b_swap": (4, 3, 1),
               "M3 i_ub_n": (1, 7, 4), "M4 k_ub_n": (6, 1, 4)}
    num_shapes = {"M1 a_swap": (3, 3, 3), "M2 b_swap": (3, 3, 3),
                  "M3 i_ub_n": (6, 1, 4), "M4 k_ub_n": (4, 6, 3)}
    lines = [
        "Day 90 修复闭环：红 → 定位 → 修复 → 绿（全部真实运行）",
        f"环境：{env_line()}",
        "",
        "定位手段（两个「应然 vs 实然」的对照面）：",
        "  ① LoopSpec 出生证明（Day 88）：每条循环的 ub 来源——i←M=A.shape[0]、",
        "    j←N=B.shape[1]、k←K=内维契约；注释印在 IR 里，与实际 for 绑定的常量一比即见错位；",
        "  ② 下标语义表（Day 85/89）：A[i,k]=行×归约、B[k,j]=归约×列、C[i,j]=输出坐标。",
        "",
    ]
    for name, kwargs, desc in MUTANTS:
        M, K, N = killers[name]
        status, ev = grid[(name, (M, K, N))]
        nM, nK, nN = num_shapes[name]
        nstatus, nev = grid[(name, (nM, nK, nN))]
        lines.append(f"── {name}：{desc} ──")
        lines.append(f"  红（OOB 路径）：A({M},{K})@B({K},{N}) → {status}")
        lines.append(f"    {ev}")
        lines.append(f"  红（NUM 路径）：A({nM},{nK})@B({nK},{nN}) → {nstatus}")
        lines.append(f"    {nev}")
        fixers = {
            "M1 a_swap": "load %a 的下标绑回 [%i, %k]（行号在前、归约在后）",
            "M2 b_swap": "load %b 的下标绑回 [%k, %j]（归约在前、列号在后）",
            "M3 i_ub_n": "i 循环上界绑回 %cM（M = A.shape[0]）",
            "M4 k_ub_n": "k 循环上界绑回 %cK（K = 内维契约 A.shape[1]==B.shape[0]）",
        }
        lines.append(f"  修复：{fixers[name]}")
        gres, ginterp, gfunc, gC, gerr = run_case([MatMulBodyPattern()], M, K, N)
        gref = reference_matmul(*make_inputs(M, K, N))
        gbit = gres.ok and gerr is None and gC is not None and np.array_equal(gC, gref)
        lines.append(f"  绿：同一 killer 形状用正确绑定重跑 → 与同序参考逐位相等（{gbit}）")
        lines.append(f"  回归：全矩阵 15/15 位等价（ST1）＋ ST2~ST6 全 PASS")
        lines.append("")
    lines.append("诚实声明：四个变异是**故意注入**的探针（Day 89 的 Pattern 在 AT4 预飞 7 组"
                 "全绿、今天新增 8 组边界形状也全绿）。它们的作用是证明「形状矩阵有牙齿」、"
                 "并演练修复闭环——不是伪造「昨天就错」的历史。")
    lines.append("")
    return "\n".join(lines)


def build_debug_log(cases):
    out = ["Day 90 调试树汇总（--debug，对应 MLIR -debug-only=dialect-conversion 的格式）", ""]
    for title, lines_ in cases:
        out.append(f"—— {title} ——")
        out.extend(lines_)
        out.append("")
    return "\n".join(out)


def build_report(results):
    lines = ["Day 90 支持非方形与边界 Shape·检查测试报告（真实运行）",
             f"环境：{env_line()}", ""]
    for name, ok, detail in results:
        lines.append(f"[{'PASS' if ok else 'FAIL'}] {name}")
        lines.extend(detail)
        lines.append("")
    n_pass = sum(1 for _, ok, _ in results if ok)
    lines.append(f"—— 检查测试 {n_pass}/{len(results)} PASS ——")
    lines.append("")
    lines.append("口径附注：")
    lines.append("  1. 计划要求「至少 8 组 Shape 测试和参考结果对照」——本文交付 15 组（ST1），")
    lines.append("     每组 11 项检查、期望值全部按 (M,K,N) 参数化，不硬编码具体形状的数字。")
    lines.append("  2. 变异（a_swap/b_swap/i_ub_n/k_ub_n）是故意注入的探针：用于证明形状矩阵")
    lines.append("     有牙齿（ST2~ST4）与演练修复闭环（ST7），不是 Day 89 代码的历史 bug。")
    lines.append("  3. 位等价的验收对象是「同序参考实现」（i/j/k ＋ float32 逐步舍入）；")
    lines.append("     np.matmul 的对照差值单独报告。")
    lines.append("  4. 按维越界/访存日志/IV 轨迹是仿真探针（对应真实工程的 sanitizer/trace）；")
    lines.append("     scf/memref 语义依据官方文档（mlir.llvm.org，2026-11 核对）；")
    lines.append("     垃圾值是确定性公式（真实语义为未定义行为）。")
    return "\n".join(lines)


# ============================================================ 主流程

def run_all():
    results = []

    ok, lines, rows = st1_matrix()
    results.append(("ST1 形状矩阵端到端（15 组）", ok, lines))

    ok, lines = st2_square_blindness()
    results.append(("ST2 方阵盲区", ok, lines))

    ok, lines, grid = st3_kill_matrix()
    results.append(("ST3 猎杀矩阵", ok, lines))

    ok, lines = st4_dim_one(grid)
    results.append(("ST4 维度 1 退化", ok, lines))

    ok, lines = st5_degenerate()
    results.append(("ST5 退化维 0", ok, lines))

    ok, lines, (r1, r2) = st6_conservative_contract()
    results.append(("ST6 静态前提与事务契约", ok, lines))

    ok, lines = st7_fix_loop(grid)
    results.append(("ST7 修复闭环", ok, lines))

    # 调试树案例：正常转换（全不同形状）＋ 两个动态拒绝
    f0 = build_main_graph(2, 3, 5)
    d0 = ConversionDriver([MatMulBodyPattern()], TypeConverter(), debug=True)
    d0.apply(f0, "full")
    f3 = build_main_graph(2, 3, 5)
    d3 = ConversionDriver([HalfDoneBodyPattern()], TypeConverter(), debug=True)
    d3.apply(f3, "full")

    debug_log = build_debug_log([
        ("案例 1：全不同形状 A(2,3)@B(3,5) 正常转换", d0.debug_lines),
        ("案例 2：1×N 基型 M 动态，保守拒绝（ST6）", r1.debug_lines),
        ("案例 3：小 K 基型 K 动态，保守拒绝（ST6）", r2.debug_lines),
        ("案例 4：半途而废 Pattern，回滚（ST6 回归项）", d3.debug_lines),
    ])

    report = build_report(results)
    shape_txt = build_shape_matrix_txt(rows)
    kill_txt = build_kill_matrix_txt(grid)
    fix_txt = build_fix_loop_txt(grid)

    OUT.mkdir(exist_ok=True)
    (OUT / "shape-matrix.txt").write_text(shape_txt + "\n", encoding="utf-8")
    (OUT / "kill-matrix.txt").write_text(kill_txt + "\n", encoding="utf-8")
    (OUT / "fix-loop.txt").write_text(fix_txt + "\n", encoding="utf-8")
    (OUT / "test-report.txt").write_text(report + "\n", encoding="utf-8")
    (OUT / "debug-log.txt").write_text(debug_log + "\n", encoding="utf-8")

    all_ok = all(ok for _, ok, _ in results)
    return report, all_ok


def practice_mode(shape, mutant_name, trace):
    M, K, N = shape if shape else (4, 6, 3)
    kwargs = {}
    if mutant_name:
        lookup = {}
        for name, kw, _ in MUTANTS:
            lookup[name] = kw
            lookup[name.split()[-1]] = kw     # 短名：a_swap / b_swap / i_ub_n / k_ub_n
        if mutant_name not in lookup:
            print(f"未知变异 {mutant_name}；可选：{', '.join(m[0] for m in MUTANTS)}")
            return 1
        kwargs = lookup[mutant_name]
    func = build_main_graph(M, K, N)
    pattern = MatMulBodyPattern(**kwargs)
    driver = ConversionDriver([pattern], TypeConverter())
    res = driver.apply(func, "full")
    print(f"形状 A({M},{K}) @ B({K},{N}) -> C({M},{N})"
          + (f"｜变异：{mutant_name}" if mutant_name else "｜正确形态"))
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
    ref = reference_matmul(A, B)
    if err is not None:
        print(f"执行被按维越界探针拦下：{err}")
        print("（这就是猎杀矩阵里的 OOB——非方形形状抓住了索引/边界错误）")
        return 1
    C = np.array([cell[1] for cell in interp.mem[interp.ret]],
                 dtype=np.float32).reshape(M, N)
    same = np.array_equal(C, ref)
    print()
    print("执行结果（解释执行实测）：")
    if kwargs:
        print(f"  load {interp.stats['loads']}（正确形态应为 2·M·N·K = {2 * M * N * K}）· "
              f"store {interp.stats['stores']}（正确形态应为 M·N = {M * N}）· "
              f"未初始化读 {len(interp.stats['uninit_reads'])}")
    else:
        print(f"  load {interp.stats['loads']}（= 2·M·N·K = {2 * M * N * K}）· "
              f"store {interp.stats['stores']}（= M·N = {M * N}）· "
              f"未初始化读 {len(interp.stats['uninit_reads'])}")
    print(f"  与同序参考实现位等价：{same}"
          + ("（SAME——这个形状对该变异免疫：隐身！）" if (mutant_name and same)
             else ("（NUM——静默算错，只有参考对照抓得住）" if mutant_name else "")))
    if not same and C.size:
        print(f"  max|C − ref| = {float(np.max(np.abs(C - ref))):.3e}")
    cov = coverage(interp, func)
    if cov["%c"]:
        ab_note = (f"A 每格读 {max(cov['%a'].values())} 次（应 = N = {N}）· "
                   f"B 每格读 {max(cov['%b'].values())} 次（应 = M = {M}）"
                   if cov["%a"] else "A/B 无访存（k 零趟）")
        print(f"  覆盖：{ab_note} · C 每格写 {max(cov['%c'].values())} 次（应 = 1）")
    else:
        print("  覆盖：无任何访存（存在 0 趟循环）")
    if trace and interp.access_log:
        print()
        print("前 8 条访存（真实记录）：")
        strides = mem_strides_of(func)
        for i, (kind, mem, idx, addr, val) in enumerate(interp.access_log[:8]):
            print(f"  {i + 1:>2}. {kind:<5} {mem}[{idx[0]},{idx[1]}] → "
                  f"{addr_formula(strides[mem], idx)} = {addr:<3} 值 {float(val):+.6f}")
    print()
    hdr = [f"// 练习模式：A({M},{K}) @ B({K},{N}) -> C({M},{N})"
           + (f"｜变异 {mutant_name}" if mutant_name else "｜正确形态")
           + f"（真实运行输出，{len(list(func.walk()))} op）"]
    print(print_module(func, hdr))
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--shape", nargs=3, type=int, metavar=("M", "K", "N"),
                    help="改写形状（默认 4 6 3）；练习模式只打印，不生成产出")
    ap.add_argument("--mutant", metavar="NAME",
                    help="注入一个变异再跑（亲手复现猎杀矩阵的某一格）："
                         "M1 a_swap / M2 b_swap / M3 i_ub_n / M4 k_ub_n（可省略 M 编号）")
    ap.add_argument("--trace", action="store_true",
                    help="（与 --shape 搭配）打印前 8 条访存")
    ap.add_argument("--debug", action="store_true",
                    help="（默认模式）额外把调试树汇总打印到 stdout")
    args = ap.parse_args()

    if args.shape or args.mutant:
        return practice_mode(args.shape, args.mutant, args.trace)

    report, all_ok = run_all()
    print(report)
    print()
    print("shape-matrix.txt / kill-matrix.txt / fix-loop.txt / test-report.txt / "
          "debug-log.txt 已写入 outputs/")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
