#!/usr/bin/env python3
"""dynamic_lab.py —— 第 61 天：动态 Shape 表示（静态 / 符号 / 未知）与约束记录。

贯穿例子（与 MLIR 侧 matmul_dynamic.mlir 用同一份数据）：
    A(2,3) = [[1,2,3],[4,5,6]]，B(3,2) = [[10,20],[30,40],[50,60]]
    C(2,2) = A×B = [[220,280],[490,640]]

把 M / K / N 三个维度换成三种表示，看推导器各自允诺什么：
    静态 int   : 编译期就知道，Verifier 可以直接对账
    Sym('m')   : 符号维度——不知道具体值，但「有名字」；同名 = 运行期必须相等
    None       : 未知维度——不知道值也没有身份；取值来自运行期的实际输入
                （对 M/N 是「任意合法值都行」；对 K，两个 None 仍隐含相等约束）

实验内容：
  1. 贯穿例子：三种表示 × 六种结局（静态对账 / 符号绑定 / 改名 / 运行期约束 / 拒绝）
  2. 判定表：12 组合，mini 预测 vs 手算期望
  3. 符号绑定与特化预演：把 Sym 换成静态值（Day 62 的入口）+ 图级绑定冲突
  4. 运行期模拟：实际 Shape 进来 → 检查约束 → numpy 对拍（有检查 vs 无检查）
  5. 随机压力：500 组随机形状，推导要么出结果要么 ShapeError，绝不崩溃
  6. IR 生成器：8 个 M/N/K 静态-动态房间 → generated_dynamic_tests.mlir
  7. 汇总断言

运行: python3 dynamic_lab.py
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

import numpy as np

CHECKS = [0, 0]


def check(name: str, cond: bool, detail: str = "") -> None:
    CHECKS[1] += 1
    CHECKS[0] += bool(cond)
    mark = "PASS" if cond else "FAIL"
    suffix = f"  ({detail})" if detail and not cond else ""
    print(f"  [{mark}] {name}{suffix}")


# ============================================================
# 1. 维度表示：int / Sym / None
# ============================================================

class ShapeError(ValueError):
    """编译期可见的形状非法（对账失败、秩不符、负维度等）。"""


class RuntimeShapeError(ValueError):
    """运行期 Shape 检查失败（对应 MLIR 里物化出来的 cf.assert）。"""


class Sym:
    """符号维度：有名字的未知。同名 Sym 在运行期必须取同一个值。"""

    __slots__ = ("name",)

    def __init__(self, name: str):
        if not isinstance(name, str) or not name:
            raise ShapeError(f"符号维度必须有名字，收到 {name!r}")
        self.name = name

    def __eq__(self, other):
        return isinstance(other, Sym) and other.name == self.name

    def __hash__(self):
        return hash(("Sym", self.name))

    def __repr__(self):
        return f"?{self.name}"


def clean_shape(shape) -> tuple:
    """构造 Shape：维度必须是自然数、None 或 Sym；-1 不是「动态」而是非法。"""
    out = []
    for d in shape:
        if d is None or isinstance(d, Sym):
            out.append(d)
        elif isinstance(d, bool) or not isinstance(d, int):
            raise ShapeError(f"维度必须是 int/Sym/None，收到 {d!r}")
        elif d < 0:
            raise ShapeError(f"negative dimensions are not allowed: {d}")
        else:
            out.append(d)
    return tuple(out)


# ============================================================
# 2. MatMul Shape 推导 + 约束记录
# ============================================================

@dataclass
class Constraints:
    """一次推导（或一张图）收集到的全部约束，分三档存放：

    bindings: 符号被静态值钉住（A 的 K 是 ?s、B 的 K 是 3 → ?s==3，
              编译期成立、特化时可直接替换——Day 62 的入口）
    renames:  两个符号被认定为同一个（?s0 == ?s1，改名保留语义）
    runtime:  运行期必须成立的等式（cf.assert 的原料——
              「? 必须等于 3」这类检查要么编译期对账，要么运行期 assert）
    """

    bindings: dict = field(default_factory=dict)
    renames: dict = field(default_factory=dict)
    runtime: list = field(default_factory=list)

    def resolve(self, dim):
        """Sym 沿 renames 链换成规范名；int/None 原样返回。"""
        seen = set()
        while isinstance(dim, Sym) and dim.name in self.renames \
                and dim.name not in seen:
            seen.add(dim.name)
            dim = Sym(self.renames[dim.name])
        return dim

    def bind(self, name: str, value: int) -> None:
        if name in self.bindings and self.bindings[name] != value:
            raise ShapeError(
                f"符号 ?{name} 已绑定 {self.bindings[name]}，又遇到 {value}")
        self.bindings[name] = value

    def rename(self, old: str, new: str) -> None:
        """把符号 old 认定为 new（同一个未知，统一叫法）。"""
        if old == new:
            return
        self.renames[old] = new

    def empty(self) -> bool:
        return not (self.bindings or self.renames or self.runtime)


def _k_account(k_a, k_b, ctx: Constraints, pos_a: str, pos_b: str):
    """K 对账：A 的第 1 维 vs B 的第 0 维，按表示档位走分支。"""
    if isinstance(k_a, int) and isinstance(k_b, int):     # 静态 vs 静态：直接比
        if k_a != k_b:
            raise ShapeError(
                f"matmul: K 对不上——A 的 {pos_a}={k_a}，B 的 {pos_b}={k_b}")
        return
    if isinstance(k_a, Sym) and isinstance(k_b, Sym):      # 符号 vs 符号
        na, nb = ctx.resolve(k_a).name, ctx.resolve(k_b).name
        if na != nb:
            ctx.rename(nb, na)                             # ?k2 就是 ?k1
        return
    if isinstance(k_a, Sym) and isinstance(k_b, int):      # 符号 vs 静态：绑定
        ctx.bind(ctx.resolve(k_a).name, k_b)                # ?s == 3
        return
    if isinstance(k_a, int) and isinstance(k_b, Sym):
        ctx.bind(ctx.resolve(k_b).name, k_a)
        return
    # 剩下的组合至少含一个 None：编译期对不了账，只能记运行期等式
    #（?k 对 ? 也一样——符号的值要到运行期才见分晓，两边只能到时候对）
    ctx.runtime.append(f"{pos_a} == {pos_b}")               # e.g. "dim(A,1) == dim(B,0)"


def matmul_shape(a, b, ctx: Constraints | None = None):
    """MatMul 输出 Shape 推导（带约束记录）。非法抛 ShapeError。

    规则：
      秩：两边都必须是二维（动态维度不豁免秩检查）；
      M：A 的第 0 维原样透传到输出（int/Sym/None 三种表示都合法）；
      N：B 的第 1 维原样透传到输出；
      K：A 的第 1 维与 B 的第 0 维对账——静态比数值、符号走绑定/改名、
         None 记运行期等式。
    ctx 不为 None 时复用同一份约束（一张图里的 ?s 只能有一个值）。
    返回 (out_shape, constraints)。
    """
    a, b = clean_shape(a), clean_shape(b)
    if len(a) != 2 or len(b) != 2:
        raise ShapeError(
            f"matmul 需要二维操作数，收到 rank {len(a)} 与 rank {len(b)}")
    ctx = ctx if ctx is not None else Constraints()
    _k_account(a[1], b[0], ctx, "dim(A,1)", "dim(B,0)")
    return (ctx.resolve(a[0]), ctx.resolve(b[1])), ctx


# ============================================================
# 3. 符号绑定与特化（Day 62 的入口，今天只做替换机制）
# ============================================================

def specialize(shape, bindings: dict, renames: dict):
    """把 shape 里的 Sym 按绑定表换成静态值；没绑定的符号与 None 保持原样。

    这是 Day 62「specialize-shape」的核心动作：约束里的 bindings 表
    告诉我们哪些符号可以安全替换（相等性已静态成立，替换不改变语义）。
    """
    out = []
    for d in shape:
        if isinstance(d, Sym):
            d = Sym(renames.get(d.name, d.name))
            out.append(bindings[d.name] if d.name in bindings else d)
        else:
            out.append(d)
    return tuple(out)


# ============================================================
# 4. 运行期模拟：实际 Shape 进来 + 约束检查 + numpy 对拍
# ============================================================

def materialize(shape, env: dict, rng: random.Random):
    """给动态维度分配具体值：Sym 用 env（同名同值），None 各自随机。

    env: {符号名: 具体值}——同名 Sym 必须拿到同一个值，这是符号的全部语义。
    """
    out = []
    for d in shape:
        if isinstance(d, Sym):
            if d.name not in env:
                env[d.name] = rng.randint(1, 5)
            out.append(env[d.name])
        elif d is None:
            out.append(rng.randint(1, 5))           # None 没有身份，各自随机
        else:
            out.append(d)
    return tuple(out)


def check_runtime(ctx: Constraints, a_real, b_real) -> list:
    """模拟运行期检查：约束里的 runtime 等式逐条核对，返回违规清单。

    对应 MLIR 侧 k_check.mlir 的 cf.assert：约束不成立 → 程序死在那里。
    """
    def value(pos):                    # pos 形如 "dim(A,1)" / "dim(B,0)"
        which = "AB".index(pos[4])
        idx = int(pos.rstrip(")").split(",")[1])
        return (a_real if which == 0 else b_real)[idx]

    broken = []
    for eq in ctx.runtime:
        lhs, rhs = eq.split(" == ")
        if value(lhs.strip()) != value(rhs.strip()):
            broken.append(eq)
    return broken


def rand_arr(rng: random.Random, shape):
    """用同一个 rng 生成 [-1,1) 的二维随机矩阵（对拍用的数据源）。"""
    return np.array([[rng.uniform(-1, 1) for _ in range(shape[1])]
                     for _ in range(shape[0])])


def simulate(a, b, rng: random.Random, *, checked=True, a_real=None,
             b_real=None, env=None, data=None):
    """端到端模拟一次动态 MatMul 调用。

    a_real/b_real：运行期实际到达的形状（缺省用 materialize 随机生成）。
    data         ：可选的 (av, bv) 输入矩阵（对拍时传入同一份随机数据）。
    checked=True  : 约束违规 → RuntimeShapeError（k_check.mlir 的行为）；
                    输出里的动态维按实际输入回填（M 跟 A 的行数、N 跟 B 的列数）。
    checked=False : 不检查，按 A 的 K 计算（k_hazard.mlir 的行为——
                    B 比 A 长的维被无声无视，答案悄悄错）。
    返回 (out_shape_real, result, actual) 三个元组，actual=(a_real,b_real)。
    """
    out_shape, ctx = matmul_shape(a, b)
    env = env if env is not None else {}
    a_real = tuple(a_real) if a_real else materialize(a, env, rng)
    b_real = tuple(b_real) if b_real else materialize(b, env, rng)
    if checked:
        broken = check_runtime(ctx, a_real, b_real)
        if broken:
            raise RuntimeShapeError(
                "matmul: dynamic dims must satisfy: " + "; ".join(broken))
    # 输出形状在运行期具体化：None/未绑定符号由实际输入决定
    spec = specialize(out_shape, ctx.bindings, ctx.renames)
    out_real = []
    for i, d in enumerate(spec):
        if d is None or isinstance(d, Sym):
            out_real.append(a_real[0] if i == 0 else b_real[1])
        else:
            out_real.append(d)
    out_real = tuple(out_real)
    # 数值执行：checked 模式下形状必然合法；unchecked 模式模仿 MLIR 循环——
    # K 上界只从 A 读（B 更长则多余部分被无声无视）
    k_a = a_real[1]
    b_used = b_real if (checked or b_real[0] <= k_a) else (k_a, b_real[1])
    if data is not None:
        av, bv = data
    else:
        av, bv = rand_arr(rng, a_real), rand_arr(rng, b_used)
    return out_real, np.matmul(av, bv), (a_real, b_real)


# ============================================================
# 5. 随机压力：推导不崩溃
# ============================================================

DIM_UNIVERSE = [1, 2, 3, 4, None, None, Sym("s0"), Sym("s1"), Sym("s2")]


def _same_dim(d1, d2) -> bool:
    return d1 == d2 or (isinstance(d1, Sym) and isinstance(d2, Sym)
                        and d1.name == d2.name)


def fuzz(n: int, seed: int) -> dict:
    """n 组随机形状过 matmul_shape：要么成功、要么 ShapeError，绝不别的异常。"""
    rng = random.Random(seed)
    stats = {"ok": 0, "shape_error": 0, "other_exception": 0, "bad_result": 0}
    for _ in range(n):
        a = tuple(rng.choice(DIM_UNIVERSE)
                  for _ in range(rng.choice([1, 2, 2, 2, 3])))
        b = tuple(rng.choice(DIM_UNIVERSE)
                  for _ in range(rng.choice([1, 2, 2, 2, 3])))
        try:
            out, ctx = matmul_shape(a, b)
        except ShapeError:
            stats["shape_error"] += 1
            continue
        except Exception as exc:                     # 不该发生的异常
            stats["other_exception"] += 1
            print(f"    崩溃现场：{a!r} × {b!r} → {type(exc).__name__}: {exc}")
            continue
        # 成功结果的不变量：秩 2；M 原样来自 A；N 原样来自 B
        if not (len(out) == 2 and _same_dim(out[0], ctx.resolve(a[0]))
                and _same_dim(out[1], ctx.resolve(b[1]))):
            stats["bad_result"] += 1
            continue
        stats["ok"] += 1
        # 幂等：同一输入再推一次，结果一致
        out2, _ = matmul_shape(a, b)
        if out2 != out:
            stats["bad_result"] += 1
    return stats


# ============================================================
# 6. IR 生成器：把推导结果写成 MLIR 测试 IR
# ============================================================

def ir_dim(d) -> str:
    """维度 → MLIR 类型文本。注意：MLIR 的 ? 分不出 Sym 和 None。"""
    if d is None or isinstance(d, Sym):
        return "?"
    return str(d)


def ir_tensor(shape) -> str:
    return "tensor<" + "x".join(ir_dim(d) for d in shape) + "xf32>"


def gen_test_ir() -> str:
    """8 个房间：M/N/K 各自取 {静态, 动态} 的全部组合。

    每个房间的输出类型由 mini 推导后写出——生成 → mlir-opt 解析 + 验证 +
    降循环（见 run_all.sh 第 6 步），这就是「推导不崩溃」的实测。
    """
    lines = [
        "// generated_dynamic_tests.mlir —— 由 dynamic_lab.py 第 6 节生成。",
        "// M/N/K 各取 {静态, 动态} 的 8 种组合；输出类型由 mini 推导后写出。",
        "// 动态维一律用 ? 表示——MLIR 的 ? 分不出「符号」和「未知」，",
        "// 这正是 shape dialect 要用 witness 补的信息（见 k_constraint.mlir）。",
        "",
        "module {",
    ]
    for i, (m_dyn, k_dyn, n_dyn) in enumerate(
            [(m, k, n) for m in (False, True)
             for k in (False, True) for n in (False, True)]):
        m = None if m_dyn else 2
        k = None if k_dyn else 3
        n = None if n_dyn else 2
        out, ctx = matmul_shape((m, k), (k, n))
        tag = (f"room_{i}_M{'dyn' if m_dyn else '2'}"
               f"_K{'dyn' if k_dyn else '3'}_N{'dyn' if n_dyn else '2'}")
        cons = f"，约束 {ctx.runtime}" if ctx.runtime else ""
        lines.append(f"  // {tag}：输出 {out!r}{cons}")
        lines.append(f"  func.func @{tag}(%a: {ir_tensor((m, k))}, "
                     f"%b: {ir_tensor((k, n))}, %init: {ir_tensor(out)}) "
                     f"-> {ir_tensor(out)} {{")
        lines.append(f"    %r = linalg.matmul ins(%a, %b : {ir_tensor((m, k))}, "
                     f"{ir_tensor((k, n))}) outs(%init : {ir_tensor(out)}) "
                     f"-> {ir_tensor(out)}")
        lines.append(f"    return %r : {ir_tensor(out)}")
        lines.append("  }")
        lines.append("")
    lines.append("}")
    return "\n".join(lines) + "\n"


# ============================================================
# 主实验流程
# ============================================================

def main() -> None:
    rng = random.Random(61)
    s = lambda n: Sym(n)

    print("=== 1. 贯穿例子：三种表示 × 六种结局 ===")
    print("  数据：A(2,3)=[[1,2,3],[4,5,6]]，B(3,2)=[[10,20],[30,40],[50,60]]")
    print("        C(2,2)=A×B=[[220,280],[490,640]]（mlir-cpu-runner 实测一致）")

    # 结局一：全静态 —— 编译期对账，零约束
    out, ctx = matmul_shape((2, 3), (3, 2))
    print(f"  ① 全静态：(2,3)×(3,2) → 输出 {out}，约束：无（K 的 3==3 编译期对完账）")
    check("全静态推导", out == (2, 2) and ctx.empty())

    # 结局二：M 用符号 —— 输出带符号，K 仍静态对账
    out, ctx = matmul_shape((s("M"), 3), (3, 2))
    print(f"  ② M 符号：(?M,3)×(3,2) → 输出 {out}，约束：无（M 透传，K 静态）")
    check("M 符号透传", out == (s("M"), 2) and ctx.empty())

    # 结局三：K 一边静态一边符号 —— 绑定
    out, ctx = matmul_shape((2, s("k")), (3, 2))
    print(f"  ③ K 符号：(2,?k)×(3,2) → 输出 {out}，绑定 {ctx.bindings}"
          f"（?k 被钉成 3，特化可直接替换）")
    check("K 符号绑定", out == (2, 2) and ctx.bindings == {"k": 3})

    # 结局四：K 两边都是未知 —— 运行期约束
    out, ctx = matmul_shape((2, None), (None, 2))
    print(f"  ④ K 未知：(2,?)×(?,2) → 输出 {out}（全静态！），运行期约束 {ctx.runtime}")
    print("     —— K 不在输出里所以输出静态，但两个 ? 仍必须相等：未知 ≠ 任意")
    check("K 双未知 → 运行期约束", out == (2, 2)
          and ctx.runtime == ["dim(A,1) == dim(B,0)"])

    # 结局五：静态失配 —— 编译期拒绝
    try:
        matmul_shape((2, 3), (4, 2))
        ok = False
    except ShapeError as e:
        ok = "K 对不上" in str(e)
        print(f"  ⑤ 静态失配：(2,3)×(4,2) → ShapeError: {e}")
    check("静态失配被拒", ok)

    # 结局六：两个不同符号的 K —— 改名统一
    out, ctx = matmul_shape((s("M"), s("k1")), (s("k2"), 2))
    print(f"  ⑥ 双符号 K：(?M,?k1)×(?k2,2) → 输出 {out}，改名 {ctx.renames}"
          f"（?k2 就是 ?k1，一个名字）")
    check("双符号 K 改名统一", out == (s("M"), 2)
          and ctx.renames == {"k2": "k1"})

    print()
    print("=== 2. 判定表：mini 推导 vs 手算期望 ===")
    cases = [
        # (名称, A, B, 期望输出, 期望绑定, 期望改名, 期望运行期约束, 期望错误)
        ("J1  全静态", (2, 3), (3, 2), (2, 2), {}, {}, [], None),
        ("J2  M 未知", (None, 3), (3, 2), (None, 2), {}, {}, [], None),
        ("J3  N 未知", (2, 3), (3, None), (2, None), {}, {}, [], None),
        ("J4  K 一边未知", (2, None), (3, 2), (2, 2), {}, {},
         ["dim(A,1) == dim(B,0)"], None),
        ("J5  K 双未知", (None, None), (None, 2), (None, 2), {}, {},
         ["dim(A,1) == dim(B,0)"], None),
        ("J6  M 符号", (s("m"), 3), (3, 2), (s("m"), 2), {}, {}, [], None),
        ("J7  N 符号", (2, 3), (3, s("n")), (2, s("n")), {}, {}, [], None),
        ("J8  K 符号对静态", (2, s("k")), (3, 2), (2, 2), {"k": 3}, {}, [], None),
        ("J9  K 双符号同名", (s("m"), s("k")), (s("k"), 2), (s("m"), 2),
         {}, {}, [], None),
        ("J10 K 双符号异名", (2, s("k1")), (s("k2"), 2), (2, 2),
         {}, {"k2": "k1"}, [], None),
        ("J11 K 未知对符号", (2, None), (s("k"), 2), (2, 2), {}, {},
         ["dim(A,1) == dim(B,0)"], None),
        ("J12 静态失配", (2, 3), (4, 2), None, None, None, None, "K 对不上"),
    ]
    print(f"  {'用例':<16}{'A':<15}{'B':<15}{'输出':<10}绑定/改名/运行期约束")
    all_ok = True
    for name, a, b, w_out, w_bind, w_ren, w_rt, w_err in cases:
        try:
            out, ctx = matmul_shape(a, b)
            ok = (out == w_out and ctx.bindings == w_bind
                  and ctx.renames == w_ren and ctx.runtime == w_rt)
            got = repr(out)
            detail = (f"绑{ctx.bindings} 改{ctx.renames} 运行期{ctx.runtime}"
                      if not ctx.empty() else "无")
        except ShapeError as e:
            ok = w_err is not None and w_err in str(e)
            got = "ShapeError"
            detail = str(e)
        all_ok &= ok
        print(f"  {name:<16}{str(a):<15}{str(b):<15}{got:<10}{detail}")
    check("判定表 12 组全部一致", all_ok)

    print()
    print("=== 3. 符号绑定与特化预演（Day 62 的入口）===")
    out, ctx = matmul_shape((2, s("k")), (3, 2))
    spec = specialize(out, ctx.bindings, ctx.renames)
    print(f"  (2,?k)×(3,2) → 输出 {out}，绑定 {ctx.bindings}")
    print(f"  specialize 后 → {spec}（符号被静态值替换，回全静态世界）")
    check("特化替换", spec == (2, 2))

    out, ctx = matmul_shape((s("M"), s("k1")), (s("k2"), 5))
    spec = specialize(out, ctx.bindings, ctx.renames)
    print(f"  (?M,?k1)×(?k2,5) → 输出 {out}，改名 {ctx.renames}")
    print(f"  specialize 后 → {spec}（?k2 改名成 ?k1；?M 没绑定，保持符号）")
    check("改名后特化保持未绑定符号", spec == (s("M"), 5))

    # 图级绑定冲突：同一张图（共享 ctx）里 ?k 不能既是 3 又是 4
    graph = Constraints()
    matmul_shape((2, s("k")), (3, 2), ctx=graph)
    try:
        matmul_shape((2, s("k")), (4, 2), ctx=graph)
        ok = False
        detail = "第二次对账没有报错"
    except ShapeError as e:
        ok = "已绑定" in str(e)
        detail = str(e)
    print(f"  图级冲突：先 (2,?k)×(3,2) 绑定 ?k=3，再 (2,?k)×(4,2) →"
          f" ShapeError: {detail}")
    print("  —— 一张图里的符号只有一个值；两条边都说它该等于不同的常数，图就是非法的")
    check("图级符号绑定冲突被拒", ok)

    print()
    print("=== 4. 运行期模拟：有检查 vs 无检查（对照 k_check / k_hazard）===")
    # ① 合法：K 双未知，运行期真的相等（实际形状 (2,3) 和 (3,2)）
    out_real, res, (ar, br) = simulate((2, None), (None, 2), rng, checked=True,
                                      a_real=(2, 3), b_real=(3, 2))
    print(f"  ① (2,?)×(?,2)，实际到达 (2,3) 和 (3,2)：检查放行 → {out_real}")
    check("合法动态输入通过检查", out_real == (2, 2))

    # ② 违规 + 有检查：K_A=3 ≠ K_B=5
    try:
        simulate((2, None), (None, 2), rng, checked=True,
                 a_real=(2, 3), b_real=(5, 2))
        fired, msg = False, ""
    except RuntimeShapeError as e:
        fired, msg = True, str(e)
    print(f"  ② 实际到达 (2,3) 和 (5,2)：RuntimeShapeError: {msg}")
    print("     —— 对应 k_check.mlir：cf.assert 触发，abort（exit=134）")
    check("违规动态输入被运行期检查拦下", fired)

    # ③ 违规 + 无检查：同样的数据，错误无声滑过
    out_real, res, _ = simulate((2, None), (None, 2), rng, checked=False,
                                a_real=(2, 3), b_real=(5, 2))
    print(f"  ③ 关掉检查，同样 (2,3) 和 (5,2)：不报错，按 A 的 K=3 悄悄算完")
    print("     —— 对应 k_hazard.mlir：B 的第 4、5 行被无声无视/越界，exit=0")
    check("无检查时违规静默滑过", out_real == (2, 2))

    # ④ numpy 对拍：随机合法组合，检查放行后数值逐位一致
    ok = True
    for seed in range(20, 24):
        r = random.Random(seed)
        env = {}
        a_real = materialize((None, 3), env, r)
        b_real = materialize((3, None), env, r)
        av, bv = rand_arr(r, a_real), rand_arr(r, b_real)
        want = np.matmul(av, bv)
        out_real, got, _ = simulate((None, 3), (3, None), r, checked=True,
                                    a_real=a_real, b_real=b_real, env=env,
                                    data=(av, bv))
        ok &= out_real == want.shape and np.allclose(got, want)
    print(f"  ④ numpy 对拍：4 组随机动态输入，模拟结果与参考实现逐位一致")
    check("动态模拟与 numpy 数值一致", ok)

    print()
    print("=== 5. 随机压力：500 组，推导要么出结果要么 ShapeError ===")
    stats = fuzz(500, 61)
    total = sum(stats.values())
    print(f"  ok={stats['ok']} · shape_error={stats['shape_error']} · "
          f"other_exception={stats['other_exception']} · bad_result={stats['bad_result']}")
    check("500 组零崩溃零坏结果", stats["other_exception"] == 0
          and stats["bad_result"] == 0 and total == 500)

    print()
    print("=== 6. IR 生成器：8 房间动态 IR（mlir-opt 验证见 run_all.sh 第 6 步）===")
    ir = gen_test_ir()
    with open("generated_dynamic_tests.mlir", "w", encoding="utf-8") as f:
        f.write(ir)
    rooms = ir.count("func.func @room_")
    qmarks = ir.count("?")
    print(f"  写出 generated_dynamic_tests.mlir：{rooms} 个房间，"
          f"类型里共 {qmarks} 个 ?")
    print("  M?/K?/N? 全组合的输出类型全部由 mini 推导生成，无一崩溃")
    check("8 房间 IR 生成", rooms == 8)

    print()
    print(f"=== 7. 汇总：{CHECKS[0]}/{CHECKS[1]} ===")
    if CHECKS[0] != CHECKS[1]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
