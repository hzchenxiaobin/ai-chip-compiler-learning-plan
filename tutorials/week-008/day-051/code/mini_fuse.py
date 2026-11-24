"""mini_fuse.py —— 第 51 天热身示例：用 ~180 行 Python 复刻 Add+Relu 融合机制。

包含：迷你 SSA 图 IR（带 use-def 关系）、Rewriter（带完整性检查）、
融合 Pattern，以及用 numpy 验证融合前后数值一致的演示。

运行: python3 mini_fuse.py
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


# ===================== 今天的融合 Pattern =====================

def fuse_add_relu_pattern(relu, rw):
    """匹配 mini.relu，若其输入由 mini.add 定义且中间结果单使用者，则融合。"""
    t = relu.inputs[0]
    add = t.def_op
    if add is None or add.name != "mini.add":   # 不是 Add -> Relu 链
        return False
    if not t.has_one_use():                     # 多使用者：第 52 天再处理
        return False

    fused = rw.create("mini.fused_add_relu", add.inputs,
                      insert_before=relu, result_name=relu.result.name + "'")
    rw.replace_all_uses_with(relu.result, fused.result)
    rw.erase(relu)      # 先擦消费者
    rw.erase(add)       # 再擦生产者
    return True


def run_fusion(graph):
    """贪心驱动：反复扫描，直到一轮下来没有任何 Pattern 命中（不动点）。"""
    rw = Rewriter(graph)
    changed_any = False
    while True:
        changed = False
        for op in [o for o in graph.ops if o.name == "mini.relu"]:
            if fuse_add_relu_pattern(op, rw):
                changed = True
                break               # 图结构变了，从头重扫，简单且安全
        changed_any |= changed
        if not changed:
            return changed_any


# ===================== 数值语义与求值 =====================

SEMANTICS = {
    "mini.add": lambda xs: xs[0] + xs[1],
    "mini.relu": lambda xs: np.maximum(xs[0], 0.0),
    "mini.fused_add_relu": lambda xs: np.maximum(xs[0] + xs[1], 0.0),
}


def evaluate(graph, feed):
    """按拓扑序求值，返回 (值名 -> ndarray) 的字典。"""
    env = {v.name: feed[v.name] for v in graph.inputs}
    for op in graph.ops:
        env[op.result.name] = SEMANTICS[op.name]([env[v.name] for v in op.inputs])
    return env


# ===================== 演示主程序 =====================

def build_demo_graph():
    g = Graph("demo")
    va = g.add_input("%a", "tensor<2x2xf32>")
    vb = g.add_input("%b", "tensor<2x2xf32>")
    g.create_op("mini.add", [va, vb], "%t")
    g.create_op("mini.relu", [g.ops[-1].result], "%r")
    g.set_outputs([g.ops[-1].result])
    return g


def main():
    feed = {
        "%a": np.array([[1.0, -2.0], [3.0, -4.0]]),
        "%b": np.array([[0.5, 0.5], [-1.0, 2.0]]),
    }

    g = build_demo_graph()
    print("===== 融合前 IR =====")
    g.print_ir()
    before = evaluate(g, feed)
    print("融合前 %r =", before["%r"].tolist())

    run_fusion(g)
    print("\n===== 融合后 IR =====")
    g.print_ir()
    after = evaluate(g, feed)
    print("融合后 %r' =", after["%r'"].tolist())

    assert np.allclose(before["%r"], after["%r'"]), "融合改变了数值语义！"
    print("\n数值验证通过：融合前后结果完全一致。")


if __name__ == "__main__":
    main()
