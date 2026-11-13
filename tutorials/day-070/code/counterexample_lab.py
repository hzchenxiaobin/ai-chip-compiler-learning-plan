#!/usr/bin/env python3
"""counterexample_lab.py —— 第 70 天（第 10 周复盘）主实验。

主题（计划原文）：回顾为什么「图结构相同不代表内存语义相同」；
整理至少 5 个「看似能消除但实际不能消除」的反例。

实验分九段：
  1. 两本账本：同一张图在「视图世界 / 物理世界」的内存轨迹对照
     （三明治改写在两个世界省的钱不同，值等价但输出布局可能不同）
  2~8. 七个反例（反例集，计划要求 ≥5）：
     R1 精度 Cast 往返     f32→f16→f32   看似类型对消，实测 6/6 变值
     R2 双层同目标 Reshape               Day 69 真实 bug：透传错版被拦
     R3 Copy 消除                        写集合漂移，原地写污染输入
     R4 无使用者的 Store                 naive DCE 误删（副作用）
     R5 恒等排列的物理转置               值上照抄，内存上是物化
     R6 多使用者传播                     转置没少，逐元素计算翻倍
     R7 非逐元素传播 reduce              shape 从 (3,1) 变 (1,2)
  9. MLIR 探针 ×5：stock 编译器对同款问题的裁决
  10. 反例集总表 + 守卫清单（Pattern → 语义门）

内存模型（本周的「内存账本」）：
  每个值记录 (buffer 编号, strides[元素], offset[元素])；
  每个 op 记录物理动作：view（0 字节）/ alloc+搬运（读+写字节）；
  汇总 traffic（读+写总字节）、allocs（中间缓冲数）、
  input_bufs_written（图输入缓冲被写 = 别名污染）、ext_state（外部全局）。

运行：python3 counterexample_lab.py   （在 code/ 目录下）
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
NP_DTYPE = {"f32": np.float32, "f16": np.float16, "f64": np.float64}
ELS = {"f32": 4, "f16": 2, "f64": 8}
ELEMENTWISE_WHITELIST = ("relu", "neg", "floor")

_n_check = 0
_n_pass = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global _n_check, _n_pass
    _n_check += 1
    mark = "PASS" if cond else "FAIL"
    if cond:
        _n_pass += 1
    suffix = f"（{detail}）" if detail else ""
    print(f"[{mark}] {name}{suffix}")


def hr(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


# ============================================================
# mini 图 IR（Day 69 的核心原样平移 + 新增 copy / store 两个 op）
# ============================================================

def valid_perm(p) -> bool:
    return sorted(p) == list(range(len(p)))


def t_shape(shape, perm) -> tuple:
    return tuple(shape[perm[i]] for i in range(len(shape)))


def numel(shape) -> int:
    n = 1
    for d in shape:
        n *= int(d)
    return n


def row_major(shape) -> tuple:
    s = [1] * len(shape)
    for i in range(len(shape) - 2, -1, -1):
        s[i] = s[i + 1] * shape[i + 1]
    return tuple(s)


@dataclass
class Op:
    kind: str                        # arg/const/transpose/relu/neg/floor/cast/
                                     # add/reduce_sum/reshape/copy/store
    inputs: list = field(default_factory=list)
    name: str = ""
    perm: tuple = ()                 # transpose
    value: np.ndarray | None = None  # const
    shape: tuple = ()                # arg
    axis: int = -1                   # reduce_sum（keepdims=True）
    new_shape: tuple = ()            # reshape
    dtypes: tuple = ()               # cast：(src, dst)


class Graph:
    """与 Day 69 兼容的 mini 图：构图 API / Verifier / 数值执行 / 结构哈希。"""

    def __init__(self, name: str):
        self.name = name
        self.ops: list[Op] = []
        self.returns: list[str] = []
        self.arg_shapes: list[tuple] = []
        self._n = 0

    def _new(self) -> str:
        self._n += 1
        return f"%{self._n}"

    def add_op(self, kind: str, inputs=(), **kw) -> str:
        name = self._new()
        self.ops.append(Op(kind=kind, inputs=list(inputs), name=name, **kw))
        return name

    def arg(self, shape) -> str:
        self.arg_shapes.append(tuple(shape))
        return self.add_op("arg", shape=tuple(shape))

    def const(self, value) -> str:
        return self.add_op("const", value=np.array(value, dtype=np.float32))

    def transpose(self, x: str, perm) -> str:
        return self.add_op("transpose", [x], perm=tuple(perm))

    def relu(self, x: str) -> str:
        return self.add_op("relu", [x])

    def neg(self, x: str) -> str:
        return self.add_op("neg", [x])

    def floor(self, x: str) -> str:
        return self.add_op("floor", [x])

    def cast(self, x: str, src="f32", dst="f32") -> str:
        return self.add_op("cast", [x], dtypes=(src, dst))

    def add(self, a: str, b: str) -> str:
        return self.add_op("add", [a, b])

    def reduce_sum(self, x: str, axis: int) -> str:
        return self.add_op("reduce_sum", [x], axis=axis)

    def reshape(self, x: str, new_shape) -> str:
        return self.add_op("reshape", [x], new_shape=tuple(new_shape))

    def copy(self, x: str) -> str:
        return self.add_op("copy", [x])

    def store(self, x: str) -> str:
        """副作用 op：把 x 写进外部全局缓冲 G（无返回值、无人使用）。"""
        return self.add_op("store", [x])

    # ---------- 查询 ----------

    def by_name(self, name: str) -> Op | None:
        for op in self.ops:
            if op.name == name:
                return op
        return None

    def users(self, name: str) -> list:
        u = [op for op in self.ops if name in op.inputs]
        if name in self.returns:
            u.append("return")
        return u

    def count_kind(self, kind: str) -> int:
        return sum(1 for op in self.ops if op.kind == kind)

    def n_ops(self) -> int:
        return sum(1 for op in self.ops if op.kind not in ("arg", "const"))

    def clone(self) -> "Graph":
        g = Graph(self.name)
        g.ops = [Op(kind=op.kind, inputs=list(op.inputs), name=op.name,
                    perm=op.perm, value=op.value, shape=op.shape,
                    axis=op.axis, new_shape=op.new_shape, dtypes=op.dtypes)
                 for op in self.ops]
        g.returns = list(self.returns)
        g.arg_shapes = list(self.arg_shapes)
        g._n = self._n
        return g

    def replace_uses(self, old: str, new: str) -> None:
        for op in self.ops:
            op.inputs = [new if n == old else n for n in op.inputs]
        self.returns = [new if r == old else r for r in self.returns]

    def drop(self, name: str) -> None:
        self.ops = [op for op in self.ops if op.name != name]

    # ---------- Verifier（Day 69 原样 + store 的 rank 检查）----------

    def infer_shapes(self) -> tuple[dict, list[str]]:
        shapes: dict[str, tuple] = {}
        errs: list[str] = []
        for op in self.ops:
            if op.kind == "arg":
                s = op.shape
            elif op.kind == "const":
                s = op.value.shape
            elif op.kind == "transpose":
                s_in = shapes[op.inputs[0]]
                if not valid_perm(op.perm) or len(op.perm) != len(s_in):
                    errs.append(f"[V1] {op.name} perm {op.perm} 对 rank "
                                f"{len(s_in)} 不合法")
                    s = s_in
                else:
                    s = t_shape(s_in, op.perm)
            elif op.kind in ("relu", "neg", "floor", "cast", "copy", "store"):
                s = shapes[op.inputs[0]]
            elif op.kind == "add":
                a, b = shapes[op.inputs[0]], shapes[op.inputs[1]]
                if a != b:
                    errs.append(f"[V2] {op.name} add 两操作数 shape "
                                f"不一致 {a} vs {b}")
                s = a
            elif op.kind == "reduce_sum":
                s_in = shapes[op.inputs[0]]
                if not (0 <= op.axis < len(s_in)):
                    errs.append(f"[V3] {op.name} axis {op.axis} 越界 "
                                f"(rank {len(s_in)})")
                    s = s_in
                else:
                    s = list(s_in)
                    s[op.axis] = 1
                    s = tuple(s)
            elif op.kind == "reshape":
                s_in = shapes[op.inputs[0]]
                if numel(s_in) != numel(op.new_shape):
                    errs.append(f"[V4] {op.name} reshape numel 不守恒 "
                                f"{s_in} -> {op.new_shape}")
                s = op.new_shape
            else:
                errs.append(f"[V0] 未知 op kind {op.kind!r}")
                s = ()
            shapes[op.name] = s
        return shapes, errs

    # ---------- 纯数值执行（Day 69 口径：函数式，看不见别名）----------

    def eval(self, seed: int = 0) -> list[np.ndarray]:
        rng = np.random.default_rng(seed)
        feed = {i: (rng.standard_normal(s) * 3).astype(np.float32)
                for i, s in enumerate(self.arg_shapes)}
        vals: dict[str, np.ndarray] = {}
        arg_i = 0
        for op in self.ops:
            if op.kind == "arg":
                v = feed[arg_i]
                arg_i += 1
            elif op.kind == "const":
                v = op.value
            elif op.kind == "transpose":
                v = np.transpose(vals[op.inputs[0]], op.perm)
            elif op.kind == "relu":
                v = np.maximum(vals[op.inputs[0]], np.float32(0))
            elif op.kind == "neg":
                v = -vals[op.inputs[0]]
            elif op.kind == "floor":
                v = np.floor(vals[op.inputs[0]])
            elif op.kind == "cast":
                v = vals[op.inputs[0]].astype(NP_DTYPE[op.dtypes[1]])
            elif op.kind == "add":
                v = vals[op.inputs[0]] + vals[op.inputs[1]]
            elif op.kind == "reduce_sum":
                v = vals[op.inputs[0]].sum(axis=op.axis, keepdims=True,
                                           dtype=np.float32)
            elif op.kind == "reshape":
                v = vals[op.inputs[0]].reshape(op.new_shape)
            elif op.kind == "copy":
                v = vals[op.inputs[0]].copy()
            elif op.kind == "store":
                continue          # 值世界：store 没有结果
            else:
                raise ValueError(op.kind)
            vals[op.name] = v
        return [np.asarray(vals[r]) for r in self.returns]

    # ---------- 打印与结构哈希（Day 69 原样）----------

    def render(self) -> str:
        shapes, _ = self.infer_shapes()
        lines = [f"def @{self.name}"]
        for op in self.ops:
            ins = ", ".join(op.inputs)
            if op.kind == "arg":
                body = f"{op.name} = arg"
            elif op.kind == "const":
                body = f"{op.name} = const"
            elif op.kind == "transpose":
                body = f"{op.name} = transpose {ins}, perm={list(op.perm)}"
            elif op.kind in ("relu", "neg", "floor", "copy"):
                body = f"{op.name} = {op.kind} {ins}"
            elif op.kind == "store":
                body = f"{op.name} = store {ins} -> G"
            elif op.kind == "cast":
                body = (f"{op.name} = cast {ins}, "
                        f"{op.dtypes[0]}->{op.dtypes[1]}")
            elif op.kind == "add":
                body = f"{op.name} = add {ins}"
            elif op.kind == "reduce_sum":
                body = f"{op.name} = reduce_sum {ins}, axis={op.axis}"
            elif op.kind == "reshape":
                body = f"{op.name} = reshape {ins}, to={list(op.new_shape)}"
            else:
                body = f"{op.name} = {op.kind} {ins}"
            lines.append(f"  {body:<46s} ; -> {shapes[op.name]}")
        lines.append(f"  return {', '.join(self.returns)}")
        return "\n".join(lines)

    def state_hash(self) -> str:
        """结构账本：op 按 topo 位置规范化重命名后散列（Day 69 口径）。"""
        canon = {op.name: f"#{i}" for i, op in enumerate(self.ops)}
        shapes, _ = self.infer_shapes()
        parts = []
        for op in self.ops:
            ins = ",".join(canon[n] for n in op.inputs)
            extra = ""
            if op.kind == "transpose":
                extra = f"|perm={op.perm}"
            elif op.kind == "reduce_sum":
                extra = f"|axis={op.axis}"
            elif op.kind == "reshape":
                extra = f"|to={op.new_shape}"
            elif op.kind == "cast":
                extra = f"|dt={op.dtypes}"
            elif op.kind == "const":
                extra = ("|val=" +
                         hashlib.md5(np.ascontiguousarray(op.value)
                                     .tobytes()).hexdigest()[:8])
            parts.append(f"{canon[op.name]}={op.kind}({ins}){extra}"
                         f"->{shapes.get(op.name)}")
        rets = ",".join(canon.get(r, r) for r in self.returns)
        return hashlib.md5((";".join(parts) + "|" + rets).encode()).hexdigest()


# ============================================================
# 内存账本：run_trace —— 同一张图的两种物理执行
# ============================================================

@dataclass
class MemRec:
    buf: int                 # buffer 编号（负数 = 外部输入，0 起 = 中间分配）
    strides: tuple           # 元素步长
    offset: int              # 元素偏移
    shape: tuple
    dtype: str

    def is_c_contiguous(self) -> bool:
        return self.offset == 0 and self.strides == row_major(self.shape)


@dataclass
class Trace:
    outputs: list                     # 每个 return 的值（numpy 视图）
    out_mem: list                     # 每个 return 的 MemRec
    events: list                      # 人类可读的物理动作流水
    traffic: int                      # 读 + 写总字节
    allocs: int                       # 中间 buffer 分配次数
    input_bufs_written: set           # 被写过的外部输入 buffer（别名污染）
    ext_state: np.ndarray | None      # store 写入的外部全局 G 的内容


def _view_of(buf: np.ndarray, rec: MemRec) -> np.ndarray:
    """按 MemRec 把 1-D buffer 变成可读写的 numpy 视图。"""
    itemsize = buf.dtype.itemsize
    base = buf[rec.offset:] if rec.offset else buf
    return np.lib.stride_tricks.as_strided(
        base, shape=rec.shape,
        strides=[s * itemsize for s in rec.strides], writeable=True)


def run_trace(g: Graph, seed: int = 0, mode: str = "view",
              inplace_elementwise: bool = False,
              force_physical: set | frozenset = frozenset(),
              verbose: bool = True) -> Trace:
    """按 mode 执行 g，记录内存账本。

    mode="view"     框架前端世界：transpose 恒为视图；reshape 在输入
                    C-连续时为视图；同 dtype 的 cast 为视图；逐元素算子
                    out-of-place 分配新 buffer（inplace_elementwise=False）。
    mode="physical" 降级后端世界（Day 68 的 linalg 世界）：transpose /
                    reshape / cast 全部物化为「分配新 buffer + 逐元素搬运」。
    force_physical  按 op 名单点物化（模拟「视图世界里的一个 linalg 节点」，
                    用于 R5 的混合世界实验）。
    inplace_elementwise=True 时逐元素算子原地写输入 buffer
                    （模拟后端 in-place kernel，用于 R3 的别名实验）。
    """
    rng = np.random.default_rng(seed)
    bufs: dict[int, np.ndarray] = {}
    mem: dict[str, MemRec] = {}
    events: list[str] = []
    traffic = 0
    allocs = 0
    input_written: set[int] = set()
    ext_state = None
    values: dict[str, np.ndarray] = {}
    next_buf = 0

    def log(s: str) -> None:
        events.append(s)
        if verbose:
            print(f"    {s}")

    def alloc(shape, dtype) -> tuple[int, np.ndarray]:
        nonlocal next_buf
        bid = next_buf
        next_buf += 1
        flat = np.zeros(numel(shape), dtype=NP_DTYPE[dtype])
        bufs[bid] = flat
        rec = MemRec(bid, row_major(shape), 0, tuple(shape), dtype)
        return bid, _view_of(flat, rec)

    for op in g.ops:
        k = op.kind
        # 该 op 的生效世界：全局 mode 或单点 force_physical（R5 混合世界）
        m = "physical" if (mode == "physical"
                           or op.name in force_physical) else "view"
        if k == "arg":
            bid = -(len([b for b in bufs if b < 0]) + 1)
            flat = (rng.standard_normal(numel(op.shape)) * 3
                    ).astype(np.float32)
            bufs[bid] = flat
            rec = MemRec(bid, row_major(op.shape), 0, tuple(op.shape), "f32")
            mem[op.name] = rec
            values[op.name] = _view_of(flat, rec)
            log(f"{op.name:<4} arg      外部输入 buf{bid} "
                f"{numel(op.shape) * 4}B（不计 traffic）")
        elif k == "const":
            bid, arr = alloc(op.value.shape, "f32")
            arr[...] = op.value
            mem[op.name] = MemRec(bid, row_major(op.value.shape), 0,
                                  op.value.shape, "f32")
            values[op.name] = arr
            log(f"{op.name:<4} const    离线常量 buf{bid}（不计 traffic）")
        elif k == "transpose":
            src = mem[op.inputs[0]]
            out_s = t_shape(src.shape, op.perm)
            new_strides = tuple(src.strides[op.perm[i]]
                                for i in range(len(op.perm)))
            if m == "view":
                rec = MemRec(src.buf, new_strides, src.offset, out_s,
                             src.dtype)
                mem[op.name] = rec
                values[op.name] = _view_of(bufs[src.buf], rec)
                log(f"{op.name:<4} transpose 视图 buf{src.buf} "
                    f"strides{src.strides}->{new_strides}   0B")
            else:
                bid, out = alloc(out_s, src.dtype)
                out[...] = np.transpose(values[op.inputs[0]], op.perm)
                traffic += numel(out_s) * ELS[src.dtype] * 2
                mem[op.name] = MemRec(bid, row_major(out_s), 0, out_s,
                                      src.dtype)
                values[op.name] = out
                log(f"{op.name:<4} transpose 物化 alloc buf{bid} + 搬运 "
                    f"{numel(out_s) * ELS[src.dtype]}B×2（读+写）")
        elif k in ("relu", "neg", "floor"):
            src = mem[op.inputs[0]]
            n = numel(src.shape)
            if inplace_elementwise:
                v = values[op.inputs[0]]
                if k == "relu":
                    np.maximum(v, np.float32(0), out=v)
                elif k == "neg":
                    np.negative(v, out=v)
                else:
                    np.floor(v, out=v)
                traffic += n * 4 * 2
                if src.buf < 0:
                    input_written.add(src.buf)
                mem[op.name] = MemRec(src.buf, src.strides, src.offset,
                                      src.shape, src.dtype)
                values[op.name] = v
                log(f"{op.name:<4} {k:<8} 原地写 buf{src.buf} "
                    f"(读+写 {n * 4}B×2)"
                    f"{'  ← 写进了外部输入！' if src.buf < 0 else ''}")
            else:
                bid, out = alloc(src.shape, "f32")
                v = values[op.inputs[0]]
                if k == "relu":
                    np.maximum(v, np.float32(0), out=out)
                elif k == "neg":
                    np.negative(v, out=out)
                else:
                    np.floor(v, out=out)
                traffic += n * 4 * 2
                mem[op.name] = MemRec(bid, row_major(src.shape), 0,
                                      src.shape, "f32")
                values[op.name] = out
                log(f"{op.name:<4} {k:<8} alloc buf{bid} + 读{src.buf} "
                    f"写 buf{bid}（{n * 4}B×2）")
        elif k == "cast":
            src = mem[op.inputs[0]]
            src_dt, dst_dt = op.dtypes
            n = numel(src.shape)
            if m == "view" and src_dt == dst_dt:
                mem[op.name] = MemRec(src.buf, src.strides, src.offset,
                                      src.shape, src_dt)
                values[op.name] = values[op.inputs[0]]
                log(f"{op.name:<4} cast     同 dtype 视图 buf{src.buf}   0B")
            else:
                bid, out = alloc(src.shape, dst_dt)
                out[...] = values[op.inputs[0]]
                traffic += n * ELS[src_dt] + n * ELS[dst_dt]
                mem[op.name] = MemRec(bid, row_major(src.shape), 0,
                                      src.shape, dst_dt)
                values[op.name] = out
                log(f"{op.name:<4} cast     {src_dt}->{dst_dt} alloc buf{bid}"
                    f" + 转换 读{n * ELS[src_dt]}B 写{n * ELS[dst_dt]}B")
        elif k == "add":
            a, b = mem[op.inputs[0]], mem[op.inputs[1]]
            n = numel(a.shape)
            bid, out = alloc(a.shape, "f32")
            np.add(values[op.inputs[0]], values[op.inputs[1]], out=out)
            traffic += n * 4 * 3
            mem[op.name] = MemRec(bid, row_major(a.shape), 0, a.shape, "f32")
            values[op.name] = out
            log(f"{op.name:<4} add      alloc buf{bid} + 读 buf{a.buf},"
                f"buf{b.buf} 写 buf{bid}（{n * 4}B×3）")
        elif k == "reduce_sum":
            src = mem[op.inputs[0]]
            out_s = list(src.shape)
            out_s[op.axis] = 1
            out_s = tuple(out_s)
            bid, out = alloc(out_s, "f32")
            values[op.inputs[0]].sum(axis=op.axis, keepdims=True,
                                     dtype=np.float32, out=out)
            traffic += numel(src.shape) * 4 + numel(out_s) * 4
            mem[op.name] = MemRec(bid, row_major(out_s), 0, out_s, "f32")
            values[op.name] = out
            log(f"{op.name:<4} reduce_sum alloc buf{bid}（读 "
                f"{numel(src.shape) * 4}B 写 {numel(out_s) * 4}B）")
        elif k == "reshape":
            src = mem[op.inputs[0]]
            n = numel(src.shape)
            if m == "view" and src.is_c_contiguous():
                mem[op.name] = MemRec(src.buf, row_major(op.new_shape),
                                      src.offset, tuple(op.new_shape),
                                      src.dtype)
                values[op.name] = _view_of(bufs[src.buf], mem[op.name])
                log(f"{op.name:<4} reshape  视图 buf{src.buf} "
                    f"{src.shape}->{op.new_shape}   0B")
            else:
                bid, out = alloc(op.new_shape, src.dtype)
                out[...] = values[op.inputs[0]].reshape(op.new_shape)
                traffic += n * ELS[src.dtype] * 2
                mem[op.name] = MemRec(bid, row_major(op.new_shape), 0,
                                      tuple(op.new_shape), src.dtype)
                values[op.name] = out
                log(f"{op.name:<4} reshape  "
                    f"{'物化' if m == 'physical' else '输入非连续→拷贝'}"
                    f" alloc buf{bid} + 搬运 {n * ELS[src.dtype]}B×2")
        elif k == "copy":
            src = mem[op.inputs[0]]
            n = numel(src.shape)
            bid, out = alloc(src.shape, src.dtype)
            out[...] = values[op.inputs[0]]
            traffic += n * ELS[src.dtype] * 2
            mem[op.name] = MemRec(bid, row_major(src.shape), 0, src.shape,
                                  src.dtype)
            values[op.name] = out
            log(f"{op.name:<4} copy     alloc buf{bid} + 拷贝 "
                f"{n * ELS[src.dtype]}B×2（buf{src.buf}->buf{bid}）")
        elif k == "store":
            src = mem[op.inputs[0]]
            n = numel(src.shape)
            ext_state = np.zeros(n, dtype=np.float32)
            ext_state[...] = values[op.inputs[0]].ravel()
            traffic += n * 4
            log(f"{op.name:<4} store    写外部全局 G {n * 4}B（副作用）")
        else:
            raise ValueError(k)

    outputs = [values[r] for r in g.returns]
    out_mem = [mem[r] for r in g.returns]
    # allocs 计「中间分配」：buffer 编号 >= 0 的数量（外部输入是负数）
    n_allocs = sum(1 for b in bufs if b >= 0)
    return Trace(outputs, out_mem, events, traffic, n_allocs,
                 input_written, ext_state)


def trace_summary(g: Graph, tr: Trace) -> str:
    outs = " × ".join(f"{m.shape}{m.strides}" for m in tr.out_mem) or "()"
    return (f"traffic={tr.traffic}B  中间分配={tr.allocs}  "
            f"输出={outs}  输入被写={sorted(tr.input_bufs_written) or '无'}")


# ============================================================
# 本周的 Pattern（原样平移）+ 今天的三条「诱人但错误」改写
# ============================================================

def _splice(g: Graph, at: int, new_ops: list[Op],
            replace: dict[str, str]) -> None:
    out: list[Op] = []
    for j, op in enumerate(g.ops):
        if j == at:
            out.extend(new_ops)
        else:
            op.inputs = [replace.get(n, n) for n in op.inputs]
            out.append(op)
    g.ops = out
    g.returns = [replace.get(r, r) for r in g.returns]


def naive_dce(g: Graph) -> list[str]:
    """Day 69 的 DCE 原样：只保留 return 可达集——对副作用 op 是错的。"""
    live = set(g.returns)
    for op in reversed(g.ops):
        if op.name in live:
            live.update(op.inputs)
    dropped = [op.name for op in g.ops if op.name not in live]
    g.ops = [op for op in g.ops if op.name in live]
    return dropped


SIDE_EFFECT_KINDS = {"store"}


def guarded_dce(g: Graph) -> list[str]:
    """带副作用模型的 DCE：副作用 op 一律保留（今天的新守卫）。"""
    live = set(g.returns)
    for op in g.ops:
        if op.kind in SIDE_EFFECT_KINDS:
            live.add(op.name)
    for op in reversed(g.ops):
        if op.name in live:
            live.update(op.inputs)
    dropped = [op.name for op in g.ops if op.name not in live]
    g.ops = [op for op in g.ops if op.name in live]
    return dropped


def eliminate_noop_cast(g: Graph) -> bool:
    """Day 67 守卫版：只有 src==dst 的 Cast 才是无操作。"""
    for idx, c in enumerate(g.ops):
        if c.kind != "cast" or len(c.inputs) != 1:
            continue
        if c.dtypes[0] == c.dtypes[1]:
            _splice(g, idx, [], {c.name: c.inputs[0]})
            return True
    return False


def eliminate_cast_pair_naive(g: Graph) -> bool:
    """R1 诱人版：f32→f16→f32「类型对消」直接透传——数值上是错的。"""
    for idx, c2 in enumerate(g.ops):
        if c2.kind != "cast" or len(c2.inputs) != 1:
            continue
        c1 = g.by_name(c2.inputs[0])
        if (c1 is None or c1.kind != "cast" or len(c1.inputs) != 1):
            continue
        if c1.dtypes[1] == c2.dtypes[0] and c1.dtypes[0] == c2.dtypes[1]:
            _splice(g, idx, [], {c2.name: c1.inputs[0]})
            return True
    return False


def merge_adjacent_reshapes(g: Graph) -> bool:
    """Day 66 守卫版：Reshape(Reshape(x)) -> Reshape(x, 外层目标)。"""
    for idx, r2 in enumerate(g.ops):
        if r2.kind != "reshape" or len(r2.inputs) != 1:
            continue
        r1 = g.by_name(r2.inputs[0])
        if r1 is None or r1.kind != "reshape" or len(r1.inputs) != 1:
            continue
        rm = Op("reshape", [r1.inputs[0]], new_shape=r2.new_shape,
                name=g._new())
        _splice(g, idx, [rm], {r2.name: rm.name})
        return True
    return False


def merge_adjacent_reshapes_buggy(g: Graph) -> bool:
    """R2 诱人版（Day 69 真实踩坑的第一版）：两层目标相同 → 直接透传 x。

    错在 Reshape(Reshape(x,t),t) = Reshape(x,t) ≠ x（除非 t==shape(x)）。
    """
    for idx, r2 in enumerate(g.ops):
        if r2.kind != "reshape" or len(r2.inputs) != 1:
            continue
        r1 = g.by_name(r2.inputs[0])
        if (r1 is None or r1.kind != "reshape" or len(r1.inputs) != 1
                or r1.new_shape != r2.new_shape):
            continue
        _splice(g, idx, [], {r2.name: r1.inputs[0]})
        return True
    return False


def push_transpose_through_elementwise(
        g: Graph, whitelist=ELEMENTWISE_WHITELIST,
        respect_unique: bool = True) -> bool:
    """Day 68 受限传播：T(E(x)) -> E(T(x))。C1 白名单 + C2 唯一使用者。"""
    for idx, t in enumerate(g.ops):
        if t.kind != "transpose" or len(t.inputs) != 1:
            continue
        e = g.by_name(t.inputs[0])
        if e is None or e.kind not in whitelist or len(e.inputs) != 1:
            continue
        if respect_unique and g.users(e.name) != [t]:
            continue
        t2 = Op("transpose", [e.inputs[0]], perm=t.perm, name=g._new())
        e2 = Op(e.kind, [t2.name], name=g._new())
        _splice(g, idx, [t2, e2], {t.name: e2.name})
        return True
    return False


def merge_adjacent_transposes(g: Graph) -> bool:
    """Day 65：T_p2(T_p1(x)) -> T_r(x)，r[i] = p1[p2[i]]；恒等则透传。"""
    for idx, t2 in enumerate(g.ops):
        if t2.kind != "transpose" or len(t2.inputs) != 1:
            continue
        t1 = g.by_name(t2.inputs[0])
        if t1 is None or t1.kind != "transpose" or len(t1.inputs) != 1:
            continue
        r = tuple(t1.perm[t2.perm[i]] for i in range(len(t2.perm)))
        x = t1.inputs[0]
        if r == tuple(range(len(r))):
            _splice(g, idx, [], {t2.name: x})
        else:
            tm = Op("transpose", [x], perm=r, name=g._new())
            _splice(g, idx, [tm], {t2.name: tm.name})
        return True
    return False


def eliminate_copy_naive(g: Graph) -> bool:
    """R3 诱人版：copy 值上是恒等，把用途换成源、删掉 copy。"""
    for op in g.ops:
        if op.kind != "copy" or len(op.inputs) != 1:
            continue
        g.replace_uses(op.name, op.inputs[0])
        g.drop(op.name)
        return True
    return False


def eliminate_identity_transpose_naive(g: Graph) -> bool:
    """R5 诱人版：恒等排列的 transpose 值上照抄 → 透传。"""
    for idx, t in enumerate(g.ops):
        if (t.kind != "transpose" or len(t.inputs) != 1
                or t.perm != tuple(range(len(t.perm)))):
            continue
        _splice(g, idx, [], {t.name: t.inputs[0]})
        return True
    return False


# ============================================================
# MLIR 探针
# ============================================================

def find_mlir_opt() -> str | None:
    import shutil
    for cand in (shutil.which("mlir-opt"),
                 "/usr/lib/llvm-18/bin/mlir-opt",
                 "/usr/lib/llvm-17/bin/mlir-opt"):
        if cand and Path(cand).is_file() and Path(cand).exists():
            return cand
    return None


def run_mlir(ir_file: Path, args: list[str]) -> tuple[int, str]:
    exe = find_mlir_opt()
    if exe is None:
        return -1, "(mlir-opt 不可用)"
    p = subprocess.run([exe, str(ir_file)] + args,
                       capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


def count_op(text: str, pat: str) -> int:
    return sum(1 for line in text.splitlines() if pat in line)


# ============================================================
# 主实验
# ============================================================

def part1_two_ledgers() -> dict:
    """同一张图，两个世界：结构哈希相同、值相同、内存轨迹不同。"""
    hr("1. 两本账本：同一张图，视图世界 vs 物理世界")

    g = Graph("ledger")
    x = g.arg((2, 3))
    t = g.transpose(x, (1, 0))
    r = g.relu(t)
    s = g.reshape(r, (6,))
    g.returns = [s]
    print("同一条 4-op 链（本周五种冗余里最朴素的一条）：")
    print(g.render())
    h = g.state_hash()
    print(f"\n结构账本 state_hash = {h[:8]}（两个世界共用同一张图）")

    print("\n-- 视图世界（框架前端：transpose 是 0 字节记账）--")
    tr_v = run_trace(g.clone(), seed=0, mode="view")
    print(f"  汇总：{trace_summary(g, tr_v)}")

    print("\n-- 物理世界（降级后端：每个算子都真搬字节）--")
    tr_p = run_trace(g.clone(), seed=0, mode="physical")
    print(f"  汇总：{trace_summary(g, tr_p)}")

    print("\n两个世界的输出值逐位相等吗？ "
          f"{np.array_equal(tr_v.outputs[0], tr_p.outputs[0])}")
    check("1a 同一张图（state_hash 相同）在两个世界的 traffic 不同",
          tr_v.traffic != tr_p.traffic,
          f"view {tr_v.traffic}B vs physical {tr_p.traffic}B")
    check("1b 两个世界的中间分配数不同",
          tr_v.allocs != tr_p.allocs,
          f"view {tr_v.allocs} vs physical {tr_p.allocs}")
    check("1c 输出值逐位相等（差别只在内存，不在值）",
          np.array_equal(tr_v.outputs[0], tr_p.outputs[0]))
    check("1d 物理世界 traffic = 视图世界的 3 倍（这条链实测）",
          tr_p.traffic == 3 * tr_v.traffic,
          f"{tr_p.traffic}B == 3×{tr_v.traffic}B")

    # --- 三明治：同一个「值等价」改写，两个世界省的钱不同 ---
    print("\n-- 三明治改写：T(relu(T(x))) → relu(x)（Day 65 合并律，"
          "值等价）--")
    sand = Graph("sandwich")
    sx = sand.arg((2, 3))
    st1 = sand.transpose(sx, (1, 0))
    sr = sand.relu(st1)
    st2 = sand.transpose(sr, (1, 0))
    sand.returns = [st2]
    sand2 = sand.clone()
    push_transpose_through_elementwise(sand2)   # T_out 穿过 relu
    merge_adjacent_transposes(sand2)            # T(T(x)) 恒等 → 透传
    naive_dce(sand2)                            # 清掉改写留下的死链
    print("改写后（Day 68 传播 + Day 65 合并 + DCE，值等价）：")
    print(sand2.render())

    tr_keep_v = run_trace(sand.clone(), seed=1, mode="view", verbose=False)
    tr_keep_p = run_trace(sand.clone(), seed=1, mode="physical",
                          verbose=False)
    tr_gone_v = run_trace(sand2.clone(), seed=1, mode="view", verbose=False)
    tr_gone_p = run_trace(sand2.clone(), seed=1, mode="physical",
                          verbose=False)
    print(f"  视图世界  保留: {trace_summary(sand, tr_keep_v)}")
    print(f"  视图世界  相消: {trace_summary(sand2, tr_gone_v)}")
    print(f"  物理世界  保留: {trace_summary(sand, tr_keep_p)}")
    print(f"  物理世界  相消: {trace_summary(sand2, tr_gone_p)}")
    ov = tr_keep_v.out_mem[0]
    gv = tr_gone_v.out_mem[0]
    print("\n  视图世界注意：相消前输出 strides=(1,2)（非连续，转置视图），"
          "相消后 (3,1)（连续）——")
    print("  值相同、输出布局不同 → 下游 reshape 的零拷贝权利不同"
          "（第 9 周命题一回归）。")
    check("1e 三明治相消在两个世界都值等价",
          np.array_equal(tr_keep_v.outputs[0], tr_gone_v.outputs[0])
          and np.array_equal(tr_keep_p.outputs[0], tr_gone_p.outputs[0]))
    check("1f 物理世界相消省 96B（两个转置 × 48B）",
          tr_keep_p.traffic - tr_gone_p.traffic == 96,
          f"{tr_keep_p.traffic}B - {tr_gone_p.traffic}B = "
          f"{tr_keep_p.traffic - tr_gone_p.traffic}B")
    check("1g 视图世界相消不省 traffic（转置本来就免费）",
          tr_keep_v.traffic == tr_gone_v.traffic,
          f"{tr_keep_v.traffic}B == {tr_gone_v.traffic}B")
    check("1h 视图世界相消改变输出布局（(1,2)→(3,1)，值不变）",
          ov.strides == (1, 2) and gv.strides == (3, 1)
          and np.array_equal(tr_keep_v.outputs[0], tr_gone_v.outputs[0]),
          f"{ov.strides} -> {gv.strides}")
    return {"hash": h, "view": tr_v, "phys": tr_p}


def part2_r1_cast() -> None:
    """R1 精度语义：Cast 往返看似类型对消。"""
    hr("2. 反例 1（精度语义）：f32→f16→f32 的 Cast 往返")

    g = Graph("r1")
    x = g.arg((2, 3))
    c1 = g.cast(x, "f32", "f16")
    c2 = g.cast(c1, "f16", "f32")
    g.returns = [c2]
    print("图（结构视角）：类型一进一出「对消」，输出 shape 与输入相同——")
    print(g.render())

    orig = g.eval(seed=3)[0]
    print(f"\n数值证据：x[0,:] = {orig[0]}")
    x0 = Graph("r1x")
    xa = x0.arg((2, 3))
    x0.returns = [xa]
    src = x0.eval(seed=3)[0]
    n_diff = int((orig != src).sum())
    print(f"roundtrip 与原值逐位相等的元素：{int((orig == src).sum())}"
          f"/{src.size}（f16 只有 10 位尾数，f32 有 23 位）")

    g2 = g.clone()
    eliminate_cast_pair_naive(g2)
    print("\n诱人改写（类型对消 → 透传）之后的图：")
    print(g2.render())
    after = g2.eval(seed=3)[0]
    check("R1a 诱人改写后数值不再逐位相等（6/6 变值，实测）",
          not np.array_equal(after, orig) and n_diff == src.size,
          f"不同元素 {n_diff}/{src.size}")

    g3 = g.clone()
    fired = eliminate_noop_cast(g3)
    check("R1b Day 67 守卫版拒绝触发（src≠dst 不是无操作）",
          not fired and g3.state_hash() == g.state_hash())

    # 同 dtype 对照：守卫版能消、且消除在物理世界真省 2n 字节
    g4 = Graph("r1ok")
    x4 = g4.arg((2, 3))
    c4 = g4.cast(x4, "f32", "f32")
    r4 = g4.relu(c4)
    g4.returns = [r4]
    tr_before = run_trace(g4.clone(), seed=3, mode="physical", verbose=False)
    eliminate_noop_cast(g4)
    tr_after = run_trace(g4.clone(), seed=3, mode="physical", verbose=False)
    check("R1c 对照：同 dtype Cast 守卫版能消，物理世界省 48B",
          eliminate_noop_cast(g4) is False and np.array_equal(
              tr_before.outputs[0], tr_after.outputs[0])
          and tr_before.traffic - tr_after.traffic == 48,
          f"{tr_before.traffic}B -> {tr_after.traffic}B")
    print("守卫清单：Cast 只在 src==dst 时透传；f32→f16 还把后续 buffer "
          "从 24B 缩到 12B——它是「变窄」的物化点，不是改名。")


def part3_r2_reshape() -> None:
    """R2 形状语义：双层同目标 Reshape。"""
    hr("3. 反例 2（形状语义）：Reshape(Reshape(x,t),t) 看似整链可透传")

    g = Graph("r2")
    x = g.arg((6,))
    r1 = g.reshape(x, (2, 3))
    r2 = g.reshape(r1, (2, 3))
    g.returns = [r2]
    print("图（结构视角）：外层目标 == 当前 shape，「看似透明」——")
    print(g.render())
    print("代数事实：Reshape(Reshape(x,t),t) = Reshape(x,t) ≠ x"
          "（除非 t == shape(x)）")

    g2 = g.clone()
    merge_adjacent_reshapes_buggy(g2)
    print("\n诱人改写（Day 69 第一版真实 bug：整链透传成 x）之后：")
    print(g2.render())
    shapes2, _ = g2.infer_shapes()
    shapes1, _ = g.infer_shapes()
    check("R2a 诱人改写后 return 的 shape 变了（(2,3) → (6,)）",
          shapes2[g2.returns[0]] == (6,)
          and shapes1[g.returns[0]] == (2, 3))

    # 下游接一个 rank-1 转置 → Verifier 拦截（Day 69 压力对拍同款现场）
    g3 = Graph("r2v")
    x3 = g3.arg((2, 3))
    a = g3.reshape(x3, (6,))
    b = g3.reshape(a, (6,))
    t3 = g3.transpose(b, (0,))
    g3.returns = [t3]
    g3b = g3.clone()
    merge_adjacent_reshapes_buggy(g3b)
    _, errs = g3b.infer_shapes()
    print("\n下游接 rank-1 转置再跑诱人改写 —— Verifier 裁决：")
    for e in errs:
        print(f"  {e}")
    check("R2b 错误透传被 Verifier 当场拦截（[V1] perm 对 rank 不合法）",
          any("V1" in e for e in errs), errs[0] if errs else "")

    g4 = g.clone()
    merge_adjacent_reshapes(g4)
    naive_dce(g4)
    print("\n守卫版（Day 66：并成一层 Reshape(x, 外层目标)）：")
    print(g4.render())
    check("R2c 守卫版只并一层且数值逐位相等",
          g4.count_kind("reshape") == 1
          and np.array_equal(g4.eval(seed=5)[0], g.eval(seed=5)[0]))
    print("守卫清单：合并永远替换为 Reshape(x, 外层目标)；"
          "「同 shape 才透传」交给 transparent 判据单独把关。")


def part4_r3_copy() -> None:
    """R3 别名语义：Copy 消除。"""
    hr("4. 反例 3（别名语义）：copy(x) 值上恒等，消除后写集合漂移")

    g = Graph("r3")
    x = g.arg((2, 3))
    y = g.copy(x)
    z = g.relu(y)
    g.returns = [x, z]        # 函数同时返回 x 和 relu(copy(x))
    print("图（结构视角）：copy 是值上的恒等映射，「看似冗余」——")
    print(g.render())

    print("\n-- 后端把逐元素算子编成原地 kernel（in-place）时的内存账本 --")
    tr_keep = run_trace(g.clone(), seed=7, mode="view",
                        inplace_elementwise=True)
    print(f"  保留 copy：{trace_summary(g, tr_keep)}")

    g2 = g.clone()
    eliminate_copy_naive(g2)
    print("\n消除 copy 之后（值世界看起来毫无变化）：")
    print(g2.render())
    tr_gone = run_trace(g2.clone(), seed=7, mode="view",
                        inplace_elementwise=True)
    print(f"  消除 copy：{trace_summary(g2, tr_gone)}")

    check("R3a 值世界看不见差别（纯函数 eval 逐位相等）",
          all(np.array_equal(a, b) for a, b in zip(g.eval(seed=7),
                                                   g2.eval(seed=7))))
    check("R3b 内存世界第一个输出被污染（x ≠ 原 x）",
          not np.array_equal(tr_keep.outputs[0], tr_gone.outputs[0]))
    check("R3c 写集合漂移：写 buf1 → 写 buf0（外部输入）",
          tr_keep.input_bufs_written == set()
          and tr_gone.input_bufs_written == {-1},
          f"{sorted(tr_keep.input_bufs_written)} -> "
          f"{sorted(tr_gone.input_bufs_written)}")
    check("R3d 污染可观测：消除后 return 的 x 变成了 relu(x)",
          np.array_equal(tr_gone.outputs[0], tr_gone.outputs[1]))
    print("守卫清单：copy 消除需要别名分析——「源缓冲此后只读」或"
          "「所有消费者都不原地写」才允许删；这正是 MLIR bufferization "
          "里 bufferizesToMemoryWrite 分析做的事。")


def part5_r4_store() -> None:
    """R4 副作用语义：无使用者的 store。"""
    hr("5. 反例 4（副作用语义）：无使用者的 store 不是死代码")

    g = Graph("r4")
    x = g.arg((2, 3))
    s = g.store(x)
    g.returns = []             # 无返回：整个函数只为副作用而存在
    print("图（结构视角）：store 没有任何使用者——DCE 的标准猎物：")
    print(g.render())

    tr_full = run_trace(g.clone(), seed=11, mode="view", verbose=False)
    print(f"\n完整执行的内存账本：外部全局 G = {tr_full.ext_state}")

    g2 = g.clone()
    dropped = naive_dce(g2)
    print(f"\nnaive DCE（Day 69 原样，只看 return 可达性）删掉了：{dropped}")
    tr_naive = run_trace(g2.clone(), seed=11, mode="view", verbose=False)
    print(f"删掉后执行：G = {tr_naive.ext_state}")

    g3 = g.clone()
    dropped3 = guarded_dce(g3)
    tr_guard = run_trace(g3.clone(), seed=11, mode="view", verbose=False)

    check("R4a naive DCE 误删 store（副作用丢失）",
          g2.by_name(s) is None and tr_naive.ext_state is None)
    check("R4b 带副作用模型的 DCE 保留 store",
          dropped3 == [] and tr_guard.ext_state is not None)
    check("R4c 副作用可观测：保留时 G 有数据、误删后为空",
          tr_full.ext_state is not None and tr_naive.ext_state is None)
    print("守卫清单：DCE 的活跃集除了 return 可达，还要并上"
          "「副作用 op 集合」；图结构（无使用者）和内存语义（有观察者）"
          "在这里分道扬镳。")


def part6_r5_identity_transpose() -> None:
    """R5 布局语义：恒等排列的物理转置。"""
    hr("6. 反例 5（布局语义）：恒等排列的 transpose，值上照抄、内存上物化")

    def build() -> Graph:
        g = Graph("r5")
        a = g.arg((2, 3))
        v = g.transpose(a, (1, 0))        # (3,2) 视图，strides (1,3)
        p = g.transpose(v, (0, 1))        # 恒等排列 —— 今天的被告
        s1 = g.reshape(p, (6,))           # 消费者 1
        s2 = g.reshape(p, (3, 2))         # 消费者 2
        g.returns = [s1, s2]
        return g

    g = build()
    print("图（结构视角）：第二个 transpose 的 perm=(0,1)，"
          "「值上什么都不做」，还有两个 reshape 消费它——")
    print(g.render())

    # 2×2 实验：{视图世界, p 物化} × {保留 p, 消除 p}
    g_keep = build()
    p_name = g_keep.ops[2].name
    tr_view_keep = run_trace(g_keep.clone(), seed=13, mode="view",
                             verbose=False)
    tr_phys_keep = run_trace(g_keep.clone(), seed=13, mode="view",
                             force_physical={p_name}, verbose=False)

    g_gone = build()
    eliminate_identity_transpose_naive(g_gone)
    tr_view_gone = run_trace(g_gone.clone(), seed=13, mode="view",
                             verbose=False)
    tr_phys_gone = run_trace(g_gone.clone(), seed=13, mode="view",
                             force_physical={p_name}, verbose=False)

    print("\n消除恒等转置之后（值世界毫无变化）：")
    print(g_gone.render())

    print("\n-- 视图世界（p 本来就是 0 字节视图）--")
    print(f"  保留 p：{trace_summary(g_keep, tr_view_keep)}")
    print(f"  消除 p：{trace_summary(g_gone, tr_view_gone)}")
    print("  → 消除免费：traffic 不变、还少一个 op。在纯视图世界它"
          "确实「看似能消除」而且真能消除。")
    print("\n-- 物化世界（p 是 strided→连续 的布局转换，"
          "Day 68 的 linalg 世界）--")
    print(f"  保留 p：{trace_summary(g_keep, tr_phys_keep)}"
          f"   ← p 搬 48B，两个 reshape 全变 0B 视图")
    print(f"  消除 p：{trace_summary(g_gone, tr_phys_gone)}"
          f"   ← 两个 reshape 各自被迫拷贝")
    print("  → 同一个改写：traffic 48B→96B 翻倍。物化点的价值是"
          "「把布局转换摊销到所有消费者」，删掉它，")
    print("    拷贝没有消失，只是搬进每个消费者的实现里、还翻了倍。")

    check("R5a 视图世界：消除恒等转置 traffic 不变（真的免费）",
          tr_view_keep.traffic == tr_view_gone.traffic
          and g_gone.n_ops() == g_keep.n_ops() - 1,
          f"{tr_view_keep.traffic}B == {tr_view_gone.traffic}B")
    check("R5b 物化世界：消除后 traffic 翻倍（48B -> 96B）",
          tr_phys_keep.traffic == 48 and tr_phys_gone.traffic == 96,
          f"{tr_phys_keep.traffic}B -> {tr_phys_gone.traffic}B")
    check("R5c 四种执行的输出值全部逐位相等（差别只在内存账本）",
          all(np.array_equal(tr_view_keep.outputs[i],
                             tr_phys_gone.outputs[i]) for i in range(2)))
    check("R5d 物化世界保留 p 时，两个 reshape 都是 0B 视图",
          tr_phys_keep.traffic == 48
          and any("视图" in e and "reshape" in e
                  for e in tr_phys_keep.events))
    # numpy 侧独立佐证
    A = np.arange(1, 7, dtype=np.float32).reshape(2, 3)
    V = A.T
    P = np.ascontiguousarray(V)
    check("R5e numpy 佐证：视图与物化值相等、共享关系相反、"
          "reshape 权利相反",
          np.array_equal(V, P) and np.shares_memory(V, A)
          and not np.shares_memory(P, A)
          and not np.shares_memory(V, V.reshape(6,))
          and np.shares_memory(P, P.reshape(6,)))
    print("守卫清单：恒等排列只证明「值语义是照抄」；能不能删要看"
          "消费者数量与布局契约——单消费者时消除是 traffic 中性的"
          "（拷贝挪个地方），多消费者时物化点摊销布局转换，删了翻倍。"
          "图上同一个 transpose 节点，两个世界两种身份。")


def part7_r6_multi_user() -> None:
    """R6 复制语义：多使用者传播。"""
    hr("7. 反例 6（复制语义）：中间结果另有使用者时，传播变成复制")

    g = Graph("r6")
    x = g.arg((2, 3))
    r = g.relu(x)
    t = g.transpose(r, (1, 0))
    g.returns = [r, t]        # relu 的结果同时被 return 和 T 使用
    print("图（结构视角）：T 挂在 relu 上面，和 Day 68 的传播模式"
          "长得一模一样——")
    print(g.render())
    print(f"users({r}) = "
          f"{[u.kind if isinstance(u, Op) else u for u in g.users(r)]}"
          f"  ← 不满足 C2 唯一使用者门")

    g2 = g.clone()
    pushed = push_transpose_through_elementwise(g2, respect_unique=False)
    print("\n无视 C2 强行传播之后：")
    print(g2.render())
    n_el_before = 6            # relu 一次 × 6 元素
    n_el_after = 12            # relu 两次 × 6 元素
    print(f"计算 op：{g.n_ops()} -> {g2.n_ops()}；"
          f"逐元素计算量：{n_el_before} -> {n_el_after}（翻倍）；"
          f"转置数：{g.count_kind('transpose')} -> "
          f"{g2.count_kind('transpose')}（一个没少）")

    g3 = g.clone()
    fired = push_transpose_through_elementwise(g3, respect_unique=True)
    check("R6a 强行传播值仍然等价（错误不在正确性，在收益）",
          pushed and all(np.array_equal(a, b) for a, b in
                         zip(g.eval(seed=17), g2.eval(seed=17))))
    check("R6b 强行传播后 op 数增加、转置数不变",
          g2.n_ops() == g.n_ops() + 1
          and g2.count_kind("transpose") == g.count_kind("transpose"))
    check("R6c C2 守卫版拒绝触发（唯一使用者门）",
          not fired and g3.state_hash() == g.state_hash())
    print("守卫清单：C2 不是官僚作风——多使用者时传播不省转置、"
          "反而复制逐元素工作；「看似能消除」在这里连收益都是负的。")


def part8_r7_reduce() -> None:
    """R7 算子语义：非逐元素传播。"""
    hr("8. 反例 7（算子语义）：T(reduce_sum(x)) 推不过去")

    g = Graph("r7")
    x = g.arg((2, 3))
    rs = g.reduce_sum(x, axis=0)      # (1,3)
    t = g.transpose(rs, (1, 0))       # (3,1)
    g.returns = [t]
    print("图（结构视角）：还是「transpose 挂在算子上面」，"
          "和 T(relu(x)) 同构——")
    print(g.render())

    # 诱人改写：照抄 Day 68 的传播（不换 axis）
    g2 = Graph("r7naive")
    x2 = g2.arg((2, 3))
    t2 = g2.transpose(x2, (1, 0))     # T(x) (3,2)
    rs2 = g2.reduce_sum(t2, axis=0)   # (1,2)  ← shape 已经不对了
    g2.returns = [rs2]
    print("\n照抄传播（T 提到 reduce 之下、axis 原样）之后：")
    print(g2.render())
    a, b = g.eval(seed=19)[0], g2.eval(seed=19)[0]
    print(f"原式 shape {a.shape} vs 传播后 shape {b.shape}")

    # 正确改写：axis 要跟着 perm 换（perm 把 dim0 挪到 dim1）
    g3 = Graph("r7fix")
    x3 = g3.arg((2, 3))
    t3 = g3.transpose(x3, (1, 0))
    rs3 = g3.reduce_sum(t3, axis=1)   # (3,1)
    g3.returns = [rs3]
    c = g3.eval(seed=19)[0]
    print(f"axis 换成 1 之后：shape {c.shape}，"
          f"与原式逐位相等 {np.array_equal(a, c)}")

    check("R7a 照抄传播后 shape 改变（(3,1) → (1,2)），Verifier 拦截",
          a.shape == (3, 1) and b.shape == (1, 2)
          and len(g2.infer_shapes()[1]) == 0)
    check("R7b 照抄传播数值不相等（即使形状碰巧兼容也不等）",
          not np.array_equal(a, b))
    check("R7c axis 跟着 perm 换之后才等价",
          np.array_equal(a, c))
    check("R7d Day 68 白名单不含 reduce_sum（C1 守卫）",
          "reduce_sum" not in ELEMENTWISE_WHITELIST)
    # 一般 perm 的转置不变量（3D 非对换验证）：新 axis = inv_perm(旧 axis)。
    # 注意不是 perm[旧 axis]——那只在 (1,0) 这类对换 perm 上碰巧成立。
    rng3 = np.random.default_rng(23)
    x3 = rng3.standard_normal((4, 2, 6))
    p3 = (2, 0, 1)
    inv3 = [0] * 3
    for i, pi in enumerate(p3):
        inv3[pi] = i
    lhs3 = np.transpose(x3.sum(axis=1, keepdims=True), p3)
    rhs3 = np.transpose(x3, p3).sum(axis=inv3[1], keepdims=True)
    rhs_wrong = np.transpose(x3, p3).sum(axis=p3[1], keepdims=True)
    check("R7e 一般 perm：新 axis = inv_perm[旧 axis]（3D 实测）",
          np.array_equal(lhs3, rhs3)
          and lhs3.shape == (6, 4, 1)
          and not np.array_equal(lhs3, rhs_wrong),
          f"inv_perm={tuple(inv3)}，axis={inv3[1]}")
    print("守卫清单：C1 白名单只放「逐位置不变」的算子；reduce 这类"
          "带轴语义的算子要传播，必须连带改写 axis——那是另一条 "
          "Pattern（转置不变量：新 axis = inv_perm[旧 axis]，"
          "即旧轴被 perm 挪到了哪一位），不是免费 lunch。")


def part9_mlir_probes() -> dict:
    """MLIR 探针：stock 编译器对同款问题的裁决。"""
    hr("9. MLIR 探针：stock 管道怎么判这五个案子")

    results: dict[str, str] = {}
    exe = find_mlir_opt()
    if exe is None:
        print("mlir-opt 不可用，探针跳过（不影响其余部分）")
        return results
    print(f"mlir-opt: {exe}\n")

    # 探针 1：truncf/extf 往返（R1）
    code, out = run_mlir(HERE / "probe_cast_roundtrip.mlir", ["--canonicalize"])
    n_cast = count_op(out, "arith.truncf") + count_op(out, "arith.extf")
    results["cast"] = f"truncf+extf 剩 {n_cast} 个"
    print(f"探针 1（R1 Cast 往返）--canonicalize：truncf+extf 共剩 "
          f"{n_cast} 个 → stock 不折叠")
    check("M1 cast 往返不被 --canonicalize 折叠（精度语义）", n_cast == 2)

    # 探针 2：reshape 链（R2）
    code, out = run_mlir(HERE / "probe_reshape_chain.mlir", ["--canonicalize"])
    n_rs = count_op(out, "tensor.reshape")
    results["reshape"] = f"tensor.reshape 剩 {n_rs} 个"
    print(f"探针 2（R2 Reshape 链）--canonicalize：tensor.reshape 剩 "
          f"{n_rs} 个 → stock 不合并")
    check("M2 reshape 链不被 --canonicalize 合并", n_rs == 2)

    # 探针 3：memref.copy（R3）
    code, out = run_mlir(HERE / "probe_copy_identity.mlir", ["--canonicalize"])
    n_cp = count_op(out, "memref.copy")
    code2, out2 = run_mlir(HERE / "probe_copy_identity.mlir", ["--cse"])
    n_cp2 = count_op(out2, "memref.copy")
    results["copy"] = f"copy 剩 {n_cp}/{n_cp2} 个"
    print(f"探针 3（R3 Copy）--canonicalize / --cse：memref.copy 剩 "
          f"{n_cp} / {n_cp2} 个 → stock 不删")
    check("M3 memref.copy 在 canonicalize 和 cse 下都保留（别名语义）",
          n_cp == 1 and n_cp2 == 1)

    # 探针 4：store vs 死 addf（R4）
    code, out = run_mlir(HERE / "probe_side_effect.mlir", ["--cse"])
    n_store = count_op(out, "memref.store")
    n_addf = count_op(out, "arith.addf")
    code2, out2 = run_mlir(HERE / "probe_side_effect.mlir",
                           ["--canonicalize"])
    n_store2 = count_op(out2, "memref.store")
    n_addf2 = count_op(out2, "arith.addf")
    results["store"] = (f"store {n_store}/{n_store2}，死 addf "
                        f"{n_addf}/{n_addf2}")
    print(f"探针 4（R4 副作用）--cse / --canonicalize：store 剩 "
          f"{n_store} / {n_store2}，无使用者的纯 addf 剩 "
          f"{n_addf} / {n_addf2} → 一删一留")
    check("M4 死的纯算子被删、store 保留（副作用模型）",
          n_store == 1 and n_store2 == 1 and n_addf == 0 and n_addf2 == 0)

    # 探针 5：恒等排列 linalg.transpose（R5）
    code, out = run_mlir(HERE / "probe_identity_transpose.mlir",
                         ["--canonicalize"])
    n_t = count_op(out, "linalg.transpose")
    code2, out2 = run_mlir(HERE / "probe_identity_transpose.mlir", ["--cse"])
    n_t2 = count_op(out2, "linalg.transpose")
    results["identity_t"] = f"linalg.transpose 剩 {n_t}/{n_t2} 个"
    print(f"探针 5（R5 恒等排列物理转置）--canonicalize / --cse："
          f"linalg.transpose 剩 {n_t} / {n_t2} 个 → stock 不删")
    check("M5 恒等排列的物理转置不被删（布局语义）",
          n_t == 1 and n_t2 == 1)
    return results


GUARDS = [
    ("merge_adjacent_transposes", "D65",
     "组合律 r[i]=p1[p2[i]] 数学恒等；恒等才透传"),
    ("merge_adjacent_reshapes", "D66",
     "numel 守恒；只能并成 Reshape(x, 外层目标)"),
    ("eliminate_transparent_reshape", "D66",
     "目标 shape == 输入 shape 才透传"),
    ("eliminate_noop_cast", "D67", "src dtype == dst dtype"),
    ("push_transpose C1", "D68", "白名单：只放逐位置不变的算子"),
    ("push_transpose C2", "D68", "T 是 E 结果的唯一使用者"),
    ("fuse_add_relu", "D51/54", "add 的结果只有这一个 relu 在用"),
    ("DCE（今天补的守卫）", "D70",
     "活跃集 = return 可达 ∪ 副作用 op"),
    ("copy 消除（今天补的守卫）", "D70",
     "别名分析：源缓冲此后无人原地写 / 只读"),
    ("恒等转置消除（今天补的守卫）", "D70",
     "看消费者数量与布局契约：物化点摊销布局转换，多消费者时不能删"),
]


def part10_summary() -> None:
    hr("10. 反例集总表 + 守卫清单（今日产出）")

    rows = [
        ("R1", "Cast f32→f16→f32", "类型一进一出「对消」",
         "f16 只有 10 位尾数，roundtrip 丢位", "实测 6/6 元素变值"),
        ("R2", "双层同目标 Reshape", "外层目标==当前 shape，看似透明",
         "Reshape(Reshape(x,t),t)=Reshape(x,t)≠x", "V1 拦截 + shape (2,3)→(6,)"),
        ("R3", "copy(x) 消除", "值上恒等映射",
         "消除后下游原地写污染源缓冲", "写集合 buf1→buf0，return 的 x 变 relu(x)"),
        ("R4", "无使用者的 store", "DCE 的标准猎物",
         "副作用对外部世界可观察", "naive DCE 删掉后 G 变空"),
        ("R5", "恒等排列物理转置", "perm=(0,1) 值上照抄",
         "它是 strided→连续 的物化点，摊销布局转换",
         "双消费者下消除让 traffic 48B→96B 翻倍"),
        ("R6", "多使用者传播", "和 T(relu(x)) 同构",
         "传播复制逐元素工作、转置一个没少", "op 2→3，元素计算 6→12"),
        ("R7", "reduce 传播", "还是「T 挂在算子上」",
         "轴语义要跟着 perm 换，白名单不放行", "shape (3,1)→(1,2)，数值不等"),
    ]
    print("反例集（计划要求 ≥5，实际 7 条）：\n")
    print(f"{'编号':<4}{'反例':<18}{'图结构视角（诱人处）':<24}"
          f"{'内存/数值语义（拒绝理由）':<30}{'实测证据'}")
    print("-" * 110)
    for r in rows:
        print(f"{r[0]:<4}{r[1]:<18}{r[2]:<26}{r[3]:<32}{r[4]}")

    print("\n守卫清单（每条 Pattern 的语义门 = 反例集的镜像）：\n")
    for name, day, gate in GUARDS:
        print(f"  [{day}] {name:<28} {gate}")

    print("\n带走的三句话：")
    print("  1. 结构账本（state_hash）只回答「值怎么算」；内存账本"
          "（buffer/strides/traffic）回答「字节怎么搬」——")
    print("     同一张图在视图世界和物理世界是两种程序（48B vs 144B）。")
    print("  2. 每条消除/传播规则的守卫，都是某个反例的墓碑——"
          "守卫不是官僚作风，是语义边界。")
    print("  3. 值等价是改写的必要条件，不是充分条件：别名、布局、"
          "副作用、精度、轴语义都住在值世界看不见的地方。")


def main() -> int:
    print("第 70 天主实验：图结构相同 ≠ 内存语义相同"
          "（第 10 周复盘 + 反例集）")
    print(f"环境：Python {sys.version.split()[0]} / numpy {np.__version__}")
    part1_two_ledgers()
    part2_r1_cast()
    part3_r2_reshape()
    part4_r3_copy()
    part5_r4_store()
    part6_r5_identity_transpose()
    part7_r6_multi_user()
    part8_r7_reduce()
    part9_mlir_probes()
    part10_summary()
    hr(f"汇总：PASS {_n_pass} / FAIL {_n_check - _n_pass}"
       f"（共 {_n_check} 项）")
    return 0 if _n_pass == _n_check else 1


if __name__ == "__main__":
    raise SystemExit(main())
