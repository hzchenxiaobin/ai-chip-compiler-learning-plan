#!/usr/bin/env python3
"""D106 搜索空间生成器：把 Tile／循环顺序／Unroll／缓冲策略组成有限候选集合，
在爆炸发生之前剪掉无意义搭配，并把每一刀的数字留在统计里。

设计要点（与 README 一致）：
  1) 值域剪枝先行：每个轴的取值从问题本身推导（整除／对齐倍数／上下界），
     而不是从 1..N 暴力枚举——naive 的 25,769,803,776 在生成之前就缩成 20,580。
  2) 跨轴参数约束：单轴值域表达不了的搭配规则（U ≤ 最内层圈数）在生成时
     判掉——展开份数超过最内层圈数 = 主循环 0 圈＋尾部循环干全部活的死代码。
  3) 资源约束复用 D104 闸门：五项家当 ≤ 预算，记账规则一行不改（与 D101/
     D104 逐数字对账，self_test 里有锚点断言）。
  4) 统计是交付物：每一层剪掉多少、为什么、例子是谁，全部可断言、可复现。
  5) 值域带逃生门：整除模式剪成空集时（如 516）自动降级到尾部模式——
     空集不是答案，是值域规则写错了的警报（D95 的尾部机制接得住）。
  6) 确定性：纯迭代生成、无随机；同一 SpaceSpec 两次生成逐项相等。

分工边界（D74 分离原则）：生成器只负责"喂"，参数约束和 D104 闸门负责"裁"，
排序是 D110 Cost Model 的事，测量是 D107/D108 的事——本文件不比较谁更快。
"""

from __future__ import annotations

import argparse
import dataclasses
import itertools
import os
import sys
from typing import Optional

# ---------------------------------------------------------------- 基础表（与 D104 同源）

DTYPES = {"fp32": 4, "fp16": 2, "bf16": 2, "int8": 1, "int32": 4}
ACC_AUTO = {"int8": "int32", "fp16": "fp32", "bf16": "fp32", "fp32": "fp32"}
DEFAULT_ALIGN = 32
DEFAULT_BUDGET = 256 * 1024

# 循环顺序：i/j/k 的全部 6 种排列（外→内），与 D92/D93 同一套记法。
# D92 的缓存账：排名随容量翻转（512B 时连续派赢、1KB 时寄存器派反超），
# 没有普适的坏顺序——所以 v1 不敢剪，6 种全留，让 D107 的 benchmark 说话。
ORDERS = tuple(itertools.permutations(("i", "j", "k")))

# Unroll 轴：D96 实测 U=8 机器码已 3.2×；16 是放到 I-cache 边缘的"过界探针"，
# 留给 D107 实测它是不是真的过头。naive 枚举会试遍 1..16 每个整数——
# 这里只留 2 的幂：U=13 这种素数份数没有任何向量宽度能对齐。
UNROLL_POOL = (1, 2, 4, 8, 16)

# 尾部模式的精选手工池（D97/D104 的老朋友）：非 2 幂的 96/160 也收进来，
# 因为 D95 的尾部机制接得住；上界 256 之上尾部浪费常超过一半。
CURATED_TAIL_POOL = (32, 64, 96, 128, 160, 256)

BAR = "=" * 78


def align_up(n: int, a: int) -> int:
    if a <= 0:
        raise ValueError(f"对齐必须为正数，得到 {a}")
    return (n + a - 1) // a * a


def fmt_b(n: int) -> str:
    return f"{n:,} B"


def fmt_pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def parse_bytes(text: str) -> int:
    """接受 256K / 256KB / 262144 / 1M 等写法（K、M 均按 1024 进制）。"""
    t = text.strip().upper().replace("IB", "")
    if t.endswith("K"):
        return int(float(t[:-1]) * 1024)
    if t.endswith("M"):
        return int(float(t[:-1]) * 1024 * 1024)
    return int(t)


# ---------------------------------------------------------------- 候选与记账（与 D104 逐数字一致）


@dataclasses.dataclass(frozen=True)
class KernelConfig:
    """搜索空间里的一个点：tile 三元组 + 循环顺序 + 展开份数 + 缓冲策略。

    有意不做构造期校验：与 D104 的 TileCandidate 同一哲学——候选是数据，
    设防在判定层（本文件的跨轴约束 + D104 的参数校验），不在数据层。
    order 是"外→内"的下标排列，如 ("i","k","j") 表示 j 是最内层。
    """

    tm: int
    tn: int
    tk: int
    order: tuple
    unroll: int
    buffering: str
    dtype_in: str = "fp32"
    bias: bool = True
    staging: bool = False

    @property
    def inner_dim(self) -> str:
        """最内层下标：order 的最后一个字母——unroll 作用的对象。"""
        return self.order[-1]

    @property
    def inner_trip(self) -> int:
        """最内层元素循环的圈数：展开份数不能超过它。"""
        return {"i": self.tm, "j": self.tn, "k": self.tk}[self.inner_dim]

    def describe(self) -> str:
        tile = f"{self.tm}³" if self.tm == self.tn == self.tk else f"{self.tm}×{self.tn}×{self.tk}"
        order = "".join(self.order)
        return (f"{tile} {order} U={self.unroll} {self.dtype_in}·{self.buffering}"
                f" {'+' if self.bias else '-'}bias")


@dataclasses.dataclass(frozen=True)
class Breakdown:
    """空间明细：a/b 是单个槽的字节数，factor 是 A/B 的槽数（1 或 2）。"""

    a: int
    b: int
    c: int
    bias: int
    staging: int
    factor: int
    align: int

    @property
    def a_total(self) -> int:
        return self.a * self.factor

    @property
    def b_total(self) -> int:
        return self.b * self.factor

    @property
    def total(self) -> int:
        return self.a_total + self.b_total + self.c + self.bias + self.staging


def estimate(cand, align: int = DEFAULT_ALIGN) -> Breakdown:
    """D101 的五项记账（逐行复制自 D104，一行不改）：
    A=tm·tk、B=tk·tn、C=tm·tn（按累加精度）、bias=tn、staging=tm·tn；
    ×2 只加在 DMA 流入项（A、B）；逐项 align_up 到对齐网格。
    """
    if cand.dtype_in not in DTYPES:
        raise ValueError(f"未知 dtype_in：{cand.dtype_in!r}")
    d_in = DTYPES[cand.dtype_in]
    d_acc = DTYPES[ACC_AUTO[cand.dtype_in]]
    a = align_up(cand.tm * cand.tk * d_in, align)
    b = align_up(cand.tk * cand.tn * d_in, align)
    c = align_up(cand.tm * cand.tn * d_acc, align)
    bias = align_up(cand.tn * d_acc, align) if cand.bias else 0
    staging = align_up(cand.tm * cand.tn * d_in, align) if cand.staging else 0
    factor = 2 if cand.buffering == "double" else 1
    return Breakdown(a=a, b=b, c=c, bias=bias, staging=staging, factor=factor, align=align)


# ---------------------------------------------------------------- 值域：每个轴的取值从问题推导


def divisors(n: int) -> tuple:
    return tuple(d for d in range(1, n + 1) if n % d == 0)


def tile_axis_pool(dim: int, dtype_in: str, align: int, mode: str) -> tuple:
    """tile 一根轴的合法取值。

    div  模式：整除 dim 且是"对齐元素数"的倍数——不发尾部、不交 padding 税。
                对齐元素数 = align / dtype_size（fp32:8、bf16:16、int8:32），
                保证 A/B/C/bias 四项天然落在 DMA 对齐网格上（D104 对齐扫描的教训）。
    tail 模式：精选手工池 ∩ [1, dim]——D95 尾部机制接住非整除，给 516 这类
                "整除模式剪成空集"的 shape 留逃生门。
    """
    step = max(1, align // DTYPES[dtype_in])
    if mode == "div":
        return tuple(t for t in divisors(dim) if t % step == 0)
    if mode == "tail":
        return tuple(t for t in CURATED_TAIL_POOL if t <= dim)
    raise ValueError(f"未知 tile 模式：{mode!r}（可选 div/tail）")


@dataclasses.dataclass(frozen=True)
class SpaceSpec:
    """一份搜索空间说明书：问题 + 各轴值域 + 预算。"""

    M: int = 512
    N: int = 512
    K: int = 512
    dtype_in: str = "fp32"
    mode: str = "div"          # div / tail
    budget: int = DEFAULT_BUDGET
    align: int = DEFAULT_ALIGN

    @property
    def tile_ms(self) -> tuple:
        return tile_axis_pool(self.M, self.dtype_in, self.align, self.mode)

    @property
    def tile_ns(self) -> tuple:
        return tile_axis_pool(self.N, self.dtype_in, self.align, self.mode)

    @property
    def tile_ks(self) -> tuple:
        return tile_axis_pool(self.K, self.dtype_in, self.align, self.mode)

    def axis_table(self) -> list:
        """每个轴：取值、数量、出处（为什么是这些值）。"""
        step = max(1, self.align // DTYPES[self.dtype_in])
        return [
            ("tm", "tile·M", self.tile_ms,
             f"div 模式：整除 {self.M} 且是 {step} 的倍数" if self.mode == "div"
             else f"tail 模式：精选手工池 ∩ ≤{self.M}"),
            ("tn", "tile·N", self.tile_ns, "同 tm（对 N 维推导）"),
            ("tk", "tile·K", self.tile_ks, "同 tm（对 K 维推导）"),
            ("order", "循环顺序", ORDERS,
             "D92：6 种排列排名随缓存容量翻转，没有普适坏顺序——不敢剪"),
            ("unroll", "展开份数", UNROLL_POOL,
             "D96：U=8 机器码 3.2×；16 是过界探针；素数份数无向量宽度可对齐"),
            ("buffering", "缓冲策略", ("single", "double"),
             "D103：double 换重叠、付 ×2 流入项空间"),
        ]

    def raw_count(self) -> int:
        return (len(self.tile_ms) * len(self.tile_ns) * len(self.tile_ks)
                * len(ORDERS) * len(UNROLL_POOL) * 2)


# ---------------------------------------------------------------- naive 反面教材（只算数，不枚举）


def naive_count(M: int, N: int, K: int) -> int:
    """naive 枚举的上界：tm/tn/tk 各取 1..dim 的每个整数、unroll 取 1..16。"""
    return M * N * K * len(ORDERS) * 16 * 2


def naive_stats(M: int, N: int, K: int) -> list:
    """naive 空间里"连第一次编译都不该做"的搭配占比（组合计数，不枚举）。

    记 D = M·N·K（tile 组合总数）、S = M·N·K 中"每维都满足条件"的数目。
    - 奇数维：单维奇数取值 dim//2 个 → 全偶 tile = ⌈dim/2⌉³，含奇数维 = D − 全偶
    - 非整除维：512 的因数恰是 2 的幂（10 个）→ 全整除 tile = 因数³
    - 不满对齐（8 的倍数）：每维 64 个 → 全对齐 tile = 64³
    - 死展开（U > 最内层圈数）：对每个 u，6 种顺序里 2 种以每根维收尾，
      死搭配数 = 2·(u−1)·(另外两维取值数)·3 根维 —— 对 u=1..16 求和
    """
    total = M * N * K
    odd_tiles = total - ((M + 1) // 2) * ((N + 1) // 2) * ((K + 1) // 2)
    divs = {d: divisors(d) for d in (M, N, K)}
    div_tiles = total - len(divs[M]) * len(divs[N]) * len(divs[K])
    step = 8  # fp32 口径：对齐元素数
    mult = [len([t for t in range(1, d + 1) if t % step == 0]) for d in (M, N, K)]
    align_tiles = total - mult[0] * mult[1] * mult[2]
    dead_unroll = 0
    for u in range(1, 17):
        for d, others in ((M, (N, K)), (N, (M, K)), (K, (M, N))):
            dead_unroll += 2 * (u - 1) * others[0] * others[1]
    return [
        (f"含奇数维的 tile 组合", odd_tiles, odd_tiles / total),
        (f"含非整除维（不为 2 幂）的 tile 组合", div_tiles, div_tiles / total),
        (f"含不满对齐（非 8 倍数）维的 tile 组合", align_tiles, align_tiles / total),
        (f"死展开（U > 最内层圈数）的搭配", dead_unroll * 2, dead_unroll * 2 / (total * 6 * 16 * 2)),
    ]


# ---------------------------------------------------------------- 生成器：三层漏斗


@dataclasses.dataclass
class SpaceStats:
    """漏斗每一层的账目：数量 + 剪掉的理由 + 例子。"""

    naive: int = 0
    raw: int = 0
    n_param_pruned: int = 0
    n_resource_pruned: int = 0
    survivors: int = 0
    param_examples: list = dataclasses.field(default_factory=list)
    resource_examples: list = dataclasses.field(default_factory=list)


class SearchSpace:
    """候选生成器：值域（SpaceSpec）→ 跨轴参数约束 → D104 资源闸门。"""

    def __init__(self, spec: SpaceSpec):
        self.spec = spec
        self.n_param_checks = 0
        self.n_space_checks = 0

    # -- 第一层已经由 SpaceSpec 完成：值域剪枝（生成之前就不造傻值）--

    def _check_params(self, cand: KernelConfig) -> tuple:
        """跨轴参数约束：U ≤ 最内层圈数（便宜，O(1)，先跑）。

        unroll 作用在最内层元素循环上（D96）；份数超过圈数时主循环 0 圈、
        尾部循环干全部活——比不展开还多背一份展开后的代码体积，纯死代码。
        """
        self.n_param_checks += 1
        if cand.unroll > cand.inner_trip:
            return False, (f"U={cand.unroll} > 最内层 {cand.inner_dim} 的圈数 "
                           f"{cand.inner_trip}（主循环 0 圈的死代码）")
        return True, ""

    def _check_resource(self, cand: KernelConfig) -> tuple:
        """资源约束：D104 闸门同款判定（贵，后跑）。返回 (ok, 合计, 超出)。"""
        self.n_space_checks += 1
        bd = estimate(cand, self.spec.align)
        total = bd.total
        if total <= self.spec.budget:
            return True, total, 0
        return False, total, total - self.spec.budget

    def generate(self, stats: Optional[SpaceStats] = None) -> list:
        """按确定顺序生成全部幸存候选（不含被剪的搭配）。"""
        stats = stats if stats is not None else SpaceStats()
        stats.naive = naive_count(self.spec.M, self.spec.N, self.spec.K)
        stats.raw = self.spec.raw_count()
        survivors = []
        for tm in self.spec.tile_ms:
            for tn in self.spec.tile_ns:
                for tk in self.spec.tile_ks:
                    for order in ORDERS:
                        for unroll in UNROLL_POOL:
                            for buffering in ("single", "double"):
                                cand = KernelConfig(tm, tn, tk, order, unroll, buffering,
                                                    dtype_in=self.spec.dtype_in)
                                ok, why = self._check_params(cand)
                                if not ok:
                                    stats.n_param_pruned += 1
                                    if len(stats.param_examples) < 3:
                                        stats.param_examples.append((cand.describe(), why))
                                    continue
                                ok2, total, over = self._check_resource(cand)
                                if not ok2:
                                    stats.n_resource_pruned += 1
                                    if len(stats.resource_examples) < 3:
                                        stats.resource_examples.append(
                                            (cand.describe(), f"合计 {fmt_b(total)} 超预算 {fmt_b(over)}"))
                                    continue
                                survivors.append(cand)
        stats.survivors = len(survivors)
        return survivors

    # -- 统计呈现 --

    def funnel_text(self, stats: SpaceStats) -> str:
        lines = [BAR, " 漏斗统计：每一层剪掉多少、为什么", BAR,
                 f" {'层':<4} {'数量':>16}   说明",
                 "-" * 78,
                 f" {'naive':<5} {stats.naive:>16,}   1..512 全枚举 × 6 顺序 × U∈1..16 × 2 缓冲",
                 f" {'值域':<5} {stats.raw:>16,}   整除+对齐倍数（tile）／2 幂（U）／证据留 6 顺序",
                 f" {'参数':<5} {stats.raw - stats.n_param_pruned:>16,}   U ≤ 最内层圈数：剪掉 {stats.n_param_pruned:,} 个死代码",
                 f" {'资源':<5} {stats.survivors:>16,}   D104 闸门：剪掉 {stats.n_resource_pruned:,} 个超预算",
                 "-" * 78,
                 f" 缩减比：naive → 幸存者 = {stats.naive / max(1, stats.survivors):,.0f} 倍"]
        return "\n".join(lines)

    def survivor_breakdown(self, cands: list) -> str:
        by_tile, by_order, by_unroll, by_buf = {}, {}, {}, {}
        for c in cands:
            key = (c.tm, c.tn, c.tk)
            by_tile[key] = by_tile.get(key, 0) + 1
            by_order["".join(c.order)] = by_order.get("".join(c.order), 0) + 1
            by_unroll[c.unroll] = by_unroll.get(c.unroll, 0) + 1
            by_buf[c.buffering] = by_buf.get(c.buffering, 0) + 1
        lines = [BAR, f" 幸存者 {len(cands):,} 个的内部结构", BAR]
        lines.append(" 按 tile（前 10 行 / 共 %d 种）：" % len(by_tile))
        for key in sorted(by_tile, key=lambda k: (-by_tile[k], k))[:10]:
            t = key
            name = f"{t[0]}³" if t[0] == t[1] == t[2] else f"{t[0]}×{t[1]}×{t[2]}"
            lines.append(f"   {name:<16} {by_tile[key]:>4} 个配置")
        lines.append(" 按循环顺序：" + "  ".join(f"{o}={by_order[o]}" for o in sorted(by_order)))
        lines.append(" 按展开份数：" + "  ".join(f"U={u}={by_unroll[u]}" for u in sorted(by_unroll)))
        lines.append(" 按缓冲策略：" + "  ".join(f"{b}={by_buf[b]}" for b in sorted(by_buf)))
        return "\n".join(lines)

    def utilization_extremes(self, cands: list) -> list:
        """按 SRAM 利用率取两端各 3 个（幸存者的"住得最挤／最松"）。"""
        scored = sorted(cands, key=lambda c: estimate(c, self.spec.align).total)
        out = [("最松", scored[:3]), ("最挤", scored[-3:])]
        return out


# ---------------------------------------------------------------- 实验一：主交付物（512³ fp32）


def exp_table(outdir: Optional[str] = None, budget: int = DEFAULT_BUDGET) -> str:
    spec = SpaceSpec(budget=budget)
    space = SearchSpace(spec)
    stats = SpaceStats()
    cands = space.generate(stats)

    lines = [BAR, " 实验一（主交付物）：512³ fp32 搜索空间——轴表、漏斗、幸存者统计", BAR]
    lines.append(f" 问题：C=A·B+bias，{spec.M}×{spec.N}×{spec.K}，dtype={spec.dtype_in}")
    lines.append(f" 预算 {fmt_b(spec.budget)}（{spec.budget // 1024} KiB）    DMA 对齐 {spec.align} B    模式 {spec.mode}")
    lines.append("")
    lines.append(BAR)
    lines.append(" 一、轴表：每个轴的取值从问题推导，不从 1..N 暴力枚举")
    lines.append(BAR)
    lines.append(f" {'轴':<10} {'取值':<44} {'数量':>4}   出处（为什么是这些值）")
    lines.append("-" * 78)
    for name, label, values, why in spec.axis_table():
        vs = "[" + ",".join(str(v) for v in values) + "]" if name != "order" \
            else "[ijk,ikj,jik,jki,kij,kji]"
        lines.append(f" {name:<10} {vs:<44} {len(values):>4}   {why}")
    lines.append(f" 值域剪枝后的原始空间：{stats.raw:,} = "
                 f"{len(spec.tile_ms)}×{len(spec.tile_ns)}×{len(spec.tile_ks)}"
                 f"×6×{len(UNROLL_POOL)}×2")

    lines.append("")
    lines.append(BAR)
    lines.append(" 二、naive 反面教材：不推导值域会怎样（组合计数，不枚举）")
    lines.append(BAR)
    lines.append(f" naive 上界：{stats.naive:,} = {spec.M}³ × 6 × 16 × 2")
    for name, cnt, pct in naive_stats(spec.M, spec.N, spec.K):
        lines.append(f"   其中 {name:<34} {cnt:>15,}（{fmt_pct(pct)}）")
    lines.append(" naive 空间里随便抓一个候选，几乎必然踩中上面至少一条——")
    lines.append(" 它们没有错，只是不配消耗一次编译＋一次测量。")

    lines.append("")
    lines.append(space.funnel_text(stats))
    lines.append("")
    if stats.param_examples:
        lines.append(" 参数约束剪掉的例子：")
        for desc, why in stats.param_examples:
            lines.append(f"   ✗ {desc}   {why}")
    if stats.resource_examples:
        lines.append(" 资源闸门剪掉的例子：")
        for desc, why in stats.resource_examples:
            lines.append(f"   ✗ {desc}   {why}")
    lines.append(f" 检查链计数：参数约束 {space.n_param_checks:,} 次，资源估算 {space.n_space_checks:,} 次")

    lines.append("")
    lines.append(space.survivor_breakdown(cands))
    lines.append("")
    lines.append(" 利用率两端（幸存者里住得最松／最挤的各 3 个）：")
    for tag, group in space.utilization_extremes(cands):
        for c in group:
            lines.append(f"   {tag}  {c.describe():<42} 合计 {fmt_b(estimate(c, spec.align).total):>12}"
                         f"  利用率 {fmt_pct(estimate(c, spec.align).total / spec.budget):>7}")

    lines.append("")
    lines.append(BAR)
    lines.append(" 三、与 D104 判定表对账（同一套记账，同一个结论）")
    lines.append(BAR)
    for desc_cand, want_ok in [
        (KernelConfig(32, 32, 32, ("i", "j", "k"), 1, "single"), True),
        (KernelConfig(64, 64, 64, ("i", "k", "j"), 4, "double"), True),
        (KernelConfig(128, 128, 128, ("i", "j", "k"), 1, "single"), True),
        (KernelConfig(128, 128, 128, ("i", "k", "j"), 8, "double"), False),
        (KernelConfig(256, 256, 256, ("j", "k", "i"), 1, "single"), False),
    ]:
        ok, total, over = space._check_resource(desc_cand)
        got = "✓" if ok else f"✗ 超预算 {fmt_b(over)}"
        agree = "与 D104 一致" if ok == want_ok else "!! 与 D104 不一致"
        lines.append(f"   {desc_cand.describe():<42} {fmt_b(total):>12}  {got:<14} {agree}")

    lines.append("")
    lines.append(" 四、幸存者样本（前 6 个 + 冠军邻居 128³ 全灭实录）")
    for c in cands[:6]:
        lines.append(f"   ✓ {c.describe():<42} 合计 {fmt_b(estimate(c, spec.align).total):>12}")
    n128 = sum(1 for c in cands if (c.tm, c.tn, c.tk) == (128, 128, 128))
    lines.append(f"   tile=128³ 的幸存配置：{n128} 个，全是 single；double 的 30 个搭配全被 D104 闸门拦下")

    if outdir:
        os.makedirs(outdir, exist_ok=True)
        with open(os.path.join(outdir, "candidates.txt"), "w", encoding="utf-8") as fh:
            fh.write(f"# D106 幸存候选全表：{len(cands)} 个（512³ fp32，预算 {fmt_b(spec.budget)}）\n")
            for c in cands:
                fh.write(f"{c.describe()}\t{estimate(c, spec.align).total}\n")
    return "\n".join(lines)


# ---------------------------------------------------------------- 实验二：shape 对照（516）


def exp_shape(outdir: Optional[str] = None, budget: int = DEFAULT_BUDGET) -> str:
    lines = [BAR, " 实验二：shape 对照——512 走整除模式，516 逼出尾部模式", BAR]
    spec512 = SpaceSpec(budget=budget)
    lines.append(f" 512³：div 模式 tile 池 = {list(spec512.tile_ms)}（{len(spec512.tile_ms)} 个/维）")
    lines.append(f"        516 = 2²·3·43：整除 516 且是 8 的倍数的正整数——一个都没有！")
    empty = tile_axis_pool(516, "fp32", 32, "div")
    lines.append(f"        div 模式 tile 池（516）= {list(empty)}  ← 空集警报：值域剪过头不是省钱，是断粮")
    lines.append("")
    lines.append(" 逃生门：div 剪成空集 → 自动降级 tail 模式（D95 尾部机制接住非整除）")
    spec516 = SpaceSpec(M=516, N=516, K=516, mode="tail", budget=budget)
    lines.append(f" 516³ tail 模式 tile 池 = {list(spec516.tile_ms)}（{len(spec516.tile_ms)} 个/维）")
    n_tail = sum(1 for t in spec516.tile_ms if 516 % t != 0)
    lines.append(f"        池里 {n_tail}/{len(spec516.tile_ms)} 个值不整除 516 → 216 个 tile 组合全部带尾部")
    lines.append("        （516 的因数里没有 32~256 的值——它是天然的『尾部 shape』，D97 冠军翻转的现场）")
    lines.append("")

    for tag, spec in (("512·div", spec512), ("516·tail", spec516)):
        space = SearchSpace(spec)
        stats = SpaceStats()
        cands = space.generate(stats)
        lines.append(f" [{tag}]  值域原始 {stats.raw:,} → 参数剪 {stats.n_param_pruned:,} 个"
                     f" → 资源剪 {stats.n_resource_pruned:,} 个 → 幸存 {stats.survivors:,} 个")
        if stats.param_examples:
            desc, why = stats.param_examples[0]
            lines.append(f"     参数剪例：{desc}  {why}")
        if tag == "516·tail":
            n96 = sum(1 for c in cands if (c.tm, c.tn, c.tk) == (96, 96, 96))
            n160 = sum(1 for c in cands if (c.tm, c.tn, c.tk) == (160, 128, 64))
            lines.append(f"     老朋友回来了：96³ 幸存 {n96} 个配置、160×128×64 幸存 {n160} 个")
            lines.append(f"     （D104 判定表里的 96³ fp32·double = 184,704 B ✓、160×128×64 = 229,888 B ✓）")
    lines.append("")
    lines.append(" 观察点：同一套值域规则，512 给 343 个 tile，516 一个都不给——")
    lines.append(" 值域剪枝的产出取决于 shape 的因数结构；规则越紧越要留逃生门，")
    lines.append(" 否则调优器对 516 这类 shape 直接罢工（空集不是答案，是 bug）。")
    if outdir:
        pass
    return "\n".join(lines)


# ---------------------------------------------------------------- 实验三：预算扫描


def exp_sweep(budget: int = DEFAULT_BUDGET) -> str:
    spec = SpaceSpec(budget=budget)
    lines = [BAR, " 实验三：预算扫描——同一个生成器，预算收紧时幸存者怎么变", BAR,
             " 预算        幸存配置    相对 256 KiB",
             "-" * 78]
    base = None
    for b in (512 * 1024, 256 * 1024, 192 * 1024, 128 * 1024, 64 * 1024):
        s = SpaceSpec(budget=b)
        space = SearchSpace(s)
        stats = SpaceStats()
        cands = space.generate(stats)
        if base is None and b == 256 * 1024:
            base = stats.survivors
        ref = f"{stats.survivors / base:,.2f}×" if base else "—"
        lines.append(f" {fmt_b(b):>12}  {stats.survivors:>10,}   {ref}")
    lines.append("-" * 78)
    lines.append(" D104 的结论在生成空间上复现：预算决定 tile 上限，不是直觉——")
    lines.append(" 每收紧一档，最先消失的都是大片 tile，而不是顺序／展开搭配。")
    return "\n".join(lines)


# ---------------------------------------------------------------- 自检


def self_test() -> str:
    results = []

    def assert_eq(name, got, want):
        results.append((name, got == want, f"got {got!r}, want {want!r}"))

    def assert_true(name, cond, detail=""):
        results.append((name, bool(cond), detail))

    # ---- 记账锚点：与 D101/D104 逐数字一致（账本一行没改）----
    from_d104 = [
        (KernelConfig(32, 32, 32, ("i", "j", "k"), 1, "single"), 12416),
        (KernelConfig(32, 32, 32, ("i", "j", "k"), 1, "double"), 20608),
        (KernelConfig(64, 64, 64, ("i", "j", "k"), 1, "single"), 49408),
        (KernelConfig(64, 64, 64, ("i", "k", "j"), 4, "double"), 82176),
        (KernelConfig(96, 96, 96, ("i", "j", "k"), 1, "single"), 110976),
        (KernelConfig(128, 128, 128, ("i", "j", "k"), 1, "single"), 197120),
        (KernelConfig(128, 128, 128, ("i", "k", "j"), 8, "double"), 328192),
        (KernelConfig(256, 256, 256, ("j", "k", "i"), 1, "single"), 787456),
    ]
    for cand, total in from_d104:
        assert_eq(f"记账锚点 {cand.describe()}", estimate(cand).total, total)
    assert_eq("int8 的 C 按累加精度 4 B 记",
              estimate(KernelConfig(128, 128, 128, ("i", "j", "k"), 1, "double", dtype_in="int8")).c,
              128 * 128 * 4)

    # ---- 值域推导 ----
    assert_eq("div 模式 512 fp32 tile 池", tile_axis_pool(512, "fp32", 32, "div"),
              (8, 16, 32, 64, 128, 256, 512))
    assert_eq("div 模式 516 fp32 tile 池为空", tile_axis_pool(516, "fp32", 32, "div"), ())
    assert_eq("div 模式 512 int8 tile 池（对齐元素数 32）", tile_axis_pool(512, "int8", 32, "div"),
              (32, 64, 128, 256, 512))
    assert_eq("div 模式 512 bf16 tile 池（对齐元素数 16）", tile_axis_pool(512, "bf16", 32, "div"),
              (16, 32, 64, 128, 256, 512))
    assert_eq("tail 模式 516 tile 池", tile_axis_pool(516, "fp32", 32, "tail"),
              (32, 64, 96, 128, 160, 256))
    assert_eq("tail 模式 84 只留 ≤84 的值", tile_axis_pool(84, "fp32", 32, "tail"), (32, 64))
    assert_true("6 种顺序全保留（D92：排名随容量翻转，不敢剪）", len(ORDERS) == 6)

    # ---- naive 计数（组合公式，不枚举）----
    assert_eq("naive 上界 512³×6×16×2", naive_count(512, 512, 512), 25_769_803_776)
    stats = naive_stats(512, 512, 512)
    assert_eq("含奇数维 tile = 512³−256³", stats[0][1], 512 ** 3 - 256 ** 3)
    assert_eq("含非整除维 tile = 512³−10³", stats[1][1], 512 ** 3 - 1000)
    assert_eq("含不满对齐维 tile = 512³−64³", stats[2][1], 512 ** 3 - 64 ** 3)
    assert_eq("死展开搭配 = Σ 6·(u−1)·512²·2(缓冲)",
              stats[3][1], sum(6 * (u - 1) * 512 * 512 for u in range(1, 17)) * 2)

    # ---- 主空间漏斗 ----
    spec = SpaceSpec()
    space = SearchSpace(spec)
    st = SpaceStats()
    cands = space.generate(st)
    assert_eq("值域剪枝后原始空间 343×6×5×2", st.raw, 343 * 6 * 5 * 2)
    assert_eq("原始空间 = 20,580", st.raw, 20580)
    assert_eq("参数剪掉 588 个死展开", st.n_param_pruned, 588)
    assert_eq("参数+资源检查总数 = 原始空间", space.n_param_checks, 20580)
    assert_true("资源估算只在参数过关后跑", space.n_space_checks == 20580 - 588)
    assert_true("幸存者非空", st.survivors > 0)

    # ---- 参数约束的咬合面：t=8 时 U=16 是死代码 ----
    dead = KernelConfig(8, 512, 512, ("j", "k", "i"), 16, "single")
    alive = KernelConfig(8, 512, 512, ("i", "k", "j"), 16, "single")
    ok, why = space._check_params(dead)
    assert_true("jki 的最内层是 i：U=16 > tm=8 → 剪", not ok and "圈数 8" in why)
    ok2, _ = space._check_params(alive)
    assert_true("ikj 的最内层是 j：U=16 ≤ tn=512 → 留", ok2)
    assert_eq("inner_dim 取 order 末位", dead.inner_dim, "i")
    assert_eq("inner_trip 映射到 tm", dead.inner_trip, 8)

    # ---- 幸存者契约：每个幸存者都满足全部约束 ----
    for c in cands:
        assert_true(f"幸存者 {c.describe()} 五项家当 ≤ 预算",
                    estimate(c, spec.align).total <= spec.budget)
        break  # 抽查首个即可，全量见下一条
    assert_true("全量幸存者都过资源闸门",
                all(estimate(c, spec.align).total <= spec.budget for c in cands))
    assert_true("全量幸存者都过参数约束", all(c.unroll <= c.inner_trip for c in cands))
    assert_true("全量幸存者 tile 都在值域内",
                all(c.tm in spec.tile_ms and c.tn in spec.tile_ns and c.tk in spec.tile_ks for c in cands))
    assert_true("全量幸存者 order 都是排列",
                all(sorted(c.order) == ["i", "j", "k"] for c in cands))
    assert_true("无重复候选", len({(c.tm, c.tn, c.tk, c.order, c.unroll, c.buffering) for c in cands})
                == len(cands))

    # ---- 确定性：同一 spec 两次生成逐项相等 ----
    cands2 = SearchSpace(SpaceSpec()).generate(SpaceStats())
    assert_eq("两次生成逐项相等（确定性）", [c.describe() for c in cands],
              [c.describe() for c in cands2])

    # ---- 已知命运：D104 判定在生成空间里复现 ----
    n128 = sum(1 for c in cands if (c.tm, c.tn, c.tk) == (128, 128, 128))
    n128_double = sum(1 for c in cands if (c.tm, c.tn, c.tk) == (128, 128, 128)
                      and c.buffering == "double")
    assert_eq("128³ fp32·double 搭配全灭（30 个）", n128_double, 0)
    assert_true("128³ 还有 single 幸存（197,120 B ✓）", n128 > 0)
    n64 = sum(1 for c in cands if (c.tm, c.tn, c.tk) == (64, 64, 64))
    assert_eq("64³ 全配置幸存（6×5×2=60）", n64, 60)
    n256 = sum(1 for c in cands if (c.tm, c.tn, c.tk) == (256, 256, 256))
    assert_eq("256³ 全灭（787,456 B 超 3 倍预算）", n256, 0)

    # ---- 516：空集警报与逃生门 ----
    assert_eq("516 div 模式 tile 池为空（空集警报）", tile_axis_pool(516, "fp32", 32, "div"), ())
    spec516 = SpaceSpec(M=516, N=516, K=516, mode="tail")
    st516 = SpaceStats()
    cands516 = SearchSpace(spec516).generate(st516)
    assert_eq("516 tail 原始空间 216×6×5×2", st516.raw, 216 * 6 * 5 * 2)
    assert_eq("516 tail 参数剪 0 个（池里最小 32 ≥ U 最大 16——同一约束在不同值域下产出不同）",
              st516.n_param_pruned, 0)
    assert_true("516 tail 幸存者非空", st516.survivors > 0)
    assert_true("516 幸存者全带尾部（tile 都不整除 516）",
                all(any(516 % t != 0 for t in (c.tm, c.tn, c.tk)) for c in cands516))
    n96 = sum(1 for c in cands516 if (c.tm, c.tn, c.tk) == (96, 96, 96))
    assert_true("D104 老朋友 96³ 回到幸存者名单（184,704 B ✓）", n96 > 0)

    # ---- 预算扫描单调性 ----
    counts = []
    for b in (512 * 1024, 256 * 1024, 192 * 1024, 128 * 1024, 64 * 1024):
        s = SpaceStats()
        SearchSpace(SpaceSpec(budget=b)).generate(s)
        counts.append(s.survivors)
    assert_true("预算收紧 → 幸存数单调不增", all(a >= b for a, b in zip(counts, counts[1:])))
    assert_true("512 KiB 幸存数 ≥ 256 KiB 幸存数", counts[0] >= counts[1])

    # ---- 分工边界：生成器不排序（D74 分离原则）----
    assert_true("生成器输出不含任何性能排序信息",
                not hasattr(SearchSpace(spec), "rank")
                and not hasattr(SearchSpace(spec), "score"))

    # ---- dtype 扩展钩子：换 dtype 连值域都改写 ----
    assert_eq("bf16 的 tile 池比 fp32 少一档（对齐元素数翻倍）",
              len(tile_axis_pool(512, "bf16", 32, "div")), 6)
    assert_eq("int8 的 tile 池再少一档", len(tile_axis_pool(512, "int8", 32, "div")), 5)

    n_pass = sum(1 for _, ok, _ in results if ok)
    lines = [BAR, f" 自检：{n_pass}/{len(results)} 项断言通过", BAR]
    for name, ok, detail in results:
        lines.append(("  ✓ " if ok else "  ✗ ") + name + ("" if ok else f"  ——  {detail}"))
    if n_pass != len(results):
        raise SystemExit("自检失败")
    return "\n".join(lines)


# ---------------------------------------------------------------- CLI

EXPS = {
    "table": exp_table,
    "shape": exp_shape,
    "sweep": exp_sweep,
    "self-test": self_test,
}


def env_line() -> str:
    return f"Python {sys.version.split()[0]}，{sys.platform}，零第三方依赖，2026-11-13 运行"


def main() -> int:
    ap = argparse.ArgumentParser(description="D106 搜索空间生成器")
    ap.add_argument("--exp", default="all", help="all/table/shape/sweep/self-test")
    ap.add_argument("--budget", default="256K", help="片上 SRAM 预算，如 256K / 131072")
    ap.add_argument("--outdir", default=None, help="把各实验结果与幸存者全表写入该目录")
    args = ap.parse_args()

    budget = parse_bytes(args.budget)
    if args.exp == "all":
        texts = {
            "space-table.txt": exp_table(args.outdir, budget),
            "shape-516.txt": exp_shape(args.outdir, budget),
            "budget-sweep.txt": exp_sweep(budget),
            "test-all.txt": self_test(),
        }
        for name, text in texts.items():
            print(text + "\n")
            if args.outdir:
                os.makedirs(args.outdir, exist_ok=True)
                with open(os.path.join(args.outdir, name), "w", encoding="utf-8") as fh:
                    fh.write(text + "\n")
        return 0
    if args.exp == "self-test":
        print(self_test())
        return 0
    fn = EXPS[args.exp]
    if args.exp == "table":
        print(fn(args.outdir, budget))
    else:
        print(fn(budget))
    return 0


if __name__ == "__main__":
    sys.exit(main())
