#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第 82 天实验：量化图中的 Cast 与 QDQ——冗余消除的判定与安全实现。

运行方式：
    python3 qdq_lab.py

内容：
  1. mini 图 IR：Node(kind, ...) + Graph，拓扑求值（值存 float64 容器，dtype 是标签，
     与 fake-quant 用 float 模拟 int8 同一思路）；
  2. classify()：对图中每对相邻转换节点打规则标签（R01~R13，SAFE / CONDITIONAL / UNSAFE）；
  3. safe_optimize()：只应用 bit-exact 的安全规则（R01~R05），拒绝其余；
  4. naive_optimize()：反面教材——见到同参相邻 Q→DQ 一律当 no-op 删除；
  5. T01~T12 单元测试：每条规则一个判定用例；
  6. 实验 1~5：贯穿例子、安全优化对照、naive 翻车、Cast 往返、Cast vs Quantize 边界。

Q/DQ 公式沿用 Day 81（round_half_away 口径）：
  quantize:   q = clip(round(x/s) + zp, -128, 127)
  dequantize: x_hat = s * (q - zp)
"""

import numpy as np

QMIN, QMAX = -128, 127

# ---------------------------------------------------------------- 基础数值函数


def round_half_away(x):
    """四舍五入（.5 远离零），C round() / TFLite 口径（Day 81 T11）。"""
    return np.sign(x) * np.floor(np.abs(x) + 0.5)


def quantize(x, scale, zp, qmin=QMIN, qmax=QMAX):
    """float 值 -> 量化码（整数容器）。clip 一步不能省（Day 81 T05 回绕教训）。"""
    q = round_half_away(np.asarray(x, dtype=np.float64) / scale) + zp
    return np.clip(q, qmin, qmax).astype(np.int64)


def dequantize(q, scale, zp):
    """量化码 -> float 值：x_hat = s * (q - zp)。离开 (s, zp) 这对元数据无法解码。"""
    return scale * (np.asarray(q, dtype=np.float64) - zp)


# ---------------------------------------------------------------- dtype 与 Cast

FP = {"fp32", "fp16"}
INT = {"int8", "int32"}

# 无损放宽：目标值集合完全包含源值集合，Cast 单向精确
WIDEN_LOSSLESS = {("fp16", "fp32"), ("int8", "int32"), ("int8", "fp32")}


def cast_values(x, src, dst, mode="saturate"):
    """Cast 的值语义：只换"表示"，不带任何 (s, zp) 元数据。

    - fp32 -> fp16：就近舍入（round-to-nearest-even），溢出变 inf。不精确。
    - fp16 -> fp32：精确（fp16 的每个值都能被 fp32 精确表示）。
    - int32 -> int8：mode="saturate" 时夹到 [-128,127]；mode="wrap" 时补码回绕
      （Day 81 T05 的 32258 -> 2 就是回绕）。两种都不精确。
    - int8 -> int32 / int8 -> fp32：精确。
    - fp32 -> int8：向零截断（C 语言 (int8_t)f 的口径），再按 mode 饱和/回绕。
    """
    x = np.asarray(x, dtype=np.float64)
    if src == dst:
        return x.copy()
    if src in FP and dst in FP:
        if dst == "fp16":
            with np.errstate(over="ignore"):  # 溢出 -> inf 是文档化行为
                return np.asarray(x, dtype=np.float16).astype(np.float64)
        return x.copy()  # fp16 -> fp32 精确
    if src in INT and dst in INT:
        if dst == "int32":
            return x.copy()  # 放宽精确
        if mode == "saturate":
            return np.clip(x, QMIN, QMAX)
        return ((x.astype(np.int64) - QMIN) % 256 + QMIN).astype(np.float64)  # 回绕
    if src in FP and dst == "int8":
        t = np.trunc(x)  # C 截断：小数部分直接丢弃
        if mode == "saturate":
            return np.clip(t, QMIN, QMAX)
        return ((t.astype(np.int64) - QMIN) % 256 + QMIN).astype(np.float64)
    if src == "int8" and dst == "fp32":
        return x.copy()  # 256 个码在 fp32 里全部精确
    raise ValueError(f"不支持的 Cast: {src} -> {dst}")


# ---------------------------------------------------------------- mini 图 IR


class Node:
    def __init__(self, kind, name, inputs=(), **params):
        self.kind = kind
        self.name = name
        self.inputs = tuple(inputs)
        self.params = params
        for k, v in params.items():
            setattr(self, k, v)

    def __repr__(self):
        if self.kind == "quantize":
            return f"Q[s={self.scale:.6g},zp={self.zp}]->{self.name}"
        if self.kind == "dequantize":
            return f"DQ[s={self.scale:.6g},zp={self.zp}]->{self.name}"
        if self.kind == "cast":
            return f"Cast[{self.src}->{self.dst}]->{self.name}"
        return f"{self.kind}->{self.name}"


class Graph:
    def __init__(self, outputs):
        self.nodes = []
        self.outputs = list(outputs)

    def add(self, kind, name, inputs=(), **params):
        self.nodes.append(Node(kind, name, inputs, **params))
        return self.nodes[-1]

    def producers(self):
        return {n.name: n for n in self.nodes}

    def use_counts(self):
        uses = {}
        for n in self.nodes:
            for i in n.inputs:
                uses[i] = uses.get(i, 0) + 1
        for o in self.outputs:
            uses[o] = uses.get(o, 0) + 1
        return uses

    def evaluate(self, feed):
        env = {}
        for n in self.nodes:
            if n.kind == "input":
                env[n.name] = np.asarray(feed[n.name], dtype=np.float64)
            elif n.kind == "const":
                env[n.name] = np.asarray(n.value, dtype=np.float64)
            elif n.kind == "quantize":
                env[n.name] = quantize(env[n.inputs[0]], n.scale, n.zp)
            elif n.kind == "dequantize":
                env[n.name] = dequantize(env[n.inputs[0]], n.scale, n.zp)
            elif n.kind == "cast":
                env[n.name] = cast_values(env[n.inputs[0]], n.src, n.dst, n.mode)
            elif n.kind == "relu":
                env[n.name] = np.maximum(env[n.inputs[0]], 0.0)
            elif n.kind == "add":
                env[n.name] = env[n.inputs[0]] + env[n.inputs[1]]
            else:
                raise ValueError(f"未知算子: {n.kind}")
        return env

    def run(self, feed):
        env = self.evaluate(feed)
        return [env[o] for o in self.outputs]


def rewire(g, old, new):
    """把所有对 old 的引用改为 new（Day 45/51 的"使用者迁移"）。"""
    for n in g.nodes:
        n.inputs = tuple(new if i == old else i for i in n.inputs)
    g.outputs = [new if o == old else o for o in g.outputs]


def remove_nodes(g, names):
    g.nodes = [n for n in g.nodes if n.name not in set(names)]


def copy_graph(g):
    g2 = Graph(list(g.outputs))
    for n in g.nodes:
        g2.add(n.kind, n.name, n.inputs, **n.params)
    return g2


# ---------------------------------------------------------------- 规则判定


def same_qparams(a, b):
    return a.scale == b.scale and a.zp == b.zp


RULES = {
    "R01": ("SAFE", "Cast(T->T) 恒等转型"),
    "R02": ("SAFE", "Cast(无损放宽)->Cast(收窄回) 无损往返"),
    "R03": ("SAFE", "同参 DQ->Q->DQ：值已在格上，删尾对 bit-exact"),
    "R04": ("SAFE", "DQ(Q(const)) 编译期常量折叠"),
    "R05": ("SAFE", "Q->Cast(int 放宽)->DQ：Cast 值不变，可合并"),
    "R06": ("CONDITIONAL", "裸 Q->DQ 单对：删除=取消该边量化（QAT 策略），非 bit-exact"),
    "R07": ("UNSAFE", "Q(s1,z1)->DQ(s2,z2) 参数不同：requant，禁止删除"),
    "R08": ("UNSAFE", "码张量有其他使用者：删除即断链/改义"),
    "R09": ("UNSAFE", "Cast(fp32->fp16)->Cast(fp16->fp32)：舍入+溢出，非恒等"),
    "R10": ("UNSAFE", "Cast(int32->int8)->Cast(int8->int32)：饱和/回绕，非恒等"),
    "R11": ("UNSAFE", "Cast 三明治包住算子：改变算子计算精度"),
    "R12": ("CONDITIONAL", "DQ->op->Q 量化岛：仅当 op 有精确整数语义才可折叠"),
    "R13": ("UNSAFE", "Cast 顶替 Quantize：无 (s,zp) 元数据，语义完全不同"),
}


def classify(g):
    """遍历图，给每个可判定/需警惕的转换节点组合打规则标签。"""
    findings = []
    producers = g.producers()
    uses = g.use_counts()

    def report(rule, where, detail=""):
        verdict, desc = RULES[rule]
        findings.append((rule, verdict, desc, where, detail))

    for n in g.nodes:
        p = producers.get(n.inputs[0]) if n.inputs else None

        # ---- Cast 相关 ----
        if n.kind == "cast":
            if n.src == n.dst:
                report("R01", n.name, f"{n.src}->{n.dst}")
            elif p is not None and p.kind == "cast" and p.dst == n.src:
                if (p.src, p.dst) in WIDEN_LOSSLESS and uses[p.name] == 1:
                    report("R02", n.name, f"{p.src}->{p.dst}->{n.dst} 放宽在前")
                elif (n.src, n.dst) in WIDEN_LOSSLESS:
                    report("R09" if n.src in FP else "R10", n.name,
                           f"{p.src}->{p.dst}->{n.dst} 收窄在前")
                elif p.src == n.dst and p.dst in FP:
                    report("R09", n.name, f"{p.src}->{p.dst}->{n.dst} 收窄在前")
                elif p.src == n.dst:
                    report("R10", n.name, f"{p.src}->{p.dst}->{n.dst} 收窄在前")
            # R11: Cast 三明治包住算子（本节点把算子输出 Cast 回来）
            if p is not None and p.kind in ("relu", "add"):
                pp = producers.get(p.inputs[0]) if p.inputs else None
                if pp is not None and pp.kind == "cast":
                    report("R11", n.name,
                           f"Cast({pp.src}->{pp.dst}) -> {p.kind} -> Cast({n.src}->{n.dst})")

        # ---- DQ 相关：Q->DQ 家族 ----
        if n.kind == "dequantize" and p is not None and p.kind == "quantize":
            if not same_qparams(p, n):
                report("R07", n.name,
                       f"Q(s={p.scale:.6g},zp={p.zp}) vs DQ(s={n.scale:.6g},zp={n.zp})")
            elif uses[p.name] > 1:
                report("R08", n.name, f"{p.name} 被 {uses[p.name]} 个使用者引用")
            else:
                src = producers.get(p.inputs[0]) if p.inputs else None
                if src is not None and src.kind == "const":
                    report("R04", n.name, f"常量 {p.inputs[0]}")
                elif (src is not None and src.kind == "dequantize"
                      and same_qparams(src, p)):
                    report("R03", n.name, f"{src.name} 已把值放上格点")
                else:
                    report("R06", n.name, f"输入 {p.inputs[0]} 不保证在格上")

        # ---- R05: Q -> Cast(int 放宽) -> DQ ----
        if (n.kind == "dequantize" and p is not None and p.kind == "cast"
                and (p.src, p.dst) in WIDEN_LOSSLESS):
            pp = producers.get(p.inputs[0]) if p.inputs else None
            if pp is not None and pp.kind == "quantize":
                report("R05", n.name, f"{p.src}->{p.dst} 夹在 Q 与 DQ 之间")

        # ---- R12: DQ -> op -> Q 量化岛 ----
        if n.kind == "quantize":
            for i in n.inputs:
                src = producers.get(i)
                if src is not None and src.kind in ("relu", "add"):
                    for j in src.inputs:
                        s2 = producers.get(j)
                        if s2 is not None and s2.kind == "dequantize":
                            report("R12", n.name,
                                   f"{s2.name} -> {src.kind} -> {n.name}（{i}）")

    return findings


# ---------------------------------------------------------------- 优化器


def safe_optimize(g, verbose=False):
    """只应用 R01~R05。在副本上改写，原图保持不动便于对照验证。"""
    g = copy_graph(g)
    for _ in range(8):
        findings = classify(g)
        applied = False
        for rule, verdict, _, where, _detail in findings:
            if verdict != "SAFE":
                continue
            producers = g.producers()
            n = producers[where]
            if rule == "R01":  # Cast(T->T)
                rewire(g, n.name, n.inputs[0])
                remove_nodes(g, [n.name])
            elif rule == "R02":  # 删两个 Cast
                inner = producers[n.inputs[0]]
                rewire(g, n.name, inner.inputs[0])
                remove_nodes(g, [inner.name, n.name])
            elif rule == "R03":  # 删尾对 Q+DQ
                q = producers[n.inputs[0]]
                rewire(g, n.name, q.inputs[0])
                remove_nodes(g, [q.name, n.name])
            elif rule == "R04":  # 常量折叠（按拓扑位置插回常量节点）
                q = producers[n.inputs[0]]
                c = producers[q.inputs[0]]
                folded = dequantize(
                    quantize(np.asarray(c.value, dtype=np.float64), q.scale, q.zp),
                    n.scale, n.zp)
                new = f"{n.name}.const"
                idx = next(i for i, nd in enumerate(g.nodes) if nd.name == n.name)
                g.nodes.insert(idx, Node("const", new, (), value=folded))
                rewire(g, n.name, new)
                remove_nodes(g, [q.name, n.name])
            elif rule == "R05":  # 删夹在 Q 与 DQ 之间的无损 Cast（值不变，重标注类型）
                c = producers[n.inputs[0]]
                rewire(g, c.name, c.inputs[0])
                remove_nodes(g, [c.name])
            applied = True
            if verbose:
                print(f"    应用 {rule}: 删除 {where} 一带")
            break
        if not applied:
            return g
    return g


def naive_optimize(g):
    """反面教材：见到同参相邻 Q->DQ 就当 no-op 删掉，不做任何上下文检查。"""
    g = copy_graph(g)
    for _ in range(8):
        producers = g.producers()
        hit = None
        for n in g.nodes:
            p = producers.get(n.inputs[0]) if n.inputs else None
            if (n.kind == "dequantize" and p is not None
                    and p.kind == "quantize" and same_qparams(p, n)):
                hit = (n, p)
                break
        if hit is None:
            return g
        dq, q = hit
        rewire(g, dq.name, q.inputs[0])   # 使用者直接改读 Q 的输入
        remove_nodes(g, [q.name, dq.name])


def verify_bit_exact(g1, g2, feeds):
    """对每组输入求值两图，输出按位置对齐、必须逐位相等（np.array_equal）。

    重连会改输出张量的名字，所以按 g.outputs 的顺序对齐，而不是按名字。
    """
    max_diff = 0.0
    for f in feeds:
        e1, e2 = g1.evaluate(f), g2.evaluate(f)
        for o1, o2 in zip(g1.outputs, g2.outputs):
            a, b = e1[o1], e2[o2]
            if not np.array_equal(a, b):
                max_diff = max(max_diff, float(np.max(np.abs(a - b))))
    return max_diff == 0.0, max_diff


# ---------------------------------------------------------------- 单元测试


def build_day_graph():
    """贯穿例子：QAT 风格量化岛。x -> Q -> DQ -> Relu -> Q -> DQ -> Q -> DQ -> out。"""
    s, z = 3.5 / 255, -128
    g = Graph(["out"])
    g.add("input", "x")
    g.add("quantize", "q1", ["x"], scale=s, zp=z)
    g.add("dequantize", "x1", ["q1"], scale=s, zp=z)
    g.add("relu", "r", ["x1"])
    g.add("quantize", "q2", ["r"], scale=s, zp=z)
    g.add("dequantize", "x2", ["q2"], scale=s, zp=z)
    g.add("quantize", "q3", ["x2"], scale=s, zp=z)
    g.add("dequantize", "out", ["q3"], scale=s, zp=z)
    return g


def build_graph(spec, outputs):
    """spec: [(kind, name, inputs, params), ...] 快速建图。"""
    g = Graph(outputs)
    for kind, name, inputs, kw in spec:
        g.add(kind, name, inputs, **kw)
    return g


def run_tests():
    print("单元测试：转换节点判定与安全优化的 12 个用例")
    s, z = 3.5 / 255, -128
    s2, z2 = 3.5 / 127, 0
    x5 = np.array([-1.2, -0.5, 0.5, 1.0, 3.5])
    ok = 0

    def check(tid, cond, msg):
        nonlocal ok
        print(f"  {tid} {'PASS' if cond else 'FAIL'}  {msg}")
        ok += int(cond)

    # T01 裸 Q->DQ：判定 CONDITIONAL，safe_optimize 不动它
    g = build_graph([("input", "x", (), {}),
                     ("quantize", "q", ["x"], dict(scale=s, zp=z)),
                     ("dequantize", "out", ["q"], dict(scale=s, zp=z))], ["out"])
    f = [r for r in classify(g) if r[1] != "SAFE" or True]
    rules = [r[0] for r in classify(g)]
    g2 = safe_optimize(g)
    check("T01", "R06" in rules and len(g2.nodes) == 3,
          f"裸 Q->DQ 判 R06({rules})，safe_optimize 不改图（{len(g2.nodes)} 节点）")

    # T02 同参 DQ->Q->DQ：R03 删尾对，bit-exact
    g = build_graph([("input", "x", (), {}),
                     ("quantize", "q1", ["x"], dict(scale=s, zp=z)),
                     ("dequantize", "x1", ["q1"], dict(scale=s, zp=z)),
                     ("quantize", "q2", ["x1"], dict(scale=s, zp=z)),
                     ("dequantize", "out", ["q2"], dict(scale=s, zp=z))], ["out"])
    rules = [r[0] for r in classify(g)]
    g2 = safe_optimize(g)
    eq, _ = verify_bit_exact(g, g2, [{"x": x5}])
    check("T02", "R03" in rules and len(g2.nodes) == 3 and eq,
          f"R03 命中，{len(g.nodes)}->{len(g2.nodes)} 节点，位等价={eq}")

    # T03 参数不匹配 Q->DQ：R07 拒绝
    g = build_graph([("input", "x", (), {}),
                     ("quantize", "q", ["x"], dict(scale=s, zp=z)),
                     ("dequantize", "out", ["q"], dict(scale=s2, zp=z2))], ["out"])
    rules = [r[0] for r in classify(g)]
    g2 = safe_optimize(g)
    check("T03", "R07" in rules and len(g2.nodes) == 3,
          "参数不同判 R07（requant），safe_optimize 拒绝")

    # T04 码张量多使用者：R08 拒绝；naive 强删则求值断链
    g = build_graph([("input", "x", (), {}),
                     ("quantize", "q", ["x"], dict(scale=s, zp=z)),
                     ("dequantize", "out1", ["q"], dict(scale=s, zp=z)),
                     ("cast", "out2", ["q"], dict(src="int8", dst="fp32",
                                                  mode="saturate"))],
                    ["out1", "out2"])
    rules = [r[0] for r in classify(g)]
    gn = naive_optimize(g)
    try:
        gn.run({"x": x5})
        crash = False
    except KeyError:
        crash = True
    check("T04", "R08" in rules and crash,
          f"多使用者判 R08；naive 强删后求值 KeyError 断链={crash}")

    # T05 Cast(T->T)：R01 删除，bit-exact
    g = build_graph([("input", "x", (), {}),
                     ("cast", "c", ["x"], dict(src="fp32", dst="fp32",
                                               mode="saturate"))], ["c"])
    rules = [r[0] for r in classify(g)]
    g2 = safe_optimize(g)
    eq, _ = verify_bit_exact(g, g2, [{"x": x5}])
    check("T05", "R01" in rules and len(g2.nodes) == 1 and eq,
          "Cast(fp32->fp32) 判 R01 删除，位等价")

    # T06 int 放宽往返：R02 删除，bit-exact
    g = build_graph([("input", "q", (), {}),
                     ("cast", "w", ["q"], dict(src="int8", dst="int32",
                                               mode="saturate")),
                     ("cast", "back", ["w"], dict(src="int32", dst="int8",
                                                  mode="saturate")),
                     ("dequantize", "out", ["back"], dict(scale=s, zp=z))], ["out"])
    rules = [r[0] for r in classify(g)]
    g2 = safe_optimize(g)
    eq, _ = verify_bit_exact(g, g2, [{"q": np.array([-3, 56, 127])}])
    check("T06", "R02" in rules and len(g2.nodes) == 2 and eq,
          f"int8->int32->int8 判 R02 删两个 Cast（剩 {len(g2.nodes)} 节点），位等价")

    # T07 fp 收窄在前往返：R09 拒绝，实测非恒等
    g = build_graph([("input", "x", (), {}),
                     ("cast", "h", ["x"], dict(src="fp32", dst="fp16",
                                                mode="saturate")),
                     ("cast", "out", ["h"], dict(src="fp16", dst="fp32",
                                                 mode="saturate"))], ["out"])
    rules = [r[0] for r in classify(g)]
    g2 = safe_optimize(g)
    err = float(np.max(np.abs(
        g.run({"x": np.array([0.1, 1e5])})[0]
        - np.array([0.1, 1e5]))))
    check("T07", "R09" in rules and len(g2.nodes) == 3 and err > 0.5,
          f"fp32->fp16->fp32 判 R09 拒删；往返 |diff|max={err:.4g}（含 inf 溢出）")

    # T08 int32->int8 饱和 vs 回绕
    v = 32258
    sat = cast_values([v], "int32", "int8", mode="saturate")[0]
    wrap = cast_values([v], "int32", "int8", mode="wrap")[0]
    check("T08", sat == 127 and wrap == 2,
          f"Cast(32258, int32->int8)：饱和={sat:.0f}，回绕={wrap:.0f}（Day 81 累加器回绕再现）")

    # T09 常量折叠 DQ(Q(const))：R04，bit-exact
    g = build_graph([("const", "c", (), dict(value=[0.1, 0.2, -0.3])),
                     ("quantize", "q", ["c"], dict(scale=s, zp=z)),
                     ("dequantize", "out", ["q"], dict(scale=s, zp=z))], ["out"])
    rules = [r[0] for r in classify(g)]
    g2 = safe_optimize(g)
    eq, _ = verify_bit_exact(g, g2, [{"x": x5}])
    check("T09", "R04" in rules and eq,
          f"DQ(Q(const)) 判 R04 常量折叠，位等价={eq}")

    # T10 Q->Cast(int 放宽)->DQ：R05 合并，bit-exact
    g = build_graph([("input", "x", (), {}),
                     ("quantize", "q", ["x"], dict(scale=s, zp=z)),
                     ("cast", "w", ["q"], dict(src="int8", dst="int32",
                                               mode="saturate")),
                     ("dequantize", "out", ["w"], dict(scale=s, zp=z))], ["out"])
    rules = [r[0] for r in classify(g)]
    g2 = safe_optimize(g)
    eq, _ = verify_bit_exact(g, g2, [{"x": x5}])
    check("T10", "R05" in rules and len(g2.nodes) == 3 and eq,
          f"Q->Cast(int8->int32)->DQ 判 R05 删 Cast（剩 {len(g2.nodes)} 节点），位等价")

    # T11 Cast vs Quantize 语义边界：0.5 -> Cast=0 vs Q=-92
    c_val = cast_values([0.5], "fp32", "int8", mode="saturate")[0]
    q_val = int(quantize([0.5], s, z)[0])
    dq_of_cast = dequantize([c_val], s, z)[0]
    check("T11", c_val == 0 and q_val == -92 and abs(dq_of_cast - 1.7569) < 1e-3,
          f"Cast(0.5)={c_val:.0f}（数被截断）vs Q(0.5)={q_val}（码）；"
          f"把码位当数解码 0 -> {dq_of_cast:.4f}")

    # T12 贯穿图端到端：分类 4 项、safe 删 2 节点、bit-exact
    g = build_day_graph()
    rules = [(r[0], r[3]) for r in classify(g)]
    g2 = safe_optimize(g)
    eq, _ = verify_bit_exact(g, g2, [{"x": x5}])
    has = {"R06", "R03"}
    check("T12", has.issubset({r for r, _ in rules})
          and len(g2.nodes) == 6 and eq,
          f"贯穿图判定 {sorted(set(r for r, _ in rules))}，"
          f"{len(g.nodes)}->{len(g2.nodes)} 节点，位等价={eq}")

    print(f"  {ok}/12 通过")
    return ok


# ---------------------------------------------------------------- 实验


def experiment_1():
    print("\n实验 1：贯穿例子——QAT 风格量化岛上的模式判定")
    s, z = 3.5 / 255, -128
    x = np.array([-1.2, -0.5, 0.5, 1.0, 3.5])
    g = build_day_graph()
    print(f"  图结构: x -> Q -> DQ -> Relu -> Q -> DQ -> Q -> DQ -> out（s={s:.6g}, zp={z}）")
    print(f"  输入 x = {list(x)}")
    env = g.evaluate({"x": x})
    print(f"  q1   = {list(env['q1'])}")
    print(f"  x1   = {['%.4f' % v for v in env['x1']]}")
    print(f"  r    = {['%.4f' % v for v in env['r']]}  （Relu 真干活：负值清零）")
    print(f"  out  = {['%.4f' % v for v in env['out']]}")
    print("\n  分类器输出（转换节点模式判定）：")
    for rule, verdict, desc, where, detail in classify(g):
        print(f"    [{verdict:11s}] {rule} @ {where:4s} {desc}  {detail}")


def experiment_2():
    print("\n实验 2：安全优化器——只动 bit-exact 的部分")
    x = np.array([-1.2, -0.5, 0.5, 1.0, 3.5])
    g = build_day_graph()
    g2 = safe_optimize(g)
    eq, _ = verify_bit_exact(g, g2, [{"x": x}])
    print(f"  节点数 {len(g.nodes)} -> {len(g2.nodes)}（删除 q3/out 这对 QDQ）")
    names = [n.name for n in g2.nodes]
    print(f"  剩余节点: {' -> '.join(names)}")
    print(f"  固定输入位等价: {eq}")
    rng = np.random.default_rng(82)
    feeds = [{"x": rng.uniform(-3.5, 3.5, 10000)} for _ in range(3)]
    eq2, d = verify_bit_exact(g, g2, feeds)
    print(f"  3 组 x 10000 随机输入位等价: {eq2}（|diff|max={d:.1e}）")

    print("\n  幂等性验证（R03 的依据）：qdq(qdq(x)) 与 qdq(x) 逐位相等？")
    s, z = 3.5 / 255, -128
    for i in range(3):
        xr = rng.uniform(-3.5, 3.5, 100000)
        sr = rng.uniform(1e-3, 10.0)
        a = dequantize(quantize(dequantize(quantize(xr, s, z), s, z), s, z), s, z)
        b = dequantize(quantize(xr, s, z), s, z)
        a2 = dequantize(quantize(dequantize(quantize(xr, sr, 0), sr, 0), sr, 0), sr, 0)
        b2 = dequantize(quantize(xr, sr, 0), sr, 0)
        print(f"    批{i + 1}: 固定尺度 np.array_equal={np.array_equal(a, b)}, "
              f"随机尺度 s={sr:.4g}: {np.array_equal(a2, b2)}")


def experiment_3():
    print("\n实验 3：naive 优化器翻车——同参 Q->DQ 一律当 no-op 删")
    x = np.array([-1.2, -0.5, 0.5, 1.0, 3.5])
    g = build_day_graph()
    out_orig = g.run({"x": x})[0]
    gn = naive_optimize(g)
    out_naive = gn.run({"x": x})[0]
    names = [n.name for n in gn.nodes]
    print(f"  naive 删除 3 对 QDQ 后: {' -> '.join(names)}（{len(gn.nodes)} 节点）")
    print(f"  out_orig  = {['%.4f' % v for v in out_orig]}")
    print(f"  out_naive = {['%.4f' % v for v in out_naive]}")
    diff = np.abs(out_orig - out_naive)
    print(f"  |diff|    = {['%.4f' % v for v in diff]}  max = {diff.max():.4f}"
          f"（半格 s/2 = {3.5 / 255 / 2:.4f}）")

    s, z, s2, z2 = 3.5 / 255, -128, 3.5 / 127, 0
    print(f"\n  requant 事故（R07 为什么连试都不能试）: Q(s={s:.6g},zp={z}) -> DQ(s={s2:.6g},zp={z2})")
    q = quantize([0.5], s, z)
    wrong = dequantize(q, s2, z2)
    right = dequantize(q, s, z)
    print(f"    0.5 -> 码 {int(q[0])}，用错刻度尺解码 -> {wrong[0]:.4f}"
          f"（正确解码 {right[0]:.4f}）")

    print("\n  裸对删除的误差账（R06 为什么不是 bit-exact）:")
    rng = np.random.default_rng(821)
    xr = rng.uniform(0.0, 3.5, 100000)          # 校准范围 [0, 3.5] 内
    snap = dequantize(quantize(xr, s, z), s, z)
    err = np.abs(snap - xr)
    print(f"    范围内 100000 随机值: max|x_hat - x| = {err.max():.6f}"
          f" <= 1 格 scale = {s:.6f}")
    xo = np.array([-1.2, 3.6, 5.0])
    sn = dequantize(quantize(xo, s, z), s, z)
    print(f"    范围外对照: [-1.2, 3.6, 5.0] -> {['%.4f' % v for v in sn]}"
          f"（误差 = 到墙的距离，Day 81 图 2 的墙）")


def experiment_4():
    print("\n实验 4：Cast 往返实验——放宽在前恒等，收窄在前失真")
    rng = np.random.default_rng(822)
    x = rng.uniform(1e-3, 1e3, 100000)
    rt_fp = cast_values(cast_values(x, "fp32", "fp16"), "fp16", "fp32")
    rel = np.abs(rt_fp - x) / np.abs(x)
    print(f"  fp32 -> fp16 -> fp32（10^5 个对数均匀样本）:")
    print(f"    非恒等比例 {np.mean(rt_fp != x) * 100:.1f}%，"
          f"max rel err = {rel.max():.3e}（fp16 半 ulp 理论 2^-11 = 4.883e-4）")
    print(f"    溢出: Cast(1e5) = {cast_values([1e5], 'fp32', 'fp16')[0]}")
    q8 = np.array([-128, -3, 56, 127], dtype=np.int64)
    rt_int = cast_values(cast_values(q8, "int8", "int32"), "int32", "int8")
    print(f"  int8 -> int32 -> int8: np.array_equal = {np.array_equal(q8, rt_int)}"
          f"（放宽在前，无损往返）")
    v = 32258
    sat = cast_values([v], "int32", "int8", mode="saturate")[0]
    wrap = cast_values([v], "int32", "int8", mode="wrap")[0]
    print(f"  int32 -> int8 -> int32: 32258 饱和成 {sat:.0f}、回绕成 {wrap:.0f}"
          f"——收窄在前，信息有去无回")

    print("\n  Cast 三明治（R11）：Cast(fp32->fp16) -> Add -> Cast(fp16->fp32)")
    g = build_graph([("input", "a", (), {}),
                     ("input", "b", (), {}),
                     ("cast", "a16", ["a"], dict(src="fp32", dst="fp16",
                                                  mode="saturate")),
                     ("cast", "b16", ["b"], dict(src="fp32", dst="fp16",
                                                  mode="saturate")),
                     ("add", "s16", ["a16", "b16"], {}),
                     ("cast", "out", ["s16"], dict(src="fp16", dst="fp32",
                                                    mode="saturate"))], ["out"])
    rules = sorted(set(r[0] for r in classify(g) if r[0] == "R11"))
    a = np.array([0.1, 0.2, 1.0])
    b = np.array([0.2, 0.1, 3.0])
    out = g.run({"a": a, "b": b})[0]
    ref = a + b
    print(f"    判定: {rules}；0.1+0.2 = {ref[0]:.17f} -> 三明治后 {out[0]:.17f}"
          f"（Add 在 fp16 里算，口径变了）")


def experiment_5():
    print("\n实验 5：Cast 与 Quantize 的语义边界——0.5 的两种命运")
    s, z = 3.5 / 255, -128
    xs = [0.5, 1.0, 2.0, 3.5]
    print(f"  {'x':>6s} {'Cast(fp32->int8)':>17s} {'Q 码':>6s} {'DQ(Q(x))':>10s}")
    for xv in xs:
        c = cast_values([xv], "fp32", "int8", mode="saturate")[0]
        q = int(quantize([xv], s, z)[0])
        d = dequantize([q], s, z)[0]
        print(f"  {xv:6.1f} {c:17.0f} {q:6d} {d:10.4f}")
    c05 = cast_values([0.5], "fp32", "int8", mode="saturate")[0]
    print(f"\n  把 Cast 的结果当码位解码（真实事故形态）: "
          f"DQ({c05:.0f}) = {dequantize([c05], s, z)[0]:.4f} —— 0.5 变 1.76")
    print("  结论: Cast 只换表示、不带 (s, zp) 元数据；Quantize 是带元数据的"
          "量程映射。Cast 永远顶替不了 Quantize（R13）。")


def main():
    np.random.seed(82)
    print("第 82 天实验：量化图中的 Cast 与 QDQ（环境：Python 3.11.4 + numpy 1.26.4）\n")
    run_tests()
    experiment_1()
    experiment_2()
    experiment_3()
    experiment_4()
    experiment_5()


if __name__ == "__main__":
    main()
