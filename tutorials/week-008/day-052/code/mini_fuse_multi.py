"""mini_fuse_multi.py —— 第 52 天核心示例：融合的多使用者限制与处理策略。

在第 51 天的迷你图 IR / Rewriter（带 use-def 完整性检查）基础上，
把融合 Pattern 遇到「中间结果多使用者」时的处理拆成四种策略：

  reject       （默认）中间结果多使用者时拒绝融合，图保持原样
  keep         融合 Relu 分支、保留 mini.add 给其他使用者
               —— 合法，但 Add 在融合分支里被重复计算一次
  rewire-t     （错误示范）把 %t 的其他使用者改接到融合结果
               —— 图结构合法、数值语义悄悄改变
  erase-anyway （错误示范）不做检查直接删生产者
               —— Rewriter 的完整性检查当场报错

运行: python3 mini_fuse_multi.py
依赖: numpy（仅用于数值验证）
"""

import numpy as np


# ===================== 迷你 IR：Value / Op / Graph =====================

class Value:
    """一个 SSA 值：由某个算子定义（def_op），或作为图的输入（def_op=None）。"""

    def __init__(self, name, vtype, def_op=None):
        self.name = name          # 例如 "%t"
        self.type = vtype         # 例如 "tensor<2x2xf32>"
        self.def_op = def_op      # 定义该值的算子；图输入为 None
        self.uses = []            # [(使用者 Op, 操作数下标), ...]

    def has_one_use(self):
        return len(self.uses) == 1


class Op:
    """一个算子：名字 + 操作数列表 + 唯一结果（mini.return 没有结果）。"""

    def __init__(self, name, inputs, result=None):
        self.name = name          # 例如 "mini.add"
        self.inputs = list(inputs)
        self.result = result      # Value；return 算子为 None


class Graph:
    """函数级计算图：输入、按拓扑序排列的算子、一个 return 算子。

    和 MLIR 的 func/return 一样，return 是一个真实算子：
    它和其他算子一样登记 use-def，因此“图输出也是一种使用者”自动成立。
    """

    def __init__(self, func_name):
        self.func_name = func_name
        self.inputs = []
        self.ops = []             # 不含 return
        self.return_op = None

    def add_input(self, name, vtype):
        v = Value(name, vtype, def_op=None)
        self.inputs.append(v)
        return v

    def create_op(self, name, inputs, result_name):
        result = Value(result_name, inputs[0].type, def_op=None)
        op = Op(name, inputs, result)
        result.def_op = op
        for i, v in enumerate(inputs):
            v.uses.append((op, i))
        self.ops.append(op)
        return op

    def set_outputs(self, values):
        """创建 mini.return；它作为普通算子登记使用关系。"""
        self.return_op = Op("mini.return", values)
        for i, v in enumerate(values):
            v.uses.append((self.return_op, i))

    @property
    def outputs(self):
        return self.return_op.inputs

    def print_ir(self):
        args = ", ".join(f"{v.name}: {v.type}" for v in self.inputs)
        rets = ", ".join(v.type for v in self.outputs)
        print(f"func @{self.func_name}({args}) -> ({rets}) {{")
        for op in self.ops:
            ins = ", ".join(v.name for v in op.inputs)
            print(f"  {op.result.name} = {op.name} {ins} : {op.result.type}")
        outs = ", ".join(v.name for v in self.outputs)
        print(f"  return {outs}")
        print("}")


# ===================== Rewriter：所有修改的必经之路 =====================

class Rewriter:
    """对图的一切修改都必须通过 Rewriter，修改前后维护 use-def 完整性。"""

    def __init__(self, graph):
        self.graph = graph

    def create(self, name, inputs, insert_before=None, result_name=None):
        result_name = result_name or f"%f{len(self.graph.ops)}"
        op = self.graph.create_op(name, inputs, result_name)
        if insert_before is not None:
            self.graph.ops.remove(op)
            pos = self.graph.ops.index(insert_before)
            self.graph.ops.insert(pos, op)
        return op

    def replace_all_uses_with(self, old, new):
        # 把 old 的每一处使用（包括 return 算子）改接到 new
        for user, idx in old.uses:
            user.inputs[idx] = new
            new.uses.append((user, idx))
        old.uses = []

    def erase(self, op):
        # 擦除前必须保证结果已无任何使用者，否则使用者会得到悬空引用
        if op.result is not None and op.result.uses:
            raise RuntimeError(
                f"不能擦除 {op.name}：结果 {op.result.name} "
                f"仍有 {len(op.result.uses)} 处使用者")
        for i, v in enumerate(op.inputs):
            v.uses = [u for u in v.uses if u[0] is not op]
        self.graph.ops.remove(op)


# ===================== 今天的核心：带策略的融合 Pattern =====================

POLICIES = ("reject", "keep", "rewire-t", "erase-anyway")


def fuse_add_relu_pattern(relu, rw, policy="reject"):
    """匹配 mini.relu；其输入由 mini.add 定义时，按 policy 处理多使用者。"""
    t = relu.inputs[0]
    add = t.def_op
    if add is None or add.name != "mini.add":   # 不是 Add -> Relu 链
        return False
    single_use = t.has_one_use()                 # 先记录：改写之后会变

    if policy == "erase-anyway":
        # 错误示范：不看使用者数量就删生产者（Rewriter 会当场拦下）
        fused = rw.create("mini.fused_add_relu", add.inputs,
                          insert_before=relu, result_name=relu.result.name + "'")
        rw.replace_all_uses_with(relu.result, fused.result)
        rw.erase(relu)
        rw.erase(add)        # 多使用者时这里抛 RuntimeError
        return True

    if policy == "reject" and not single_use:
        return False         # 保守策略：这块图不归我管，保持原样

    # 单使用者：与第 51 天完全相同的四步
    # 多使用者 + keep：融合 Relu 分支，但保留 mini.add
    # 多使用者 + rewire-t：错误示范，把 %t 的其他使用者改接到融合结果
    fused = rw.create("mini.fused_add_relu", add.inputs,
                      insert_before=relu, result_name=relu.result.name + "'")
    rw.replace_all_uses_with(relu.result, fused.result)
    rw.erase(relu)          # 先擦消费者
    if single_use:
        rw.erase(add)       # 中间结果独占：生产者一并删除
    elif policy == "keep":
        pass                # 多使用者：保留 mini.add，%t 继续喂给其他使用者
    else:                   # policy == "rewire-t"
        rw.replace_all_uses_with(t, fused.result)   # 其他使用者拿到 relu(a+b)！
        rw.erase(add)
    return True


def run_fusion(graph, policy="reject"):
    """贪心驱动：反复扫描，直到一轮下来没有任何 Pattern 命中（不动点）。"""
    rw = Rewriter(graph)
    changed_any = False
    while True:
        changed = False
        for op in [o for o in graph.ops if o.name == "mini.relu"]:
            if fuse_add_relu_pattern(op, rw, policy):
                changed = True
                break               # 图结构变了，从头重扫，简单且安全
        changed_any |= changed
        if not changed:
            return changed_any


# ===================== 数值语义、求值与代价估算 =====================

SEMANTICS = {
    "mini.add": lambda xs: xs[0] + xs[1],
    "mini.relu": lambda xs: np.maximum(xs[0], 0.0),
    "mini.fused_add_relu": lambda xs: np.maximum(xs[0] + xs[1], 0.0),
}

# 玩具代价模型：整张 tensor 读 / 写一次各计 1 个「张量遍数」；
# fused_add_relu 里那一次加法算 1 次「加法执行」。
OP_COST = {
    "mini.add":              {"add": 1, "tensor_passes": 3},  # 读 2 写 1
    "mini.relu":             {"add": 0, "tensor_passes": 2},  # 读 1 写 1
    "mini.fused_add_relu":   {"add": 1, "tensor_passes": 3},  # 读 2 写 1
}


def evaluate(graph, feed):
    """按拓扑序求值，返回 (值名 -> ndarray) 的字典。"""
    env = {v.name: feed[v.name] for v in graph.inputs}
    for op in graph.ops:
        env[op.result.name] = SEMANTICS[op.name]([env[v.name] for v in op.inputs])
    return env


def count_cost(graph):
    """返回 (加法执行次数, 张量读写遍数)。估算口径见 OP_COST 注释。"""
    add_calls = sum(OP_COST[op.name]["add"] for op in graph.ops)
    passes = sum(OP_COST[op.name]["tensor_passes"] for op in graph.ops)
    return add_calls, passes


# ===================== 演示主程序 =====================

def build_multi_user_graph():
    """%t 有两个使用者：mini.relu 和第二个 mini.add —— 今天的反例图。"""
    g = Graph("multi")
    va = g.add_input("%a", "tensor<2x2xf32>")
    vb = g.add_input("%b", "tensor<2x2xf32>")
    vc = g.add_input("%c", "tensor<2x2xf32>")
    t = g.create_op("mini.add", [va, vb], "%t")
    r = g.create_op("mini.relu", [t.result], "%r")
    g.create_op("mini.add", [t.result, vc], "%s")
    g.set_outputs([r.result, g.ops[-1].result])
    return g


def build_single_user_graph():
    """对照：%t 只有一个使用者，第 51 天的正例。"""
    g = Graph("single")
    va = g.add_input("%a", "tensor<2x2xf32>")
    vb = g.add_input("%b", "tensor<2x2xf32>")
    g.create_op("mini.add", [va, vb], "%t")
    g.create_op("mini.relu", [g.ops[-1].result], "%r")
    g.set_outputs([g.ops[-1].result])
    return g


FEED = {
    "%a": np.array([[1.0, -2.0], [3.0, -4.0]]),
    "%b": np.array([[0.5, 0.5], [-1.0, 2.0]]),
    "%c": np.array([[10.0, 10.0], [10.0, 10.0]]),
}


def run_policy_and_report(policy):
    g = build_multi_user_graph()
    print(f"\n===== 策略 {policy} =====")
    run_fusion(g, policy)
    g.print_ir()
    out = evaluate(g, FEED)
    add_calls, passes = count_cost(g)
    print(f"加法执行次数 = {add_calls}，张量读写遍数 = {passes}")

    ref_r = np.maximum(FEED["%a"] + FEED["%b"], 0.0)
    ref_s = FEED["%a"] + FEED["%b"] + FEED["%c"]
    r_name, s_name = g.outputs[0].name, g.outputs[1].name
    ok_r = np.allclose(out[r_name], ref_r)
    ok_s = np.allclose(out[s_name], ref_s)
    print(f"{r_name} = {out[r_name].tolist()}   期望 {ref_r.tolist()}   {'一致' if ok_r else '不一致!'}")
    print(f"{s_name} = {out[s_name].tolist()}   期望 {ref_s.tolist()}   {'一致' if ok_s else '不一致!'}")
    return ok_r and ok_s


def main():
    g = build_multi_user_graph()
    print("===== 融合前 IR（%t 有 2 个使用者）=====")
    g.print_ir()
    ref = evaluate(g, FEED)
    print(f"参考结果 %r = {ref['%r'].tolist()}，%s = {ref['%s'].tolist()}")
    add_calls, passes = count_cost(g)
    print(f"加法执行次数 = {add_calls}，张量读写遍数 = {passes}")

    results = {}
    for policy in ("reject", "keep", "rewire-t"):
        results[policy] = run_policy_and_report(policy)

    print("\n===== 错误示范：不做检查直接删生产者（erase-anyway）=====")
    g2 = build_multi_user_graph()
    try:
        run_fusion(g2, policy="erase-anyway")
    except RuntimeError as e:
        print(f"Rewriter 拦截：{e}")
    else:
        raise AssertionError("erase-anyway 本应被 Rewriter 拦截")

    print("\n===== 结论 =====")
    print("reject  ：图未变，语义必然不变（默认策略）")
    print("keep    ：语义不变，但融合分支的加法算了 2 次（全图 2→3 次）—— 合法 ≠ 有收益")
    print("rewire-t：%s 的输入被改接到融合结果，语义悄悄改变" % "%s")
    print("          —— 坏在图结构完全合法，verify 也发现不了")
    ok = {k: v for k, v in results.items()}
    print(f"数值一致性：{ok}")


if __name__ == "__main__":
    main()
