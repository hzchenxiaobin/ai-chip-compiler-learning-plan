#!/usr/bin/env python3
"""fusion_gate_lab.py —— 第 74 天主实验：合法性与收益性分离。

问题：昨天（第 73 天）的结尾留了一个反例——MatMul→MatMul 融合「合法」
（Pattern 匹配得上、数值上也能做），但 K1=4096 时收益兑现率只剩 9.4%。
可第 50/52 天的融合 RewritePattern 是「匹配上就替换」：Pattern 只回答
「能否融合」，从不回答「值得融合吗」。而且 Pattern 手里也没有机器卡、
Shape 和 tile——收益判断需要的信息它拿不到。

今天把门拆成两个函数 + 一个策略：
  can_fuse(candidate)          → LegalityReport   能否融合：只读图结构/语义
                                                      （模式、纯度、Shape、dtype、
                                                      D52 的使用者与保留规则）
  should_fuse(candidate, m)     → ProfitReport     值不值得：D72 的 ΔB 公式
                                                      ＋ D73 的资源账（Machine 卡）
  decide(leg, prof, policy)     → Decision          策略：conservative（默认）/
                                                      auto / force

接口边界（今天的核心产出，用 inspect 真正检查签名）：
  - can_fuse 不读机器、不算字节——「能否」与机器无关；
  - should_fuse 不重查结构——假设合法性已由上一层把过；
  - decide 只读两份报告——策略可整体替换（D76 的 Cost Model 只换第三层）。

运行：python3 fusion_gate_lab.py
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field

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
# 1. 机器假设卡（与第 73 天完全一致）＋ 假设清单 B1–B8
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
    "B1 机器假设卡沿用第 73 天（64 KiB 寄存器堆 / 192 KiB SRAM / 64 通道 / "
    "fp32），可整体替换重算；合法性判断不读这张卡",
    "B2 ΔB 沿用第 72 天多使用者规则：组外使用者 = 0 时省 (1＋组内数) 趟；"
    "组外 > 0 时写与组外读保留，只省组内读",
    "B3 资源账沿用第 73 天：活集先填寄存器堆、超出的降级 SRAM、再超出 spill "
    "两趟（下界口径）；spill 成本按 2×溢出字节的下界计，真实更高",
    "B4 策略语义：conservative 拒绝 spill > 0 或收益未知的候选（拒绝 = 回到"
    "已知正确的基线）；auto 只看净收益 > 0；force 只看合法性（A/B 实验用）",
    "B5 epilogue 指令增量 2/K 只报告不设门（软代价）；(add,relu) 与 "
    "MatMul→MatMul 的指令增量今天不建模",
    "B6 动态维度（-1）的候选：合法性可以通过，但活集/ΔB 无法估算 → 收益未知 "
    "→ 非 force 策略一律拒绝（D62 的静态特化是后续入口）",
    "B7 候选枚举沿用第 52 天：组外有使用者时，拒绝 / 保留中间（keep）两种合法"
    "形式，删除中间（不给组外使用者留值）非法；「不融合」是恒可用的基线，"
    "净收益记 0",
    "B8 沿用第 73 天 A10：MatMul→MatMul 按行块调度模型计（spill 按行块数缩放、"
    "输入分块不建模）；MatMul+Bias(+Relu) 按单实例 kernel 计（tile 是实例形状）；"
    "不计 launch、编译时间与多核竞争",
]


# ================================================================
# 2. 候选的图结构描述（合法性只看这一层）
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
    """组内生产的中间 Tensor 的使用者关系（D52 的口径）。

    in_group_users  组内消费者数（这些读在融合后消失）
    out_group_users 组外消费者数（这些读必须保留）
    kept            组外 > 0 时是否保留落盘（keep 策略）；False 且组外 > 0 → 非法
    elems           元素数；未知（动态）填 -1
    """

    name: str
    elems: int
    in_group_users: int
    out_group_users: int
    kept: bool = False


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
    ("matmul", "matmul"): "experimental.matmul_matmul",   # D73 反例结构，今天进门当候选
}
SUPPORTED_DTYPES = {"fp32"}


# ================================================================
# 3. 第一层：合法性 Pattern —— 只读结构/语义，不读机器、不算字节
# ================================================================

@dataclass
class LegalityReport:
    ok: bool
    reasons: list[str] = field(default_factory=list)
    pattern_name: str = ""
    kept_outputs: list[str] = field(default_factory=list)
    dynamic: bool = False     # 有未知维度：合法性不拦（L3 按 -1 通配），交给收益层


def _dims_compatible(a: tuple[int, ...], b: tuple[int, ...]) -> bool:
    """静态维度必须一致；-1（未知）通配——合法性与『能否确定』分开（D61）。"""
    if len(a) != len(b):
        return False
    return all(x == y or x < 0 or y < 0 for x, y in zip(a, b))


def can_fuse(c: FusionCandidate) -> LegalityReport:
    """能否融合：结构/语义问题，与机器无关、与收益无关。

    检查项（沿用到第 75 天的负例来源）：
      L1 算子链是否在支持的模式里（D50/D37 的融合算子定义）
      L2 组内算子是否纯（无副作用；D25 的口径）
      L3 逐算子 Shape/dtype 规则（D39/D40 Verifier 的子集；未知维度按 -1 通配）
      L4 中间 Tensor 的使用者规则（D52：组外使用者必须有人喂，keep 才合法）
    """
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
    for it in c.intermediates:                             # L4
        if it.out_group_users > 0 and not it.kept:
            reasons.append(f"L4 中间 {it.name} 有 {it.out_group_users} 个组外使用者"
                           "且未保留落盘（D52：删除中间 = 偷走别人的输入）")
        if it.in_group_users == 0 and it.out_group_users == 0:
            reasons.append(f"L4 中间 {it.name} 没有任何使用者（DCE 的事，不该当融合候选）")

    dynamic = any(d < 0 for op in c.ops for s in (op.out_shape, *op.in_shapes)
                  for d in s)
    kept = [it.name for it in c.intermediates if it.kept]
    return LegalityReport(ok=not reasons, reasons=reasons,
                          pattern_name=pattern_name, kept_outputs=kept,
                          dynamic=dynamic)


# ================================================================
# 4. 第二层：收益性分析 —— D72 的 ΔB ＋ D73 的资源账（接口边界：不重查结构）
# ================================================================

@dataclass
class ProfitReport:
    known: bool = True
    delta_b: int = 0                # D72 口径：被消除中间的省流量
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
    reasons: list[str] = field(default_factory=list)


def _d72_passes(it: Intermediate) -> int:
    """D72 多使用者规则：组外无人 → 写＋组内读全消失；组外有人 → 只省组内读。"""
    return (1 + it.in_group_users) if it.out_group_users == 0 else it.in_group_users


def should_fuse(c: FusionCandidate, m: Machine) -> ProfitReport:
    """是否值得融合：账本问题。输入 = 候选的资源上下文 + 机器假设卡。

    接口契约：不重查结构（合法性由 can_fuse 负责）；动态维度算不出账 →
    known=False 交给策略层保守拒绝。
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

    # ---- ΔB（D72 公式）----
    r.delta_b = sum(_d72_passes(it) * it.elems * m.itemsize for it in c.intermediates)

    # ---- 资源账（D73 公式，按模式推导活集）----
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
                             else min(reg_cap, sram_cap))     # D73 错误一的教训：下限 1

    # ---- spill 流量缩放（B8：MM→MM 按行块，其余单实例）----
    scale = (M // tm) if kinds == ("matmul", "matmul") else 1
    r.spill_traffic = 2 * r.spill_bytes * scale

    r.net_gain = r.delta_b - r.spill_traffic
    r.redeem_rate = (r.net_gain / r.delta_b) if r.delta_b > 0 else None
    if kinds in (("matmul", "add"), ("matmul", "add", "relu")) and K > 0:
        r.instr_overhead = 2 / K                             # D73 §6：epilogue 增量
    return r


# ================================================================
# 5. 第三层：策略 —— 只读两份报告，默认保守
# ================================================================

@dataclass
class Decision:
    action: str                     # "fuse" | "refuse"
    policy: str
    reasons: list[str] = field(default_factory=list)
    hint: str = ""


def decide(leg: LegalityReport, prof: ProfitReport | None,
           policy: str = "conservative") -> Decision:
    """决策 = 合法性 ∧ 策略(收益)。报告是唯一输入——换策略不动前两层。"""
    if not leg.ok:
        return Decision("refuse", policy, ["合法性：" + r for r in leg.reasons],
                        "先修结构/语义，再谈收益（D75 的负例来源）")
    if policy == "force":
        return Decision("fuse", policy, ["合法性通过；force 模式只看合法性（A/B 实验用）"])
    if prof is None or not prof.known:
        if leg.dynamic:
            why = "收益未知：动态维度算不出活集与 ΔB"
        else:
            why = "收益未知"
        hint = "D62：特化成静态 Shape 后重新进门"
        return Decision("refuse", policy, [why], hint)

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


DECISION_LOG: list[str] = []


def run_gate(c: FusionCandidate, m: Machine, policy: str = "conservative"
             ) -> tuple[LegalityReport, ProfitReport | None, Decision]:
    """把候选过一遍三层门，并记一行决策日志（D75 的案例来源）。"""
    leg = can_fuse(c)
    prof = should_fuse(c, m) if leg.ok else None
    dec = decide(leg, prof, policy)
    net = (f"{prof.net_gain:,}" if (prof and prof.known)
           else ("?" if leg.ok else "—"))
    DECISION_LOG.append(
        f"{c.name:<24s} {policy:<13s} {leg.ok!s:<5s} {net:>12s} "
        f"{dec.action:<6s} {dec.reasons[0] if dec.reasons else ''}"
        + (f" ｜ {dec.hint}" if dec.hint else ""))
    return leg, prof, dec


# ================================================================
# 候选构造（贯穿示例与 D72/D73 的场景）
# ================================================================

def chain_ops(M: int, K: int, N: int) -> tuple[Op, ...]:
    """贯穿链 MatMul(M,K)@B(K,N) → +D → relu 的算子序列（D39/D40 规则全过）。"""
    return (Op("matmul", ((M, K), (K, N)), (M, N)),
            Op("add", ((M, N), (M, N)), (M, N)),
            Op("relu", ((M, N),), (M, N)))


def cand_full(M: int, K: int, N: int, name: str = "P3 全融合",
              tile: tuple[int, int] | None = None) -> FusionCandidate:
    """候选：{MatMul, Add, Relu} 一组，C、E 组内消化（D50 的 fused_matmul_bias_relu）。"""
    elems = M * N
    return FusionCandidate(name, chain_ops(M, K, N),
                           intermediates=(Intermediate("C", elems, 1, 0),
                                          Intermediate("E", elems, 1, 0)),
                           workload=(M, K, N), tile=tile)


def cand_p2(M: int, K: int, N: int) -> FusionCandidate:
    """候选 P2：{MatMul, Add} 融合，E 保留落盘喂 relu（D52 的 keep 形式）。"""
    return FusionCandidate("P2 FusedMatMulBias",
                           chain_ops(M, K, N)[:2],
                           intermediates=(Intermediate("C", M * N, 1, 0),
                                          Intermediate("E", M * N, 0, 1, kept=True)),
                           workload=(M, K, N))


def cand_p1(M: int, K: int, N: int) -> FusionCandidate:
    """候选 P1：{Add, Relu} 融合。C 由组外的 MatMul 生产——不算组内中间。"""
    return FusionCandidate("P1 FusedAddReLU",
                           chain_ops(M, K, N)[1:],
                           intermediates=(Intermediate("E", M * N, 1, 0),),
                           workload=(M, K, N))


def cand_mm_mm(M: int, K: int, Kmid: int, N: int, tile: tuple[int, int]
              ) -> FusionCandidate:
    """候选：MatMul(M,K)→G(M,Kmid)→MatMul(Kmid,N)（D73 §5 的反例结构）。"""
    ops = (Op("matmul", ((M, K), (K, Kmid)), (M, Kmid)),
           Op("matmul", ((M, Kmid), (Kmid, N)), (M, N)))
    return FusionCandidate(f"MM→MM K1={Kmid}", ops,
                           intermediates=(Intermediate("G", M * Kmid, 1, 0),),
                           workload=(M, K, N), tile=tile)


# ================================================================
# 主实验
# ================================================================

def main() -> None:
    m = Machine()

    # ---- 1. 接口卡 + 假设清单 ----
    print("== 1. 接口卡：两个函数 + 一个策略（今天的核心产出）==")
    print(f"  can_fuse{inspect.signature(can_fuse)}   → LegalityReport（结构/语义）")
    print(f"  should_fuse{inspect.signature(should_fuse)}  → ProfitReport（账本）")
    print(f"  decide{inspect.signature(decide)}  → Decision（策略）")
    print("  边界：can_fuse 不读机器不算字节；should_fuse 不重查结构；"
          "decide 只读报告")
    for b in ASSUMPTIONS:
        print(f"  {b}")
    leg_params = set(inspect.signature(can_fuse).parameters)
    prof_params = set(inspect.signature(should_fuse).parameters)
    dec_params = set(inspect.signature(decide).parameters)
    check("1a 接口边界落在签名上：can_fuse 不吃 Machine，should_fuse 吃",
          "m" not in leg_params and "machine" not in leg_params
          and "m" in prof_params)
    check("1b decide 只读报告不吃候选：换策略不动前两层",
          not ({"c", "candidate"} & dec_params))
    check("1c 假设清单 B1–B8 共 8 项且覆盖 ΔB/资源/策略/动态维度",
          len(ASSUMPTIONS) == 8
          and any("ΔB" in b for b in ASSUMPTIONS)
          and any("spill" in b for b in ASSUMPTIONS)
          and any("策略" in b for b in ASSUMPTIONS)
          and any("动态维度" in b for b in ASSUMPTIONS))

    # ---- 2. 合法性：结构/语义层（不看机器、不算字节）----
    print("\n== 2. 合法性 Pattern：贯穿链的合法形式与四个负例 ==")
    M0, K0, N0 = 2, 3, 2
    p1, p2, p3 = cand_p1(M0, K0, N0), cand_p2(M0, K0, N0), cand_full(M0, K0, N0)
    for c in (p1, p2, p3):
        leg = can_fuse(c)
        print(f"  {c.name:<22s} → {leg.ok}（{leg.pattern_name}，保留 {leg.kept_outputs}）")
    check("2a 贯穿链三种融合形式全部合法：P1/P2/P3",
          all(can_fuse(c).ok for c in (p1, p2, p3)))
    check("2b P2 的 E 有组外使用者（relu）且 kept=True → 合法（D52 keep）",
          can_fuse(p2).ok and can_fuse(p2).kept_outputs == ["E"])
    negs = []
    bad_chain = FusionCandidate("负例：Relu→MatMul",
                                (Op("relu", ((2, 2),), (2, 2)),
                                 Op("matmul", ((2, 2), (2, 2)), (2, 2))))
    side_effect = FusionCandidate("负例：副作用",
                                  (Op("matmul", ((2, 3), (3, 2)), (2, 2)),
                                   Op("add", ((2, 2), (2, 2)), (2, 2), pure=False),
                                   Op("relu", ((2, 2),), (2, 2))))
    shape_bad = FusionCandidate("负例：Shape 不一致",
                                (Op("matmul", ((2, 3), (3, 2)), (2, 2)),
                                 Op("add", ((2, 3), (2, 2)), (2, 3)),
                                 Op("relu", ((2, 3),), (2, 3))))
    dtype_bad = FusionCandidate("负例：int8",
                                (Op("matmul", ((2, 3), (3, 2)), (2, 2), dtype="int8"),
                                 Op("add", ((2, 2), (2, 2)), (2, 2), dtype="int8"),
                                 Op("relu", ((2, 2),), (2, 2), dtype="int8")))
    steal = FusionCandidate("负例：偷走 E",
                            chain_ops(M0, K0, N0),
                            intermediates=(Intermediate("C", 4, 1, 0),
                                           Intermediate("E", 4, 1, 1, kept=False)))
    dead = FusionCandidate("负例：无使用者",
                           chain_ops(M0, K0, N0),
                           intermediates=(Intermediate("C", 4, 0, 0),))
    for c in (bad_chain, side_effect, shape_bad, dtype_bad, steal, dead):
        leg = can_fuse(c)
        negs.append(leg.ok)
        print(f"  {c.name:<22s} → {leg.ok}（{leg.reasons[0][:46]}）")
    check("2c 六个负例全部被拦：模式/纯度/Shape/dtype/偷中间/无使用者",
          not any(negs) and len(negs) == 6)
    check("2d 负例原因可追溯到具体规则号（L1–L5）",
          all(any(r.startswith(f"L{i}") for r in can_fuse(c).reasons)
              for c, i in ((bad_chain, 1), (side_effect, 2), (shape_bad, 3),
                           (dtype_bad, 5), (steal, 4), (dead, 4))))

    # ---- 3. 收益性：贯穿示例四行账（对上 D72 的 0/32/32/64）----
    print("\n== 3. 收益判断：贯穿示例的候选账本（基线恒 0）==")
    print("  候选                ΔB      活集(reg)  落位    spill  净收益  保守门")
    best, best_net = None, 0
    for c in (p1, p2, p3):
        prof = should_fuse(c, m)
        dec = decide(can_fuse(c), prof)
        print(f"  {c.name:<20s}{prof.delta_b:>4} B  {prof.reg_demand:>6} B"
              f"  {prof.placement:>6s}  {prof.spill_bytes:>4} B"
              f"  {prof.net_gain:>5} B  {dec.action}")
        if prof.net_gain > best_net:
            best, best_net = c, prof.net_gain
    print(f"  基线（不融合）      0 B       —          —       0 B      0 B  refuse")
    print(f"  → 规划器按净收益排序选最优：{best.name}（{best_net} B）")
    profs = {c.name: should_fuse(c, m) for c in (p1, p2, p3)}
    check("3a ΔB 与 D72 逐位一致：P1=P2=32 B、P3=64 B（多使用者规则内建）",
          profs["P1 FusedAddReLU"].delta_b == 32
          and profs["P2 FusedMatMulBias"].delta_b == 32
          and profs["P3 全融合"].delta_b == 2 * 2 * (2 * 2) * 4 == 64)
    check("3b P3 的账本 = D73 的资源账：reg 272 B（累加器 16 + bias 256）、"
          "staging 48 B、零 spill",
          profs["P3 全融合"].reg_demand == 272
          and profs["P3 全融合"].sram_demand == 48
          and profs["P3 全融合"].spill_bytes == 0)
    check("3c 净收益恒等式：net = ΔB − spill 流量（三个候选都成立）",
          all(p.net_gain == p.delta_b - p.spill_traffic for p in profs.values()))
    check("3d 保守门全放行（零 spill 且 net > 0），排序选出 P3",
          all(decide(can_fuse(c), profs[c.name]).action == "fuse"
              for c in (p1, p2, p3))
          and best_net == 64 and best.name == "P3 全融合")
    check("3e epilogue 指令增量如实报告：K=3 → 66.7%（D73 §6 的口径）",
          abs(profs["P3 全融合"].instr_overhead - 2 / 3) < 1e-12)

    # ---- 4. 放大 2048²：同一候选 × 5 tile × 3 策略的决策矩阵 ----
    print("\n== 4. 决策矩阵：P3(M=N=2048, K=64) × tile × 策略（D73 的账本过门）==")
    print("  tile     活集(reg)   落位       spill   净收益(下界)  conservative"
          "     auto        force")
    M1, K1s, N1 = 2048, 64, 2048
    db1 = should_fuse(cand_full(M1, K1s, N1), m).delta_b
    print(f"  （ΔB = 16·MN = {db1:,} B = {kib(db1)}，与 K、tile 无关）")
    decisions = {}
    for t in (32, 64, 128, 256, 2048):
        c = cand_full(M1, K1s, N1, name=f"P3 tile={t}", tile=(t, t))
        leg, prof, dec = run_gate(c, m)           # conservative；顺带记决策日志
        row = [dec.action] + [decide(leg, prof, p).action
                              for p in ("auto", "force")]
        decisions[t] = (prof, row, dec)
        print(f"  {t:>4}  {prof.reg_demand:>10,} B  {prof.placement:>8s}"
              f"  {prof.spill_bytes:>10,} B  {prof.net_gain:>11,} B"
              f"  {row[0]:<13s}  {row[1]:<11s}  {row[2]}")
    check("4a conservative 只收零 spill：32/64/128 融、256/2048 拒",
          [decisions[t][1][0] for t in (32, 64, 128, 256, 2048)]
          == ["fuse"] * 3 + ["refuse"] * 2)
    check("4b tile 128×128 降级 256 B 但零 spill → conservative 融"
          "（落位 reg+sram 不设门）",
          decisions[128][0].demoted_bytes == 256
          and decisions[128][0].placement == "reg+sram"
          and decisions[128][1][0] == "fuse")
    check("4c 2048 不分块：净收益 34,078,208 B（D73 的 50.8%）仍为正，"
          "但 conservative 因为 spill 拒绝；auto 接受",
          decisions[2048][0].net_gain == 34078208
          and decisions[2048][0].redeem_rate is not None
          and abs(decisions[2048][0].redeem_rate - 0.508) < 1e-3
          and decisions[2048][1] == ["refuse", "fuse", "fuse"])
    dec2048 = decisions[2048][2]
    check("4d 拒绝理由来自收益层而不是合法性层（同一候选合法）",
          can_fuse(cand_full(M1, K1s, N1, tile=(2048, 2048))).ok
          and dec2048.action == "refuse"
          and dec2048.reasons[0].startswith("保守策略"))
    check("4e auto 全收（五档 net > 0），force 全收（只看合法）",
          all(decisions[t][1][1] == "fuse" and decisions[t][1][2] == "fuse"
              for t in decisions))
    print("  → 同一个合法候选，三个策略三种答案：保守门只问「有没有 spill」，"
          "不赌下界成本；")
    print("    2048 的拒绝不是终局——hint 会让你缩小 tile 重试，64 就能过门")

    # ---- 5. 合法 ≠ 值得：MatMul→MatMul 过门（D73 反例回到今天的主场）----
    print("\n== 5. 合法 ≠ 值得：MM→MM(2048,64)→G(2048,K1)→(K1,2048)，tile 128 ==")
    print("   K1    活集    落位      spill/行块  ΔB      净收益   兑现率"
          "   保守门    auto门")
    mm_dec = {}
    for Kmid in (64, 256, 1024, 4096):
        c = cand_mm_mm(M1, K1s, Kmid, N1, tile=(128, 128))
        leg, prof, dec = run_gate(c, m)
        dec_auto = decide(leg, prof, "auto")
        mm_dec[Kmid] = (leg, prof, dec, dec_auto)
        rate = f"{prof.redeem_rate:.1%}" if prof.redeem_rate is not None else "—"
        print(f"  {Kmid:>5}  {prof.live_bytes:>9,} B  {prof.placement:>8s}"
              f"  {prof.spill_bytes:>9,} B  {kib(prof.delta_b):>6s}"
              f"  {kib(prof.net_gain):>7s}  {rate:>7s}"
              f"  {dec.action:<8s}  {dec_auto.action}")
    check("5a 四档全部合法（实验模式）：合法性与 K1 无关——结构不随账本变",
          all(mm_dec[k][0].ok for k in mm_dec))
    check("5b K1=64/256 零 spill → 保守门放行（净收益 1/4 MiB）",
          mm_dec[64][2].action == "fuse" and mm_dec[256][2].action == "fuse"
          and mm_dec[64][1].net_gain == 1048576
          and mm_dec[256][1].net_gain == 4194304)
    check("5c K1=1024/4096 spill > 0 → 保守门拒绝，尽管净收益（下界）同为 6 MiB",
          mm_dec[1024][1].net_gain == mm_dec[4096][1].net_gain == 6291456
          and mm_dec[1024][2].action == "refuse"
          and mm_dec[4096][2].action == "refuse")
    check("5d auto 门对四档全放行（net > 0）：保守策略在 K1=4096 上"
          "「把 6 MiB 留在桌上」——保守的代价，D75/D76 再细化",
          all(mm_dec[k][3].action == "fuse" for k in mm_dec))
    check("5e K1=4096 的拒绝理由点名 spill（收益层），而合法性报告干净",
          mm_dec[4096][2].reasons[0].startswith("保守策略")
          and "spill" in mm_dec[4096][2].reasons[0]
          and not mm_dec[4096][0].reasons)

    # ---- 6. 多使用者：合法性过滤非法形式，收益性排序合法形式 ----
    print("\n== 6. 多使用者：E 还被外部 G 读（D72 §5 的 48 B 回到今天）==")
    c_keep = FusionCandidate("B: 融合但保留 E", chain_ops(M0, K0, N0),
                             intermediates=(Intermediate("C", 4, 1, 0),
                                            Intermediate("E", 4, 1, 1, kept=True)),
                             workload=(M0, K0, N0))
    c_steal = FusionCandidate("C: 融合并删除 E", chain_ops(M0, K0, N0),
                              intermediates=(Intermediate("C", 4, 1, 0),
                                             Intermediate("E", 4, 1, 1, kept=False)),
                              workload=(M0, K0, N0))
    for c in (c_keep, c_steal):
        leg, prof, dec = run_gate(c, m)
        net = f"{prof.net_gain} B" if prof and prof.known else "—"
        why = dec.reasons[0][:46] + ("…" if len(dec.reasons[0]) > 46 else "")
        print(f"  {c.name:<18s} 合法 {leg.ok!s:<5s} 净收益 {net:>6s}"
              f"  → {dec.action}（{why}）")
    print("  A: 拒绝融合（基线）  合法 True  净收益    0 B  → 基线")
    check("6a 删除 E 被合法性层拦截（L4：组外使用者没人喂）",
          not can_fuse(c_steal).ok
          and any(r.startswith("L4") for r in can_fuse(c_steal).reasons))
    check("6b 保留 E 合法且 ΔB = 48 B = C 两趟 32 + E 一趟 16（D72 §5 逐位一致）",
          can_fuse(c_keep).ok
          and should_fuse(c_keep, m).delta_b == 48)
    check("6c 收益排序：B(48) > A 基线(0) > C(非法，出局)——"
          "合法性过滤、收益性选择",
          should_fuse(c_keep, m).net_gain == 48
          and decide(can_fuse(c_keep), should_fuse(c_keep, m)).action == "fuse")

    # ---- 7. 动态维度：合法但收益未知 → 保守拒绝 ----
    print("\n== 7. 动态维度：M 未知（D61/D62 的候选今天怎么处理）==")
    dyn = FusionCandidate("动态 M 的全融合",
                          (Op("matmul", ((-1, 3), (3, 2)), (-1, 2)),
                           Op("add", ((-1, 2), (-1, 2)), (-1, 2)),
                           Op("relu", ((-1, 2),), (-1, 2))),
                          intermediates=(Intermediate("C", -1, 1, 0),
                                         Intermediate("E", -1, 1, 0)),
                          workload=(-1, 3, 2))
    leg_d = can_fuse(dyn)
    prof_d = should_fuse(dyn, m)
    for p in ("conservative", "auto", "force"):
        dec_d = decide(leg_d, prof_d, p)
        print(f"  策略 {p:<13s} → {dec_d.action}（{dec_d.reasons[0] if dec_d.reasons else ''}"
              f"{'｜' + dec_d.hint if dec_d.hint else ''}）")
    check("7a 合法性不拦动态维度：-1 按 D61 的「未知」通配 → 合法",
          leg_d.ok and leg_d.dynamic)
    check("7b 收益层如实说「不知道」：known=False（不编造保守猜测值）",
          not prof_d.known)
    check("7c 保守与 auto 都拒绝（收益未知 ≠ 收益为负）；force 放行",
          decide(leg_d, prof_d, "conservative").action == "refuse"
          and decide(leg_d, prof_d, "auto").action == "refuse"
          and decide(leg_d, prof_d, "force").action == "fuse")
    check("7d 拒绝理由带出口：D62 的静态特化是后续入口",
          "特化" in decide(leg_d, prof_d).hint)

    # ---- 8. 决策日志（今天的第二份产出：D75 负例与 D76 Cost Model 的输入）----
    print("\n== 8. 决策日志（每行一条：候选/策略/合法/净收益/动作/理由）==")
    for line in DECISION_LOG:
        print(f"  {line}")
    check("8a 日志按序记录 §4 tile 扫描(5 行)＋§5 MM→MM(4 行)＋§6 多使用者"
          "(2 行)共 11 条，无空行",
          len(DECISION_LOG) == 11
          and DECISION_LOG[0].startswith("P3 tile=32")
          and DECISION_LOG[5].startswith("MM→MM")
          and DECISION_LOG[9].startswith("B:")
          and all(len(line.strip()) > 0 for line in DECISION_LOG))
    check("8b 日志行结构完整：动作字段清楚，refuse 行都带出口 hint（｜…）",
          all((" fuse " in f" {line} " or " refuse " in f" {line} ")
              for line in DECISION_LOG)
          and all("｜" in line for line in DECISION_LOG
                  if " refuse " in f" {line} "))

    print(f"\n== 结果：{PASSED}/{CHECKS} 项检查通过 ==")


if __name__ == "__main__":
    main()
