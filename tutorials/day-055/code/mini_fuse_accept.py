#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mini_fuse_accept.py —— 第 55 天核心示例：融合负例总验收。

在第 51～54 天的迷你图 IR / Rewriter（带 use-def 完整性检查）基础上，
把第 8 周攒下的全部融合负例整理成一套「验收语料」，并用三道闸门逐一判：

  闸门一 Verifier    ：结构合法性（Shape 三分类、rank、dtype、结果类型）
  闸门二 Pattern     ：融合前置条件（多使用者、类型边界、两侧 matmul 歧义）
  闸门三 数值对账    ：融合前后 evaluate 结果一致（求值器能力以内的语义）

验收判据（每条用例）：
  R1 正例：bottom-up / top-down 两种遍历必须收敛到同一形态（Day 54 教训）；
  R2 负例：拒绝必须是恒等变换——IR 逐字不变、代价账本不变（无副作用）；
  R3 数值：融合前后所有输出 allclose；
  R4 Verifier 层负例：verify 报错即拦下；再关掉 verify 复跑，Pattern 的
     第二道防线必须仍然拦下（防线冗余可观测）。

运行:
    python3 mini_fuse_accept.py                 # 全量验收 + 汇总表
    python3 mini_fuse_accept.py --case C08      # 只跑一个用例（带决策日志）
    python3 mini_fuse_accept.py --no-type-guard # 对照实验：拆掉类型闸门
"""

import argparse
import sys

import numpy as np

# ===================== 类型、值、算子、图（第 51～53 天同款） =====================


def tt(*dims, dtype="f32"):
    """张量类型：(shape, dtype)。"""
    return ("tensor", tuple(dims), dtype)


def shape_of(vtype):
    return vtype[1]


def dtype_of(vtype):
    return vtype[2]


class Value:
    def __init__(self, name, vtype, def_op=None):
        self.name, self.type, self.def_op = name, vtype, def_op
        self.uses = []          # [Op] —— 谁在用我（use-def 的 use 侧）

    def has_one_use(self):
        return len(self.uses) == 1

    def n_uses(self):
        return len(self.uses)


class Op:
    def __init__(self, name, inputs, result):
        self.name, self.inputs, self.result = name, inputs, result
        self.alive = True
        if result is not None:            # func.return 没有结果
            result.def_op = self
        for v in inputs:
            v.uses.append(self)

    def __repr__(self):
        return f"<{self.name} -> {self.result.name}>"


class Graph:
    """图输出建模成真实的 func.return 算子：return 也是使用者！
    这正是 C08（%s 共用）能被 hasOneUse 闸门拦下的前提——MLIR 里
    func.return %r, %s 同样让 %s 的 use 计数 +1。"""

    def __init__(self, func_name):
        self.func_name = func_name
        self.inputs = []        # [Value]（图输入，无 def_op）
        self.ops = []           # [Op] 程序序（含末尾的 func.return）
        self.ret = None

    def add_input(self, name, vtype):
        v = Value(name, vtype)
        self.inputs.append(v)
        return v

    def create_op(self, name, inputs, result_name, result_type):
        for v in inputs:
            assert v.def_op is not None or v in self.inputs, \
                f"{v.name} 既不是图输入也没有定义者"
        res = Value(result_name, result_type) if result_name is not None else None
        op = Op(name, inputs, res)
        self.ops.append(op)
        return op

    def set_outputs(self, values):
        self.ret = Op("func.return", list(values), None)
        self.ops.append(self.ret)

    def outputs(self):
        return list(self.ret.inputs)

    def body_ops(self):
        """除 func.return 外的算子（验收名单、代价账本、Verifier 都只看它们）。"""
        return [op for op in self.ops if op.alive and op.name != "func.return"]

    def op_names(self):
        return [op.name for op in self.body_ops()]

    def print_ir(self):
        lines = [f"func.func @{self.func_name}("
                 + ", ".join(f"{v.name}: {fmt_type(v.type)}"
                             for v in self.inputs) + ") -> ("
                 + ", ".join(fmt_type(v.type) for v in self.ret.inputs)
                 + ") {"]
        for op in self.ops:
            if not op.alive or op.name == "func.return":
                continue
            ops_fmt = ", ".join(v.name for v in op.inputs)
            lines.append(f"  {op.result.name} = {op.name} {ops_fmt} : "
                         + ", ".join(fmt_type(v.type) for v in op.inputs)
                         + f" -> {fmt_type(op.result.type)}")
        lines.append("  return " + ", ".join(v.name for v in self.ret.inputs))
        lines.append("}")
        return "\n".join(lines)


def fmt_type(vtype):
    shape = "x".join(str(d) for d in vtype[1])
    return f"tensor<{shape}x{vtype[2]}>"


class Rewriter:
    """对图的一切修改都必须通过 Rewriter，修改前后维护 use-def 完整性。"""

    def __init__(self, graph):
        self.graph = graph

    def create(self, name, inputs, insert_before, result_name, result_type):
        res = Value(result_name, result_type)
        op = Op(name, inputs, res)
        idx = self.graph.ops.index(insert_before)
        self.graph.ops.insert(idx, op)
        return op

    def replace_all_uses_with(self, old, new):
        # old 的每个使用者：把输入槽里的 old 换成 new
        for user in list(old.uses):
            user.inputs = [new if v is old else v for v in user.inputs]
            new.uses.append(user)
        old.uses = []

    def erase(self, op):
        # 前提（调用方保证）：op 结果的 use 表已空
        assert not op.result.uses, \
            f"{op.result.name} 还有 {len(op.result.uses)} 个使用者，不能删"
        for v in op.inputs:
            v.uses.remove(op)
        op.alive = False
        self.graph.ops.remove(op)


# ===================== 闸门一：Verifier（与 MLIR 版 MiniRules 同口径） =====================


def classify_bias_shape(bias_type, out_type):
    """bias 相对输出形状三分类（第 40/53 天口径）。"""
    if shape_of(bias_type) == shape_of(out_type):
        return "Same"
    bs, os_ = shape_of(bias_type), shape_of(out_type)
    if len(bs) == 1 and len(os_) > 0 and bs[0] == os_[-1]:
        return "BroadcastOnly"
    return "Mismatch"


def verify_matmul(op):
    lhs_t, rhs_t, res_t = (op.inputs[0].type, op.inputs[1].type,
                           op.result.type)
    for t in (lhs_t, rhs_t, res_t):
        if t[0] != "tensor":
            return f"{op.result.name}: 操作数与结果必须是 ranked tensor"
    if len(shape_of(lhs_t)) != 2 or len(shape_of(rhs_t)) != 2 \
            or len(shape_of(res_t)) != 2:
        return f"{op.result.name}: 本教程壳只支持 rank-2 张量"
    if any(dtype_of(t) != "f32" for t in (lhs_t, rhs_t, res_t)):
        return f"{op.result.name}: 元素类型必须是 f32"
    m, k = shape_of(lhs_t)
    k2, n = shape_of(rhs_t)
    if k != k2:
        return f"{op.result.name}: 内维不匹配: lhs 是 [{m},{k}]，rhs 是 [{k2},{n}]"
    if shape_of(res_t) != (m, n):
        return f"{op.result.name}: 结果 shape 应为 [{m},{n}]（跟 matmul 走）"
    return None


def verify_add_like(op):
    lhs_t, rhs_t = op.inputs[0].type, op.inputs[1].type
    for t in (lhs_t, rhs_t, op.result.type):
        if t[0] != "tensor":
            return f"{op.result.name}: 操作数必须是 ranked tensor"
    kind = classify_bias_shape(rhs_t, lhs_t)
    if kind == "BroadcastOnly":
        return (f"{op.result.name}: rhs shape 对 lhs 需要广播——"
                f"第 40 天起故意不支持（第 60 天放行）")
    if kind == "Mismatch":
        return f"{op.result.name}: 两个操作数 shape 不匹配"
    if op.result.type != lhs_t:
        return f"{op.result.name}: 结果类型必须等于 lhs 类型"
    return None


def verify_graph(g):
    """返回错误列表；空列表 = 通过。规则与 MLIR 版 Verifier 逐条对齐。"""
    errors = []
    for op in g.body_ops():
        err = None
        if op.name == "mini.matmul":
            err = verify_matmul(op)
        elif op.name in ("mini.add", "mini.fused_add_relu"):
            err = verify_add_like(op)
        elif op.name == "mini.relu":
            if op.inputs[0].type != op.result.type:
                err = f"{op.result.name}: relu 要求输入输出类型一致"
        elif op.name in ("mini.fused_matmul_bias",
                         "mini.fused_matmul_bias_relu"):
            err = verify_matmul(op)  # lhs/rhs/res 占前三个槽位语义
            if err is None:
                bias_t, res_t = op.inputs[2].type, op.result.type
                kind = classify_bias_shape(bias_t, res_t)
                if kind != "Same":
                    err = f"{op.result.name}: bias shape 与结果 shape 连广播都对不上"
        if err:
            errors.append(err)
    return errors


# ===================== 闸门二：Pattern（第 8 周收官管道） =====================


def _log(log, msg):
    if log is not None:
        log.append(msg)


def find_matmul_pair(add, log=None):
    """在 add 两侧找 (乘积, bias)。两侧都是 matmul 时拒绝（第 53 天判定）。"""
    lhs, rhs = add.inputs
    lmm = lhs.def_op.name == "mini.matmul" if lhs.def_op else False
    rmm = rhs.def_op.name == "mini.matmul" if rhs.def_op else False
    if lmm and rmm:
        _log(log, "  [拒绝] 匹配 Add：两侧都是 mini.matmul —— "
                  "分不清谁是 bias，拒绝融合")
        return None
    if not (lmm or rmm):
        return None                      # 没有链，安静返回（不是错误）
    mm = lhs.def_op if lmm else rhs.def_op
    bias = rhs if lmm else lhs           # 另一侧就是 bias，左右都认
    return (mm, bias)


def _all_f32(*values):
    return all(dtype_of(v.type) == "f32" for v in values)


def p3_direct(add, rw, log=None, type_guard=True):
    """P3（benefit 2, root add）：MatMul + Add (+Relu) 一步到位。"""
    pair = find_matmul_pair(add, log)
    if pair is None:
        return False
    mm, bias = pair
    m = mm.result
    if classify_bias_shape(bias.type, m.type) != "Same":
        _log(log, "  [P3] bias 形状非 Same -> 拒绝（第二道防线，Verifier 已拦过）")
        return False
    if type_guard and not _all_f32(mm.inputs[0], mm.inputs[1], bias):
        _log(log, "  [P3] 类型边界：元素类型非全 f32 -> 拒绝"
                  "（融合语义只对 f32 验证过）")
        return False
    if m.n_uses() != 1:
        _log(log, f"  [P3] 匹配 Add：乘积使用者 {m.n_uses()}"
                  " -> 拒绝（Day 52 规则），保留整条链")
        return False
    relu = None
    if add.result.has_one_use() and add.result.uses[0].name == "mini.relu":
        relu = add.result.uses[0]
    if relu is not None:
        fused = rw.create("mini.fused_matmul_bias_relu",
                          [mm.inputs[0], mm.inputs[1], bias],
                          add, add.result.name + "'",
                          m.type)
        rw.replace_all_uses_with(relu.result, fused.result)
        rw.erase(relu)
        rw.erase(add)
        rw.erase(mm)
        _log(log, "  [P3] 匹配 MatMul + Add + Relu -> fused_matmul_bias_relu"
                  "（直接三算子，一步到位）")
    else:
        fused = rw.create("mini.fused_matmul_bias",
                          [mm.inputs[0], mm.inputs[1], bias],
                          add, add.result.name + "'",
                          m.type)
        rw.replace_all_uses_with(add.result, fused.result)
        rw.erase(add)
        rw.erase(mm)
        _log(log, "  [P3] 匹配 MatMul + Add -> fused_matmul_bias"
                  "（%s 还有别的使用者时不吸收 Relu）" % add.result.name)
    return True


def p1_two_stage(add, rw, log=None, type_guard=True):
    """P1（benefit 1, root add）：两阶段第一步，只融前两个。"""
    pair = find_matmul_pair(add, log)
    if pair is None:
        return False
    mm, bias = pair
    m = mm.result
    if classify_bias_shape(bias.type, m.type) != "Same":
        return False
    if type_guard and not _all_f32(mm.inputs[0], mm.inputs[1], bias):
        return False
    if m.n_uses() != 1:
        _log(log, f"  [P1] 匹配 Add：乘积使用者 {m.n_uses()}"
                  " -> 拒绝（Day 52 规则），保留整条链")
        return False
    fused = rw.create("mini.fused_matmul_bias",
                      [mm.inputs[0], mm.inputs[1], bias],
                      add, add.result.name + "'", m.type)
    rw.replace_all_uses_with(add.result, fused.result)
    rw.erase(add)
    rw.erase(mm)
    _log(log, "  [P1] 匹配 MatMul + Add -> fused_matmul_bias"
              "（两阶段·第一步，Relu 原地不动）")
    return True


def p2_absorb(relu, rw, log=None):
    """P2（benefit 1, root relu）：吸收 epilogue。"""
    x = relu.inputs[0]
    if x.def_op is None or x.def_op.name != "mini.fused_matmul_bias":
        _log(log, f"  [P2] 访问 Relu：操作数由 "
                  f"{'图输入' if x.def_op is None else x.def_op.name}"
                  " 定义 -> 不匹配")
        return False
    if x.n_uses() != 1:
        _log(log, f"  [P2] 融合结果 {x.name} 有 {x.n_uses()}"
                  " 个使用者 -> 不能吸收 Relu")
        return False
    fm = x.def_op
    fused = rw.create("mini.fused_matmul_bias_relu", list(fm.inputs),
                      relu, relu.result.name + "'", x.type)
    rw.replace_all_uses_with(relu.result, fused.result)
    rw.erase(relu)
    rw.erase(fm)
    _log(log, "  [P2] fused_matmul_bias + relu -> fused_matmul_bias_relu"
              "（两阶段·第二步，epilogue 吸收）")
    return True


def p51g_small(relu, rw, log=None, type_guard=True):
    """P51g（benefit 1, root relu）：Add + Relu 小融合，带两条收手：
    让位规则（add 操作数是乘积就让给大融合）＋类型边界（只融 f32）。"""
    x = relu.inputs[0]
    if x.def_op is None or x.def_op.name != "mini.add" or not x.has_one_use():
        return False
    ad = x.def_op
    if any(v.def_op is not None and v.def_op.name == "mini.matmul"
           for v in ad.inputs):
        _log(log, "  [P51g] add 的操作数之一是 matmul 乘积 -> "
                  "让位给更大的融合（MatMul+Bias 系），本次不抢")
        return False
    if type_guard and not _all_f32(ad.inputs[0], ad.inputs[1]):
        _log(log, "  [P51g] 类型边界：元素类型非 f32 -> 拒绝"
                  "（fused_add_relu 的语义只对 f32 验证过）")
        return False
    fused = rw.create("mini.fused_add_relu", list(ad.inputs),
                      relu, relu.result.name + "'", x.type)
    rw.replace_all_uses_with(relu.result, fused.result)
    rw.erase(relu)
    rw.erase(ad)
    _log(log, "  [P51g] 匹配 Add + Relu -> fused_add_relu"
              "（Add+Relu 小融合）")
    return True


def run_pipeline(g, order="bottom-up", log=None, type_guard=True):
    """贪心驱动到不动点。order 只改变访问顺序（Day 54 的唯一随机性来源）。"""
    roots = {
        "mini.add": [("P3", 2, p3_direct), ("P1", 1, p1_two_stage)],
        "mini.relu": [("P2", 1, p2_absorb), ("P51g", 1, p51g_small)],
    }
    rw = Rewriter(g)
    while True:
        changed = False
        seq = [op for op in g.ops if op.alive]
        if order == "bottom-up":
            seq = seq[::-1]             # 消费者先（程序序逆序）
        for op in seq:
            if not op.alive:
                continue
            for tag, _benefit, fn in roots.get(op.name, []):
                kw = {"type_guard": type_guard} if fn in (p3_direct,
                                                          p1_two_stage,
                                                          p51g_small) else {}
                if fn(op, rw, log, **kw):
                    changed = True
                    break
            if changed:
                break                    # 改写后从头复查（重复匹配）
        if not changed:
            return


# ===================== 闸门三：数值语义与代价账本（第 53 天口径） =====================

SEMANTICS = {
    "mini.matmul": lambda xs: xs[0] @ xs[1],
    "mini.add": lambda xs: xs[0] + xs[1],
    "mini.relu": lambda xs: np.maximum(xs[0], 0.0),
    "mini.fused_add_relu": lambda xs: np.maximum(xs[0] + xs[1], 0.0),
    "mini.fused_matmul_bias": lambda xs: xs[0] @ xs[1] + xs[2],
    "mini.fused_matmul_bias_relu": lambda xs: np.maximum(xs[0] @ xs[1] + xs[2], 0.0),
}


def _prod(shape):
    n = 1
    for d in shape:
        n *= d
    return n


def op_cost(op):
    """玩具代价模型：整张张量读/写遍数（Day 53/54 口径）。
      matmul 读 2 写 1 = 3；add/fused_add_relu 读 2 写 1 = 3；
      relu 读 1 写 1 = 2；fused_mm_bias(_relu) 读 3 写 1 = 4。"""
    n_in = len(op.inputs)
    if op.name == "mini.matmul":
        return 3
    if op.name in ("mini.add", "mini.fused_add_relu"):
        return 3
    if op.name == "mini.relu":
        return 2
    if op.name in ("mini.fused_matmul_bias", "mini.fused_matmul_bias_relu"):
        return 4
    raise KeyError(op.name)


def count_cost(g):
    return sum(op_cost(op) for op in g.body_ops())


def evaluate(g, feed):
    """按程序序求值，返回与 return 一一对应的输出列表（位置对齐）。"""
    env = {v.name: feed[v.name] for v in g.inputs}
    for op in g.ops:
        if not op.alive or op.name == "func.return":
            continue
        env[op.result.name] = SEMANTICS[op.name]([env[v.name] for v in op.inputs])
    return [env[v.name] for v in g.outputs()]


# ===================== 验收语料：14 个用例 =====================

FEED = {
    "%a": np.array([[1.0, -2.0, 3.0], [-4.0, 5.0, -6.0]]),    # 2x3
    "%b": np.array([[1.0, 0.0], [-1.0, 2.0], [3.0, -3.0]]),   # 3x2
    "%bias": np.array([[10.0, -10.0], [20.0, -20.0]]),        # 2x2
    "%c": np.array([[2.0, -1.0, 0.5], [0.0, 3.0, 1.0]]),      # 2x3（第二条链）
    "%d": np.array([[1.0, 1.0], [0.0, -2.0], [1.0, 1.0]]),    # 3x2
    "%a2": np.array([[1.0, -2.0], [3.0, -4.0]]),              # 2x2（第 52 天同款）
    "%b2": np.array([[0.5, 0.5], [-1.0, 2.0]]),               # 2x2（第 52 天同款）
    "%x": np.array([[1.5, -0.5], [-2.0, 4.0]]),               # 2x2（f64 用）
    "%y": np.array([[0.25, 2.0], [1.0, -3.0]]),               # 2x2（f64 用）
    "%v1": np.array([[10.0, -10.0]]),                         # 1x2（错秩）
    "%v2": np.array([10.0, -10.0]),                           # 2（[N] 向量）
}


def _mm(g, a, b, name):
    return g.create_op("mini.matmul", [a, b], name, tt(2, 2))


def build_c01():
    """正例：主线 MatMul -> Add(bias) -> Relu，全部单使用者。"""
    g = Graph("bias_relu")
    a, b, bias = g.add_input("%a", tt(2, 3)), g.add_input("%b", tt(3, 2)), \
        g.add_input("%bias", tt(2, 2))
    m = _mm(g, a, b, "%m")
    s = g.create_op("mini.add", [m.result, bias], "%s", tt(2, 2))
    r = g.create_op("mini.relu", [s.result], "%r", tt(2, 2))
    g.set_outputs([r.result])
    return g


def build_c02():
    """正例：MatMul -> Add(bias)，没有 Relu。"""
    g = Graph("bias_only")
    a, b, bias = g.add_input("%a", tt(2, 3)), g.add_input("%b", tt(3, 2)), \
        g.add_input("%bias", tt(2, 2))
    m = _mm(g, a, b, "%m")
    s = g.create_op("mini.add", [m.result, bias], "%s", tt(2, 2))
    g.set_outputs([s.result])
    return g


def build_c03():
    """正例：纯 Add + Relu（小融合的主场，输入是第 52 天同款 2x2）。"""
    g = Graph("add_relu_only")
    a, b = g.add_input("%a2", tt(2, 2)), g.add_input("%b2", tt(2, 2))
    s = g.create_op("mini.add", [a, b], "%s", tt(2, 2))
    r = g.create_op("mini.relu", [s.result], "%r", tt(2, 2))
    g.set_outputs([r.result])
    return g


def build_c04():
    """正例：bias 写在左边 mini.add %bias, %m —— Pattern 左右都得认。"""
    g = Graph("bias_on_left")
    a, b, bias = g.add_input("%a", tt(2, 3)), g.add_input("%b", tt(3, 2)), \
        g.add_input("%bias", tt(2, 2))
    m = _mm(g, a, b, "%m")
    s = g.create_op("mini.add", [bias, m.result], "%s", tt(2, 2))
    r = g.create_op("mini.relu", [s.result], "%r", tt(2, 2))
    g.set_outputs([r.result])
    return g


def build_c05():
    """假负例：relu 结果被 return 和第二个 add 同时使用。
    被擦除的是 relu 自己，它的结果多使用不妨碍融合（replaceAllUses 迁移）。"""
    g = Graph("relu_out_multi")
    a, b, bias = g.add_input("%a", tt(2, 3)), g.add_input("%b", tt(3, 2)), \
        g.add_input("%bias", tt(2, 2))
    m = _mm(g, a, b, "%m")
    s = g.create_op("mini.add", [m.result, bias], "%s", tt(2, 2))
    r = g.create_op("mini.relu", [s.result], "%r", tt(2, 2))
    s2 = g.create_op("mini.add", [r.result, bias], "%s2", tt(2, 2))
    g.set_outputs([r.result, s2.result])
    return g


def build_c06():
    """假负例：bias 同时喂两条独立的 MatMul 链。
    bias 是操作数不是被删生产者——操作数共享从来不妨碍融合。"""
    g = Graph("bias_shared")
    a, b = g.add_input("%a", tt(2, 3)), g.add_input("%b", tt(3, 2))
    c, d = g.add_input("%c", tt(2, 3)), g.add_input("%d", tt(3, 2))
    bias = g.add_input("%bias", tt(2, 2))
    m1 = _mm(g, a, b, "%m1")
    m2 = g.create_op("mini.matmul", [c, d], "%m2", tt(2, 2))
    s1 = g.create_op("mini.add", [m1.result, bias], "%s1", tt(2, 2))
    s2 = g.create_op("mini.add", [m2.result, bias], "%s2", tt(2, 2))
    g.set_outputs([s1.result, s2.result])
    return g


def build_c07():
    """负例（多使用者·乘积）：%m 被 add 和另一个 relu 同时使用。"""
    g = Graph("multi_product")
    a, b, bias = g.add_input("%a", tt(2, 3)), g.add_input("%b", tt(3, 2)), \
        g.add_input("%bias", tt(2, 2))
    m = _mm(g, a, b, "%m")
    s = g.create_op("mini.add", [m.result, bias], "%s", tt(2, 2))
    r = g.create_op("mini.relu", [s.result], "%r", tt(2, 2))
    t = g.create_op("mini.relu", [m.result], "%t", tt(2, 2))
    g.set_outputs([r.result, t.result])
    return g


def build_c08():
    """负例（额外使用约束·%s 共用）：加法结果被 relu 和 return 同时使用。
    正确形态是半融合：fused_matmul_bias + relu（不是拒绝，也不是三合一）。"""
    g = Graph("shared_result")
    a, b, bias = g.add_input("%a", tt(2, 3)), g.add_input("%b", tt(3, 2)), \
        g.add_input("%bias", tt(2, 2))
    m = _mm(g, a, b, "%m")
    s = g.create_op("mini.add", [m.result, bias], "%s", tt(2, 2))
    r = g.create_op("mini.relu", [s.result], "%r", tt(2, 2))
    g.set_outputs([r.result, s.result])
    return g


def build_c09():
    """负例（类型不支持·f64）：add/relu 对 f64 结构合法（Verifier 只查形状），
    但融合语义只对 f32 验证过——Pattern 的类型边界必须收手。"""
    g = Graph("f64_add_relu")
    x, y = g.add_input("%x", tt(2, 2, dtype="f64")), g.add_input("%y", tt(2, 2, dtype="f64"))
    s = g.create_op("mini.add", [x, y], "%s", tt(2, 2, dtype="f64"))
    r = g.create_op("mini.relu", [s.result], "%r", tt(2, 2, dtype="f64"))
    g.set_outputs([r.result])
    return g


def build_c10():
    """负例（歧义）：add 两侧都是 matmul 乘积——分不清谁是 bias。"""
    g = Graph("both_matmul")
    a, b = g.add_input("%a", tt(2, 3)), g.add_input("%b", tt(3, 2))
    c, d = g.add_input("%c", tt(2, 3)), g.add_input("%d", tt(3, 2))
    m1 = _mm(g, a, b, "%m1")
    m2 = g.create_op("mini.matmul", [c, d], "%m2", tt(2, 2))
    s = g.create_op("mini.add", [m1.result, m2.result], "%s", tt(2, 2))
    g.set_outputs([s.result])
    return g


def build_c11():
    """负例（类型不支持·混合 dtype）：f32 乘积 + f64 bias。
    mini.add 的 Verifier 只比形状（Same 放行），但「f32 结果 ← f64 加数」
    的语义从没定义过——唯一挡得住的是 Pattern 的类型边界。"""
    g = Graph("mixed_dtype")
    a, b = g.add_input("%a", tt(2, 3)), g.add_input("%b", tt(3, 2))
    y = g.add_input("%y", tt(2, 2, dtype="f64"))
    m = _mm(g, a, b, "%m")
    s = g.create_op("mini.add", [m.result, y], "%s", tt(2, 2))
    r = g.create_op("mini.relu", [s.result], "%r", tt(2, 2))
    g.set_outputs([r.result])
    return g


def build_c12():
    """Verifier 层负例（Shape 不兼容·Mismatch）：bias 是 1x2，连广播都对不上。"""
    g = Graph("bad_bias_mismatch")
    a, b = g.add_input("%a", tt(2, 3)), g.add_input("%b", tt(3, 2))
    v1 = g.add_input("%v1", tt(1, 2))
    m = _mm(g, a, b, "%m")
    s = g.create_op("mini.add", [m.result, v1], "%s", tt(2, 2))
    r = g.create_op("mini.relu", [s.result], "%r", tt(2, 2))
    g.set_outputs([r.result])
    return g


def build_c13():
    """Verifier 层负例（Shape 不兼容·BroadcastOnly）：bias 是 [2] 向量，
    第 60 天学 Broadcast 之前故意不放行。"""
    g = Graph("bad_bias_broadcast")
    a, b = g.add_input("%a", tt(2, 3)), g.add_input("%b", tt(3, 2))
    v2 = g.add_input("%v2", tt(2))
    m = _mm(g, a, b, "%m")
    s = g.create_op("mini.add", [m.result, v2], "%s", tt(2, 2))
    r = g.create_op("mini.relu", [s.result], "%r", tt(2, 2))
    g.set_outputs([r.result])
    return g


def build_c14():
    """Verifier 层负例（类型不支持·f64 matmul）：matmul 只收 f32。"""
    g = Graph("f64_matmul")
    x = g.add_input("%x", tt(2, 2, dtype="f64"))
    y = g.add_input("%y", tt(2, 2, dtype="f64"))
    m = g.create_op("mini.matmul", [x, y], "%m", tt(2, 2, dtype="f64"))
    s = g.create_op("mini.add", [m.result, y], "%s", tt(2, 2, dtype="f64"))
    g.set_outputs([s.result])
    return g


CASES = [
    # (编号, 名称, 类别, 构造器, 期望判决, 期望最终算子名单)
    ("C01", "bias_relu",          "正例", build_c01,
     "fused", ["mini.fused_matmul_bias_relu"]),
    ("C02", "bias_only",          "正例", build_c02,
     "fused", ["mini.fused_matmul_bias"]),
    ("C03", "add_relu_only",      "正例", build_c03,
     "fused", ["mini.fused_add_relu"]),
    ("C04", "bias_on_left_relu",  "正例", build_c04,
     "fused", ["mini.fused_matmul_bias_relu"]),
    ("C05", "relu_out_multi",     "假负例", build_c05,
     "fused", ["mini.add", "mini.fused_matmul_bias_relu"]),
    ("C06", "bias_shared_2chains", "假负例", build_c06,
     "fused", ["mini.fused_matmul_bias", "mini.fused_matmul_bias"]),
    ("C07", "multi_user_product", "负例·多使用者", build_c07,
     "identity", None),
    ("C08", "shared_result",      "负例·额外使用", build_c08,
     "fused", ["mini.fused_matmul_bias", "mini.relu"]),
    ("C09", "f64_add_relu",       "负例·类型不支持", build_c09,
     "identity", None),
    ("C10", "both_matmul",        "负例·歧义", build_c10,
     "identity", None),
    ("C11", "mixed_dtype_bias",   "负例·类型不支持", build_c11,
     "identity", None),
    ("C12", "bad_bias_shape",     "负例·Shape(Verifier)", build_c12,
     "verifier_reject", None),
    ("C13", "bad_bias_broadcast", "负例·Shape(Verifier)", build_c13,
     "verifier_reject", None),
    ("C14", "f64_matmul_chain",   "负例·类型(Verifier)", build_c14,
     "verifier_reject", None),
]


# ===================== 验收器：三道闸门逐条判 =====================


def run_one_case(case, type_guard=True, verbose=False):
    """跑一个用例，返回 (记录 dict, 是否通过)。"""
    cid, name, cat, build, expect_kind, expect_ops = case
    rec = {"id": cid, "name": name, "cat": cat, "expect": expect_kind,
           "checks": [], "log": []}
    ok = True

    def check(cond, desc):
        nonlocal ok
        rec["checks"].append((bool(cond), desc))
        ok &= bool(cond)

    g0 = build()
    pre_ir = g0.print_ir()
    pre_ops = g0.op_names()
    pre_cost = count_cost(g0)
    rec["pre_ops"] = pre_ops
    rec["pre_cost"] = pre_cost

    # ---- 闸门一：Verifier ----
    errors = verify_graph(g0)
    rec["verify_errors"] = errors
    if errors:
        check(expect_kind == "verifier_reject",
              f"Verifier 拦下 {len(errors)} 条错误，期望判决 = {expect_kind}")
        rec["got"] = "verifier_reject"
        # R4：关掉 Verifier 复跑，第二道防线必须仍然拦下（恒等）
        gb = build()
        log = rec["log"] if verbose else None
        run_pipeline(gb, order="bottom-up", log=log, type_guard=type_guard)
        check(gb.print_ir() == pre_ir,
              "绕过 Verifier 后 Pattern 第二道防线仍拦下（IR 恒等）")
        rec["bypass_ops"] = gb.op_names()
        rec["post_cost"] = count_cost(gb)
        return rec, ok

    # ---- 闸门二：Pattern（两种遍历方向）----
    g1, g2 = build(), build()
    log1 = rec["log"] if verbose else None
    run_pipeline(g1, order="bottom-up", log=log1, type_guard=type_guard)
    run_pipeline(g2, order="top-down", log=None, type_guard=type_guard)
    ir1, ir2 = g1.print_ir(), g2.print_ir()
    ops1, ops2 = g1.op_names(), g2.op_names()
    rec["got"] = "fused" if ops1 != pre_ops else "identity"
    rec["post_ops"] = ops1
    rec["post_cost"] = count_cost(g1)

    # R1：两种遍历必须殊途同归（Day 54 的教训写成断言）
    check(ir1 == ir2, "R1 双遍历同形态（bottom-up == top-down）")
    # R2：负例必须是恒等拒绝（IR 逐字不变）
    if expect_kind == "identity":
        check(ir1 == pre_ir, "R2 恒等拒绝：IR 逐字不变")
        check(count_cost(g1) == pre_cost, "R2 恒等拒绝：代价账本不变")
    else:
        check(sorted(ops1) == sorted(expect_ops),
              f"R1 最终算子名单 == 期望 {sorted(expect_ops)}")
    check(rec["got"] == expect_kind, f"判决符合期望（{rec['got']} == {expect_kind}）")
    # 融合后必须仍通过 Verifier
    check(not verify_graph(g1), "融合后 Verifier 复查通过")

    # ---- 闸门三：数值对账（按 return 位置对齐）----
    ref_out = evaluate(g0, FEED)
    new_out = evaluate(g1, FEED)
    same = (len(ref_out) == len(new_out)
            and all(np.allclose(a, b) for a, b in zip(ref_out, new_out)))
    check(same, "R3 数值对账：融合前后所有输出一致")
    rec["numeric_ok"] = same
    return rec, ok


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--case", default=None, help="只跑指定编号，如 C08")
    ap.add_argument("--no-type-guard", action="store_true",
                    help="对照实验：拆掉 Pattern 的类型闸门")
    args = ap.parse_args()

    cases = [c for c in CASES if args.case is None or c[0] == args.case]
    if not cases:
        print(f"没有编号为 {args.case} 的用例；可用：",
              ", ".join(c[0] for c in CASES))
        return 1

    print("=" * 78)
    print("第 55 天融合负例总验收（Python 层）"
          + ("  [类型闸门已拆除！]" if args.no_type_guard else ""))
    print("=" * 78)
    all_ok = True
    for case in cases:
        rec, ok = run_one_case(case, type_guard=not args.no_type_guard,
                               verbose=True)
        all_ok &= ok
        print(f"\n--- {rec['id']} {rec['name']}（{rec['cat']}）"
              f"  期望 = {rec['expect']}")
        for line in rec["log"]:
            print(line)
        if rec["verify_errors"]:
            for e in rec["verify_errors"]:
                print(f"  [Verifier] {e}")
        print(f"  融合前算子: {rec['pre_ops']}  遍数 = {rec['pre_cost']}")
        print(f"  融合后算子: {rec.get('post_ops', rec['pre_ops'])}"
              f"  遍数 = {rec.get('post_cost', rec['pre_cost'])}")
        for good, desc in rec["checks"]:
            print(f"  [{'PASS' if good else 'FAIL'}] {desc}")

    print("\n" + "=" * 78)
    print(f"{'用例':<6}{'名称':<22}{'类别':<18}{'期望':<17}{'实测':<17}{'遍数':<10}{'判定'}")
    n_pass = 0
    for case in cases:
        rec, ok = run_one_case(case, type_guard=not args.no_type_guard)
        if ok:
            n_pass += 1
        cost = f"{rec['pre_cost']}->{rec.get('post_cost', rec['pre_cost'])}"
        print(f"{rec['id']:<6}{rec['name']:<22}{rec['cat']:<18}"
              f"{rec['expect']:<17}{rec['got']:<17}{cost:<10}"
              f"{'通过' if ok else '失败'}")
    print("=" * 78)
    print(f"汇总: {n_pass}/{len(cases)} 通过"
          + ("，全部通过 ✔" if n_pass == len(cases) else "，存在失败 ✘"))
    return 0 if all_ok and n_pass == len(cases) else 1


if __name__ == "__main__":
    sys.exit(main())
