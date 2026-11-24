#!/usr/bin/env python3
"""cost_model.py —— 第 76 天主实验：简单 Cost Model 集成（Cost Model v0.1）。

问题：到第 75 天收工时，「值不值得融合」住着四个函数——D74 的门（R1/R2）、
D75 的重算账（R3）、D75 的舒适区（R4）、外加合法性的 L 规则。理由前缀不同、
口径不同、没法排序、没法统一调参。今天把它们装进**一台报价机**：

  CostModel(machine).evaluate(candidate, mode) -> CostReport
    输入  = 融合候选（图＋Shape＋dtype＋声明形式）＋ 机器假设卡（绑进对象）＋ 模式
    输出  = 评分（itemized 明细账，每项带公式出处）
           ＋ 决策（fuse / refuse）
           ＋ 理由（合法性 / 评分 / 门槛，三类可归因）
           ＋ 融合前后的 mini-IR 对照
    模式  = force 强制融合（合法即融，评分照记——A/B 校准的测量工具）
           ＋ auto 自动决策（评分 > 0 且过三个硬门槛）

统一计价的纪律（沿用 D75 的「不编数字」）：
  - 只对「有账」的项计价：ΔB（D72）、重算罚（D75 扩展②）、spill 两趟税（D73）；
  - 未计价项只报告不编数：寄存器并发（活集口径的容量 proxy，用 D73 舒适区
    阈值当门槛）、staging（复用损失，只警告）、launch / 编译时间 / 多核竞争（C8）；
  - 决策在候选**声明的形式**上做（keep / recompute）；形式排序只输出提示
    ——换形式 = 改写候选图，是后续 Pattern 的活（E6）。

验收主线：这台报价机必须**复现第 75 天案例库的全部 16 例判决**（ground truth），
再用记账执行器对拍评分的流量项（20 组随机，逐位一致），最后用两个「只拧一个
参数」的实弹演示误差来源（换机器卡 → R4 翻转；动态 Shape → 评分未知）。

运行：python3 cost_model.py
"""

from __future__ import annotations

import inspect
import random
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
# 1. 机器假设卡（D73 同款）＋ 假设清单 E1–E8（E = 误差/估算，今天的主题）
# ================================================================

@dataclass(frozen=True)
class Machine:
    """机器假设卡：Cost Model 的唯一机器依据（第 73 天同款，可整体替换）。"""

    name: str = "toy-core v0"
    regfile_bytes: int = 64 * 1024      # 每核寄存器堆 64 KiB
    sram_bytes: int = 192 * 1024        # 每核片上 SRAM 192 KiB
    lanes: int = 64                     # 每核 64 条并行通道
    itemsize: int = 4                   # fp32

    @property
    def onchip_bytes(self) -> int:
        return self.regfile_bytes + self.sram_bytes


ASSUMPTIONS: list[str] = [
    "E1 机器假设卡沿用第 73 天（64 KiB 寄存器堆 / 192 KiB SRAM / 64 通道 / "
    "fp32），可整体替换重算；CostModel 把卡绑进对象（target 绑定），"
    "evaluate 只吃候选＋模式——这是与 D74 should_fuse(c, m) 的接口差别",
    "E2 计价内核沿用 D72/D73/D75 三本账：keep 形式 ΔB = Σ passes·elems·4"
    "（组外使用者只省组内读）；重算形式 elim = (1＋组内＋组外)·elems·4、"
    "罚 = 组外数 × 生产者输入字节；spill = 活集三级阶梯 → 两趟税（下界口径）",
    "E3 统一评分 score = 收益项 − 代价项（单位字节）。只对「有账」的项计价；"
    "并行度 / launch / 编译时间 / 多核竞争未计价（C8 沿用）——未计价项只报告，"
    "不编数字（D75 的纪律）",
    "E4 记账执行器 = D72 仪器化执行器去掉数值部分（数值语义 D50/52 已证）："
    "按 kernel 边界记 DRAM 读写；重算形式假设组外使用者把生产者含进自己的 "
    "kernel（中间在其内部也不落盘）。对拍只覆盖流量项，不覆盖 spill"
    "（容量模型只在 cost model 里——这正是「对拍证明了什么」的边界）",
    "E5 auto 硬门槛 = 评分 > 0 ∧ 零 spill ∧ 寄存器并发 ≥ 3。寄存器并发 = "
    "寄存器堆 ÷ 单 tile 占用（D73 的 reg_cap，活集口径：融合核工作集装得下"
    "几份）；输入分块超 SRAM（staging 失败）损失的是复用不是工作集——只作"
    "警告。门槛集与 D75 案例库 ground truth 对齐：R4（工作集顶爆寄存器堆）拒、"
    "R3keep（staging 失败）仍融",
    "E6 决策在候选**声明的形式**（form 字段）上做；形式排序只输出提示——"
    "换形式 = 改写候选图（谁读谁不读变了），是后续 Pattern 的工作",
    "E7 force 模式只看合法性（合法即融），评分照记——它是 A/B 校准与误差"
    "测量的工具，不是生产模式；默认模式必须是 auto",
    "E8 误差四轴：口径（spill 下界、不计 launch）/ 参数（机器卡是假设的）/"
    "输入（动态 Shape → 评分未知）/ 未计价（并发等）。今天的两个实弹只演示"
    "参数轴（换卡翻转 R4）与输入轴（动态 Shape 拒之门外）",
]


# ================================================================
# 2. 候选的图结构描述（与第 75 天同构；新增 form 字段）
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
    """组内生产的中间 Tensor 的使用者关系（D52 口径）＋ 拓扑信息（D75）。

    in_group_users  组内消费者数（这些读在融合后消失）
    out_group_users 组外消费者数（这些读必须保留；kept=True 或走重算形式）
    kept            组外 > 0 时是否保留落盘（keep 策略）
    elems           元素数；未知（动态）填 -1
    producer/consumers  D75 的 L6 拓扑序检查用（不填 = 不检查）
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
    """一个待评估的融合候选：结构（合法性读）＋ 资源上下文（计价读）＋ 形式。

    form  声明的融合形式（E6）："keep"（默认，中间落盘喂组外）或
          "recompute"（删中间，组外使用者重算生产者）
    """

    name: str
    ops: tuple[Op, ...]
    intermediates: tuple[Intermediate, ...] = ()
    workload: tuple[int, int, int] | None = None     # (M, K, N)；动态维 -1
    tile: tuple[int, int] | None = None              # (tile_m, tile_n)；None = 不分块
    form: str = "keep"


SUPPORTED_PATTERNS: dict[tuple[str, ...], str] = {
    ("matmul", "add"): "mini.fused_matmul_bias",
    ("matmul", "add", "relu"): "mini.fused_matmul_bias_relu",
    ("add", "relu"): "mini.fused_add_relu",
    ("matmul", "matmul"): "experimental.matmul_matmul",
}
SUPPORTED_DTYPES = {"fp32"}
MODES = ("force", "auto")


# ================================================================
# 3. 合法性层：D75 规则集原样（L1–L6 含 L3b/L6，接口与 D74/D75 一致）
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


def can_fuse(c: FusionCandidate) -> LegalityReport:
    """能否融合：结构/语义问题，与机器无关、与收益无关（D75 规则集）。"""
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
    for i in range(len(c.ops) - 1):                         # L3b（D75）
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
    for it in c.intermediates:                             # L6（D75）
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


# ================================================================
# 4. 计价内核：D72/D73/D75 三本账 → itemized 明细（CostItem）
# ================================================================

@dataclass
class CostItem:
    """明细账的一行：带符号的字节数 ＋ 公式出处 ＋ 一句人话（可解释性的最小单位）。"""

    name: str          # 账目名，如「消除中间落盘 ΔB」
    sign: int          # +1 收益 / −1 代价
    bytes: int         # 字节数（恒正；符号在 sign 里）
    source: str        # 公式出处：D72 / D73 / D75
    why: str           # 一句人话解释


@dataclass
class FormScore:
    """一种融合形式（keep / recompute）的评分单。"""

    form: str                      # "keep" | "recompute"
    known: bool = True             # 动态 Shape → False（D61/D62：未知 ≠ 任意）
    score: int | None = None       # = Σ sign·bytes（统一计价，字节）
    items: list[CostItem] = field(default_factory=list)
    # 资源侧（D73 同款；keep 与 recompute 共用——融合核结构一样）
    reg_demand: int = 0            # 单 tile 寄存器占用（累加器 + bias 在飞）
    extra_live: int = 0            # 额外活集（MM→MM 的 G 行块）
    sram_demand: int = 0           # A/B 分块驻留需求
    live_bytes: int = 0
    spill_bytes: int = 0
    spill_traffic: int = 0         # = 2 × spill_bytes × 行块缩放（D73 A4 下界）
    placement: str = ""
    reg_tiles: int = 1             # 寄存器并发 = 寄存器堆 ÷ 单 tile 占用（门槛量）
    concurrent_tiles: int = 1      # D73 完整模型并发 = min(寄存器, SRAM 分块)（报告量）
    staging_ok: bool = True
    # 形式专属
    delta_b: int = 0               # keep：消除的落盘（D72）
    recompute_elim: int = 0        # recompute：消除的全部流量（D75 扩展②）
    recompute_penalty: int = 0     # recompute：组外重读罚（D75 扩展②）


def _d72_passes(it: Intermediate) -> int:
    """D72 多使用者规则：组外无人 → 写＋组内读全消失；组外有人 → 只省组内读。"""
    return (1 + it.in_group_users) if it.out_group_users == 0 else it.in_group_users


def _resource_side(c: FusionCandidate, m: Machine, fs: FormScore) -> None:
    """D73 的资源账（keep 与 recompute 共用：融合核结构一样，只是中间落不落盘）。"""
    kinds = tuple(op.kind for op in c.ops)
    M, K, N = c.workload
    tm, tn = c.tile if c.tile is not None else (M, N)

    if "matmul" in kinds:
        fs.reg_demand = tm * tn * m.itemsize                 # 累加器块
        if "add" in kinds:                                   # bias 在飞：每通道 1 槽
            fs.reg_demand += m.lanes * m.itemsize
        fs.sram_demand = (tm * K + K * tn) * m.itemsize       # A/B 分块（有复用才驻留）
        if kinds == ("matmul", "matmul"):                    # G 行块（消费者归约维钉死）
            Kmid = c.ops[0].out_shape[1]
            fs.extra_live = tm * Kmid * m.itemsize
            fs.sram_demand = 0                                # D73 A10：输入分块不建模
    else:                                                    # (add, relu)：在飞向量
        fs.reg_demand = m.lanes * (2 + 1) * m.itemsize        # 2 入 1 出（D73 A5）

    fs.live_bytes = fs.reg_demand + fs.extra_live
    demoted = min(max(0, fs.live_bytes - m.regfile_bytes), m.sram_bytes)
    fs.spill_bytes = max(0, fs.live_bytes - m.onchip_bytes)
    fs.placement = ("spill" if fs.spill_bytes > 0
                    else "reg+sram" if demoted > 0 else "reg")
    staging_left = m.sram_bytes - demoted
    fs.staging_ok = fs.sram_demand <= staging_left
    # 门槛量（E5）：寄存器并发只看工作集（累加器），与 D73 的 reg_cap 同式
    fs.reg_tiles = max(1, m.regfile_bytes // max(1, fs.reg_demand))
    # 报告量：D73 完整模型（min 寄存器 / SRAM 分块）——两个数都进报告
    reg_cap = m.regfile_bytes // max(1, fs.reg_demand)
    sram_cap = (staging_left // fs.sram_demand) if fs.sram_demand > 0 else None
    fs.concurrent_tiles = max(1, reg_cap if sram_cap is None
                              else min(reg_cap, sram_cap))     # D73 教训：下限 1

    scale = (M // tm) if kinds == ("matmul", "matmul") else 1  # B8：MM→MM 按行块
    fs.spill_traffic = 2 * fs.spill_bytes * scale


def _dynamic(c: FusionCandidate) -> bool:
    M, K, N = c.workload if c.workload is not None else (None, None, None)
    tm, tn = c.tile if c.tile is not None else (M, N)
    return (M is None or tm is None or tn is None
            or min(M, K, N, tm, tn) < 0
            or any(it.elems < 0 for it in c.intermediates))


def price_keep(c: FusionCandidate, m: Machine) -> FormScore:
    """keep 形式计价（D72 ΔB − D73 spill），产出 itemized 明细。"""
    fs = FormScore("keep")
    if _dynamic(c):
        fs.known = False
        return fs
    fs.delta_b = sum(_d72_passes(it) * it.elems * m.itemsize for it in c.intermediates)
    if fs.delta_b > 0:
        fs.items.append(CostItem(
            "消除中间落盘 ΔB", +1, fs.delta_b, "D72",
            "被消除中间的趟数 × 字节（组外使用者只省组内读）"))
    _resource_side(c, m, fs)
    if fs.spill_traffic > 0:
        fs.items.append(CostItem(
            "spill 两趟税", -1, fs.spill_traffic, "D73",
            f"活集 {fs.live_bytes:,} B 装不下 {kib(m.onchip_bytes)} 片上，"
            "溢出部分写一遍读一遍（下界口径）"))
    fs.score = fs.delta_b - fs.spill_traffic
    return fs


def price_recompute(c: FusionCandidate, m: Machine) -> FormScore:
    """recompute 形式计价（D75 扩展②：消除全部中间流量 − 组外重读罚 − spill）。"""
    fs = FormScore("recompute")
    if _dynamic(c):
        fs.known = False
        return fs
    fs.recompute_elim = sum((1 + it.in_group_users + it.out_group_users)
                            * it.elems * m.itemsize for it in c.intermediates)
    producer_in_elems = 0
    for dims in c.ops[0].in_shapes:
        e = 1
        for d in dims:
            e *= max(d, 0)
        producer_in_elems += e
    fs.recompute_penalty = sum(it.out_group_users for it in c.intermediates) \
        * producer_in_elems * m.itemsize
    if fs.recompute_elim > 0:
        fs.items.append(CostItem(
            "消除全部中间流量", +1, fs.recompute_elim, "D75",
            "中间的写＋组内读＋组外读全部消失（彻底不落盘）"))
    if fs.recompute_penalty > 0:
        fs.items.append(CostItem(
            "组外重读罚", -1, fs.recompute_penalty, "D75",
            "每个组外使用者把生产者输入重读一遍"))
    _resource_side(c, m, fs)
    if fs.spill_traffic > 0:
        fs.items.append(CostItem(
            "spill 两趟税", -1, fs.spill_traffic, "D73",
            f"活集 {fs.live_bytes:,} B 溢出（与 keep 形式共用资源账）"))
    fs.score = fs.recompute_elim - fs.recompute_penalty - fs.spill_traffic
    return fs


# ================================================================
# 5. ★ Cost Model v0.1：统一计价 ＋ 两种模式 ＋ 可解释报告
# ================================================================

@dataclass
class CostReport:
    """Cost Model 的输出：评分明细 ＋ 决策 ＋ 理由 ＋ IR 对照。"""

    cand_name: str
    mode: str                                  # "force" | "auto"
    legal: bool
    legality_reasons: list[str] = field(default_factory=list)
    pattern_name: str = ""
    forms: dict[str, FormScore] = field(default_factory=dict)   # 评估过的形式
    form: str = ""                             # 声明的形式
    action: str = ""                           # "fuse" | "refuse"
    reasons: list[str] = field(default_factory=list)
    hints: list[str] = field(default_factory=list)              # 形式排序提示
    unpriced: list[str] = field(default_factory=list)           # 未计价项（只报告）
    ir_before: str = ""
    ir_after: str = ""


@dataclass
class CostModel:
    """简单 Cost Model v0.1：绑一张机器卡，对候选统一计价并给出决策。

    mode  force  强制融合：合法性过了就融，评分照记（A/B 校准用，E7）
          auto   自动决策：评分 > 0 ∧ 零 spill ∧ 寄存器并发 ≥ min_concurrency（E5）
    """

    machine: Machine
    min_concurrency: int = 3                   # D73 舒适区阈值（未计价项的门槛）

    # ---- 门槛：只查「有账 / 有阈值」的项，返回全部失败项（不短路，便于归因）----
    def _gate_fails(self, fs: FormScore) -> list[str]:
        fails: list[str] = []
        if not fs.known:
            fails.append("评分未知：动态 Shape 算不出活集与 ΔB（D61/D62：先特化）")
        elif fs.score <= 0:
            fails.append(f"评分 {fs.score:,} B ≤ 0（收益项盖不住代价项）")
        if fs.known and fs.spill_bytes > 0:
            fails.append(f"一票否决：spill {fs.spill_bytes:,} B > 0"
                         "（D73 A4：两趟税是下界，真实更贵）")
        if fs.known and fs.reg_tiles < self.min_concurrency:
            fails.append(f"并行度门槛：寄存器并发 {fs.reg_tiles} < "
                         f"{self.min_concurrency}"
                         "（D73 活集口径：工作集 ÷ 寄存器堆；未计价，只设阈值）")
        return fails

    def evaluate(self, c: FusionCandidate, mode: str = "auto") -> CostReport:
        """评估一个候选：合法性 → 双形式计价 → 声明形式决策 ＋ 形式提示。"""
        if mode not in MODES:
            raise ValueError(f"未知模式：{mode}（支持 {MODES}）")
        leg = can_fuse(c)
        rep = CostReport(cand_name=c.name, mode=mode, legal=leg.ok,
                         legality_reasons=leg.reasons,
                         pattern_name=leg.pattern_name,
                         form=c.form if leg.ok else "",
                         ir_before=emit_ir_before(c) if leg.ok else "",
                         unpriced=["launch / 编译时间 / 多核竞争不计（C8 沿用；E3）",
                                   "并发 tile 数是容量 proxy，不是吞吐率（D73 A7）"])

        if not leg.ok:                          # 非法：两种模式都拒（force 也不融非法图）
            rep.action = "refuse"
            rep.reasons = ["合法性：" + r for r in leg.reasons]
            return rep

        # ---- 计价：keep 恒评；recompute 在「有组外使用者」或「声明了」时评 ----
        rep.forms["keep"] = price_keep(c, self.machine)
        has_out_users = any(it.out_group_users > 0 for it in c.intermediates)
        if has_out_users or c.form == "recompute":
            rep.forms["recompute"] = price_recompute(c, self.machine)
        declared = rep.forms.get(c.form)
        if declared is None:                    # 声明 recompute 但没评上 → 回落 keep
            rep.form = "keep"
            declared = rep.forms["keep"]
        else:
            rep.form = c.form

        # ---- 未计价项的补充报告（staging 警告，E5）----
        if declared.known and not declared.staging_ok:
            rep.unpriced.append(
                f"staging 警告：输入分块 {declared.sram_demand:,} B 超出剩余 SRAM"
                "（损失复用是流量问题不是容量问题——只警告不否决）")

        # ---- 决策分叉：两种模式 ----
        if mode == "force":                     # E7：合法即融，评分照记
            rep.action = "fuse"
            score_txt = (f"{declared.score:,} B" if declared.known else "未知（动态）")
            rep.reasons = [f"合法性通过；force 只看合法性（评分照记：{score_txt}）"]
        else:                                   # auto：评分门槛（E5）
            fails = self._gate_fails(declared)
            if fails:
                rep.action = "refuse"
                rep.reasons = fails
            else:
                rep.action = "fuse"
                rep.reasons = [f"评分 {declared.score:,} B > 0 且三门槛全过"
                               f"（零 spill / staging ok / 寄存器并发 "
                               f"{declared.reg_tiles} ≥ {self.min_concurrency}）"]

        # ---- 形式排序提示（E6：只提示，不改写决策）----
        for fname, fs in rep.forms.items():
            if fname == rep.form or not (fs.known and declared.known):
                continue
            if fs.score > declared.score:
                other_fails = self._gate_fails(fs)
                tail = ("；但 " + "；".join(other_fails)) if other_fails \
                    else "；且门槛全过——值得改写候选"
                rep.hints.append(f"{fname} 形式评分 {fs.score:,} B（高于声明形式"
                                 f" {declared.score:,} B{tail}）")

        # ---- IR 对照（融合后按声明形式发射）----
        rep.ir_after = emit_ir_after(c, declared, leg.pattern_name)
        return rep


def explain(rep: CostReport) -> str:
    """把报告展开成人话明细账（可解释性的落地形式）。"""
    lines = [f"CostReport「{rep.cand_name}」  mode={rep.mode}  "
             f"form={rep.form or '—'}  pattern={rep.pattern_name or '—'}"]
    if not rep.legal:
        lines.append("  合法性：不通过")
        lines.extend(f"    {r}" for r in rep.legality_reasons)
        lines.append(f"  判决：{rep.action}（两种模式都拒——force 也不融非法的图）")
        return "\n".join(lines)
    fs = rep.forms[rep.form]
    lines.append("  合法性：通过")
    if not fs.known:
        lines.append("  评分：未知（动态 Shape，D61/D62——特化后再来）")
    else:
        lines.append("  明细账（评分 = Σ 带符号项，单位 B）：")
        for it in fs.items:
            lines.append(f"    {'+' if it.sign > 0 else '−'}{it.bytes:>12,}  "
                         f"{it.name}  [{it.source}] {it.why}")
        lines.append(f"  评分 = {fs.score:,} B（落位 {fs.placement}，寄存器并发 "
                     f"{fs.reg_tiles}，完整模型并发 {fs.concurrent_tiles}）")
    lines.append(f"  判决：{rep.action}")
    lines.extend(f"    理由：{r}" for r in rep.reasons)
    lines.extend(f"    提示：{h}" for h in rep.hints)
    lines.extend(f"    未计价：{u}" for u in rep.unpriced)
    return "\n".join(lines)


# ================================================================
# 6. mini-IR 发射器：融合前后对照（今天的第二份产出）
# ================================================================

def _t(shape: tuple[int, ...]) -> str:
    return "memref<" + "x".join(str(d) for d in shape) + "xf32>"


def _chain_layout(c: FusionCandidate) -> tuple[list, list]:
    """线性链布局：返回 (图输入, 每算子的输入名)。

    约定：算子 i 的第一个输入是链边（算子 i-1 的输出：中间 i-1 或最终输出），
    其余输入是图输入。图输入按出现顺序命名为 %a、%b、%d（bias）、%b1……
    """
    graph_inputs: list[tuple[str, tuple[int, ...]]] = []
    op_inputs: list[list[str]] = [[] for _ in c.ops]
    for i, op in enumerate(c.ops):
        for j, s in enumerate(op.in_shapes):
            if i > 0 and j == 0:                # 链边
                nm = (c.intermediates[i - 1].name.lower()
                      if i - 1 < len(c.intermediates) else "f")
                op_inputs[i].append("%" + nm)
            else:                               # 图输入
                if not graph_inputs:
                    base = "a"
                elif len(graph_inputs) == 1:
                    base = "b"
                elif op.kind == "add":
                    base = "d"
                else:
                    base = "b1"
                nm, k = base, 2
                while any(n == "%" + nm for n, _ in graph_inputs):
                    nm, k = f"{base}{k}", k + 1
                graph_inputs.append(("%" + nm, s))
                op_inputs[i].append("%" + nm)
    return graph_inputs, op_inputs


def emit_ir_before(c: FusionCandidate) -> str:
    """融合前：每个算子一个 kernel，中间 Tensor 显式 alloc 落盘。"""
    gins, opins = _chain_layout(c)
    out = c.ops[-1].out_shape
    head = ", ".join(f"{n}: {_t(s)}" for n, s in gins)
    inter_names = "、".join("%" + it.name.lower() for it in c.intermediates)
    lines = [f"// 融合前：{len(c.ops)} 个独立 kernel；中间 {inter_names} "
             "落盘（写 1 遍 + 被读 N 遍）",
             f"func.func @main({head}) -> {_t(out)} {{"]
    for i, op in enumerate(c.ops):
        if i < len(c.intermediates):            # 链上的中间：先 alloc 再写
            nm = c.intermediates[i].name.lower()
            lines.append(f"  %{nm} = memref.alloc() : {_t(op.out_shape)}"
                         + " " * 12 + "// 中间落盘")
            tgt = f"%{nm}"
        else:
            lines.append(f"  %f = memref.alloc() : {_t(out)}")
            tgt = "%f"
        sig = ", ".join(f"{n}: {_t(s)}" for n, s in zip(opins[i], op.in_shapes))
        opname = "mini.matmul" if op.kind == "matmul" else f"mini.{op.kind}"
        lines.append(f"  {opname} ins({sig}) outs({tgt} : {_t(op.out_shape)})")
    lines.append(f"  return %f : {_t(out)}")
    lines.append("}")
    return "\n".join(lines)


def emit_ir_after(c: FusionCandidate, fs: FormScore, pattern: str) -> str:
    """融合后：一个 kernel；keep 形式 kept 中间照样 alloc，recompute 不落盘。"""
    gins, _ = _chain_layout(c)
    out = c.ops[-1].out_shape
    head = ", ".join(f"{n}: {_t(s)}" for n, s in gins)
    kept_idx = [i for i, it in enumerate(c.intermediates)
                if it.kept and fs.form == "keep"]
    name = pattern + ("_keep" if kept_idx else "") + \
           ("_recompute" if fs.form == "recompute" else "")
    if not fs.known:
        cmt = f"// 融合后（{fs.form} 形式）：1 个 kernel（动态 Shape，评分未知）"
    elif fs.form == "keep":
        if kept_idx:
            cmt = (f"// 融合后（keep 形式）：1 个 kernel；kept 中间落盘喂组外"
                   f"——只省组内读，ΔB = {fs.delta_b:,} B")
        else:
            cmt = (f"// 融合后（keep 形式）：1 个 kernel；中间只活在核内（寄存器），"
                   f"ΔB = {fs.delta_b:,} B")
    else:
        cmt = (f"// 融合后（recompute 形式）：1 个 kernel；中间彻底不落盘："
               f"消除 {fs.recompute_elim:,} B − 重读罚 {fs.recompute_penalty:,} B")
    lines = [cmt, f"func.func @main({head}) -> {_t(out)} {{"]
    for i in kept_idx:
        nm = c.intermediates[i].name.lower()
        lines.append(f"  %{nm} = memref.alloc() : {_t(c.ops[i].out_shape)}"
                     + " " * 12 + "// kept：组外还要读")
    lines.append(f"  %f = memref.alloc() : {_t(out)}")
    sig_in = ", ".join(f"{n}: {_t(s)}" for n, s in gins)
    outs = [f"%{c.intermediates[i].name.lower()} : {_t(c.ops[i].out_shape)}"
            for i in kept_idx]
    outs.append(f"%f : {_t(out)}")
    lines.append(f"  {name} ins({sig_in}) outs({', '.join(outs)})")
    lines.append(f"  return %f : {_t(out)}")
    lines.append("}")
    return "\n".join(lines)


# ================================================================
# 7. 记账执行器：按 kernel 边界记 DRAM 读写（对拍评分的流量项）
# ================================================================

def prod(shape: tuple[int, ...]) -> int:
    p = 1
    for d in shape:
        p *= max(d, 1)
    return p


def ledger_bytes(c: FusionCandidate, form: str) -> tuple[int, int]:
    """独立执行 vs 融合执行的总 DRAM 流量（字节）。

    口径（E4）：不跑数值（数值语义 D50/52 已证），只按 kernel 边界记账——
      独立执行：每个算子读全部输入、写输出；组外使用者各读一遍中间；
      融合 keep：一个 kernel 读图输入、写最终输出＋kept 中间（各 1 遍），
                 组外使用者照读；
      融合 recompute：一个 kernel 读图输入、写最终输出；中间不写；每个
                 组外使用者把生产者含进自己的 kernel（重读生产者输入）。
    两端自己的输出不计（两种执行完全相同，进差分就消掉了）。
    """
    itemsize = 4
    gins, _ = _chain_layout(c)
    graph_in = sum(prod(s) * itemsize for _, s in gins)
    final = prod(c.ops[-1].out_shape) * itemsize
    inter = [(it, it.elems * itemsize) for it in c.intermediates]
    producer_in = sum(prod(s) * itemsize for s in c.ops[0].in_shapes)

    baseline = graph_in + final
    for it, b in inter:
        baseline += (1 + it.in_group_users + it.out_group_users) * b   # 写＋所有读

    if form == "keep":
        fused = graph_in + final
        for it, b in inter:
            if it.kept:                          # 写 1 遍 ＋ 组外各读 1 遍
                fused += (1 + it.out_group_users) * b
    else:                                        # recompute
        fused = graph_in + final
        for it, b in inter:
            fused += it.out_group_users * producer_in     # 每个组外重读生产者输入
    return baseline, fused


# ================================================================
# 8. 第 75 天案例库（ground truth 回归用）：两翼 16 例
# ================================================================

@dataclass
class CaseEntry:
    name: str
    wing: str
    cat: str
    why: str
    build: object                              # 零参函数 → FusionCandidate
    expect_auto: str = "refuse"                # D75 案例库的 ground truth 判决


def chain_ops(M: int, K: int, N: int) -> tuple[Op, ...]:
    """贯穿链 MatMul(M,K)@B(K,N) → +D → relu 的算子序列（D39/D40 规则全过）。"""
    return (Op("matmul", ((M, K), (K, N)), (M, N)),
            Op("add", ((M, N), (M, N)), (M, N)),
            Op("relu", ((M, N),), (M, N)))


def cand_full(M: int, K: int, N: int, tile: tuple[int, int] | None = None,
              name: str = "P3 全融合",
              form: str = "keep") -> FusionCandidate:
    """贯穿链全融合：C、E 组内消化（D50 的 fused_matmul_bias_relu）。"""
    return FusionCandidate(name, chain_ops(M, K, N),
                           intermediates=(Intermediate("C", M * N, 1, 0),
                                          Intermediate("E", M * N, 1, 0)),
                           workload=(M, K, N), tile=tile, form=form)


def cand_mm_mm(M: int, K: int, Kmid: int, N: int, tile: tuple[int, int],
               out_users: int = 0, name: str | None = None,
               form: str = "keep") -> FusionCandidate:
    """MatMul(M,K)→G(M,Kmid)→MatMul(Kmid,N)；out_users>0 时 G 有组外使用者。"""
    ops = (Op("matmul", ((M, K), (K, Kmid)), (M, Kmid)),
           Op("matmul", ((M, Kmid), (Kmid, N)), (M, N)))
    kept = out_users > 0
    return FusionCandidate(name or f"MM→MM K1={Kmid}", ops,
                           intermediates=(Intermediate("G", M * Kmid, 1, out_users,
                                                       kept=kept),),
                           workload=(M, K, N), tile=tile, form=form)


def cand_skinny(M: int, K: int, N: int, out_users: int = 2,
                name: str = "skinny {MatMul,Add}",
                form: str = "keep") -> FusionCandidate:
    """瘦矩阵 MatMul(M,K)→C(M,N)→+D：C 有 out_users 个组外使用者。"""
    ops = (Op("matmul", ((M, K), (K, N)), (M, N)),
           Op("add", ((M, N), (M, N)), (M, N)))
    return FusionCandidate(name, ops,
                           intermediates=(Intermediate("C", M * N, 1, out_users,
                                                       kept=out_users > 0),),
                           workload=(M, K, N), tile=(M, N), form=form)


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
        CaseEntry("A7 组内循环依赖", "A 结构负例", "L6 拓扑序",
                  "F 由算子2(relu) 生产却被算子0(matmul) 消费——组内成环",
                  lambda: FusionCandidate(
                      "A7 循环依赖", chain_ops(M0, K0, N0),
                      intermediates=(Intermediate("C", 4, 1, 0,
                                                  producer=0, consumers=(1,)),
                                     Intermediate("E", 4, 1, 0,
                                                  producer=1, consumers=(2,)),
                                     Intermediate("F", 4, 1, 0,
                                                  producer=2, consumers=(0,))))),
        CaseEntry("A8 边形状不匹配", "A 结构负例", "L3b 边形状",
                  "MatMul 输出 (2,4) 直接喂 (4,2) 的 add——边上有隐式 Reshape",
                  lambda: FusionCandidate(
                      "A8 隐式 Reshape",
                      (Op("matmul", ((2, 3), (3, 4)), (2, 4)),
                       Op("add", ((4, 2), (4, 2)), (4, 2))))),
    ]


def wing_b_cases() -> list[CaseEntry]:
    M1, K1s, N1 = 2048, 64, 2048          # 放大版贯穿链
    return [
        CaseEntry("R1 多使用者", "B 负收益", "R1 多使用者",
                  "G 有 1 个组外使用者：写趟被钉死，ΔB 从 16 MiB 塌缩到 8 MiB，"
                  "keep 形式评分 −2 MiB",
                  lambda: cand_mm_mm(M1, K1s, 1024, N1, (128, 128), out_users=1,
                                     name="R1 MM→MM K1=1024 +1 组外")),
        CaseEntry("R1 对照（无组外）", "B 负收益", "R1 多使用者",
                  "同一张图、没有组外使用者：ΔB 16 MiB，评分 +6 MiB——"
                  "但 spill 未消除，auto 仍拒（翻转点）",
                  lambda: cand_mm_mm(M1, K1s, 1024, N1, (128, 128), out_users=0,
                                     name="R1ctl MM→MM K1=1024")),
        CaseEntry("R2 资源超限", "B 负收益", "R2 资源超限",
                  "tile=2048 不分块：活集 17,301,504 B 顶爆 256 KiB，"
                  "spill 两趟税 34 MiB 吞掉 ΔB 1 MiB",
                  lambda: cand_mm_mm(M1, K1s, 64, N1, (2048, 2048),
                                     name="R2 MM→MM K1=64 tile2048")),
        CaseEntry("R2 对照（tile 64）", "B 负收益", "R2 资源超限",
                  "同一张图缩到 tile=64：活集 32,768 B 全驻寄存器，"
                  "并发 4，评分 +1 MiB——图没问题，是 tile 的锅",
                  lambda: cand_mm_mm(M1, K1s, 64, N1, (64, 64),
                                     name="R2ctl MM→MM K1=64 tile64"),
                  expect_auto="fuse"),
        CaseEntry("R3 keep 形式", "B 负收益", "R3 重复计算",
                  "瘦矩阵 K=4096：keep 形式省 C 的组内读 16 KiB，"
                  "零 spill、寄存器并发 3——对照组",
                  lambda: cand_skinny(64, 4096, 64, out_users=2,
                                      name="R3keep skinny(64,4096)"),
                  expect_auto="fuse"),
        CaseEntry("R3 重算形式", "B 负收益", "R3 重复计算",
                  "删 C 靠重算喂 2 个组外使用者：消除 64 KiB，"
                  "生产者输入重读 4 MiB——评分 −3.94 MiB",
                  lambda: cand_skinny(64, 4096, 64, out_users=2,
                                      name="R3recompute skinny(64,4096)",
                                      form="recompute")),
        CaseEntry("R4 并行度下降", "B 负收益", "R4 并行度",
                  "P3 tile=128：评分 +64 MiB、零 spill，但占用 65,792 B "
                  "超过寄存器堆——寄存器并发 1 < 3",
                  lambda: cand_full(M1, K1s, N1, tile=(128, 128),
                                    name="R4 P3 tile128")),
        CaseEntry("R4 对照（tile 64）", "B 负收益", "R4 并行度",
                  "同一张图缩到 tile=64：寄存器并发 3、评分不变 64 MiB——"
                  "拒绝坏 tile 一分钱不花",
                  lambda: cand_full(M1, K1s, N1, tile=(64, 64),
                                    name="R4ctl P3 tile64"),
                  expect_auto="fuse"),
    ]


# ================================================================
# 主实验
# ================================================================

def main() -> None:
    m = Machine()
    model = CostModel(m)
    print("== 1. 接口卡与假设清单（Cost Model v0.1）==")
    print(f"  CostModel 字段：machine={m.name}（target 绑定，E1），"
          f"min_concurrency={model.min_concurrency}（D73 舒适区）")
    print(f"  evaluate{inspect.signature(CostModel.evaluate)}；"
          f"can_fuse{inspect.signature(can_fuse)}（不吃机器卡——接口纪律沿用 D74/D75）")
    print(f"  模式：{MODES[0]}（合法即融，评分照记）/ {MODES[1]}（评分 > 0 ∧ "
          f"零 spill ∧ 寄存器并发 ≥ {model.min_concurrency}）")
    for a in ASSUMPTIONS:
        print(f"  {a}")
    leg_params = set(inspect.signature(can_fuse).parameters)
    ev_params = set(inspect.signature(CostModel.evaluate).parameters)
    check("1a 接口纪律：can_fuse 不吃机器卡；evaluate 吃候选＋模式，不吃账本",
          "m" not in leg_params and "machine" not in leg_params
          and {"c", "mode"} <= ev_params and "prof" not in ev_params)
    check("1b 假设清单 E1–E8 共 8 项，覆盖四类误差来源（口径/参数/输入/未计价）",
          len(ASSUMPTIONS) == 8
          and any("口径" in a for a in ASSUMPTIONS)
          and any("参数" in a for a in ASSUMPTIONS)
          and any("输入" in a for a in ASSUMPTIONS)
          and any("未计价" in a for a in ASSUMPTIONS))
    try:
        model.evaluate(cand_full(2, 3, 2), mode="turbo")
        bad_mode_raises = False
    except ValueError:
        bad_mode_raises = True
    check("1c 未知模式直接报错（不静默回落）", bad_mode_raises)

    # ---- 2. 贯穿例子：P3 小链的完整报告 ----
    print("\n== 2. 贯穿例子：P3 小链 A(2,3)@B(3,2)→+D→relu 的第一张报价单 ==")
    rep = model.evaluate(cand_full(2, 3, 2), mode="auto")
    print(explain(rep))
    fs = rep.forms["keep"]
    check("2a keep 形式评分 = 64 B（与 D72 的 ΔB 逐位一致；活集 272 B 零 spill）",
          fs.score == 64 and fs.delta_b == 64 and fs.spill_bytes == 0
          and fs.live_bytes == 272)
    check("2b auto 判 fuse：三门槛全过（零 spill / staging ok / 寄存器并发 240）",
          rep.action == "fuse" and fs.reg_tiles == 240 and fs.staging_ok)
    rep_f = model.evaluate(cand_full(2, 3, 2), mode="force")
    check("2c force 也判 fuse，但理由不同（只看合法性，评分照记）",
          rep_f.action == "fuse"
          and rep_f.reasons[0].startswith("合法性通过；force"))
    print("\n  IR 对照（融合前 3 kernel → 融合后 1 kernel）：")
    print("\n".join("  " + l for l in rep.ir_before.splitlines()))
    print()
    print("\n".join("  " + l for l in rep.ir_after.splitlines()))
    check("2d IR 对照：融合前 3 个 mini kernel、3 次 alloc（2 中间＋1 输出）；"
          "融合后 1 个 fused kernel、1 次 alloc",
          rep.ir_before.count("mini.matmul") == 1
          and rep.ir_before.count("mini.add") == 1
          and rep.ir_before.count("mini.relu") == 1
          and rep.ir_before.count("memref.alloc") == 3
          and rep.ir_after.count("mini.fused_matmul_bias_relu") == 1
          and rep.ir_after.count("memref.alloc") == 1)
    txt = explain(rep)
    check("2e 可解释性机检：明细账每项带 [D72]/[D73]/[D75] 出处标注",
          all(f"[{it.source}]" in txt for it in fs.items) and "[D72]" in txt)

    # ---- 3. 记账对拍：评分的流量项 vs 逐 kernel 记账 ----
    print("\n== 3. 记账对拍：评分公式 vs 逐 kernel 记账（20 组随机，E4 口径）==")
    rng = random.Random(76)
    n_ok_keep = n_ok_recompute = n_recompute = 0
    for t in range(20):
        kind = rng.choice(("p3", "mm2", "skinny"))
        M, K, N, Kmid = (rng.randint(1, 48) for _ in range(4))
        r = rng.randint(0, 3)
        if kind == "p3":
            r1, r2 = rng.randint(0, 2), rng.randint(0, 2)
            c = FusionCandidate(
                f"rand{t}", chain_ops(M, K, N),
                intermediates=(Intermediate("C", M * N, 1, r1, kept=r1 > 0),
                               Intermediate("E", M * N, 1, r2, kept=r2 > 0)),
                workload=(M, K, N))
        elif kind == "mm2":
            c = cand_mm_mm(M, K, Kmid, N, (M, N), out_users=r, name=f"rand{t}")
        else:
            c = cand_skinny(M, K, N, out_users=r, name=f"rand{t}")
        base_k, fused_k = ledger_bytes(c, "keep")
        fs_k = price_keep(c, m)
        if base_k - fused_k == fs_k.delta_b:
            n_ok_keep += 1
        if any(it.out_group_users > 0 for it in c.intermediates):
            n_recompute += 1
            base_r, fused_r = ledger_bytes(c, "recompute")
            fs_r = price_recompute(c, m)
            if base_r - fused_r == fs_r.recompute_elim - fs_r.recompute_penalty:
                n_ok_recompute += 1
    print("  随机 20 组（p3/mm2/skinny 混合，组外 0~3 随机）：")
    print(f"    keep 形式：记账差值 == ΔB 公式 → {n_ok_keep}/20")
    print(f"    recompute 形式（有组外使用者的 {n_recompute} 组）："
          f"记账差值 == elim − 罚 → {n_ok_recompute}/{n_recompute}")
    check("3a keep 对拍：20 组随机上「独立执行 − 融合执行」== ΔB 公式（逐位）",
          n_ok_keep == 20)
    check("3b recompute 对拍：记账差值 == elim − 罚（逐位）",
          n_ok_recompute == n_recompute and n_recompute >= 8)
    c0 = cand_full(2, 3, 2)
    b0, f0 = ledger_bytes(c0, "keep")
    check("3c 拆账闭合（贯穿例）：独立执行 144 B、融合执行 80 B、差值 64 B"
          "（D71/D72 账本逐位对上）",
          b0 == 144 and f0 == 80 and b0 - f0 == 64)
    c_mm = cand_mm_mm(2048, 64, 1024, 2048, (128, 128))
    b_mm, f_mm = ledger_bytes(c_mm, "keep")
    fs_mm = price_keep(c_mm, m)
    check("3d 对拍的边界：记账器只看流量（差值 == ΔB 16,777,216 B），"
          "cost model 还有一笔它看不见的 spill 两趟税 10,485,760 B"
          "——容量模型只在 cost model 里",
          b_mm - f_mm == fs_mm.delta_b == 16_777_216
          and fs_mm.spill_traffic == 10_485_760)

    # ---- 4. 形式排序：R1 那张图，keep 与 recompute 同台 ----
    print("\n== 4. 形式排序：R1 的图（MM→MM K1=1024，1 个组外使用者）==")
    r1 = cand_mm_mm(2048, 64, 1024, 2048, (128, 128), out_users=1,
                    name="R1 MM→MM K1=1024 +1 组外")
    rep_r1 = model.evaluate(r1, mode="auto")
    print(explain(rep_r1))
    fk = rep_r1.forms["keep"]
    fr = rep_r1.forms["recompute"]
    print(f"\n  形式排序：keep {fk.score:,} B  <  recompute {fr.score:,} B"
          f"（差 {fr.score - fk.score:,} B）")
    check("4a keep 形式评分 −2,097,152 B（复现 D75 的净收益，逐位）",
          fk.score == -2_097_152 and fk.delta_b == 8_388_608)
    check("4b recompute 形式评分 +13,893,632 B（消除 25,165,824 − 罚 786,432 "
          "− spill 10,485,760）",
          fr.score == 13_893_632 and fr.recompute_elim == 25_165_824
          and fr.recompute_penalty == 786_432 and fr.spill_traffic == 10_485_760)
    check("4c 资源账与形式无关：两形式的 spill 同为 10,485,760 B"
          "（融合核结构一样，D75 的共用口径）",
          fk.spill_traffic == fr.spill_traffic == 10_485_760)
    check("4d 声明形式（keep）决策：refuse；recompute 门槛也过不了（spill 一票否决）"
          "——ground truth 的 R1 判决保持",
          rep_r1.action == "refuse"
          and model._gate_fails(fr)[0].startswith("一票否决：spill"))
    check("4e 形式提示如实输出：报告含「recompute 形式评分更高」且带门槛结论",
          any("recompute 形式评分 13,893,632" in h and "一票否决" in h
              for h in rep_r1.hints))
    check("4f 评分恒等式：score == Σ sign·bytes（两个形式都成立）",
          fk.score == sum(i.sign * i.bytes for i in fk.items)
          and fr.score == sum(i.sign * i.bytes for i in fr.items))

    # ---- 5. 误差实弹：参数轴（换机器卡）与输入轴（动态 Shape）----
    print("\n== 5. 误差实弹：只拧一个参数，看判决怎么翻（E8）==")
    r4 = cand_full(2048, 64, 2048, tile=(128, 128), name="R4 P3 tile128")
    rep_r4 = model.evaluate(r4, mode="auto")
    big_card = CostModel(Machine(name="toy-core wide", regfile_bytes=256 * 1024))
    rep_r4_big = big_card.evaluate(r4, mode="auto")
    print("  [参数轴] 同一候选 R4 P3 tile128，只换机器卡：")
    print(f"    {m.name}（64 KiB 寄存器堆）：寄存器并发 "
          f"{rep_r4.forms['keep'].reg_tiles} → {rep_r4.action}"
          f"（评分 {rep_r4.forms['keep'].score:,} B）")
    print(f"    {big_card.machine.name}（256 KiB 寄存器堆）：寄存器并发 "
          f"{rep_r4_big.forms['keep'].reg_tiles} → {rep_r4_big.action}"
          f"（评分 {rep_r4_big.forms['keep'].score:,} B）")
    check("5a 参数误差实弹：寄存器堆 64→256 KiB，R4 寄存器并发 1→3，"
          "auto 判决 refuse→fuse；评分一字不差（67,108,864 B）",
          rep_r4.action == "refuse" and rep_r4_big.action == "fuse"
          and rep_r4.forms["keep"].reg_tiles == 1
          and rep_r4_big.forms["keep"].reg_tiles == 3
          and rep_r4.forms["keep"].score == rep_r4_big.forms["keep"].score
          == 67_108_864)
    r4_dyn = cand_full(-1, 64, 2048, tile=(64, 64), name="R4dyn P3 动态M")
    rep_dyn = model.evaluate(r4_dyn, mode="auto")
    rep_dyn_f = model.evaluate(r4_dyn, mode="force")
    print(f"  [输入轴] M 拧成 -1（动态）：评分 "
          f"{'未知' if not rep_dyn.forms['keep'].known else '已知'}"
          f" → auto {rep_dyn.action}；force {rep_dyn_f.action}")
    print(f"    理由：{rep_dyn.reasons[0]}")
    check("5b 输入误差实弹：动态 Shape → 评分未知（known=False）→ auto 拒；"
          "force 仍融（它只看合法性——模式差异）",
          not rep_dyn.forms["keep"].known and rep_dyn.action == "refuse"
          and rep_dyn_f.action == "fuse")
    check("5c 未计价项清单非空且如实：launch/编译时间/多核竞争 + 并发 proxy 说明",
          len(rep_r4.unpriced) >= 2
          and any("launch" in u for u in rep_r4.unpriced)
          and any("proxy" in u for u in rep_r4.unpriced))
    skinny_rep = model.evaluate(cand_skinny(64, 4096, 64), mode="auto")
    check("5d staging 警告（不否决）：R3keep 输入分块 2,097,152 B > SRAM、"
          "完整模型并发 1，但寄存器并发 3、判决仍 fuse——工作集与复用分开（E5）",
          not skinny_rep.forms["keep"].staging_ok
          and skinny_rep.forms["keep"].concurrent_tiles == 1
          and skinny_rep.forms["keep"].reg_tiles == 3
          and any("staging" in u for u in skinny_rep.unpriced)
          and skinny_rep.action == "fuse")

    # ---- 6. IR 对照：R1 双形式与 R3 双形式 ----
    print("\n== 6. IR 对照（第二份产出）：同一张图、两种形式的融合后 IR ==")
    rep_r1r = model.evaluate(
        cand_mm_mm(2048, 64, 1024, 2048, (128, 128), out_users=1,
                   name="R1 keep", form="keep"), mode="auto")
    rep_r1x = model.evaluate(
        cand_mm_mm(2048, 64, 1024, 2048, (128, 128), out_users=1,
                   name="R1 recompute", form="recompute"), mode="auto")
    print("\n".join("  " + l for l in rep_r1r.ir_after.splitlines()))
    print()
    print("\n".join("  " + l for l in rep_r1x.ir_after.splitlines()))
    outs_line_r = [l for l in rep_r1r.ir_after.splitlines() if "outs(" in l][0]
    outs_line_x = [l for l in rep_r1x.ir_after.splitlines() if "outs(" in l][0]
    check("6a R1 keep IR：outs 两个（%g kept ＋ %f），kernel 名带 _keep 后缀，"
          "注释含 ΔB 8,388,608 B",
          "experimental.matmul_matmul_keep" in outs_line_r
          and "%g" in outs_line_r and "%f" in outs_line_r
          and "8,388,608" in rep_r1r.ir_after)
    check("6b R1 recompute IR：outs 只剩 %f（G 不落盘），kernel 名带 _recompute，"
          "注释含重读罚 786,432 B",
          "experimental.matmul_matmul_recompute" in outs_line_x
          and "%f" in outs_line_x and "%g" not in rep_r1x.ir_after
          and "786,432" in rep_r1x.ir_after)
    rep_r3k = model.evaluate(cand_skinny(64, 4096, 64, out_users=2,
                                         name="R3 keep"), mode="auto")
    rep_r3x = model.evaluate(cand_skinny(64, 4096, 64, out_users=2,
                                         name="R3 recompute",
                                         form="recompute"), mode="auto")
    check("6c R3 双形式 IR 对照：keep 的 %c 有 alloc（落盘喂组外）、kernel 名带"
          "_keep；recompute 的 %c 消失（重算）、kernel 名带 _recompute",
          "%c = memref.alloc" in rep_r3k.ir_after
          and "mini.fused_matmul_bias_keep" in rep_r3k.ir_after
          and "%c" not in rep_r3x.ir_after
          and "mini.fused_matmul_bias_recompute" in rep_r3x.ir_after)

    # ---- 7. 决策结果表：16 例 ground truth 回归（今天的核心产出）----
    print("\n== 7. 决策结果表：D75 案例库 16 例 × 两种模式（ground truth 回归）==")
    print("  案例                          形式          评分(B)       spill  R并发"
          "  force   auto    首条理由 / 提示")
    all_cases = wing_a_cases() + wing_b_cases()
    results: dict[str, CostReport] = {}
    n_match = 0
    for e in all_cases:
        c = e.build()
        rf = model.evaluate(c, mode="force")
        ra = model.evaluate(c, mode="auto")
        results[e.name] = ra
        if ra.action == e.expect_auto:
            n_match += 1
        fs = ra.forms.get(ra.form) if ra.legal else None
        score = f"{fs.score:,}" if (fs and fs.known) else "—"
        spill = f"{fs.spill_bytes:,}" if (fs and fs.known) else "—"
        conc = str(fs.reg_tiles) if (fs and fs.known) else "—"
        first = (ra.reasons[0] if ra.reasons else "")[:46]
        hint = ("  ↳ " + ra.hints[0][:44]) if ra.hints else ""
        print(f"  {c.name:<30s} {ra.form if ra.legal else '—':<9s} {score:>12s} "
              f"{spill:>9s} {conc:>4s}  {rf.action:<6s}  {ra.action:<6s} "
              f"{first}{hint}")
    check("7a 表 16 行完整：翼 A 8 ＋ 翼 B 8，全部带两种模式的判决",
          len(all_cases) == 16 and len(results) == 16)
    check("7b ground truth 回归：auto 判决与 D75 案例库逐例一致（16/16）",
          n_match == 16)
    legal = [e for e in all_cases if results[e.name].legal]
    check("7c force 列：合法 8 例全部 fuse（评分照记）、非法 8 例全部 refuse"
          "（force 也不融非法的图）",
          len(legal) == 8
          and all(model.evaluate(e.build(), "force").action == "fuse"
                  for e in legal)
          and all(model.evaluate(e.build(), "force").action == "refuse"
                  for e in all_cases if e not in legal))
    prefixes = ("合法性：", "评分", "一票否决", "并行度门槛")
    refuse_rows = [results[e.name] for e in all_cases
                   if results[e.name].action == "refuse"]
    check("7d 理由可归因：auto 拒绝行的首条理由 ∈ {合法性：/ 评分 / 一票否决：spill"
          " / 并行度门槛：}（cost model 把 D75 的四层判据归成三类）",
          all(r.reasons[0].startswith(prefixes) for r in refuse_rows))
    check("7e 形式提示出现在该出现的地方：R1（keep 拒、recompute 分高）与 "
          "R3recompute（recompute 拒、keep 分高）都有提示",
          any("recompute 形式评分" in h for h in results["R1 多使用者"].hints)
          and any("keep 形式评分" in h for h in results["R3 重算形式"].hints))
    check("7f 三类拒绝理由都在表里出现：评分 ≤ 0（R1）/ spill 一票否决（R1ctl）/"
          " 并行度门槛（R4）——门槛归因互不相同",
          results["R1 多使用者"].reasons[0].startswith("评分")
          and results["R1 对照（无组外）"].reasons[0].startswith("一票否决")
          and results["R4 并行度下降"].reasons[0].startswith("并行度门槛"))

    # ---- 8. 结果 ----
    print(f"\n== 结果：{PASSED}/{CHECKS} 项检查通过 ==")


if __name__ == "__main__":
    main()
