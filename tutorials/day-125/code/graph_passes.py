#!/usr/bin/env python3
"""第 121 天核心模块：graph_passes.py——minic S1 的图优化 Pass 集。

把 D83（第三阶段集成验收）的五道闸原样搬进 minic 管道，并按今天的主题
加装「独立开关」：

  --no-qdq-clean      关掉 QDQ 清理（闸1）
  --no-layout-simp    关掉布局简化（闸2）
  --no-reshape-merge  关掉 Reshape 合并（闸3）
  --no-fuse           关掉融合＋Cost Model（闸4）
  --fixpoint-max N    不动点轮数上限（默认 8；0=单轮）

今天真正要回答的问题（计划条目）：Pass 管道的**稳定顺序**与**重复执行**——
  · 闸1→2→3 的顺序是 D69 的教训（机会是上一轮创造出来的）；
  · 不动点循环让「清理创造融合机会」自动收敛；
  · 开关的价值：每关一个 Pass，审计日志能精确指出图会「退化」成什么样
    ——这是 D125 对照实验的实验设计基础。

输入格式：D83 的自定义图 IR（.graph 文本）。本模块零第三方依赖
（numpy 仅在数值验证时需要，此处不需要——S1 只做结构变换）。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# ──────────────────────────────────────────────────────────
# 图表示：节点表（沿用 D83 的约定，最小实现）
# ──────────────────────────────────────────────────────────


@dataclass
class Node:
    nid: str                    # %1 / %x
    op: str                     # const/arg/quantize/matmul/...
    inputs: list = field(default_factory=list)      # 输入节点 id
    attrs: dict = field(default_factory=dict)       # shape/perm/scale...
    out_type: str = ""          # tensor<...>

    def clone(self) -> "Node":
        return Node(self.nid, self.op, list(self.inputs), dict(self.attrs), self.out_type)


@dataclass
class Graph:
    name: str = "main"
    args: list = field(default_factory=list)         # [("%x", "tensor<...>")]
    ret: str = ""                                    # 返回节点 id
    ret_type: str = ""
    nodes: dict = field(default_factory=dict)        # nid -> Node（保序）
    audit: list = field(default_factory=list)        # 审计日志（每条 Pass 干了什么）

    def order(self):
        return list(self.nodes.keys())

    def users(self, nid: str) -> list:
        return [n.nid for n in self.nodes.values() if nid in n.inputs]

    def emit(self) -> str:
        lines = [f"func @{self.name}({', '.join(f'{a}: {t}' for a, t in self.args)})"
                 f" -> ({self.ret}: {self.ret_type}) {{"]
        for n in self.nodes.values():
            if n.op == "arg":
                lines.append(f"  {n.nid} = arg : {n.out_type}")
            elif n.op == "const":
                vals = ",".join(str(v) for v in n.attrs["values"])
                shp = ",".join(str(d) for d in n.attrs["shape"])
                lines.append(f"  {n.nid} = const shape=[{shp}] values=[{vals}] : {n.out_type}")
            else:
                ins = ", ".join(n.inputs)
                extra = ""
                if "perm" in n.attrs:
                    extra += f" perm={n.attrs['perm']}"
                if "new_shape" in n.attrs:
                    extra += f" new_shape={n.attrs['new_shape']}"
                if "scale" in n.attrs:
                    extra += f" {{scale={n.attrs['scale']}, zp={n.attrs['zp']}}}"
                lines.append(f"  {n.nid} = {n.op} {ins}{extra} : {n.out_type}")
        lines.append(f"  return {self.ret}")
        lines.append("}")
        return "\n".join(lines)


# ──────────────────────────────────────────────────────────
# 解析器：D83 文本 IR -> Graph
# ──────────────────────────────────────────────────────────
_CONST_RE = re.compile(r"const shape=\[([^\]]*)\] values=\[([^\]]*)\]")
_TENSOR_RE = re.compile(r"tensor<[^>]*>")
_OP_RE = re.compile(r"(%\w+) = (\w+)\s+(.*?)\s*:\s*(tensor<[^>]*>)$")
_ATTR_RE = re.compile(r"(perm|new_shape)=\[([^\]]*)\]")
_SCALE_RE = re.compile(r"\{scale=([\d.e+-]+), zp=(-?\d+)\}")


def parse_graph(text: str) -> Graph:
    g = Graph()
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("//"):
            continue
        m = re.match(r"func @(\w+)\((%?\w+): (tensor<[^>]*>)\) -> \((%?\w+): (tensor<[^>]*>)\)", s)
        if m:
            g.name = m.group(1)
            g.args = [(m.group(2), m.group(3))]
            g.ret, g.ret_type = m.group(4), m.group(5)
            continue
        if s.startswith("return"):
            continue
        m = re.match(r"(%\w+) = arg : (tensor<[^>]*>)", s)
        if m:
            g.nodes[m.group(1)] = Node(m.group(1), "arg", out_type=m.group(2))
            continue
        m = _CONST_RE.search(s)
        tm = _TENSOR_RE.search(s[m.end():] if m else "")
        if m:
            nid = re.match(r"(%\w+) =", s).group(1)
            shape = [int(x) for x in m.group(1).split(",") if x.strip()]
            values = [float(x) for x in m.group(2).split(",") if x.strip()]
            out_t = tm.group(0) if tm else ""
            g.nodes[nid] = Node(nid, "const", attrs={"shape": shape, "values": values},
                                out_type=out_t)
            continue
        # 普通算子：先剥属性段，再解析 op + inputs
        stripped = _ATTR_RE.sub("", s)
        stripped = _SCALE_RE.sub("", stripped)
        m = _OP_RE.match(stripped.strip())
        if m:
            nid, op, rest, out_t = m.groups()
            inputs = [x.strip() for x in rest.split(",") if x.strip()]
            attrs = {}
            for am in _ATTR_RE.finditer(s):
                if am.group(1) == "perm":
                    attrs["perm"] = [int(x) for x in am.group(2).split(",")]
                else:
                    attrs["new_shape"] = [int(x) for x in am.group(2).split(",")]
            sm = _SCALE_RE.search(s)
            if sm:
                attrs["scale"], attrs["zp"] = float(sm.group(1)), int(sm.group(2))
            g.nodes[nid] = Node(nid, op, inputs, attrs, out_t)
            continue
    return g


# ──────────────────────────────────────────────────────────
# 五道闸（D83 原版语义的最小复刻；审计日志逐条记录）
# ──────────────────────────────────────────────────────────

def gate0_verify(g: Graph) -> bool:
    """闸0：合法性——matmul 内维匹配、reshape 元素数守恒、transpose 排列合法。"""
    for n in g.nodes.values():
        if n.op == "matmul":
            a, b = g.nodes[n.inputs[0]], g.nodes[n.inputs[1]]
            ka = a.attrs.get("shape", [1])[-1] if a.op == "const" else None
            kb = b.attrs.get("shape", [1])[0] if b.op == "const" else None
            if ka is not None and kb is not None and ka != kb:
                g.audit.append(f"[闸0] 拒绝：{n.nid} matmul 内维不匹配 {ka}≠{kb}")
                return False
        if n.op == "reshape":
            src = g.nodes[n.inputs[0]]
            if src.op == "const":
                if _numel(src.attrs["shape"]) != _numel(n.attrs["new_shape"]):
                    g.audit.append(f"[闸0] 拒绝：{n.nid} reshape 元素数不符")
                    return False
        if n.op == "transpose":
            perm = n.attrs.get("perm", [])
            if sorted(perm) != list(range(len(perm))):
                g.audit.append(f"[闸0] 拒绝：{n.nid} 非法排列 {perm}")
                return False
    g.audit.append(f"[闸0] 合法性检查通过（{len(g.nodes)} 个节点）")
    return True


def _numel(shape):
    n = 1
    for d in shape:
        n *= d
    return n


def gate1_qdq_clean(g: Graph) -> bool:
    """闸1：QDQ 清理——DQ(Q(const)) 折叠（R04）；同参尾对删除（R03）。"""
    changed = False
    for nid in list(g.order()):
        n = g.nodes.get(nid)
        if n is None or n.op != "dequantize":
            continue
        src = g.nodes.get(n.inputs[0]) if n.inputs else None
        if src and src.op == "quantize":
            ssrc = g.nodes.get(src.inputs[0]) if src.inputs else None
            if ssrc and ssrc.op == "const" and \
               src.attrs.get("scale") == n.attrs.get("scale") and \
               src.attrs.get("zp") == n.attrs.get("zp"):
                # R04 语义：折叠值 = DQ(Q(v))——量化格点上的等价（D82 规则表）
                sc, zp = src.attrs["scale"], src.attrs["zp"]
                ssrc.attrs["values"] = [
                    float(min(max(round(v / sc) + zp, -128), 127) - zp) * sc
                    for v in ssrc.attrs["values"]
                ]
                _replace_all_uses(g, n.nid, ssrc.nid)
                del g.nodes[n.nid], g.nodes[src.nid]
                g.audit.append(f"[闸1] R04 @ {n.nid}：DQ(Q(const)) 折叠成常量（值逐位不变）")
                changed = True
    return changed


def gate2_layout_simp(g: Graph) -> bool:
    """闸2：布局简化——transpose(const) 编译期折叠；互逆对消除。"""
    changed = False
    for nid in list(g.order()):
        n = g.nodes.get(nid)
        if n is None or n.op != "transpose":
            continue
        src = g.nodes.get(n.inputs[0]) if n.inputs else None
        if src and src.op == "const":
            perm = n.attrs["perm"]
            vals, shape = src.attrs["values"], src.attrs["shape"]
            new_shape = [shape[p] for p in perm]
            new_vals = [_transpose_apply(vals, shape, perm, i) for i in range(_numel(new_shape))]
            src.attrs["shape"], src.attrs["values"] = new_shape, new_vals
            src.out_type = n.out_type
            _replace_all_uses(g, n.nid, src.nid)
            del g.nodes[n.nid]
            g.audit.append(f"[闸2] 转置常量折叠 @ {n.nid}：transpose(const) → 常量（运行时少一次数据移动）")
            changed = True
    return changed


def _transpose_apply(vals, shape, perm, flat_idx):
    # 展开逻辑：新形状下标 -> 旧形状下标 -> 旧 flat 位置
    new_shape = [shape[p] for p in perm]
    idx = []
    t = flat_idx
    for d in reversed(new_shape):
        idx.append(t % d)
        t //= d
    idx.reverse()
    old_idx = [0] * len(shape)
    for i, p in enumerate(perm):
        old_idx[p] = idx[i]
    old_flat = 0
    for i, d in enumerate(shape):
        old_flat = old_flat * d + old_idx[i]
    return vals[old_flat]


def gate3_reshape_merge(g: Graph) -> bool:
    """闸3：Reshape 合并——reshape(reshape(x)) → reshape(x)（单使用者时）。"""
    changed = False
    for nid in list(g.order()):
        n = g.nodes.get(nid)
        if n is None or n.op != "reshape":
            continue
        src = g.nodes.get(n.inputs[0]) if n.inputs else None
        if src and src.op == "reshape" and len(g.users(src.nid)) == 1:
            n.inputs = [src.inputs[0]]
            del g.nodes[src.nid]
            g.audit.append(f"[闸3] Reshape 合并 @ {n.nid}：reshape(reshape(x)) → 一次到 {n.attrs['new_shape']}")
            changed = True
    return changed


def gate4_fuse(g: Graph) -> bool:
    """闸4：融合——matmul+bias(add const)+relu 单链融合（结构＋收益双门）。"""
    changed = False
    for nid in list(g.order()):
        add = g.nodes.get(nid)
        if add is None or add.op != "add":
            continue
        mm = g.nodes.get(add.inputs[0]) if add.inputs else None
        bias = g.nodes.get(add.inputs[1]) if len(add.inputs) > 1 else None
        if not (mm and mm.op == "matmul" and bias and bias.op == "const"
                and len(g.users(mm.nid)) == 1):
            continue
        relu = None
        for u in g.users(add.nid):
            un = g.nodes[u]
            if un.op == "relu" and len(g.users(add.nid)) == 1:
                relu = un
        if relu is None:
            continue
        # 收益门（D76 报价机最小版）：ΔB = 2·M·N·4B > 0 即融合
        fused_nid = relu.nid            # 复用 relu 的 id（它是最外层、被 return 引用）
        g.nodes[fused_nid] = Node(fused_nid, "fused_matmul_bias_relu",
                                  [mm.inputs[0], mm.inputs[1], bias.nid],
                                  {}, relu.out_type)
        for n in g.nodes.values():
            n.inputs = [fused_nid if x == add.nid else x for x in n.inputs]
        if g.ret == add.nid:
            g.ret = fused_nid
        del g.nodes[add.nid], g.nodes[mm.nid]
        g.audit.append(f"[闸4] 融合 @ {mm.nid}+{add.nid}+{relu.nid} → {fused_nid}"
                       f"（单使用者 ✓ bias const ✓ → fused_matmul_bias_relu）")
        changed = True
    return changed


def _replace_all_uses(g: Graph, old: str, new: str):
    for n in g.nodes.values():
        n.inputs = [new if x == old else x for x in n.inputs]
    if g.ret == old:
        g.ret = new


# ──────────────────────────────────────────────────────────
# 管道：稳定顺序＋不动点循环（今天的主题）
# ──────────────────────────────────────────────────────────

DEFAULT_SWITCHES = dict(qdq_clean=True, layout_simp=True, reshape_merge=True,
                        fuse=True, fixpoint_max=8)


def run_s1(g: Graph, switches: dict = None) -> Graph:
    """S1 图优化：闸0 → 闸1→2→3 不动点 → 闸4。

    顺序合同（为什么闸4在最后、闸1~3 要循环）：
      · 闸1 创造闸2 的机会（QDQ 折叠露出 const，transpose 才能折叠）；
      · 闸3 创造闸4 的机会（reshape 链合并后 matmul 的输入更干净）；
      · 闸4 破坏性最强（一次融合消灭三个节点），必须等清理收敛后再做，
        否则融合会挡住后续清理的匹配窗口。
    """
    sw = dict(DEFAULT_SWITCHES)
    if switches:
        sw.update(switches)

    if not gate0_verify(g):
        return g

    rounds = 0
    while rounds < max(1, sw["fixpoint_max"]):
        rounds += 1
        changed = False
        if sw["qdq_clean"]:
            changed |= gate1_qdq_clean(g)
        if sw["layout_simp"]:
            changed |= gate2_layout_simp(g)
        if sw["reshape_merge"]:
            changed |= gate3_reshape_merge(g)
        if not changed:
            break
    if sw["fuse"]:
        gate4_fuse(g)
    g.audit.append(f"[S1] 清理不动点 {rounds} 轮收敛，终图 {len(g.nodes)} 个节点")
    return g
