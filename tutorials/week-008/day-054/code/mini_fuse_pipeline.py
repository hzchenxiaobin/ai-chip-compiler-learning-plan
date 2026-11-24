"""mini_fuse_pipeline.py —— 第 54 天核心示例：三算子融合与 Pattern 优先级。

第 53 天把 `MatMul + Add(bias) (+ Relu)` 的融合 Pattern 写对了；今天的问题
是「把多个融合 Pattern 放进同一个 Pass 管道后，最终形态由谁决定」：

    %m = mini.matmul %a, %b        : 2x3 · 3x2 -> 2x2   （乘积，中间值）
    %s = mini.add     %m, %bias    : 2x2 + 2x2 -> 2x2   （bias 加法）
    %r = mini.relu    %s           : 2x2     -> 2x2     （可选）

通往 `mini.fused_matmul_bias_relu` 有两条路线：

  路线 A（两阶段）：P1 先把 MatMul+Add 融成 fused_matmul_bias；
                   P2 再把 Relu 吸收进 epilogue，升成 fused_matmul_bias_relu。
  路线 B（直接三算子）：P3 一步到位（第 53 天的形态，加法结果唯一使用者
                   是 Relu 时直接吸收）。

今天的三个新概念：

  1. Pattern 优先级（benefit）：同一 root 上，benefit 高的先被尝试
     （MLIR 的 PatternApplicator 对每个 root 的 Pattern 列表按 benefit
     稳定降序排序）；不同 root 的先后由工作表访问顺序决定——那是
     驱动的实现细节，不是 Pattern 集合的契约。
  2. 重复匹配：改写发生后，输入被替换的算子会被重新入队、再次匹配。
     两阶段路线不需要人工编排顺序，靠的就是这个机制。
  3. 抢跑（steal）事故：把第 51 天的 `Add+Relu -> fused_add_relu` 和
     P3 放进同一个集合，谁先被访问谁就抢走 Add+Relu 这对邻居——
     最终形态从「不依赖执行顺序」变成「看驱动心情」。

本文件还实现了一个带护栏的迷你贪心驱动（visit 次数上限），用来安全地
演示「互相打架的 Pattern 永不收敛」（Unfuse vs P2 的振荡）。

运行: python3 mini_fuse_pipeline.py
依赖: numpy（仅用于数值验证）
"""

import numpy as np


# ===================== 迷你 IR：Value / Op / Graph（与第 53 天一致） =====================

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


# ===================== Rewriter：所有修改的必经之路（今天兼职 Listener） =====================

class Rewriter:
    """对图的一切修改都必须通过 Rewriter，修改前后维护 use-def 完整性。

    第 54 天新增：改写事件记录（create / replace）。真实 MLIR 里驱动靠
    RewriterBase::Listener 感知修改；这里的 events 就是它的最小版——
    贪心驱动读它来决定「哪些算子需要重新入队」。
    """

    def __init__(self, graph):
        self.graph = graph
        self.events = []          # [("create", op) | ("replace", [user, ...])]

    def create(self, name, inputs, insert_before=None, result_name=None,
               result_type=None):
        result_name = result_name or f"%f{len(self.graph.ops)}"
        op = self.graph.create_op(name, inputs, result_name, result_type)
        if insert_before is not None:
            self.graph.ops.remove(op)
            pos = self.graph.ops.index(insert_before)
            self.graph.ops.insert(pos, op)
        self.events.append(("create", op))
        return op

    def replace_all_uses_with(self, old, new):
        users = [user for user, _ in old.uses]     # 先拍快照：谁的操作数要变
        for user, idx in old.uses:
            user.inputs[idx] = new
            new.uses.append((user, idx))
        old.uses = []
        self.events.append(("replace", users))

    def erase(self, op):
        if op.result is not None and op.result.uses:
            raise RuntimeError(
                f"不能擦除 {op.name}：结果 {op.result.name} "
                f"仍有 {len(op.result.uses)} 处使用者")
        for i, v in enumerate(op.inputs):
            v.uses = [u for u in v.uses if u[0] is not op]
        self.graph.ops.remove(op)


# ===================== Bias Shape 三分类（口径与第 40/50/53 天一致） =====================

def classify_bias_shape(bias_type, out_type):
    """Same / BroadcastOnly / Mismatch；今天仍只放行 Same（第 60 天放行广播）。"""
    bs, os_ = shape_of(bias_type), shape_of(out_type)
    if bs == os_:
        return "Same"
    if len(bs) == 1 and len(os_) >= 1 and bs[0] == os_[-1]:
        return "BroadcastOnly"
    return "Mismatch"


# ===================== Pattern 与贪心驱动：今天的核心机制 =====================

class Pattern:
    """一个 RewritePattern 的最小形态：root（匹配哪种算子）＋ benefit（优先级）。

    benefit 与 MLIR 的 PatternBenefit 同族：无量纲，0~65535，越大越先被
    尝试；官方建议的量纲是「一次匹配吃掉的算子数」。
    """

    def __init__(self, name, root, benefit=1):
        self.name = name
        self.root = root
        self.benefit = benefit

    def match_and_rewrite(self, op, rw):
        raise NotImplementedError


class NonConvergence(Exception):
    """工作表在访问次数上限内没有排空：Pattern 集合不收敛（互相打架）。"""


class GreedyDriver:
    """工作表式贪心驱动（与 MLIR applyPatternsAndFoldGreedily 同族的最小复现）。

    规则明说（这四条就是本日 §3 的全部机制）：
      1. 按程序序把全部算子播种进工作表；
      2. visit="bottom-up"（默认）从表尾弹出——消费者先被访问，
         对应 MLIR 默认的 useTopDownTraversal=false；
         visit="top-down" 从表头弹出——生产者先被访问；
      3. 访问某个算子时，只尝试 root 匹配的 Pattern，按 benefit 稳定
         降序（同 benefit 保持插入序），第一个命中即生效、本轮结束；
      4. Pattern 命中后：新创建的算子、以及「输入被替换的使用者」
         重新入队（重复匹配的来源）；已擦除的算子弹出时跳过。

    护栏：max_visits 次访问内工作表未排空 -> NonConvergence。
    （真实 MLIR 的对应旋钮是 maxIterations / maxNumRewrites，见教程 §5。）
    """

    def __init__(self, graph, patterns, visit="bottom-up", max_visits=100):
        self.graph = graph
        self.rw = Rewriter(graph)
        self.visit = visit
        self.max_visits = max_visits
        self.by_root = {}
        for p in patterns:
            self.by_root.setdefault(p.root, []).append(p)
        for lst in self.by_root.values():
            lst.sort(key=lambda p: -p.benefit)     # 稳定排序：同 benefit 保持插入序

    def run(self):
        worklist = list(self.graph.ops)            # 程序序播种
        rewrites = visits = 0
        while worklist:
            op = worklist.pop() if self.visit == "bottom-up" else worklist.pop(0)
            visits += 1
            if visits > self.max_visits:
                raise NonConvergence(
                    f"工作表在 {self.max_visits} 次访问内未排空"
                    f"（已改写 {rewrites} 次）——Pattern 集合不收敛")
            if op not in self.graph.ops:           # 已被之前的改写擦除
                continue
            for p in self.by_root.get(op.name, []):
                self.rw.events.clear()
                if p.match_and_rewrite(op, self.rw):
                    rewrites += 1
                    for kind, payload in self.rw.events:
                        if kind == "create":
                            worklist.append(payload)
                        else:                       # "replace"：输入变了的使用者
                            worklist.extend(u for u in payload
                                            if u in self.graph.ops)
                    break                          # 同 root 第一个命中的生效
        return rewrites


# ===================== 五个 Pattern ＋ 一个「反面教材」 =====================

def _find_matmul_pair(add):
    """在 add 的两个操作数里找「乘积 / bias」：返回 (matmul_op, bias_value)。

    左右都认（第 53 天实验 C）；两侧都是乘积 -> None（分不清谁是 bias）。
    """
    lhs, rhs = add.inputs
    lhs_mm = lhs.def_op is not None and lhs.def_op.name == "mini.matmul"
    rhs_mm = rhs.def_op is not None and rhs.def_op.name == "mini.matmul"
    if lhs_mm and rhs_mm:
        return None
    if not lhs_mm and not rhs_mm:
        return None
    return (lhs.def_op, rhs) if lhs_mm else (rhs.def_op, lhs)


class FuseMatmulBiasTwoStage(Pattern):
    """P1 两阶段·第一步：MatMul + Add -> fused_matmul_bias（不看 Relu）。

    和第 53 天 Pattern 的唯一区别：这里绝不吸收 Relu——第二步交给 P2。
    乘积 %m 必须单使用者（第 52 天规则，改写前采样）。
    """

    def __init__(self, benefit=1):
        super().__init__("P1 FuseMatmulBias（两阶段·第一步）", "mini.add", benefit)

    def match_and_rewrite(self, add, rw):
        pair = _find_matmul_pair(add)
        if pair is None:
            return False                     # 没有链或双侧都是乘积：安静返回
        mm, bias = pair
        m = mm.result
        if classify_bias_shape(bias.type, m.type) != "Same":
            return False                     # 输入图已过 Verifier，这是第二道防线
        if not m.has_one_use():
            print(f"  [P1] 乘积 {m.name} 有 {len(m.uses)} 个使用者"
                  "——拒绝融合（第 52 天规则），保留整条链")
            return False
        fused = rw.create("mini.fused_matmul_bias",
                          [mm.inputs[0], mm.inputs[1], bias],
                          insert_before=add, result_name=add.result.name + "'",
                          result_type=m.type)   # 结果类型跟 matmul 走（Day 53）
        rw.replace_all_uses_with(add.result, fused.result)
        rw.erase(add)
        rw.erase(mm)                             # 乘积独占 -> 生产者一并删除
        print(f"  [P1] {mm.name} + {add.name} -> mini.fused_matmul_bias"
              "（两阶段·第一步，Relu 原地不动）")
        return True


class AbsorbReluEpilogue(Pattern):
    """P2 两阶段·第二步：Relu(fused_matmul_bias) -> fused_matmul_bias_relu。

    锚在 mini.relu（消费者）上。允许不匹配时安静返回以外的场合也打一行
    日志——这样「同一个 relu 被访问两次（第一次不匹配、第二次吸收）」
    就直接写在输出里，重复匹配看得见。
    """

    def __init__(self, benefit=1):
        super().__init__("P2 AbsorbRelu（两阶段·第二步）", "mini.relu", benefit)

    def match_and_rewrite(self, relu, rw):
        x = relu.inputs[0]
        fm = x.def_op
        if fm is None or fm.name != "mini.fused_matmul_bias":
            print(f"  [P2] 访问 {relu.result.name}：操作数由 "
                  f"{'图输入' if fm is None else fm.name} 定义 -> 不匹配")
            return False
        if not x.has_one_use():
            print(f"  [P2] 融合结果 {x.name} 有 {len(x.uses)} 个使用者"
                  "——不能吸收 Relu（第 53 天场景 E 的规则）")
            return False
        fused = rw.create("mini.fused_matmul_bias_relu", list(fm.inputs),
                          insert_before=fm, result_name=relu.result.name + "'",
                          result_type=x.type)
        rw.replace_all_uses_with(relu.result, fused.result)
        rw.erase(relu)                           # 先擦消费者
        rw.erase(fm)                             # 再擦生产者（结果已无人用）
        print("  [P2] fused_matmul_bias + relu -> mini.fused_matmul_bias_relu"
              "（两阶段·第二步，epilogue 吸收）")
        return True


class FuseMatmulBiasReluDirect(Pattern):
    """P3 直接三算子：MatMul + Add (+Relu) -> fused_matmul_bias(_relu)。

    第 53 天的 Pattern 原样搬来，默认 benefit=2：同一 root（mini.add）
    上压过 P1——「一次匹配吃掉三个算子」的优先级就该更高。
    """

    def __init__(self, benefit=2):
        super().__init__("P3 FuseMatmulBiasRelu（直接三算子）", "mini.add", benefit)

    def match_and_rewrite(self, add, rw):
        pair = _find_matmul_pair(add)
        if pair is None:
            return False
        mm, bias = pair
        m = mm.result
        if classify_bias_shape(bias.type, m.type) != "Same":
            return False
        single_use = m.has_one_use()             # 改写前采样（Day 52 错误 3）
        if not single_use:
            print(f"  [P3] 乘积 {m.name} 有 {len(m.uses)} 个使用者"
                  "——拒绝融合（第 52 天规则），保留整条链")
            return False
        relu = None                              # 可选 Relu：%s 的唯一使用者
        s = add.result
        if s.has_one_use() and s.uses[0][0].name == "mini.relu":
            relu = s.uses[0][0]
        fused_name = ("mini.fused_matmul_bias_relu" if relu is not None
                      else "mini.fused_matmul_bias")
        fused = rw.create(fused_name, [mm.inputs[0], mm.inputs[1], bias],
                          insert_before=add, result_name=s.name + "'",
                          result_type=m.type)
        if relu is not None:
            rw.replace_all_uses_with(relu.result, fused.result)
            rw.erase(relu)                       # 先擦最上层消费者
            rw.erase(add)
            rw.erase(mm)
            print(f"  [P3] {mm.name} + {add.name} + {relu.name} -> {fused_name}"
                  "（直接三算子，一步到位）")
            return True
        rw.replace_all_uses_with(s, fused.result)
        rw.erase(add)
        rw.erase(mm)
        print(f"  [P3] {mm.name} + {add.name} -> {fused_name}（直接两算子）")
        return True


class FuseAddRelu(Pattern):
    """P51 第 51 天的 Add + Relu -> fused_add_relu（本日的「抢跑者」）。

    锚在 mini.relu 上。它完全合法（第 51 天就是这么写的），但和 P3
    放进同一个集合时：谁先被访问，谁就抢走 Add+Relu 这对邻居。
    """

    def __init__(self, benefit=1, guard_matmul=False, name=None):
        super().__init__(name or "P51 FuseAddRelu（第 51 天·抢跑者）",
                         "mini.relu", benefit)
        self.guard_matmul = guard_matmul         # True = 让位版 P51g

    def match_and_rewrite(self, relu, rw):
        x = relu.inputs[0]
        ad = x.def_op
        if ad is None or ad.name != "mini.add":
            return False                         # 没有链，安静返回
        if not x.has_one_use():
            return False
        if self.guard_matmul:
            for v in ad.inputs:                  # 让位规则：add 的操作数里有乘积
                if v.def_op is not None and v.def_op.name == "mini.matmul":
                    print("  [P51g] add 的操作数之一是 matmul 乘积"
                          "——让位给更大的融合（MatMul+Bias 系），本次不抢")
                    return False
        fused = rw.create("mini.fused_add_relu", list(ad.inputs),
                          insert_before=ad, result_name=relu.result.name + "'",
                          result_type=x.type)
        rw.replace_all_uses_with(relu.result, fused.result)
        rw.erase(relu)
        rw.erase(ad)
        tag = "P51g" if self.guard_matmul else "P51"
        print(f"  [{tag}] {ad.name} + {relu.name} -> mini.fused_add_relu"
              "（Add+Relu 小融合）")
        return True


class UnfuseMatmulBiasRelu(Pattern):
    """反面教材：fused_matmul_bias_relu -> fused_matmul_bias + relu。

    语义上完全等价（拆开而已），但它和 P2 互为逆变换——放进同一个
    集合就是「互相打架」，用来演示不收敛。真实工程里它的名字叫
    「昨天调试时忘了删的 Pattern」。
    """

    def __init__(self, benefit=3):
        super().__init__("Unfuse（反面教材）", "mini.fused_matmul_bias_relu",
                         benefit)

    def match_and_rewrite(self, f, rw):
        a, b, bias = f.inputs
        m = rw.create("mini.fused_matmul_bias", [a, b, bias],
                      insert_before=f, result_name=f.result.name + "_m",
                      result_type=f.result.type)
        r = rw.create("mini.relu", [m.result],
                      insert_before=f, result_name=f.result.name + "_r",
                      result_type=f.result.type)
        rw.replace_all_uses_with(f.result, r.result)
        rw.erase(f)
        print("  [Unfuse] fused_matmul_bias_relu 拆回 matmul-bias + relu"
              "（语义不变，但 P2 会再把它融回去……）")
        return True


# ===================== 数值语义、求值与代价账本（口径同第 53 天） =====================

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
    """玩具代价模型：matmul/add 执行次数 + FLOPs + 张量读/写遍数（Day 53 口径）。"""
    res_shape = shape_of(op.result.type)
    n = _prod(res_shape)
    lhs_elems = _prod(shape_of(op.inputs[0].type))
    mm_flops = 2 * lhs_elems * res_shape[1]
    if op.name == "mini.matmul":
        return {"matmul": 1, "add": 0, "flops": mm_flops, "passes": 3}
    if op.name == "mini.add":
        return {"matmul": 0, "add": 1, "flops": n, "passes": 3}
    if op.name == "mini.relu":
        return {"matmul": 0, "add": 0, "flops": n, "passes": 2}
    if op.name == "mini.fused_add_relu":
        return {"matmul": 0, "add": 1, "flops": 2 * n, "passes": 3}
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
    "%x": np.array([[1.0, -2.0], [3.0, -4.0]]),              # 2x2（Add+Relu 图用）
    "%y": np.array([[5.0, 6.0], [-7.0, 8.0]]),               # 2x2
}

REF_PRODUCT = FEED["%a"] @ FEED["%b"]                     # [[12,-13],[-27,28]]
REF_BIASED = REF_PRODUCT + FEED["%bias"]                  # [[22,-23],[-7,8]]
REF_RELU = np.maximum(REF_BIASED, 0.0)                     # [[22,0],[0,8]]
REF_ADD_RELU = np.maximum(FEED["%x"] + FEED["%y"], 0.0)    # [[6,4],[0,4]]


def build_bias_relu_graph():
    """主线图：MatMul -> Add(bias) -> Relu，全部单使用者。"""
    g = Graph("bias_relu")
    va = g.add_input("%a", tt(2, 3))
    vb = g.add_input("%b", tt(3, 2))
    vbias = g.add_input("%bias", tt(2, 2))
    m = g.create_op("mini.matmul", [va, vb], "%m", result_type=tt(2, 2))
    s = g.create_op("mini.add", [m.result, vbias], "%s", result_type=tt(2, 2))
    r = g.create_op("mini.relu", [s.result], "%r", result_type=tt(2, 2))
    g.set_outputs([r.result])
    return g


def build_add_relu_only_graph():
    """没有 matmul 的纯 Add + Relu 图：小融合在这里才是正确答案。"""
    g = Graph("add_relu_only")
    vx = g.add_input("%x", tt(2, 2))
    vy = g.add_input("%y", tt(2, 2))
    s = g.create_op("mini.add", [vx, vy], "%s", result_type=tt(2, 2))
    r = g.create_op("mini.relu", [s.result], "%r", result_type=tt(2, 2))
    g.set_outputs([r.result])
    return g


def build_shared_result_graph():
    """加法结果 %s 被 relu 和 return 同时使用——不能吸收 Relu 的组合。"""
    g = Graph("shared_result")
    va = g.add_input("%a", tt(2, 3))
    vb = g.add_input("%b", tt(3, 2))
    vbias = g.add_input("%bias", tt(2, 2))
    m = g.create_op("mini.matmul", [va, vb], "%m", result_type=tt(2, 2))
    s = g.create_op("mini.add", [m.result, vbias], "%s", result_type=tt(2, 2))
    r = g.create_op("mini.relu", [s.result], "%r", result_type=tt(2, 2))
    g.set_outputs([r.result, s.result])
    return g


def build_multi_user_product_graph():
    """乘积 %m 被 add 和另一个 relu 同时使用——拒绝是恒等变换（Day 52/53）。"""
    g = Graph("multi_product")
    va = g.add_input("%a", tt(2, 3))
    vb = g.add_input("%b", tt(3, 2))
    vbias = g.add_input("%bias", tt(2, 2))
    m = g.create_op("mini.matmul", [va, vb], "%m", result_type=tt(2, 2))
    s = g.create_op("mini.add", [m.result, vbias], "%s", result_type=tt(2, 2))
    r = g.create_op("mini.relu", [s.result], "%r", result_type=tt(2, 2))
    t = g.create_op("mini.relu", [m.result], "%t", result_type=tt(2, 2))
    g.set_outputs([r.result, t.result])
    return g


# ===================== 演示主程序 =====================

def report(g, expect, extra=""):
    g.print_ir()
    matmul, add, flops, passes = count_cost(g)
    print(f"matmul 执行 = {matmul}，add 执行 = {add}，"
          f"FLOPs = {flops}，张量读写遍数 = {passes}{extra}")
    out = evaluate(g, FEED)
    for name, ref in expect.items():
        v = out[name]
        print(f"{name} = {v.tolist()}   期望 {ref.tolist()}   "
              f"{'一致' if np.allclose(v, ref) else '不一致!'}")


def run_set(g, patterns, visit="bottom-up", max_visits=100):
    drv = GreedyDriver(g, patterns, visit=visit, max_visits=max_visits)
    n = drv.run()
    return n


def main():
    print("===== 参考数值（numpy 直算）=====")
    print(f"%m = A·B        = {REF_PRODUCT.tolist()}")
    print(f"%s = %m + bias  = {REF_BIASED.tolist()}")
    print(f"%r = relu(%s)   = {REF_RELU.tolist()}")

    print("\n===== 场景 A：两条路线通向同一个不动点 =====")
    for label, pats in [
        ("A1 两阶段 [P1, P2]", [FuseMatmulBiasTwoStage(), AbsorbReluEpilogue()]),
        ("A1' 两阶段换插入序 [P2, P1]", [AbsorbReluEpilogue(), FuseMatmulBiasTwoStage()]),
        ("A2 直接 [P3]", [FuseMatmulBiasReluDirect()]),
        ("A3 全家桶 [P1, P2, P3]（P3 benefit=2 同 root 领先）",
         [FuseMatmulBiasTwoStage(), AbsorbReluEpilogue(), FuseMatmulBiasReluDirect()]),
        ("A4 全家桶但 P3 benefit=1（同 benefit 插入序说话）",
         [FuseMatmulBiasTwoStage(), AbsorbReluEpilogue(),
          FuseMatmulBiasReluDirect(benefit=1)]),
    ]:
        g = build_bias_relu_graph()
        n = run_set(g, pats)
        print(f"--- {label}：改写 {n} 次，最终形态 ->")
        report(g, {g.outputs[0].name: REF_RELU},
               extra=f"，改写次数 = {n}")
        print()

    print("===== 场景 B：抢跑事故——同样的 Pattern 集，访问顺序决定命运 =====")
    for visit in ("bottom-up", "top-down"):
        g = build_bias_relu_graph()
        pats = [FuseAddRelu(), FuseMatmulBiasReluDirect()]
        n = run_set(g, pats, visit=visit)
        print(f"--- 集合 [P51, P3]，visit = {visit}：改写 {n} 次，最终形态 ->")
        report(g, {g.outputs[0].name: REF_RELU},
               extra=f"，改写次数 = {n}")
        print()

    print("===== 场景 C：两种修法——让位规则 / Pass 管道顺序 =====")
    for visit in ("bottom-up", "top-down"):
        g = build_bias_relu_graph()
        pats = [FuseAddRelu(guard_matmul=True,
                            name="P51g FuseAddRelu（让位版）"),
                FuseMatmulBiasReluDirect()]
        n = run_set(g, pats, visit=visit)
        print(f"--- 让位版 [P51g, P3]，visit = {visit}：改写 {n} 次，最终形态 ->")
        report(g, {g.outputs[0].name: REF_RELU})
        print()

    g = build_bias_relu_graph()
    n1 = run_set(g, [FuseMatmulBiasReluDirect()])
    print(f"--- 管道修法：先跑 P3（改写 {n1} 次），再跑 P51 ->")
    n2 = run_set(g, [FuseAddRelu()])
    print(f"第二个 Pass 改写 {n2} 次（P51 已无可抢）。最终形态 ->")
    report(g, {g.outputs[0].name: REF_RELU})
    print()

    g = build_add_relu_only_graph()
    n1 = run_set(g, [FuseMatmulBiasReluDirect()])
    n2 = run_set(g, [FuseAddRelu()])
    print("--- 管道修法在纯 Add+Relu 图上：P3 改写 0 次，P51 正常融合 ->")
    report(g, {g.outputs[0].name: REF_ADD_RELU},
           extra=f"，改写次数 = {n2}")
    print()

    print("===== 场景 D：%s 被 return 共用——半融合形态是所有路线的共同不动点 =====")
    for label, pats in [
        ("两阶段 [P1, P2]", [FuseMatmulBiasTwoStage(), AbsorbReluEpilogue()]),
        ("直接 [P3]", [FuseMatmulBiasReluDirect()]),
    ]:
        g = build_shared_result_graph()
        run_set(g, pats)
        print(f"--- {label}，最终形态 ->")
        report(g, {"%r": REF_RELU, "%s'": REF_BIASED})
        print()

    print("===== 场景 E：乘积多使用者——新管道下的恒等变换 =====")
    g = build_multi_user_product_graph()
    before = g.op_names()
    run_set(g, [FuseMatmulBiasTwoStage(), AbsorbReluEpilogue(),
                FuseMatmulBiasReluDirect()])
    assert g.op_names() == before, "拒绝必须是恒等变换"
    report(g, {"%r": REF_RELU, "%t": np.maximum(REF_PRODUCT, 0.0)})
    print()

    print("===== 场景 F：互相打架的 Pattern——不收敛 =====")
    g = build_bias_relu_graph()
    try:
        run_set(g, [FuseMatmulBiasTwoStage(), AbsorbReluEpilogue(),
                    UnfuseMatmulBiasRelu()], max_visits=20)
        print("!! 不该走到这里：Unfuse 和 P2 应当永不收敛")
    except NonConvergence as e:
        print(f"NonConvergence: {e}")
        print("（此刻的 IR 语义仍然正确——每次改写都保持语义；浪费的是编译时间）")
        out = evaluate(g, FEED)
        print(f"{g.outputs[0].name} = {out[g.outputs[0].name].tolist()}   "
              f"期望 {REF_RELU.tolist()}   "
              f"{'一致' if np.allclose(out[g.outputs[0].name], REF_RELU) else '不一致!'}")
    print()

    print("===== 结论 =====")
    print("1. 两阶段与直接三算子在主线图上殊途同归（fused_matmul_bias_relu）；")
    print("   benefit 决定同一 root 上谁先出手，只影响改写次数，不影响不动点。")
    print("2. 抢跑事故：P51 与 P3 的 root 不同，benefit 管不到先后——")
    print("   访问顺序（bottom-up / top-down）决定最终形态，这就是「偶然执行顺序」。")
    print("3. 修法一：P51g 让位规则（add 的操作数是乘积就收手）；")
    print("   修法二：Pass 管道顺序（大融合的 Pass 先跑）。两种都不依赖驱动心情。")
    print("4. 互相为逆的 Pattern 会让工作表永不排空——护栏（maxIterations/")
    print("   maxNumRewrites/访问上限）只能止损，纪律才是根本。")


if __name__ == "__main__":
    main()
