#!/usr/bin/env python3
"""第 87 天：生成输出初始化——alloc 不清零，零起点必须在 IR 里显式交代。

本机未安装 MLIR。与 Day 57~86 的做法一致：用 Python 复刻 MLIR DialectConversion
的 Pattern / Rewriter / 驱动器语义（仿真），并在其上加一个**解释执行器**，
用来验证「输出初始化」的内存语义。不伪造 MLIR 本身的行为。与真实 MLIR 的
对应关系（依据 mlir.llvm.org 官方文档《Dialect Conversion》《Pattern Rewriting》
《scf dialect》，2026-11 核对）：

    MLIR 里的机制                                                     仿真里的对应
    ------------------------------------------------------------------------------
    memref.alloc：分配缓冲区，内容未初始化（malloc 语义）               Interp 的 MemState（uninit/written + 垃圾值）
    memref.fill %zero, %c ：把 C 全部元素写成 %zero                     exec fill（方案 A 的显式清零）
    scf.for ... iter_args(%acc = %zero) -> (f32)                        Op.operands[3:] 追加初值 + attrs["iter_args"]
      区域参数 %acc（体内可见）≠ 循环结果 %acc（体外可见）                attrs["iter_args"] 的区域 Value vs op.results
      scf.yield %s 回传下一迭代的 iter_args 值                          exec_body 到 yield 取回传值
      零次迭代 → 结果 = 初值                                            range(lo, up, st) 为空时 cur 保持 inits
    动态维度的保守路径：静态 Pattern 拒绝 tensor<?x?>，                  match 检测 '?' → notifyMatchFailure
      动态版走 memref.dim + 动态 alloc（真实编译器的分工）                （宁拒不猜；动态路径留给后续专题）

诚实声明（与真实 MLIR 的差异）：
  1. 真实 scf.for 的 iter_args/yield 由区域入口块参数实现（BlockArgument）；
     本仿真用 attrs["iter_args"] 里预建的 Value 对象模拟区域参数。
  2. 未初始化读在真实硬件上是未定义行为；本仿真用确定性垃圾值
     garbage(addr) = 777 + 7·addr 让它「可观察、可计数、可复现」。
  3. 真实 MLIR 的 Pattern 事务/回滚深度见 Day 86 头部声明，本仿真沿用 Pattern 级事务。

用法：
    python3 init_pass.py                # 运行 IT1~IT5 检查测试，生成 outputs/
    python3 init_pass.py --shape 2 3 2  # 换形状，只打印 IR 与摘要（练习用）
    python3 init_pass.py --debug        # 额外打印主图与各案例的 dialect-conversion 风格调试树

产出：
    outputs/init-ir.txt     Day 87 版 Lowering 后的 IR（初始化就位、访存留白，预留标注 Day 88）
    outputs/test-report.txt IT1~IT5 检查测试报告（真实运行）
    outputs/debug-log.txt   调试树（主图 + 动态维度拒绝 + 回滚回归案例）
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

    scf.for 的约定（Day 87 升级）：
      operands = [lb, ub, step, *iter_args 初值]
      attrs    = {"iv": "%k", "iv_value": Value,        # 归纳变量（区域参数）
                  "iter_names": ["%acc"],                # iter_args 显示名
                  "iter_args": [Value, ...]}             # iter_args 区域参数
      results  = [Value, ...]                            # 循环结束后的循环携带值
    scf.yield 带操作数 = 回传下一迭代的 iter_args 值。
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
    """把 func 树打印成 MLIR 风格文本（Day 87 版：支持 iter_args / yield 操作数 /
    load / store / fill / mulf / addf——后四类是三策略预演 IR 需要的）。"""

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
# （与 Day 86 相同的三段式事务：create/replaceOp 暂存 → commit / rollback）

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


# ============================================================ Day 87 的初始化 Pattern

class MatMulInitPattern(ConversionPattern):
    """Day 87 版 mini.matmul → 循环表示：在 Day 86 骨架上填入「输出初始化」。

    相对 Day 86 骨架的三处升级（对应 Day 85 任务清单③的方案 B）：
      ① %zero = arith.constant 0.0 : f32   —— 零起点显式化（SSA 值，不是内存）
      ② 最内层 scf.for 升级 iter_args(%acc = %zero) -> (f32)
         —— 累加器初值挂在循环上，C 不需要预清零（每个元素只写不读）
      ③ scf.yield 升级为带操作数：yield %zero
         —— 占位回传初值（恒等循环：%acc ≡ 0.0）；Day 88 把 %zero 换成 %s = addf %acc, %p

    match 阶段在 Day 86 四连问之外新增第五问：shape 必须静态（动态维 '?' 走保守拒绝）。
    """

    root_name = "mini.matmul"
    benefit = 1
    debug_name = "MatMulInitPattern"

    def __init__(self):
        self.seen_adaptor = None

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
        if not (is_static(sa) and is_static(sb)):
            return rewriter.notifyMatchFailure(
                op, f"动态维度（A{sa} @ B{sb}）：alloc 类型与循环边界无法编译期确定，"
                    f"本 Pattern 只接静态 shape——保守路径，宁拒不猜"
                    f"（动态版需要 memref.dim ＋动态 alloc，留给后续专题）")
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

        # ① 输出缓冲：alloc（Day 85 任务清单①的类型表；注意：不清零！）
        alloc = rewriter.create(
            "memref.alloc", result_names=["%c"], result_types=[make_memref((M, N))],
            comments=[f"任务① 输出缓冲 {M * N * 4} B：memref.alloc 不清零——零起点靠下面的 %zero"])

        # ② 零起点：今天的第一块肉（Day 85 任务清单③方案 B 的第 1 步）
        zero = rewriter.create(
            "arith.constant", result_names=["%zero"], result_types=["f32"],
            attrs={"value": 0.0},
            comments=["任务③ 初始化 1/2：零起点是 SSA 值，不写内存——C 每元素只写不读"])

        # ③ 5 个 index 常量（Day 86 骨架栏目，原样保留）
        consts = [rewriter.create("arith.constant", result_names=[cname(v)],
                                  result_types=["index"], attrs={"value": v})
                  for v in (0, 1, M, N, K)]
        for c, note in zip(consts, ["下界 0", "步长 1", "M ← A.shape[0]",
                                     "N ← B.shape[1]", "K ← 内维契约 A.shape[1]==B.shape[0]"]):
            c.comments.append(note)
        lo, st, bm, bn, bk = [c.results[0] for c in consts]

        # ④ 最内层循环体：yield 升级为带操作数（占位回传初值）
        yld = rewriter.create(
            "scf.yield", operands=[zero.results[0]],
            comments=["任务③ 初始化 2/2：iter_args 的回传口",
                      "占位：恒等循环（%acc ≡ %zero）；Day 88 把 %zero 换成 %s = addf %acc, %p",
                      "预留(Day 88 填): load %a[%i,%k] · load %b[%k,%j] · mulf · addf · store %c[%i,%j]"])

        # ⑤ 最内层 for 升级：iter_args(%acc = %zero) -> (f32)——从内向外创建
        fk = rewriter.create(
            "scf.for", operands=[lo, bk, st, zero.results[0]],
            result_names=["%acc"], result_types=["f32"],
            attrs={"iv": "%k", "iv_value": Value("%k", "index"),
                   "iter_names": ["%acc"],
                   "iter_args": [Value("%acc", "f32")]},
            body=[yld],
            comments=["任务③ 初始化：累加器初值 = %zero（Day 85 清单③方案 B，+0 B 流量）",
                      "体内 %acc（iter_args 区域参数）≠ 体外 %acc（循环结果）——同名不同值"])
        fj = rewriter.create("scf.for", operands=[lo, bn, st], attrs={"iv": "%j",
                            "iv_value": Value("%j", "index")}, body=[fk])
        fi = rewriter.create("scf.for", operands=[lo, bm, st], attrs={"iv": "%i",
                            "iv_value": Value("%i", "index")}, body=[fj])
        # ---------- 处置 root：%mm(tensor) → %c(memref)；uses 延迟到 finalize 替换 ----------
        rewriter.replaceOp(op, [alloc.results[0]])
        return True


class HalfDoneInitPattern(ConversionPattern):
    """反面教材（IT5 回归用）：先 create 再放弃——验证升级后的骨架仍满足「失败不留痕」。"""

    root_name = "mini.matmul"
    benefit = 2
    debug_name = "HalfDoneInitPattern"

    def matchAndRewrite(self, op, adaptor, rewriter):
        rewriter.create("memref.alloc", result_names=["%bad"],
                        result_types=["memref<4x3xf32, strided<[3, 1]>>"])
        rewriter.create("arith.constant", result_names=["%bad0"], result_types=["f32"],
                        attrs={"value": 0.0})
        return rewriter.notifyMatchFailure(
            op, "故意半途而废：先 create 了 alloc ＋ %zero 再放弃（回归测试：回滚必须不留痕）")


# ============================================================ 测试图构造

def build_main_graph(M=4, K=6, N=3):
    """S0 源图：Day 83 终图 GEMM 的形状（Day 85~87 贯穿例子）。"""
    x = Value("%x", f"tensor<{M}x{K}xf32>")
    w = Value("%w", f"tensor<{K}x{N}xf32>")
    mm = Value("%mm", f"tensor<{M}x{N}xf32>")
    matmul = Op("mini.matmul", [x, w], [mm])
    ret = Op("func.return", [mm])
    return Op("func.func", body=[matmul, ret],
              attrs={"sym_name": "main", "args": [x, w],
                     "result_types": [f"tensor<{M}x{N}xf32>"]})


def build_dynamic_graph(dyn="M"):
    """动态维度变体：M 或 N 为 '?'——测保守拒绝路径（IT4）。

    签名转换会把 tensor<?x6> 转成 memref<?x6, strided<[6,1]>>（strides 仍可知），
    Pattern 在 match 里检测到 '?' 后保守拒绝。
    """
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
    """跑一次 Day 87 版 MatMul Lowering Pass。返回 (pattern, result)。"""
    pat = MatMulInitPattern()
    driver = ConversionDriver([pat, *extra], TypeConverter(), debug=debug)
    res = driver.apply(func, mode)
    return pat, res


EXPECTED_INIT = (["func.func", "memref.alloc"]
                 + ["arith.constant"] * 6       # %zero(f32) ＋ 5 个 index 常量
                 + ["scf.for"] * 3 + ["scf.yield", "func.return"])


# ============================================================ 解释执行器（内存语义验证）

class Interp:
    """最小解释执行器：跑通 alloc/fill/load/store/scf.for(iter_args)/yield/mulf/addf。

    内存模型（这是今天的主角）：
      每块 memref 是 list[[state, value]]，state ∈ {"uninit", "written"}。
      - memref.alloc：全部元素 uninit，值 = 确定性垃圾 garbage(addr)——
        真实语义是未定义行为，仿真让它「可观察、可计数、可复现」；
      - memref.load 读到 uninit 元素：记入 stats["uninit_reads"]（地址＋下标），返回垃圾值；
      - memref.fill / memref.store：置为 written。
    f32 运算用 numpy.float32（与参考实现同序 → 可验证位等价）。
    """

    def __init__(self, args_data):
        self.env = {}      # id(Value) -> int | np.float32
        self.mem = {}      # id(Value) -> list[[state, np.float32]]
        self.stats = {"uninit_reads": [], "loads": 0, "stores": 0, "fills": 0, "allocs": 0}
        self.args_data = args_data
        self.ret = None

    # ---- 工具 ----
    @staticmethod
    def garbage(addr):
        return np.float32(GARBAGE_BASE + 7.0 * addr)

    def val(self, v):
        return self.env[id(v)]

    def addr_of(self, op):
        """load/store 的线性地址：sum(stride_d × idx_d)（Day 85 任务清单②）。"""
        m = op.operands[0] if op.name == "memref.load" else op.operands[1]
        strides = memref_strides(m.type)
        idxs = op.operands[1:] if op.name == "memref.load" else op.operands[2:]
        return sum(s * int(self.val(i)) for s, i in zip(strides, idxs))

    # ---- 入口 ----
    def run(self, func):
        for a in func.attrs["args"]:
            data = self.args_data[a.name]
            if isinstance(data, np.ndarray):
                # 入参 memref：外部传入、内容已定义（全部 written，行主序展平）
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
            addr = self.addr_of(op)
            cell = self.mem[id(m)][addr]
            if cell[0] == "uninit":
                idxs = tuple(int(self.val(i)) for i in op.operands[1:])
                self.stats["uninit_reads"].append((m.name, idxs, addr))
            self.env[id(op.results[0])] = np.float32(cell[1])
            self.stats["loads"] += 1
        elif n == "memref.store":
            m = op.operands[1]
            self.mem[id(m)][self.addr_of(op)] = ["written", np.float32(self.val(op.operands[0]))]
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
            # 返回的是 memref 句柄：存 id（数值在 self.mem 里，由调用方取）
            self.ret = id(op.operands[0]) if op.operands else None
        else:
            raise RuntimeError(f"Interp：不支持的 op '{n}'")

    def exec_for(self, op):
        """执行 scf.for（含 iter_args）。

        区域参数绑定：iv_value / iter_args 里的 Value 每次迭代重新绑定；
        yield 回传下一迭代的 iter_args 值；零次迭代 → 结果 = 初值。
        """
        lb, ub, st = (int(self.val(v)) for v in op.operands[:3])
        cur = [self.val(v) for v in op.operands[3:]]     # iter_args 初值（今天的重点）
        region_args = op.attrs.get("iter_args", [])
        for it in range(lb, ub, st):
            self.env[id(op.attrs["iv_value"])] = it
            for rarg, v in zip(region_args, cur):
                self.env[id(rarg)] = v
            yv = self.exec_body(op.body)
            if yv is not None:
                cur = yv
        for r, v in zip(op.results, cur):
            self.env[id(r)] = v

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


# ============================================================ 三策略预演 IR（Day 88 完整版的手工构造）

def build_full_ir(strategy, M=4, K=6, N=3, A=None, B=None):
    """构造「访存也填好」的完整循环 IR——今天 Pattern 还不产出这些（Day 88 才填），
    但内存语义必须现在验证：三种初始化策略的差别压缩在 **iter_args 初值来自哪里**。

      strategy="B"    ：iter_args(%acc = %zero)        —— 初值来自 SSA 常量（Day 85 选定）
      strategy="A"    ：memref.fill ＋ iter_args(%acc = load C[i,j])
                                                     —— 初值来自内存（fill 过的 0）
      strategy="none" ：iter_args(%acc = load C[i,j])，但没有 fill
                                                     —— 读未初始化内存（探针：UB）

    返回 (func, {名字: Value} 字典)——A/B 数据由 Interp 从 args_data 注入。
    """
    ta, tb, tc = make_memref((M, K)), make_memref((K, N)), make_memref((M, N))
    a = Value("%a", ta)
    b = Value("%b", tb)
    body = []
    c = Op("memref.alloc", results=[Value("%c", tc)],
           comments=["任务① 输出缓冲（alloc 不清零）"])
    body.append(c)
    zero = Op("arith.constant", results=[Value("%zero", "f32")], attrs={"value": 0.0})
    if strategy == "A":
        body.append(zero)
        body.append(Op("memref.fill", operands=[zero.results[0], c.results[0]],
                       comments=["方案 A：把 0.0 写进 C 的每个元素（＋M×N×4 B 写流量）"]))
    consts = [Op("arith.constant", results=[Value(f"%c{v}", "index")], attrs={"value": v})
              for v in (0, 1, M, N, K)]
    body.extend(consts)
    lo, st, bm, bn, bk = [x.results[0] for x in consts]
    iv = {"%i": Value("%i", "index"), "%j": Value("%j", "index"), "%k": Value("%k", "index")}
    acc_arg = Value("%acc", "f32")        # 循环体内可见的 iter_args 区域参数
    acc_res = Value("%acc", "f32")        # 循环结果（体外可见）——同名不同值！

    # ---- 最内层 %k 循环体：load ×2 · mulf · addf · yield %s（Day 88 的完整形态）----
    xa = Op("memref.load", operands=[a, iv["%i"], iv["%k"]], results=[Value("%xa", "f32")])
    xb = Op("memref.load", operands=[b, iv["%k"], iv["%j"]], results=[Value("%xb", "f32")])
    p = Op("arith.mulf", operands=[xa.results[0], xb.results[0]], results=[Value("%p", "f32")])
    s = Op("arith.addf", operands=[acc_arg, p.results[0]], results=[Value("%s", "f32")])
    yld = Op("scf.yield", operands=[s.results[0]])
    # ---- iter_args 初值：三策略唯一分叉点 ----
    if strategy == "B":
        init_val, init_note = zero.results[0], "方案 B：初值 = %zero（SSA 常量，C 零读零 fill）"
        body.insert(1, zero)      # %zero 放在 alloc 之后（与今天的 Pattern 产出同构）
        j_body_prefix = []
    else:
        cij = Op("memref.load", operands=[c.results[0], iv["%i"], iv["%j"]],
                 results=[Value("%cij", "f32")],
                 comments=["读改写：k 循环外先 load C[i,j]（Day 85 清单③方案 A 原文）",
                           "方案 A：fill 保证了它是 0.0；none：垃圾——差别只在有没有 fill"])
        init_val = cij.results[0]
        init_note = ("方案 A：初值 = load C[i,j]（fill 过，是 0.0）"
                     if strategy == "A" else
                     "探针 none：初值 = load C[i,j]（没有 fill——读未初始化内存，UB）")
        j_body_prefix = [cij]     # load C 必须在 k 循环外：初值先就位，k 循环才能起步
    fk = Op("scf.for", operands=[lo, bk, st, init_val],
            results=[acc_res],
            attrs={"iv": "%k", "iv_value": iv["%k"], "iter_names": ["%acc"],
                   "iter_args": [acc_arg]},
            body=[xa, xb, p, s, yld],
            comments=[init_note])
    st_op = Op("memref.store", operands=[acc_res, c.results[0], iv["%i"], iv["%j"]],
               comments=["C 每元素只写一次（最终值）"])
    fj = Op("scf.for", operands=[lo, bn, st],
            attrs={"iv": "%j", "iv_value": iv["%j"]}, body=j_body_prefix + [fk, st_op])
    fi = Op("scf.for", operands=[lo, bm, st],
            attrs={"iv": "%i", "iv_value": iv["%i"]}, body=[fj])
    body.extend([fi])
    ret = Op("func.return", operands=[c.results[0]])
    return Op("func.func", body=body + [ret],
              attrs={"sym_name": "main", "args": [a, b], "result_types": [tc]})


def run_strategy(strategy, A, B, M=4, K=6, N=3):
    """构造三策略预演 IR → 解释执行 → 返回 (C 结果矩阵, Interp 统计, func)。"""
    func = build_full_ir(strategy, M, K, N)
    interp = Interp({"%a": A, "%b": B})
    interp.run(func)
    C = np.array([cell[1] for cell in interp.mem[interp.ret]],
                 dtype=np.float32).reshape(M, N)
    return C, interp.stats, func


def make_inputs(M=4, K=6, N=3):
    """固定种子 87 的输入矩阵（可复现）。"""
    rng = np.random.RandomState(SEED)
    return (rng.randn(M, K).astype(np.float32),
            rng.randn(K, N).astype(np.float32))


# ============================================================ 检查测试 IT1~IT5

def it1_init_structure(func, res, before_names):
    """IT1 结构升级：3 op → 13 op；%zero 就位；iter_args 挂对；骨架栏目全保留。"""
    after = [op.name for op in func.walk()]
    body = func.body
    alloc, zero, consts, fi = body[0], body[1], body[2:7], body[7]
    fj, fk, yld = fi.body[0], fi.body[0].body[0], fi.body[0].body[0].body[0]
    seq_ok = after == EXPECTED_INIT
    zero_ok = (zero.results[0].name == "%zero" and zero.results[0].type == "f32"
               and float(zero.attrs["value"]) == 0.0)
    fk_ok = (len(fk.operands) == 4
             and fk.operands[3].name == "%zero"
             and fk.attrs["iter_names"] == ["%acc"]
             and fk.results[0].name == "%acc" and fk.results[0].type == "f32")
    yld_ok = len(yld.operands) == 1 and yld.operands[0].name == "%zero"
    fj_ok = len(fj.operands) == 3 and len(fi.operands) == 3   # 中外层无 iter_args
    cvals = sorted(int(c.attrs["value"]) for c in consts)
    bounds = [int(c.attrs["value"]) for c in (consts[2], consts[3], consts[4])]
    consts_ok = cvals == [0, 1, 3, 4, 6] and bounds == [4, 3, 6]
    alloc_ok = alloc.results[0].type == make_memref((4, 3))
    ok = (res.ok and seq_ok and zero_ok and fk_ok and yld_ok and fj_ok
          and consts_ok and alloc_ok)
    lines = [f"  转换前 {len(before_names)} op → 转换后 {len(after)} op"
             f"（Day 86 骨架 12 ＋ %zero = 13；func＋alloc＋constant×6＋for×3＋yield＋return）",
             f"  %zero = arith.constant 0.0 : f32：位置在 alloc 之后（{zero_ok}）",
             f"  最内层 for：iter_args(%acc = %zero) -> (f32)，结果 %acc（{fk_ok}）；"
             f"中外层 for 无 iter_args（{fj_ok}）",
             f"  scf.yield 升级为带操作数：yield %zero : f32（占位回传初值，{yld_ok}）",
             f"  Day 86 骨架栏目保留：常量值 {cvals}、边界 i/j/k = {bounds}、"
             f"alloc {alloc.results[0].type}（{consts_ok and alloc_ok}）",
             f"  mini 方言残留：{[n for n in after if n.startswith('mini.')] or '无'}"]
    return ok, lines


def it2_placeholder_semantics(func):
    """IT2 占位语义（解释执行主 IR）：恒等循环成立、C 零访问、零未初始化读。

    今天的 IR 是「初始化就位、计算留白」的中间态：yield %zero 让 %acc ≡ 0.0
    （恒等循环）。执行它验证这个中间态是**安全**的——没有对 C 的任何访问，
    自然也没有未初始化读。
    """
    A, B = make_inputs()
    interp = Interp({"%a": A, "%b": B})
    interp.run(func)
    # 找到内层 for 的结果 %acc 的终值
    fi = func.body[7]
    fk = fi.body[0].body[0]
    acc_final = interp.env[id(fk.results[0])]
    acc_ok = float(acc_final) == 0.0
    no_c_access = (interp.stats["loads"] == 0 and interp.stats["stores"] == 0
                   and interp.stats["fills"] == 0)
    no_uninit = len(interp.stats["uninit_reads"]) == 0
    ok = acc_ok and no_c_access and no_uninit
    lines = [f"  解释执行今天的 IR（A/B 为种子 {SEED} 的真实数据）：执行成功",
             f"  恒等循环成立：%acc 终值 = {float(acc_final):.1f}（≡ %zero，{acc_ok}）——"
             f"yield %zero 占位的语义就是「回传初值」",
             f"  对 C 的访问：load 0 次 · store 0 次 · fill 0 次（{no_c_access}）——"
             f"访存是 Day 88 的填空",
             f"  未初始化读：{len(interp.stats['uninit_reads'])} 次（{no_uninit}）——"
             f"中间态安全，零起点已显式化"]
    return ok, lines


def it3_three_strategies():
    """IT3 三策略对照（预演 Day 88 完整 IR 的内存语义）。

    三策略的差别只在 iter_args 初值来自哪里：SSA 常量（B）/ fill 过的内存（A）/
    未初始化内存（none）。用未初始化读检测＋位等价验证 Day 85 清单③的结论。
    """
    A, B = make_inputs()
    ref = reference_matmul(A, B)
    lines, ok = [], True
    # ---- 方案 B：iter_args 从 %zero 起步 ----
    CB, stB, _ = run_strategy("B", A, B)
    diffB = float(np.max(np.abs(CB - ref))) if CB.shape == ref.shape else float("inf")
    b_ok = (len(stB["uninit_reads"]) == 0 and diffB == 0.0)
    ok &= b_ok
    lines.append(f"  方案 B（iter_args 初值 = %zero）：未初始化读 {len(stB['uninit_reads'])} 次，"
                 f"max|C-ref| = {diffB:.1e} ← {'位等价' if diffB == 0.0 else '不等价'}"
                 f"（{'PASS' if b_ok else 'FAIL'}）")
    lines.append(f"    流量：load A/B 共 {stB['loads']} 次（A 72 ＋ B 72，M×N×K 次 each）· "
                 f"store C {stB['stores']} 次 · fill 0 次——C 零读零 fill，每元素只写一次（＋0 B）")
    # ---- 方案 A：fill + 读改写 ----
    CA, stA, _ = run_strategy("A", A, B)
    diffA = float(np.max(np.abs(CA - ref)))
    extraA = 2 * 4 * 3 * 4
    a_ok = (len(stA["uninit_reads"]) == 0 and diffA == 0.0)
    ok &= a_ok
    lines.append(f"  方案 A（fill 0.0 ＋ 初值 = load C[i,j]）：未初始化读 {len(stA['uninit_reads'])} 次，"
                 f"max|C-ref| = {diffA:.1e} ← {'位等价' if diffA == 0.0 else '不等价'}"
                 f"（{'PASS' if a_ok else 'FAIL'}）")
    lines.append(f"    流量：比 B 多付 fill 写 M×N×4 B ＋ load C M×N×4 B = 2×M×N×4 = "
                 f"{extraA} B（与 Day 85 清单③口径一致）")
    # ---- 探针 none：什么都不做 ----
    CN, stN, _ = run_strategy("none", A, B)
    diffN = float(np.max(np.abs(CN - ref)))
    n_reads = len(stN["uninit_reads"])
    n_ok = (n_reads == 12 and diffN > 1.0)     # 预期：12 次未初始化读＋结果被污染
    ok &= n_ok
    lines.append(f"  探针 none（初值 = load C[i,j]，没有 fill）：未初始化读 {n_reads} 次"
                 f"（M×N = 4×3 = 12，{'符合' if n_reads == 12 else '不符合'}预期），"
                 f"max|C-ref| = {diffN:.3e} ← 不等价（未定义行为，垃圾值污染）")
    lines.append(f"    首个未初始化读：{stN['uninit_reads'][0][0]}"
                 f"{stN['uninit_reads'][0][1]}（线性地址 {stN['uninit_reads'][0][2]}，"
                 f"垃圾值 {Interp.garbage(0):.1f}）")
    lines.append("  —— Day 85 清单③的三行结论在 IR 层复现：B 位等价＋0 流量；A 位等价＋96 B；"
                 "什么都不做是 UB。Pattern 产出 B。")
    return ok, lines


def it4_dynamic_conservative():
    """IT4 动态维度的保守路径：'?' → Pattern 保守拒绝；full 失败 / partial 残留。"""
    lines, ok = [], True
    f1 = build_dynamic_graph("M")
    _, r1 = run_pass(f1, "full", debug=True)
    good1 = (not r1.ok and "无法合法化 'mini.matmul'" in r1.message
             and "都拒绝了这次匹配" in r1.message)
    ok &= good1
    lines.append(f"  A(?x6) @ B(6x3)（M 动态），full 模式：{'按预期失败' if not r1.ok else '意外成功'}")
    lines.append(f"  签名转换后：%a : memref<?x6xf32, strided<[6, 1]>>（strides 仍可知）"
                 f"——类型转换不拒绝动态，拒绝发生在 Pattern 的 match")
    dbg_text = "\n".join(r1.debug_lines)
    in_debug = "动态维度" in dbg_text and "宁拒不猜" in dbg_text
    ok &= in_debug
    lines.append(f"  拒绝原因（只在 --debug 调试树）：动态维度（A('?', 6) @ B(6, 3)）："
                 f"alloc 类型与循环边界无法编译期确定…保守路径，宁拒不猜（{in_debug}）")
    f2 = build_dynamic_graph("N")
    _, r2 = run_pass(f2, "partial")
    good2 = (r2.ok and r2.residue == ["mini.matmul"])
    ok &= good2
    lines.append(f"  N 动态（A(4x6) @ B(6x?)），partial 模式：成功，显式残留 {r2.residue}"
                 f"（交给后续 Pass——动态版 Pattern 走 memref.dim ＋动态 alloc）")
    lines.append("  保守路径的意义：宁可拒绝（图保持原样），也不生成边界靠猜的错误代码——"
                 "「不生成错代码」优先于「生成代码」")
    return ok, lines, r1.debug_lines


def it5_atomicity_regression():
    """IT5 事务回归：升级版 Pattern 仍满足「失败不留痕」（Day 86 DT6 的延续）。"""
    lines, ok = [], True
    f1 = build_main_graph()
    _, r1 = run_pass(f1, "full", extra=[HalfDoneInitPattern()], debug=True)
    ir1 = print_module(f1)
    f2 = build_main_graph()
    run_pass(f2, "full")
    ir2 = print_module(f2)
    same = ir1 == ir2
    ok &= r1.ok and same
    lines.append(f"  [HalfDone(benefit=2，先 create alloc＋%zero 再拒绝) → 回滚] ＋ "
                 f"[Init(benefit=1) → 接手]：{'成功' if r1.ok else '失败'}，"
                 f"终图与只用 Init 的结果逐字相同：{same}")
    f3 = build_main_graph()
    before = [op.name for op in f3.walk()]
    driver = ConversionDriver([HalfDoneInitPattern()], TypeConverter(), debug=True)
    r3 = driver.apply(f3, "full")
    after = [op.name for op in f3.walk()]
    stray = [n for n in after if n in ("memref.alloc",) or n.startswith("scf.")
             or n == "arith.constant"]
    ok &= (not r3.ok and after == before and not stray)
    lines.append(f"  只注册 HalfDone：full 失败，失败后 op 序列 = {after}（与转换前相同："
                 f"{after == before}），半成品（alloc/%zero/循环）残留 = {stray or '无'}")
    lines.append("  —— 填了第一块肉之后，Day 86 的事务性承诺依然成立：失败不留痕")
    return ok, lines, driver.debug_lines


# ============================================================ 报告与产出

def env_line():
    return (f"Linux {platform.machine()}, Python {platform.python_version()}, "
            f"numpy {np.__version__}; 本机未安装 MLIR（DialectConversion 语义仿真＋"
            f"内存语义解释执行，不伪造 MLIR 行为）")


INIT_HEADER = [
    "// 生成自 init_pass.py（Day 87）——输出初始化就位版 MatMul Lowering Pass 的输出",
    "// 相对 Day 86 骨架的三处升级：%zero 常量 · iter_args(%acc=%zero) · yield %zero（占位回传）",
    "// 计算仍留白：load/store/mulf/addf 是 Day 88 的填空（见 scf.yield 处的预留注释）",
]


def build_report(results):
    lines = ["Day 87 输出初始化·检查测试报告（真实运行）",
             f"环境：{env_line()}", ""]
    for name, ok, detail in results:
        lines.append(f"[{'PASS' if ok else 'FAIL'}] {name}")
        lines.extend(detail)
        lines.append("")
    n_pass = sum(1 for _, ok, _ in results if ok)
    lines.append(f"—— 检查测试 {n_pass}/{len(results)} PASS ——")
    lines.append("")
    lines.append("口径附注：")
    lines.append("  1. op 计数沿用 Day 86 口径：主图 3 op → 13 op（骨架 10 ＋ %zero = 11 目标 op；")
    lines.append("     完整目标 = 11 ＋ Day 88 待填 5（load×2、mulf、addf、store）= 16 目标 op。")
    lines.append("  2. IT3 的三策略预演用手工构造的完整 IR（含 Day 88 访存 op）做内存语义验证；")
    lines.append("     Pattern 本身只产出今天的 13 op 版（访存留白）——分工见 README §5。")
    lines.append("  3. 垃圾值是确定性公式 garbage(addr) = 777 + 7·addr（真实语义为未定义行为，")
    lines.append("     仿真让它可观察、可计数、可复现）；位等价的参考实现与循环 IR 严格同序。")
    return "\n".join(lines)


def build_debug_log(cases):
    out = ["Day 87 调试树汇总（--debug，对应 MLIR -debug-only=dialect-conversion 的格式）", ""]
    for title, lines_ in cases:
        out.append(f"—— {title} ——")
        out.extend(lines_)
        out.append("")
    return "\n".join(out)


def run_all():
    # 主运行：一次转换，IT1/IT2 共享同一个 func / pattern / result
    func = build_main_graph()
    before_names = [op.name for op in func.walk()]
    pattern = MatMulInitPattern()
    driver = ConversionDriver([pattern], TypeConverter(), debug=True)
    res = driver.apply(func, "full")

    results = []
    ok, lines = it1_init_structure(func, res, before_names)
    results.append(("IT1 初始化结构", ok, lines))
    ok, lines = it2_placeholder_semantics(func)
    results.append(("IT2 占位语义（解释执行）", ok, lines))
    ok, lines = it3_three_strategies()
    results.append(("IT3 三策略内存语义", ok, lines))
    ok, lines, dbg4 = it4_dynamic_conservative()
    results.append(("IT4 动态维度保守路径", ok, lines))
    ok, lines, dbg5 = it5_atomicity_regression()
    results.append(("IT5 事务性回归", ok, lines))

    init_ir = print_module(func, INIT_HEADER)
    debug_log = build_debug_log([
        ("案例 1：主图正常路径（骨架＋初始化落地）", driver.debug_lines),
        ("案例 2：动态维度 M='?'，保守拒绝（IT4）", dbg4),
        ("案例 3：半途而废 Pattern，回滚（IT5）", dbg5),
    ])
    return results, init_ir, debug_log


def practice_mode(M, K, N):
    func = build_main_graph(M, K, N)
    _, res = run_pass(func, "full")
    print(f"形状 A({M},{K}) @ B({K},{N}) -> C({M},{N})")
    print(f"转换：{'成功' if res.ok else '失败'}——{res.message}")
    print()
    print(print_module(func, [
        f"// 练习模式：A({M},{K}) @ B({K},{N}) -> C({M},{N}) 的初始化版 IR（真实运行输出）"]))
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

    results, init_ir, debug_log = run_all()
    report = build_report(results)

    OUT.mkdir(exist_ok=True)
    (OUT / "init-ir.txt").write_text(init_ir, encoding="utf-8")
    (OUT / "test-report.txt").write_text(report + "\n", encoding="utf-8")
    (OUT / "debug-log.txt").write_text(debug_log + "\n", encoding="utf-8")

    print(report)
    if args.debug:
        print()
        print(debug_log)
    print()
    print("init-ir.txt / test-report.txt / debug-log.txt 已写入 outputs/")
    all_ok = all(ok for _, ok, _ in results)
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
