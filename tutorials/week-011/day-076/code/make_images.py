#!/usr/bin/env python3
"""make_images.py —— 第 76 天（简单 Cost Model 集成）教程的四张手绘 sketch 风 SVG 信息图。

风格约定（与第 71–75 天一致，Excalidraw-like）：
  - 背景 #fdfaf2（米白），盒子白底 + 深灰 #6b6357 手绘描边
  - 强调色不超过 4 种柔和色：蓝 #4a7fa5 / 橙 #a8772e / 绿 #5a8a5a / 红 #b0605a
  - 线条带轻微抖动（L 段折线），圆头笔触，线宽 2 左右
  - 手写感字体栈：Comic Sans MS / Comic Neue / Kaiti SC / 楷体 / cursive
  - 只用矩形、格子、箭头、圆角框等简单几何形状

图中全部数字来自 2026-11-13 的真实运行（code/outputs/）：
  cost_model 31/31；test_cost_model 33/33；
  贯穿例 P3(2,3,2)：评分 64 B（= D72 的 ΔB）、活集 272 B、寄存器并发 240；
  记账对拍：keep 20/20、recompute 13/13（有组外的 13 组）；
  R1（MM→MM K1=1024 +1 组外，tile128）：keep 评分 −2,097,152 B（ΔB 8,388,608 −
    spill 10,485,760）；recompute 评分 +13,893,632 B（消除 25,165,824 − 罚
    786,432 − spill 10,485,760）；两形式 spill 共用；
  决策结果表：auto 与 D75 ground truth 16/16 一致；force 合法 8 融 / 非法 8 拒；
  误差实弹：R4 tile128 换 256 KiB 寄存器堆卡 → 并发 1→3、refuse→fuse、评分
    67,108,864 B 不变；32 KiB 卡 → R2ctl/R3keep/R4ctl 翻拒；动态 M=-1 →
    评分未知 → auto 拒 / force 融；R3keep staging 2,097,152 B 超 SRAM 只警告。

运行：python3 make_images.py   （在 code/ 目录下，输出到 ../images/）
"""

from __future__ import annotations

import math
import random
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "images"
OUT.mkdir(parents=True, exist_ok=True)

FONT = ("Comic Sans MS, Comic Neue, Segoe Print, Kaiti SC, KaiTi, 楷体, "
        "cursive")
INK = "#3b352d"
MUTED = "#84796a"
STROKE = "#6b6357"
BG = "#fdfaf2"
BLUE, ORANGE, GREEN, RED = "#4a7fa5", "#a8772e", "#5a8a5a", "#b0605a"
TINT = {"blue": "#eef3f7", "orange": "#f8f0e2", "green": "#edf4ee",
        "red": "#f7ecea", "white": "#ffffff", "gray": "#f1efe9"}

rng = random.Random(76)


def esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;")
              .replace(">", "&gt;"))


def tw(s: str, size: float) -> float:
    """粗略的字宽估算：CJK 约 1×size，ASCII 约 0.55×size。"""
    return sum(size if ord(c) > 0x2E80 else size * 0.55 for c in s)


def txt(x, y, s, size=12, fill=INK, anchor="start", bold=False,
        opacity=1.0):
    w = 'font-weight="bold"' if bold else 'font-weight="normal"'
    return (f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" '
            f'fill="{fill}" text-anchor="{anchor}" opacity="{opacity}" '
            f'{w}>{esc(s)}</text>')


def sketch_rect(x, y, w, h, fill="#ffffff", stroke=STROKE, sw=2.2, nseg=6):
    pts = []

    def seg(x0, y0, x1, y1):
        for i in range(nseg + 1):
            t = i / nseg
            jx = rng.uniform(-1.2, 1.2) if 0 < i < nseg else 0
            jy = rng.uniform(-1.2, 1.2) if 0 < i < nseg else 0
            pts.append((x0 + (x1 - x0) * t + jx, y0 + (y1 - y0) * t + jy))

    seg(x, y, x + w, y)
    seg(x + w, y, x + w, y + h)
    seg(x + w, y + h, x, y + h)
    seg(x, y + h, x, y)
    d = f"M {pts[0][0]:.1f},{pts[0][1]:.1f} " + " ".join(
        f"L {px:.1f},{py:.1f}" for px, py in pts[1:])
    return (f'<path d="{d}" fill="{fill}" stroke="{stroke}" '
            f'stroke-width="{sw}" stroke-linecap="round" '
            f'stroke-linejoin="round"/>')


def sketch_line(x0, y0, x1, y1, stroke=STROKE, sw=2.0, arrow=False,
                opacity=1.0, dashed=False):
    if dashed:
        main = (f'<path d="M {x0:.1f},{y0:.1f} L {x1:.1f},{y1:.1f}" '
                f'fill="none" stroke="{stroke}" stroke-width="{sw}" '
                f'stroke-linecap="round" stroke-dasharray="7 6" '
                f'opacity="{opacity}"/>')
    else:
        main = (f'<path d="M {x0:.1f},{y0:.1f} L {x1:.1f},{y1:.1f}" '
                f'fill="none" stroke="{stroke}" stroke-width="{sw}" '
                f'stroke-linecap="round" stroke-linejoin="round" '
                f'opacity="{opacity}"/>')
    out = [main]
    if arrow:
        ang = math.atan2(y1 - y0, x1 - x0)
        L, A = 11, 0.5
        ax, ay = x1 - L * math.cos(ang), y1 - L * math.sin(ang)
        out.append(f'<path d="M {x1:.1f},{y1:.1f} L {ax:.1f},{ay - 4:.1f}" '
                   f'fill="none" stroke="{stroke}" stroke-width="{sw}" '
                   f'stroke-linecap="round" opacity="{opacity}"/>')
        out.append(f'<path d="M {x1:.1f},{y1:.1f} L {ax:.1f},{ay + 4:.1f}" '
                   f'fill="none" stroke="{stroke}" stroke-width="{sw}" '
                   f'stroke-linecap="round" opacity="{opacity}"/>')
    return "".join(out)


def header(w, h, title, sub):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" '
            f'height="{h}" viewBox="0 0 {w} {h}">\n'
            f'<rect width="{w}" height="{h}" fill="{BG}"/>\n'
            + txt(40, 38, title, 20, INK, bold=True) + "\n"
            + txt(40, 61, sub, 12, MUTED) + "\n")


def save(name: str, body: str) -> None:
    path = OUT / name
    path.write_text(body + "</svg>\n", encoding="utf-8")
    print(f"wrote {path} ({path.stat().st_size} bytes)")


def panel_title(x, y, s, color=INK):
    return txt(x, y, s, 14, color, bold=True)


def badge(x, y, s, color, size=11.5, h=22, fill=None):
    w = tw(s, size) + 16
    return (sketch_rect(x, y, w, h, fill=fill or TINT["white"], stroke=color,
                        sw=1.8, nseg=4)
            + txt(x + w / 2, y + h - 7, s, size, color, anchor="middle",
                  bold=True))


# ============================================================
# 图 1：全貌——Cost Model v0.1 在编译链路中的位置
# ============================================================

def fig1() -> None:
    w, h = 1180, 880
    body = header(w, h, "第 76 天全貌：Cost Model v0.1——把四本账装进一台报价机",
                  "位置：Pattern 改写之前的「值不值得」裁判。D74 的纪律：能否融合（合法性）与值不值得（计价）是两个函数。")

    # ---- 顶部：编译器流水线 ----
    body += panel_title(40, 100, "① 编译链路里的位置：Cost Model 站在改写之前")
    pipe = [("前端图\n(mini-IR)", 44, 142, "gray"),
            ("Pattern\n发现融合候选", 212, 172, "blue"),
            ("can_fuse\n合法性 L1–L6", 410, 160, "blue"),
            ("★ Cost Model v0.1\n统一计价＋决策", 596, 190, "orange"),
            ("改写执行\n融 / 不融", 812, 150, "green"),
            ("后端\n代码生成", 988, 142, "gray")]
    y0, hh = 116, 62
    for label, x, bw, col in pipe:
        lines = label.split("\n")
        body += sketch_rect(x, y0, bw, hh, fill=TINT[col], sw=2.4)
        for i, ln in enumerate(lines):
            body += txt(x + bw / 2, y0 + 26 + i * 17, ln, 12, INK,
                        anchor="middle", bold=("★" in ln))
    for i in range(len(pipe) - 1):
        x_from = pipe[i][1] + pipe[i][2]
        x_to = pipe[i + 1][1]
        body += sketch_line(x_from + 3, y0 + hh / 2, x_to - 5, y0 + hh / 2,
                            arrow=True, sw=2.2)

    # Cost Model 的输入 / 输出
    body += sketch_line(661, y0 + hh, 661, y0 + hh + 26, arrow=True, sw=2.0)
    io_y = y0 + hh + 30
    body += sketch_rect(300, io_y, 270, 74, fill=TINT["white"], sw=2.0)
    body += txt(312, io_y + 20, "输入", 12, BLUE, bold=True)
    body += txt(312, io_y + 38, "候选（图＋Shape＋声明形式）", 11)
    body += txt(312, io_y + 54, "机器假设卡 · 模式（force / auto）", 11)
    body += sketch_rect(610, io_y, 270, 74, fill=TINT["white"], sw=2.0)
    body += txt(622, io_y + 20, "输出（CostReport）", 12, GREEN, bold=True)
    body += txt(622, io_y + 38, "评分明细 ＋ 决策 ＋ 理由", 11)
    body += txt(622, io_y + 54, "形式提示 ＋ 融合前后 IR 对照", 11)
    body += sketch_line(570, io_y + 37, 606, io_y + 37, arrow=True, sw=2.0)

    # ---- 中部：四本账 → 统一评分 ----
    body += panel_title(40, 276, "② 统一计价：四本账进一个评分，出处留在明细里")
    ledger = [("D72 收益账", "ΔB = passes·elems·4", "组外使用者只省组内读"),
              ("D73 资源账", "活集 → 阶梯 → spill", "两趟税（下界口径）"),
              ("D75 重算账", "elim − 组外重读罚", "删中间的另一种形式"),
              ("D73 舒适区", "寄存器并发 ≥ 3", "未计价 → 当门槛用")]
    lx, ly, lw, lh = 44, 292, 250, 66
    for i, (t, f, note) in enumerate(ledger):
        x = lx + i * 278
        body += sketch_rect(x, ly, lw, lh, fill=TINT["blue"], sw=2.0)
        body += txt(x + 12, ly + 21, t, 12, BLUE, bold=True)
        body += txt(x + 12, ly + 38, f, 11)
        body += txt(x + 12, ly + 54, note, 10.5, MUTED)
        body += sketch_line(x + lw / 2, ly + lh, x + lw / 2, ly + lh + 22,
                            arrow=True, sw=2.0)
    sy = ly + lh + 26
    body += sketch_rect(300, sy, 580, 44, fill=TINT["orange"], sw=2.4)
    body += txt(590, sy + 27, "统一评分  score = 收益项 − 代价项（字节）"
                "  ·  未计价项只报告，不编数字", 13, INK, anchor="middle",
                bold=True)

    # ---- 下部：本周时间线 ----
    body += panel_title(40, 452, "③ 本周时间线：前五天造零件，今天装机器，明天复盘")
    days = [("D71", "算账", "FLOPs/流量"), ("D72", "ΔB", "收益公式"),
            ("D73", "资源", "活集/spill"), ("D74", "三层门", "接口分离"),
            ("D75", "案例库", "16 例判据"), ("D76", "Cost Model", "今天 ★"),
            ("D77", "复盘", "合法/正确/更快")]
    dx, dy, dw, dh = 44, 470, 148, 58
    for i, (d, t, note) in enumerate(days):
        x = dx + i * 160
        col = "orange" if d == "D76" else ("gray" if d == "D77" else "blue")
        body += sketch_rect(x, dy, dw, dh, fill=TINT[col], sw=2.4 if col == "orange" else 2.0)
        body += txt(x + dw / 2, dy + 21, f"{d} {t}", 12.5, INK,
                    anchor="middle", bold=(d == "D76"))
        body += txt(x + dw / 2, dy + 41, note, 10.5, MUTED, anchor="middle")
        if i < len(days) - 1:
            body += sketch_line(x + dw + 3, dy + dh / 2, x + dw + 12,
                                dy + dh / 2, arrow=True, sw=2.0)

    # D75 → D76 的 ground truth 箭头
    body += sketch_line(868, dy + dh + 6, 868, dy + dh + 30, stroke=GREEN,
                        sw=2.2, arrow=True)
    body += sketch_line(868, dy + dh + 30, 700, dy + dh + 30, stroke=GREEN,
                        sw=2.2, arrow=True)
    body += txt(880, dy + dh + 22, "ground truth", 11, GREEN, bold=True)
    body += txt(880, dy + dh + 38, "auto 判决 16/16 复现", 10.5, GREEN)

    # ---- 底部：两种模式 ----
    body += panel_title(40, 592, "④ 两种模式：一台机器，两种用法")
    body += sketch_rect(44, 608, 520, 96, fill=TINT["red"], sw=2.2)
    body += txt(60, 630, "force 强制融合", 13, RED, bold=True)
    body += txt(60, 650, "合法即融，评分照记", 11.5)
    body += txt(60, 668, "用途：A/B 实验、校准评分与实测的偏差", 11)
    body += txt(60, 686, "不是生产模式（R2 倒亏 31.5 MiB 也会被融进去）", 10.5, MUTED)
    body += sketch_rect(616, 608, 520, 96, fill=TINT["green"], sw=2.2)
    body += txt(632, 630, "auto 自动决策（默认）", 13, GREEN, bold=True)
    body += txt(632, 650, "评分 > 0 ∧ 零 spill ∧ 寄存器并发 ≥ 3", 11.5)
    body += txt(632, 668, "判决复现 D75 案例库 16/16（含 R4 分歧行同判）", 11)
    body += txt(632, 686, "拒绝理由三类：合法性 / 评分 / 门槛", 10.5, MUTED)

    # 底部一句话
    body += sketch_rect(44, 730, 1092, 60, fill=TINT["white"], sw=2.0)
    body += txt(590, 754, "真实编译器同款问题：LLVM 用 TargetTransformInfo 给向量化/内联计价，",
                12, INK, anchor="middle")
    body += txt(590, 774, "Google MLGO 用强化学习校准内联代价——模型＋校准，"
                "而不是「拍脑袋阈值」", 12, INK, anchor="middle")
    save("01-overview.svg", body)


# ============================================================
# 图 2：核心机制——evaluate 的流程与 R1 的两张账单
# ============================================================

def fig2() -> None:
    w, h = 1180, 920
    body = header(w, h, "核心机制：CostModel.evaluate——合法性 → 双形式计价 → 门槛决策",
                  "数字全部来自 2026-11-13 真实运行。右侧贯穿例：R1（MatMul(2048,64)→G(2048,1024)→MatMul，1 个组外使用者，tile 128）。")

    # ---- 左列：流程 ----
    body += panel_title(44, 100, "① evaluate(c, mode) 的四步")
    steps = [
        ("候选 ＋ 机器卡 ＋ 模式", 112, 56, "white", INK),
        ("① can_fuse：合法性 L1–L6", 186, 64, "blue", INK),
        ("② 双形式计价（itemized）", 268, 120, "blue", INK),
        ("③ 声明形式上的决策", 406, 136, "orange", INK),
        ("CostReport（输出）", 560, 132, "green", INK),
    ]
    for label, y, bh, col, tcol in steps:
        body += sketch_rect(60, y, 330, bh, fill=TINT[col], sw=2.2)
        body += txt(225, y + 20, label, 12.5, tcol, anchor="middle",
                    bold=True)
    for i in range(len(steps) - 1):
        y_from = steps[i][1] + steps[i][2]
        body += sketch_line(225, y_from + 2, 225, steps[i + 1][1] - 4,
                            arrow=True, sw=2.2)

    # 非法出口
    body += sketch_line(390, 218, 470, 218, stroke=RED, sw=2.0, arrow=True)
    body += sketch_rect(474, 192, 180, 52, fill=TINT["red"], sw=2.0)
    body += txt(564, 213, "非法 → refuse", 12, RED, anchor="middle", bold=True)
    body += txt(564, 232, "force 也不融非法的图", 10.5, RED, anchor="middle")

    # 步骤②的两个形式子盒（画在②盒内部：268..388）
    body += sketch_rect(74, 300, 140, 40, fill=TINT["white"], sw=1.8)
    body += txt(144, 317, "keep 形式", 11, INK, anchor="middle", bold=True)
    body += txt(144, 332, "ΔB − spill", 10, INK, anchor="middle")
    body += sketch_rect(228, 300, 148, 40, fill=TINT["white"], sw=1.8)
    body += txt(302, 317, "recompute 形式", 11, INK, anchor="middle", bold=True)
    body += txt(302, 332, "elim − 罚 − spill", 10, INK, anchor="middle")
    body += txt(76, 366, "评分 = Σ 带符号项（字节），", 10.5, MUTED)
    body += txt(76, 382, "每项带 [D72]/[D73]/[D75] 出处", 10.5, MUTED)

    # 步骤③的模式分叉（画在③盒内部：406..542）
    body += sketch_line(180, 448, 180, 478, stroke=RED, sw=2.0, arrow=True)
    body += sketch_line(290, 448, 290, 478, stroke=GREEN, sw=2.0, arrow=True)
    body += sketch_rect(76, 482, 140, 38, fill=TINT["red"], sw=1.8)
    body += txt(146, 498, "force：合法即融", 11, RED, anchor="middle", bold=True)
    body += txt(146, 514, "（评分照记）", 10, RED, anchor="middle")
    body += sketch_rect(244, 482, 140, 38, fill=TINT["green"], sw=1.8)
    body += txt(314, 498, "auto：三门槛", 11, GREEN, anchor="middle", bold=True)
    body += txt(314, 514, "（评分/零spill/并发）", 9.5, GREEN, anchor="middle")

    # 形式排序提示（从②到右侧）
    body += sketch_line(390, 330, 470, 330, stroke=BLUE, sw=2.0, arrow=True,
                        dashed=True)
    body += txt(400, 322, "形式排序 → 提示", 10.5, BLUE)
    body += txt(400, 352, "（不改写决策，E6）", 10, MUTED)

    # CostReport 的四个输出（画在 CostReport 盒内部）
    for i, s in enumerate(["评分明细（每项带公式出处）",
                           "决策 ＋ 三类可归因理由",
                           "形式提示（另一形式分更高？）",
                           "融合前后 mini-IR 对照"]):
        body += txt(84, 600 + i * 22, "· " + s, 10.5)

    # ---- 右列：R1 的两张账单 ----
    body += panel_title(540, 100, "② 贯穿例：R1 的两张账单（同一张图，两种形式）")

    # keep 账单
    body += sketch_rect(540, 118, 600, 150, fill=TINT["white"], sw=2.2)
    body += txt(556, 140, "keep 形式（声明）", 12.5, BLUE, bold=True)
    body += txt(556, 162, "＋ 8,388,608    消除中间落盘 ΔB   [D72]"
                "  G 的组内读 1 趟（写趟被组外钉死）", 11)
    body += txt(556, 182, "− 10,485,760  spill 两趟税        [D73]"
                "  活集 589,824 B 溢出（下界）", 11)
    body += sketch_line(556, 194, 1124, 194, sw=1.4)
    body += txt(556, 216, "评分 = −2,097,152 B", 13, RED, bold=True)
    body += badge(790, 202, "auto：refuse", RED)
    body += txt(920, 216, "评分 ≤ 0（还有 spill 与并发两条也挂）", 10.5, MUTED)

    # recompute 账单
    body += sketch_rect(540, 290, 600, 170, fill=TINT["white"], sw=2.2)
    body += txt(556, 312, "recompute 形式（形式排序里更高）", 12.5, ORANGE,
                bold=True)
    body += txt(556, 334, "＋ 25,165,824  消除全部中间流量 [D75]"
                "  写＋组内读＋组外读全消失", 11)
    body += txt(556, 354, "− 786,432      组外重读罚       [D75]"
                "  1 个组外 × 生产者输入", 11)
    body += txt(556, 374, "− 10,485,760  spill 两趟税      [D73]"
                "  与 keep 共用（核结构一样）", 11)
    body += sketch_line(556, 386, 1124, 386, sw=1.4)
    body += txt(556, 408, "评分 = +13,893,632 B", 13, GREEN, bold=True)
    body += txt(800, 408, "但门槛：spill 327,680 B > 0 → 仍拒", 11, RED)

    # 形式排序箭头
    body += sketch_line(840, 268, 840, 286, stroke=ORANGE, sw=2.4, arrow=True)
    body += txt(856, 280, "排序差 15,990,784 B", 11, ORANGE, bold=True)

    # 提示框
    body += sketch_rect(540, 482, 600, 64, fill=TINT["orange"], sw=2.0)
    body += txt(556, 504, "提示（hint）如实输出：", 11.5, ORANGE, bold=True)
    body += txt(556, 522, "「recompute 形式评分 13,893,632 B（高于声明形式"
                " −2,097,152 B；", 10.5)
    body += txt(556, 538, "  但 一票否决：spill …）」——换形式救不了 R1，"
                "先缩 tile 才是真出口", 10.5)

    # ---- 底部：auto 三门槛 ＋ 未计价 ----
    body += panel_title(44, 712, "③ auto 的三道门槛与「只报告不编数」的未计价项")
    gates = [("门槛 1", "评分 > 0", "收益盖得住代价（R1：−2 MiB ✗）", GREEN),
             ("门槛 2", "零 spill", "两趟税是下界，真实更贵（R1ctl ✗）", GREEN),
             ("门槛 3", "寄存器并发 ≥ 3", "工作集 ÷ 寄存器堆（R4：1 ✗）", GREEN)]
    for i, (t, f, note, col) in enumerate(gates):
        x = 44 + i * 250
        body += sketch_rect(x, 724, 236, 62, fill=TINT["green"], sw=2.0)
        body += txt(x + 12, 744, f"{t}：{f}", 11.5, col, bold=True)
        body += txt(x + 12, 762, note, 10.5, MUTED)
        body += txt(x + 12, 778, "有账（字节）或有阈值，才进门", 10, MUTED)
    unpriced = [("未计价 1", "staging 失败 → 只警告", "R3keep：分块 2 MiB 超 SRAM 仍融"),
                ("未计价 2", "launch / 编译 / 多核", "C8 沿用，进清单不进评分"),
                ("未计价 3", "并发是容量 proxy", "不是吞吐率——不知道慢多少")]
    for i, (t, f, note) in enumerate(unpriced):
        x = 800
        y = 724 + i * 50
        body += sketch_rect(x, y, 340, 44, fill=TINT["gray"], sw=1.8)
        body += txt(x + 12, y + 17, f"{t}：{f}", 11, INK, bold=True)
        body += txt(x + 12, y + 34, note, 10, MUTED)

    body += txt(412, 812, "为什么门槛用「寄存器并发」（工作集装不装得下，R4）"
                "而 staging 只警告（复用损失，R3keep）——", 11, INK,
                anchor="middle")
    body += txt(412, 832, "两个量都在报告里，只有一个当门槛（E5 的设计决定，"
                "与 D75 ground truth 对齐）", 11, INK, anchor="middle")
    save("02-mechanism.svg", body)


# ============================================================
# 图 3：决策结果表（16 例 × force/auto）
# ============================================================

def fig3() -> None:
    w, h = 1220, 1060
    body = header(w, h, "决策结果表：D75 案例库 16 例 × 两种模式（ground truth 回归 16/16）",
                  "评分单位 B；R并发 = 寄存器并发（门槛量）；spill 为字节数。数字为 2026-11-13 真实运行（code/outputs/cost_model.txt §7）。")

    rows = [
        ("A1 Relu→MatMul", "—", "—", "—", "—", "合法性 L1", False),
        ("A2 副作用 add", "—", "—", "—", "—", "合法性 L2", False),
        ("A3 Shape 不一致", "—", "—", "—", "—", "合法性 L3", False),
        ("A4 int8 全链", "—", "—", "—", "—", "合法性 L5", False),
        ("A5 偷走 E", "—", "—", "—", "—", "合法性 L4", False),
        ("A6 无使用者", "—", "—", "—", "—", "合法性 L4", False),
        ("A7 循环依赖", "—", "—", "—", "—", "合法性 L6", False),
        ("A8 隐式 Reshape", "—", "—", "—", "—", "合法性 L3b", False),
        ("R1 +1 组外", "keep", "-2,097,152", "327,680", "1", "评分 ≤ 0 ＋重算提示", False),
        ("R1ctl 无组外", "keep", "6,291,456", "327,680", "1", "spill 一票否决", False),
        ("R2 tile2048", "keep", "-33,030,144", "17,039,360", "1", "评分 ≤ 0", False),
        ("R2ctl tile64", "keep", "1,048,576", "0", "4", "三门槛全过", True),
        ("R3keep", "keep", "16,384", "0", "3", "三门槛全过（staging 警告）", True),
        ("R3recompute", "recompute", "-4,128,768", "0", "3", "评分 ≤ 0 ＋keep 提示", False),
        ("R4 tile128", "keep", "67,108,864", "0", "1", "并发门槛 1 < 3", False),
        ("R4ctl tile64", "keep", "67,108,864", "0", "3", "三门槛全过", True),
    ]

    x_name, x_form, x_score, x_spill, x_conc, x_force, x_auto, x_why = \
        46, 320, 415, 560, 690, 775, 855, 935
    y0, rh = 106, 46
    table_w = 1140

    # 表头
    body += sketch_rect(x_name - 6, y0 - 26, table_w, 30, fill=TINT["gray"],
                        sw=1.8, nseg=4)
    heads = [(x_name, "案例"), (x_form, "形式"), (x_score, "评分(B)"),
             (x_spill, "spill"), (x_conc, "R并发"), (x_force, "force"),
             (x_auto, "auto"), (x_why, "auto 首条理由")]
    for x, t in heads:
        body += txt(x, y0 - 6, t, 11.5, INK, bold=True)

    for i, (name, form, score, spill, conc, why, fuse) in enumerate(rows):
        y = y0 + i * rh
        wing_a = i < 8
        base = TINT["gray"] if wing_a else TINT["white"]
        body += sketch_rect(x_name - 6, y, table_w, rh - 6, fill=base,
                            sw=1.4, nseg=3)
        body += txt(x_name, y + 21, name, 11.5,
                    MUTED if wing_a else INK, bold=not wing_a)
        body += txt(x_form, y + 21, form, 11)
        body += txt(x_score, y + 21, score, 11,
                    RED if score.startswith("-") else INK)
        body += txt(x_spill, y + 21, spill, 11,
                    RED if spill not in ("0", "—") else MUTED)
        body += txt(x_conc, y + 21, conc, 11,
                    RED if conc == "1" else INK)
        body += txt(x_force, y + 21, "fuse" if not wing_a else "refuse", 11,
                    GREEN if not wing_a else MUTED)
        # auto 单元格上色
        cell_w = 66
        body += sketch_rect(x_auto - 6, y + 3, cell_w, rh - 12,
                            fill=TINT["green"] if fuse else TINT["red"],
                            sw=1.6, nseg=3)
        body += txt(x_auto + cell_w / 2 - 6, y + 21,
                    "fuse" if fuse else "refuse", 11,
                    GREEN if fuse else RED, anchor="middle", bold=True)
        body += txt(x_why, y + 21, why, 10.5,
                    MUTED if wing_a else INK)

    # 翼分隔标注
    body += txt(1196, y0 + 3.5 * rh, "翼 A", 12, MUTED, anchor="end", bold=True)
    body += txt(1196, y0 + 11.5 * rh, "翼 B", 12, MUTED, anchor="end", bold=True)
    body += sketch_line(46, y0 + 8 * rh - 10, 1186, y0 + 8 * rh - 10,
                        stroke=MUTED, sw=1.2, dashed=True)

    # 底部汇总
    sy = y0 + 16 * rh + 14
    body += sketch_rect(46, sy, 1140, 78, fill=TINT["orange"], sw=2.2)
    body += txt(62, sy + 24, "回归结论（全部真实运行）：", 12.5, ORANGE, bold=True)
    body += txt(62, sy + 44, "auto 判决与 D75 案例库 16/16 逐例一致"
                "（翼 A 8 拒 ＋ 翼 B 5 拒 3 融）；force 对合法 8 例全融、非法 8 例全拒。", 11)
    body += txt(62, sy + 64, "拒绝理由归三类：合法性 L·（8 例）/ 评分 ≤ 0（3 例）/"
                "spill 一票否决（1 例）/ 并发门槛（1 例）；两处形式提示（R1、R3recompute）。", 11)
    body += txt(1196, sy + 24, "force 列另有一行", 10.5, MUTED, anchor="end")
    body += txt(1196, sy + 40, "「评分照记」", 10.5, MUTED, anchor="end")
    save("03-decision-table.svg", body)


# ============================================================
# 图 4：误差四轴（两个实弹 + 对拍边界 + 未计价）
# ============================================================

def fig4() -> None:
    w, h = 1180, 900
    body = header(w, h, "误差四轴：评分是模型输出，不是测量结果",
                  "今天用两个「只拧一个参数」的实弹演示参数轴与输入轴；口径轴与未计价轴来自对拍边界与警告清单。数字为真实运行。")

    # ---- 左上：参数轴 ----
    body += panel_title(44, 100, "① 参数轴：机器卡是假设的（E1/E8）", BLUE)
    body += sketch_rect(44, 112, 540, 240, fill=TINT["white"], sw=2.2)
    body += txt(60, 136, "实弹：R4 P3 tile128（评分恒为 67,108,864 B），只换寄存器堆：",
                11.5)
    body += sketch_rect(60, 148, 250, 74, fill=TINT["red"], sw=1.8)
    body += txt(70, 168, "toy-core v0（64 KiB）", 11, INK, bold=True)
    body += txt(70, 186, "寄存器并发 1  →  refuse", 11, RED, bold=True)
    body += txt(70, 204, "评分 +67,108,864 B（正也没用）", 10.5, MUTED)
    body += sketch_rect(322, 148, 250, 74, fill=TINT["green"], sw=1.8)
    body += txt(332, 168, "toy-core wide（256 KiB）", 11, INK, bold=True)
    body += txt(332, 186, "寄存器并发 3  →  fuse", 11, GREEN, bold=True)
    body += txt(332, 204, "评分 +67,108,864 B（一字不差）", 10.5, MUTED)
    body += sketch_line(310, 185, 320, 185, stroke=ORANGE, sw=2.4, arrow=True)
    body += txt(60, 246, "翻转全部来自门槛（容量），不来自计价（流量）——"
                "换卡不换账，只换判决。", 11)
    body += txt(60, 266, "另一侧：32 KiB 卡让 R2ctl / R3keep / R4ctl 三个原本"
                "融合的也翻成 refuse。", 11)
    body += txt(60, 286, "含义：上真机前，机器卡参数（寄存器堆/SRAM/通道）"
                "必须实测校准。", 11, MUTED)

    # ---- 右上：输入轴 ----
    body += panel_title(620, 100, "② 输入轴：动态 Shape 算不出账（D61/D62）", BLUE)
    body += sketch_rect(620, 112, 516, 240, fill=TINT["white"], sw=2.2)
    body += txt(636, 136, "实弹：R4 的 M 从 2048 拧成 -1（未知维度）：", 11.5)
    body += txt(636, 162, "M = 2048：评分 67,108,864 B，auto refuse（并发门槛）",
                11)
    body += txt(636, 184, "M = -1：评分「未知」（known=False）", 11, RED, bold=True)
    body += sketch_rect(636, 198, 236, 60, fill=TINT["red"], sw=1.8)
    body += txt(646, 218, "auto → refuse", 11.5, RED, bold=True)
    body += txt(646, 238, "「动态 Shape 算不出活集与 ΔB」", 10.5)
    body += sketch_rect(888, 198, 236, 60, fill=TINT["green"], sw=1.8)
    body += txt(898, 218, "force → fuse", 11.5, GREEN, bold=True)
    body += txt(898, 238, "「只看合法性（评分照记：未知）」", 10.5)
    body += txt(636, 284, "出口：先特化成静态 Shape 再进门（D62）；"
                "两种模式对未知的处理不同，", 11)
    body += txt(636, 304, "这不是 bug——force 本来就是给校准实验用的。", 11, MUTED)

    # ---- 左下：口径轴 ----
    body += panel_title(44, 392, "③ 口径轴：公式有边界，对拍只证一半（E4）", ORANGE)
    body += sketch_rect(44, 404, 540, 240, fill=TINT["white"], sw=2.2)
    body += txt(60, 428, "记账对拍（20 组随机）：流量项逐位一致——", 11.5)
    body += txt(60, 448, "keep：记账差值 == ΔB 公式 → 20/20", 11, GREEN, bold=True)
    body += txt(60, 468, "recompute：记账差值 == elim − 罚 → 13/13", 11, GREEN,
                bold=True)
    body += txt(60, 494, "但对拍的边界（MM→MM 实例）：", 11.5)
    body += txt(60, 514, "记账器看得见：ΔB = 16,777,216 B", 11)
    body += txt(60, 534, "记账器看不见：spill 两趟税 10,485,760 B", 11, RED,
                bold=True)
    body += txt(60, 560, "spill 是下界（D73 A4）：真实更贵；launch / 编译时间 /"
                " 多核竞争不计（C8）。", 10.5, MUTED)
    body += txt(60, 580, "结论：对拍证明「收益项没算错」，不证明「代价项够准」——"
                "后者靠 force + 实测。", 11)

    # ---- 右下：未计价轴 ----
    body += panel_title(620, 392, "④ 未计价轴：不知道 ≠ 编一个（D75 纪律）", RED)
    body += sketch_rect(620, 404, 516, 240, fill=TINT["white"], sw=2.2)
    body += txt(636, 428, "R3keep 的报告（真实输出）：", 11.5)
    body += txt(636, 448, "输入分块 2,097,152 B > 剩余 SRAM 196,608 B"
                " → staging ✗", 11)
    body += txt(636, 468, "完整模型并发 1 / 寄存器并发 3 → 判决仍是 fuse"
                "（警告不否决）", 11)
    body += txt(636, 494, "并发 tile 数是容量 proxy，不是吞吐率（D73 A7）：", 11.5)
    body += txt(636, 514, "「并发 1 < 3 不舒服」有阈值支撑；", 11)
    body += txt(636, 534, "「慢 3 倍」没有任何测量支撑——不写。", 11, RED, bold=True)
    body += txt(636, 560, "两种诚实：知道不舒服（阈值）/ 不知道慢多少（清单）；", 10.5, MUTED)
    body += txt(636, 580, "编数字是第三种，唯一不可接受的那种（D75 错误三）。", 10.5, MUTED)

    # ---- 底部：force 的用途 = 校准 ----
    body += panel_title(44, 684, "⑤ 误差怎么收口：force 模式 = 校准工具")
    body += sketch_rect(44, 698, 1092, 92, fill=TINT["blue"], sw=2.2)
    body += txt(60, 722, "闭环：auto 拒的候选用 force 强制融合 → 跑实测（流量/时间）→ "
                "对照评分找系统性偏差 → 修口径（spill 系数）或修参数（机器卡）", 12)
    body += txt(60, 744, "今天的 v0.1 只走到「流量项可对拍、资源项是下界」这一步："
                "20/20 与 13/13 的对拍是收益项的质检，spill 与并发等真实代价", 11)
    body += txt(60, 764, "要靠真机校准——真实编译器同样走这条路：LLVM TTI 提供"
                "目标代价接口，Google MLGO 用 RL 从实测回流校准内联代价。", 11)
    body += txt(60, 784, "（引用仅为路线对照：本教程的 toy-core 是假设卡，"
                "所有数字都是模型口径。）", 10.5, MUTED)
    save("04-error-sources.svg", body)


if __name__ == "__main__":
    fig1()
    fig2()
    fig3()
    fig4()
