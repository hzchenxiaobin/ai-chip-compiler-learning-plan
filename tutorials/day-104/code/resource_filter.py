#!/usr/bin/env python3
"""D104 资源约束过滤器：在代码生成之前，自动拒绝超出片上 SRAM 预算的
Tiling 候选配置，并给出带拒绝码、数字与降级出路的诊断。

设计要点（与 README 一致）：
  1) fail-closed：候选来自搜索空间生成器（D106），什么都可能有——
     参数不认识/不合法 → BAD_PARAM 拒绝，绝不猜默认值（D95 消费门同款）；
     所以 TileCandidate 有意不在构造时校验：候选是数据，设防在判定层。
  2) 检查链有序、短路求值：便宜的参数校验在前，贵的空间估算在后；
     n_param_checks / n_space_checks 计数器把短路顺序变成可观测、可断言。
  3) 只判合法性，不排收益：排序是 D110 Cost Model 的事（D74 分离原则），
     候选生成是 D106 搜索空间的事——过滤器只回答「能不能跑」。
  4) 诊断必须带数字：拒绝码 + 空间明细 + 超出字节数 + 三条降级出路
     （每条出路本身也要重新过同一道过滤器）。

空间记账与 D101 estimator 同一套规则：五项家当（A/B/C/bias/staging）、
×2 只加在 DMA 流入项（A、B）、累加精度不跟输入走（acc=auto 时恒 4 B）、
每项 align_up 到 DMA 对齐网格。
"""

from __future__ import annotations

import argparse
import dataclasses
import os
import sys
from typing import Optional

# ---------------------------------------------------------------- 基础表

DTYPES = {"fp32": 4, "fp16": 2, "bf16": 2, "int8": 1, "int32": 4}
ACC_AUTO = {"int8": "int32", "fp16": "fp32", "bf16": "fp32", "fp32": "fp32"}
DTYPE_DOWN = {"fp32": "bf16", "fp16": "int8", "bf16": "int8", "int32": None}
DEFAULT_ALIGN = 32
DEFAULT_BUDGET = 256 * 1024

# 拒绝码：OK / BAD_PARAM（参数非法）/ SRAM_OVERFLOW（片上空间超预算）
OK = "OK"
BAD_PARAM = "BAD_PARAM"
SRAM_OVERFLOW = "SRAM_OVERFLOW"


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


# ---------------------------------------------------------------- 候选与估算


@dataclasses.dataclass(frozen=True)
class TileCandidate:
    """一个 Tiling 候选：tile 三元组 + dtype + 缓冲策略 + 家当开关。

    有意不做构造期校验：候选是「外部输入」（搜索空间/命令行/测试都可能
    喂进非法值），设防的责任全部在 ResourceFilter——fail-closed 的前提
    是判定层全设防，而不是数据层碰巧干净。
    """

    tm: int
    tn: int
    tk: int
    dtype_in: str = "fp32"
    buffering: str = "double"
    bias: bool = True
    staging: bool = False

    def describe(self) -> str:
        tile = f"{self.tm}³" if self.tm == self.tn == self.tk else f"{self.tm}×{self.tn}×{self.tk}"
        extra = ("+" if self.bias else "-") + "bias"
        if self.staging:
            extra += "+staging"
        return f"{tile} {self.dtype_in}·{self.buffering} {extra}"


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

    def formula(self) -> str:
        x = f"×{self.factor}" if self.factor > 1 else ""
        parts = [f"A {fmt_b(self.a)}{x}", f"B {fmt_b(self.b)}{x}", f"C {fmt_b(self.c)}"]
        if self.bias:
            parts.append(f"bias {fmt_b(self.bias)}")
        if self.staging:
            parts.append(f"staging {fmt_b(self.staging)}")
        return " + ".join(parts) + f" = {fmt_b(self.total)}"


def estimate(cand: TileCandidate, align: int = DEFAULT_ALIGN) -> Breakdown:
    """D101 的五项记账：假定输入已被参数校验放行（库函数信任调用方）。

    直接对非法 dtype 调用本函数会抛 ValueError——这正是「参数校验必须
    先跑」的第一现场，self_test 里有对应断言。
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


# ---------------------------------------------------------------- 判定与诊断


@dataclasses.dataclass
class Suggestion:
    """一条降级出路：本身也是一个候选，必须重新过同一道过滤器。"""

    label: str
    axis: str          # 代价轴：时间 / 空间 / 精度
    note: str
    total: int
    ok: bool


@dataclasses.dataclass
class Verdict:
    """过滤器对单个候选的判定：合法性 + 拒绝码 + 数字 + 出路。"""

    cand: TileCandidate
    ok: bool
    code: str
    message: str = ""
    total: Optional[int] = None
    overflow: int = 0
    utilization: Optional[float] = None
    breakdown: Optional[Breakdown] = None
    failed_check: Optional[str] = None
    suggestions: list = dataclasses.field(default_factory=list)


class ResourceFilter:
    """检查链：参数校验（便宜）→ 空间估算（贵）→ 预算判定。

    将来接入更贵的检查（寄存器压力、并行度下限、合法化后的指令模拟）
    时，只需按「便宜先行」继续往后追加——前面的结论不变。
    """

    def __init__(self, budget: int = DEFAULT_BUDGET, align: int = DEFAULT_ALIGN):
        self.budget = budget
        self.align = align
        # 可观测性：短路顺序可以用断言钉死
        self.n_param_checks = 0
        self.n_space_checks = 0

    def _check_params(self, cand: TileCandidate) -> tuple[bool, str]:
        """检查一：参数校验。O(1)，fail-closed——不认识的输入一律拒绝。"""
        for name in ("tm", "tn", "tk"):
            v = getattr(cand, name)
            if not isinstance(v, int) or isinstance(v, bool) or v <= 0:
                return False, f"tile.{name} = {v!r} 不是正整数"
        if cand.dtype_in not in DTYPES:
            return False, f"未知 dtype_in = {cand.dtype_in!r}（可选 {'/'.join(DTYPES)}）"
        if cand.buffering not in ("single", "double"):
            return False, f"未知缓冲策略 = {cand.buffering!r}（可选 single/double）"
        return True, ""

    def check(self, cand: TileCandidate) -> Verdict:
        """检查二：空间估算 + 预算判定。参数挂了就短路，估算不会跑。"""
        self.n_param_checks += 1
        ok, msg = self._check_params(cand)
        if not ok:
            return Verdict(cand, False, BAD_PARAM, msg, failed_check="params")
        self.n_space_checks += 1
        bd = estimate(cand, self.align)
        total = bd.total
        if total <= self.budget:
            return Verdict(cand, True, OK, total=total, breakdown=bd,
                           utilization=total / self.budget)
        return Verdict(cand, False, SRAM_OVERFLOW,
                       message=f"合计 {fmt_b(total)} 超出预算 {fmt_b(self.budget)} {fmt_b(total - self.budget)}",
                       total=total, overflow=total - self.budget,
                       breakdown=bd, failed_check="space",
                       suggestions=self._fallbacks(cand))

    def _fallbacks(self, cand: TileCandidate) -> list:
        """三条降级出路：每条都重新过同一道过滤器（合法性递归）。"""
        alts = []
        if cand.buffering == "double":
            alts.append((dataclasses.replace(cand, buffering="single"),
                         "时间", "退单缓冲",
                         "丢掉 D103 的计算/搬运重叠，回到轮流值班"))
        if (cand.tm, cand.tn, cand.tk) != (64, 64, 64):
            alts.append((dataclasses.replace(cand, tm=64, tn=64, tk=64),
                         "空间", "缩 tile 到 64³",
                         "片上复用变差 → HBM 流量上升（D101 的 reuse 账）"))
        down = DTYPE_DOWN.get(cand.dtype_in)
        if down:
            alts.append((dataclasses.replace(cand, dtype_in=down),
                         "精度", f"降 dtype 到 {down}",
                         "数值风险交给 D78~81 的误差阈值把关"))
        out = []
        for alt, axis, label, note in alts:
            bd = estimate(alt, self.align)
            out.append(Suggestion(label=label, axis=axis, note=note,
                                  total=bd.total, ok=bd.total <= self.budget))
        return out

    def filter_all(self, cands) -> list:
        return [self.check(c) for c in cands]


# ---------------------------------------------------------------- 决策日志

BAR = "=" * 78


def _verdict_row(idx, v: Verdict, budget: int) -> str:
    if v.ok:
        return (f"{idx:>2}  {v.cand.describe():<28} {fmt_b(v.total):>12}"
                f"  {fmt_pct(v.utilization):>7}   ✓")
    if v.code == BAD_PARAM:
        return f"{idx:>2}  {v.cand.describe():<28} {'—':>12}  {'—':>7}   ✗ {v.code}  {v.message}"
    return (f"{idx:>2}  {v.cand.describe():<28} {fmt_b(v.total):>12}"
            f"  {fmt_pct(v.total / budget):>7}   ✗ {v.code}  超 {fmt_b(v.overflow)}")


def diagnose(v: Verdict, budget: int, align: int) -> str:
    """一份完整拒绝诊断：拒绝码 + 空间明细 + 数字 + 三条出路。"""
    lines = [f"[✗ 拒绝] {v.cand.describe()}", f"  拒绝码   : {v.code}"]
    if v.code == BAD_PARAM:
        lines.append(f"  原因     : {v.message}")
        lines.append("  说明     : fail-closed——不认识的输入一律拒绝，绝不猜默认值")
        return "\n".join(lines)
    lines.append(f"  空间明细 : {v.breakdown.formula()}")
    lines.append(f"  预算     : {fmt_b(budget)}，对齐 {align} B")
    lines.append(f"  超出     : {fmt_b(v.overflow)}（预算的 {fmt_pct(v.overflow / budget)}）")
    if v.suggestions:
        lines.append("  出路（每条都重新过同一道过滤器）:")
        for i, s in enumerate(v.suggestions):
            mark = "✓" if s.ok else "✗"
            lines.append(f"    {'abc'[i]}) {s.label:<10} → {fmt_b(s.total):>10}  {mark}"
                         f"  代价轴={s.axis}（{s.note}）")
    return "\n".join(lines)


def decision_log(verdicts, budget: int, align: int, title: str) -> str:
    lines = [BAR, f" {title}", BAR,
             f" 预算 {fmt_b(budget)}（{budget // 1024} KiB）    DMA 对齐 {align} B",
             "-" * 78,
             " #  候选                        合计        利用率   判定"]
    for i, v in enumerate(verdicts, 1):
        lines.append(_verdict_row(i, v, budget))
    n_ok = sum(1 for v in verdicts if v.ok)
    lines.append("-" * 78)
    lines.append(f" 共 {len(verdicts)} 个候选：{n_ok} 个放行，{len(verdicts) - n_ok} 个拒绝")
    return "\n".join(lines)


# ---------------------------------------------------------------- 实验素材

def main_candidates() -> list:
    """12 个候选：沿用 D97/D101/D103 的那道题（512³ MatMul）与冠军配置。"""
    return [
        TileCandidate(32, 32, 32, "fp32", "single"),
        TileCandidate(32, 32, 32, "fp32", "double"),
        TileCandidate(64, 64, 64, "fp32", "single"),
        TileCandidate(64, 64, 64, "fp32", "double"),
        TileCandidate(96, 96, 96, "fp32", "single"),
        TileCandidate(96, 96, 96, "fp32", "double"),
        TileCandidate(128, 128, 128, "fp32", "single"),
        TileCandidate(128, 128, 128, "fp32", "double"),   # D97 CPU 冠军＝纸面最优
        TileCandidate(128, 128, 128, "bf16", "double"),
        TileCandidate(128, 128, 128, "int8", "double"),
        TileCandidate(160, 128, 64, "fp32", "double"),
        TileCandidate(256, 256, 256, "fp32", "single"),
    ]


def bad_param_candidates() -> list:
    """参数负例：构造不校验，判定层必须全部拦下。"""
    return [
        TileCandidate(0, 128, 128),
        TileCandidate(128, 128, -8),
        TileCandidate(128, 128, 128, dtype_in="fp64"),
        TileCandidate(128, 128, 128, buffering="triple"),
    ]


# ---------------------------------------------------------------- 实验一：主决策日志

def exp_table(budget: int = DEFAULT_BUDGET, align: int = DEFAULT_ALIGN) -> str:
    f = ResourceFilter(budget, align)
    out = []
    out.append(decision_log(f.filter_all(main_candidates()), budget, align,
                            "实验一：12 个 Tiling 候选 × 预算判定（主交付物）"))
    out.append("")
    out.append(BAR)
    out.append(" 参数负例：fail-closed——不认识的输入一律拒绝，绝不猜默认值")
    out.append(BAR)
    verdicts = f.filter_all(bad_param_candidates())
    for i, v in enumerate(verdicts, 1):
        out.append(_verdict_row("p" + str(i), v, budget))
    out.append("")
    out.append(" 拒绝诊断样例（被拒的纸面最优 128³ fp32·double）：")
    out.append("-" * 78)
    champ = ResourceFilter(budget, align).check(TileCandidate(128, 128, 128, "fp32", "double"))
    out.append(diagnose(champ, budget, align))
    out.append("-" * 78)
    out.append(f" 检查链短路可观测：参数校验 {f.n_param_checks} 次，"
                f"空间估算 {f.n_space_checks} 次（4 个非法参数没有走到估算）")
    return "\n".join(out)


# ---------------------------------------------------------------- 实验二：预算扫描

def exp_budget_sweep(align: int = DEFAULT_ALIGN) -> str:
    cands = main_candidates()
    budgets = [512 * 1024, 256 * 1024, 192 * 1024, 128 * 1024, 64 * 1024]
    lines = [BAR, " 实验二：预算扫描——同一个过滤器，预算收紧时幸存者怎么变",
             BAR,
             " 预算        幸存/12  新增阵亡名单",
             "-" * 78]
    prev = set()
    for b in budgets:
        f = ResourceFilter(b, align)
        verdicts = f.filter_all(cands)
        ok_set = {i for i, v in enumerate(verdicts) if v.ok}
        newly_dead = [cands[i].describe() for i in prev - ok_set]
        lines.append(f" {fmt_b(b):>12}  {len(ok_set):>4}      "
                     + ("、".join(newly_dead) if newly_dead else "（无新增）"))
        prev = ok_set
    lines.append("-" * 78)
    lines.append(" 128 KiB 档：int8 128³·double 131,584 B 超 512 B——bias 一票否决（D101 同款）")
    lines.append(" 64 KiB 档 ：64³·double 82,176 B 也出局——预算决定 tile 上限，不是直觉")
    return "\n".join(lines)


# ---------------------------------------------------------------- 实验三：对齐扫描

def exp_align_sweep() -> str:
    lines = [BAR, " 实验三：对齐网格扫描——贴线候选的生死在零头里",
             BAR,
             " 候选                对齐 32 B   对齐 64 B   对齐 128 B",
             "-" * 78]
    odd = TileCandidate(33, 33, 33, "int8", "single")
    pw2 = TileCandidate(64, 64, 64, "fp32", "double")
    for cand in (odd, pw2):
        row = [f" {cand.describe():<18}"]
        for a in (32, 64, 128):
            row.append(f"{fmt_b(estimate(cand, a).total):>11}  ")
        lines.append("".join(row))
    lines.append("-" * 78)
    lines.append(" 把 33³ int8·single 放上『恰好贴线』的预算 6,784 B（= 对齐 32 B 的合计）：")
    for a in (32, 64, 128):
        f = ResourceFilter(6784, a)
        v = f.check(odd)
        tag = "✓ 贴线放行（合计 == 预算）" if v.ok else f"✗ 拒绝，超 {fmt_b(v.overflow)}"
        lines.append(f"   对齐 {a:>3} B → {tag}")
    lines.append(" 2 幂 tile（64³）三项天然落网格：换对齐合计纹丝不动——")
    lines.append(" 奇数 tile 三项同时 padding，贴线时 128 B 就够翻案。")
    return "\n".join(lines)


# ---------------------------------------------------------------- 实验四：拒绝诊断与出路

def exp_fallback(budget: int = DEFAULT_BUDGET, align: int = DEFAULT_ALIGN) -> str:
    lines = [BAR, " 实验四：纸面最优被拒后的三条出路（代价轴各不相同）", BAR]
    f = ResourceFilter(budget, align)
    champ = f.check(TileCandidate(128, 128, 128, "fp32", "double"))
    lines.append(diagnose(champ, budget, align))
    lines.append("")
    lines.append(" 同一个候选在 128 KiB 预算下：出路的出路也会被拒——建议必须现场重算：")
    f128 = ResourceFilter(128 * 1024, align)
    v = f128.check(TileCandidate(128, 128, 128, "bf16", "double"))
    lines.append(f"   {v.cand.describe()} → "
                 + ("✓" if v.ok else f"✗ {v.code} 超 {fmt_b(v.overflow)}"))
    lines.append(f"   （{fmt_b(v.total)} vs 预算 {fmt_b(128 * 1024)}——出路 c) 在这个预算下也要再退）")
    return "\n".join(lines)


# ---------------------------------------------------------------- 自检（合法／非法配置测试）

def self_test() -> str:
    results = []

    def assert_eq(name, got, want):
        results.append((name, got == want, f"got {got!r}, want {want!r}"))

    def assert_true(name, cond, detail=""):
        results.append((name, bool(cond), detail))

    # ---- 记账规则 ----
    assert_eq("align_up(1089,32)", align_up(1089, 32), 1120)
    assert_eq("align_up(512,32) 已对齐不动", align_up(512, 32), 512)
    assert_eq("33³ int8 single @32 == 6,784（D101 数字）",
              estimate(TileCandidate(33, 33, 33, "int8", "single"), 32).total, 6784)
    assert_eq("33³ int8 single @64 == 6,912",
              estimate(TileCandidate(33, 33, 33, "int8", "single"), 64).total, 6912)
    assert_eq("33³ int8 single @128 == 7,040",
              estimate(TileCandidate(33, 33, 33, "int8", "single"), 128).total, 7040)

    # ---- 合法配置的合计（D101/D103 已验证的锚点）----
    for cand, total in [
        (TileCandidate(32, 32, 32, "fp32", "single"), 12416),
        (TileCandidate(32, 32, 32, "fp32", "double"), 20608),
        (TileCandidate(64, 64, 64, "fp32", "single"), 49408),
        (TileCandidate(64, 64, 64, "fp32", "double"), 82176),
        (TileCandidate(96, 96, 96, "fp32", "single"), 110976),
        (TileCandidate(96, 96, 96, "fp32", "double"), 184704),
        (TileCandidate(128, 128, 128, "fp32", "single"), 197120),
        (TileCandidate(128, 128, 128, "fp32", "double"), 328192),
        (TileCandidate(128, 128, 128, "bf16", "double"), 197120),
        (TileCandidate(128, 128, 128, "int8", "double"), 131584),
        (TileCandidate(160, 128, 64, "fp32", "double"), 229888),
        (TileCandidate(256, 256, 256, "fp32", "single"), 787456),
    ]:
        assert_eq(f"合计 {cand.describe()}", estimate(cand).total, total)

    # ---- 累加精度规则：C 不跟输入走 ----
    bd = estimate(TileCandidate(128, 128, 128, "int8", "double"))
    assert_eq("int8 的 C 按 int32(4 B) 记", bd.c, 128 * 128 * 4)
    assert_eq("int8 的 A/B 按 1 B 记", bd.a, 128 * 128)

    # ---- 过滤器主判定 ----
    f = ResourceFilter()
    v_ok = f.check(TileCandidate(64, 64, 64, "fp32", "double"))
    assert_true("64³ fp32·double 放行", v_ok.ok and v_ok.code == OK)
    assert_eq("利用率 82,176/262,144", round(v_ok.utilization, 4), round(82176 / 262144, 4))
    v_bad = f.check(TileCandidate(128, 128, 128, "fp32", "double"))
    assert_true("128³ fp32·double 拒绝", not v_bad.ok and v_bad.code == SRAM_OVERFLOW)
    assert_eq("溢出 66,048 B", v_bad.overflow, 66048)
    assert_eq("溢出占预算 25.2%", round(v_bad.overflow / f.budget, 4), round(66048 / 262144, 4))
    v_huge = f.check(TileCandidate(256, 256, 256, "fp32", "single"))
    assert_true("256³ fp32·single 拒绝", not v_huge.ok and v_huge.overflow == 525312)

    # ---- 贴线：合计 == 预算 → 放行（判定用 ≤）----
    line_cfg = TileCandidate(128, 128, 128, "fp32", "single", bias=False, staging=True)
    assert_eq("贴线候选合计 262,144 == 预算", estimate(line_cfg).total, 262144)
    v_line = ResourceFilter(262144).check(line_cfg)
    assert_true("合计==预算 → ✓ 放行", v_line.ok and v_line.failed_check is None)
    v_line2 = ResourceFilter(262144).check(TileCandidate(128, 128, 128, "fp32", "single", bias=True, staging=True))
    assert_true("加上 512 B bias → ✗ 拒绝", not v_line2.ok and v_line2.overflow == 512)

    # ---- 非法参数：fail-closed，四类全拦 ----
    for cand in bad_param_candidates():
        v = ResourceFilter().check(cand)
        assert_true(f"非法参数被拦：{v.cand.describe()}",
                    not v.ok and v.code == BAD_PARAM and v.failed_check == "params")

    # ---- 短路可观测：非法参数不触发空间估算 ----
    f2 = ResourceFilter()
    f2.filter_all(bad_param_candidates())
    assert_eq("参数校验跑了 4 次", f2.n_param_checks, 4)
    assert_eq("空间估算 0 次（短路）", f2.n_space_checks, 0)
    f2.check(TileCandidate(64, 64, 64))
    assert_eq("合法候选补跑 1 次估算", f2.n_space_checks, 1)

    # ---- 直接调用 estimate 的非法 dtype 抛异常（参数校验必须先行）----
    try:
        estimate(TileCandidate(8, 8, 8, dtype_in="fp64"))
        assert_true("estimate 拒绝未知 dtype", False, "没有抛异常")
    except ValueError:
        assert_true("estimate 拒绝未知 dtype（抛 ValueError）", True)

    # ---- 诊断质量：出路必须带数字且重新过闸 ----
    s = v_bad.suggestions
    assert_eq("三条出路", len(s), 3)
    assert_eq("出路合计（单缓冲/64³/bf16）", [x.total for x in s], [197120, 82176, 197120])
    assert_true("三条出路全部住得下", all(x.ok for x in s))
    assert_eq("代价轴", [x.axis for x in s], ["时间", "空间", "精度"])
    diag = diagnose(v_bad, 262144, 32)
    for needle in ("SRAM_OVERFLOW", "328,192", "66,048", "197,120 B", "82,176 B"):
        assert_true(f"诊断包含 {needle}", needle in diag)

    # ---- 预算扫描的幸存数（fail-closed 的可观测后果）----
    want_survivors = {512 * 1024: 11, 256 * 1024: 10, 192 * 1024: 7, 128 * 1024: 5, 64 * 1024: 3}
    for b, want in want_survivors.items():
        n = sum(1 for v in ResourceFilter(b).filter_all(main_candidates()) if v.ok)
        assert_eq(f"预算 {b//1024} KiB 幸存 {want} 个", n, want)

    # ---- bias 一票否决：128 KiB 下 int8 128³ ----
    v_int8 = ResourceFilter(128 * 1024).check(TileCandidate(128, 128, 128, "int8", "double"))
    assert_true("128 KiB 下 int8 128³ 被拒", not v_int8.ok and v_int8.overflow == 512)

    # ---- 对齐翻案：贴线候选 33³ int8 @ 预算 6,784 ----
    assert_true("对齐 32 → ✓ 贴线", ResourceFilter(6784, 32).check(TileCandidate(33, 33, 33, "int8", "single")).ok)
    v64 = ResourceFilter(6784, 64).check(TileCandidate(33, 33, 33, "int8", "single"))
    assert_true("对齐 64 → ✗ 超 128 B", not v64.ok and v64.overflow == 128)
    v128 = ResourceFilter(6784, 128).check(TileCandidate(33, 33, 33, "int8", "single"))
    assert_true("对齐 128 → ✗ 超 256 B", not v128.ok and v128.overflow == 256)

    # ---- 2 幂 tile 对对齐不敏感 ----
    assert_eq("64³ double @32", estimate(TileCandidate(64, 64, 64, "fp32", "double"), 32).total, 82176)
    assert_eq("64³ double @128", estimate(TileCandidate(64, 64, 64, "fp32", "double"), 128).total, 82176)

    # ---- 决策日志行格式 ----
    log = decision_log(ResourceFilter().filter_all(main_candidates()[:1]), 262144, 32, "t")
    assert_true("放行行有 ✓", "✓" in log and "12,416 B" in log)

    # ---- 合法性与收益性分离：过滤器不排序 ----
    f3 = ResourceFilter()
    small = f3.check(TileCandidate(32, 32, 32, "fp32", "double"))
    big_ok = f3.check(TileCandidate(96, 96, 96, "fp32", "double"))
    assert_true("合法候选一律放行，不比较谁更快",
                small.ok and big_ok.ok and small.total < big_ok.total)

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
    "sweep": exp_budget_sweep,
    "align": exp_align_sweep,
    "fallback": exp_fallback,
    "self-test": self_test,
}


def main() -> int:
    ap = argparse.ArgumentParser(description="D104 资源约束过滤器")
    ap.add_argument("--exp", default="all", help="all/table/sweep/align/fallback/self-test")
    ap.add_argument("--budget", default="256K", help="片上 SRAM 预算，如 256K / 131072")
    ap.add_argument("--align", type=int, default=DEFAULT_ALIGN, help="DMA 对齐网格（B）")
    ap.add_argument("--outdir", default=None, help="把各实验结果写入该目录")
    args = ap.parse_args()

    budget = parse_bytes(args.budget)
    if args.exp == "all":
        texts = {
            "filter-table.txt": exp_table(budget, args.align),
            "budget-sweep.txt": exp_budget_sweep(args.align),
            "align-sweep.txt": exp_align_sweep(),
            "fallback.txt": exp_fallback(budget, args.align),
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
    print(EXPS[args.exp](budget, args.align))
    return 0


if __name__ == "__main__":
    sys.exit(main())
