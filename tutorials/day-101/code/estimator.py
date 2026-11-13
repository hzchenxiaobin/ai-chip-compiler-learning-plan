#!/usr/bin/env python3
"""D101 片上空间估算：根据 Tile、Dtype 与缓冲策略，估算一个 Tiled MatMul
需要常驻片上 SRAM 的字节数，并对照预算给出「住得下 / 住不下」判定。

家当清单（五项，与 README 一致）：
  A tile（输入激活） Tm × Tk × dtype_in   —— DMA 流入 → 双缓冲时 ×2
  B tile（权重）     Tk × Tn × dtype_in   —— DMA 流入 → 双缓冲时 ×2
  C tile（输出累加） Tm × Tn × dtype_acc  —— 常驻整个 tile 生命周期 → 恒 ×1
  bias 切片          Tn   × dtype_acc     —— 常驻 → ×1
  staging（可选）    Tm × Tn × dtype_in   —— 重排/重量化输出的临时 tile

两条记账规则：
  1) 累加精度（D80/D81：低精度输入、高精度累加）——acc="auto" 时
     int8 → int32、fp16/bf16/fp32 → fp32；从空间看都是 4 B；
  2) 每项 align_up 到 DMA 对齐（D100 伏笔：尺寸要凑对齐倍数）。

只做空间账，不做时间账：双缓冲的重叠收益、DMA 时间线是 D102/D103 的内容。
"""

from __future__ import annotations

import argparse
import dataclasses
import sys
from typing import Optional

# ---------------------------------------------------------------- 基础表

DTYPES = {"fp32": 4, "fp16": 2, "bf16": 2, "int8": 1, "int32": 4}
ACC_AUTO = {"int8": "int32", "fp16": "fp32", "bf16": "fp32", "fp32": "fp32"}
DEFAULT_ALIGN = 32


def align_up(n: int, a: int) -> int:
    """把字节数 n 向上取整到对齐网格 a（a 为 2 的幂时等价于位运算）。"""
    if a <= 0:
        raise ValueError(f"对齐必须为正数，得到 {a}")
    return (n + a - 1) // a * a


def fmt_b(n: int) -> str:
    return f"{n:,} B"


def fmt_kb(n: int) -> str:
    return f"{n / 1024:.1f} KB"


def parse_bytes(text: str) -> int:
    """接受 256K / 256KB / 262144 / 1M 等写法（K、M 均按 1024 进制）。"""
    t = text.strip().upper().replace("IB", "")
    if t.endswith("K"):
        return int(float(t[:-1]) * 1024)
    if t.endswith("M"):
        return int(float(t[:-1]) * 1024 * 1024)
    return int(t)


# ---------------------------------------------------------------- 模型


@dataclasses.dataclass(frozen=True)
class TileConfig:
    """一个 Tiled MatMul 配置的形状与精度部分。

    tm/tn/tk 即 D93~D95 的 tile 三元组；dtype_in 是 A/B 元素精度；
    acc 是累加器精度（"auto" 按 D80 规则映射）；bias/staging 对应
    最终项目算子 MatMul+Bias+ReLU 的家当（ReLU 逐元素原地，不占新空间）。
    """

    tm: int
    tn: int
    tk: int
    dtype_in: str = "fp32"
    acc: str = "auto"
    bias: bool = True
    staging: bool = False

    def __post_init__(self):
        for name in ("tm", "tn", "tk"):
            v = getattr(self, name)
            if not isinstance(v, int) or isinstance(v, bool) or v <= 0:
                raise ValueError(f"tile.{name} 必须是正整数，得到 {v!r}")
        if self.dtype_in not in DTYPES:
            raise ValueError(f"未知 dtype_in：{self.dtype_in}（可选 {'/'.join(DTYPES)}）")
        if self.acc != "auto" and self.acc not in DTYPES:
            raise ValueError(f"未知 acc：{self.acc}（可选 auto 或 {'/'.join(DTYPES)}）")

    def acc_dtype(self) -> str:
        return self.acc if self.acc != "auto" else ACC_AUTO[self.dtype_in]


@dataclasses.dataclass(frozen=True)
class Breakdown:
    """估算明细：a/b 是单个槽的字节数，factor 是 A/B 的槽数（1 或 2）。"""

    a: int          # A tile 单槽（Tm×Tk×dtype_in，已对齐）
    b: int          # B tile 单槽（Tk×Tn×dtype_in，已对齐）
    c: int          # C tile（Tm×Tn×acc，常驻 ×1，已对齐）
    bias: int       # bias 切片（Tn×acc，常驻 ×1，已对齐；关闭时 0）
    staging: int     # 临时 tile（Tm×Tn×dtype_in，已对齐；关闭时 0）
    factor: int      # 1 = 单缓冲，2 = 双缓冲（只乘 A+B 两个流入项）
    cfg: TileConfig

    @property
    def a_total(self) -> int:
        return self.a * self.factor

    @property
    def b_total(self) -> int:
        return self.b * self.factor

    @property
    def total(self) -> int:
        return self.a_total + self.b_total + self.c + self.bias + self.staging


def estimate(cfg: TileConfig, buffering: str = "double", align: int = DEFAULT_ALIGN) -> Breakdown:
    """空间估算主函数：Tile + Dtype + 缓冲策略 → 片上字节明细。"""
    if buffering not in ("single", "double"):
        raise ValueError(f"未知缓冲策略：{buffering}（可选 single/double）")
    d_in = DTYPES[cfg.dtype_in]
    d_acc = DTYPES[cfg.acc_dtype()]
    a = align_up(cfg.tm * cfg.tk * d_in, align)
    b = align_up(cfg.tk * cfg.tn * d_in, align)
    c = align_up(cfg.tm * cfg.tn * d_acc, align)
    bias = align_up(cfg.tn * d_acc, align) if cfg.bias else 0
    staging = align_up(cfg.tm * cfg.tn * d_in, align) if cfg.staging else 0
    factor = 2 if buffering == "double" else 1
    return Breakdown(a=a, b=b, c=c, bias=bias, staging=staging, factor=factor, cfg=cfg)


def check_budget(total: int, budget: int) -> tuple[bool, int]:
    """返回 (住得下?, 溢出字节数)。溢出为 0 表示恰好贴线住下。"""
    ok = total <= budget
    return ok, total - budget


# ---------------------------------------------------------------- 报告


def report_config(cfg: TileConfig, buffering: str, budget: int,
                  align: int = DEFAULT_ALIGN, title: str = "") -> str:
    bd = estimate(cfg, buffering, align)
    lines = []
    bar = "=" * 72
    head = title or "片上空间估算"
    lines.append(bar)
    lines.append(f"{head}：tile={cfg.tm}×{cfg.tn}×{cfg.tk}  dtype={cfg.dtype_in}"
                 f"  acc={cfg.acc_dtype()}{'' if cfg.acc == 'auto' else '（显式）'}"
                 f"  缓冲={buffering}  对齐={align} B")
    lines.append(f"预算：{fmt_b(budget)}（{fmt_kb(budget)}）")
    lines.append(bar)
    lines.append("-- 家当清单（五项逐项记账）--")
    mul = "×2 双缓冲" if bd.factor == 2 else "×1 单缓冲"
    lines.append(f"A tile（输入激活）  Tm×Tk = {cfg.tm}×{cfg.tk} × {DTYPES[cfg.dtype_in]} B"
                 f"   {fmt_b(bd.a):>12}  {mul}  = {fmt_b(bd.a_total)}")
    lines.append(f"B tile（权重）      Tk×Tn = {cfg.tk}×{cfg.tn} × {DTYPES[cfg.dtype_in]} B"
                 f"   {fmt_b(bd.b):>12}  {mul}  = {fmt_b(bd.b_total)}")
    lines.append(f"C tile（输出累加）  Tm×Tn = {cfg.tm}×{cfg.tn} × {DTYPES[cfg.acc_dtype()]} B"
                 f"   {fmt_b(bd.c):>12}  ×1 常驻     = {fmt_b(bd.c)}")
    if cfg.bias:
        lines.append(f"bias 切片           Tn = {cfg.tn} × {DTYPES[cfg.acc_dtype()]} B"
                     f"             {fmt_b(bd.bias):>12}  ×1 常驻     = {fmt_b(bd.bias)}")
    else:
        lines.append("bias 切片           关闭                0 B")
    if cfg.staging:
        lines.append(f"staging（重排）     Tm×Tn = {cfg.tm}×{cfg.tn} × {DTYPES[cfg.dtype_in]} B"
                     f"   {fmt_b(bd.staging):>12}  ×1 常驻     = {fmt_b(bd.staging)}")
    else:
        lines.append("staging（重排）     关闭                0 B")
    lines.append(" " * 46 + "-" * 24)
    lines.append(f"{'合计':>40}  {fmt_b(bd.total)}（{fmt_kb(bd.total)}）")
    lines.append("")
    lines.append("-- 预算判定 --")
    ok, over = check_budget(bd.total, budget)
    util = bd.total / budget * 100
    if ok:
        lines.append(f"需求 {fmt_b(bd.total)} ≤ 预算 {fmt_b(budget)}：✓ 住得下"
                     f"（利用率 {util:.1f}%）")
    else:
        lines.append(f"需求 {fmt_b(bd.total)} > 预算 {fmt_b(budget)}：✗ 住不下，"
                     f"溢出 {fmt_b(over)}（{fmt_kb(over)}）")
        bd1 = estimate(cfg, "single", align)
        if bd1.total <= budget:
            lines.append(f"  降级参考：single 缓冲需 {fmt_b(bd1.total)} ✓"
                         "（放弃计算/搬运重叠，代价见 D103）")
        lines.append("  旋钮参考：降 tile / 换 dtype / 关 staging —— 见 --table 与 --budget-sweep")
    return "\n".join(lines)


def table(tiles, dtypes, budget: int, align: int = DEFAULT_ALIGN) -> str:
    """计划点名的交付物：不同 Tile 的空间表。"""
    lines = []
    lines.append("-- 空间表：Tile × Dtype × 缓冲策略（acc=auto，bias=on，"
                 f"对齐 {align} B；预算 {fmt_b(budget)}，KB 均为 1024 进制）--")
    lines.append(f"{'Tile':<14}{'dtype':<7}{'单缓冲':>14}{'双缓冲':>14}"
                 f"{'利用率(双)':>12}{'256 KB 预算':>14}")
    for (tm, tn, tk) in tiles:
        label = f"{tm}×{tn}×{tk}"
        for dt in dtypes:
            cfg = TileConfig(tm, tn, tk, dtype_in=dt)
            s = estimate(cfg, "single", align).total
            d = estimate(cfg, "double", align).total
            ok, _ = check_budget(d, budget)
            mark = "✓" if ok else "✗ 溢出"
            lines.append(f"{label:<14}{dt:<7}{fmt_b(s):>14}{fmt_b(d):>14}"
                         f"{d / budget * 100:>11.1f}%{mark:>15}")
    lines.append("")
    lines.append("读法：唯一被拒的是 fp32·128³ 双缓冲（D97 的 CPU 冠军配置）；")
    lines.append("      规律——dtype 每降一档（4→2→1 B），双缓冲合计恰好＝上一档的单缓冲")
    lines.append("      （A+B 减半、×2 找补回来，C 与 bias 跟着 acc 走、纹丝不动）。")
    return "\n".join(lines)


def dtype_sweep(tile=(128, 128, 128), buffering="double",
                budget: int = 256 * 1024, align: int = DEFAULT_ALIGN) -> str:
    """固定 Tile 换 dtype：看清「输入精度只影响 A+B，累加精度独占 C」。"""
    tm, tn, tk = tile
    lines = [f"-- Dtype 扫描：tile={tm}×{tn}×{tk}，缓冲={buffering}，预算 {fmt_b(budget)} --"]
    lines.append(f"{'dtype':<7}{'A 槽':>12}{'B 槽':>12}{'C（acc）':>16}{'bias':>10}"
                 f"{'合计':>14}{'acc':>8}{'预算':>10}")
    for dt in DTYPES:
        if dt == "int32":
            continue
        cfg = TileConfig(tm, tn, tk, dtype_in=dt)
        bd = estimate(cfg, buffering, align)
        acc = cfg.acc_dtype()
        ok, _ = check_budget(bd.total, budget)
        lines.append(f"{dt:<7}{fmt_b(bd.a):>12}{fmt_b(bd.b):>12}"
                     f"{fmt_b(bd.c):>16}{fmt_b(bd.bias):>10}{fmt_b(bd.total):>14}"
                     f"{acc:>8}{'✓' if ok else '✗':>10}")
    lines.append("")
    lines.append("注意 C 列对所有 dtype 都是 65,536 B：auto 规则下累加器恒为 4 B——")
    lines.append("int8 省下的只有 A+B 两项（int8 的双缓冲合计 = fp16 的单缓冲）。")
    return "\n".join(lines)


def budget_sweep(align: int = DEFAULT_ALIGN) -> str:
    """给定预算，最大的立方 Tile 是多少？与 2 幂网格对比浪费了多少。"""
    budgets = [64, 128, 256, 512, 1024]
    lines = [f"-- 预算扫描：双缓冲 + acc=auto + bias=on，找最大立方 Tile（对齐 {align} B）--"]
    lines.append(f"{'预算':>10}{'dtype':>8}{'最大立方t':>10}{'t 时的需求':>14}"
                 f"{'利用率':>9}{'2幂网格t':>10}{'网格利用率':>11}")
    for kb_val in budgets:
        budget = kb_val * 1024
        for dt in ("fp32", "int8"):
            t_best, total_best = 0, 0
            for t in range(1, 1025):
                cfg = TileConfig(t, t, t, dtype_in=dt)
                tot = estimate(cfg, "double", align).total
                if tot <= budget:
                    t_best, total_best = t, tot
            t_pow = 1 << (t_best.bit_length() - 1)  # ≤ t_best 的最大 2 幂
            tot_pow = estimate(TileConfig(t_pow, t_pow, t_pow, dtype_in=dt), "double", align).total
            lines.append(f"{kb_val} KB{dt:>8}{t_best:>10}{fmt_b(total_best):>14}"
                         f"{total_best / budget * 100:>8.1f}%{t_pow:>10}"
                         f"{tot_pow / budget * 100:>10.1f}%")
    lines.append("")
    # 用刚算出的真实数字写注脚，避免手抄漂移
    t114 = estimate(TileConfig(114, 114, 114, dtype_in="fp32"), "double").total
    t64 = estimate(TileConfig(64, 64, 64, dtype_in="fp32"), "double").total
    lines.append(f"两个看点：① 2 幂网格在 256 KB 上只敢住 64³（{t64 / (256 * 1024) * 100:.1f}%），"
                 f"最优 114³ 用到 {t114 / (256 * 1024) * 100:.1f}%——")
    lines.append("  非 2 幂 Tile（96/112/114）是真实编译器的常规选择（尾部代价另见 D95）；")
    lines.append("② int8 在 128 KB 上 t=128 差 bias 的 512 B 被挤出去，最大只能 127³——")
    lines.append("  小缓冲在贴线时不是零头，是决定性的。")
    return "\n".join(lines)


def reuse(shape=(512, 512, 512), dtype="fp32",
          budget: int = 256 * 1024, align: int = DEFAULT_ALIGN) -> str:
    """为什么想住「大 Tile」：C 常驻策略下（k0 在最内层），HBM 流量 ∝ 1/Tm + 1/Tn。"""
    m, k, n = shape
    d = DTYPES[dtype]
    flops = 2 * m * n * k
    c_write = m * n * d
    lines = [f"-- 大 Tile 的动机：{m}×{k}×{n} {dtype} 的 HBM 流量 vs Tile（C 常驻，k0 最内）--"]
    lines.append(f"{'Tile':<14}{'A+B 流量':>15}{'C 写流量':>13}{'HBM 总流量':>15}"
                 f"{'算术强度':>11}{'片上(双缓冲)':>15}{'256 KB':>8}")
    # 未切块：整矩阵当一块
    ab0 = (m * k + k * n) * d
    lines.append(f"{'不切块(整矩阵)':<14}{fmt_b(ab0):>15}{fmt_b(c_write):>13}"
                 f"{fmt_b(ab0 + c_write):>15}{flops / (ab0 + c_write):>10.1f}f"
                 f"{'—':>15}{'—':>8}")
    for t in (128, 64, 32):
        cfg = TileConfig(t, t, t, dtype_in=dtype)
        ab = m * n * k * d * (1 / t + 1 / t)
        tot = estimate(cfg, "double", align).total
        ok, _ = check_budget(tot, budget)
        lines.append(f"{t}³{'':<11}{fmt_b(int(ab)):>15}{fmt_b(c_write):>13}"
                     f"{fmt_b(int(ab) + c_write):>15}{flops / (ab + c_write):>10.1f}f"
                     f"{fmt_b(tot):>15}{'✓' if ok else '✗':>8}")
    lines.append("")
    lines.append("读法：Tile 每翻一倍，A+B 流量减半（1/t + 1/t），算术强度翻倍；")
    lines.append("     但片上空间按 t² 涨——SRAM 容量就是「再省流量」的硬上限。")
    lines.append("     注：这是 C 常驻（k0 最内层）的账；D94 的 k0 最外层形态对应 C 流出，")
    lines.append("     流量更高。顺序 × 搬运的相互作用是 D102 的主场。")
    return "\n".join(lines)


def error_demos(align: int = DEFAULT_ALIGN) -> str:
    """三个真实错误：现象 → 估算对照 → 结论。数字全部由 estimate() 现算。"""
    lines = []
    lines.append("-- 错误一：用输入 dtype 记 C 的账（忘了累加精度）--")
    budget = 256 * 1024
    right = estimate(TileConfig(224, 224, 224, dtype_in="int8"), "double", align)
    wrong_cfg = TileConfig(224, 224, 224, dtype_in="int8", acc="int8")
    wrong = estimate(wrong_cfg, "double", align)
    lines.append(f"配置：tile=224³，int8，双缓冲，预算 {fmt_b(budget)}")
    lines.append(f"  正确（acc=int32，D80 规则）：C = {fmt_b(right.c)}，合计 {fmt_b(right.total)}"
                 f"  → {'✗ 住不下' if right.total > budget else '✓'}")
    lines.append(f"  错误（acc=int8）           ：C = {fmt_b(wrong.c)}，合计 {fmt_b(wrong.total)}"
                 f"  → {'✗ 住不下' if wrong.total > budget else '✓ 住得下（假象）'}")
    lines.append("  现象：编译期判定「住得下」，生成代码后片上溢出/真机跑挂。")
    lines.append("  修复：acc 默认 auto——int8 输入按 4 B 累加器记 C 的账。\n")

    lines.append("-- 错误二：把 ×2 抄给所有缓冲（C 也双缓冲）--")
    cfg = TileConfig(128, 128, 128, dtype_in="fp16")
    right = estimate(cfg, "double", align)
    wrong_total = 2 * (right.a + right.b + right.c) + right.bias
    lines.append(f"配置：tile=128³，fp16，双缓冲，预算 {fmt_b(budget)}")
    lines.append(f"  正确：×2 只给 A+B     → {fmt_b(right.total)}   ✓ 住得下")
    ok, over = check_budget(wrong_total, budget)
    lines.append(f"  错误：×2(A+B+C)      → {fmt_b(wrong_total)}   "
                 f"{'✗ 被拒' if not ok else '✓'}（溢出 {fmt_b(over)}，恰好是 bias）")
    lines.append("  现象：不会跑挂，但搜索空间里合法配置被误杀，auto-tuner 只能选次优。")
    lines.append("  修复：C 是计算目的地、常驻整个 tile 生命周期，×2 属于「输出乒乓」，")
    lines.append("  是另一个显式特性（D103+），绝不许默认套用。\n")

    lines.append("-- 错误三：小缓冲当零头扔掉（bias / 对齐 padding）--")
    budget192 = 192 * 1024
    cfg = TileConfig(128, 128, 128, dtype_in="fp32")
    bd = estimate(cfg, "single", align)
    no_bias = bd.total - bd.bias
    lines.append(f"配置：tile=128³，fp32，单缓冲，预算 {fmt_b(budget192)}（= A+B+C 的 3×65,536）")
    lines.append(f"  正确：A+B+C+bias = {fmt_b(bd.total)} → "
                 f"{'✗ 溢出 ' + fmt_b(bd.total - budget192) if bd.total > budget192 else '✓'}"
                 f"（A+B+C 恰好铺满预算，bias 的 {fmt_b(bd.bias)} 是最后一根稻草）")
    lines.append(f"  错误：忽略 bias    = {fmt_b(no_bias)} → "
                 f"{'✗ 同样被拒' if no_bias > budget192 else '✓「恰好住下」（假象）'}")
    odd = TileConfig(33, 33, 33, dtype_in="int8")
    bd_odd = estimate(odd, "single", align)
    raw = 33 * 33 * 1 * 2 + 33 * 33 * 4 + 33 * 4
    lines.append(f"  对齐同理：tile=33³ int8 单缓冲，未对齐 {fmt_b(raw)} → "
                 f"对齐后 {fmt_b(bd_odd.total)}（padding {fmt_b(bd_odd.total - raw)}）；")
    lines.append("  奇数 Tile 时 padding 是三项同时发生的。")
    lines.append("  修复：五项全记账、每项 align_up，预算判定用 ≤ 而不是「约等于」。")
    return "\n".join(lines)


# ---------------------------------------------------------------- 图表


def chart_svg(tiles, dtypes, budget: int, path: str,
              align: int = DEFAULT_ALIGN) -> str:
    """程序绘制：双缓冲合计 vs 预算线的横向条形图（干净矢量风，非手绘）。"""
    w, h = 980, 560
    left, right = 250, 900
    top, bottom = 96, 500
    rows = [(t, dt) for t in tiles for dt in dtypes]
    n = len(rows)
    max_bytes = max(estimate(TileConfig(*t, dtype_in=dt), "double", align).total
                    for t, dt in rows)
    max_bytes = max(max_bytes, budget) * 1.08
    scale = (right - left) / max_bytes
    colors = {"fp32": "#7FA8D9", "fp16": "#E8A87C", "bf16": "#E8C48C", "int8": "#93C6A0"}

    def x(v):
        return left + v * scale

    out = []
    out.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
               'font-family="Helvetica,Arial,sans-serif">')
    out.append(f'<rect x="0" y="0" width="{w}" height="{h}" fill="#FFFFFF"/>')
    out.append(f'<text x="{w / 2}" y="30" text-anchor="middle" font-size="17" '
               f'font-weight="bold" fill="#333">不同 Tile 的片上空间（双缓冲）vs '
               f'{budget // 1024} KB 预算</text>')
    out.append(f'<text x="{w / 2}" y="50" text-anchor="middle" font-size="12" '
               f'fill="#777">acc=auto，bias=on，对齐 {align} B；条内白色刻度 = 单缓冲合计；'
               f'由 estimator.py --chart 生成</text>')
    # 预算线
    bx = x(budget)
    out.append(f'<line x1="{bx:.1f}" y1="{top - 18}" x2="{bx:.1f}" y2="{bottom}" '
               f'stroke="#C0392B" stroke-width="2" stroke-dasharray="7 5"/>')
    out.append(f'<text x="{bx:.1f}" y="{top - 26}" text-anchor="middle" font-size="12" '
               f'fill="#C0392B">预算 {budget // 1024} KB = {budget:,} B</text>')
    row_h = (bottom - top) / n
    for i, (t, dt) in enumerate(rows):
        cfg = TileConfig(*t, dtype_in=dt)
        d = estimate(cfg, "double", align).total
        s = estimate(cfg, "single", align).total
        y = top + i * row_h
        bar_h = row_h * 0.52
        over = d > budget
        color = "#D98484" if over else colors[dt]
        out.append(f'<text x="{left - 10}" y="{y + row_h / 2 + 4}" text-anchor="end" '
                   f'font-size="12" fill="#333">{t[0]}×{t[1]}×{t[2]} · {dt}</text>')
        out.append(f'<rect x="{left}" y="{y + (row_h - bar_h) / 2:.1f}" width="{x(d) - left:.1f}" '
                   f'height="{bar_h:.1f}" fill="{color}" fill-opacity="0.85"/>')
        out.append(f'<line x1="{x(s):.1f}" y1="{y + (row_h - bar_h) / 2:.1f}" '
                   f'x2="{x(s):.1f}" y2="{y + (row_h - bar_h) / 2 + bar_h:.1f}" '
                   f'stroke="#FFFFFF" stroke-width="3"/>')
        label = f'{d:,} B'
        lx = x(d) + (8 if not over else -8)
        anchor = "start" if not over else "end"
        lcolor = "#C0392B" if over else "#555"
        out.append(f'<text x="{lx:.1f}" y="{y + row_h / 2 + 4}" text-anchor="{anchor}" '
                   f'font-size="12" font-weight="{"bold" if over else "normal"}" '
                   f'fill="{lcolor}">{label}{"（✗ 溢出）" if over else ""}</text>')
    out.append('</svg>')
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    return f"已写入 {path}（{n} 组配置）"


# ---------------------------------------------------------------- 自检


def run_tests() -> list[str]:
    results = []
    fails = 0

    def check(name, got, want):
        nonlocal fails
        ok = got == want
        fails += 0 if ok else 1
        results.append(f"[{'PASS' if ok else 'FAIL'}] {name}：{got}"
                       f"{'' if ok else f'（期望 {want}）'}")

    # E1 已知账单：32³/64³/128³ fp32（bias = Tn×4 也计入）
    check("E1a fp32 32³ 单缓冲", estimate(TileConfig(32, 32, 32), "single").total, 12416)
    check("E1b fp32 32³ 双缓冲", estimate(TileConfig(32, 32, 32), "double").total, 20608)
    check("E1c fp32 64³ 双缓冲", estimate(TileConfig(64, 64, 64), "double").total, 82176)
    check("E1d fp32 128³ 单缓冲", estimate(TileConfig(128, 128, 128), "single").total, 197120)
    check("E1e fp32 128³ 双缓冲", estimate(TileConfig(128, 128, 128), "double").total, 328192)
    ok, over = check_budget(328192, 256 * 1024)
    check("E1f fp32 128³ 双缓冲 vs 256 KB 溢出", over, 66048)

    # E2 dtype 换算与累加规则
    check("E2a fp16 128³ 双缓冲 = fp32 单缓冲",
          estimate(TileConfig(128, 128, 128, dtype_in="fp16"), "double").total, 197120)
    check("E2b bf16 128³ 双缓冲", estimate(TileConfig(128, 128, 128, dtype_in="bf16"), "double").total, 197120)
    check("E2c int8 128³ 双缓冲", estimate(TileConfig(128, 128, 128, dtype_in="int8"), "double").total, 131584)
    check("E2d int8 128³ 双缓冲 = fp16 单缓冲（规律）",
          estimate(TileConfig(128, 128, 128, dtype_in="int8"), "double").total,
          estimate(TileConfig(128, 128, 128, dtype_in="fp16"), "single").total)
    check("E2e acc=auto 映射 int8→int32", TileConfig(1, 1, 1, dtype_in="int8").acc_dtype(), "int32")

    # E3 对齐与奇数 tile
    check("E3a align_up(1089, 32)", align_up(1089, 32), 1120)
    check("E3b 33³ int8 单缓冲", estimate(TileConfig(33, 33, 33, dtype_in="int8"), "single").total, 6784)
    check("E3c 33³ int8 padding = 118",
          estimate(TileConfig(33, 33, 33, dtype_in="int8"), "single").total - 6666, 118)

    # E4 预算扫描的已知答案
    def largest_cube(dt, budget):
        t_best = 0
        for t in range(1, 1025):
            if estimate(TileConfig(t, t, t, dtype_in=dt), "double").total <= budget:
                t_best = t
        return t_best
    check("E4a fp32 256 KB 最大立方", largest_cube("fp32", 256 * 1024), 114)
    check("E4b int8 128 KB 最大立方", largest_cube("int8", 128 * 1024), 127)
    check("E4c int8 256 KB 最大立方", largest_cube("int8", 256 * 1024), 180)

    # E5 复用流量（512³ fp32，C 常驻）
    m = n = k = 512
    d = 4
    check("E5a 128³ A+B 流量", int(m * n * k * d * (1 / 128 + 1 / 128)), 8388608)
    check("E5b 不切块总流量", (m * k + k * n) * d + m * n * d, 3145728)

    # E6 错误演示的数字
    right = estimate(TileConfig(224, 224, 224, dtype_in="int8"), "double")
    wrong = estimate(TileConfig(224, 224, 224, dtype_in="int8", acc="int8"), "double")
    check("E6a int8 224³ 正确合计（住不下）", right.total, 402304)
    check("E6b int8 224³ acc=int8 错误合计（假象）", wrong.total, 251104)
    fp16 = estimate(TileConfig(128, 128, 128, dtype_in="fp16"), "double")
    check("E6c fp16 128³ 全 ×2 误杀", 2 * (fp16.a + fp16.b + fp16.c) + fp16.bias, 262656)
    check("E6d fp32 128³ 单缓冲 vs 192 KB",
          estimate(TileConfig(128, 128, 128), "single").total - 192 * 1024, 512)

    # E7 长方形 tile 与矩形家的直觉
    check("E7a tile=64×128×128 fp32 双缓冲", estimate(TileConfig(64, 128, 128), "double").total, 229888)
    check("E7b 必做练习手算值 tile=64×128×128", estimate(TileConfig(64, 128, 128), "double").total,
          2 * (64 * 128 * 4 + 128 * 128 * 4) + 64 * 128 * 4 + align_up(128 * 4, 32))

    # E8 坏输入拒绝
    for name, fn in [
        ("tm=0", lambda: TileConfig(0, 8, 8)),
        ("tk 负数", lambda: TileConfig(8, 8, -1)),
        ("dtype 拼错", lambda: TileConfig(8, 8, 8, dtype_in="fp64")),
        ("acc 拼错", lambda: TileConfig(8, 8, 8, acc="fp64")),
        ("buffering 拼错", lambda: estimate(TileConfig(8, 8, 8), "triple")),
        ("align=0", lambda: estimate(TileConfig(8, 8, 8), "double", 0)),
    ]:
        try:
            fn()
            check(f"E8 拒绝 {name}", "未拒绝", "应抛 ValueError")
        except ValueError:
            check(f"E8 拒绝 {name}", "ValueError", "ValueError")

    return results, fails


# ---------------------------------------------------------------- CLI


def parse_config(spec: str) -> dict:
    out = {}
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        key, _, val = part.partition("=")
        key, val = key.strip().lower(), val.strip()
        if not val:
            raise ValueError(f"配置项缺值：{part}")
        if key == "tile":
            dims = [int(v) for v in val.lower().replace("×", "x").split("x")]
            if len(dims) != 3:
                raise ValueError(f"tile 需要三维：{val}")
            out["tile"] = tuple(dims)
        elif key == "dtype":
            out["dtype_in"] = val
        elif key in ("acc", "buffer", "buffering", "budget", "align"):
            out[key] = val
        elif key in ("bias", "staging"):
            if val.lower() in ("on", "true", "1", "yes"):
                out[key] = True
            elif val.lower() in ("off", "false", "0", "no"):
                out[key] = False
            else:
                raise ValueError(f"{key} 只接受 on/off：{val}")
        else:
            raise ValueError(f"未知配置项：{key}（可用 tile/dtype/acc/buffer/bias/staging/budget/align）")
    return out


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description="D101 片上空间估算")
    p.add_argument("--config", default="", help='配置串，如 "tile=64x64x64,dtype=fp32,buffer=double"')
    p.add_argument("--table", action="store_true", help="不同 Tile 的空间表（交付物）")
    p.add_argument("--dtype-sweep", action="store_true", help="固定 128³ 扫 dtype")
    p.add_argument("--budget-sweep", action="store_true", help="预算 → 最大立方 Tile")
    p.add_argument("--reuse", action="store_true", help="HBM 流量 vs Tile（大 Tile 的动机）")
    p.add_argument("--errors", action="store_true", help="三个常见错误的估算对照")
    p.add_argument("--chart", metavar="PATH", help="生成空间条形图 SVG")
    p.add_argument("--test", action="store_true", help="断言式自检")
    args = p.parse_args(argv)

    tiles = [(32, 32, 32), (64, 64, 64), (128, 128, 128)]
    dtypes = ["fp32", "fp16", "bf16", "int8"]
    budget = 256 * 1024

    if args.config:
        cfg_kw = parse_config(args.config)
        tile = cfg_kw.pop("tile", (128, 128, 128))
        budget = parse_bytes(cfg_kw.pop("budget", "256K"))
        buffering = cfg_kw.pop("buffer", cfg_kw.pop("buffering", "double"))
        align = int(cfg_kw.pop("align", DEFAULT_ALIGN))
        cfg = TileConfig(*tile, **cfg_kw)
        print(report_config(cfg, buffering, budget, align))
        return 0

    if args.table:
        print(table(tiles, dtypes, budget))
        return 0
    if args.dtype_sweep:
        print(dtype_sweep(budget=budget))
        return 0
    if args.budget_sweep:
        print(budget_sweep())
        return 0
    if args.reuse:
        print(reuse(budget=budget))
        return 0
    if args.errors:
        print(error_demos())
        return 0
    if args.chart:
        print(chart_svg(tiles, dtypes, budget, args.chart))
        return 0
    if args.test:
        results, fails = run_tests()
        print("—— D101 自检：已知账单 / 累加规则 / 对齐 / 预算扫描 / 错误数字 ——")
        for r in results:
            print(r)
        print(f"\n{len(results) - fails}/{len(results)} 项通过"
              + ("" if fails == 0 else f"；{fails} 项失败"))
        return 1 if fails else 0

    # 默认：主例报告（D97 冠军配置的判定）
    cfg = TileConfig(128, 128, 128, dtype_in="fp32")
    print(report_config(cfg, "double", budget,
                        title="主例：D97 的冠军 tile 遇上 256 KB 片上预算"))
    print()
    cfg2 = TileConfig(64, 64, 64, dtype_in="fp32")
    print(report_config(cfg2, "double", budget,
                        title="对照：降到 64³ 就能住下"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
