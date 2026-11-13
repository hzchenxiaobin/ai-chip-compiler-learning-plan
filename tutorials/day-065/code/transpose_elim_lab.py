#!/usr/bin/env python3
"""transpose_elim_lab.py —— 第 65 天主实验：连续 Transpose 消除。

任务（来自学习计划第 65 天）：
  学习：两次 Permutation 的组合，什么时候等价于恒等或一次 Transpose；
  实践：先实现互逆 Transpose 消除，再实现一般情况下的 Permutation 合并；
  产出：两个 RewritePattern 和组合测试（测试在 test_transpose_elim.py）。

贯穿例子（延续第 64 天的 B）：
  B(2,3,4) = arange(24)，strides (12, 4, 1)
  3-循环 p = (1, 2, 0)：B --p--> (3,4,2) --p--> (4,2,3) --p--> (2,3,4)
  互逆对：p = (1,2,0)，inv(p) = (2,0,1)

mini 的约定（第 64 天钉死，与 numpy / LLVM 18 linalg.transpose 一致）：
  out_shape[i] = in_shape[perm[i]]     （输出第 i 维拽输入第 perm[i] 维）

组合方向（今天的核心推导，全部经 numpy 对拍验证）：
  B = T_p(A)：B.shape[i] = A.shape[p[i]]
  C = T_q(B)：C.shape[i] = B.shape[q[i]] = A.shape[p[q[i]]]
  所以 C = T_r(A)，r = compose(p, q)，r[i] = p[q[i]]     ← 内层先作用
  互逆消除：q == inv(p) ⟺ r == 恒等（排列群 ab = e ⟺ b = a⁻¹）
  3-循环 (1,2,0)：p² = inv(p) = (2,0,1)，p³ = 恒等——三连链两轮 Pattern 消除

两个 RewritePattern：
  P1 CancelInverseTranspose：T_q(T_p(x)) 且 q == inv(p) 且中间值唯一使用者 → x
  P2 MergeConsecutiveTranspose：T_q(T_p(x)) 且中间值唯一使用者 →
     r = compose(p, q)；r == 恒等则整体消除为 x，否则合并为一个 T_r(x)
  P1 在数学上是 P2 的特例——单独实现它是因为：先易后难；且互逆判据
  不需要构造新排列就能短路。

MLIR 侧的真实事实（本机 LLVM 18.1.8 实测）：
  连续两个 linalg.transpose（哪怕互逆对，语义合计为恒等）交给
  --canonicalize：IR 原样返回——linalg.transpose 没有注册这类
  canonicalization pattern。--convert-linalg-to-loops 后是 6 层循环、
  numel×2 次 load/store——「什么都没做」的转置对把数据搬了两遍。
  这条优化在 stock 管道里不存在，要自己写——mini 的两个 Pattern
  就是练习场。

用法：python3 transpose_elim_lab.py   （在 code/ 目录下；输出另存 outputs/）
"""

from __future__ import annotations

import itertools
import platform
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


# ============================================================
# 排列代数（第 64 天的语义 + 今天的组合）——供 lab 与 test 共用
# ============================================================

def infer_transposed_shape(shape, perm):
    """Shape 推导：out_shape[i] = in_shape[perm[i]]。前提：perm 已过 Verifier。"""
    return tuple(int(shape[p]) for p in perm)


def inverse_perm(perm):
    """逆排列 inv：inv[perm[i]] = i。撤销一次转置靠它，不是「再转一次」。"""
    inv = [0] * len(perm)
    for i, p in enumerate(perm):
        inv[p] = i
    return tuple(inv)


def compose_perm(p, q):
    """组合排列：C = T_q(T_p(A)) 时 C.shape[i] = A.shape[p[q[i]]]。

    r = compose(p, q)，r[i] = p[q[i]]——内层 p 先作用，所以 p 在外圈。
    方向是今天的第一个陷阱：写成 q[p[i]] 在 2D（对合）测试永远发现不了。
    """
    return tuple(int(p[int(q_i)]) for q_i in q)


def is_identity(perm) -> bool:
    return tuple(perm) == tuple(range(len(perm)))


def perm_order(perm):
    """排列的阶：最少自乘几次回到恒等（第 64 天已测：(1,0)→2，(1,2,0)→3）。"""
    cur, k = tuple(perm), 1
    ident = tuple(range(len(perm)))
    while cur != ident:
        cur = compose_perm(cur, perm)
        k += 1
        if k > len(perm) + 1:
            return -1
    return k


def verify_transpose(in_shape, perm, result_shape=None) -> list[str]:
    """四关 Verifier（第 64 天同款）：E1 长度 → E2 值域 → E3 双射 → E4 形状。

    今天它有双重身份：入口守门（构造图之前），以及合并 Pattern 的
    「产物自检」——Pattern 2 合并出新排列后必须再过一遍。
    """
    errs: list[str] = []
    rank = len(in_shape)
    perm = tuple(int(p) for p in perm)

    if len(perm) != rank:
        errs.append(f"[E1] 排列长度 {len(perm)} 与输入秩 {rank} 不相等")
        return errs
    for i, p in enumerate(perm):
        if not (0 <= p < rank):
            errs.append(f"[E2] 排列第 {i} 项 {p} 超出 0..{rank - 1}")
            return errs
    if sorted(perm) != list(range(rank)):
        errs.append(f"[E3] 排列 {list(perm)} 不是双射")
        return errs
    if result_shape is not None:
        result_shape = tuple(int(d) for d in result_shape)
        want = infer_transposed_shape(in_shape, perm)
        if tuple(result_shape) != want:
            for i, (w, r) in enumerate(zip(want, result_shape)):
                if w != r:
                    errs.append(
                        f"[E4] 结果第 {i} 维应为 {w}（= 输入第 {perm[i]} 维），"
                        f"实际写的 {r}")
    return errs


# ============================================================
# mini 图 IR：Operation + 图 + 使用计数 + 数值执行
# ============================================================

@dataclass
class MiniTransposeOp:
    """mini.transpose Operation（第 64 天同款文本格式，去掉解析器）。"""
    result_id: str
    input_id: str
    in_shape: tuple
    dtype: str = "f32"
    perm: tuple = ()

    @property
    def result_shape(self) -> tuple:
        return infer_transposed_shape(self.in_shape, self.perm)

    def print_ir(self) -> str:
        perm_s = "[" + ", ".join(str(p) for p in self.perm) + "]"
        in_t = "x".join(str(d) for d in self.in_shape) + "x" + self.dtype
        out_t = "x".join(str(d) for d in self.result_shape) + "x" + self.dtype
        return (f"{self.result_id} = mini.transpose {self.input_id} "
                f"permutation = {perm_s} : ({in_t}) -> ({out_t})")


@dataclass
class MiniGraph:
    """极简计算图：ops 顺序列表 + 返回值列表（返回值也算使用者）。"""
    ops: list = field(default_factory=list)
    returns: list = field(default_factory=list)   # 返回的 value id
    inputs: dict = field(default_factory=dict)    # value id -> ndarray

    def use_count(self, value_id: str) -> int:
        n = sum(1 for op in self.ops if op.input_id == value_id)
        if value_id in self.returns:
            n += 1
        return n

    def users_of(self, value_id: str) -> list:
        users = [op for op in self.ops if op.input_id == value_id]
        if value_id in self.returns:
            users.append("func.return")
        return users

    def verify(self) -> list[str]:
        errs = []
        known = set(self.inputs.keys())
        for op in self.ops:
            if op.input_id not in known:
                errs.append(f"[G1] {op.result_id} 的输入 {op.input_id} 无定义")
                continue
            errs += verify_transpose(op.in_shape, op.perm, op.result_shape)
            known.add(op.result_id)
        for r in self.returns:
            if r not in known:
                errs.append(f"[G2] 返回值 {r} 无定义")
        return errs

    def print_ir(self) -> str:
        lines = []
        for vid, arr in self.inputs.items():
            lines.append(f"  {vid} : shape {arr.shape} "
                         f"（func 入参，值可由 numpy 提供可见性）")
        for op in self.ops:
            lines.append(f"  {op.print_ir()}")
        lines.append(f"  func.return {', '.join(self.returns)}")
        return "\n".join(lines)

    def replace_all_uses(self, old: str, new: str) -> None:
        """把 old 的所有使用换成 new（ops 的输入 + 返回值）。"""
        for op in self.ops:
            if op.input_id == old:
                op.input_id = new
        self.returns = [new if r == old else r for r in self.returns]

    def erase(self, result_id: str) -> None:
        self.ops = [op for op in self.ops if op.result_id != result_id]

    def eval(self) -> tuple:
        """数值执行：按 ops 顺序求值，返回 returns 对应的 ndarray 元组。"""
        env = dict(self.inputs)
        for op in self.ops:
            env[op.result_id] = np.transpose(env[op.input_id], op.perm)
        return tuple(env[r] for r in self.returns)


def chain_of(graph: MiniGraph):
    """生成所有「连续转置链」候选 (inner, outer)：

    outer.input_id == inner.result_id。是否允许消除由 Pattern 的
    合法性检查决定（中间值唯一使用者）——这里只负责找到链。
    """
    for inner in list(graph.ops):
        for outer in list(graph.ops):
            if outer.input_id == inner.result_id:
                yield inner, outer


# ============================================================
# 两个 RewritePattern（今天的核心产出）
# ============================================================

def cancel_inverse_transpose(graph: MiniGraph) -> bool:
    """Pattern 1：互逆 Transpose 消除。

    T_q(T_p(x)) 且 q == inv(p) 且中间值唯一使用者 → 整体替换为 x。
    合法性边界：
      - q == inv(p) 保证 C 的值与 x 逐元素相等（组合为恒等排列）；
      - 中间值唯一使用者保证删除 inner 不剥夺其他消费方；
      - 返回值也是使用者（被 return 的中间结果不能删）。
    """
    for inner, outer in chain_of(graph):
        if outer.perm != inverse_perm(inner.perm):
            continue
        if graph.use_count(inner.result_id) != 1:
            continue          # 中间值有别的消费者（或被 return）→ 保守拒绝
        graph.replace_all_uses(outer.result_id, inner.input_id)
        graph.erase(outer.result_id)
        graph.erase(inner.result_id)
        return True           # 本轮只做一次，留给 PassManager 迭代
    return False


def merge_consecutive_transpose(graph: MiniGraph) -> bool:
    """Pattern 2：一般情况下的 Permutation 合并。

    T_q(T_p(x)) 且中间值唯一使用者 →
      r = compose(p, q)（r[i] = p[q[i]]，内层先作用）
      r == 恒等  → 整体消除为 x（互逆是它的特例）
      r != 恒等  → 替换为一个 T_r(x)（两次转置 → 一次）
    合法性边界：同 Pattern 1——中间值唯一使用者；合并产物的排列、
    形状必须能再次通过四关 Verifier（构造时已由推导保证）。
    """
    for inner, outer in chain_of(graph):
        if graph.use_count(inner.result_id) != 1:
            continue
        r = compose_perm(inner.perm, outer.perm)
        if is_identity(r):
            graph.replace_all_uses(outer.result_id, inner.input_id)
            graph.erase(outer.result_id)
            graph.erase(inner.result_id)
        else:
            merged = MiniTransposeOp(
                result_id=outer.result_id, input_id=inner.input_id,
                in_shape=inner.in_shape, dtype=inner.dtype, perm=r)
            if verify_transpose(merged.in_shape, merged.perm,
                                merged.result_shape) != []:
                continue      # 产物非法就不动（防御，正常构造不出非法）
            outer.perm, outer.input_id, outer.in_shape = (
                merged.perm, merged.input_id, merged.in_shape)
            graph.erase(inner.result_id)
        return True
    return False


def run_passes(graph: MiniGraph, patterns, trace=None, max_rounds=10):
    """PassManager：迭代跑到不动点，返回 (轮数, 应用次数)。

    三连链需要多轮：T T T →（合并）→ T T →（再合并/消除）→ T 或 x。
    max_rounds 是防御上限——Pattern 都单调减 op 数，理论上很快收敛。
    """
    rounds, applied = 0, 0
    while True:
        changed = False
        for name, pat in patterns:
            if pat(graph):
                changed = True
                applied += 1
                if trace is not None:
                    trace.append(f"round {rounds + 1}: {name} 应用后的 IR")
        rounds += 1
        if trace is not None and changed:
            trace.append(graph.print_ir())
        if not changed or rounds >= max_rounds:
            return rounds, applied


# ============================================================
# MLIR 侧：linalg.transpose 链的真实裁决
# ============================================================

def find_mlir_opt() -> str | None:
    for cand in (shutil.which("mlir-opt"), "/usr/lib/llvm-18/bin/mlir-opt"):
        if cand and Path(cand).exists() and Path(cand).stat().st_mode & 0o111:
            return cand
    return None


def linalg_chain_ir() -> str:
    """连续两个互逆 linalg.transpose（语义合计恒等）的合法 IR。

    in 2x3x4 --[1,2,0]--> 3x4x2 --[2,0,1]--> 2x3x4（回到原形状）
    """
    return """module {
  func.func @chain(%in: memref<2x3x4xf32>) -> memref<2x3x4xf32> {
    %0 = memref.alloc() : memref<3x4x2xf32>
    linalg.transpose ins(%in: memref<2x3x4xf32>) outs(%0: memref<3x4x2xf32>) permutation = [1, 2, 0]
    %1 = memref.alloc() : memref<2x3x4xf32>
    linalg.transpose ins(%0: memref<3x4x2xf32>) outs(%1: memref<2x3x4xf32>) permutation = [2, 0, 1]
    return %1 : memref<2x3x4xf32>
  }
}
"""


def run_mlir_opt(ir_text: str, extra_args: list[str]) -> tuple[int, str]:
    exe = find_mlir_opt()
    if exe is None:
        return -1, "mlir-opt 不可用"
    p = subprocess.run([exe, *extra_args, "-"], input=ir_text,
                       capture_output=True, text=True)
    return p.returncode, p.stdout


# ============================================================
# 主实验
# ============================================================

def main() -> int:
    rng = random.Random(65)

    print("=" * 66)
    print("第 65 天主实验：连续 Transpose 消除（互逆消除 + Permutation 合并）")
    print("=" * 66)

    print("\n== 0. 环境与主线 ==")
    print(f"python  {platform.python_version()}")
    print(f"numpy   {np.__version__}")
    print(f"arch    {platform.machine()}")
    mlir_opt = find_mlir_opt()
    if mlir_opt:
        ver = subprocess.run([mlir_opt, "--version"], capture_output=True,
                             text=True).stdout.splitlines()
        print(f"mlir-opt {mlir_opt}（{(ver or ['?'])[0]}）")
    else:
        print("mlir-opt 不可用")
    print("主线：连续两个（或一串）转置什么时候能消除/合并——组合排列的数学、"
          "两个 RewritePattern、多使用者边界、数值对拍与 MLIR 实测对照。")

    B = np.arange(24, dtype=np.float32).reshape(2, 3, 4)   # 贯穿例子（第 64 天同款）

    # ---- 1. 现场一：语义合计为恒等的转置对，stock 管道不动它 ----
    print("\n== 1. 现场一：一对互逆转置（合计零语义），mlir-opt 实测 ==")
    print("IR：in 2x3x4 --[1,2,0]--> 3x4x2 --[2,0,1]--> 2x3x4（回到原形状）")
    if mlir_opt:
        code, canon = run_mlir_opt(linalg_chain_ir(), ["--canonicalize"])
        n_trans = canon.count("linalg.transpose")
        print(f"  --canonicalize 退出码 {code}，输出里 linalg.transpose 仍剩 "
              f"{n_trans} 个（输入是 2 个）")
        (OUT / "transpose_chain.canon.mlir").write_text(canon,
                                                        encoding="utf-8")
        check("互逆转置对经 --canonicalize 后原样保留（LLVM 18 无此规则）",
              code == 0 and n_trans == 2)

        code_l, loops = run_mlir_opt(linalg_chain_ir(),
                                     ["--convert-linalg-to-loops"])
        (OUT / "transpose_chain.loops.mlir").write_text(loops,
                                                        encoding="utf-8")
        n_for = loops.count("scf.for")
        n_load = loops.count("memref.load")
        n_store = loops.count("memref.store")
        numel = 2 * 3 * 4
        print(f"  --convert-linalg-to-loops：{n_for} 层循环、{n_load} 行 load、"
              f"{n_store} 行 store——每行在循环里执行 {numel} 次，"
              f"共 {n_load * numel} 读 + {n_store * numel} 写（数据搬两遍）")
        check("不消除的代价：6 层循环、2 行 load、2 行 store（numel×2 次访存）",
              code_l == 0 and n_for == 6 and n_load == 2 and n_store == 2)

        single = """module {
  func.func @one(%in: memref<2x3x4xf32>) -> memref<3x4x2xf32> {
    %0 = memref.alloc() : memref<3x4x2xf32>
    linalg.transpose ins(%in: memref<2x3x4xf32>) outs(%0: memref<3x4x2xf32>) permutation = [1, 2, 0]
    return %0 : memref<3x4x2xf32>
  }
}
"""
        _, loops1 = run_mlir_opt(single, ["--convert-linalg-to-loops"])
        print(f"  对照：单个转置降级后是 {loops1.count('scf.for')} 层循环、"
              f"{loops1.count('memref.load')} 行 load（执行 24 次）——"
              f"一对互逆转置白付一整次搬运")
        check("单个转置降级为 3 层循环、1 行 load/store",
              loops1.count("scf.for") == 3
              and loops1.count("memref.load") == 1)
    else:
        print("  mlir-opt 不可用，现场一降级为「预期输出，尚未执行」")

    # ---- 2. 组合数学：方向、互逆、3-循环 ----
    print("\n== 2. 组合排列：方向钉死 + 全量对拍 ==")
    p = (1, 2, 0)
    print(f"推导：C = T_q(T_p(A))，C.shape[i] = A.shape[p[q[i]]] "
          f"→ r = compose(p, q)，r[i] = p[q[i]]")
    print(f"  p = {p}，inv(p) = {inverse_perm(p)}，"
          f"compose(p, inv(p)) = {compose_perm(p, inverse_perm(p))}（恒等）")
    print(f"  compose(p, p) = {compose_perm(p, p)}（= inv(p)，3-循环的 p²）")
    print(f"  B(2,3,4) 经 p 三连：{infer_transposed_shape((2,3,4), p)} → "
          f"{infer_transposed_shape(infer_transposed_shape((2,3,4), p), p)} → "
          f"{infer_transposed_shape(infer_transposed_shape(infer_transposed_shape((2,3,4), p), p), p)}"
          "（回到原形状）")

    ok = True
    for p_ in itertools.permutations(range(3)):
        for q_ in itertools.permutations(range(3)):
            lhs = np.transpose(np.transpose(B, p_), q_)
            rhs = np.transpose(B, compose_perm(p_, q_))
            if not np.array_equal(lhs, rhs):
                ok = False
    check("36 对 3 元排列全量对拍：T_q∘T_p == T_{compose(p,q)}", ok)

    ok = all(np.array_equal(np.transpose(np.transpose(B, p_), q_), B)
             == is_identity(compose_perm(p_, q_))
             for p_ in itertools.permutations(range(3))
             for q_ in itertools.permutations(range(3)))
    check("回到原样 ⟺ compose(p,q) 是恒等（⟺ q == inv(p)），36 对验证",
          ok)

    order_ok = True
    for p_ in itertools.permutations(range(4)):
        cur = tuple(range(4))                 # 从恒等（原样）出发
        for _ in range(perm_order(p_)):       # 连做「阶」次同款转置
            cur = compose_perm(cur, p_)
        if cur != tuple(range(4)):
            order_ok = False
    check("4 元全排列（24 个）：T_p 连做『阶』次回到恒等（k 次自乘 = 恒等）",
          order_ok)

    # ---- 3. mini 图 + 两个 Pattern 的现场 ----
    print("\n== 3. mini 侧：两个 RewritePattern 的现场 ==")
    print("Pattern 1（互逆消除）：T_q(T_p(x))，q == inv(p)，中间值唯一使用者 → x")
    print("Pattern 2（一般合并）：T_q(T_p(x))，中间值唯一使用者 → "
          "T_{compose(p,q)}(x)（合成恒等则消除）")

    # 场景 A：互逆对（2D，对合——两个方向碰巧都成立）
    print("\n场景 A（2D 互逆对，T T → x）：")
    gA = MiniGraph(
        ops=[MiniTransposeOp("%t", "%in", (2, 3), "f32", (1, 0)),
             MiniTransposeOp("%c", "%t", (3, 2), "f32", (1, 0))],
        returns=["%c"],
        inputs={"%in": np.arange(1, 7, dtype=np.float32).reshape(2, 3)})
    print(gA.print_ir())
    before = gA.eval()
    rounds, applied = run_passes(gA, [
        ("P1 cancel_inverse_transpose", cancel_inverse_transpose),
        ("P2 merge_consecutive_transpose", merge_consecutive_transpose)])
    print(f"→ PassManager {rounds} 轮、应用 {applied} 次：")
    print(gA.print_ir())
    check("A：2D 互逆对整体消除（op 数 2→0）", len(gA.ops) == 0
          and np.array_equal(gA.eval()[0], before[0]))

    # 场景 B：互逆对（3D，非对合——q 必须真的等于 inv(p)）
    print("\n场景 B（3D 互逆对，p=(1,2,0)，q=(2,0,1)=inv(p)，→ x）：")
    gB = MiniGraph(
        ops=[MiniTransposeOp("%t", "%in", (2, 3, 4), "f32", (1, 2, 0)),
             MiniTransposeOp("%c", "%t", (3, 4, 2), "f32", (2, 0, 1))],
        returns=["%c"],
        inputs={"%in": B})
    print(gB.print_ir())
    before = gB.eval()
    trace = [gB.print_ir()]
    rounds, applied = run_passes(gB, [
        ("P1 cancel_inverse_transpose", cancel_inverse_transpose),
        ("P2 merge_consecutive_transpose", merge_consecutive_transpose)],
        trace=trace)
    print(f"→ PassManager {rounds} 轮、应用 {applied} 次：")
    print(gB.print_ir())
    check("B：3D 互逆对整体消除（op 数 2→0）且数值不变",
          len(gB.ops) == 0 and np.array_equal(gB.eval()[0], before[0]))

    # 场景 C：一般对（3D，合并成一个转置）
    print("\n场景 C（3D 一般对，p=q=(1,2,0)，合并 → T_{p²}=T_{inv(p)} 单转置）：")
    gC = MiniGraph(
        ops=[MiniTransposeOp("%t", "%in", (2, 3, 4), "f32", (1, 2, 0)),
             MiniTransposeOp("%c", "%t", (3, 4, 2), "f32", (1, 2, 0))],
        returns=["%c"],
        inputs={"%in": B})
    print(gC.print_ir())
    before = gC.eval()
    rounds, applied = run_passes(gC, [
        ("P1 cancel_inverse_transpose", cancel_inverse_transpose),
        ("P2 merge_consecutive_transpose", merge_consecutive_transpose)])
    print(f"→ PassManager {rounds} 轮、应用 {applied} 次：")
    print(gC.print_ir())
    check("C：一般对合并为单转置（op 数 2→1，perm=(2,0,1)）",
          len(gC.ops) == 1 and gC.ops[0].perm == (2, 0, 1)
          and gC.ops[0].input_id == "%in"
          and np.array_equal(gC.eval()[0], before[0]))

    # 场景 D：3-循环三连链（两轮 Pattern：先合并再消除）
    print("\n场景 D（3-循环三连链 T T T，阶 3 → 两轮 → x）：")
    gD = MiniGraph(
        ops=[MiniTransposeOp("%t1", "%in", (2, 3, 4), "f32", (1, 2, 0)),
             MiniTransposeOp("%t2", "%t1", (3, 4, 2), "f32", (1, 2, 0)),
             MiniTransposeOp("%c", "%t2", (4, 2, 3), "f32", (1, 2, 0))],
        returns=["%c"],
        inputs={"%in": B})
    print(gD.print_ir())
    before = gD.eval()
    trace = [gD.print_ir()]
    rounds, applied = run_passes(gD, [
        ("P1 cancel_inverse_transpose", cancel_inverse_transpose),
        ("P2 merge_consecutive_transpose", merge_consecutive_transpose)],
        trace=trace)
    print(f"PassManager {rounds} 轮、应用 {applied} 次（轮间 IR 存 trace）：")
    print(gD.print_ir())
    check("D：三连链两轮消除为 x（op 数 3→0）且数值不变",
          len(gD.ops) == 0 and np.array_equal(gD.eval()[0], before[0]))

    # 场景 E：多使用者反例（保守拒绝）
    print("\n场景 E（多使用者反例：%t 被两个消费方用 → Pattern 拒绝，图不动）：")
    gE = MiniGraph(
        ops=[MiniTransposeOp("%t", "%in", (2, 3, 4), "f32", (1, 2, 0)),
             MiniTransposeOp("%c", "%t", (3, 4, 2), "f32", (2, 0, 1)),
             MiniTransposeOp("%u", "%t", (3, 4, 2), "f32", (0, 2, 1))],
        returns=["%c", "%u"],
        inputs={"%in": B})
    before = gE.eval()
    rounds, applied = run_passes(gE, [
        ("P1 cancel_inverse_transpose", cancel_inverse_transpose),
        ("P2 merge_consecutive_transpose", merge_consecutive_transpose)])
    print(gE.print_ir())
    print(f"  %t 的使用者数 = {gE.use_count('%t')}（%c、%u 各一）——两个 Pattern 都拒绝")
    check("E：多使用者时图不动（3 个 op 原样）且数值不变",
          len(gE.ops) == 3 and rounds >= 1
          and all(np.array_equal(a, b) for a, b in zip(gE.eval(), before)))
    print("  保守拒绝的理由：删除 %t 会剥夺 %u 的定义；「激进版」可以把 %c "
          "改成直接 T_{compose}(%in) 而 %t 原样保留（选做挑战）")

    # 场景 F：中间值被 return 的反例
    print("\n场景 F（中间值 %t 被 func.return → 也是使用者，拒绝）：")
    gF = MiniGraph(
        ops=[MiniTransposeOp("%t", "%in", (2, 3, 4), "f32", (1, 2, 0)),
             MiniTransposeOp("%c", "%t", (3, 4, 2), "f32", (2, 0, 1))],
        returns=["%c", "%t"],
        inputs={"%in": B})
    before = gF.eval()
    print(gF.print_ir())
    print(f"  %t 的使用者数 = {gF.use_count('%t')}（%c 一个 + func.return 一个）")
    run_passes(gF, [
        ("P1 cancel_inverse_transpose", cancel_inverse_transpose),
        ("P2 merge_consecutive_transpose", merge_consecutive_transpose)])
    check("F：被 return 的中间值同样拒绝（op 数仍 2）",
          len(gF.ops) == 2
          and all(np.array_equal(a, b) for a, b in zip(gF.eval(), before)))

    # ---- 4. 判定表 + 随机压力对拍 ----
    print("\n== 4. 判定表：12 个链式场景，优化前后数值对拍 ==")
    scenes = [
        ("S1  2D TT（对合）",       (2, 3),   [(1, 0), (1, 0)], 0),
        ("S2  2D 恒等对",           (2, 3),   [(0, 1), (1, 0)], 1),
        ("S3  3D 互逆对",           (2, 3, 4), [(1, 2, 0), (2, 0, 1)], 0),
        ("S4  3D 一般对 p=q",       (2, 3, 4), [(1, 2, 0), (1, 2, 0)], 1),
        ("S5  3D 一般对 p≠q",       (2, 3, 4), [(1, 2, 0), (0, 2, 1)], 1),
        ("S6  3D 三连链（阶 3）",   (2, 3, 4), [(1, 2, 0)] * 3, 0),
        ("S7  3D 四连链（阶 3）",   (2, 3, 4), [(1, 2, 0)] * 4, 1),
        ("S8  4D 互逆对",           (2, 3, 4, 5), [(3, 2, 1, 0), (3, 2, 1, 0)], 0),
        ("S9  4D 长链 5 个",        (2, 3, 4, 5), [(1, 2, 3, 0)] * 5, 1),
        ("S10 单转置（无链可配）",  (2, 3),   [(1, 0)], 1),
        ("S11 恒等单转置",          (2, 3),   [(0, 1)], 1),
        ("S12 交错链 4 个",         (2, 3, 4, 5), [(1, 0, 2, 3), (0, 2, 1, 3),
                                                   (2, 1, 0, 3), (3, 0, 1, 2)], 1),
    ]
    print("用例                   输入shape     排列链                    "
          "优化后op数  数值对拍")
    all_ok = True
    for name, shape, perms, expect_ops in scenes:
        x = np.arange(int(np.prod(shape)), dtype=np.float32).reshape(shape)
        cur_shape = tuple(shape)
        ops_ = []
        ids = ["%in"] + [f"%t{i}" for i in range(len(perms))]
        for i, pm in enumerate(perms):
            ops_.append(MiniTransposeOp(ids[i + 1], ids[i], cur_shape,
                                       "f32", pm))
            cur_shape = infer_transposed_shape(cur_shape, pm)
        g = MiniGraph(ops=ops_, returns=[ids[-1]], inputs={"%in": x})
        before = g.eval()
        run_passes(g, [
            ("P1 cancel_inverse_transpose", cancel_inverse_transpose),
            ("P2 merge_consecutive_transpose", merge_consecutive_transpose)])
        after = g.eval()
        ok = (len(g.ops) == expect_ops
              and np.array_equal(after[0], before[0])
              and g.verify() == [])
        all_ok &= ok
        chain_s = " → ".join(str(list(pm)) for pm in perms)
        if len(chain_s) > 34:
            chain_s = chain_s[:31] + "…"
        print(f"{name:<22} {str(shape):>12}  {chain_s:>34}  "
              f"{len(g.ops):>6}      {'ok' if ok else 'MISMATCH'}")
    check(f"判定表 {len(scenes)}/{len(scenes)}：op 数符合预期 + 数值不变 + Verifier 通过",
          all_ok)

    print("\n随机压力对拍（300 组随机链，秩 1..5、链长 1..5）：")
    rand_ok, rand_ops = 0, 0
    for t in range(300):
        rank = rng.randint(1, 5)
        shape = tuple(rng.randint(1, 5) for _ in range(rank))
        L = rng.randint(1, 5)
        perms = []
        cur_shape = shape
        for _ in range(L):
            pm = list(range(rank))
            rng.shuffle(pm)
            perms.append(tuple(pm))
        x = np.arange(int(np.prod(shape)), dtype=np.float32).reshape(shape)
        ids = ["%in"] + [f"%t{i}" for i in range(L)]
        ops_ = []
        cur_shape = shape
        for i, pm in enumerate(perms):
            ops_.append(MiniTransposeOp(ids[i + 1], ids[i], cur_shape,
                                        "f32", pm))
            cur_shape = infer_transposed_shape(cur_shape, pm)
        g = MiniGraph(ops=ops_, returns=[ids[-1]], inputs={"%in": x})
        before = g.eval()
        run_passes(g, [
            ("P1 cancel_inverse_transpose", cancel_inverse_transpose),
            ("P2 merge_consecutive_transpose", merge_consecutive_transpose)])
        after = g.eval()
        rand_ops += len(g.ops)
        if (np.array_equal(after[0], before[0]) and g.verify() == []
                and len(g.ops) <= L):
            rand_ok += 1
    check(f"随机对拍 {rand_ok}/300：数值不变、Verifier 通过、op 数不增",
          rand_ok == 300)
    print(f"  300 组共 {300 * 3} 个初始 op（平均链长 3），优化后剩 {rand_ops} 个"
          f"（{rand_ops / 9:.1f}%）——消除与合并都在干活")

    # ---- 5. 方向反了的错误实现（2D 绿、3D 崩的真实现场） ----
    print("\n== 5. 错误实现现场：组合方向写成 q[p[i]]（2D 测试发现不了）==")
    def wrong_compose(p, q):
        return tuple(q[int(p_i)] for p_i in p)     # 方向反了
    print(f"  p=q=(1,0)（2D 对合）：正确 {compose_perm((1,0),(1,0))}，"
          f"错误 {wrong_compose((1,0),(1,0))}——碰巧都是恒等，2D 全绿")
    w = wrong_compose((1, 2, 0), (0, 2, 1))
    r = compose_perm((1, 2, 0), (0, 2, 1))
    print(f"  p=(1,2,0), q=(0,2,1)（3D）：正确 {r}，错误 {w}")
    want = infer_transposed_shape(
        infer_transposed_shape((2, 3, 4), (1, 2, 0)), (0, 2, 1))
    got_right = infer_transposed_shape((2, 3, 4), r)
    got_wrong = infer_transposed_shape((2, 3, 4), w)
    print(f"  链的真实终点 {want}；正确合并 {got_right}；错误合并 {got_wrong}"
          f"（{ '撞上了' if got_wrong == want else '对不上' }）")
    check("错误方向在 3D 链上撞出错误 shape（正确方向推导与链终点一致）",
          got_right == want and got_wrong != want)
    lhs = np.transpose(np.transpose(B, (1, 2, 0)), (0, 2, 1))
    check("数值终审：T_q∘T_p 的值 == T_{compose(p,q)} 的值（正确方向）",
          np.array_equal(lhs, np.transpose(B, r)))

    # ---- 6. 汇总 ----
    print()
    print("=" * 66)
    print(f"汇总：PASS {PASS} / FAIL {FAIL}")
    print("=" * 66)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
