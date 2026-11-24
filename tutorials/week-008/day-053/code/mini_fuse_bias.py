"""mini_fuse_bias.py —— 第 53 天核心示例：MatMul + Bias 融合。

在第 51/52 天的迷你图 IR / Rewriter（带 use-def 完整性检查）基础上，
把融合机制推广到今天的目标链：

    %m = mini.matmul %a, %b        : 2x3 · 3x2 -> 2x2   （乘积，中间值）
    %s = mini.add     %m, %bias   : 2x2 + 2x2 -> 2x2   （bias 加法）
    %r = mini.relu    %s          : 2x2     -> 2x2     （可选）

今天的三个新问题，Pattern 必须一一回答：

  1. Bias Shape：add 有两个操作数，谁是 bias？bias 形状对不上怎么办？
     —— 三分类 Same / BroadcastOnly / Mismatch（口径同第 40/50 天），
        今天只有 Same（与乘积同形）能融合；[N] 向量要等第 60 天的 broadcast。
  2. 输出类型：融合算子的结果类型听谁的？
     —— 听 matmul 的（乘积的形状 [M,N]），不跟 bias 走，更不跟「第一个
        操作数」走——第 52 天的 create_op 用 inputs[0].type 当结果类型，
        matmul 一来就露馅（lhs 是 2x3，结果却是 2x2）。
  3. 融合语义与可选 Relu：没有 Relu 融成 fused_matmul_bias（今天新定义）；
     加法结果的唯一使用者是 Relu 时，直接吸收成 fused_matmul_bias_relu
     （第 50 天定义）。%s 还有别的使用者时绝不吸收——那是第 54 天的入口。

运行: python3 mini_fuse_bias.py
依赖: numpy（仅用于数值验证）
"""

import numpy as np


# ===================== 迷你 IR：Value / Op / Graph =====================

class Value:
    """一个 SSA 值：由某个算子定义（def_op），或作为图的输入（def_op=None）。"""

    def __init__(self, name, vtype, def_op=None):
        self.name = name          # 例如 "%m"
        self.type = vtype         # 例如 "tensor<2x2xf32>"
        self.def_op = def_op      # 定义该值的算子；图输入为 None
        self.uses = []            # [(使用者 Op, 操作数下标), ...]

    def has_one_use(self):
        return len(self.uses) == 1


class Op:
    """一个算子：名字 + 操作数列表 + 唯一结果（mini.return 没有结果）。"""

    def __init__(self, name, inputs, result=None):
        self.name = name
        self.inputs = list(inputs)
        self.result = result


class Graph:
    """函数级计算图：输入、按拓扑序排列的算子、一个 return 算子。"""

    def __init__(self, func_name):
        self.func_name = func_name
        self.inputs = []
        self.ops = []
        self.return_op = None

    def add_input(self, name, vtype):
        v = Value(name, vtype, def_op=None)
        self.inputs.append(v)
        return v

    def create_op(self, name, inputs, result_name, result_type=None):
        # 第 52 天这里写的是 inputs[0].type——对逐元素算子恰好成立；
        # matmul 的输出形状 [M,N] 和第一个操作数 [M,K] 不同，所以今天
        # 必须显式传 result_type。缺省仍回退到旧写法，是为了让错误 1
        # 能被测试复现，而不是让构造器替 Pattern 掩盖问题。
        if result_type is None:
            result_type = inputs[0].type
        result = Value(result_name, result_type, def_op=None)
        op = Op(name, inputs, result)
        result.def_op = op
        for i, v in enumerate(inputs):
            v.uses.append((op, i))
        self.ops.append(op)
        return op

    def set_outputs(self, values):
        self.return_op = Op("mini.return", values)
        for i, v in enumerate(values):
            v.uses.append((self.return_op, i))

    @property
    def outputs(self):
        return self.return_op.inputs

    def op_names(self):
        return [op.name for op in self.ops]

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


def tt(*dims):
    """构造 tensor 类型字符串：tt(2,3) -> "tensor<2x3xf32>"。"""
    return "tensor<" + "x".join(str(d) for d in dims) + "xf32>"


def shape_of(vtype):
    """tensor<2x3xf32> -> (2, 3)。等价于 MLIR 里 RankedTensorType::getShape()。"""
    body = vtype[len("tensor<"):-len("xf32>")]
    return tuple(int(d) for d in body.split("x"))


# ===================== Rewriter：所有修改的必经之路 =====================

class Rewriter:
    """对图的一切修改都必须通过 Rewriter，修改前后维护 use-def 完整性。"""

    def __init__(self, graph):
        self.graph = graph

    def create(self, name, inputs, insert_before=None, result_name=None,
               result_type=None):
        result_name = result_name or f"%f{len(self.graph.ops)}"
        op = self.graph.create_op(name, inputs, result_name, result_type)
        if insert_before is not None:
            self.graph.ops.remove(op)
            pos = self.graph.ops.index(insert_before)
            self.graph.ops.insert(pos, op)
        return op

    def replace_all_uses_with(self, old, new):
        for user, idx in old.uses:
            user.inputs[idx] = new
            new.uses.append((user, idx))
        old.uses = []

    def erase(self, op):
        if op.result is not None and op.result.uses:
            raise RuntimeError(
                f"不能擦除 {op.name}：结果 {op.result.name} "
                f"仍有 {len(op.result.uses)} 处使用者")
        for i, v in enumerate(op.inputs):
            v.uses = [u for u in v.uses if u[0] is not op]
        self.graph.ops.remove(op)


# ===================== 今天的核心之一：Bias Shape 三分类 =====================

def classify_bias_shape(bias_type, out_type):
    """三分类：Same / BroadcastOnly / Mismatch。

    口径与第 40/50 天完全一致：
      Same          bias 与输出逐维相同 —— 今天唯一能融合的形状
      BroadcastOnly bias 是 [N]、输出末维是 N —— 语义上就是经典 bias
                    （torch.nn.Linear 就用 [N]），但 mini 第 40 天起故意
                    不支持，第 60 天放行；Pattern 今天不碰它
      Mismatch      连广播都对不上 —— 永久不合法
    """
    bs, os_ = shape_of(bias_type), shape_of(out_type)
    if bs == os_:
        return "Same"
    if len(bs) == 1 and len(os_) >= 1 and bs[0] == os_[-1]:
        return "BroadcastOnly"
    return "Mismatch"


# ===================== 今天的核心之二：MatMul + Bias 融合 Pattern =====================

def fuse_matmul_bias_pattern(add, rw, policy="reject"):
    """匹配 mini.add；某一侧操作数由 mini.matmul 定义时，融合成
    mini.fused_matmul_bias（无 Relu）或 mini.fused_matmul_bias_relu
    （加法结果的唯一使用者是 Relu 时直接吸收）。"""

    # (1) 找乘积：先看 lhs，再看 rhs；两侧都是 matmul —— 没有「bias」可言
    lhs, rhs = add.inputs
    lhs_mm = lhs.def_op is not None and lhs.def_op.name == "mini.matmul"
    rhs_mm = rhs.def_op is not None and rhs.def_op.name == "mini.matmul"
    if lhs_mm and rhs_mm:
        print("  [reject] 两侧操作数都是 mini.matmul —— 分不清谁是 bias，拒绝融合")
        return False
    if not lhs_mm and not rhs_mm:
        return False                     # 没有链，安静返回（不是错误）
    mm = lhs.def_op if lhs_mm else rhs.def_op
    bias = rhs if lhs_mm else lhs        # 另一侧就是 bias，左右都认
    m = mm.result                        # 乘积 %m：本 Pattern 的中间值

    # (2) Bias Shape 检查：三分类里今天只放 Same
    kind = classify_bias_shape(bias.type, m.type)
    if kind != "Same":
        why = ("需要广播——第 40 天起故意不支持，第 60 天放行"
               if kind == "BroadcastOnly" else "shape 连广播都对不上")
        print(f"  [reject] bias {bias.type} 对乘积 {m.type}：{why}")
        return False

    # (3) 多使用者检查：乘积 %m 必须只被这个 add 使用 —— 改写前采样！
    single_use = m.has_one_use()

    # (4) 可选 Relu：加法结果 %s 的唯一使用者是 mini.relu 时才能吸收。
    #     %s 还有别的使用者时吸收 = 把人家的 a+b 换成 relu(a+b)，语义悄悄变错。
    relu = None
    s = add.result
    if s.has_one_use() and s.uses[0][0].name == "mini.relu":
        relu = s.uses[0][0]

    if policy == "reject" and not single_use:
        print(f"  [reject] 乘积 {m.name} 有 {len(m.uses)} 个使用者"
              "（第 52 天的规则原样适用）——拒绝融合")
        return False

    # (5) 改写。注意两点：
    #     a. 结果类型跟 matmul 走（m.type = [M,N]），不跟 bias、不跟 inputs[0] 走
    #     b. 擦除顺序：先擦最上层消费者（Relu），再擦 Add，最后看 %m 决定 MatMul
    fused_name = ("mini.fused_matmul_bias_relu" if relu is not None
                  else "mini.fused_matmul_bias")
    fused = rw.create(fused_name, [mm.inputs[0], mm.inputs[1], bias],
                      insert_before=add, result_name=s.name + "'",
                      result_type=m.type)
    if relu is not None:
        rw.replace_all_uses_with(relu.result, fused.result)
        rw.erase(relu)
        print(f"  [fuse3] {mm.name} + {add.name} + {relu.name}"
              f" -> {fused_name}（Relu 直接吸收）")
    else:
        print(f"  [fuse2] {mm.name} + {add.name} -> {fused_name}")
    rw.replace_all_uses_with(s, fused.result)
    rw.erase(add)
    if single_use:
        rw.erase(mm)
    else:
        print(f"  [keep] 乘积 {m.name} 还有别的使用者，保留 {mm.name}"
              "——整次 matmul 将在融合算子里重算（比第 52 天重算加法贵得多）")
    return True


def run_fusion(graph, policy="reject", verbose=True):
    """贪心驱动：反复扫描 mini.add，直到一轮下来没有任何 Pattern 命中。"""
    rw = Rewriter(graph)
    while True:
        changed = False
        for op in [o for o in graph.ops if o.name == "mini.add"]:
            if fuse_matmul_bias_pattern(op, rw, policy):
                changed = True
                break
        if not changed:
            return


# ===================== 数值语义、求值与代价估算 =====================

SEMANTICS = {
    "mini.matmul": lambda xs: xs[0] @ xs[1],
    "mini.add": lambda xs: xs[0] + xs[1],
    "mini.relu": lambda xs: np.maximum(xs[0], 0.0),
    "mini.fused_matmul_bias": lambda xs: xs[0] @ xs[1] + xs[2],
    "mini.fused_matmul_bias_relu": lambda xs: np.maximum(xs[0] @ xs[1] + xs[2], 0.0),
}


def _prod(shape):
    n = 1
    for d in shape:
        n *= d
    return n


def op_cost(op):
    """玩具代价模型：matmul/add 执行次数 + 乘加 FLOPs + 整张张量读/写遍数。

    口径（与第 52 天同族，但把「加法次数」升级成 FLOPs——matmul 的重算
    代价必须用乘加次数才能显出来）：
      matmul   ：一次乘加循环 2·M·N·K 次 FLOPs；读 A、B 各 1 遍，写 %m 1 遍
      add/relu ：逐元素，各 M·N 次；add 读 2 写 1，relu 读 1 写 1
      fused_mm_bias(_relu)：2·M·N·K (+M·N / +2·M·N)；读 3 写 1
    """
    res_shape = shape_of(op.result.type)
    n = _prod(res_shape)
    lhs_elems = _prod(shape_of(op.inputs[0].type))     # M·K
    mm_flops = 2 * lhs_elems * res_shape[1]            # 2·M·K·N
    if op.name == "mini.matmul":
        return {"matmul": 1, "add": 0, "flops": mm_flops, "passes": 3}
    if op.name == "mini.add":
        return {"matmul": 0, "add": 1, "flops": n, "passes": 3}
    if op.name == "mini.relu":
        return {"matmul": 0, "add": 0, "flops": n, "passes": 2}
    if op.name == "mini.fused_matmul_bias":
        return {"matmul": 1, "add": 1, "flops": mm_flops + n, "passes": 4}
    if op.name == "mini.fused_matmul_bias_relu":
        return {"matmul": 1, "add": 1, "flops": mm_flops + 2 * n, "passes": 4}
    raise KeyError(op.name)


def evaluate(graph, feed):
    env = {v.name: feed[v.name] for v in graph.inputs}
    for op in graph.ops:
        env[op.result.name] = SEMANTICS[op.name]([env[v.name] for v in op.inputs])
    return env


def count_cost(graph):
    matmul = add = flops = passes = 0
    for op in graph.ops:
        c = op_cost(op)
        matmul += c["matmul"]
        add += c["add"]
        flops += c["flops"]
        passes += c["passes"]
    return matmul, add, flops, passes


# ===================== 场景图：一套数字贯穿全篇 =====================

FEED = {
    "%a": np.array([[1.0, -2.0, 3.0], [-4.0, 5.0, -6.0]]),   # 2x3
    "%b": np.array([[1.0, 0.0], [-1.0, 2.0], [3.0, -3.0]]),  # 3x2
    "%bias": np.array([[10.0, -10.0], [20.0, -20.0]]),       # 2x2
    "%v1": np.array([[10.0, -10.0]]),                        # 1x2（错秩）
    "%v2": np.array([10.0, -10.0]),                          # 2（[N] 向量）
}


def _matmul(g, a, b, name="%m"):
    return g.create_op("mini.matmul", [a, b], name, result_type=tt(2, 2))


def build_bias_relu_graph():
    """主线图：MatMul -> Add(bias) -> Relu，全部单使用者。"""
    g = Graph("bias_relu")
    va = g.add_input("%a", tt(2, 3))
    vb = g.add_input("%b", tt(3, 2))
    vbias = g.add_input("%bias", tt(2, 2))
    m = _matmul(g, va, vb)
    s = g.create_op("mini.add", [m.result, vbias], "%s", result_type=tt(2, 2))
    r = g.create_op("mini.relu", [s.result], "%r", result_type=tt(2, 2))
    g.set_outputs([r.result])
    return g


def build_bias_only_graph():
    g = Graph("bias_only")
    va = g.add_input("%a", tt(2, 3))
    vb = g.add_input("%b", tt(3, 2))
    vbias = g.add_input("%bias", tt(2, 2))
    m = _matmul(g, va, vb)
    s = g.create_op("mini.add", [m.result, vbias], "%s", result_type=tt(2, 2))
    g.set_outputs([s.result])
    return g


def build_bias_on_left_graph():
    """bias 写在左边：mini.add %bias, %m —— Pattern 左右都得认。"""
    g = Graph("bias_on_left")
    va = g.add_input("%a", tt(2, 3))
    vb = g.add_input("%b", tt(3, 2))
    vbias = g.add_input("%bias", tt(2, 2))
    m = _matmul(g, va, vb)
    s = g.create_op("mini.add", [vbias, m.result], "%s", result_type=tt(2, 2))
    g.set_outputs([s.result])
    return g


def build_multi_user_product_graph():
    """乘积 %m 被 add 和另一个 relu 同时使用 —— 今天的「更致命」反例。"""
    g = Graph("multi_product")
    va = g.add_input("%a", tt(2, 3))
    vb = g.add_input("%b", tt(3, 2))
    vbias = g.add_input("%bias", tt(2, 2))
    m = _matmul(g, va, vb)
    s = g.create_op("mini.add", [m.result, vbias], "%s", result_type=tt(2, 2))
    r = g.create_op("mini.relu", [s.result], "%r", result_type=tt(2, 2))
    t = g.create_op("mini.relu", [m.result], "%t", result_type=tt(2, 2))
    g.set_outputs([r.result, t.result])
    return g


def build_shared_result_graph():
    """加法结果 %s 被 relu 和 return 同时使用 —— 不能吸收 Relu 的组合。"""
    g = Graph("shared_result")
    va = g.add_input("%a", tt(2, 3))
    vb = g.add_input("%b", tt(3, 2))
    vbias = g.add_input("%bias", tt(2, 2))
    m = _matmul(g, va, vb)
    s = g.create_op("mini.add", [m.result, vbias], "%s", result_type=tt(2, 2))
    r = g.create_op("mini.relu", [s.result], "%r", result_type=tt(2, 2))
    g.set_outputs([r.result, s.result])
    return g


def build_bad_bias_graph(kind="mismatch"):
    """非法 bias 形状：Mismatch（连广播都对不上）或 BroadcastOnly（[N] 向量）。

    注意：这样的图在真实 mini Dialect 里过不了 mini.add 的 Verifier（第 40 天），
    这里没有 Verifier，所以 Pattern 自己的三分类是唯一闸门——正好用它演示
    「Pattern 的合法性检查不能依赖求值器的能力」。
    """
    g = Graph("bad_bias_" + kind)
    va = g.add_input("%a", tt(2, 3))
    vb = g.add_input("%b", tt(3, 2))
    bad = g.add_input("%v1" if kind == "mismatch" else "%v2",
                      tt(1, 2) if kind == "mismatch" else tt(2))
    m = _matmul(g, va, vb)
    s = g.create_op("mini.add", [m.result, bad], "%s", result_type=tt(2, 2))
    r = g.create_op("mini.relu", [s.result], "%r", result_type=tt(2, 2))
    g.set_outputs([r.result])
    return g


# ===================== 演示主程序 =====================

REF_PRODUCT = FEED["%a"] @ FEED["%b"]                     # [[12,-13],[-27,28]]
REF_BIASED = REF_PRODUCT + FEED["%bias"]                  # [[22,-23],[-7,8]]
REF_RELU = np.maximum(REF_BIASED, 0.0)                     # [[22,0],[0,8]]


def report(g, expect):
    """打印 IR、代价并核对每个输出。expect: 输出名 -> 参考值。"""
    g.print_ir()
    matmul, add, flops, passes = count_cost(g)
    print(f"matmul 执行 = {matmul}，add 执行 = {add}，"
          f"FLOPs = {flops}，张量读写遍数 = {passes}")
    out = evaluate(g, FEED)
    ok = True
    for name, ref in expect.items():
        v = out[name]
        good = np.allclose(v, ref)
        ok &= good
        print(f"{name} = {v.tolist()}   期望 {ref.tolist()}   "
              f"{'一致' if good else '不一致!'}")
    return ok


def main():
    print("===== 参考数值（numpy 直算）=====")
    print(f"%m = A·B        = {REF_PRODUCT.tolist()}")
    print(f"%s = %m + bias  = {REF_BIASED.tolist()}")
    print(f"%r = relu(%s)   = {REF_RELU.tolist()}")

    print("\n===== 场景 A：主线图 MatMul -> Add(bias) -> Relu =====")
    g = build_bias_relu_graph()
    print("融合前：")
    g.print_ir()
    mm, ad, fl, ps = count_cost(g)
    print(f"matmul={mm}, add={ad}, FLOPs={fl}, 张量遍数={ps}")
    print("融合后：")
    run_fusion(g)
    report(g, {g.outputs[0].name: REF_RELU})

    print("\n===== 场景 B：没有 Relu —— 两算子融合成 fused_matmul_bias =====")
    g = build_bias_only_graph()
    run_fusion(g)
    report(g, {g.outputs[0].name: REF_BIASED})

    print("\n===== 场景 C：乘积 %m 多使用者（默认 reject）=====")
    g = build_multi_user_product_graph()
    before = g.op_names()
    run_fusion(g)
    assert g.op_names() == before, "拒绝必须是恒等变换"
    report(g, {"%r": REF_RELU, "%t": np.maximum(REF_PRODUCT, 0.0)})

    print("\n===== 场景 D：同一张图换 --policy=keep（重算的代价）=====")
    g = build_multi_user_product_graph()
    run_fusion(g, policy="keep")
    ok = report(g, {"%s'": REF_RELU, "%t": np.maximum(REF_PRODUCT, 0.0)})

    print("\n===== 场景 E：%s 被 relu 和 return 共用 —— 不吸收 Relu =====")
    g = build_shared_result_graph()
    run_fusion(g)
    ok &= report(g, {"%r": REF_RELU, "%s'": REF_BIASED})

    print("\n===== 场景 F：bias 是 [N] 向量（BroadcastOnly）=====")
    g = build_bad_bias_graph("broadcast")
    run_fusion(g)
    print("（对照：numpy 会按行广播算出 "
          f"{(REF_PRODUCT + FEED['%v2']).tolist()} —— 求值器「能算」")
    print("不等于 mini.add 的规则「允许算」；真实 MLIR 里这张图会在")
    print("Verifier 就被拦下，见教程 §5.4 实验 H。")

    print("\n===== 结论 =====")
    print("1. bias 与乘积同形（Same）时：两算子融成 fused_matmul_bias，")
    print("   唯一使用者是 Relu 时进一步吸收成 fused_matmul_bias_relu；")
    print("2. 乘积 %m 多使用者：默认拒绝（第 52 天规则原样适用）；keep 的")
    print("   代价从「重算一次加法」放大成「重算整次 matmul」；")
    print("3. 加法结果 %s 多使用者时绝不吸收 Relu——只做两算子融合，")
    print("   留下的 relu(fused_matmul_bias) 正是第 54 天的入口。")


if __name__ == "__main__":
    main()
