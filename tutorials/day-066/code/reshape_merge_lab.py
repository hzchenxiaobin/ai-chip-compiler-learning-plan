#!/usr/bin/env python3
"""reshape_merge_lab.py —— 第 66 天主实验：连续 Reshape 合并。

任务（来自学习计划第 66 天）：
  学习：Reshape 链、元素数量和中间使用者约束；
  实践：实现 Reshape(Reshape(x)) → Reshape(x)，保留必要中间结果；
  产出：Reshape 合并 Pattern、正例和多使用者反例（测试在 test_reshape_merge.py）。

贯穿例子（延续第 64/65 天的 B）：
  B(2,3,4) = arange(24)（值肉眼可核对）
  朴素链：B --reshape--> (6,4) --reshape--> (24,)
  绕回链：B --reshape--> (6,4) --reshape--> (2,3,4)（链尾 == 起点 → 恒等）

今天的核心数学（比昨天简单，但边界更微妙）：
  C 序 reshape 不改变元素的线性先后顺序，只改「每行放几个」——重新画分隔线；
  所以 Reshape(Reshape(x, s1), s2) == Reshape(x, s2) 对任何 numel 守恒的 s1 成立：
    判据里 s1 完全消失，也没有排列组合的方向陷阱；
  单个 reshape 的合法性 = 元素数量守恒 prod(in) == prod(out)（三关 Verifier 的 E2）；
  链尾形状 == 输入形状 → 恒等，可整体消除（P1 是 P2 合成恒等的特例，同昨天）。

合法性边界（今天真正的新东西——「被替换」与「被删除」是两件事）：
  P1 恒等消除 Reshape(x, shape(x)) → x：
    删除的是 op 自身，它的结果被整体替换成输入（两者值相等）；
    replaceAllUses 会把所有使用者改道——所以 P1 不需要唯一使用者检查！
  P2 链合并 Reshape(Reshape(x, s1), s2) → Reshape(x, s2)：
    要删除中间值 %t = Reshape(x, s1)——只有 use_count(%t) == 1 才允许删；
    func.return 也是使用者（被导出的中间结果必须保留）。
  激进版（第 5 节现场）：「改写 outer 直读 %in」永远合法（值相等），
    只有「删除 %t」才有条件——这就是昨天预告的「微妙」。

MLIR 侧的真实事实（本机 LLVM 18.1.8 实测，2026-11-12）：
  ① tensor.reshape 链交给 --canonicalize：IR 原样保留（2 个 reshape 都在）；
  ② tensor.collapse_shape 连链：折叠成单 op，reassociation 组合成 [[0, 1, 2]]；
  ③ tensor.expand_shape 连链：同样折叠成单 op [[0, 1, 2]]；
  ④ expand→collapse 互逆对：整体消除为 return %arg0；
  ⑤ collapse→expand 非互逆（(2,3,4)→(6,4)→(6,2,2)）：原样保留 2 个 op——
    组合成的变换无法用单个 reassociative reshape 表达，stock 管道不重写成 tensor.reshape。
  结论：结构化信息（reassociation 分组）决定 stock 管道里有没有组合规则；
  普通 tensor.reshape 的合并要自己写——mini 的两个 Pattern 就是练习场。

用法：python3 reshape_merge_lab.py   （在 code/ 目录下；输出另存 outputs/）
"""

from __future__ import annotations

import platform
import random
import shutil
import subprocess
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
# Reshape 语义：numel 守恒 + 三关 Verifier
# ============================================================

def numel(shape) -> int:
    """元素数量：所有维度连乘（第 9 周 Shape 语义的老朋友）。"""
    n = 1
    for d in shape:
        n *= int(d)
    return n


def verify_reshape(in_shape, out_shape, order="C") -> list[str]:
    """三关 Verifier（仿第 64/65 天风格）：
    E1 形状合法（非空、每维 ≥1 的整数）→ E2 元素数量守恒 → E3 order 合法。

    mini 支持两个 order：'C'（行主序，默认）与 'F'（列主序）——
    两者单独都是合法 reshape，但只有 C 序的链能合并（见第 5 节的数值证明）。
    真实框架还有 -1（推断一维）等语法，mini 不做（练习 3 扩展）。
    """
    errs: list[str] = []
    try:
        out = tuple(int(d) for d in out_shape)
    except (TypeError, ValueError):
        return [f"[E1] 形状 {out_shape} 不是整数列表"]

    if len(out) == 0:
        errs.append("[E1] 输出形状为空（mini 不支持标量 ()）")
    for i, d in enumerate(out):
        if d < 1:
            errs.append(f"[E1] 输出第 {i} 维 {d} < 1（mini 每维须为 ≥1 整数）")
    if errs:
        return errs

    n_in, n_out = numel(in_shape), numel(out)
    if n_in != n_out:
        errs.append(f"[E2] 元素数量不守恒：输入 {n_in} ≠ 输出 {n_out}")

    if order not in ("C", "F"):
        errs.append(f"[E3] 未知 order = {order!r}（mini 只认 'C' / 'F'）")
    return errs


# ============================================================
# mini 图 IR：MiniReshapeOp + 图 + 使用计数 + 数值执行
# ============================================================

@dataclass
class MiniReshapeOp:
    """mini.reshape Operation（文本格式仿第 64/65 天）：

    %r = mini.reshape %in shape = [6, 4] order = "C" : (2x3x4xf32) -> (6x4xf32)
    """
    result_id: str
    input_id: str
    in_shape: tuple
    dtype: str = "f32"
    out_shape: tuple = ()
    order: str = "C"

    @property
    def result_shape(self) -> tuple:
        return tuple(int(d) for d in self.out_shape)

    def print_ir(self) -> str:
        shape_s = "[" + ", ".join(str(d) for d in self.out_shape) + "]"
        in_t = "x".join(str(d) for d in self.in_shape) + "x" + self.dtype
        out_t = "x".join(str(d) for d in self.result_shape) + "x" + self.dtype
        return (f"{self.result_id} = mini.reshape {self.input_id} "
                f"shape = {shape_s} order = \"{self.order}\" "
                f": ({in_t}) -> ({out_t})")


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
        shapes = {vid: arr.shape for vid, arr in self.inputs.items()}
        for op in self.ops:
            if op.input_id not in known:
                errs.append(f"[G1] {op.result_id} 的输入 {op.input_id} 无定义")
                continue
            if tuple(op.in_shape) != tuple(shapes[op.input_id]):
                errs.append(f"[G3] {op.result_id} 声明输入形状 {op.in_shape} "
                            f"与生产者实际形状 {shapes[op.input_id]} 不一致")
            errs += verify_reshape(op.in_shape, op.out_shape, op.order)
            known.add(op.result_id)
            shapes[op.result_id] = op.result_shape
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
            env[op.result_id] = np.reshape(env[op.input_id], op.result_shape,
                                           order=op.order)
        return tuple(env[r] for r in self.returns)


def chain_of(graph: MiniGraph):
    """生成所有「连续 reshape 链」候选 (inner, outer)：outer 输入 == inner 结果。

    是否允许合并由 Pattern 的合法性检查决定（中间值唯一使用者、order）。
    """
    for inner in list(graph.ops):
        for outer in list(graph.ops):
            if outer.input_id == inner.result_id:
                yield inner, outer


# ============================================================
# 两个 RewritePattern（今天的正式产出）＋ 激进版对照
# ============================================================

def eliminate_identity_reshape(graph: MiniGraph) -> bool:
    """Pattern 1：恒等 Reshape 消除。

    Reshape(x, shape == shape(x)) → x，无论 order——同形状的 reshape 是
    位置上的恒等映射（读 C 序写 C 序、或读 F 序写 F 序，元素各回原位）。

    合法性论证（与昨天 P1 的关键差别）：
      - 被删除的只有 op 自身；它的结果被替换成输入（两者值相等）；
      - replaceAllUses 把 %r 的全部使用者改道到 %x——多使用者无妨；
      - 所以 P1 不需要「唯一使用者」检查。
    需要「唯一使用者」的是被删除的中间生产者——那是 P2 的事。
    """
    for op in list(graph.ops):
        if op.out_shape != op.in_shape:
            continue
        graph.replace_all_uses(op.result_id, op.input_id)
        graph.erase(op.result_id)
        return True            # 本轮只做一次，留给 PassManager 迭代
    return False


def merge_consecutive_reshape(graph: MiniGraph) -> bool:
    """Pattern 2：连续 Reshape 合并（保守版，mini 默认）。

    Reshape(Reshape(x, s1), s2) → Reshape(x, s2)
    合法性边界：
      - use_count(inner.result) == 1：中间值唯一使用者才允许删
        （func.return 也算使用者——被导出的中间结果必须保留）；
      - 两跳 order 都是 'C'：只有 C 序链保证线性顺序不变（第 5 节数值证明）；
      - 合并产物再过一遍三关 Verifier（防御性自检）。
    特例：合并后 s2 == shape(x) → 整体消除（恒等是合并的特例，同昨天）。
    """
    for inner, outer in chain_of(graph):
        if graph.use_count(inner.result_id) != 1:
            continue           # 中间值有别的消费者（或被 return）→ 保守拒绝
        if inner.order != "C" or outer.order != "C":
            continue           # 混 order 的链不保持线性顺序 → 拒绝
        if tuple(outer.out_shape) == tuple(inner.in_shape):
            graph.replace_all_uses(outer.result_id, inner.input_id)
            graph.erase(outer.result_id)
            graph.erase(inner.result_id)
        else:
            # 原地把 outer 改写成直读 inner 的输入——中间形状 s1 从 IR 消失
            outer.input_id, outer.in_shape = inner.input_id, inner.in_shape
            if verify_reshape(outer.in_shape, outer.out_shape,
                              outer.order) != []:
                continue       # 产物非法就不动（防御，正常构造不出非法）
            graph.erase(inner.result_id)
        return True
    return False


def merge_aggressive_reshape(graph: MiniGraph) -> bool:
    """激进版（第 5 节的对照实验，不在默认管道里）：

    「改写 outer 直读 %in」永远合法——C 序 reshape 的值只依赖输入的
    线性顺序，而 %t = Reshape(x, s1) 与 x 的线性顺序相同；
    「删除 %t」才有条件——改写后 use_count(%t) == 0 才删（否则保留，
    即「保留必要中间结果」）。
    """
    for inner, outer in chain_of(graph):
        if inner.order != "C" or outer.order != "C":
            continue
        outer.input_id, outer.in_shape = inner.input_id, inner.in_shape
        if graph.use_count(inner.result_id) == 0:
            graph.erase(inner.result_id)
        if tuple(outer.out_shape) == tuple(outer.in_shape):
            graph.replace_all_uses(outer.result_id, outer.input_id)
            graph.erase(outer.result_id)
        return True
    return False


def run_passes(graph: MiniGraph, patterns, trace=None, max_rounds=10):
    """PassManager：迭代跑到不动点，返回 (轮数, 应用次数)。

    长链需要多轮：L 跳链每轮合并一对，L-1 次应用后剩单 op（或恒等消除）。
    Pattern 都单调减 op 数，理论上不可能振荡；max_rounds 是防御上限。
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


TWO_PATTERNS = [
    ("P1 eliminate_identity_reshape", eliminate_identity_reshape),
    ("P2 merge_consecutive_reshape", merge_consecutive_reshape),
]


# ============================================================
# MLIR 侧：reshape 链在 stock 管道里的真实裁决
# ============================================================

def find_mlir_opt() -> str | None:
    for cand in (shutil.which("mlir-opt"), "/usr/lib/llvm-18/bin/mlir-opt"):
        if cand and Path(cand).exists() and Path(cand).stat().st_mode & 0o111:
            return cand
    return None


TENSOR_RESHAPE_CHAIN_IR = """module {
  func.func @chain(%in: tensor<2x3x4xf32>) -> tensor<24xf32> {
    %s1 = arith.constant dense<[6, 4]> : tensor<2xi32>
    %s2 = arith.constant dense<[24]> : tensor<1xi32>
    %t = tensor.reshape %in(%s1) : (tensor<2x3x4xf32>, tensor<2xi32>) -> tensor<6x4xf32>
    %r = tensor.reshape %t(%s2) : (tensor<6x4xf32>, tensor<1xi32>) -> tensor<24xf32>
    return %r : tensor<24xf32>
  }
}
"""

COLLAPSE_CHAIN_IR = """module {
  func.func @cc(%in: tensor<2x3x4xf32>) -> tensor<24xf32> {
    %t = tensor.collapse_shape %in [[0, 1], [2]] : tensor<2x3x4xf32> into tensor<6x4xf32>
    %r = tensor.collapse_shape %t [[0, 1]] : tensor<6x4xf32> into tensor<24xf32>
    return %r : tensor<24xf32>
  }
}
"""

EXPAND_CHAIN_IR = """module {
  func.func @ee(%in: tensor<24xf32>) -> tensor<2x3x4xf32> {
    %t = tensor.expand_shape %in [[0, 1]] : tensor<24xf32> into tensor<6x4xf32>
    %r = tensor.expand_shape %t [[0, 1], [2]] : tensor<6x4xf32> into tensor<2x3x4xf32>
    return %r : tensor<2x3x4xf32>
  }
}
"""

EXPAND_COLLAPSE_INVERSE_IR = """module {
  func.func @ec(%in: tensor<24xf32>) -> tensor<24xf32> {
    %t = tensor.expand_shape %in [[0, 1]] : tensor<24xf32> into tensor<6x4xf32>
    %r = tensor.collapse_shape %t [[0, 1]] : tensor<6x4xf32> into tensor<24xf32>
    return %r : tensor<24xf32>
  }
}
"""

COLLAPSE_EXPAND_NONINVERSE_IR = """module {
  func.func @ce(%in: tensor<2x3x4xf32>) -> tensor<6x2x2xf32> {
    %t = tensor.collapse_shape %in [[0, 1], [2]] : tensor<2x3x4xf32> into tensor<6x4xf32>
    %r = tensor.expand_shape %t [[0], [1, 2]] : tensor<6x4xf32> into tensor<6x2x2xf32>
    return %r : tensor<6x2x2xf32>
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
    rng = random.Random(66)

    print("=" * 66)
    print("第 66 天主实验：连续 Reshape 合并（numel 守恒 + 中间使用者约束）")
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
    print("主线：Reshape 链什么时候能合并——元素数量守恒的判据、两个 "
          "RewritePattern、被替换/被删除的合法性区别、数值对拍与 MLIR 实测。")

    B = np.arange(24, dtype=np.float32).reshape(2, 3, 4)   # 贯穿例子（第 64 天同款）

    # ---- 1. 现场一：MLIR stock 管道对 reshape 链的裁决 ----
    print("\n== 1. 现场一：reshape 链交给 --canonicalize，stock 管道动不动？==")
    if mlir_opt:
        cases = [
            ("① tensor.reshape 链（今天的对照主线）", TENSOR_RESHAPE_CHAIN_IR,
             "tensor_reshape_chain", "tensor.reshape"),
            ("② tensor.collapse_shape 连链", COLLAPSE_CHAIN_IR,
             "collapse_chain", "tensor.collapse_shape"),
            ("③ tensor.expand_shape 连链", EXPAND_CHAIN_IR,
             "expand_chain", "tensor.expand_shape"),
            ("④ expand→collapse 互逆对", EXPAND_COLLAPSE_INVERSE_IR,
             "expand_collapse_inverse", "tensor."),
            ("⑤ collapse→expand 非互逆（→(6,2,2)）", COLLAPSE_EXPAND_NONINVERSE_IR,
             "collapse_expand_noninverse", "tensor."),
        ]
        for title, ir, stem, counter in cases:
            code, canon = run_mlir_opt(ir, ["--canonicalize"])
            (OUT / f"{stem}.canon.mlir").write_text(canon, encoding="utf-8")
            n_rs = canon.count("tensor.reshape")
            n_co = canon.count("tensor.collapse_shape")
            n_ex = canon.count("tensor.expand_shape")
            print(f"  {title}")
            print(f"    --canonicalize exit={code}：reshape {n_rs} · "
                  f"collapse {n_co} · expand {n_ex}")
        print("  对照读法：① 原样保留（无规则）；②③ 折叠成单 op（reassociation "
              "组合成 [[0, 1, 2]]）；④ 整体消除为 return %arg0；")
        print("            ⑤ 原样保留——组合出的变换无法用单个 reassociative "
              "reshape 表达，stock 也不重写成 tensor.reshape")

        _, c1 = run_mlir_opt(TENSOR_RESHAPE_CHAIN_IR, ["--canonicalize"])
        check("① tensor.reshape 链经 --canonicalize 原样保留（LLVM 18 无此规则）",
              c1.count("tensor.reshape") == 2)

        _, c2 = run_mlir_opt(COLLAPSE_CHAIN_IR, ["--canonicalize"])
        check("② collapse 连链折叠成单 op，reassociation 组合为 [[0, 1, 2]]",
              c2.count("tensor.collapse_shape") == 1
              and "[[0, 1, 2]]" in c2)

        _, c3 = run_mlir_opt(EXPAND_CHAIN_IR, ["--canonicalize"])
        check("③ expand 连链折叠成单 op [[0, 1, 2]]",
              c3.count("tensor.expand_shape") == 1 and "[[0, 1, 2]]" in c3)

        _, c4 = run_mlir_opt(EXPAND_COLLAPSE_INVERSE_IR, ["--canonicalize"])
        check("④ 互逆对整体消除为 return %arg0",
              c4.count("tensor.expand_shape") == 0
              and c4.count("tensor.collapse_shape") == 0
              and "return %arg0" in c4)

        _, c5 = run_mlir_opt(COLLAPSE_EXPAND_NONINVERSE_IR, ["--canonicalize"])
        check("⑤ 非互逆 collapse→expand 原样保留（2 个 op）",
              c5.count("tensor.collapse_shape") == 1
              and c5.count("tensor.expand_shape") == 1)
    else:
        print("  mlir-opt 不可用，现场一降级为「预期输出，尚未执行」")

    # ---- 2. Reshape 语义：numel 守恒 + 三关 Verifier + view/copy 现场 ----
    print("\n== 2. Reshape 语义：元素数量守恒 + 三关 Verifier ==")
    print("  判据只有一个数：prod(in_shape) == prod(out_shape)（元素数量守恒）")
    for bad in [((2, 3, 4), (5, 7), "C"), ((2, 3, 4), (0, 6), "C"),
                ((2, 3, 4), (24,), "A")]:
        errs = verify_reshape(*bad)
        print(f"  verify_reshape{bad} → {errs[0]}")
    check("E1/E2/E3 反例全部被三关 Verifier 拦截",
          verify_reshape((2, 3, 4), (5, 7), "C") != []
          and verify_reshape((2, 3, 4), (0, 6), "C") != []
          and verify_reshape((2, 3, 4), (24,), "A") != [])
    check("E2 正例：(2,3,4) → (6,4) → (24,) 每跳 numel 都是 24",
          all(verify_reshape(s1, s2) == []
              for s1, s2 in [((2, 3, 4), (6, 4)), ((6, 4), (24,)),
                             ((2, 3, 4), (24,))]))

    print("\n  物理代价现场（numpy 1.26.4 实测，reshape 是视图还是拷贝？）：")
    t = B.reshape(6, 4)
    xT = B.T                       # 非连续视图（第 64 天的老朋友）
    t2 = xT.reshape(6, 4)          # 非连续输入的 reshape → 被迫拷贝
    t3 = t2.reshape(24)            # 拷贝结果的二跳 → 视图
    merged = xT.reshape(24)        # 合并一步（同样一次拷贝）
    print(f"    连续输入 B --reshape--> (6,4)：shares_memory = "
          f"{np.shares_memory(B, t)}（视图）")
    print(f"    非连续输入 B.T --reshape--> (6,4)：shares_memory = "
          f"{np.shares_memory(xT, t2)}（被迫拷贝一次）")
    print(f"    二跳 (6,4) --reshape--> (24,)：shares_memory = "
          f"{np.shares_memory(t2, t3)}（视图）")
    print(f"    合并一步 B.T --reshape--> (24,)：也是一次拷贝，值与两跳相等 = "
          f"{np.array_equal(t3, merged)}")
    check("C 序链的物理代价：连续输入全视图；非连续输入至多第一跳拷贝一次，"
          "合并一步拷贝次数相同",
          np.shares_memory(B, t) and not np.shares_memory(xT, t2)
          and np.shares_memory(t2, t3) and np.array_equal(t3, merged))

    # ---- 3. mini 侧：两个 Pattern 的现场 ----
    print("\n== 3. mini 侧：P1 恒等消除 + P2 链合并的现场 ==")
    print("Pattern 1（恒等消除）：Reshape(x, shape(x)) → x——不需要唯一使用者检查")
    print("Pattern 2（链合并）：Reshape(Reshape(x, s1), s2) → Reshape(x, s2)"
          "——中间值唯一使用者")

    print("\n场景 A（恒等单跳，结果被 2 个消费者 + 0 return 使用 → P1 照样消除）：")
    gA = MiniGraph(
        ops=[MiniReshapeOp("%r", "%in", (2, 3, 4), "f32", (2, 3, 4)),
             MiniReshapeOp("%a", "%r", (2, 3, 4), "f32", (24,)),
             MiniReshapeOp("%b", "%r", (2, 3, 4), "f32", (4, 6))],
        returns=["%a", "%b"],
        inputs={"%in": B})
    print(gA.print_ir())
    print(f"  %r 的使用者数 = {gA.use_count('%r')}（%a、%b 各一）——P1 不看这个")
    before = gA.eval()
    rounds, applied = run_passes(gA, TWO_PATTERNS)
    print(f"→ PassManager {rounds} 轮、应用 {applied} 次：")
    print(gA.print_ir())
    check("A：恒等消除不看使用者数（op 数 3→2），%a/%b 全部改道读 %in",
          len(gA.ops) == 2 and gA.ops[0].input_id == "%in"
          and gA.ops[1].input_id == "%in"
          and all(np.array_equal(a, b) for a, b in zip(gA.eval(), before)))

    print("\n场景 B（朴素链 B --(6,4)--> --(24,)-->，P2 合并跳过中间形状）：")
    gB = MiniGraph(
        ops=[MiniReshapeOp("%t", "%in", (2, 3, 4), "f32", (6, 4)),
             MiniReshapeOp("%c", "%t", (6, 4), "f32", (24,))],
        returns=["%c"],
        inputs={"%in": B})
    print(gB.print_ir())
    before = gB.eval()
    trace = [gB.print_ir()]
    rounds, applied = run_passes(gB, TWO_PATTERNS, trace=trace)
    print(f"→ PassManager {rounds} 轮、应用 {applied} 次：")
    print(gB.print_ir())
    check("B：朴素链合并为单 reshape（op 数 2→1，直读 %in，shape=[24]）",
          len(gB.ops) == 1 and gB.ops[0].input_id == "%in"
          and gB.ops[0].out_shape == (24,)
          and np.array_equal(gB.eval()[0], before[0]))

    print("\n场景 C（绕回链 B --(6,4)--> --(2,3,4)-->，合并成恒等 → 整体消除）：")
    gC = MiniGraph(
        ops=[MiniReshapeOp("%t", "%in", (2, 3, 4), "f32", (6, 4)),
             MiniReshapeOp("%c", "%t", (6, 4), "f32", (2, 3, 4))],
        returns=["%c"],
        inputs={"%in": B})
    print(gC.print_ir())
    before = gC.eval()
    rounds, applied = run_passes(gC, TWO_PATTERNS)
    print(f"→ PassManager {rounds} 轮、应用 {applied} 次：")
    print(gC.print_ir())
    check("C：绕回链整体消除（op 数 2→0，链尾形状 == 输入形状）",
          len(gC.ops) == 0 and np.array_equal(gC.eval()[0], before[0]))

    print("\n场景 D（五连链 B→(6,4)→(24,)→(2,12)→(24,1)→(12,2)，迭代到单 op）：")
    chain_shapes = [(6, 4), (24,), (2, 12), (24, 1), (12, 2)]
    ops_, cur = [], (2, 3, 4)
    ids = ["%in"] + [f"%t{i}" for i in range(len(chain_shapes))]
    for i, s in enumerate(chain_shapes):
        ops_.append(MiniReshapeOp(ids[i + 1], ids[i], cur, "f32", s))
        cur = s
    gD = MiniGraph(ops=ops_, returns=[ids[-1]], inputs={"%in": B})
    before = gD.eval()
    rounds, applied = run_passes(gD, TWO_PATTERNS)
    print(f"→ PassManager {rounds} 轮、应用 {applied} 次（每轮合并一对）：")
    print(gD.print_ir())
    check("D：五连链合并为单 reshape（op 数 5→1，直读 %in，shape=[12,2]）",
          len(gD.ops) == 1 and gD.ops[0].input_id == "%in"
          and gD.ops[0].out_shape == (12, 2)
          and np.array_equal(gD.eval()[0], before[0]))

    print("\n场景 E（多使用者反例：%t 被 %c、%u 两个消费者用 → P2 拒绝，图不动）：")
    gE = MiniGraph(
        ops=[MiniReshapeOp("%t", "%in", (2, 3, 4), "f32", (6, 4)),
             MiniReshapeOp("%c", "%t", (6, 4), "f32", (24,)),
             MiniReshapeOp("%u", "%t", (6, 4), "f32", (4, 6))],
        returns=["%c", "%u"],
        inputs={"%in": B})
    before = gE.eval()
    rounds, applied = run_passes(gE, TWO_PATTERNS)
    print(gE.print_ir())
    print(f"  %t 的使用者数 = {gE.use_count('%t')}（%c、%u 各一）——P2 拒绝")
    check("E：多使用者时图不动（3 个 op 原样）且数值不变",
          len(gE.ops) == 3 and rounds >= 1 and applied == 0
          and all(np.array_equal(a, b) for a, b in zip(gE.eval(), before)))

    print("\n场景 F（中间值 %t 被 func.return 导出 → 也是使用者，拒绝）：")
    gF = MiniGraph(
        ops=[MiniReshapeOp("%t", "%in", (2, 3, 4), "f32", (6, 4)),
             MiniReshapeOp("%c", "%t", (6, 4), "f32", (24,))],
        returns=["%c", "%t"],
        inputs={"%in": B})
    before = gF.eval()
    print(gF.print_ir())
    print(f"  %t 的使用者数 = {gF.use_count('%t')}（%c 一个 + func.return 一个）")
    run_passes(gF, TWO_PATTERNS)
    check("F：被 return 的中间值同样拒绝（op 数仍 2）且数值不变",
          len(gF.ops) == 2
          and all(np.array_equal(a, b) for a, b in zip(gF.eval(), before)))

    print("\n场景 G（混 order 链：内层 C、外层 F → P2 拒绝，图不动）：")
    gG = MiniGraph(
        ops=[MiniReshapeOp("%t", "%in", (2, 3, 4), "f32", (6, 4), "C"),
             MiniReshapeOp("%c", "%t", (6, 4), "f32", (24,), "F")],
        returns=["%c"],
        inputs={"%in": B})
    before = gG.eval()
    print(gG.print_ir())
    run_passes(gG, TWO_PATTERNS)
    print("  拒绝理由：F 序 reshape 会重排线性顺序（数值证明见第 5 节）")
    check("G：混 order 链拒绝合并（op 数仍 2）且数值不变",
          len(gG.ops) == 2
          and np.array_equal(gG.eval()[0], before[0]))

    # ---- 4. 判定表 + 随机压力对拍 ----
    print("\n== 4. 判定表：12 个场景，优化前后数值对拍 ==")

    def build_chain(x_shape, shapes, order="C"):
        ops_, cur = [], x_shape
        ids = ["%in"] + [f"%t{i}" for i in range(len(shapes))]
        for i, s in enumerate(shapes):
            ops_.append(MiniReshapeOp(ids[i + 1], ids[i], cur, "f32", s,
                                      order))
            cur = s
        return ops_, ids

    def run_simple(x_shape, shapes, order="C"):
        x = np.arange(numel(x_shape), dtype=np.float32).reshape(x_shape)
        ops_, ids = build_chain(x_shape, shapes, order)
        g = MiniGraph(ops=ops_, returns=[ids[-1]], inputs={"%in": x})
        before = g.eval()
        run_passes(g, TWO_PATTERNS)
        return g, np.array_equal(g.eval()[0], before[0]) and g.verify() == []

    scenes = [
        ("S1  恒等单跳",          (2, 3, 4), [(2, 3, 4)], 0),
        ("S2  朴素二连",          (2, 3, 4), [(6, 4), (24,)], 1),
        ("S3  绕回二连",          (2, 3, 4), [(6, 4), (2, 3, 4)], 0),
        ("S4  三连",              (2, 3, 4), [(6, 4), (24,), (4, 6)], 1),
        ("S5  五连",              (2, 3, 4),
         [(6, 4), (24,), (2, 12), (24, 1), (12, 2)], 1),
        ("S6  二连绕回（不同中间）", (2, 3, 4), [(24,), (2, 3, 4)], 0),
        ("S7  单跳非恒等",        (2, 3, 4), [(24,)], 1),
        ("S8  恒等单跳 order=F",  (2, 3, 4), [(2, 3, 4)], 0),
        ("S9  4D 长链",           (2, 3, 4, 5),
         [(6, 4, 5), (120,), (2, 60), (10, 12)], 1),
        ("S10 标量维参与",        (2, 3, 4), [(1, 24), (24, 1)], 1),
    ]
    print("用例                       输入shape        形状链"
          "                              优化后op数  数值对拍")
    all_ok = True
    for name, shape, shapes, expect in scenes:
        g, ok = run_simple(shape, shapes,
                           order="F" if "order=F" in name else "C")
        ok = ok and len(g.ops) == expect
        all_ok &= ok
        chain_s = " → ".join(str(list(s)) for s in shapes)
        if len(chain_s) > 36:
            chain_s = chain_s[:33] + "…"
        print(f"{name:<24} {str(shape):>14}  {chain_s:>36}  "
              f"{len(g.ops):>6}      {'ok' if ok else 'MISMATCH'}")
    print("  （S11–S12 是两张特殊构造的图，单独跑：）")
    x = np.arange(24, dtype=np.float32).reshape(2, 3, 4)

    g11 = MiniGraph(
        ops=[MiniReshapeOp("%t1", "%in", (2, 3, 4), "f32", (6, 4)),
             MiniReshapeOp("%t2", "%t1", (6, 4), "f32", (24,)),
             MiniReshapeOp("%u", "%t1", (6, 4), "f32", (4, 6)),
             MiniReshapeOp("%v", "%u", (4, 6), "f32", (2, 12))],
        returns=["%t2", "%v"],
        inputs={"%in": x})
    before11 = g11.eval()
    run_passes(g11, TWO_PATTERNS)
    ok11 = (len(g11.ops) == 3 and g11.ops[2].input_id == "%t1"
            and all(np.array_equal(a, b)
                    for a, b in zip(g11.eval(), before11)))
    print(f"  S11 分叉链（%t1 被 %t2、%u 共用）：4 op → {len(g11.ops)} op——"
          f"被多使用者切开的两段独立判定：(%t1,%t2) 阻塞、(%u,%v) 照样合并，"
          f"数值{'不变' if ok11 else '出错！'}")
    all_ok &= ok11

    g12 = MiniGraph(
        ops=[MiniReshapeOp("%a", "%in", (2, 3, 4), "f32", (24,)),
             MiniReshapeOp("%b", "%a", (24,), "f32", (6, 4)),
             MiniReshapeOp("%c", "%b", (6, 4), "f32", (24,))],
        returns=["%c", "%a"],
        inputs={"%in": x})
    before12 = g12.eval()
    run_passes(g12, TWO_PATTERNS)
    ok12 = (len(g12.ops) == 1
            and all(np.array_equal(a, b)
                    for a, b in zip(g12.eval(), before12)))
    print(f"  S12 %a 被 return 的链：3 op → {len(g12.ops)} op"
          f"（%b 唯一使用者是 %c → (%b,%c) 合并成恒等后整体消除；"
          f"%a 是图输出所以保留），数值{'不变' if ok12 else '出错！'}")
    all_ok &= ok12
    check("判定表 12/12：op 数符合预期 + 数值不变 + Verifier 通过", all_ok)

    print("\n  规律：C 序链的最终 op 数由「链尾形状」一刀决定——"
          "链尾 == 输入形状 → 0，否则 → 1（与链长和中间形状无关）。")

    print("\n随机压力对拍（300 组随机链，秩 1..4、链长 1..5、中间形状随机分解）：")
    rand_ok, ops_before, ops_after = 0, 0, 0

    def random_factorization(rng_, n, max_rank=4):
        rank = rng_.randint(1, max_rank)
        dims, rem = [], n
        for _ in range(rank - 1):
            divs = [d for d in range(1, rem + 1) if rem % d == 0]
            d = rng_.choice(divs)
            dims.append(d)
            rem //= d
        dims.append(rem)
        return tuple(dims)

    for _ in range(300):
        rank = rng.randint(1, 4)
        shape = tuple(rng.randint(1, 5) for _ in range(rank))
        n = numel(shape)
        L = rng.randint(1, 5)
        shapes = [random_factorization(rng, n) for _ in range(L)]
        xv = np.arange(n, dtype=np.float32).reshape(shape)
        ops_, ids = build_chain(shape, shapes)
        g = MiniGraph(ops=ops_, returns=[ids[-1]], inputs={"%in": xv})
        before = g.eval()
        run_passes(g, TWO_PATTERNS)
        after = g.eval()
        ops_before += L
        ops_after += len(g.ops)
        expect = 0 if tuple(shapes[-1]) == tuple(shape) else 1
        if (np.array_equal(after[0], before[0]) and g.verify() == []
                and len(g.ops) == expect):
            rand_ok += 1
    check(f"随机对拍 {rand_ok}/300：数值不变、Verifier 通过、op 数 = 链尾判定",
          rand_ok == 300)
    print(f"  300 组共 {ops_before} 个初始 op（平均链长 3），优化后剩 {ops_after} 个"
          f"（{ops_after / ops_before * 100:.1f}%）——几乎全部坍缩成单跳")

    # ---- 5. 激进版现场：改写永远合法，删除才有条件 ----
    print("\n== 5. 激进版现场：「改写 outer 直读 %in」永远合法，删除 %t 才有条件 ==")

    def copy_of(g):
        import copy as _copy
        return _copy.deepcopy(g)

    print("  5a. 多使用者图（场景 E 同款）跑激进版（迭代到不动点）：")
    gE2 = copy_of(gE)
    print(gE2.print_ir())
    before = gE2.eval()
    applied_cnt = 0
    while merge_aggressive_reshape(gE2):
        applied_cnt += 1
    print(f"  激进版应用 {applied_cnt} 次后：")
    print(gE2.print_ir())
    print("  两条消费路径都改写成直读 %in（各自值不变）；内部中间值 %t 的"
          "使用者随之归零 → 连带删除（op 数 3→2）")
    print("  ——「必要中间结果」只有图输出（被 return 的值）才真正必要，"
          "内部值永远可以被绕过")
    check("5a：激进版把 %c、%u 都改道直读 %in 后删除无人的 %t（op 数 3→2，"
          "值不变）",
          len(gE2.ops) == 2 and gE2.ops[0].input_id == "%in"
          and gE2.ops[1].input_id == "%in"
          and all(np.array_equal(a, b) for a, b in zip(gE2.eval(), before)))

    print("  5b. 唯一使用者的链（场景 B 同款）跑激进版：")
    gB2 = copy_of(gB)
    before = gB2.eval()
    while merge_aggressive_reshape(gB2):
        pass
    print(gB2.print_ir())
    check("5b：唯一使用者时激进版与保守版殊途同归（%t 删除，op 数 2→1）",
          len(gB2.ops) == 1 and gB2.ops[0].input_id == "%in"
          and np.array_equal(gB2.eval()[0], before[0]))

    print("  5c. 中间值被 return 的图（场景 F 同款）跑激进版：")
    gF2 = copy_of(gF)
    before = gF2.eval()
    while merge_aggressive_reshape(gF2):
        pass
    print(gF2.print_ir())
    print("  %t 是图输出，必须物化保留；%c 改直读 %in——物理拷贝次数没省，"
          "省的是 %c 这条路径的读端与后续 Pattern 的通过性")
    check("5c：被 return 的 %t 保留，%c 仍被改写成直读 %in（op 数仍 2）",
          len(gF2.ops) == 2 and gF2.ops[1].input_id == "%in"
          and all(np.array_equal(a, b) for a, b in zip(gF2.eval(), before)))

    # ---- 6. 混 order 的数值终审：C∘F 不是任何单个 reshape ----
    print("\n== 6. 混 order 终审：为什么 P2 要求两跳都是 C 序 ==")
    a = np.reshape(B, (6, 4), order="C")
    b = np.reshape(a, (24,), order="F")
    cC = np.reshape(B, (24,), order="C")
    cF = np.reshape(B, (24,), order="F")
    print(f"  C∘F 链的值前 8 个：{b[:8].astype(int).tolist()}")
    print(f"  单个 C 序 reshape：{cC[:8].astype(int).tolist()}")
    print(f"  单个 F 序 reshape：{cF[:8].astype(int).tolist()}")
    print(f"  C∘F == 单个C？ {np.array_equal(b, cC)}；"
          f"C∘F == 单个F？ {np.array_equal(b, cF)}")
    check("C∘F 链不等于任何单个 reshape（C 或 F）——混 order 不可合并",
          not np.array_equal(b, cC) and not np.array_equal(b, cF))
    ok = all(np.array_equal(np.reshape(np.reshape(B, s1), s2),
                            np.reshape(B, s2))
             for s1 in [(6, 4), (24,), (4, 6), (2, 12), (1, 24)]
             for s2 in [(6, 4), (24,), (4, 6), (2, 12), (1, 24)])
    check("C∘C 链对 25 组形状组合全部等于单个 C 序 reshape（合并规则）", ok)

    # ---- 7. 汇总 ----
    print()
    print("=" * 66)
    print(f"汇总：PASS {PASS} / FAIL {FAIL}")
    print("=" * 66)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
