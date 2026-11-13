#!/usr/bin/env python3
"""combo_lab.py —— 第 69 天（图优化组合测试）主实验。

今天的核心：把第 8 周的融合 Pattern 与本周的 Transpose / Reshape / Cast /
传播 Pattern 装进**同一根管道**，研究只有组合才会暴露的三件事：

  ① 不动点（fixpoint）   跑几轮停？停下来的 IR 是否「稳定」——
                         稳定三条件：二次运行零轮次（幂等）+ 状态哈希不变
                         + 数值逐位相等。
  ② 意外无限变换         单测都收敛的规则，组合后可能：
                         · 规则环：可交换算子的双向交换规则在排列空间转圈；
                         · undo 对：fuse / unfuse 互相撤销；
                         · 哈希陷阱：用原始 SSA 名字做状态哈希，名字每轮递增，
                           环永远测不出来，只有 max_rounds 兜底。
                         驯服办法：单调配度（良基测度每步严格下降）——
                         给交换规则一个规范序（按算子秩排序），每步恰消一个逆序。
  ③ 优化顺序             合流对（confluent）：换顺序只影响轮次，终点相同
                         （实测 Cast 消除 × 融合）；
                         竞争对：换顺序换终点（实测 传播 × 融合 争同一个
                         「窗口」relu：先传播 5 op，先融合 4 op，数值都对）。

MLIR 对表（第 6 节，本机 LLVM 18.1.8 实测）：
    --canonicalize 与 --cse 各自幂等（跑两遍 = 跑一遍）；
    --canonicalize --cse → 1 个 addf，--cse --canonicalize → 2 个 addf
    （一次性管道按序执行，CSE 先跑时常量还没被折出来），
    再补一趟 --cse 又能追平——差的是调度不是能力；
    --canonicalize 会删恒等 tensor.cast，从而把 2 个相同的 linalg.generic
    交给 CSE 合成 1 个；顺序反过来就合不成。

运行：python3 combo_lab.py   （在 code/ 目录下）
"""

from __future__ import annotations

import hashlib
import random
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
OUT = HERE / "outputs"
OUT.mkdir(exist_ok=True)

PASS = 0
FAIL = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"[PASS] {name}" + (f"（{detail}）" if detail else ""))
    else:
        FAIL += 1
        print(f"[FAIL] {name}" + (f"（{detail}）" if detail else ""))


def hr(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


# ============================================================
# 排列 / 形状工具（Day 64/65 约定的直接复用）
# ============================================================

def valid_perm(p) -> bool:
    return sorted(p) == list(range(len(p)))


def inv_perm(p) -> tuple:
    q = [0] * len(p)
    for i, pi in enumerate(p):
        q[pi] = i
    return tuple(q)


def t_shape(shape, perm) -> tuple:
    """Day 64 约定：out_shape[i] = in_shape[perm[i]]（与 np.transpose 一致）。"""
    return tuple(shape[perm[i]] for i in range(len(shape)))


def numel(shape) -> int:
    n = 1
    for d in shape:
        n *= int(d)
    return n


# ============================================================
# mini 图 IR：Op + Graph + Verifier + 数值执行
# （在 Day 68 的基础上扩了三种 op：cast / floor / fused_add_relu）
# ============================================================

@dataclass
class Op:
    kind: str                       # arg/const/transpose/relu/neg/floor/cast/add/
                                    # fused_add_relu/reduce_sum/reshape
    inputs: list = field(default_factory=list)
    name: str = ""
    perm: tuple = ()                # transpose
    value: np.ndarray | None = None  # const
    shape: tuple = ()               # arg
    axis: int = -1                  # reduce_sum（keepdims=True）
    new_shape: tuple = ()           # reshape
    dtypes: tuple = ()              # cast：(src, dst)，如 ("f32", "f32")


ELEMENTWISE_WHITELIST = ("relu", "neg", "floor")   # C1 语义门（D68，今日加 floor）

NP_DTYPE = {"f32": np.float32, "f16": np.float16, "f64": np.float64}


class Graph:
    def __init__(self, name: str):
        self.name = name
        self.ops: list[Op] = []
        self.returns: list[str] = []
        self.arg_shapes: list[tuple] = []
        self._n = 0

    # ---------- 构图 API ----------

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

    def fused_add_relu(self, a: str, b: str) -> str:
        return self.add_op("fused_add_relu", [a, b])

    def reduce_sum(self, x: str, axis: int) -> str:
        return self.add_op("reduce_sum", [x], axis=axis)

    def reshape(self, x: str, new_shape) -> str:
        return self.add_op("reshape", [x], new_shape=tuple(new_shape))

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
        """算子数（不含 arg / const 叶子，与本周各天口径一致）。"""
        return sum(1 for op in self.ops if op.kind not in ("arg", "const"))

    def n_all(self) -> int:
        """全部 op 数（含 arg / const，D68 的「op 4」口径）。"""
        return len(self.ops)

    def kinds_seq(self) -> tuple:
        return tuple(op.kind for op in self.ops if op.kind not in ("arg", "const"))

    def copy(self) -> "Graph":
        g = Graph(self.name)
        g.ops = [Op(kind=op.kind, inputs=list(op.inputs), name=op.name,
                    perm=op.perm, value=op.value, shape=op.shape,
                    axis=op.axis, new_shape=op.new_shape, dtypes=op.dtypes)
                 for op in self.ops]
        g.returns = list(self.returns)
        g.arg_shapes = list(self.arg_shapes)
        g._n = self._n
        return g

    # ---------- Verifier ----------

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
            elif op.kind in ("relu", "neg", "floor", "cast"):
                s = shapes[op.inputs[0]]
            elif op.kind in ("add", "fused_add_relu"):
                a, b = shapes[op.inputs[0]], shapes[op.inputs[1]]
                if a != b:
                    errs.append(f"[V2] {op.name} {op.kind} 两操作数 shape "
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

    # ---------- 数值执行 ----------

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
            elif op.kind == "fused_add_relu":
                v = np.maximum(vals[op.inputs[0]] + vals[op.inputs[1]],
                               np.float32(0))
            elif op.kind == "reduce_sum":
                v = vals[op.inputs[0]].sum(axis=op.axis, keepdims=True,
                                           dtype=np.float32)
            elif op.kind == "reshape":
                v = vals[op.inputs[0]].reshape(op.new_shape)
            else:
                raise ValueError(op.kind)
            vals[op.name] = v
        return [np.asarray(vals[r]) for r in self.returns]

    # ---------- 打印与状态哈希 ----------

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
            elif op.kind in ("relu", "neg", "floor"):
                body = f"{op.name} = {op.kind} {ins}"
            elif op.kind == "cast":
                body = (f"{op.name} = cast {ins}, "
                        f"{op.dtypes[0]}->{op.dtypes[1]}")
            elif op.kind == "add":
                body = f"{op.name} = add {ins}"
            elif op.kind == "fused_add_relu":
                body = f"{op.name} = fused_add_relu {ins}"
            elif op.kind == "reduce_sum":
                body = f"{op.name} = reduce_sum {ins}, axis={op.axis}"
            elif op.kind == "reshape":
                body = f"{op.name} = reshape {ins}, to={list(op.new_shape)}"
            else:
                body = f"{op.name} = {op.kind} {ins}"
            lines.append(f"  {body:<44s} ; -> {shapes[op.name]}")
        lines.append(f"  return {', '.join(self.returns)}")
        return "\n".join(lines)

    def state_hash(self) -> str:
        """规范化结构哈希：op 按 topo 位置重命名为 #k——振荡检测的前提。

        如果用原始 SSA 名字（%1 %2 …）做哈希，每次改写名字都会递增，
        状态即使回到结构相同的图，哈希也不同——环测不出来（第 4 节实测）。
        """
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

    def raw_hash(self) -> str:
        """反面教材：原始 SSA 名字哈希（render 里带 %N，N 只增不减）。"""
        return hashlib.md5(self.render().encode()).hexdigest()

    # ---------- 死代码消除 ----------

    def dce(self) -> int:
        live = set(self.returns)
        for op in reversed(self.ops):
            if op.name in live:
                live.update(op.inputs)
        before = len(self.ops)
        self.ops = [op for op in self.ops if op.name in live]
        return before - len(self.ops)


def _splice(g: Graph, at: int, new_ops: list[Op],
            replace: dict[str, str]) -> None:
    """把 g.ops[at] 位置替换为 new_ops，并把全图对 replace 键的引用改名。"""
    out: list[Op] = []
    for j, op in enumerate(g.ops):
        if j == at:
            out.extend(new_ops)
        else:
            op.inputs = [replace.get(n, n) for n in op.inputs]
            out.append(op)
    g.ops = out
    g.returns = [replace.get(r, r) for r in g.returns]


# ============================================================
# 零件库：7 条正式 Pattern（第 8 周 + 本周，全部原样取用 / 平移过来）
# ============================================================

def merge_adjacent_transposes(g: Graph) -> bool:
    """Day 65：T_p2(T_p1(x)) -> T_r(x)，r[i] = p1[p2[i]]；r=恒等时透传。"""
    for idx, t2 in enumerate(g.ops):
        if t2.kind != "transpose" or len(t2.inputs) != 1:
            continue
        t1 = g.by_name(t2.inputs[0])
        if t1 is None or t1.kind != "transpose" or len(t1.inputs) != 1:
            continue
        r = tuple(t1.perm[t2.perm[i]] for i in range(len(t2.perm)))
        x = t1.inputs[0]
        if r == tuple(range(len(r))):
            repl = x
            new_ops: list[Op] = []
        else:
            tm = Op("transpose", [x], perm=r, name=g._new())
            repl = tm.name
            new_ops = [tm]
        _splice(g, idx, new_ops, {t2.name: repl})
        g.dce()
        return True
    return False


def merge_adjacent_reshapes(g: Graph) -> bool:
    """Day 66：Reshape(Reshape(x)) -> Reshape(x, 外层目标)。

    无论两层目标是否相同，都替换为 Reshape(x, 外层目标)——
    即使 t2 == t1 也不能直接换成 x：Reshape(Reshape(x,t),t) = Reshape(x,t)，
    只有 t 恰好等于 shape(x) 时才能透传（那一步交给 transparent_r）。
    中间结果另有使用者时不强行删除（DCE 只回收死结点）。
    """
    for idx, r2 in enumerate(g.ops):
        if r2.kind != "reshape" or len(r2.inputs) != 1:
            continue
        r1 = g.by_name(r2.inputs[0])
        if r1 is None or r1.kind != "reshape" or len(r1.inputs) != 1:
            continue
        x = r1.inputs[0]
        rm = Op("reshape", [x], new_shape=r2.new_shape, name=g._new())
        _splice(g, idx, [rm], {r2.name: rm.name})
        g.dce()
        return True
    return False


def eliminate_transparent_reshape(g: Graph) -> bool:
    """reshape(x) 且目标 shape == 输入 shape：纯改名，透传。"""
    shapes, _ = g.infer_shapes()
    for idx, r in enumerate(g.ops):
        if r.kind != "reshape" or len(r.inputs) != 1:
            continue
        if tuple(r.new_shape) == shapes[r.inputs[0]]:
            _splice(g, idx, [], {r.name: r.inputs[0]})
            g.dce()
            return True
    return False


def eliminate_noop_cast(g: Graph) -> bool:
    """Day 67：输入输出类型完全一致的 Cast 是无操作，透传。

    精度扩展 / 缩减（f32->f16 等）可能改变数值，一律不动——
    今天所有测试图里的 cast 也全部是 f32->f32。
    """
    for idx, c in enumerate(g.ops):
        if c.kind != "cast" or len(c.inputs) != 1:
            continue
        if c.dtypes[0] == c.dtypes[1]:
            _splice(g, idx, [], {c.name: c.inputs[0]})
            g.dce()
            return True
    return False


def fold_transpose_into_constant(g: Graph) -> bool:
    """Day 68：T(Const) -> Const'（权重离线转置，运行时零开销）。"""
    for idx, t in enumerate(g.ops):
        if t.kind != "transpose" or len(t.inputs) != 1:
            continue
        c = g.by_name(t.inputs[0])
        if c is None or c.kind != "const":
            continue
        c2 = Op("const", [],
                value=np.transpose(c.value, t.perm).copy(), name=g._new())
        _splice(g, idx, [c2], {t.name: c2.name})
        g.dce()
        return True
    return False


def push_transpose_through_elementwise(
        g: Graph, whitelist=ELEMENTWISE_WHITELIST,
        respect_unique: bool = True) -> bool:
    """Day 68 受限传播：T(E(x)) -> E(T(x))。

    C1 语义门：E ∈ 白名单（逐位置不变）；
    C2 唯一使用者门：T 是 E 结果的唯一使用者。
    """
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
        g.dce()
        return True
    return False


def fuse_add_relu(g: Graph) -> bool:
    """Day 51/54：relu(add(a, b)) -> fused_add_relu(a, b)。

    多使用者门（Day 52）：add 的结果只有这一个 relu 在用时才融合——
    否则 add 死不掉，融合变成复制。
    """
    for idx, r in enumerate(g.ops):
        if r.kind != "relu" or len(r.inputs) != 1:
            continue
        a = g.by_name(r.inputs[0])
        if a is None or a.kind != "add" or len(a.inputs) != 2:
            continue
        if g.users(a.name) != [r]:
            continue
        f = Op("fused_add_relu", list(a.inputs), name=g._new())
        _splice(g, idx, [f], {r.name: f.name})
        g.dce()
        return True
    return False


# ---- 推荐顺序（今日产出「Pass 顺序说明」的默认版，理由见第 3 节实测）----
#   消除类（把图变小、给别人减负）→ 融合（改变算子形态，终结其他机会，
#   放在传播之前：实测先传播会把 relu 换成 T，融合从此够不着）
#   → 传播（最后收尾：让转置去和伙伴会合）。
RECOMMENDED_PATTERNS = [
    merge_adjacent_transposes,       # D65
    merge_adjacent_reshapes,         # D66
    eliminate_transparent_reshape,   # D66 附带
    eliminate_noop_cast,             # D67
    fold_transpose_into_constant,    # D68
    fuse_add_relu,                   # D51/54
    push_transpose_through_elementwise,  # D68
]


# ============================================================
# 反面教材（只进第 4 节的实验，不进正式 Pattern 集）
# ============================================================

def unfuse_add_relu(g: Graph) -> bool:
    """undo 对的另一半：fused_add_relu(a,b) -> relu(add(a,b))。

    现实出处：后端不支持融合算子时的「物化」（materialize）。
    与 fuse_add_relu 同场 = 互相撤销 = 振荡（第 4 节实测）。
    """
    for idx, f in enumerate(g.ops):
        if f.kind != "fused_add_relu" or len(f.inputs) != 2:
            continue
        a = Op("add", list(f.inputs), name=g._new())
        r = Op("relu", [a.name], name=g._new())
        _splice(g, idx, [a, r], {f.name: r.name})
        g.dce()
        return True
    return False


def swap_adjacent(g: Graph, producer_kind: str, consumer_kind: str) -> bool:
    """交换规则：链 x -> P -> V（V 是 P 的唯一使用者，均为一元），
    改写为 x -> V' -> P'，即 V(P(x)) -> P(V(x))。

    只对**已证可交换**的算子对使用（第 4 节先数值验证再上规则）。
    """
    for idx, v in enumerate(g.ops):
        if v.kind != consumer_kind or len(v.inputs) != 1:
            continue
        p = g.by_name(v.inputs[0])
        if p is None or p.kind != producer_kind or len(p.inputs) != 1:
            continue
        if g.users(p.name) != [v]:
            continue
        x = p.inputs[0]
        v2 = Op(v.kind, [x], perm=v.perm, dtypes=v.dtypes, name=g._new())
        p2 = Op(p.kind, [v2.name], perm=p.perm, dtypes=p.dtypes, name=g._new())
        _splice(g, idx, [v2, p2], {v.name: p2.name})
        g.dce()
        return True
    return False


# 单调配度：给可交换算子定一个规范序（秩小者在生产者一侧）。
# 交换规则只在「逆序」时触发——每步恰好消掉一个逆序，逆序数是良基测度，
# 终止性由此保证（这正是把「无限交换」驯服成「冒泡排序」的办法）。
SWAP_RANK = {"transpose": 0, "relu": 1, "floor": 2}


def canonical_swap(g: Graph) -> bool:
    """单调版交换：只把「秩大在前」的相邻对换到规范序。"""
    for idx, v in enumerate(g.ops):
        if v.kind not in SWAP_RANK or len(v.inputs) != 1:
            continue
        p = g.by_name(v.inputs[0])
        if p is None or p.kind not in SWAP_RANK or len(p.inputs) != 1:
            continue
        if SWAP_RANK[p.kind] <= SWAP_RANK[v.kind]:
            continue                                  # 已在规范序，不动
        if g.users(p.name) != [v]:
            continue
        x = p.inputs[0]
        v2 = Op(v.kind, [x], perm=v.perm, dtypes=v.dtypes, name=g._new())
        p2 = Op(p.kind, [v2.name], perm=p.perm, dtypes=p.dtypes, name=g._new())
        _splice(g, idx, [v2, p2], {v.name: p2.name})
        g.dce()
        return True
    return False


def inversions(g: Graph) -> int:
    """链上算子（按 topo 序）的**总逆序数**：i<j 且 rank(i) > rank(j)。

    经典结论（冒泡排序）：交换一对「逆序的相邻元素」恰使总逆序数减 1——
    这正是 canonical_swap 的终止性证明。注意不能用「相邻逆序对数」当测度：
    它在交换后可能不降（本实验第一次实现时就踩了这个坑，见 README 第 6 节）。
    """
    ranks = [SWAP_RANK[op.kind] for op in g.ops if op.kind in SWAP_RANK]
    n = 0
    for i in range(len(ranks)):
        for j in range(i + 1, len(ranks)):
            if ranks[i] > ranks[j]:
                n += 1
    return n


# ============================================================
# PassManager：循环到不动点 + 状态哈希环检测
# ============================================================

def run_passes(g: Graph, patterns, max_rounds: int = 40,
               hash_fn=None) -> tuple[int, str]:
    """跑到不动点；用规范化状态哈希检测振荡（Day 68 原样复用）。"""
    hash_fn = hash_fn or Graph.state_hash
    seen = {hash_fn(g)}
    rounds = 0
    while rounds < max_rounds:
        fired = False
        for p in patterns:
            if p(g):
                fired = True
                break
        if not fired:
            return rounds, "fixpoint"
        rounds += 1
        h = hash_fn(g)
        if h in seen:
            return rounds, "oscillation"
        seen.add(h)
    return rounds, "max_rounds"


def run_passes_traced(g: Graph, patterns, max_rounds: int = 40,
                      hash_fn=None) -> tuple[int, str, list]:
    """同 run_passes，但记录每一轮之后的 (kinds 序列, 哈希)——看轨迹用。"""
    hash_fn = hash_fn or Graph.state_hash
    trace = [(g.kinds_seq(), hash_fn(g))]
    seen = {trace[0][1]}
    rounds = 0
    while rounds < max_rounds:
        fired = False
        for p in patterns:
            if p(g):
                fired = True
                break
        if not fired:
            return rounds, "fixpoint", trace
        rounds += 1
        trace.append((g.kinds_seq(), hash_fn(g)))
        if trace[-1][1] in seen:
            return rounds, "oscillation", trace
        seen.add(trace[-1][1])
    return rounds, "max_rounds", trace


# ---------- 对拍 ----------

def graphs_equal_num(a: Graph, b: Graph, seeds=(0, 1, 2)) -> tuple[bool, str]:
    for s in seeds:
        ra, rb = a.eval(seed=s), b.eval(seed=s)
        if len(ra) != len(rb):
            return False, f"返回个数 {len(ra)} vs {len(rb)}"
        for i, (x, y) in enumerate(zip(ra, rb)):
            if x.shape != y.shape:
                return False, f"seed={s} ret#{i} shape {x.shape} vs {y.shape}"
            if not np.array_equal(x, y):
                return False, (f"seed={s} ret#{i} 数值不等，"
                               f"max|diff|={np.max(np.abs(x - y)):.3e}")
    return True, "ok"


def op_stats(g: Graph) -> dict:
    return {"ops": g.n_ops(),
            "transpose": g.count_kind("transpose"),
            "reshape": g.count_kind("reshape"),
            "cast": g.count_kind("cast"),
            "fused": g.count_kind("fused_add_relu")}


# ============================================================
# MLIR 侧：stock 管道的真实裁决
# ============================================================

def find_mlir_opt() -> str | None:
    cand = [shutil.which("mlir-opt"), "/usr/lib/llvm-18/bin/mlir-opt",
            "/usr/lib/llvm-19/bin/mlir-opt", "/usr/lib/llvm-17/bin/mlir-opt"]
    for c in cand:
        if c and Path(c).is_file() and Path(c).exists():
            return c
    return None


def run_mlir(ir_file: Path, args: list[str]) -> tuple[int, str]:
    m = find_mlir_opt()
    if m is None:
        return -1, ""
    r = subprocess.run([m, str(ir_file)] + args,
                       capture_output=True, text=True, timeout=60)
    return r.returncode, r.stdout + r.stderr


def count_lines(text: str, pat: str) -> int:
    return sum(1 for line in text.splitlines() if pat in line)


# ============================================================
# 主实验
# ============================================================

def build_mixed_chain() -> Graph:
    """贯穿例子：10-op 混合链（2 arg + 8 计算 op），本周五种冗余全占齐。"""
    g = Graph("mixed_chain")
    x = g.arg((2, 3))
    y = g.arg((2, 3))
    t1 = g.transpose(x, (1, 0))            # (3,2)
    t2 = g.transpose(t1, (1, 0))           # (2,3)  D65：r=恒等 → 透传
    c = g.cast(t2, "f32", "f32")           # D67：无操作 → 透传
    a = g.add(c, y)                        # (2,3)
    r = g.relu(a)                          # 传播/融合争夺的窗口
    big_t = g.transpose(r, (1, 0))         # (3,2)  D68：从它向下传播
    s1 = g.reshape(big_t, (6,))            # D66：合并
    s2 = g.reshape(s1, (3, 2))             #       → 目标=输入shape → 透传
    g.returns = [s2]
    return g


def main() -> int:
    hr("== 0. 环境 ==")
    print(f"python  {sys.version.split()[0]}")
    print(f"numpy   {np.__version__}")
    m = find_mlir_opt()
    if m:
        v = subprocess.run([m, "--version"], capture_output=True, text=True)
        print(f"mlir-opt {v.stdout.splitlines()[0]}  ({m})")
    else:
        print("mlir-opt 不可用（第 6 节将降级）")

    # --------------------------------------------------------
    hr("== 1. 零件清点：7 条 Pattern 装进同一根管道 ==")
    print("""
正式 Pattern 集（顺序 = 推荐顺序，第 3 节给出顺序说明）：
  1 merge_adjacent_transposes       D65  T(T(x)) -> T_r(x) / 透传
  2 merge_adjacent_reshapes         D66  R(R(x)) -> R(x, 外层目标)
  3 eliminate_transparent_reshape   D66  R(x)=同shape -> x
  4 eliminate_noop_cast             D67  cast 同类型 -> x
  5 fold_transpose_into_constant    D68  T(Const) -> Const'
  6 fuse_add_relu                   D51  relu(add(a,b)) -> fused(a,b)
  7 push_transpose_through_elementwise  D68  T(E(x)) -> E(T(x))
先逐条最小用例验证没装坏：""")

    def one(pattern, build, expect_kinds) -> None:
        g = build()
        before = g.kinds_seq()
        ok = pattern(g)
        _, errs = g.infer_shapes()
        check(f"零件-{pattern.__name__}",
              ok and not errs and g.kinds_seq() == expect_kinds,
              f"{before} -> {g.kinds_seq()}")

    one(merge_adjacent_transposes, lambda: _g_t_t(), ("transpose",))
    one(merge_adjacent_reshapes, lambda: _g_r_r(), ("reshape",))
    one(eliminate_transparent_reshape, lambda: _g_r_same(), ())
    one(eliminate_noop_cast, lambda: _g_cast(), ("relu",))
    one(fold_transpose_into_constant, lambda: _g_fold(), ("relu",))
    one(fuse_add_relu, lambda: _g_fuse(), ("fused_add_relu",))
    one(push_transpose_through_elementwise, lambda: _g_push(),
        ("transpose", "relu"))

    # 数值抽查：每条 Pattern 改写后数值不变
    for name, build in [("T合并", _g_t_t), ("R合并", _g_r_r),
                        ("透明R", _g_r_same), ("Cast", _g_cast),
                        ("折常量", _g_fold), ("融合", _g_fuse),
                        ("传播", _g_push)]:
        g0 = build()
        g1 = build()
        pattern_map = {"T合并": merge_adjacent_transposes,
                       "R合并": merge_adjacent_reshapes,
                       "透明R": eliminate_transparent_reshape,
                       "Cast": eliminate_noop_cast,
                       "折常量": fold_transpose_into_constant,
                       "融合": fuse_add_relu,
                       "传播": push_transpose_through_elementwise}
        pattern_map[name](g1)
        ok, msg = graphs_equal_num(g0, g1)
        check(f"零件-{name} 数值不变", ok, msg)

    # --------------------------------------------------------
    hr("== 2. 多步组合用例：10-op 混合链 -> 稳定 IR ==")

    g0 = build_mixed_chain()
    print("改写前（10 op：2 arg + 8 计算）：")
    print(g0.render())
    print(f"\nop 统计：{op_stats(g0)}")

    g = g0.copy()
    rounds, verdict = run_passes(g, RECOMMENDED_PATTERNS)
    print(f"\n推荐顺序跑完：{rounds} 轮，verdict={verdict}")
    print("改写后（稳定 IR）：")
    print(g.render())
    print(f"\nop 统计：{op_stats(g)}")

    check("混合链-verdict 是 fixpoint", verdict == "fixpoint",
          f"{rounds} 轮")
    check("混合链-总 op 10 -> 4（含 2 个 arg；计算 op 8 -> 2）",
          g.n_all() == 4 and g.n_ops() == 2,
          f"实际 {g.n_all()}（计算 {g.n_ops()}）")
    check("混合链-转置 2 -> 1（卡在 fused 上，传播白名单不认 fused）",
          g.count_kind("transpose") == 1)
    check("混合链-cast 1 -> 0", g.count_kind("cast") == 0)
    check("混合链-reshape 2 -> 0", g.count_kind("reshape") == 0)
    check("混合链-fused 0 -> 1", g.count_kind("fused_add_relu") == 1)
    ok, msg = graphs_equal_num(g0, g)
    check("混合链-数值逐位相等", ok, msg)

    # 稳定三条件
    h1 = g.state_hash()
    rounds2, verdict2 = run_passes(g, RECOMMENDED_PATTERNS)
    check("稳定条件1-二次运行零轮次（幂等）",
          rounds2 == 0 and verdict2 == "fixpoint", f"{rounds2} 轮")
    check("稳定条件2-状态哈希不变", g.state_hash() == h1)
    check("稳定条件3-数值仍逐位相等", graphs_equal_num(g0, g)[0])

    print("\n结论：混合链的 5 次触发依次是")
    print("  merge_t（r=恒等，透传）→ merge_r → transparent_r → cast → fuse")
    print("  剩下的 1 个转置卡在 fused_add_relu 上：C1 白名单只有 relu/neg/floor。")

    # --------------------------------------------------------
    hr("== 3. 合流 vs 竞争：Pattern 顺序研究 ==")
    print("""
顺序只有两类行为（今天全部实测）：
  合流（confluent）：换顺序只影响轮次，终点相同；
  竞争：换顺序换终点——两个不动点都合法，选谁是 Cost Model（第 11 周）的事。
""")

    # ---- 3a. 合流对：cast 消除 x 融合 ----
    def build_cast_between() -> Graph:
        g = Graph("cast_between")
        x = g.arg((2, 3))
        y = g.arg((2, 3))
        a = g.add(x, y)
        c = g.cast(a, "f32", "f32")     # 卡在 add 与 relu 之间
        r = g.relu(c)
        g.returns = [r]
        return g

    gc1 = build_cast_between()
    r1, _ = run_passes(gc1, [eliminate_noop_cast, fuse_add_relu])
    gc2 = build_cast_between()
    r2, _ = run_passes(gc2, [fuse_add_relu, eliminate_noop_cast])
    check("合流-cast×融合 终点相同（哈希相等）",
          gc1.state_hash() == gc2.state_hash(),
          f"轮次 {r1} vs {r2}，终点 {'相同' if gc1.state_hash() == gc2.state_hash() else '不同'}")
    check("合流-两个终点都是 fused（cast 被消掉）",
          gc1.count_kind("fused_add_relu") == 1
          and gc2.count_kind("fused_add_relu") == 1
          and gc1.count_kind("cast") == 0)
    print(f"  cast 先消：{r1} 轮；融合先试：{r2} 轮——轮次相同，"
          f"因为 run_passes 每轮把 Pattern 集整个试一遍，")
    print("  被挡住的模式下一轮还有机会（一次性管道没有这个机会，见第 6 节）。")

    # ---- 3b. 竞争对：传播 x 融合，争同一个窗口 ----
    def build_window() -> Graph:
        g = Graph("window")
        x = g.arg((2, 3))
        y = g.arg((2, 3))
        a = g.add(x, y)
        r = g.relu(a)                    # <- 传播与融合争夺的窗口
        t = g.transpose(r, (1, 0))       # (3,2)
        g.returns = [t]
        return g

    print("\n竞争现场：z = T( relu( add(x, y) ) )——窗口是那个 relu")
    ord_push = [push_transpose_through_elementwise, fuse_add_relu,
                merge_adjacent_transposes, eliminate_noop_cast]
    ord_fuse = [fuse_add_relu, push_transpose_through_elementwise,
                merge_adjacent_transposes, eliminate_noop_cast]

    gw1 = build_window()
    rr1, vv1 = run_passes(gw1, ord_push)
    print(f"\n顺序A（传播在前）：{rr1} 轮 {vv1}")
    print(gw1.render())
    print(f"  op 统计：{op_stats(gw1)}")

    gw2 = build_window()
    rr2, vv2 = run_passes(gw2, ord_fuse)
    print(f"\n顺序B（融合在前）：{rr2} 轮 {vv2}")
    print(gw2.render())
    print(f"  op 统计：{op_stats(gw2)}")

    check("竞争-两个终点不同（哈希不等）",
          gw1.state_hash() != gw2.state_hash())
    check("竞争-先传播 5 op、先融合 4 op（含 2 个 arg）",
          gw1.n_all() == 5 and gw2.n_all() == 4,
          f"{gw1.n_all()} vs {gw2.n_all()}")
    check("竞争-两边都剩 1 个卡住的转置",
          gw1.count_kind("transpose") == 1
          and gw2.count_kind("transpose") == 1)
    ok1, _ = graphs_equal_num(build_window(), gw1)
    ok2, _ = graphs_equal_num(build_window(), gw2)
    check("竞争-两个不动点数值都对", ok1 and ok2)
    print("\n机制：融合把 relu 吞进 fused_add_relu，传播的白名单（relu/neg/floor）")
    print("认不出 fused；传播把 T 推到 relu 下面，融合的匹配（relu 的输入是 add）")
    print("也断了。谁先用掉这个 relu，谁就关掉另一条路。")
    print("今天 mini 的裁决：融合在前 op 更少（4 < 5）；但若传播有机会让两个转置")
    print("会合（三明治），收益是整段搬运归零——选谁属于 Cost Model（第 11 周）。")

    # ---- 3c. 混合链上的顺序表 ----
    print("\n混合链上的顺序表（同一条 10-op 链，不同 Pattern 顺序）：")
    orders = {
        "推荐(消除->融合->传播)": RECOMMENDED_PATTERNS,
        "传播优先": [push_transpose_through_elementwise,
                    fuse_add_relu, merge_adjacent_transposes,
                    merge_adjacent_reshapes, eliminate_transparent_reshape,
                    eliminate_noop_cast, fold_transpose_into_constant],
        "融合优先": [fuse_add_relu, push_transpose_through_elementwise,
                    merge_adjacent_transposes, merge_adjacent_reshapes,
                    eliminate_transparent_reshape, eliminate_noop_cast,
                    fold_transpose_into_constant],
        "倒序": list(reversed(RECOMMENDED_PATTERNS)),
    }
    results = {}
    for name, pats in orders.items():
        gg = build_mixed_chain()
        rr, vv = run_passes(gg, pats)
        st = op_stats(gg)
        okn, _ = graphs_equal_num(g0, gg)
        results[name] = (rr, vv, st, gg.state_hash()[:8], okn)
        print(f"  {name:<16s} {rr} 轮 {vv:<10s} ops={st['ops']} "
              f"T={st['transpose']} cast={st['cast']} R={st['reshape']} "
              f"fused={st['fused']} hash={gg.state_hash()[:8]} "
              f"数值={'对' if okn else '错'}")
    uniq_hashes = {v[3] for v in results.values()}
    check("顺序表-推荐与倒序终点可以不同（顺序敏感）", len(uniq_hashes) >= 2,
          f"{len(uniq_hashes)} 个不同终点")
    check("顺序表-所有顺序数值都对",
          all(v[4] for v in results.values()))

    # --------------------------------------------------------
    hr("== 4. 意外无限变换：三类现场与驯服 ==")

    # ---- 4a. 先证交换律，再上交换规则 ----
    print("""
交换规则 V(P(x)) -> P(V(x)) 的合法性 = 算子对可交换。
先数值验证（不凭直觉），(relu, neg) 是反例——它不能进交换规则集：""")
    rng = np.random.default_rng(69)
    A = (rng.standard_normal((2, 3, 4)) * 3).astype(np.float32)
    perm3 = (2, 0, 1)

    def np_op(kind, arr):
        if kind == "transpose":
            return np.transpose(arr, perm3)
        if kind == "relu":
            return np.maximum(arr, np.float32(0))
        if kind == "neg":
            return -arr
        if kind == "floor":
            return np.floor(arr)
        raise ValueError(kind)

    pairs = [("transpose", "relu"), ("transpose", "neg"),
             ("transpose", "floor"), ("relu", "floor"), ("relu", "neg")]
    for u, v in pairs:
        lhs = np_op(v, np_op(u, A))       # V(U(x))
        rhs = np_op(u, np_op(v, A))       # U(V(x))
        eq = np.array_equal(lhs, rhs)
        check(f"交换律-{u}×{v} {'可交换' if eq else '不可交换（反例）'}",
              eq if (u, v) != ("relu", "neg") else not eq,
              "" if eq else
              f"A[0,0,1]={A[0, 0, 1]:.2f}: {u}后{v}={lhs[0, 0, 1]:.2f}, "
              f"{v}后{u}={rhs[0, 0, 1]:.2f}")

    # ---- 4b. 现场一：交换规则环 ----
    print("""
现场一（规则环）：三个可交换算子 {T, relu, floor}，每对都配双向交换规则
（共 6 条，优先级 = 列表顺序，first-match-wins）。
链上 3 个算子共 6 种排列——从每个排列出发看调度器的真实轨迹：""")
    swap_rules = []
    for a, b in [("transpose", "relu"), ("transpose", "floor"),
                 ("relu", "floor")]:
        swap_rules.append(lambda g, a=a, b=b: swap_adjacent(g, a, b))
        swap_rules.append(lambda g, a=a, b=b: swap_adjacent(g, b, a))

    def build_chain3(order3) -> Graph:
        g = Graph("chain3_" + "".join(k[0] for k in order3))
        x = g.arg((2, 3, 4))
        cur = x
        for kind in order3:
            if kind == "transpose":
                cur = g.transpose(cur, perm3)
            else:
                cur = g.add_op(kind, [cur])
        g.returns = [cur]
        return g

    from itertools import permutations
    all_osc = True
    nums_ok = True
    first_trace = None
    print("  起点排列              轮次  verdict        轨迹尾部")
    for order3 in permutations(["transpose", "relu", "floor"]):
        gr = build_chain3(order3)
        rr, vv, trace = run_passes_traced(gr, swap_rules, max_rounds=30)
        if first_trace is None:
            first_trace = (order3, rr, vv, trace)
        seqs = [" -> ".join(ks) for ks, _ in trace]
        tail = " ... ".join(seqs[-2:]) if vv == "oscillation" else seqs[-1]
        print(f"  {'->'.join(order3):<20s} {rr:>3d}  {vv:<14s} {tail}")
        if vv != "oscillation":
            all_osc = False
        okn, _ = graphs_equal_num(build_chain3(order3), gr)
        if not okn:
            nums_ok = False
    order3, rr, vv, trace = first_trace
    print(f"\n  第一个起点的完整轨迹（每轮后的算子序列，生产者->消费者）：")
    for i, (ks, _) in enumerate(trace):
        print(f"    轮{i}: {' -> '.join(ks)}")
    check("规则环-6 个起点全部 oscillation（没有可达的不动点）", all_osc)
    check("规则环-每条规则语义正确（振荡中数值始终不变）", nums_ok)
    gr = build_chain3(("floor", "relu", "transpose"))
    rr0, vv0, _ = run_passes_traced(gr, swap_rules, max_rounds=30)
    check("规则环-判定 oscillation（不是 fixpoint）", vv0 == "oscillation",
          f"{rr0} 轮")
    print("\n  每条规则单独存在时都能停（各自到不动点或无事可做）；")
    print("  6 条共存后 6 个排列全部流入环——状态空间只有 6 个状态，")
    print("  每步必有规则可触发（相邻对总能换向），抽屉原理保证必环。")

    # ---- 4c. 现场二：undo 对（fuse / unfuse） ----
    print("""
现场二（undo 对）：fuse_add_relu 与 unfuse_add_relu（后端不支持融合算子时的
物化规则）同场——每条各自都「有用」，合在一起互相撤销：""")

    def build_fuse_case() -> Graph:
        g = Graph("fuse_case")
        x = g.arg((2, 3))
        y = g.arg((2, 3))
        a = g.add(x, y)
        r = g.relu(a)
        g.returns = [r]
        return g

    gu = build_fuse_case()
    rr2, vv2, trace2 = run_passes_traced(
        gu, [fuse_add_relu, unfuse_add_relu], max_rounds=30)
    print(f"  跑了 {rr2} 轮，verdict={vv2}")
    for i, (ks, _) in enumerate(trace2):
        print(f"    轮{i}: {' -> '.join(ks) if ks else '(空)'}")
    check("undo对-判定 oscillation", vv2 == "oscillation", f"{rr2} 轮")
    oku, _ = graphs_equal_num(build_fuse_case(), gu)
    check("undo对-数值仍对", oku)

    # ---- 4d. 现场三：哈希陷阱 ----
    print("""
现场三（哈希陷阱）：同样的 fuse/unfuse 振荡，改用**原始 SSA 名字**做状态哈希
（render 里 %N 只增不减）——结构上早就转圈了，哈希却每次都「新鲜」：""")
    gu2 = build_fuse_case()
    rr3, vv3 = run_passes(gu2, [fuse_add_relu, unfuse_add_relu],
                          max_rounds=40, hash_fn=Graph.raw_hash)
    print(f"  规范化哈希：2 轮检出 oscillation（上面实测 {rr2} 轮）")
    print(f"  原始名哈希：{rr3} 轮，verdict={vv3}（只有 max_rounds 兜底，")
    print(f"             真实编译器里这就是超时 / 死循环的现场）")
    check("哈希陷阱-原始名哈希测不出振荡（只能 max_rounds 兜底）",
          vv3 == "max_rounds", f"{rr3} 轮 {vv3}")

    # ---- 4e. 驯服：单调配度（规范序 + 逆序数每步恰降 1） ----
    print("""
驯服：给交换规则一个**规范序**（transpose < relu < floor，按秩排），
只在「逆序」时交换——这就是冒泡排序，逆序数是良基测度：""")
    canon_hashes = set()
    for perm in permutations(["transpose", "relu", "floor"]):
        g = Graph("sort_" + "".join(p[0] for p in perm))
        x = g.arg((2, 3, 4))
        cur = x
        for kind in perm:
            if kind == "transpose":
                cur = g.transpose(cur, perm3)
            elif kind == "relu":
                cur = g.relu(cur)
            else:
                cur = g.floor(cur)
        g.returns = [cur]
        g0p = g.copy()
        inv0 = inversions(g)
        steps = []
        while canonical_swap(g):
            steps.append(inversions(g))
        rr4, vv4 = run_passes(g, [canonical_swap])
        okn, _ = graphs_equal_num(g0p, g)
        check(f"驯服-起始{'->'.join(perm)} {inv0} 步排好、总逆序 "
              f"{inv0}->0",
              vv4 == "fixpoint" and okn
              and (steps[-1] if steps else 0) == 0
              and len(steps) == inv0,
              f"逆序轨迹 {[inv0] + steps}")
        canon_hashes.add(g.state_hash())
    check("驯服-6 个起点到达同一个规范形（canonical form）",
          len(canon_hashes) == 1, f"{len(canon_hashes)} 个")

    # --------------------------------------------------------
    hr("== 5. 压力对拍：200 组随机混合图 ==")
    print("""
随机图：rank 2~3 起点，链长 4~9，算子从 {transpose, relu, neg, floor,
cast(f32->f32), reshape} 随机抽；30% 的图以 add(x, y) 起头（融合机会），
15% 带 const 起点（常量折叠机会）。每张图断言五条：
数值逐位相等 / fixpoint / 二次运行零轮（幂等）/ op 数不增 / 无振荡。""")

    rng = random.Random(6900)
    N = 200

    def all_shapes(num, rank):
        if num < 1 or rank < 1:
            return []
        if rank == 1:
            return [(num,)] if num >= 1 else []
        out = []
        for d in range(1, num + 1):
            if num % d == 0:
                for sub in all_shapes(num // d, rank - 1):
                    out.append((d,) + sub)
        return out

    shape_pool = {num: {k: all_shapes(num, k) for k in (1, 2, 3)}
                  for num in (6, 24)}

    stats = {"rounds": [], "ops_b": 0, "ops_a": 0, "t_b": 0, "t_a": 0,
             "c_b": 0, "c_a": 0, "r_b": 0, "r_a": 0, "fused": 0}
    all_ok = True

    def random_perm(rank):
        p = list(range(rank))
        rng.shuffle(p)
        return tuple(p)

    for gi in range(N):
        rank = rng.choice([2, 3])
        base_shape = (2, 3) if rank == 2 else (2, 3, 4)
        g = Graph(f"rand{gi}")
        cur = g.arg(base_shape)
        if rng.random() < 0.30:
            other = g.arg(base_shape)
            cur = g.add(cur, other)
        elif rng.random() < 0.15:
            cval = np.arange(numel(base_shape), dtype=np.float32).reshape(
                base_shape) - numel(base_shape) / 2
            cur = g.const(cval)
        shape = base_shape
        for _ in range(rng.randint(4, 9)):
            kind = rng.choice(["transpose", "relu", "neg", "floor",
                               "cast", "reshape", "reshape"])
            if kind == "transpose":
                cur = g.transpose(cur, random_perm(len(shape)))
                shape = t_shape(shape, g.ops[-1].perm)
            elif kind == "cast":
                cur = g.cast(cur, "f32", "f32")
            elif kind == "reshape":
                pool = shape_pool[numel(shape)]
                shape = rng.choice(pool[rng.choice([1, 2, 3])])
                cur = g.reshape(cur, shape)
            else:
                cur = g.add_op(kind, [cur])
        g.returns = [cur]
        _, errs = g.infer_shapes()
        if errs:
            all_ok = False
            print(f"  [图{gi}] Verifier 报错：{errs}")
            continue

        g_before = g.copy()
        sb = op_stats(g)
        rr, vv = run_passes(g, RECOMMENDED_PATTERNS)
        sa = op_stats(g)
        rr_again, _ = run_passes(g, RECOMMENDED_PATTERNS)
        okn, msg = graphs_equal_num(g_before, g, seeds=(0, 1))
        good = (vv == "fixpoint" and okn and rr_again == 0
                and sa["ops"] <= sb["ops"])
        if not good:
            all_ok = False
            print(f"  [图{gi}] 失败：{vv}, 数值={okn}({msg}), "
                  f"二次={rr_again}轮, ops {sb['ops']}->{sa['ops']}")
        stats["rounds"].append(rr)
        stats["ops_b"] += sb["ops"]
        stats["ops_a"] += sa["ops"]
        stats["t_b"] += sb["transpose"]
        stats["t_a"] += sa["transpose"]
        stats["c_b"] += sb["cast"]
        stats["c_a"] += sa["cast"]
        stats["r_b"] += sb["reshape"]
        stats["r_a"] += sa["reshape"]
        stats["fused"] += sa["fused"]

    rs = stats["rounds"]
    print(f"\n  数值等价 + fixpoint + 幂等 + op 不增："
          f"{'200/200' if all_ok else '存在失败'}")
    print(f"  轮次分布：min={min(rs)} 中位={sorted(rs)[len(rs)//2]} "
          f"max={max(rs)}")
    print(f"  计算 op 总数：{stats['ops_b']} -> {stats['ops_a']}"
          f"（消掉 {stats['ops_b'] - stats['ops_a']}，"
          f"{100 * (stats['ops_b'] - stats['ops_a']) / max(stats['ops_b'], 1):.1f}%）")
    print(f"  转置总数：{stats['t_b']} -> {stats['t_a']}；"
          f"cast：{stats['c_b']} -> {stats['c_a']}；"
          f"reshape：{stats['r_b']} -> {stats['r_a']}；"
          f"生成 fused：{stats['fused']}")
    check("压力-200 组全部通过（数值/fixpoint/幂等/op 不增/无振荡）",
          all_ok and len(rs) == N)
    check("压力-轮次有界（max <= 15）", max(rs) <= 15, f"max={max(rs)}")

    # --------------------------------------------------------
    hr("== 6. MLIR 对表：stock 管道的幂等与顺序（本机实测） ==")
    if m is None:
        print("mlir-opt 不可用，本节降级为「未执行」。")
    else:
        # 探针 1：--canonicalize 幂等
        f = HERE / "idem_canon.mlir"
        _, o1 = run_mlir(f, ["--canonicalize"])
        _, o2 = run_mlir(f, ["--canonicalize", "--canonicalize"])
        check("MLIR-探针1 canonicalize 幂等（跑两遍=跑一遍）", o1 == o2,
              f"输出 {'相同' if o1 == o2 else '不同'}")
        print(f"    恒等 tensor.cast 剩余："
              f"{count_lines(o1, 'tensor.cast')}（输入里有 1 个）")

        # 探针 2：--cse 幂等
        f = HERE / "idem_cse.mlir"
        _, o1 = run_mlir(f, ["--cse"])
        _, o2 = run_mlir(f, ["--cse", "--cse"])
        check("MLIR-探针2 cse 幂等", o1 == o2)
        print(f"    linalg.generic 剩余：{count_lines(o1, 'linalg.generic')}"
              f"（输入里有 2 个相同副本）")

        # 探针 3：顺序敏感（arith：常量折叠解锁 CSE）
        f = HERE / "order_arith.mlir"
        _, oa = run_mlir(f, ["--canonicalize", "--cse"])
        _, ob = run_mlir(f, ["--cse", "--canonicalize"])
        _, oc = run_mlir(f, ["--cse", "--canonicalize", "--cse"])
        na, nb, nc = (count_lines(t, "arith.addf") for t in (oa, ob, oc))
        check("MLIR-探针3 顺序敏感：canon->cse = 1 个 addf", na == 1,
              f"实际 {na}")
        check("MLIR-探针3 顺序敏感：cse->canon = 2 个 addf", nb == 2,
              f"实际 {nb}")
        check("MLIR-探针3 补一趟 cse 追平（差的是调度不是能力）", nc == 1,
              f"实际 {nc}")
        print(f"    --canonicalize --cse          -> {na} 个 addf")
        print(f"    --cse --canonicalize          -> {nb} 个 addf")
        print(f"    --cse --canonicalize --cse    -> {nc} 个 addf（追平）")

        # 探针 4：Cast 消除解锁 CSE（linalg：恒等 tensor.cast）
        f = HERE / "order_cast.mlir"
        _, oc1 = run_mlir(f, ["--canonicalize"])
        _, oa2 = run_mlir(f, ["--canonicalize", "--cse"])
        _, ob2 = run_mlir(f, ["--cse", "--canonicalize"])
        n_cast = count_lines(oc1, "tensor.cast")
        ga, gb = (count_lines(t, "linalg.generic") for t in (oa2, ob2))
        check("MLIR-探针4 canonicalize 删除恒等 tensor.cast", n_cast == 0,
              f"剩余 {n_cast}")
        check("MLIR-探针4 canon->cse = 1 个 generic（cast 删掉后双胞胎合并）",
              ga == 1, f"实际 {ga}")
        check("MLIR-探针4 cse->canon = 2 个 generic（先跑时操作数还不同）",
              gb == 2, f"实际 {gb}")
        print(f"    --canonicalize --cse -> {ga} 个 generic；"
              f"--cse --canonicalize -> {gb} 个 generic")

        print("\n  结论：mlir-opt 的 pass 按命令行顺序一次性执行，不会回头；")
        print("  「先造机会的在前，用机会的在后」——顺序是真实编译器的真实决策。")

    # --------------------------------------------------------
    hr("== 7. 汇总 ==")
    print(f"通过 {PASS} 项，失败 {FAIL} 项")
    print("""
今日三问的答案：
  ① 不动点：混合链 5 次触发后停住；稳定 = 幂等 + 哈希不变 + 数值相等，
     200 组随机图全部满足（二次运行零轮次）。
  ② 无限变换：规则环（6 条交换规则转圈）、undo 对（fuse/unfuse）、
     哈希陷阱（原始名哈希漏检）——前两者状态哈希当场抓住，
     驯服靠单调配度（规范序 + 逆序数每步恰降 1，6 个起点同一规范形）。
  ③ 优化顺序：cast×融合 合流（终点相同）；传播×融合 竞争（5 op vs 4 op，
     两个不动点数值都对）；MLIR 实测同款现象（addf 1 vs 2、generic 1 vs 2，
     补一趟能追平）。推荐顺序与理由见 README 第 5 节的 Pass 顺序说明。""")
    return 0 if FAIL == 0 else 1


# ---------- 零件清点用的小图 ----------

def _g_t_t() -> Graph:
    g = Graph("t_t")
    x = g.arg((2, 3, 4))
    t1 = g.transpose(x, (1, 2, 0))          # (3,4,2)
    t2 = g.transpose(t1, (1, 2, 0))         # (4,2,3)
    g.returns = [t2]                        # r = (2,0,1) ≠ 恒等 → 仍 1 个转置
    return g


def _g_r_r() -> Graph:
    g = Graph("r_r")
    x = g.arg((2, 3))
    r1 = g.reshape(x, (6,))
    r2 = g.reshape(r1, (3, 2))
    g.returns = [r2]
    return g


def _g_r_same() -> Graph:
    g = Graph("r_same")
    x = g.arg((2, 3))
    r = g.reshape(x, (2, 3))
    g.returns = [r]
    return g


def _g_cast() -> Graph:
    g = Graph("cast")
    x = g.arg((2, 3))
    c = g.cast(x, "f32", "f32")
    r = g.relu(c)
    g.returns = [r]
    return g


def _g_fold() -> Graph:
    g = Graph("fold")
    c = g.const([[1.0, -2.0, 3.0], [-4.0, 5.0, -6.0]])
    t = g.transpose(c, (1, 0))
    r = g.relu(t)
    g.returns = [r]
    return g


def _g_fuse() -> Graph:
    g = Graph("fuse")
    x = g.arg((2, 3))
    y = g.arg((2, 3))
    a = g.add(x, y)
    r = g.relu(a)
    g.returns = [r]
    return g


def _g_push() -> Graph:
    g = Graph("push")
    x = g.arg((2, 3))
    r = g.relu(x)
    t = g.transpose(r, (1, 0))
    g.returns = [t]
    return g


if __name__ == "__main__":
    raise SystemExit(main())
