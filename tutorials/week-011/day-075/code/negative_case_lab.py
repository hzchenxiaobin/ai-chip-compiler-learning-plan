#!/usr/bin/env python3
"""negative_case_lab.py —— 第 75 天主实验：构造不融合案例（负收益案例库）。

问题：第 74 天收工时留下 11 行决策日志当「原料清单」——但那只是几张表的
副产物。今天要把它变成一座**案例库**：每个案例 = 一个具体的图 + 一个明确
的「应拒绝」理由 + 一条可机检的断言。计划里点名四类负收益：

  R1 多使用者：组外使用者把中间的写趟钉死，ΔB 塌缩（+6 MiB 翻成 −2 MiB）
  R2 资源超限：活集顶爆片上容量，spill 两趟税吞掉全部收益（−31.5 MiB）
  R3 重复计算：删中间靠重算喂组外使用者，输入重读流量 64 倍于消除流量
  R4 并行度下降：每实例占用变大，并发 tile 数从 3/4 掉到 1（软代价）

案例库分两翼：
  翼 A 结构负例（图本身非法，8 例）：D74 的六类 + 今天补的两条新规则
       ——L3b 相邻算子边形状必须一致（隐式 Reshape 不在融合模式里）
       ——L6 组内拓扑序（中间的生产者必须先于消费者，防循环依赖）
  翼 B 负收益案例（图合法但应拒绝，4 类 + 4 个对照，8 例）

D75 的三条扩展（都不动 D74 的接口签名）：
  扩展① can_fuse 补 L3b/L6（合法性层补漏；d74_can_fuse 保留作回归对照）
  扩展② price_recompute：D72 流量公式在「删除＋重算」形式下的推广
  扩展③ 舒适区判据（来自 D73 检查 4f）：零 spill＋staging ok＋并发 ≥ 3，
        只用来判 R4 类（并行度）案例——账本没给并行度计价，这是阈值不是计价

产出：16 行决策日志（每个案例一行：合法性 / ΔB / spill / 净收益 / 并发 /
三个策略的动作 / 案例库判决 / 归属理由）。

运行：python3 negative_case_lab.py
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Callable

PASSED = 0
CHECKS = 0


def check(name: str, cond: bool, detail: str = "") -> bool:
    global PASSED, CHECKS
    CHECKS += 1
    print(f"[{'PASS' if cond else 'FAIL'}] {name}{(' ' + detail) if detail else ''}")
    if cond:
        PASSED += 1
    return cond


def kib(n: float) -> str:
    """字节数的友好显示：大于 1 MiB 用 MiB，大于 1 KiB 用 KiB，否则 B。"""
    if n >= 1024 * 1024:
        s = n / 1024 / 1024
        return f"{s:.2f} MiB" if s != int(s) else f"{int(s)} MiB"
    if n >= 1024:
        s = n / 1024
        return f"{s:.2f} KiB" if s != int(s) else f"{int(s)} KiB"
    return f"{int(n)} B"


# ================================================================
# 1. 机器假设卡（D73 同款）＋ 假设清单 C1–C8
# ================================================================

@dataclass(frozen=True)
class Machine:
    """机器假设卡：收益性分析的唯一机器依据（第 73 天同款，可整体替换）。"""

    name: str = "toy-core v0"
    regfile_bytes: int = 64 * 1024      # 每核寄存器堆 64 KiB
    sram_bytes: int = 192 * 1024        # 每核片上 SRAM 192 KiB
    lanes: int = 64                     # 每核 64 条并行通道
    itemsize: int = 4                   # fp32

    @property
    def onchip_bytes(self) -> int:
        return self.regfile_bytes + self.sram_bytes


ASSUMPTIONS: list[str] = [
    "C1 机器假设卡沿用第 73 天（64 KiB 寄存器堆 / 192 KiB SRAM / 64 通道 / "
    "fp32），可整体替换重算；合法性判断不读这张卡",
    "C2 keep 形式的 ΔB 与资源账沿用第 72/73/74 天：ΔB = Σ passes·elems·4，"
    "资源 = 活集 → 三级容量阶梯 → spill 两趟（下界口径）",
    "C3 扩展② 重算形式的流量账（D72 公式的推广）：中间彻底不落盘，"
    "ΔB_elim = (1＋组内读＋组外读)·elems·4；代价 = 组外使用者数 × 生产者"
    "输入字节数（每重算一遍就把生产者输入重读一遍）；只做流量，不做时间模型",
    "C4 扩展③ 舒适区判据来自第 73 天检查 4f：零 spill ＋ staging ok ＋ "
    "并发 ≥ 3；并行度是软代价、当前账本未计价——这是阈值报告，不是计价模型",
    "C5 扩展① 合法性补两条：L3b 相邻算子的边形状必须一致（链上边 = 下一算子"
    "的第一个输入；隐式 Reshape 不在融合模式里）；L6 组内拓扑序——中间的"
    "生产者序号必须小于所有消费者序号（防循环依赖）",
    "C6 案例库只构造案例＋记录判据，不替换第 76 天的 Cost Model：R1/R2 用"
    "D74 的门原样判，R3 用流量推广公式判，R4 用舒适区阈值判——统一计价是 D76",
    "C7 策略语义沿用第 74 天：conservative 拒 spill>0 与收益未知；auto 只看"
    "净收益>0；force 只看合法性。「应拒绝」= 三策略中 conservative 与 auto "
    "一致拒绝，或 D75 扩展判据拒绝",
    "C8 不计 launch、编译时间、多核竞争与跨核 SRAM 竞争（沿用第 73 天 A8）；"
    "MM→MM 沿用 A10 按行块调度模型计（输入分块不建模）",
]


# ================================================================
# 2. 候选的图结构描述（与第 74 天同构；Intermediate 加拓扑字段供 L6 用）
# ================================================================

@dataclass(frozen=True)
class Op:
    """融合组里的一个算子。静态维度用非负整数，未知维度用 -1（D61 口径）。"""

    kind: str                                        # "matmul" | "add" | "relu"
    in_shapes: tuple[tuple[int, ...], ...]
    out_shape: tuple[int, ...]
    dtype: str = "fp32"
    pure: bool = True                                # L2：副作用算子不许进组


@dataclass(frozen=True)
class Intermediate:
    """组内生产的中间 Tensor 的使用者关系（D52 口径）＋ 拓扑信息（D75 新增）。

    in_group_users  组内消费者数（这些读在融合后消失）
    out_group_users 组外消费者数（这些读必须保留；kept=True 或走重算形式）
    kept            组外 > 0 时是否保留落盘（keep 策略）；False 且组外 > 0 → 非法
    elems           元素数；未知（动态）填 -1
    producer        生产它的算子序号（D75：L6 拓扑序检查用；None = 不检查）
    consumers       组内消费它的算子序号（D75：L6 用；() = 不检查）
    """

    name: str
    elems: int
    in_group_users: int
    out_group_users: int
    kept: bool = False
    producer: int | None = None
    consumers: tuple[int, ...] = ()


@dataclass(frozen=True)
class FusionCandidate:
    """一个待过门的融合候选：结构（合法性读）＋ 资源上下文（收益性读）。"""

    name: str
    ops: tuple[Op, ...]
    intermediates: tuple[Intermediate, ...] = ()
    workload: tuple[int, int, int] | None = None     # (M, K, N)；动态维 -1
    tile: tuple[int, int] | None = None              # (tile_m, tile_n)；None = 不分块


SUPPORTED_PATTERNS: dict[tuple[str, ...], str] = {
    ("matmul", "add"): "mini.fused_matmul_bias",
    ("matmul", "add", "relu"): "mini.fused_matmul_bias_relu",
    ("add", "relu"): "mini.fused_add_relu",
    ("matmul", "matmul"): "experimental.matmul_matmul",
}
SUPPORTED_DTYPES = {"fp32"}


# ================================================================
# 3. 第一层：合法性 Pattern —— D74 的 L1–L5 ＋ D75 补的 L3b / L6
# ================================================================

@dataclass
class LegalityReport:
    ok: bool
    reasons: list[str] = field(default_factory=list)
    pattern_name: str = ""
    kept_outputs: list[str] = field(default_factory=list)
    dynamic: bool = False


def _dims_compatible(a: tuple[int, ...], b: tuple[int, ...]) -> bool:
    """静态维度必须一致；-1（未知）通配——合法性与『能否确定』分开（D61）。"""
    if len(a) != len(b):
        return False
    return all(x == y or x < 0 or y < 0 for x, y in zip(a, b))


def _check_legality(c: FusionCandidate, *, l3b: bool, l6: bool) -> LegalityReport:
    """合法性检查主体。l3b/l6 关掉时 = 第 74 天的规则集（回归对照用）。"""
    reasons: list[str] = []
    kinds = tuple(op.kind for op in c.ops)
    pattern_name = SUPPORTED_PATTERNS.get(kinds, "")

    if not pattern_name:                                    # L1
        reasons.append(f"L1 算子链 {kinds} 不在支持的模式里（D50 定义 + 1 个实验模式）")
    for op in c.ops:                                       # L2
        if not op.pure:
            reasons.append(f"L2 {op.kind} 有副作用，不能进融合组（D25 口径）")
    for op in c.ops:                                       # L3 / L5
        if op.dtype not in SUPPORTED_DTYPES:
            reasons.append(f"L5 dtype {op.dtype} 暂不支持（D50 的融合算子只定义了 fp32）")
        if op.kind == "matmul":
            (m, k1), (k2, n) = op.in_shapes
            if k1 != k2 and k1 >= 0 and k2 >= 0:
                reasons.append(f"L3 MatMul 内维不匹配：{k1} != {k2}（D39 规则）")
            elif not _dims_compatible(op.out_shape, (m, n)):
                reasons.append(f"L3 MatMul 输出形状 {op.out_shape} != ({m},{n})（D39 规则）")
        elif op.kind in ("add", "relu"):
            outs = [op.out_shape, *op.in_shapes]
            if not all(_dims_compatible(s, outs[0]) for s in outs[1:]):
                reasons.append(f"L3 逐元素 {op.kind} 的 Shape 不完全一致（D40 规则）")
    if l3b:                                                 # L3b（D75 新增）
        for i in range(len(c.ops) - 1):
            edge_from = c.ops[i].out_shape
            edge_to = c.ops[i + 1].in_shapes[0]
            if not _dims_compatible(edge_from, edge_to):
                reasons.append(
                    f"L3b 边形状不匹配：算子{i}({c.ops[i].kind}) 输出 {edge_from} "
                    f"!= 算子{i+1}({c.ops[i+1].kind}) 输入 {edge_to}"
                    "（隐式 Reshape 不在融合模式里）")
    for it in c.intermediates:                             # L4
        if it.out_group_users > 0 and not it.kept:
            reasons.append(f"L4 中间 {it.name} 有 {it.out_group_users} 个组外使用者"
                           "且未保留落盘（D52：删除中间 = 偷走别人的输入）")
        if it.in_group_users == 0 and it.out_group_users == 0:
            reasons.append(f"L4 中间 {it.name} 没有任何使用者（DCE 的事，不该当融合候选）")
    if l6:                                                  # L6（D75 新增）
        for it in c.intermediates:
            if it.producer is not None and it.consumers:
                bad = [k for k in it.consumers if it.producer >= k]
                if bad:
                    reasons.append(
                        f"L6 组内循环依赖：中间 {it.name} 由算子{it.producer} 生产、"
                        f"却被算子{bad} 消费——生产者必须先于消费者（拓扑序）")

    dynamic = any(d < 0 for op in c.ops for s in (op.out_shape, *op.in_shapes)
                  for d in s)
    kept = [it.name for it in c.intermediates if it.kept]
    return LegalityReport(ok=not reasons, reasons=reasons,
                          pattern_name=pattern_name, kept_outputs=kept,
                          dynamic=dynamic)


def can_fuse(c: FusionCandidate) -> LegalityReport:
    """能否融合：结构/语义问题，与机器无关、与收益无关（D75 规则集）。"""
    return _check_legality(c, l3b=True, l6=True)


def d74_can_fuse(c: FusionCandidate) -> LegalityReport:
    """D74 的规则集（无 L3b/L6）——只作回归对照，证明两条新规则各拦住一个漏网案例。"""
    return _check_legality(c, l3b=False, l6=False)


# ================================================================
# 4. 第二层：收益性分析 —— D74 原样（keep 形式）
# ================================================================

@dataclass
class ProfitReport:
    known: bool = True
    delta_b: int = 0                # D72 口径：被消除中间的省流量（keep 形式）
    reg_demand: int = 0             # D73 公式：必须驻寄存器的活集
    extra_live: int = 0             # 额外活集（MM→MM 的 G 行块）
    sram_demand: int = 0            # A/B 分块驻留
    live_bytes: int = 0
    demoted_bytes: int = 0
    spill_bytes: int = 0
    spill_traffic: int = 0          # = 2 × spill_bytes × 缩放（D73 A4 下界）
    net_gain: int = 0               # = ΔB − spill 流量
    placement: str = ""
    concurrent_tiles: int = 1
    staging_ok: bool = True
    instr_overhead: float | None = None
    redeem_rate: float | None = None
    recompute_penalty: int = 0      # D75 扩展②：重算形式的生产者输入重读流量
    recompute_elim: int = 0         # D75 扩展②：中间彻底不落盘省下的全部流量
    reasons: list[str] = field(default_factory=list)


def _d72_passes(it: Intermediate) -> int:
    """D72 多使用者规则：组外无人 → 写＋组内读全消失；组外有人 → 只省组内读。"""
    return (1 + it.in_group_users) if it.out_group_users == 0 else it.in_group_users


def _resource_side(c: FusionCandidate, m: Machine, r: ProfitReport) -> None:
    """D73 的资源账（keep 与重算共用：融合核结构一样，只是 C 落不落盘）。"""
    kinds = tuple(op.kind for op in c.ops)
    M, K, N = c.workload
    tm, tn = c.tile if c.tile is not None else (M, N)

    if "matmul" in kinds:
        r.reg_demand = tm * tn * m.itemsize                 # 累加器块
        if "add" in kinds:                                   # bias 在飞：每通道 1 槽
            r.reg_demand += m.lanes * m.itemsize
        r.sram_demand = (tm * K + K * tn) * m.itemsize       # A/B 分块（有复用才驻留）
        if kinds == ("matmul", "matmul"):                    # G 行块（消费者归约维钉死）
            Kmid = c.ops[0].out_shape[1]
            r.extra_live = tm * Kmid * m.itemsize
            r.sram_demand = 0                                # D73 A10：输入分块不建模
    else:                                                    # (add, relu)：在飞向量
        r.reg_demand = m.lanes * (2 + 1) * m.itemsize        # 2 入 1 出（D73 A5）

    r.live_bytes = r.reg_demand + r.extra_live
    demoted = min(max(0, r.live_bytes - m.regfile_bytes), m.sram_bytes)
    r.demoted_bytes = demoted
    r.spill_bytes = max(0, r.live_bytes - m.onchip_bytes)
    r.placement = ("spill" if r.spill_bytes > 0
                   else "reg+sram" if demoted > 0 else "reg")
    staging_left = m.sram_bytes - demoted
    r.staging_ok = r.sram_demand <= staging_left
    reg_cap = m.regfile_bytes // max(1, r.reg_demand)
    sram_cap = (staging_left // r.sram_demand) if r.sram_demand > 0 else None
    r.concurrent_tiles = max(1, reg_cap if sram_cap is None
                             else min(reg_cap, sram_cap))     # D73 教训：下限 1

    scale = (M // tm) if kinds == ("matmul", "matmul") else 1  # B8：MM→MM 按行块
    r.spill_traffic = 2 * r.spill_bytes * scale


def should_fuse(c: FusionCandidate, m: Machine) -> ProfitReport:
    """是否值得融合（keep 形式）：账本问题，输入 = 候选 + 机器假设卡。

    接口契约与 D74 完全一致：不重查结构；动态维度算不出账 → known=False。
    """
    r = ProfitReport()
    kinds = tuple(op.kind for op in c.ops)
    M, K, N = c.workload if c.workload is not None else (None, None, None)
    tm, tn = c.tile if c.tile is not None else (M, N)

    if M is None or tm is None or tn is None or min(M, K, N, tm, tn) < 0 \
            or any(it.elems < 0 for it in c.intermediates):
        r.known = False
        r.reasons.append("动态维度：活集与 ΔB 都无法估算（D61/D62：未知 ≠ 任意）")
        return r

    r.delta_b = sum(_d72_passes(it) * it.elems * m.itemsize for it in c.intermediates)
    _resource_side(c, m, r)
    r.net_gain = r.delta_b - r.spill_traffic
    r.redeem_rate = (r.net_gain / r.delta_b) if r.delta_b > 0 else None
    if kinds in (("matmul", "add"), ("matmul", "add", "relu")) and K > 0:
        r.instr_overhead = 2 / K                             # D73 §6：epilogue 增量
    return r


def price_recompute(c: FusionCandidate, m: Machine) -> ProfitReport:
    """D75 扩展②：「删除＋重算」形式的流量账（D72 公式的推广）。

    与 keep 形式的差别：中间彻底不落盘——写、组内读、组外读全部消失；
    代价：每个组外使用者都要把生产者（算子 0）的输入重读一遍。
    只做流量账（C3），不做时间模型；多中间的重算调度不建模（D76 的活）。
    """
    r = ProfitReport()
    M, K, N = c.workload if c.workload is not None else (None, None, None)
    if M is None or K is None or N is None or c.tile is None \
            or min(M, K, N, *c.tile) < 0 or any(it.elems < 0 for it in c.intermediates):
        r.known = False
        r.reasons.append("动态维度：重算账算不出（D61/D62）")
        return r

    r.recompute_elim = sum((1 + it.in_group_users + it.out_group_users)
                           * it.elems * m.itemsize for it in c.intermediates)
    producer_in_elems = 0
    for dims in c.ops[0].in_shapes:
        e = 1
        for d in dims:
            e *= max(d, 0)
        producer_in_elems += e
    r.recompute_penalty = sum(it.out_group_users for it in c.intermediates) \
        * producer_in_elems * m.itemsize
    _resource_side(c, m, r)
    r.delta_b = r.recompute_elim                            # 口径：消除的总流量
    r.net_gain = r.recompute_elim - r.recompute_penalty - r.spill_traffic
    r.redeem_rate = (r.net_gain / r.recompute_elim) if r.recompute_elim > 0 else None
    if not any(it.out_group_users > 0 for it in c.intermediates):
        r.reasons.append("无组外使用者：重算形式没有意义（keep 已经全省）")
    return r


# ================================================================
# 5. 第三层：策略（D74 原样）＋ D75 舒适区判据
# ================================================================

@dataclass
class Decision:
    action: str                     # "fuse" | "refuse"
    policy: str
    reasons: list[str] = field(default_factory=list)
    hint: str = ""


def decide(leg: LegalityReport, prof: ProfitReport | None,
           policy: str = "conservative") -> Decision:
    """决策 = 合法性 ∧ 策略(收益)。报告是唯一输入——换策略不动前两层（D74 原样）。"""
    if not leg.ok:
        return Decision("refuse", policy, ["合法性：" + r for r in leg.reasons],
                         "先修结构/语义，再谈收益（负例库翼 A）")
    if policy == "force":
        return Decision("fuse", policy, ["合法性通过；force 模式只看合法性（A/B 实验用）"])
    if prof is None or not prof.known:
        why = "收益未知：动态维度算不出活集与 ΔB" if leg.dynamic else "收益未知"
        return Decision("refuse", policy, [why], "D62：特化成静态 Shape 后重新进门")

    if policy == "conservative":
        if prof.spill_bytes > 0:
            hint = ("spill 成本是下界（D73 A4：真实更贵）；先缩小 tile 再重试"
                    if prof.net_gain > 0 else
                    "spill 流量吞掉全部收益：不值得融合")
            return Decision("refuse", policy,
                            [f"保守策略：spill {prof.spill_bytes:,} B > 0"
                             f"（D73 阶梯第 3 级），净收益按下界 {prof.net_gain:,} B"],
                            hint)
        if prof.net_gain <= 0:
            return Decision("refuse", policy,
                            [f"保守策略：净收益 {prof.net_gain} B ≤ 0（基线是 0）"])
        return Decision("fuse", policy,
                        [f"合法性通过；净收益 {prof.net_gain:,} B > 0 且零 spill"
                         f"（落位 {prof.placement}）"])
    if policy == "auto":
        if prof.net_gain > 0:
            return Decision("fuse", policy,
                            [f"合法性通过；净收益（下界）{prof.net_gain:,} B > 0"])
        return Decision("refuse", policy, [f"净收益 {prof.net_gain} B ≤ 0"])
    raise ValueError(f"未知策略：{policy}")


def comfort_ok(prof: ProfitReport) -> bool:
    """D75 扩展③：D73 检查 4f 的舒适区——零 spill ＋ staging ok ＋ 并发 ≥ 3。"""
    return prof.spill_bytes == 0 and prof.staging_ok and prof.concurrent_tiles >= 3


# ================================================================
# 6. 案例库：两翼 16 例（结构负例 8 ＋ 负收益 4 类 8 例）
# ================================================================

@dataclass
class CaseEntry:
    name: str                      # 决策日志用名
    wing: str                      # "A 结构负例" | "B 负收益"
    cat: str                       # 类别标签
    why: str                       # 一行「为什么应拒绝 / 为什么对照放行」
    build: Callable[[], FusionCandidate]
    kind: str = "gate"             # "gate"=走 D74 门 | "recompute"=重算账 | "comfort"=门+舒适区
    expect_gate: str = "refuse"    # D74 门（conservative）期望
    expect_lib: str = "refuse"     # 案例库判决期望


def chain_ops(M: int, K: int, N: int) -> tuple[Op, ...]:
    """贯穿链 MatMul(M,K)@B(K,N) → +D → relu 的算子序列（D39/D40 规则全过）。"""
    return (Op("matmul", ((M, K), (K, N)), (M, N)),
            Op("add", ((M, N), (M, N)), (M, N)),
            Op("relu", ((M, N),), (M, N)))


def cand_full(M: int, K: int, N: int, tile: tuple[int, int] | None = None,
              name: str = "P3 全融合") -> FusionCandidate:
    """贯穿链全融合：C、E 组内消化（D50 的 fused_matmul_bias_relu）。"""
    return FusionCandidate(name, chain_ops(M, K, N),
                           intermediates=(Intermediate("C", M * N, 1, 0),
                                          Intermediate("E", M * N, 1, 0)),
                           workload=(M, K, N), tile=tile)


def cand_mm_mm(M: int, K: int, Kmid: int, N: int, tile: tuple[int, int],
               out_users: int = 0, name: str | None = None) -> FusionCandidate:
    """MatMul(M,K)→G(M,Kmid)→MatMul(Kmid,N)；out_users>0 时 G 有组外使用者（keep）。"""
    ops = (Op("matmul", ((M, K), (K, Kmid)), (M, Kmid)),
           Op("matmul", ((M, Kmid), (Kmid, N)), (M, N)))
    kept = out_users > 0
    return FusionCandidate(name or f"MM→MM K1={Kmid}", ops,
                           intermediates=(Intermediate("G", M * Kmid, 1, out_users,
                                                        kept=kept),),
                           workload=(M, K, N), tile=tile)


def cand_skinny(M: int, K: int, N: int, out_users: int = 2,
                name: str = "skinny {MatMul,Add}") -> FusionCandidate:
    """瘦矩阵 MatMul(M,K)→C(M,N)→+D：C 有 out_users 个组外使用者（D73/D74 口径）。"""
    ops = (Op("matmul", ((M, K), (K, N)), (M, N)),
           Op("add", ((M, N), (M, N)), (M, N)))
    return FusionCandidate(name, ops,
                           intermediates=(Intermediate("C", M * N, 1, out_users,
                                                        kept=out_users > 0),),
                           workload=(M, K, N), tile=(M, N))


# ---- 翼 A：结构负例（D74 的六类 ＋ D75 新增两类）----

def wing_a_cases() -> list[CaseEntry]:
    M0, K0, N0 = 2, 3, 2
    return [
        CaseEntry("A1 模式不支持", "A 结构负例", "L1 模式",
                   "Relu→MatMul 不在 D50 的融合模式里", lambda: FusionCandidate(
                       "A1 Relu→MatMul",
                       (Op("relu", ((2, 2),), (2, 2)),
                        Op("matmul", ((2, 2), (2, 2)), (2, 2))))),
        CaseEntry("A2 副作用算子", "A 结构负例", "L2 纯度",
                   "组内有副作用的算子，融合会改变可观察行为", lambda: FusionCandidate(
                       "A2 副作用 add",
                       (Op("matmul", ((2, 3), (3, 2)), (2, 2)),
                        Op("add", ((2, 2), (2, 2)), (2, 2), pure=False),
                        Op("relu", ((2, 2),), (2, 2))))),
        CaseEntry("A3 逐元素 Shape 不齐", "A 结构负例", "L3 Shape",
                   "add 的输入形状不一致，逐元素规则（D40）不过", lambda: FusionCandidate(
                       "A3 Shape 不一致",
                       (Op("matmul", ((2, 3), (3, 2)), (2, 2)),
                        Op("add", ((2, 3), (2, 2)), (2, 3)),
                        Op("relu", ((2, 3),), (2, 3))))),
        CaseEntry("A4 int8 全链", "A 结构负例", "L5 dtype",
                   "融合算子只定义了 fp32，int8 数值语义未定义", lambda: FusionCandidate(
                       "A4 int8",
                       (Op("matmul", ((2, 3), (3, 2)), (2, 2), dtype="int8"),
                        Op("add", ((2, 2), (2, 2)), (2, 2), dtype="int8"),
                        Op("relu", ((2, 2),), (2, 2), dtype="int8")))),
        CaseEntry("A5 偷走中间", "A 结构负例", "L4 使用者",
                   "E 有组外使用者却想删——偷走别人的输入", lambda: FusionCandidate(
                       "A5 偷走 E", chain_ops(M0, K0, N0),
                       intermediates=(Intermediate("C", 4, 1, 0),
                                      Intermediate("E", 4, 1, 1, kept=False)))),
        CaseEntry("A6 无使用者", "A 结构负例", "L4 死代码",
                   "没人消费的中间是 DCE 的事，不是融合候选", lambda: FusionCandidate(
                       "A6 无使用者", chain_ops(M0, K0, N0),
                       intermediates=(Intermediate("C", 4, 0, 0),))),
        CaseEntry("A7 组内循环依赖", "A 结构负例", "L6 拓扑序（新）",
                   "F 由算子2(relu) 生产却被算子0(matmul) 消费——组内成环",
                   lambda: FusionCandidate(
                       "A7 循环依赖", chain_ops(M0, K0, N0),
                       intermediates=(Intermediate("C", 4, 1, 0,
                                                   producer=0, consumers=(1,)),
                                      Intermediate("E", 4, 1, 0,
                                                   producer=1, consumers=(2,)),
                                      Intermediate("F", 4, 1, 0,
                                                   producer=2, consumers=(0,))))),
        CaseEntry("A8 边形状不匹配", "A 结构负例", "L3b 边形状（新）",
                   "MatMul 输出 (2,4) 直接喂 (4,2) 的 add——边上有隐式 Reshape",
                   lambda: FusionCandidate(
                       "A8 隐式 Reshape",
                       (Op("matmul", ((2, 3), (3, 4)), (2, 4)),
                        Op("add", ((4, 2), (4, 2)), (4, 2))))),
    ]


# ---- 翼 B：负收益案例（4 类 ＋ 4 个对照）----

def wing_b_cases() -> list[CaseEntry]:
    M1, K1s, N1 = 2048, 64, 2048          # 放大版贯穿链
    return [
        CaseEntry("R1 多使用者", "B 负收益", "R1 多使用者",
                  "G 有 1 个组外使用者：写趟被钉死，ΔB 从 16 MiB 塌缩到 8 MiB，"
                  "净收益 +6 MiB 翻成 −2 MiB",
                  lambda: cand_mm_mm(M1, K1s, 1024, N1, (128, 128), out_users=1,
                                    name="R1 MM→MM K1=1024 +1 组外"),
                  "gate", expect_gate="refuse"),
        CaseEntry("R1 对照（无组外）", "B 负收益", "R1 多使用者",
                  "同一张图、没有组外使用者：ΔB 16 MiB，净收益 +6 MiB——"
                  "auto 放行（翻转点）",
                  lambda: cand_mm_mm(M1, K1s, 1024, N1, (128, 128), out_users=0,
                                     name="R1ctl MM→MM K1=1024"),
                  "gate", expect_gate="refuse"),
        CaseEntry("R2 资源超限", "B 负收益", "R2 资源超限",
                  "tile=2048 不分块：活集 17,301,504 B 顶爆 256 KiB，"
                  "spill 两趟税 34 MiB 吞掉 ΔB 1 MiB 还倒亏 31.5 MiB",
                  lambda: cand_mm_mm(M1, K1s, 64, N1, (2048, 2048),
                                     name="R2 MM→MM K1=64 tile2048"),
                  "gate", expect_gate="refuse"),
        CaseEntry("R2 对照（tile 64）", "B 负收益", "R2 资源超限",
                  "同一张图缩到 tile=64：活集 32,768 B 全驻寄存器，"
                  "并发 4，净收益 +1 MiB——图没问题，是 tile 的锅",
                  lambda: cand_mm_mm(M1, K1s, 64, N1, (64, 64),
                                     name="R2ctl MM→MM K1=64 tile64"),
                  "gate", expect_gate="fuse", expect_lib="fuse"),
        CaseEntry("R3 keep 形式", "B 负收益", "R3 重复计算",
                  "瘦矩阵 K=4096：keep 形式合法又划算（省 C 的组内读 16 KiB，"
                  "epilogue 开销 0.05%）——对照组",
                  lambda: cand_skinny(64, 4096, 64, out_users=2,
                                      name="R3keep skinny(64,4096)"),
                  "gate", expect_gate="fuse", expect_lib="fuse"),
        CaseEntry("R3 重算形式", "B 负收益", "R3 重复计算",
                  "删 C 靠重算喂 2 个组外使用者：消除 64 KiB，"
                  "生产者输入重读 4 MiB——净亏 3.94 MiB",
                  lambda: cand_skinny(64, 4096, 64, out_users=2,
                                      name="R3recompute skinny(64,4096)"),
                  "recompute", expect_gate="refuse"),
        CaseEntry("R4 并行度下降", "B 负收益", "R4 并行度",
                  "P3 tile=128：D74 门放行（净收益 64 MiB、零 spill），"
                  "但占用 65,792 B 超过寄存器堆——并发 1 < 3",
                  lambda: cand_full(M1, K1s, N1, tile=(128, 128),
                                    name="R4 P3 tile128"),
                  "comfort", expect_gate="fuse", expect_lib="refuse"),
        CaseEntry("R4 对照（tile 64）", "B 负收益", "R4 并行度",
                  "同一张图缩到 tile=64：并发 3、净收益不变 64 MiB——"
                  "拒绝坏 tile 一分钱不花（ΔB 与 tile 无关）",
                  lambda: cand_full(M1, K1s, N1, tile=(64, 64),
                                    name="R4ctl P3 tile64"),
                  "comfort", expect_gate="fuse", expect_lib="fuse"),
    ]


DECISION_LOG: list[str] = []


def run_case(e: CaseEntry, m: Machine) -> dict:
    """把一个案例过一遍门＋D75 判据，记一行决策日志，返回全部细节。"""
    c = e.build()
    leg = can_fuse(c)
    prof = should_fuse(c, m) if leg.ok else None
    prof_r = price_recompute(c, m) if (leg.ok and e.kind == "recompute") else None
    the_prof = prof_r if prof_r is not None else prof
    dec_cons = decide(leg, the_prof, "conservative")
    dec_auto = decide(leg, the_prof, "auto")

    # 案例库判决（C6：分层判据——结构负例看合法性；R1/R2 用 D74 的门；
    # R3 用重算流量账；R4 用 D73 舒适区阈值）
    if not leg.ok:
        lib_action, lib_reason = "refuse", "合法性：" + leg.reasons[0]
    elif e.kind == "recompute" and the_prof is not None and the_prof.known:
        if the_prof.net_gain > 0:
            lib_action, lib_reason = "fuse", (
                f"重算账：净收益 {the_prof.net_gain:,} B > 0")
        else:
            lib_action, lib_reason = "refuse", (
                f"重算账：净收益 {the_prof.net_gain:,} B ≤ 0"
                f"（消除 {the_prof.recompute_elim:,} B − 重读罚 "
                f"{the_prof.recompute_penalty:,} B）")
    elif dec_cons.action == "refuse":
        lib_action = "refuse"
        lib_reason = dec_cons.reasons[0]
    elif e.kind == "comfort" and not comfort_ok(prof):
        lib_action = "refuse"
        lib_reason = (f"并行度：并发 {prof.concurrent_tiles} < 3（D73 舒适区；"
                      f"占用 {prof.reg_demand:,} B，零 spill 但延迟隐藏差）")
    else:
        lib_action = "fuse"
        lib_reason = dec_cons.reasons[0] if dec_cons.reasons else "合法且账面为正"

    db = f"{the_prof.delta_b:,}" if (the_prof and the_prof.known) else "—"
    st = f"{the_prof.spill_traffic:,}" if (the_prof and the_prof.known) else "—"
    net = f"{the_prof.net_gain:,}" if (the_prof and the_prof.known) else "—"
    conc = str(the_prof.concurrent_tiles) if (the_prof and the_prof.known) else "—"
    DECISION_LOG.append(
        f"{c.name:<30s} {e.cat:<12s} {leg.ok!s:<5s} {db:>11s} {st:>11s} "
        f"{net:>11s} {conc:>3s} {dec_cons.action:<6s} {dec_auto.action:<6s} "
        f"{lib_action:<6s} {lib_reason[:64]}")
    return {"entry": e, "cand": c, "leg": leg, "prof": prof,
            "prof_recompute": prof_r, "dec_cons": dec_cons, "dec_auto": dec_auto,
            "lib_action": lib_action, "lib_reason": lib_reason}


# ================================================================
# 主实验
# ================================================================

def main() -> None:
    m = Machine()
    print("== 1. 接口卡与 D75 扩展（案例库的判据分层）==")
    print(f"  门（D74 原样）：can_fuse{inspect.signature(can_fuse)}"
          f" / should_fuse{inspect.signature(should_fuse)}"
          f" / decide{inspect.signature(decide)}")
    print("  扩展① can_fuse 补 L3b（边形状）/ L6（组内拓扑序）；d74_can_fuse 留作对照")
    print("  扩展② price_recompute：D72 流量公式在「删除＋重算」形式下的推广")
    print("  扩展③ comfort_ok：D73 检查 4f 的舒适区（零 spill＋staging ok＋并发≥3）")
    for a in ASSUMPTIONS:
        print(f"  {a}")
    leg_params = set(inspect.signature(can_fuse).parameters)
    prof_params = set(inspect.signature(should_fuse).parameters)
    check("1a 门接口与 D74 一致：can_fuse 不吃 Machine，should_fuse 吃",
          "m" not in leg_params and "machine" not in leg_params and "m" in prof_params)
    check("1b 假设清单 C1–C8 共 8 项，覆盖四类负收益与三条扩展",
          len(ASSUMPTIONS) == 8
          and any("重算" in a for a in ASSUMPTIONS)
          and any("舒适区" in a for a in ASSUMPTIONS)
          and any("L3b" in a for a in ASSUMPTIONS))
    wing_a, wing_b = wing_a_cases(), wing_b_cases()
    check("1c 案例库 16 例：翼 A 结构负例 8 ＋ 翼 B 负收益 8（4 类＋4 对照）",
          len(wing_a) == 8 and len(wing_b) == 8
          and len({e.name for e in wing_a + wing_b}) == 16)

    # ---- 2. 翼 A：结构负例 ----
    print("\n== 2. 翼 A：结构负例 8 例（D74 六类 ＋ D75 新规则两类）==")
    print("  案例                can_fuse  首条理由")
    a_res, res = {}, {}
    for e in wing_a:
        out = run_case(e, m)
        res[e.name] = out
        leg = out["leg"]
        a_res[e.name] = leg
        first = leg.reasons[0] if leg.reasons else ""
        print(f"  {e.name:<18s}  {leg.ok!s:<7s}  {first[:66]}")
    check("2a 八个结构负例全部被拦", all(not r.ok for r in a_res.values()))
    check("2b 理由可定位到规则号：A1→L1、A2→L2、A3→L3、A4→L5、A5/A6→L4、"
          "A7→L6、A8→L3b",
          a_res["A1 模式不支持"].reasons[0].startswith("L1")
          and a_res["A2 副作用算子"].reasons[0].startswith("L2")
          and a_res["A3 逐元素 Shape 不齐"].reasons[0].startswith("L3")
          and a_res["A4 int8 全链"].reasons[0].startswith("L5")
          and a_res["A5 偷走中间"].reasons[0].startswith("L4")
          and a_res["A7 组内循环依赖"].reasons[0].startswith("L6")
          and a_res["A8 边形状不匹配"].reasons[0].startswith("L3b"))
    print("  —— 两个新负例在 D74 规则集下会漏过（d74_can_fuse 回归对照）——")
    for nm in ("A7 组内循环依赖", "A8 边形状不匹配"):
        e = next(x for x in wing_a if x.name == nm)
        old = d74_can_fuse(e.build())
        print(f"  {nm:<18s}  D74 门 → {old.ok}（漏网）  D75 门 → "
              f"{a_res[nm].ok!s}（拦下）")
    check("2c 两条新规则各拦住一个 D74 漏网案例（循环依赖、隐式 Reshape）",
          d74_can_fuse(next(e for e in wing_a
                            if e.name == "A7 组内循环依赖").build()).ok
          and d74_can_fuse(next(e for e in wing_a
                                if e.name == "A8 边形状不匹配").build()).ok
          and not a_res["A7 组内循环依赖"].ok
          and not a_res["A8 边形状不匹配"].ok)
    old_friends = [cand_full(2, 3, 2), cand_full(2048, 64, 2048, tile=(128, 128)),
                   cand_mm_mm(2048, 64, 1024, 2048, (128, 128)),
                   cand_skinny(64, 4096, 64)]
    check("2d 新规则不误伤：P3 贯穿链 / 放大版 / MM→MM / skinny 全部仍合法",
          all(can_fuse(c).ok for c in old_friends))

    # ---- 3. 翼 B-1：R1 多使用者 ----
    print("\n== 3. 翼 B-1 多使用者：R1 —— 一个组外使用者把 +6 MiB 翻成 −2 MiB ==")
    print("   案例                        ΔB        spill流量   净收益     "
          "并发  cons    auto")
    r1 = next(e for e in wing_b if e.name == "R1 多使用者")
    r1c = next(e for e in wing_b if e.name == "R1 对照（无组外）")
    for e in (r1, r1c):
        out = run_case(e, m)
        res[e.name] = out
        p = out["prof"]
        print(f"  {out['cand'].name:<28s} {kib(p.delta_b):>8s} "
              f"{kib(p.spill_traffic):>10s} {p.net_gain:>10,} B "
              f"{p.concurrent_tiles:>4d}  {out['dec_cons'].action:<6s}"
              f"  {out['dec_auto'].action}")
    p1, p1c = res["R1 多使用者"]["prof"], res["R1 对照（无组外）"]["prof"]
    check("3a R1 图结构合法（keep 形式：组外使用者有人喂）",
          res["R1 多使用者"]["leg"].ok)
    check("3b 多使用者把 ΔB 砍半：16,777,216 → 8,388,608 B"
          "（写趟被组外使用者钉死，只剩组内读一趟）",
          p1c.delta_b == 16_777_216 and p1.delta_b == 8_388_608)
    check("3c 资源账分文未动：spill 流量同为 10,485,760 B——"
          "负收益全部来自 ΔB 塌缩",
          p1c.spill_traffic == p1.spill_traffic == 10_485_760)
    check("3d 净收益翻转：+6,291,456 → −2,097,152 B；cons 与 auto 一致拒绝",
          p1c.net_gain == 6_291_456 and p1.net_gain == -2_097_152
          and res["R1 多使用者"]["dec_cons"].action == "refuse"
          and res["R1 多使用者"]["dec_auto"].action == "refuse")
    check("3e 不变量：net(对照) − net(R1) = |G|×4 = 8,388,608 B"
          "（被钉回来的正是 G 的写趟）",
          p1c.net_gain - p1.net_gain == 2048 * 1024 * 4 == p1c.delta_b - p1.delta_b)

    # ---- 4. 翼 B-2：R2 资源超限 ----
    print("\n== 4. 翼 B-2 资源超限：R2 —— 不分块的活集顶爆 256 KiB ==")
    print("   案例                        活集          spill     净收益"
          "        并发  cons    auto")
    r2 = next(e for e in wing_b if e.name == "R2 资源超限")
    r2c = next(e for e in wing_b if e.name == "R2 对照（tile 64）")
    for e in (r2, r2c):
        out = run_case(e, m)
        res[e.name] = out
        p = out["prof"]
        print(f"  {out['cand'].name:<28s} {p.live_bytes:>12,} B "
              f"{p.spill_bytes:>10,} B {p.net_gain:>11,} B {p.concurrent_tiles:>4d}"
              f"  {out['dec_cons'].action:<6s}  {out['dec_auto'].action}")
    p2, p2c = res["R2 资源超限"]["prof"], res["R2 对照（tile 64）"]["prof"]
    check("4a R2 图结构合法（实验模式 experimental.matmul_matmul）",
          res["R2 资源超限"]["leg"].ok)
    check("4b 不分块：活集 17,301,504 B，spill 17,039,360 B，"
          "净收益 −33,030,144 B（−31.5 MiB）——cons 与 auto 一致拒绝",
          p2.live_bytes == 17_301_504 and p2.spill_bytes == 17_039_360
          and p2.net_gain == -33_030_144
          and res["R2 资源超限"]["dec_cons"].action == "refuse"
          and res["R2 资源超限"]["dec_auto"].action == "refuse")
    check("4c 同一张图缩 tile=64：活集 32,768 B、零 spill、并发 4、"
          "净收益 +1,048,576 B——cons 放行（图没问题，是 tile 的锅）",
          p2c.live_bytes == 32_768 and p2c.spill_bytes == 0
          and p2c.concurrent_tiles == 4 and p2c.net_gain == 1_048_576
          and res["R2 对照（tile 64）"]["dec_cons"].action == "fuse")
    check("4d 拒绝理由来自收益层（前缀「保守策略」），合法性报告干净",
          res["R2 资源超限"]["dec_cons"].reasons[0].startswith("保守策略")
          and not res["R2 资源超限"]["leg"].reasons)

    # ---- 5. 翼 B-3：R3 重复计算 ----
    print("\n== 5. 翼 B-3 重复计算：R3 —— 瘦矩阵上「删除＋重算」必亏 ==")
    r3k = next(e for e in wing_b if e.name == "R3 keep 形式")
    r3r = next(e for e in wing_b if e.name == "R3 重算形式")
    out_k = run_case(r3k, m)
    out_r = run_case(r3r, m)
    res["R3 keep 形式"], res["R3 重算形式"] = out_k, out_r
    pk, pr = out_k["prof"], out_r["prof_recompute"]
    print(f"  {out_k['cand'].name:<28s} keep 形式：ΔB {pk.delta_b:,} B，"
          f"净收益 {pk.net_gain:,} B，epilogue 开销 {pk.instr_overhead:.2%} → "
          f"{out_k['dec_cons'].action}")
    print(f"  {out_r['cand'].name:<28s} 重算形式：消除 {pr.recompute_elim:,} B "
          f"− 重读罚 {pr.recompute_penalty:,} B = 净收益 {pr.net_gain:,} B"
          f"（{pr.recompute_penalty // pr.recompute_elim}:1）→ "
          f"{out_r['lib_action']}")
    check("5a 图结构合法：keep 与重算都不破坏语义（C 有人喂 / 每个使用者重算一份）",
          out_k["leg"].ok and out_r["leg"].ok)
    check("5b keep 账本：ΔB = 1×|C|×4 = 16,384 B（只省组内读一趟），"
          "零 spill → 门放行；epilogue 开销 2/4096 ≈ 0.05%",
          pk.delta_b == 16_384 and pk.spill_bytes == 0
          and out_k["dec_cons"].action == "fuse"
          and abs(pk.instr_overhead - 2 / 4096) < 1e-12)
    check("5c 重算账本：消除 (1+1+2)×16,384 = 65,536 B，"
          "重读罚 2×(64×4096+4096×64)×4 = 4,194,304 B",
          pr.recompute_elim == 65_536 and pr.recompute_penalty == 4_194_304)
    check("5d 重算净收益 −4,128,768 B（约 −3.94 MiB）→ 案例库拒绝；"
          "同一张图 keep 形式净收益 +16,384 B → 放行",
          pr.net_gain == -4_128_768 and out_r["lib_action"] == "refuse"
          and out_k["lib_action"] == "fuse")
    check("5e 判据可读：重读罚 / 消除 = 64:1（K=4096 的瘦矩阵：输入远大于输出，"
          "每重算一遍就把 2 MiB 输入重读一遍）",
          pr.recompute_penalty // pr.recompute_elim == 64
          and (64 * 4096 + 4096 * 64) * 4 == 2_097_152)

    # ---- 6. 翼 B-4：R4 并行度下降 ----
    print("\n== 6. 翼 B-4 并行度下降：R4 —— 占用超寄存器堆，并发 1 < 3（软代价）==")
    print("   案例                  占用        并发   净收益        D74 门"
          "     案例库")
    r4 = next(e for e in wing_b if e.name == "R4 并行度下降")
    r4c = next(e for e in wing_b if e.name == "R4 对照（tile 64）")
    for e in (r4, r4c):
        out = run_case(e, m)
        res[e.name] = out
        p = out["prof"]
        print(f"  {out['cand'].name:<22s} {p.reg_demand:>10,} B {p.concurrent_tiles:>4d}"
              f"   {p.net_gain:>10,} B  {out['dec_cons'].action:<8s}"
              f"  {out['lib_action']}")
    p4, p4c = res["R4 并行度下降"]["prof"], res["R4 对照（tile 64）"]["prof"]
    check("6a R4 图结构合法、零 spill、净收益 +67,108,864 B——D74 门（cons）放行",
          res["R4 并行度下降"]["leg"].ok and p4.spill_bytes == 0
          and p4.net_gain == 67_108_864
          and res["R4 并行度下降"]["dec_cons"].action == "fuse")
    check("6b 但占用 65,792 B > 寄存器堆 65,536 B → 并发 1 < 3："
          "案例库按 D73 舒适区拒绝",
          p4.reg_demand == 65_792 and p4.concurrent_tiles == 1
          and res["R4 并行度下降"]["lib_action"] == "refuse")
    # 未融合基线：单独的 MatMul tile=64 → 并发 4
    base = FusionCandidate("基线 MatMul tile64",
                           (Op("matmul", ((2048, 64), (64, 2048)), (2048, 2048)),),
                           workload=(2048, 64, 2048), tile=(64, 64))
    pb = should_fuse(base, m)
    print(f"  未融合基线（MatMul tile=64）：占用 {pb.reg_demand:,} B → "
          f"并发 {pb.concurrent_tiles}")
    check("6c 融合的并行度税如实报告：tile=64 时融合占用 16,640 B 并发 3，"
          "未融合 MatMul 占用 16,384 B 并发 4（−25%，账本未计价的软代价）",
          p4c.reg_demand == 16_640 and p4c.concurrent_tiles == 3
          and pb.reg_demand == 16_384 and pb.concurrent_tiles == 4)
    check("6d 对照 tile=64：并发 3 ≥ 3 且净收益不变 67,108,864 B——"
          "拒绝坏 tile 一分钱不花",
          p4c.concurrent_tiles == 3 and p4c.net_gain == p4.net_gain
          and res["R4 对照（tile 64）"]["lib_action"] == "fuse")
    check("6e ΔB 与 tile 无关（消除的是中间不是输入分块）：128 与 64 两行相等",
          p4.delta_b == p4c.delta_b == 67_108_864)

    # ---- 7. 决策日志 ----
    print("\n== 7. 决策日志（16 行：案例 / 类别 / 合法 / ΔB / spill / 净收益 / "
          "并发 / cons / auto / 库 / 理由）==")
    for line in DECISION_LOG:
        print(f"  {line}")
    check("7a 日志 16 行、顺序完整：翼 A 8 行＋翼 B 8 行，无空行",
          len(DECISION_LOG) == 16
          and DECISION_LOG[0].startswith("A1") and DECISION_LOG[7].startswith("A8")
          and DECISION_LOG[8].startswith("R1 MM→MM")
          and DECISION_LOG[15].startswith("R4ctl")
          and all(len(l.strip()) > 0 for l in DECISION_LOG))
    refuse_rows = [l for l in DECISION_LOG if " refuse " in f" {l} "]
    check("7b 库判决为 refuse 的行，理由归属可机检：结构负例以「合法性：L…」开头，"
          "R1/R2 以「保守策略」或「重算账」开头，R4 以「并行度」开头",
          any("合法性：L6" in l for l in refuse_rows)
          and any("保守策略" in l for l in refuse_rows)
          and any("重算账" in l for l in refuse_rows)
          and any("并行度" in l for l in refuse_rows))
    wing_b_refuse = [e for e in wing_b if res.get(e.name, {}).get("lib_action") == "refuse"]
    check("7c 四类负收益各至少一个「图合法但库拒绝」：R1/R2/R3重算/R4",
          {res["R1 多使用者"]["entry"].cat, res["R2 资源超限"]["entry"].cat,
           res["R3 重算形式"]["entry"].cat, res["R4 并行度下降"]["entry"].cat}
          == {"R1 多使用者", "R2 资源超限", "R3 重复计算", "R4 并行度"}
          and all(res[n]["leg"].ok for n in
                  ("R1 多使用者", "R2 资源超限", "R3 重算形式", "R4 并行度下降")))
    check("7d 门与库在 R4 上分歧且如实记录：D74 门 fuse、案例库 refuse——"
          "分歧原因是账本没给并行度计价（D76 的输入）",
          res["R4 并行度下降"]["dec_cons"].action == "fuse"
          and res["R4 并行度下降"]["lib_action"] == "refuse")

    print(f"\n== 结果：{PASSED}/{CHECKS} 项检查通过 ==")


if __name__ == "__main__":
    main()
