#!/usr/bin/env python3
"""make_images.py —— 第 75 天（构造不融合案例）教程的四张手绘 sketch 风 SVG 信息图。

风格约定（与第 71–74 天一致，Excalidraw-like）：
  - 背景 #fdfaf2（米白），盒子白底 + 深灰 #6b6357 手绘描边
  - 强调色不超过 4 种柔和色：蓝 #4a7fa5 / 橙 #a8772e / 绿 #5a8a5a / 红 #b0605a
  - 线条带轻微抖动（L 段折线），圆头笔触，线宽 2 左右
  - 手写感字体栈：Comic Sans MS / Comic Neue / Kaiti SC / 楷体 / cursive
  - 只用矩形、格子、箭头、圆角框等简单几何形状

图中全部数字来自 2026-11-13 的真实运行（code/outputs/）：
  negative_case_lab 30/30；test_negative_cases 34/34；
  R1 多使用者：MM→MM(2048,64,K1=1024) tile=128：无组外 ΔB 16,777,216 B /
    spill 流量 10,485,760 B / net +6,291,456 B（auto 放行）；
    +1 组外使用者：ΔB 8,388,608 / net −2,097,152（cons+auto 全拒，兑现率 −25%）；
  R2 资源超限：MM→MM K1=64：tile 2048 活集 17,301,504 B、spill 17,039,360 B、
    net −33,030,144；tile 64 活集 32,768 B、并发 4、net +1,048,576；
  R3 重复计算：skinny(64,4096)：keep ΔB 16,384 B 融合；重算消除 65,536 B、
    重读罚 4,194,304 B、net −4,128,768（64:1）拒；
  R4 并行度：P3(2048²,K=64)：tile 128 占用 65,792 B → 并发 1（D74 门 fuse、
    库 refuse）；tile 64 占用 16,640 B → 并发 3；未融合 MatMul@64 并发 4；
  结构负例 8 例（6 旧 + L3b/L6 两新），决策日志 16 行。

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

rng = random.Random(75)


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


def dot(x, y, r=5, fill=INK, stroke=STROKE):
    return (f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="1.8"/>')


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
# 图 1：全貌
# ============================================================

def fig1() -> None:
    w, h = 1180, 840
    b = [header(w, h, "第 75 天全貌：构造不融合案例——把拒绝记录变成案例库",
                 "第 11 周「融合收益与代价模型」第五天 —— 四类负收益：多使用者 / "
                 "重复计算 / 资源超限 / 并行度下降 ｜ "
                 "图中数字均为 2026-11-13 本机实测")]

    # ---- 顶部：阶段进度条 ----
    b.append(txt(40, 92, "学习计划位置（24 周 / 168 天）", 13, MUTED, bold=True))
    stages = [
        ("W1–4", "C++/IR/基础 Pass", False),
        ("W5–8", "MLIR/融合", False),
        ("W9–10", "Shape/Layout/图优化", False),
        ("W11", "融合收益与代价 ← 今天", True),
        ("W12", "数值精度与量化", False),
        ("W13–16", "Lowering/Tiling/调优", False),
        ("W17–24", "端到端与收口", False),
    ]
    bx, by, bw, bh, gap = 40, 100, 152, 50, 8
    for i, (rng_, theme, cur) in enumerate(stages):
        x = bx + i * (bw + gap)
        fill = TINT["orange"] if cur else TINT["gray"]
        b.append(sketch_rect(x, by, bw, bh, fill=fill,
                             stroke=ORANGE if cur else STROKE,
                             sw=2.6 if cur else 2.0))
        b.append(txt(x + bw / 2, by + 20, rng_, 12,
                     ORANGE if cur else MUTED, anchor="middle", bold=True))
        b.append(txt(x + bw / 2, by + 38, theme, 10.5,
                     INK if cur else MUTED, anchor="middle", bold=cur))

    # ---- 中排：本周七天 ----
    b.append(txt(40, 178, "本周链路（第 11 周：融合收益与代价模型）", 13, MUTED,
                 bold=True))
    days = [("D71", "计算量与访存量"), ("D72", "融合减少的流量"),
             ("D73", "融合的资源代价"), ("D74", "合法/收益分离"),
             ("D75", "构造不融合案例 ←",), ("D76", "简单 Cost Model"),
             ("D77", "复盘")]
    dx, dy, dw, dh = 40, 186, 152, 46
    for i, (d, t) in enumerate(days):
        x = dx + i * (dw + 8)
        cur = i == 4
        b.append(sketch_rect(x, dy, dw, dh,
                             fill=TINT["orange"] if cur else TINT["white"],
                             stroke=ORANGE if cur else STROKE,
                             sw=2.6 if cur else 1.8))
        b.append(txt(x + dw / 2, dy + 19, d, 12,
                     ORANGE if cur else INK, anchor="middle", bold=True))
        b.append(txt(x + dw / 2, dy + 36, t, 10.5, INK, anchor="middle"))
    b.append(sketch_line(40 + 7 * (dw + 8) - 4, dy + dh / 2, 1140,
                         dy + dh / 2, stroke=MUTED, sw=1.6, dashed=True))

    # ---- 盒 1：昨天留下的原料 ----
    x, y, bw2, bh2 = 40, 258, 552, 240
    b.append(sketch_rect(x, y, bw2, bh2, fill=TINT["white"], stroke=RED,
                         sw=2.4))
    b.append(txt(x + 14, y + 24, "① 昨天的门只回答「这个候选」", 13, RED, bold=True))
    b.append(txt(x + 14, y + 50, "D74 的 11 行决策日志是「表的副产物」——"
                 "今天要把它变成资产：案例库", 11.5, INK))
    b.append(txt(x + 14, y + 72, "每个案例 = 一个具体的图 ＋ 一个明确的「应拒绝」理由"
                 " ＋ 一条机检断言", 11.5, ORANGE, bold=True))
    b.append(sketch_rect(x + 14, y + 88, 524, 74, fill=TINT["red"],
                         stroke=RED, sw=2.0, nseg=8))
    b.append(txt(x + 276, y + 112, "计划点名四类负收益：", 12.5, INK,
                 anchor="middle", bold=True))
    b.append(txt(x + 276, y + 134, "多使用者 · 重复计算 · 资源超限 · 并行度下降",
                 11.5, INK, anchor="middle"))
    b.append(txt(x + 276, y + 152, "——都要求「图结构合法但应拒绝」的带理由案例",
                 10.5, RED, anchor="middle"))
    b.append(txt(x + 14, y + 186, "融合不是免费午餐：D74 的门已经拦住了其中两类，"
                 "还有两类它根本看不见", 11.5, INK))
    b.append(txt(x + 14, y + 208, "看不见 ≠ 不存在：今天把四类都造成案例，"
                 "给 D76 的 Cost Model 备料", 11, GREEN, bold=True))

    # ---- 盒 2：案例库结构 ----
    x, y = 612, 258
    b.append(sketch_rect(x, y, 528, 240, fill=TINT["white"], stroke=GREEN,
                         sw=2.4))
    b.append(txt(x + 14, y + 24, "② 今天的产出：两翼 16 例的案例库", 13,
                 GREEN, bold=True))
    rows = [
        ("翼 A 结构负例 8 例", "图本身非法：D74 六类 ＋ 新规则 L3b/L6", BLUE),
        ("翼 B 负收益 8 例", "图合法但应拒绝：R1–R4 四类 ＋ 4 个对照", ORANGE),
        ("决策日志 16 行", "每行：合法性 / ΔB / spill / 净收益 / 并发 / 三策略 / 库", GREEN),
    ]
    for i, (sig, desc, color) in enumerate(rows):
        yy = y + 52 + i * 56
        b.append(badge(x + 14, yy - 17, sig, color, size=10.5, h=21))
        b.append(txt(x + 22, yy + 24, desc, 10.8, INK))
        if i < 2:
            b.append(sketch_line(x + 250, yy + 6, x + 250, yy + 34,
                                 stroke=MUTED, sw=1.6, arrow=True))
    b.append(txt(x + 14, y + 220, "测试把每例的预期判决写成断言：改门必须先过案例库",
                 11, GREEN, bold=True))

    # ---- 盒 3：四个判决 ----
    x, y, bw2, bh2 = 40, 522, 552, 184
    b.append(sketch_rect(x, y, bw2, bh2, fill=TINT["white"], stroke=ORANGE,
                         sw=2.4))
    b.append(txt(x + 14, y + 24, "③ 四个判决（全部真实运行）", 13, ORANGE,
                 bold=True))
    b.append(txt(x + 14, y + 50, "R1 多使用者：+1 个组外使用者，净收益 +6,291,456 B"
                 " 翻成 −2,097,152 B", 11.5, INK))
    b.append(txt(x + 14, y + 70, "R2 资源超限：不分块净收益 −33,030,144 B；同图 tile=64"
                 " 救活 +1,048,576 B", 11.5, INK))
    b.append(txt(x + 14, y + 96, "R3 重复计算：重算消除 65,536 B，重读罚 4,194,304 B"
                 "（64:1）→ 亏 3.94 MiB", 11.5, INK))
    b.append(txt(x + 14, y + 116, "  同一张图 keep 形式 +16,384 B 放行——"
                 "负收益的是「形式」不是「图」", 11, RED, bold=True))
    b.append(txt(x + 14, y + 142, "R4 并行度：D74 门放行（net +64 MiB），但并发 1 < 3"
                 " → 案例库拒", 11.5, INK))
    b.append(txt(x + 14, y + 162, "  tile=64 并发 3、净收益不变——门与库的分歧如实记录",
                 11, RED, bold=True))

    # ---- 盒 4：输出去向 ----
    x, y = 612, 522
    b.append(sketch_rect(x, y, 528, 184, fill=TINT["white"], stroke=BLUE,
                         sw=2.4))
    b.append(txt(x + 14, y + 24, "④ 案例库交给谁（本周后半程）", 13, BLUE,
                 bold=True))
    b.append(txt(x + 14, y + 50, "D76 Cost Model v0.1：把四类判据统一成可插拔的"
                 "评分器", 11.5, INK))
    b.append(txt(x + 14, y + 70, "  R3 的流量推广公式和 R4 的舒适区阈值就是它的两块料",
                 11, MUTED))
    b.append(txt(x + 14, y + 96, "D77 复盘：16 例当回归资产——以后改门，先过案例库",
                 11.5, INK))
    b.append(txt(x + 14, y + 116, "  两条新规则 L3b/L6 就是案例库反哺门的证据",
                 11, MUTED))
    b.append(txt(x + 14, y + 148, "今天的产出：负收益案例 4 类 8 例 ＋ 决策日志 16 行"
                 " ＋ 结构负例 8 例", 11.5, GREEN, bold=True))

    # ---- 底部徽标 ----
    badges = [("主实验 30/30", GREEN), ("验收测试 34/34", GREEN),
              ("产出：案例库 16 例＋日志 16 行", ORANGE),
              ("4 张图全部真实数字", BLUE)]
    bx3 = 40
    for s, c in badges:
        b.append(badge(bx3, 748, s, c))
        bx3 += tw(s, 11.5) + 34

    b.append(txt(40, 806, "运行入口：code/run_all.sh（主实验 → 独立测试 → "
                "重新生成本组图片）", 11, MUTED))
    save("01-overview.svg", "".join(b))


# ============================================================
# 图 2：核心机制——四类负收益的机理 + 两条新规则
# ============================================================

def fig2() -> None:
    w, h = 1180, 830
    b = [header(w, h, "核心机制：四类负收益怎么把「合法」变成「不值得」",
                 "左上起顺时针：R1 多使用者 / R2 资源超限 / R3 重复计算 / R4 并行度"
                 " ｜ 中间：案例库反哺门的两条新规则 ｜ 数字均为真实运行")]

    # ---- R1 多使用者 ----
    x, y, cw, ch = 40, 100, 545, 250
    b.append(sketch_rect(x, y, cw, ch, fill=TINT["white"], stroke=RED, sw=2.2))
    b.append(txt(x + 12, y + 22, "R1 多使用者：写趟被组外使用者钉死", 12.5, RED,
                 bold=True))
    # 小图：MatMul→G→MatMul，G 分叉出组外
    mx, my = x + 14, y + 44
    b.append(sketch_rect(mx, my + 18, 96, 34, fill=TINT["blue"], stroke=BLUE,
                         sw=1.8, nseg=5))
    b.append(txt(mx + 48, my + 40, "MatMul₁", 10.5, INK, anchor="middle"))
    b.append(sketch_line(mx + 96, my + 35, mx + 136, my + 35, stroke=MUTED,
                         sw=1.8, arrow=True))
    b.append(dot(mx + 146, my + 35, 6, fill=ORANGE))
    b.append(txt(mx + 146, my + 18, "G", 11, ORANGE, anchor="middle", bold=True))
    b.append(sketch_line(mx + 156, my + 35, mx + 196, my + 35, stroke=MUTED,
                         sw=1.8, arrow=True))
    b.append(sketch_rect(mx + 196, my + 18, 96, 34, fill=TINT["blue"],
                         stroke=BLUE, sw=1.8, nseg=5))
    b.append(txt(mx + 244, my + 40, "MatMul₂", 10.5, INK, anchor="middle"))
    b.append(sketch_line(mx + 146, my + 42, mx + 146, my + 74, stroke=RED,
                         sw=2.0, arrow=True))
    b.append(txt(mx + 156, my + 66, "组外使用者（还要读 G）", 10.5, RED, bold=True))
    # 账本
    ax, ay = x + 330, y + 44
    lines = [
        ("无组外：ΔB = 2 趟 × 8 MiB", INK, False),
        ("= 16,777,216 B → net +6,291,456", GREEN, True),
        ("有组外：写趟留下，只剩组内读", INK, False),
        ("ΔB = 1 趟 = 8,388,608 B", RED, True),
        ("spill 流量不变 10,485,760 B", INK, False),
        ("net = −2,097,152 B（−25%）", RED, True),
        ("→ cons 与 auto 一致拒绝", RED, True),
    ]
    for i, (s, c, bold_) in enumerate(lines):
        b.append(txt(ax, ay + 16 + i * 22, s, 10.8, c, bold=bold_))
    b.append(txt(x + 12, y + 152, "机理：组外使用者必须从 DRAM 拿到 G，融合只能保留"
                 " G 的写——省的只有组内那一趟读；", 11, INK))
    b.append(txt(x + 12, y + 172, "spill 一分没少，收益砍半：+6 MiB 翻成 −2 MiB。"
                 "不变量：net(对照)−net(R1) = |G|×4", 11, INK))
    b.append(txt(x + 12, y + 200, "案例：MatMul(2048,64)→G(2048,1024)→MatMul，"
                 "tile 128，G 有 1 个组外使用者（keep）", 10.5, MUTED))
    b.append(txt(x + 12, y + 222, "对应到技术上：D52 的 keep 形式 ＋ D72 多使用者规则"
                 "（组外>0 只省组内读）", 10.5, MUTED))

    # ---- R2 资源超限 ----
    x, y = 595, 100
    b.append(sketch_rect(x, y, 545, 250, fill=TINT["white"], stroke=RED, sw=2.2))
    b.append(txt(x + 12, y + 22, "R2 资源超限：spill 两趟税吞掉全部 ΔB", 12.5, RED,
                 bold=True))
    # 三级容量阶梯
    lx, ly = x + 14, y + 46
    b.append(sketch_rect(lx, ly, 120, 26, fill=TINT["green"], stroke=GREEN,
                         sw=1.8, nseg=5))
    b.append(txt(lx + 60, ly + 18, "reg 64 KiB", 10.5, INK, anchor="middle"))
    b.append(sketch_rect(lx, ly + 30, 120, 26, fill=TINT["orange"], stroke=ORANGE,
                         sw=1.8, nseg=5))
    b.append(txt(lx + 60, ly + 48, "SRAM 192 KiB", 10.5, INK, anchor="middle"))
    b.append(sketch_rect(lx, ly + 60, 120, 44, fill=TINT["red"], stroke=RED,
                         sw=1.8, nseg=5))
    b.append(txt(lx + 60, ly + 86, "spill → DRAM", 10.5, RED, anchor="middle",
                 bold=True))
    b.append(sketch_line(lx + 132, ly + 82, lx + 168, ly + 82, stroke=MUTED,
                         sw=1.8, arrow=True))
    b.append(txt(lx + 176, ly + 78, "活集 17,301,504 B", 10.8, RED, bold=True))
    b.append(txt(lx + 176, ly + 96, "spill 17,039,360 B ×2 趟", 10.8, RED))
    ax, ay = x + 330, y + 44
    lines = [
        ("ΔB = 2×|G|×4 = 1,048,576 B", INK, False),
        ("spill 流量 = 34,078,720 B", RED, True),
        ("net = −33,030,144 B", RED, True),
        ("tile=64：活集 32,768 B 全驻 reg", INK, False),
        ("并发 4，net +1,048,576 B → 放行", GREEN, True),
        ("→ 图没问题，是 tile 的锅", ORANGE, True),
    ]
    for i, (s, c, bold_) in enumerate(lines):
        b.append(txt(ax, ay + 16 + i * 22, s, 10.8, c, bold=bold_))
    b.append(txt(x + 12, y + 152, "机理：融合把生产者和消费者塞进一个核，活集＝累加器"
                 "＋G 行块一起涨；装不下就付", 11, INK))
    b.append(txt(x + 12, y + 172, "「写一遍读一遍」的两趟税（D73 A4 下界口径）——"
                 "税超过省的流量就是负收益", 11, INK))
    b.append(txt(x + 12, y + 200, "案例：MatMul(2048,64)→G(2048,64)→MatMul，"
                 "tile=2048 不分块 vs tile=64", 10.5, MUTED))
    b.append(txt(x + 12, y + 222, "对应到技术上：D73 三级容量阶梯（reg → SRAM → spill）"
                 "＋ spill_traffic = 2×溢出×行块数", 10.5, MUTED))

    # ---- R3 重复计算 ----
    x, y, cw, ch = 40, 366, 545, 250
    b.append(sketch_rect(x, y, cw, ch, fill=TINT["white"], stroke=RED, sw=2.2))
    b.append(txt(x + 12, y + 22, "R3 重复计算：删中间喂组外＝输入重读", 12.5, RED,
                 bold=True))
    # 小图：A,B → MatMul → C 分叉给 Add(组内) 和 2 个组外
    mx, my = x + 14, y + 40
    b.append(sketch_rect(mx, my + 18, 60, 30, fill=TINT["gray"], stroke=STROKE,
                         sw=1.6, nseg=5))
    b.append(txt(mx + 30, my + 38, "A,B", 10, INK, anchor="middle"))
    b.append(sketch_line(mx + 60, my + 33, mx + 92, my + 33, stroke=MUTED,
                         sw=1.6, arrow=True))
    b.append(sketch_rect(mx + 92, my + 18, 70, 30, fill=TINT["blue"],
                         stroke=BLUE, sw=1.6, nseg=5))
    b.append(txt(mx + 127, my + 38, "MatMul", 9.5, INK, anchor="middle"))
    b.append(sketch_line(mx + 162, my + 33, mx + 192, my + 33, stroke=MUTED,
                         sw=1.6, arrow=True))
    b.append(dot(mx + 202, my + 33, 6, fill=ORANGE))
    b.append(txt(mx + 202, my + 16, "C", 11, ORANGE, anchor="middle", bold=True))
    b.append(sketch_line(mx + 212, my + 33, mx + 242, my + 22, stroke=MUTED,
                         sw=1.6, arrow=True))
    b.append(txt(mx + 248, my + 22, "+D（组内）", 10, INK))
    b.append(sketch_line(mx + 202, my + 40, mx + 242, my + 58, stroke=RED,
                         sw=2.0, arrow=True))
    b.append(txt(mx + 248, my + 62, "组外 ×2：各重算一遍 MatMul", 10, RED))
    ax, ay = x + 330, y + 40
    lines = [
        ("keep：ΔB = 1 趟读 = 16,384 B", GREEN, True),
        ("  零 spill → 放行（开销 0.05%）", INK, False),
        ("重算：消除写+3 读 = 65,536 B", INK, False),
        ("  重读罚 = 2 × 2 MiB = 4,194,304 B", RED, True),
        ("  net = −4,128,768 B（64:1）", RED, True),
        ("→ 拒绝的是「重算形式」", ORANGE, True),
    ]
    for i, (s, c, bold_) in enumerate(lines):
        b.append(txt(ax, ay + 16 + i * 22, s, 10.8, c, bold=bold_))
    b.append(txt(x + 12, y + 152, "机理：K=4096 的瘦矩阵输入 (64×4096) 远大于输出"
                 " (64×64)——每为组外重算一遍，就把 2 MiB 输入", 11, INK))
    b.append(txt(x + 12, y + 172, "重读一遍；换掉的 C 流量只有 64 KiB。判据是流量比"
                 "（输入重读 vs 中间消除），不是时间模型", 11, INK))
    b.append(txt(x + 12, y + 200, "案例：skinny MatMul(64,4096)→C(64,64)→+D，"
                 "C 有 2 个组外使用者", 10.5, MUTED))
    b.append(txt(x + 12, y + 222, "对应到技术上：D72 流量公式在「删除＋重算」形式下的"
                 "推广（D75 扩展②，只做流量）", 10.5, MUTED))

    # ---- R4 并行度 ----
    x, y = 595, 366
    b.append(sketch_rect(x, y, 545, 250, fill=TINT["white"], stroke=RED, sw=2.2))
    b.append(txt(x + 12, y + 22, "R4 并行度下降：占用变大，并发 tile 掉档", 12.5,
                 RED, bold=True))
    # 寄存器堆被占满的小图
    lx, ly = x + 14, y + 46
    b.append(sketch_rect(lx, ly, 150, 88, fill=TINT["gray"], stroke=STROKE,
                         sw=2.0))
    b.append(txt(lx + 75, ly - 6, "寄存器堆 64 KiB", 10, MUTED, anchor="middle"))
    b.append(sketch_rect(lx + 6, ly + 6, 138, 40, fill=TINT["red"], stroke=RED,
                         sw=1.6, nseg=4))
    b.append(txt(lx + 75, ly + 28, "融合核 tile128：65,792 B", 9.8, INK,
                 anchor="middle", bold=True))
    b.append(txt(lx + 75, ly + 62, "装不下第二个 tile → 并发 1", 9.8, RED,
                 anchor="middle"))
    ax, ay = x + 330, y + 40
    lines = [
        ("D74 门：net +67,108,864 B → fuse", INK, False),
        ("库：并发 1 < 3（D73 舒适区）", RED, True),
        ("tile=64：占用 16,640 B → 并发 3", INK, False),
        ("  net 不变 +64 MiB（ΔB 与 tile 无关）", GREEN, True),
        ("未融合 MatMul@64：并发 4", INK, False),
        ("  → 融合税 4→3，账本未计价的软代价", ORANGE, True),
    ]
    for i, (s, c, bold_) in enumerate(lines):
        b.append(txt(ax, ay + 16 + i * 22, s, 10.8, c, bold=bold_))
    b.append(txt(x + 12, y + 152, "机理：寄存器堆被所有并发 tile 分摊，每 tile 占用"
                 "越大、驻留越少、延迟隐藏越差（D73 软代价）；", 11, INK))
    b.append(txt(x + 12, y + 172, "舒适区判据（零 spill＋staging ok＋并发≥3）只挑坏 tile"
                 "——拒绝 tile=128 一分钱不花", 11, INK))
    b.append(txt(x + 12, y + 200, "案例：P3 = MatMul(2048,64)→+D→relu 全融合，"
                 "tile 128 vs 64", 10.5, MUTED))
    b.append(txt(x + 12, y + 222, "对应到技术上：D73 的并发公式 max(1, min(reg÷占用, "
                 "SRAM÷分块)) ＋ 检查 4f 的舒适区", 10.5, MUTED))

    # ---- 底部：两条新规则 ----
    x, y, bw2, bh2 = 40, 632, 1100, 150
    b.append(sketch_rect(x, y, bw2, bh2, fill=TINT["white"], stroke=GREEN,
                         sw=2.2))
    b.append(txt(x + 14, y + 24, "案例库反哺门：两条新合法性规则（各自拦住一个 D74 "
                 "漏网案例，老正例一个不伤）", 12.5, GREEN, bold=True))
    b.append(badge(x + 14, y + 44, "L3b 边形状", BLUE, size=11, h=22))
    b.append(txt(x + 130, y + 60, "相邻算子的边形状必须一致：MatMul 输出 (2,4) 直接喂"
                 " (4,2) 的 add——边上有隐式 Reshape，", 11, INK))
    b.append(txt(x + 130, y + 80, "不在融合模式里；-1 未知维度照旧通配（D61 口径）",
                 11, INK))
    b.append(badge(x + 14, y + 100, "L6 组内拓扑序", BLUE, size=11, h=22))
    b.append(txt(x + 130, y + 116, "中间的生产者序号必须小于消费者：F 由算子2(relu) 生产"
                 "却被算子0(matmul) 消费——组内成环，", 11, INK))
    b.append(txt(x + 130, y + 136, "D74 规则集下这两例都会被判「合法」（d74_can_fuse "
                 "回归对照可复现）", 11, INK))
    save("02-mechanism.svg", "".join(b))


# ============================================================
# 图 3：实例对照——四组对照实验
# ============================================================

def fig3() -> None:
    w, h = 1180, 830
    b = [header(w, h, "实例对照：四组「拧一个参数」实验——负收益从哪来、怎么救",
                 "数据来自 code/outputs/negative_case_lab.txt §3–§6 真实运行"
                 "（每个案例都有对照：只改一个变量，看判决翻转）")]

    # ---- 左上：R1 翻转表 ----
    x, y, cw, ch = 40, 100, 550, 300
    b.append(sketch_rect(x, y, cw, ch, fill=TINT["white"], stroke=BLUE, sw=2.2))
    b.append(txt(x + 12, y + 22, "实验一（R1）：拧「组外使用者」——0 个 vs 1 个",
                 12.5, BLUE, bold=True))
    cols = [("G 的组外使用者", x + 14), ("ΔB", x + 168), ("spill 流量", x + 260),
            ("净收益", x + 350), ("cons", x + 452), ("auto", x + 505)]
    ty = y + 50
    for name, cxx in cols:
        b.append(txt(cxx, ty, name, 10.5, MUTED, bold=True))
    b.append(sketch_line(x + 10, ty + 8, x + cw - 12, ty + 8, stroke=MUTED, sw=1.2))
    rows = [
        ("0 个（对照）", "16,777,216 B", "10,485,760 B", "+6,291,456 B",
         "refuse", "fuse", False),
        ("1 个（R1）", "8,388,608 B", "10,485,760 B", "−2,097,152 B",
         "refuse", "refuse", True),
    ]
    ry = ty + 28
    for g, db, st, net, c1, c2, hot in rows:
        base = RED if hot else INK
        b.append(txt(x + 14, ry, g, 11, base, bold=hot))
        b.append(txt(x + 168, ry, db, 10.5, base))
        b.append(txt(x + 260, ry, st, 10.5, base))
        b.append(txt(x + 350, ry, net, 10.5, base, bold=True))
        b.append(badge(x + 452, ry - 16, c1, RED if c1 == "refuse" else GREEN,
                        size=9.8, h=18))
        b.append(badge(x + 505, ry - 16, c2, RED if c2 == "refuse" else GREEN,
                        size=9.8, h=18))
        ry += 34
    b.append(txt(x + 14, ry + 4, "图/机器/tile 全不变，只给 G 加 1 个组外使用者：",
                 10.8, INK))
    b.append(txt(x + 14, ry + 24, "· ΔB 减半：写趟被钉死，只剩组内读一趟", 10.8, INK))
    b.append(txt(x + 14, ry + 44, "· spill 分文未动：负收益全来自收益侧塌缩", 10.8, INK))
    b.append(txt(x + 14, ry + 64, "· auto 从 fuse 翻成 refuse；差 = |G|×4 = 8,388,608 B",
                 10.8, ORANGE, bold=True))
    b.append(txt(x + 14, ry + 84, "案例：MM→MM(2048,64,1024,2048) tile128", 10.2, MUTED))

    # ---- 右上：R2 tile 表 ----
    x, y = 606, 100
    b.append(sketch_rect(x, y, 534, 300, fill=TINT["white"], stroke=GREEN, sw=2.2))
    b.append(txt(x + 12, y + 22, "实验二（R2）：拧「tile」——2048 不分块 vs 64",
                 12.5, GREEN, bold=True))
    cols = [("tile", x + 14), ("活集", x + 76), ("spill", x + 196),
            ("净收益", x + 306), ("并发", x + 416), ("库", x + 466)]
    ty = y + 50
    for name, cxx in cols:
        b.append(txt(cxx, ty, name, 10.5, MUTED, bold=True))
    b.append(sketch_line(x + 10, ty + 8, x + cw - 12 if False else x + 520,
                         ty + 8, stroke=MUTED, sw=1.2))
    rows = [
        ("2048", "17,301,504 B", "17,039,360 B", "−33,030,144 B", "1", "refuse",
         True),
        ("64", "32,768 B", "0 B", "+1,048,576 B", "4", "fuse", False),
    ]
    ry = ty + 28
    for t, live, sp, net, conc, act, hot in rows:
        base = RED if hot else INK
        b.append(txt(x + 14, ry, t, 11, base, bold=hot))
        b.append(txt(x + 76, ry, live, 10.5, base))
        b.append(txt(x + 196, ry, sp, 10.5, base))
        b.append(txt(x + 306, ry, net, 10.5, base, bold=True))
        b.append(txt(x + 416, ry, conc, 10.5, base))
        b.append(badge(x + 466, ry - 16, act, RED if act == "refuse" else GREEN,
                        size=9.8, h=18))
        ry += 34
    b.append(txt(x + 14, ry + 4, "同一张图（K1=64）：活集 = 累加器 4·t² ＋ G 行块 "
                 "4·t·K1", 10.8, INK))
    b.append(txt(x + 14, ry + 24, "· t=2048：spill 两趟税 34 MiB ≫ ΔB 1 MiB → 倒亏 31.5 MiB",
                 10.8, INK))
    b.append(txt(x + 14, ry + 44, "· t=64：全驻 reg、并发 4 → cons/auto 都放行", 10.8,
                 INK))
    b.append(txt(x + 14, ry + 64, "拒绝理由在收益层（「保守策略：」前缀），hint：缩 tile 重试",
                 10.8, ORANGE, bold=True))
    b.append(txt(x + 14, ry + 84, "案例：MM→MM(2048,64,64,2048)", 10.2, MUTED))

    # ---- 左下：R3 两本账 ----
    x, y, cw, ch = 40, 420, 550, 300
    b.append(sketch_rect(x, y, cw, ch, fill=TINT["white"], stroke=ORANGE, sw=2.2))
    b.append(txt(x + 12, y + 22, "实验三（R3）：拧「喂组外的形式」——keep vs 重算",
                 12.5, ORANGE, bold=True))
    ty = y + 50
    cols = [("形式", x + 14), ("消除流量", x + 120), ("重读罚", x + 240),
            ("净收益", x + 360), ("库", x + 470)]
    for name, cxx in cols:
        b.append(txt(cxx, ty, name, 10.5, MUTED, bold=True))
    b.append(sketch_line(x + 10, ty + 8, x + 538, ty + 8, stroke=MUTED, sw=1.2))
    rows = [
        ("keep（C 落盘）", "16,384 B", "—", "+16,384 B", "fuse", False),
        ("重算（删 C）", "65,536 B", "4,194,304 B", "−4,128,768 B", "refuse",
         True),
    ]
    ry = ty + 28
    for f, el, rr, net, act, hot in rows:
        base = RED if hot else INK
        b.append(txt(x + 14, ry, f, 11, base, bold=hot))
        b.append(txt(x + 120, ry, el, 10.5, base))
        b.append(txt(x + 240, ry, rr, 10.5, base))
        b.append(txt(x + 360, ry, net, 10.5, base, bold=True))
        b.append(badge(x + 470, ry - 16, act, RED if act == "refuse" else GREEN,
                        size=9.8, h=18))
        ry += 34
    b.append(txt(x + 14, ry + 4, "同一张图（skinny 64×4096×64，C 有 2 个组外使用者）："
                 "keep 赚 16 KiB", 10.8, INK))
    b.append(txt(x + 14, ry + 24, "· 重算消除 4 趟 C 流量 64 KiB，但 2 个组外各把 "
                 "2 MiB 输入重读一遍", 10.8, INK))
    b.append(txt(x + 14, ry + 44, "· 重读罚:消除 = 64:1——K=4096 的瘦矩阵输入远大于输出",
                 10.8, INK))
    b.append(txt(x + 14, ry + 64, "· 被拒的是「重算形式」不是「图」：形式可换，图不变",
                 10.8, ORANGE, bold=True))
    b.append(txt(x + 14, ry + 84, "恒等式：net = 消除 − 重读罚 − spill 流量", 10.2, MUTED))

    # ---- 右下：R4 门与库的分歧 ----
    x, y = 606, 420
    b.append(sketch_rect(x, y, 534, 300, fill=TINT["white"], stroke=RED, sw=2.2))
    b.append(txt(x + 12, y + 22, "实验四（R4）：拧「tile」——门放行、库拒绝", 12.5,
                 RED, bold=True))
    ty = y + 50
    cols = [("案例", x + 14), ("占用", x + 130), ("并发", x + 250),
            ("净收益", x + 320), ("D74 门", x + 440), ("案例库", x + 500)]
    for name, cxx in cols:
        b.append(txt(cxx, ty, name, 10.5, MUTED, bold=True))
    b.append(sketch_line(x + 10, ty + 8, x + 522, ty + 8, stroke=MUTED, sw=1.2))
    rows = [
        ("P3 tile128", "65,792 B", "1", "+67,108,864 B", "fuse", "refuse", True),
        ("P3 tile64", "16,640 B", "3", "+67,108,864 B", "fuse", "fuse", False),
        ("未融合 MM64", "16,384 B", "4","—", "—", "—", False),
    ]
    ry = ty + 28
    for c, occ, conc, net, g, lib, hot in rows:
        base = RED if hot else INK
        b.append(txt(x + 14, ry, c, 10.5, base, bold=hot))
        b.append(txt(x + 130, ry, occ, 10.5, base))
        b.append(txt(x + 250, ry, conc, 10.5, base))
        b.append(txt(x + 320, ry, net, 10.5, base))
        if g != "—":
            b.append(badge(x + 440, ry - 16, g, GREEN if g == "fuse" else RED,
                           size=9.8, h=18))
            b.append(badge(x + 500, ry - 16, lib, RED if lib == "refuse" else GREEN,
                           size=9.8, h=18))
        ry += 34
    b.append(txt(x + 14, ry + 4, "tile128：零 spill、net +64 MiB——门（只看流量与 spill）"
                 "放行；", 10.8, INK))
    b.append(txt(x + 14, ry + 24, "· 但占用 65,792 B ＞ 寄存器堆 65,536 B → 并发 1，"
                 "违反 D73 舒适区（≥3）", 10.8, INK))
    b.append(txt(x + 14, ry + 44, "· tile64 并发 3、net 不变（ΔB 与 tile 无关）："
                 "拒绝坏 tile 一分钱不花", 10.8, INK))
    b.append(txt(x + 14, ry + 64, "· 分歧如实记录：并行度是账本没计价的软代价——"
                 "D76 的输入", 10.8, ORANGE, bold=True))
    b.append(txt(x + 14, ry + 84, "案例：P3(2048,64,2048) 全融合", 10.2, MUTED))
    save("03-comparison.svg", "".join(b))


# ============================================================
# 图 4：案例库总表（16 行决策日志）
# ============================================================

def fig4() -> None:
    w, h = 1180, 830
    b = [header(w, h, "第二份产出：决策日志 16 行——案例库的完整判决书",
                 "数据来自 code/outputs/negative_case_lab.txt §7 真实运行 ｜ "
                 "列：案例 / 类别 / 合法 / ΔB / spill 流量 / 净收益 / 并发 / "
                 "cons / auto / 库 / 理由（截选）")]

    # 列头
    cols = [("案例", 56), ("类别", 200), ("ΔB", 272), ("spill流量", 340),
            ("净收益", 420), ("并发", 500), ("cons", 528), ("auto", 586),
            ("库", 644), ("理由（截选，前缀＝归属层）", 690)]
    ty = 128
    for name, cxx in cols:
        b.append(txt(cxx, ty, name, 10.5, MUTED, bold=True))
    b.append(sketch_line(52, ty + 8, 1140, ty + 8, stroke=MUTED, sw=1.2))

    log = [
        ("A1 Relu→MatMul", "L1 模式", "—", "—", "—", "—", "refuse", "refuse",
         "refuse", "合法性：L1 不在支持的模式里", RED),
        ("A2 副作用 add", "L2 纯度", "—", "—", "—", "—", "refuse", "refuse",
         "refuse", "合法性：L2 有副作用不能进组", RED),
        ("A3 Shape 不一致", "L3 Shape", "—", "—", "—", "—", "refuse", "refuse",
         "refuse", "合法性：L3 逐元素 Shape 不齐", RED),
        ("A4 int8 全链", "L5 dtype", "—", "—", "—", "—", "refuse", "refuse",
         "refuse", "合法性：L5 dtype 暂不支持", RED),
        ("A5 偷走 E", "L4 使用者", "—", "—", "—", "—", "refuse", "refuse",
         "refuse", "合法性：L4 组外使用者没人喂", RED),
        ("A6 无使用者", "L4 死代码", "—", "—", "—", "—", "refuse", "refuse",
         "refuse", "合法性：L4 没有任何使用者", RED),
        ("A7 循环依赖", "L6 拓扑序（新）", "—", "—", "—", "—", "refuse",
         "refuse", "refuse", "合法性：L6 生产者晚于消费者（D74 会漏）", RED),
        ("A8 隐式 Reshape", "L3b 边形状（新）", "—", "—", "—", "—", "refuse",
         "refuse", "refuse", "合法性：L3b 边形状 (2,4)≠(4,2)（D74 会漏）", RED),
        ("R1 +1 组外", "R1 多使用者", "8,388,608", "10,485,760", "−2,097,152",
         "1", "refuse", "refuse", "refuse", "保守策略：spill＞0，净收益按下界为负",
         RED),
        ("R1ctl 无组外", "R1 多使用者", "16,777,216", "10,485,760", "+6,291,456",
         "1", "refuse", "fuse", "refuse", "对照：auto 放行——一个使用者翻转判决",
         ORANGE),
        ("R2 tile2048", "R2 资源超限", "1,048,576", "34,078,720", "−33,030,144",
         "1", "refuse", "refuse", "refuse", "保守策略：spill 两趟税吞掉全部 ΔB",
         RED),
        ("R2ctl tile64", "R2 资源超限", "1,048,576", "0", "+1,048,576", "4",
         "fuse", "fuse", "fuse", "对照：同图缩 tile 救活（并发 4）", GREEN),
        ("R3keep keep 形式", "R3 重复计算", "16,384", "0", "+16,384", "1",
         "fuse", "fuse", "fuse", "对照：keep 省组内读一趟，零 spill", GREEN),
        ("R3recompute", "R3 重复计算", "65,536", "0", "−4,128,768", "1",
         "refuse", "refuse", "refuse", "重算账：消除 64 KiB − 重读罚 4 MiB（64:1）",
         RED),
        ("R4 P3 tile128", "R4 并行度", "67,108,864", "0", "+67,108,864", "1",
         "fuse", "fuse", "refuse", "并行度：并发 1＜3（D73 舒适区）——门放行库拒绝",
         RED),
        ("R4ctl P3 tile64", "R4 并行度", "67,108,864", "0", "+67,108,864", "3",
         "fuse", "fuse", "fuse", "对照：并发 3、净收益不变（ΔB 与 tile 无关）",
         GREEN),
    ]
    ry = ty + 24
    for name, cat, db, st, net, conc, c1, c2, lib, why, color in log:
        hot = lib == "refuse"
        if hot:
            b.append(sketch_rect(52, ry - 16, 1090, 22,
                                 fill=TINT["red"] if cat[0] != "R" or name.startswith(
                                     "R4 P3") else TINT["red"],
                                 stroke=STROKE, sw=1.0, nseg=4))
        b.append(txt(56, ry, name, 10, INK, bold=True))
        b.append(txt(200, ry, cat, 9.5, MUTED))
        b.append(txt(272, ry, db, 9.5, INK))
        b.append(txt(340, ry, st, 9.5, INK))
        b.append(txt(420, ry, net, 9.5, INK, bold=hot))
        b.append(txt(500, ry, conc, 9.5, INK))
        b.append(badge(528, ry - 15, c1, GREEN if c1 == "fuse" else RED,
                       size=8.8, h=17))
        b.append(badge(586, ry - 15, c2, GREEN if c2 == "fuse" else RED,
                       size=8.8, h=17))
        b.append(badge(644, ry - 15, lib, GREEN if lib == "fuse" else RED,
                       size=8.8, h=17))
        b.append(txt(690, ry, why, 9.3, color if hot else INK))
        ry += 25

    b.append(txt(52, ry + 8, "读法：前 8 行「合法 = False」是结构负例（图非法，理由"
                 "都是「合法性：L…」）；后 8 行全部「合法 = True」，", 10.5, INK))
    b.append(txt(62, ry + 28, "但库判决分两半——拒绝理由的前缀说清归属：「保守策略」＝"
                 "收益层、「重算账」＝D75 扩展②、「并行度」＝D75 扩展③。", 10.5, INK))
    b.append(txt(62, ry + 48, "R1ctl 的 auto=fuse 与 R1 的 auto=refuse 对照读："
                 "一个组外使用者把 +6 MiB 翻成 −2 MiB。", 10.5, ORANGE, bold=True))

    # 底部：判据分层卡
    y0 = ry + 78
    b.append(panel_title(40, y0, "判据分层：谁在拒绝（C6：案例库不做统一计价，那是 D76）",
                         BLUE))
    cards = [
        ("合法性层 L1–L6", "结构负例 8 例：模式 / 纯度 / Shape / dtype / 使用者"
         "＋新补的 L3b 边形状、L6 拓扑序", "理由前缀：合法性：", BLUE),
        ("收益层 D74 门", "R1/R2：ΔB（D72）− spill 流量（D73）；conservative 拒 "
         "spill＞0，auto 拒 net≤0", "理由前缀：保守策略：", GREEN),
        ("D75 扩展②/③", "R3：重算流量账（消除 − 重读罚）；R4：舒适区阈值"
         "（零 spill＋staging ok＋并发≥3）", "理由前缀：重算账： / 并行度：", ORANGE),
    ]
    for i, (name, rule, note, color) in enumerate(cards):
        x = 56 + i * 366
        b.append(sketch_rect(x, y0 + 14, 348, 110, fill=TINT["white"],
                             stroke=color, sw=2.0))
        b.append(txt(x + 14, y0 + 38, name, 11.5, color, bold=True))
        b.append(txt(x + 14, y0 + 62, rule, 9.8, INK))
        b.append(txt(x + 14, y0 + 88, note, 9.8, MUTED))
        if i < 2:
            b.append(sketch_line(x + 352, y0 + 70, x + 364, y0 + 70,
                                 stroke=MUTED, sw=1.6, arrow=True))
    b.append(txt(56, y0 + 148, "案例库的价值：16 例全部有「预期判决」断言（测试 F2）——"
                 "以后改门改账本，先过案例库，再谈优化", 11, GREEN, bold=True))
    save("04-case-library.svg", "".join(b))


if __name__ == "__main__":
    fig1()
    fig2()
    fig3()
    fig4()
    print("done.")
