#!/usr/bin/env python3
"""layout_prop_lab.py —— 第 68 天（Layout 转换传播）主实验。

今天的核心：把 Layout 转换（mini 里就是 Transpose）「穿过」逐元素算子，
向生产者方向移动，让它去和别的转换相遇——相邻才能合并（Day 65），
互逆才能相消，推到常量边上能折叠成编译期值。

手工推导（第 1 节现场证明）：
    T_p(Relu(x)) == Relu(T_p(x))
    依据只有一条：逐位置不变性 Relu(A)[idx] = relu(A[idx])。

受限 Pattern（第 2 节）：
    push_transpose_through_elementwise：
      T(E(x)) -> E(T(x))，当且仅当
      C1  E ∈ 逐元素白名单（relu / neg）
      C2  T 是 E 结果的唯一使用者（否则 E 会被复制而不是被穿过）

收益来源（第 3 节，三明治）：
    T_p(Relu(T_q(x))) --传播--> Relu(T_p(T_q(x))) --合并--> Relu(T_r(x))
    r[i] = q[p[i]]（Day 65 组合方向：内层 q 先作用）；r 为恒等时整体相消。

语义约束说明（第 4 节，今日产出）：
    能穿：relu / neg（逐位置不变）；add 合法但要两侧同 perm（收益另算）；
    不能穿：reduce_sum（需 axis 重映射 k' = p^-1(k)）、reshape（位置重新线性化，
    同 shape 也可能错值——附反例）、conv/matmul（跨位置加权混合）；
    唯一使用者被违反 → 复制算子的劣化；双向规则同时在场 → 振荡（Day 69 预告）。

MLIR 对表（第 6 节，本机 LLVM 18.1.8 实测）：
    --canonicalize 不把 linalg.transpose 穿过逐元素 linalg.generic；
    互逆三明治 T(ReLU(T^-1(x))) 原样保留 3 个 op；
    --convert-linalg-to-loops 后三明治 = 6 层 scf.for + 3 行 load + 3 行 store
    （每个元素搬 3 遍），相消后只剩 ReLU = 2 层 for + 1 行 load + 1 行 store；
    --tosa-layerwise-constant-fold 会把 tosa.transpose(常量) 折成转置后的
    tosa.const——「推到常量边上」这条收益路径在真实编译器里存在。

运行：python3 layout_prop_lab.py   （在 code/ 目录下）
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
# 排列工具（Day 64/65 约定的直接复用）
# ============================================================

def valid_perm(p) -> bool:
    return sorted(p) == list(range(len(p)))


def inv_perm(p) -> tuple:
    """逆排列：q[p[i]] = i。"""
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
# ============================================================

@dataclass
class Op:
    kind: str                       # arg/const/transpose/relu/neg/add/reduce_sum/reshape
    inputs: list = field(default_factory=list)
    name: str = ""
    perm: tuple = ()                # transpose
    value: np.ndarray | None = None  # const
    shape: tuple = ()               # arg
    axis: int = -1                  # reduce_sum（keepdims=True）
    new_shape: tuple = ()           # reshape


ELEMENTWISE_WHITELIST = ("relu", "neg")
NOT_PROPAGATABLE = ("reduce_sum", "reshape", "add", "arg", "const", "transpose")


class Graph:
    def __init__(self, name: str):
        self.name = name
        self.ops: list[Op] = []
        self.returns: list[str] = []
        self.arg_shapes: list[tuple] = []   # 构图时按序记录，供 eval 生成输入
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

    def add(self, a: str, b: str) -> str:
        return self.add_op("add", [a, b])

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
        """谁在用这个结果：op 输入引用 + return 引用。"""
        u = [op for op in self.ops if name in op.inputs]
        if name in self.returns:
            u.append("return")
        return u

    def count_kind(self, kind: str) -> int:
        return sum(1 for op in self.ops if op.kind == kind)

    def copy(self) -> "Graph":
        g = Graph(self.name)
        g.ops = [Op(kind=op.kind, inputs=list(op.inputs), name=op.name,
                    perm=op.perm, value=op.value, shape=op.shape,
                    axis=op.axis, new_shape=op.new_shape) for op in self.ops]
        g.returns = list(self.returns)
        g.arg_shapes = list(self.arg_shapes)
        g._n = self._n
        return g

    # ---------- Verifier（四关里今天用到的三关） ----------

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
            elif op.kind in ("relu", "neg"):
                s = shapes[op.inputs[0]]
            elif op.kind == "add":
                a, b = shapes[op.inputs[0]], shapes[op.inputs[1]]
                if a != b:
                    errs.append(f"[V2] {op.name} add 两操作数 shape 不一致 "
                                f"{a} vs {b}")
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
        """按 arg_shapes 生成确定性随机输入（f32），执行整张图。"""
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
            elif op.kind == "add":
                v = vals[op.inputs[0]] + vals[op.inputs[1]]
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
            elif op.kind == "relu":
                body = f"{op.name} = relu {ins}"
            elif op.kind == "neg":
                body = f"{op.name} = neg {ins}"
            elif op.kind == "add":
                body = f"{op.name} = add {ins}"
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
        """规范化结构哈希：op 按 topo 位置重命名为 #k，用于振荡检测。"""
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
            elif op.kind == "const":
                extra = ("|val=" +
                         hashlib.md5(np.ascontiguousarray(op.value)
                                     .tobytes()).hexdigest()[:8])
            parts.append(f"{canon[op.name]}={op.kind}({ins}){extra}"
                         f"->{shapes.get(op.name)}")
        rets = ",".join(canon.get(r, r) for r in self.returns)
        return hashlib.md5((";".join(parts) + "|" + rets).encode()).hexdigest()

    # ---------- 死代码消除 ----------

    def dce(self) -> int:
        live = set(self.returns)
        for op in reversed(self.ops):
            if op.name in live:
                live.update(op.inputs)
        before = len(self.ops)
        self.ops = [op for op in self.ops if op.name in live]
        return before - len(self.ops)


# ============================================================
# Pattern（今天的正式产出）＋ 反面教材
# ============================================================

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


def push_transpose_through_elementwise(
        g: Graph, whitelist=ELEMENTWISE_WHITELIST,
        respect_unique: bool = True) -> bool:
    """受限 Pattern（今日主产出）：

    T(E(x)) -> E(T(x))     E ∈ 逐元素白名单（relu/neg）

    约束：
      C1 语义门：E 逐位置不变（白名单）；
      C2 图门：T 是 E 结果的唯一使用者——否则 E 会被复制一份（劣化），
         穿过就不再是「移动」而是「增殖」。
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


def push_transpose_through_elementwise_unchecked(g: Graph) -> bool:
    """反面教材：忽略 C2 唯一使用者约束的版本。

    结果不会算错（数值仍等价），但 E 被复制：算子变多、搬运变多——
    「合法但劣化」，这就是 C2 存在的理由。
    """
    return push_transpose_through_elementwise(g, respect_unique=False)


def merge_adjacent_transposes(g: Graph) -> bool:
    """Day 65 的一般合并（今天作为传播的「会合点」复用）：

    T_p2(T_p1(x)) -> T_r(x)，r[i] = p1[p2[i]]（内层 p1 先作用）。
    r 为恒等时直接透传 x（互逆消除是一般合并的特例）。
    """
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


def fold_transpose_into_constant(g: Graph) -> bool:
    """T(Const) -> Const'：转置折进常量（权重离线转置，运行时零开销）。

    真实世界的对照：mlir-opt --tosa-layerwise-constant-fold 对
    tosa.transpose(常量) 做的正是这件事（第 6 节实测）。
    """
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


def push_transpose_up_through_elementwise(
        g: Graph, whitelist=ELEMENTWISE_WHITELIST) -> bool:
    """反方向规则（仅用于第 4 节的振荡演示，不在正式 Pattern 集里）：

    E(T(x)) -> T(E(x))   向消费者方向推。
    单独存在时也能到不动点；和向下推的规则同时在场时会互相 undo——
    这就是 Day 69「意外无限变换」的最小现场。
    """
    for idx, e in enumerate(g.ops):
        if e.kind not in whitelist or len(e.inputs) != 1:
            continue
        t = g.by_name(e.inputs[0])
        if t is None or t.kind != "transpose" or len(t.inputs) != 1:
            continue
        if g.users(t.name) != [e]:
            continue
        e2 = Op(e.kind, [t.inputs[0]], name=g._new())
        t2 = Op("transpose", [e2.name], perm=t.perm, name=g._new())
        _splice(g, idx, [e2, t2], {e.name: t2.name})
        g.dce()
        return True
    return False


def run_passes(g: Graph, patterns, max_rounds: int = 40
               ) -> tuple[int, str]:
    """跑到不动点；用规范化状态哈希检测振荡。"""
    seen = {g.state_hash()}
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
        h = g.state_hash()
        if h in seen:
            return rounds, "oscillation"
        seen.add(h)
    return rounds, "max_rounds"


# ---------- 收益记账 ----------

def traffic_report(g: Graph) -> dict:
    """物理搬运视角：一个实体化转置 = 读 numel + 写 numel。

    逐元素算子也搬数据，但那是「有用功」；这里只统计转置的纯搬运。
    """
    shapes, _ = g.infer_shapes()
    n_t = g.count_kind("transpose")
    moves = sum(2 * numel(shapes[t.inputs[0]]) for t in g.ops
                if t.kind == "transpose")
    return {"transposes": n_t, "element_moves": moves,
            "bytes": moves * 4}


def graphs_equal_num(a: Graph, b: Graph, seeds=(0, 1, 2)) -> tuple[bool, str]:
    """数值对拍：两张图在多组随机输入下输出完全一致。"""
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


def count_in_text(text: str, pat: str) -> int:
    return sum(1 for line in text.splitlines() if pat in line)


# ============================================================
# 主实验
# ============================================================

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

    # 贯穿例子（延续本周的 B 家族，值肉眼可核对）
    B = np.array([[-1.5, 0.5, 2.0],
                  [3.5, -0.5, -2.5]], dtype=np.float32)
    B3 = ((np.arange(24, dtype=np.float32) - 12.0) / 4.0).reshape(2, 3, 4)
    print(f"\n贯穿例子 B(2,3)  = {B.tolist()}")
    print(f"           B3(2,3,4) = (arange(24)-12)/4，含正负值")

    # --------------------------------------------------------
    hr("== 1. 手工推导：Transpose 穿过逐元素算子（T(E(x)) ≡ E(T(x))） ==")

    print("""
推导（只用一条性质）：
  约定（Day 64）：T_p(A) 的第 i 根轴 = A 的第 p[i] 根轴；
                 取值时索引按轴对应关系跟着换（记 q = p^-1）：
                 T_p(A)[i0..in-1] = A[i_{q(0)}..i_{q(n-1)}]
  左边：T_p(Relu(x))[idx] = Relu(x)[idx∘q] = relu( x[idx∘q] )
                              ~~~~~~~~~~~~ 逐元素：Relu(A)[任何位置] = relu(A[该位置])
  右边：Relu(T_p(x))[idx]  = relu( T_p(x)[idx] ) = relu( x[idx∘q] )
  两边逐位置相等。∎
  唯一用到的性质：E(A)[idx] = e(A[idx])——「逐位置不变性」。
  谁没有这条性质，谁就不能被穿过（第 4 节的反例都从这查）。""")

    # 逐位置追踪表：2D 例子，肉眼核对
    p = (1, 0)
    lhs = np.transpose(np.maximum(B, 0), p)
    rhs = np.maximum(np.transpose(B, p), 0)
    print(f"\n贯穿例子（B(2,3)，p=(1,0)）：")
    print(f"  T(Relu(B)) =\n{lhs}")
    print(f"  Relu(T(B)) =\n{rhs}")
    check("推导-数值对拍 T(Relu(B)) == Relu(T(B))",
          np.array_equal(lhs, rhs))
    check("推导-数值对拍 T(Neg(B)) == Neg(T(B))",
          np.array_equal(np.transpose(-B, p), -np.transpose(B, p)))

    # 位置追踪表（3 个代表位置，均在 T 后的 (3,2) 域内）
    q = inv_perm(p)
    print(f"\n  位置追踪（q = p^-1 = {q}）：")
    spots = [(0, 1), (2, 0), (2, 1)]
    for pos in spots:
        src = tuple(pos[q[k]] for k in range(len(pos)))
        print(f"    输出位置 {pos} ← 两边都取 relu(B{src})"
              f" = relu({B[src]}) = {max(B[src], 0.0):.1f}")
    l_ok = all(lhs[pos] == max(B[tuple(pos[q[k]] for k in range(2))], 0.0)
               for pos in spots)
    check("推导-追踪表 3 个位置与矩阵值一致", l_ok)

    # 随机对拍（10 组 shape×perm）
    rng = np.random.default_rng(68)
    ok_n = 0
    for trial in range(10):
        rank = int(rng.integers(2, 5))
        shape = tuple(int(rng.integers(2, 5)) for _ in range(rank))
        perm = tuple(rng.permutation(rank))
        x = (rng.standard_normal(shape) * 3).astype(np.float32)
        a = np.transpose(np.maximum(x, 0), perm)
        b = np.maximum(np.transpose(x, perm), 0)
        if np.array_equal(a, b):
            ok_n += 1
    check("推导-随机对拍 10 组（rank 2~4 随机 perm）", ok_n == 10,
          f"{ok_n}/10")

    # --------------------------------------------------------
    hr("== 2. 受限 Pattern：push_transpose_through_elementwise ==")

    g = Graph("simple")
    x = g.arg((2, 3))
    r = g.relu(x)
    t = g.transpose(r, (1, 0))
    g.returns = [t]
    print("改写前：")
    print(g.render())
    fired = push_transpose_through_elementwise(g)
    print("\n改写后（T(Relu(x)) -> Relu(T(x))）：")
    print(g.render())
    check("Pattern-改写发生", fired)
    check("Pattern-转置仍在图里（移动而非删除）",
          g.count_kind("transpose") == 1)
    check("Pattern-relu 仍在图里", g.count_kind("relu") == 1)
    # 与原始图对拍（重新构造同一张图作为基准）：
    g0 = Graph("simple")
    x0 = g0.arg((2, 3))
    r0 = g0.relu(x0)
    t0 = g0.transpose(r0, (1, 0))
    g0.returns = [t0]
    ok, d = graphs_equal_num(g0, g)
    check("Pattern-数值等价（3 组随机输入，逐位相等）", ok, d)

    # C2 门：多使用者时拒绝
    g2 = Graph("multi_user")
    x2 = g2.arg((2, 3))
    r2 = g2.relu(x2)
    t2 = g2.transpose(r2, (1, 0))
    n2 = g2.neg(r2)          # 第二个使用者：neg 也要 r2
    g2.returns = [t2, n2]
    fired2 = push_transpose_through_elementwise(g2)
    check("Pattern-C2 多使用者时拒绝触发", fired2 is False)
    check("Pattern-C2 图保持原样（3 个计算 op）",
          len([o for o in g2.ops if o.kind != "arg"]) == 3)

    # 反面教材：无视 C2 强推 —— 合法但劣化
    g3 = g2.copy()
    before_ops = len([o for o in g3.ops if o.kind != "arg"])
    before_t = g3.count_kind("transpose")
    fired3 = push_transpose_through_elementwise_unchecked(g3)
    after_ops = len([o for o in g3.ops if o.kind != "arg"])
    after_t = g3.count_kind("transpose")
    ok3, d3 = graphs_equal_num(g2, g3, seeds=(0, 1, 2))
    print(f"\n反面教材（无视 C2 强推多使用者图）：")
    print(g3.render())
    check("反面教材-强推后数值仍等价（不算错）", ok3, d3)
    check("反面教材-但算子增殖（劣化）",
          after_ops > before_ops,
          f"计算 op {before_ops} -> {after_ops}，转置 {before_t} -> {after_t}"
          f"（relu 被复制，转置并没少）")

    # --------------------------------------------------------
    hr("== 3. 收益从哪来：三明治的传播 → 合并 → 相消 ==")

    def sandwich(name, shape, p_out, p_in, inner="relu"):
        g = Graph(name)
        x = g.arg(shape)
        w = g.transpose(x, p_in)
        e = g.relu(w) if inner == "relu" else g.neg(w)
        z = g.transpose(e, p_out)
        g.returns = [z]
        return g

    # 3a. 完全相消：p_out = p_in = (1,0)（自逆）
    gs = sandwich("sandwich_full", (2, 3), (1, 0), (1, 0))
    gs0 = gs.copy()
    print("三明治（互逆，语义合计 = Relu(x)）改写前：")
    print(gs.render())
    rounds, status = run_passes(gs, [push_transpose_through_elementwise,
                                     merge_adjacent_transposes,
                                     fold_transpose_into_constant])
    print(f"\n跑 PassManager：{rounds} 轮，状态 = {status}")
    print(gs.render())
    check("三明治-互逆整体相消（转置 2 -> 0）",
          gs.count_kind("transpose") == 0)
    check("三明治-最终只剩 1 个 relu", gs.count_kind("relu") == 1)
    ok, d = graphs_equal_num(gs0, gs)
    check("三明治-数值等价", ok, d)

    tb, ta = traffic_report(gs0), traffic_report(gs)
    n_el = numel((2, 3))
    print(f"\n收益记账（numel = {n_el}，f32）：")
    print(f"  改写前：转置 {tb['transposes']} 个，纯搬运 "
          f"{tb['element_moves']} 次元素移动 = {tb['bytes']} B")
    print(f"  改写后：转置 {ta['transposes']} 个，纯搬运 "
          f"{ta['element_moves']} 次元素移动 = {ta['bytes']} B")
    check("三明治-纯搬运降为 0", ta["element_moves"] == 0)

    # 3b. 部分收益：3D 非自逆（p 相同但不互逆，r != 恒等）
    gs2 = sandwich("sandwich_partial", (2, 3, 4), (1, 2, 0), (1, 2, 0))
    gs20 = gs2.copy()
    rounds2, status2 = run_passes(
        gs2, [push_transpose_through_elementwise,
              merge_adjacent_transposes,
              fold_transpose_into_constant])
    r_expect = tuple(np.transpose(np.zeros((2, 3, 4)), (1, 2, 0)).shape)
    print(f"\n部分收益（3D，p_out = p_in = (1,2,0)，r = q[p[i]] ≠ 恒等）："
          f"{rounds2} 轮，{status2}")
    print(gs2.render())
    check("三明治-部分合并（转置 2 -> 1）",
          gs2.count_kind("transpose") == 1)
    ok, d = graphs_equal_num(gs20, gs2)
    check("三明治-部分合并数值等价", ok, d)

    # 3c. 链式：多个逐元素算子夹多层转置（传播的递推能力）
    # p = (1,2,0) 是 3-循环，阶 = 3：p³ = 恒等（Day 65 的 perm_order）
    # 三个同向转置被逐元素算子隔开，合计仍为恒等 —— 传播能让它们全部会合
    g4 = Graph("chain")
    x4 = g4.arg((2, 3, 4))
    c = g4.transpose(x4, (1, 2, 0))
    c = g4.relu(c)
    c = g4.transpose(c, (1, 2, 0))
    c = g4.neg(c)
    c = g4.transpose(c, (1, 2, 0))
    g4.returns = [c]
    g40 = g4.copy()
    rounds4, status4 = run_passes(
        g4, [push_transpose_through_elementwise,
             merge_adjacent_transposes,
             fold_transpose_into_constant])
    print(f"\n链式（3 个同向转置夹 2 个逐元素，p³ = 恒等）：{rounds4} 轮，{status4}")
    print(g4.render())
    ok, d = graphs_equal_num(g40, g4)
    check("链式-3 转置 3 逐元素，最终转置 0 个",
          g4.count_kind("transpose") == 0, f"剩余 {g4.count_kind('transpose')}")
    check("链式-逐元素算子全保留且顺序不变（relu 1 + neg 1）",
          g4.count_kind("relu") == 1 and g4.count_kind("neg") == 1)
    check("链式-数值等价", ok, d)

    # 3d. 推到常量边上：T(Relu(Const)) -> Relu(T(Const)) -> Relu(Const')
    g5 = Graph("const_push")
    w5 = g5.const(B3)
    r5 = g5.relu(w5)
    t5 = g5.transpose(r5, (1, 2, 0))
    g5.returns = [t5]
    g50 = g5.copy()
    rounds5, status5 = run_passes(
        g5, [push_transpose_through_elementwise,
             merge_adjacent_transposes,
             fold_transpose_into_constant])
    print(f"\n推到常量边上（权重离线转置）：{rounds5} 轮，{status5}")
    print(g5.render())
    check("常量-转置折进常量（运行时转置 0 个）",
          g5.count_kind("transpose") == 0)
    ok, d = graphs_equal_num(g50, g5)
    check("常量-数值等价", ok, d)

    # 3e. 规模换算（明确标注：理论计算，非测量）
    nchw = (1, 3, 224, 224)
    n_bytes = numel(nchw) * 4
    print(f"\n规模换算（理论计算，非测量）："
          f"NCHW {nchw} f32，numel = {numel(nchw)}，单张 {n_bytes} B")
    print(f"  一个实体化转置 = 读+写 = {2 * n_bytes} B ≈ "
          f"{2 * n_bytes / 1024 / 1024:.2f} MiB 纯搬运")
    print(f"  三明治两个转置 = {4 * n_bytes} B ≈ "
          f"{4 * n_bytes / 1024 / 1024:.2f} MiB —— 相消后为 0")

    # --------------------------------------------------------
    hr("== 4. 语义约束说明（今日产出）：能穿 / 不能穿 / 什么时候不许动 ==")

    print("""
判据只有一条：E(A)[idx] = e(A[idx])（逐位置不变性）。
  ✓ relu / neg        逐位置同函数 —— 直接穿
  △ add              合法但要「两侧同 perm」：T(Add(a,b)) = Add(T(a),T(b))，
                       第二个操作数要新转置（常量可折，张量要算账）
  ✗ reduce_sum        跨位置求和：正确推法要把 axis 重映射为 p^-1(k)，
                       同 axis 硬推会被 shape 检查抓住（下面实测）
  ✗ reshape           位置重新线性化：即使 shape 对得上，值也可能错（反例）
  ✗ conv / matmul     跨位置加权混合（本周不展开，同属「不能穿」家族）""")

    # 4a. reduce：同 axis 硬推 → shape 被抓住
    # 注意选 p[k] != k 的排列：p 固定 k 时重映射恰好与原 axis 重合，
    # 是「碰巧正确」的边界（shape 也对得上），不能当反例
    gr = Graph("reduce_naive")
    xr = gr.arg((2, 3, 4))
    yr = gr.reduce_sum(xr, axis=0)            # -> (1,3,4)
    zr = gr.transpose(yr, (1, 0, 2))          # -> (3,1,4)
    gr.returns = [zr]
    fired_r = push_transpose_through_elementwise(gr)
    check("约束-reduce 不在白名单，Pattern 拒绝", fired_r is False)

    # 「如果硬写一个同 axis 的推法」：T(x) 后同 axis reduce，shape 当场对不上
    xt = np.transpose(np.zeros((2, 3, 4)), (1, 0, 2))     # (3,2,4)
    naive_shape = list(xt.shape)
    naive_shape[0] = 1                                     # (1,2,4)
    correct = np.transpose(np.zeros((2, 3, 4)).sum(axis=0, keepdims=True),
                           (1, 0, 2)).shape                # (3,1,4)
    print(f"\n  reduce 反例（axis=0，p=(1,0,2)，p[0]=1 ≠ 0=k）：")
    print(f"    正确结果 shape {correct}")
    print(f"    同 axis 硬推 shape {tuple(naive_shape)} —— shape 检查当场抓住")
    print(f"    （若 p 恰好固定 k，如 p=(0,2,1)，重映射 p^-1(k)=k 与原 axis "
          f"重合，是「碰巧正确」的边界，不能证明合法性）")
    check("约束-reduce 同 axis 硬推 shape 不一致",
          tuple(naive_shape) != correct)

    # 正确的重映射公式（数值证明）：k' = p^-1(k)
    rng4 = np.random.default_rng(7)
    ok_rem = True
    for trial in range(20):
        rank = int(rng4.integers(2, 5))
        shape = tuple(int(rng4.integers(2, 5)) for _ in range(rank))
        perm = tuple(rng4.permutation(rank))
        k = int(rng4.integers(0, rank))
        x = rng4.standard_normal(shape).astype(np.float32)
        lhs = np.transpose(x.sum(axis=k, keepdims=True, dtype=np.float32),
                           perm)
        rhs = np.transpose(x, perm).sum(axis=inv_perm(perm)[k], keepdims=True,
                                        dtype=np.float32)
        if not (lhs.shape == rhs.shape and np.array_equal(lhs, rhs)):
            ok_rem = False
    check("约束-reduce 正确重映射公式 T(reduce(x,k)) == "
          "reduce(T(x), p^-1(k))（20 组随机）", ok_rem)

    # 4b. reshape：同 shape 也可能错值
    xrr = np.array([[1., 2., 3.], [4., 5., 6.]], dtype=np.float32)
    lhs_rr = np.transpose(xrr.reshape(3, 2), (1, 0))
    rhs_rr = np.transpose(xrr, (1, 0)).reshape(2, 3)
    print(f"\n  reshape 反例（x 2x3 -> reshape 3x2 -> T；对比 T -> reshape 2x3）：")
    print(f"    左边 =\n{lhs_rr}")
    print(f"    右边 =\n{rhs_rr}")
    check("约束-reshape 同 shape 不同值（位置重新线性化）",
          lhs_rr.shape == rhs_rr.shape and not np.array_equal(lhs_rr, rhs_rr))

    # 4c. add：合法但要看第二个操作数的账
    ga = Graph("add_const")
    xa = ga.arg((2, 3))
    wb = ga.const(np.array([[1., -2., 3.], [-4., 5., -6.]], np.float32))
    aa = ga.add(xa, wb)
    ta = ga.transpose(aa, (1, 0))
    ga.returns = [ta]
    lhs_a = np.transpose(xrr + np.array([[1., -2., 3.], [-4., 5., -6.]]),
                         (1, 0))
    rhs_a = (np.transpose(xrr, (1, 0)) +
             np.transpose(np.array([[1., -2., 3.], [-4., 5., -6.]]), (1, 0)))
    check("约束-add 数学上可穿（两侧同 perm）",
          np.array_equal(lhs_a, rhs_a))
    print("\n  add 的账：另一个操作数是常量 → 转置可折进常量（免费）；"
          "是张量 → 要新增一个转置（第 5 节选做挑战再算）")

    # 4d. 方向门：双向规则同时在场 → 振荡（Day 69 预告）
    go = Graph("oscillation")
    xo = go.arg((2, 3))
    ro = go.relu(xo)
    to = go.transpose(ro, (1, 0))
    go.returns = [to]
    rounds_o, status_o = run_passes(
        go, [push_transpose_through_elementwise,
             push_transpose_up_through_elementwise], max_rounds=40)
    print(f"\n  方向门（同图双向规则）：{rounds_o} 轮后状态 = {status_o}"
          f"（状态哈希回到已见过的值——互相 undo，永不收敛）")
    check("约束-双向规则振荡被检测", status_o == "oscillation")

    go2 = Graph("one_direction")
    xo2 = go2.arg((2, 3))
    ro2 = go2.relu(xo2)
    to2 = go2.transpose(ro2, (1, 0))
    go2.returns = [to2]
    rounds_o2, status_o2 = run_passes(
        go2, [push_transpose_through_elementwise,
              push_transpose_up_through_elementwise])
    # 单独向下已在第 2 节验证收敛；这里验证「只保留一个方向」的集合
    go3 = Graph("down_only")
    xo3 = go3.arg((2, 3))
    ro3 = go3.relu(xo3)
    to3 = go3.transpose(ro3, (1, 0))
    go3.returns = [to3]
    rounds_o3, status_o3 = run_passes(go3, [push_transpose_through_elementwise])
    check("约束-单方向规则正常收敛",
          status_o3 == "fixpoint", f"{rounds_o3} 轮")

    # --------------------------------------------------------
    hr("== 5. 压力对拍：300 组随机图（数值 + 收益 + 不动点） ==")

    rng5 = np.random.default_rng(20261112)
    n_cases = 300
    n_eq = n_mono = n_fix = n_term = 0
    t_before_total = t_after_total = 0
    worst_gain = 10**9
    for case in range(n_cases):
        g = Graph(f"rand{case}")
        rank = int(rng5.integers(2, 5))
        shape = tuple(int(rng5.integers(2, 5)) for _ in range(rank))
        if rng5.random() < 0.25:
            cur = g.const((rng5.standard_normal(shape) * 3).astype(np.float32))
        else:
            cur = g.arg(shape)
        n_ops = int(rng5.integers(4, 10))
        for _ in range(n_ops):
            u = rng5.random()
            if u < 0.45:
                cur = g.transpose(cur, tuple(rng5.permutation(rank)))
            elif u < 0.70:
                cur = g.relu(cur)
            elif u < 0.90:
                cur = g.neg(cur)
            else:
                cur = g.relu(cur)
        g.returns = [cur]
        g_orig = g.copy()
        tb = traffic_report(g)
        rounds_c, status_c = run_passes(
            g, [push_transpose_through_elementwise,
                merge_adjacent_transposes,
                fold_transpose_into_constant])
        ta = traffic_report(g)
        ok, _ = graphs_equal_num(g_orig, g, seeds=(case % 7,))
        if ok:
            n_eq += 1
        if ta["transposes"] <= tb["transposes"]:
            n_mono += 1
        worst_gain = min(worst_gain,
                         tb["transposes"] - ta["transposes"])
        # 不动点：再跑一遍应当 0 轮
        r2, s2 = run_passes(g, [push_transpose_through_elementwise,
                                merge_adjacent_transposes,
                                fold_transpose_into_constant])
        if r2 == 0 and s2 == "fixpoint":
            n_fix += 1
        if status_c in ("fixpoint",):
            n_term += 1
        t_before_total += tb["transposes"]
        t_after_total += ta["transposes"]
    print(f"随机图 {n_cases} 组（rank 2~4，链长 4~9，25% 常量起点）：")
    print(f"  数值等价        {n_eq}/{n_cases}")
    print(f"  转置数不增      {n_mono}/{n_cases}")
    print(f"  二次运行不动点  {n_fix}/{n_cases}")
    print(f"  全部收敛        {n_term}/{n_cases}")
    print(f"  转置总数        {t_before_total} -> {t_after_total}"
          f"（消掉 {t_before_total - t_after_total} 个，"
          f"{100 * (t_before_total - t_after_total) / max(t_before_total, 1):.1f}%）")
    check("压力-数值等价 300/300", n_eq == n_cases, f"{n_eq}/{n_cases}")
    check("压力-转置数单调不增 300/300", n_mono == n_cases, f"{n_mono}/{n_cases}")
    check("压力-二次运行到达不动点 300/300", n_fix == n_cases, f"{n_fix}/{n_cases}")
    check("压力-全部收敛（无振荡无超轮数）", n_term == n_cases, f"{n_term}/{n_cases}")

    # --------------------------------------------------------
    hr("== 6. MLIR 对表：stock 管道的真实裁决 ==")

    m = find_mlir_opt()
    if m is None:
        print("mlir-opt 不可用，本节降级跳过")
    else:
        probes = [
            ("push_probe.mlir", ["--canonicalize"], "linalg",
             "canonicalize 会不会把 transpose 穿过逐元素 generic"),
            ("sandwich_probe.mlir", ["--canonicalize"], "linalg",
             "互逆三明治会不会被相消"),
            ("sandwich_memref.mlir", ["--convert-linalg-to-loops"], "loops",
             "三明治降循环后的物理搬运行数"),
            ("sandwich_after.mlir", ["--convert-linalg-to-loops"], "loops",
             "相消后（只剩 ReLU）的循环面貌"),
            ("tosa_const_probe.mlir", ["--tosa-layerwise-constant-fold"],
             "tosa", "tosa 会不会把 transpose(常量) 折掉"),
        ]
        for fname, args, kind, question in probes:
            f = HERE / fname
            rc, text = run_mlir(f, args)
            (OUT / (f"{f.stem}.{kind}.txt")).write_text(text)
            if kind == "linalg":
                n_t = count_in_text(text, "linalg.transpose")
                n_g = count_in_text(text, "linalg.generic")
                print(f"\n[{fname}] {question}")
                print(f"  mlir-opt {fname} {' '.join(args)} -> exit={rc}")
                print(f"  linalg.transpose {n_t} 个，linalg.generic {n_g} 个"
                      f"（完整输出存 outputs/{f.stem}.{kind}.txt）")
                if fname == "push_probe.mlir":
                    check("MLIR-canonicalize 不推（generic+transpose 原样）",
                          rc == 0 and n_t == 1 and n_g == 1)
                else:
                    check("MLIR-互逆三明治原样保留 3 个 op",
                          rc == 0 and n_t == 2 and n_g == 1)
            elif kind == "loops":
                n_for = count_in_text(text, "scf.for")
                n_load = count_in_text(text, "memref.load")
                n_store = count_in_text(text, "memref.store")
                print(f"\n[{fname}] {question}")
                print(f"  mlir-opt {fname} {' '.join(args)} -> exit={rc}")
                print(f"  scf.for {n_for} 层，memref.load {n_load} 行，"
                      f"memref.store {n_store} 行")
                if fname == "sandwich_memref.mlir":
                    check("MLIR-三明治降循环：6 for / 3 load / 3 store",
                          rc == 0 and n_for == 6 and n_load == 3 and
                          n_store == 3,
                          f"每元素被搬 3 遍（numel=6：18 读+写）")
                    lo = (n_load, n_store)
                else:
                    check("MLIR-相消后：2 for / 1 load / 1 store",
                          rc == 0 and n_for == 2 and n_load == 1 and
                          n_store == 1, "每元素只搬 1 遍")
            else:
                n_t = count_in_text(text, "tosa.transpose")
                n_c = count_in_text(text, "tosa.const")
                has_val = "dense<[[1.000000e+00, -4.000000e+00]" in text
                print(f"\n[{fname}] {question}")
                print(f"  mlir-opt {fname} {' '.join(args)} -> exit={rc}")
                print(f"  tosa.transpose {n_t} 个，tosa.const {n_c} 个，"
                      f"常量已转置：{has_val}")
                check("MLIR-tosa 把 transpose(常量) 折成转置后的 const",
                      rc == 0 and n_t == 0 and has_val,
                      "推到常量边上的收益路径在真实编译器里存在")

    # --------------------------------------------------------
    hr("== 汇总 ==")
    print(f"PASS {PASS} / FAIL {FAIL}")
    if FAIL:
        print("存在失败项，请检查上文 [FAIL] 行")
        return 1
    print("""
今日产出对照：
  1. Layout 传播 Pattern：push_transpose_through_elementwise（C1 白名单
     + C2 唯一使用者，向生产者单方向）
  2. 语义约束说明：逐位置不变性判据 + 能穿/不能穿裁决表 + 三道门
     （语义门/唯一使用者门/方向门）+ reduce 重映射与 reshape 反例
  3. 收益记账：三明治 2->0（互逆）/ 2->1（一般合并）/ 常量折叠 1->0，
     以及 MLIR loops 侧 3 load + 3 store vs 1 load + 1 store 的实测对照""")
    return 0


if __name__ == "__main__":
    sys.exit(main())
