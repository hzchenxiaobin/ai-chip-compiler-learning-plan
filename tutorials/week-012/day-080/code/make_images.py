#!/usr/bin/env python3
"""生成第 80 天教程的 4 张手绘风（Excalidraw-like）SVG 技术图。

运行方式：
    python3 make_images.py

输出到 ../images/ 目录：
    01-overview.svg   今天在数值精度周中的位置 + 三旋钮实验流水线
    02-mechanism.svg  三处精度旋钮在 MatMul 数据通路上的位置与机制
    03-ksweep.svg     K 扫描真实数据：FP16 累加税随 K 增长，FP32 累加不动
    04-table.svg      六组合精度对照表（数据来自 precision_sweep.py 实际运行）

风格与 Day 78/79 保持一致：手绘抖动线条、马克笔笔触、米白背景、
蓝/橙/绿/红四种柔和强调色、简单几何形状。
"""

import math
import random
from pathlib import Path

random.seed(80)

INK = "#3b3b3b"
SOFT = "#6b6459"
BLUE = "#5f8fcb"
ORANGE = "#e8973f"
GREEN = "#79b26a"
RED = "#d96c5c"
BG = "#fdf9f0"
L_BLUE = "#dbe7f6"
L_ORANGE = "#fdead3"
L_GREEN = "#e5f1dc"
L_RED = "#f9dfd9"
FONT = "'Comic Sans MS','Segoe Print','Bradley Hand','Kaiti SC','KaiTi','STKaiti',cursive"

OUT = Path(__file__).resolve().parent.parent / "images"


def jseg(x1, y1, x2, y2, amp=1.3):
    dx, dy = (x2 - x1) / 2.0, (y2 - y1) / 2.0
    a = random.uniform(-amp, amp)
    b = random.uniform(-amp, amp)
    c = random.uniform(-amp, amp)
    d = random.uniform(-amp, amp)
    e = random.uniform(-amp, amp)
    f = random.uniform(-amp, amp)
    return (f"M {x1 + a:.1f},{y1 + b:.1f} Q {x1 + dx + c:.1f},{y1 + dy + d:.1f} "
            f"{x2 + e:.1f},{y2 + f:.1f}")


def style(fill="none", stroke=INK, sw=2.2, dash=None):
    s = f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round"'
    if dash:
        s += f' stroke-dasharray="{dash}"'
    return s


def srect(x, y, w, h, fill="none", stroke=INK, sw=2.2, amp=1.3, dash=None):
    pts = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
    d = " ".join(jseg(*p, *q, amp) for p, q in zip(pts, pts[1:] + pts[:1]))
    return f'<path d="{d} Z" {style(fill, stroke, sw, dash)}/>'


def sline(x1, y1, x2, y2, stroke=INK, sw=2.2, dash=None, amp=1.3):
    return f'<path d="{jseg(x1, y1, x2, y2, amp)}" {style("none", stroke, sw, dash)}/>'


def head(x, y, ang, stroke, sw, l=13, spread=0.46):
    a1 = (x - l * math.cos(ang - spread), y - l * math.sin(ang - spread))
    a2 = (x - l * math.cos(ang + spread), y - l * math.sin(ang + spread))
    return (f'<path d="{jseg(x, y, a1[0], a1[1], 0.7)}" {style("none", stroke, sw)}/>'
            f'<path d="{jseg(x, y, a2[0], a2[1], 0.7)}" {style("none", stroke, sw)}/>')


def arrow(x1, y1, x2, y2, stroke=INK, sw=2.2, dash=None):
    ang = math.atan2(y2 - y1, x2 - y1)
    return (f'<path d="{jseg(x1, y1, x2, y2)}" {style("none", stroke, sw, dash)}/>'
            + head(x2, y2, ang, stroke, sw))


def carrow(p0, ctrl, p1, stroke=INK, sw=2.2, dash=None):
    d = f"M {p0[0]:.1f},{p0[1]:.1f} Q {ctrl[0]:.1f},{ctrl[1]:.1f} {p1[0]:.1f},{p1[1]:.1f}"
    ang = math.atan2(p1[1] - ctrl[1], p1[0] - ctrl[0])
    return f'<path d="{d}" {style("none", stroke, sw, dash)}/>' + head(p1[0], p1[1], ang, stroke, sw)


def text(x, y, s, size=16, fill=INK, anchor="start", rot=None):
    t = f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-size="{size}" fill="{fill}"'
    if rot:
        t += f' transform="rotate({rot} {x} {y})"'
    return t + f">{s}</text>"


def svg_doc(w, h, body):
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d">' % (w, h, w, h)
            + f'<rect x="3" y="3" width="{w - 6}" height="{h - 6}" rx="7" fill="{BG}"/>'
            + f'<g font-family="{FONT}">' + body + "</g></svg>")


def dot(x, y, color, r=7):
    return (f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{color}" '
            f'stroke="{INK}" stroke-width="1.8"/>')


# ---------------------------------------------------------------------------
# 图 1：全局定位 + 三旋钮实验流水线
# ---------------------------------------------------------------------------

def fig1():
    b = []
    b.append(text(55, 54, "第 80 天：FP16 / BF16 测试", 27))
    b.append(text(55, 82, "—— 低精度输入、高精度累加、输出只舍一刀：三笔账分开算", 16, SOFT, rot=-0.4))

    # 本周日程
    b.append(text(55, 120, "本周：数值精度周（第 12 周）", 13, SOFT))
    week = [
        ("Day 78", "浮点格式 + 累加误差", "知道误差为什么会来", None),
        ("Day 79", "参考实现 + 误差指标", "造出判 PASS/FAIL 的尺子", None),
        ("Day 80 · 今天", "FP16/BF16 三旋钮实验", "量出三笔税的单价", None),
        ("Day 81", "INT8 量化基础", "Scale / Zero Point", None),
    ]
    xs = [50, 272, 494, 716]
    for i, ((cap, main, sub, _), x) in enumerate(zip(week, xs)):
        hot = i == 2
        b.append(srect(x, 130, 205, 74,
                       L_ORANGE if hot else "none",
                       ORANGE if hot else INK, 3.0 if hot else 2.2))
        b.append(text(x + 102, 152, cap, 14, SOFT, "middle"))
        b.append(text(x + 102, 172, main, 14.5, INK, "middle"))
        b.append(text(x + 102, 194, sub, 12, RED if hot else SOFT, "middle"))
    for x in (258, 480, 702):
        b.append(arrow(x, 165, x + 11, 165))

    # 三旋钮实验流水线
    b.append(text(55, 250, "今天的实验流水线（测量仪 check_close / TOLERANCES 从 Day 79 原样搬来）", 13, SOFT))
    steps = [
        ("① 固定输入", "2x3 例子 + 随机 64x64", 168, None),
        ("② 拧组合", "六种 输入×累加×输出", 150, None),
        ("③ 双 golden 对账", "FP64 vs 量化输入版", 178, BLUE),
        ("④ 扫 K", "16 → 4096", 96, None),
        ("⑤ 字节 + 耗时", "全部实测", 138, None),
    ]
    x = 50
    xs2 = []
    for t1, t2, w, hc in steps:
        xs2.append((x, w))
        hot = hc is not None
        b.append(srect(x, 262, w, 64, L_BLUE if hot else "none",
                       hc if hot else INK, 2.6 if hot else 2.2))
        b.append(text(x + w / 2, 286, t1, 15, INK, "middle"))
        b.append(text(x + w / 2, 310, t2, 12.5, SOFT, "middle"))
        x += w + 15
    for i in range(len(xs2) - 1):
        x0, w0 = xs2[i]
        x1, _ = xs2[i + 1]
        b.append(arrow(x0 + w0 + 3, 294, x1 - 4, 294))

    # 三笔税
    b.append(text(55, 368, "今天要量出来的三笔“税”（分别挂在三个旋钮上，增长率完全不同）：", 14.5, INK))
    cards = [
        ("输入格式税", "一次性，与 K 无关", "FP16 ≈ 4.9e-4 / BF16 ≈ 3.9e-3", "可被对齐 golden 消掉", BLUE),
        ("累加税", "随 K 增长（√K 随机游走）", "FP32 累加 ~1e-6 可忽略；", "FP16 累加 6.4e-4 → 9.4e-3", RED),
        ("输出舍入税", "最后一刀 ≈ eps/2", "FP16 出 ~4.9e-4，省一半写回；", "超过 65504 → inf", ORANGE),
    ]
    cx = [50, 355, 660]
    for (t1, t2, t3, t4, color), x in zip(cards, cx):
        b.append(srect(x, 382, 290, 100, "none", color, 2.6))
        b.append(text(x + 16, 408, t1, 16, color))
        b.append(text(x + 16, 432, t2, 13, INK))
        b.append(text(x + 16, 456, t3, 12.5, SOFT))
        b.append(text(x + 16, 476, t4, 12.5, SOFT))

    # 贯穿问题
    b.append(srect(50, 510, 880, 76, L_RED, RED, 2.4))
    b.append(text(66, 538, "贯穿问题：同一个 MatMul，输入 / 累加 / 输出各用什么精度，误差和性能各付什么代价？", 15.5, INK))
    b.append(text(66, 562, "—— 今天用真实数据把三笔税的单价、增长率和归属性量出来，", 15.5, INK))
    b.append(text(66, 582, "再回答“低精度迁移到底值不值、错在哪”。（昨天造好的尺子，今天一把不动地复用。）", 12.5, SOFT))
    return svg_doc(960, 610, "".join(b))


# ---------------------------------------------------------------------------
# 图 2：三旋钮数据通路
# ---------------------------------------------------------------------------

def fig2():
    b = []
    b.append(text(55, 50, "三个旋钮挂在哪一站：一条 MatMul 数据通路", 26))
    b.append(text(55, 78, "乘法站免费精确，是“低精度输入 + 高精度累加”整条配方的数学底牌（数值全部真实运行）", 14.5, SOFT))

    y0 = 210

    # ① 输入站
    b.append(srect(55, y0 - 60, 150, 120, "none", INK, 2.2))
    b.append(text(130, y0 - 36, "A（2 字节/元素）", 13, INK, "middle"))
    b.append(text(130, y0 - 14, "B（2 字节/元素）", 13, INK, "middle"))
    b.append(text(130, y0 + 12, "fp16 / bf16", 13, BLUE, "middle"))
    b.append(srect(60, y0 - 96, 140, 26, L_BLUE, INK, 1.8, amp=0.8))
    b.append(text(130, y0 - 78, "旋钮① 输入精度", 13.5, INK, "middle"))
    b.append(text(130, y0 + 40, "0.1 →", 12.5, SOFT, "middle"))
    b.append(text(130, y0 + 58, "0.0999755859375", 11.5, SOFT, "middle"))

    b.append(arrow(210, y0, 258, y0))

    # ② 乘法站
    b.append(srect(262, y0 - 60, 170, 120, L_GREEN, GREEN, 2.6))
    b.append(srect(267, y0 - 96, 160, 26, "none", GREEN, 1.8, amp=0.8))
    b.append(text(347, y0 - 78, "旋钮② 乘法（免费精确）", 13, GREEN, "middle"))
    b.append(text(347, y0 - 34, "11 位 × 11 位", 14.5, INK, "middle"))
    b.append(text(347, y0 - 10, "= 22 位 ≤ 24 位", 14.5, INK, "middle"))
    b.append(text(347, y0 + 16, "FP32 桶装得下", 13.5, GREEN, "middle"))
    b.append(text(347, y0 + 44, "bf16: 8+8=16 位，更宽松", 11.5, SOFT, "middle"))

    b.append(arrow(437, y0, 485, y0))

    # ③ 累加站：两条路
    b.append(srect(490, y0 - 150, 200, 58, "none", INK, 1.8, amp=0.8))
    b.append(text(590, y0 - 114, "旋钮③ 累加精度", 13.5, INK, "middle"))
    # FP32 大桶
    b.append(srect(490, y0 - 84, 200, 78, L_GREEN, GREEN, 2.6))
    b.append(text(590, y0 - 58, "FP32 累加器（大桶）", 14, GREEN, "middle"))
    b.append(text(590, y0 - 34, "22 位乘积原样进 24 位桶", 12.5, INK, "middle"))
    b.append(text(590, y0 - 12, "税 ~1e-6，基本无损", 12.5, INK, "middle"))
    # FP16 漏桶
    b.append(srect(490, y0 + 8, 200, 92, L_RED, RED, 2.6))
    b.append(text(590, y0 + 32, "FP16 累加器（漏桶）", 14, RED, "middle"))
    b.append(text(590, y0 + 56, "每加一步舍回 11 位 + 吸收：", 12, INK, "middle"))
    b.append(text(590, y0 + 76, "2048 + 1 → 2048", 13, RED, "middle"))
    b.append(text(590, y0 + 94, "税随 K 按 √K 增长", 12, INK, "middle"))
    # 漏桶裂缝
    b.append(sline(560, y0 + 100, 585, y0 + 88, RED, 2.0, amp=0.6))
    b.append(sline(585, y0 + 88, 610, y0 + 100, RED, 2.0, amp=0.6))
    b.append(text(700, y0 + 104, "漏出去的：误差", 11.5, RED))

    b.append(arrow(695, y0 - 45, 743, y0 - 45))
    b.append(arrow(695, y0 + 54, 743, y0 + 54, RED, 2.0, dash="5 4"))

    # ④ 输出站
    b.append(srect(747, y0 - 96, 178, 110, "none", INK, 2.2))
    b.append(srect(752, y0 - 132, 168, 26, L_ORANGE, ORANGE, 1.8, amp=0.8))
    b.append(text(836, y0 - 114, "旋钮④ 输出精度", 13.5, INK, "middle"))
    b.append(text(836, y0 - 66, "FP32 出：0 刀", 13.5, GREEN))
    b.append(text(836, y0 - 44, "FP16 出：1 刀 ≈ 4.9e-4", 13.5, ORANGE))
    b.append(text(836, y0 - 20, "省一半写回带宽", 12, SOFT))
    # 65504 天花板
    b.append(sline(770, y0 + 8, 900, y0 + 8, INK, 2.2))
    b.append(text(836, y0 + 28, "天花板 65504", 12, INK, "middle"))
    b.append(text(836, y0 + 50, "180000 → inf ✗", 13, RED, "middle"))
    b.append(text(836, y0 + 70, "（FP32 出则安全）", 11.5, SOFT, "middle"))

    # 底部：真实数据注记
    b.append(srect(55, y0 + 130, 430, 92, L_RED, RED, 2.4))
    b.append(text(71, y0 + 156, "吸收的实测（实验 2，真实运行）：", 13.5, INK))
    b.append(text(71, y0 + 180, "4096 个 1.0 相加：FP32 累加 = 4096.0", 14, GREEN))
    b.append(text(71, y0 + 202, "FP16 累加 = 2048.0（卡死，差 50%）", 14, RED))
    b.append(text(71, y0 + 222, "numpy 的 fp16 @ 内部是 FP32 累加（位模式差 0 个码）", 11.5, SOFT))

    b.append(srect(510, y0 + 130, 430, 92, L_GREEN, GREEN, 2.4))
    b.append(text(526, y0 + 156, "精确乘法的实测（实验 1，真实运行）：", 13.5, INK))
    b.append(text(526, y0 + 180, "fp16入·fp32累·fp32出", 13.5, INK))
    b.append(text(526, y0 + 202, "对量化输入版 golden：max_abs = 0", 14, GREEN))
    b.append(text(526, y0 + 222, "乘法精确 + 3 项和恰好无舍入 → 零实现税", 11.5, SOFT))
    return svg_doc(960, y0 + 240, "".join(b))


# ---------------------------------------------------------------------------
# 图 3：K 扫描（真实数据）
# ---------------------------------------------------------------------------

KS = [16, 64, 256, 1024, 4096]
SERIES = [
    ("fp16入·fp16累·fp16出", RED,
     [6.445e-04, 1.203e-03, 2.390e-03, 4.754e-03, 9.379e-03]),
    ("fp16入·fp32累·fp32出", BLUE,
     [5.871e-08, 1.302e-07, 2.801e-07, 5.667e-07, 1.171e-06]),
    ("fp32入·fp32累·fp32出", INK,
     [7.806e-08, 1.484e-07, 2.914e-07, 5.808e-07, 1.128e-06]),
    ("bf16入·fp32累·fp32出", GREEN,
     [1.828e-08, 4.294e-08, 9.068e-08, 2.084e-07, 5.196e-07]),
]


def fig3():
    b = []
    b.append(text(55, 50, "K 扫描：FP16 累加税随 K 长，FP32 累加不动", 26))
    b.append(text(55, 78, "真实数据（M=N=64，种子 7）：rel_F = ‖C−golden‖F / ‖golden‖F，golden = 量化输入版 FP64", 14.5, SOFT))

    # 绘图区
    px0, px1 = 150, 880
    py0, py1 = 300, 110   # y 越小越高
    lo, hi = -8.0, -1.0   # log10 范围 1e-8 ~ 1e-1 上限留白

    def X(k):
        lk0, lk1 = math.log10(16), math.log10(4096)
        return px0 + (math.log10(k) - lk0) / (lk1 - lk0) * (px1 - px0)

    def Y(v):
        lv = math.log10(v)
        return py0 - (lv - lo) / (hi - lo) * (py0 - py1)

    # 网格线（数量级）
    for e in range(-8, 0):
        y = Y(10.0 ** e)
        b.append(sline(px0, y, px1, y, "#d8d2c6", 1.4, amp=0.5))
        b.append(text(px0 - 12, y + 5, f"1e{e}", 12, SOFT, "end"))
    # x 刻度
    for k in KS:
        x = X(k)
        b.append(sline(x, py0, x, py0 + 8, INK, 1.8, amp=0.6))
        b.append(text(x, py0 + 28, str(k), 13, SOFT, "middle"))
    b.append(sline(px0, py0, px1, py0, INK, 2.4))
    b.append(sline(px0, py0, px0, py1 - 10, INK, 2.4) + head(px0, py1 - 10, -math.pi / 2, INK, 2.4))
    b.append(text(px1, py0 + 48, "K（累加长度）→", 13.5, SOFT, "end"))
    b.append(text(64, 180, "rel_F", 14, SOFT, "middle", rot=-90))

    # 折线（手绘感：分段抖动线 + 数据点）
    label_off = {
        "fp16入·fp16累·fp16出": (-10, -14),
        "fp16入·fp32累·fp32出": (12, 6),
        "fp32入·fp32累·fp32出": (10, -12),
        "bf16入·fp32累·fp32出": (12, 6),
    }
    for name, color, vals in SERIES:
        pts = [(X(k), Y(v)) for k, v in zip(KS, vals)]
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            b.append(sline(x1, y1, x2, y2, color, 3.0, amp=1.0))
        for (x, y), v in zip(pts, vals):
            b.append(dot(x, y, color, 6))
        # 首点/末点标注
        x, y = pts[0]
        dx, dy = label_off[name]
        b.append(text(x + dx, y + dy, f"{vals[0]:.1e}", 11.5, color))
        x, y = pts[-1]
        b.append(text(x + dx, y + dy, f"{vals[-1]:.1e}", 11.5, color))

    # 图例
    lx, ly = 470, 118
    for i, (name, color, _) in enumerate(SERIES):
        yy = ly + i * 26
        b.append(sline(lx, yy - 5, lx + 34, yy - 5, color, 3.0, amp=0.8))
        b.append(text(lx + 44, yy, name, 13.5, INK))

    # √K 注记
    b.append(carrow((X(256), Y(2.390e-03) - 16), (X(700), Y(2.5e-03) - 60), (X(1024), Y(4.754e-03) - 26),
                    RED, 2.0, dash="5 4"))
    b.append(text(X(640), Y(4.2e-03) - 74, "K×256，误差×14.6 ≈ √256", 13, RED, "middle"))

    # 底注框
    b.append(srect(55, 352, 430, 108, L_BLUE, BLUE, 2.4))
    b.append(text(71, 378, "输入税去哪了？", 13.5, INK))
    b.append(text(71, 400, "golden 用的是“量化输入版”，输入税已被对齐掉；", 12.5, INK))
    b.append(text(71, 420, "所以三条 FP32 累加的线只剩累加税（1e-8~1e-6）。", 12.5, INK))
    b.append(text(71, 440, "要看输入税，得对 FP64 golden（见实验 1 / 图 4）。", 12.5, SOFT))

    b.append(srect(510, 352, 430, 108, L_ORANGE, ORANGE, 2.4))
    b.append(text(526, 378, "输出税对照（实验 4，K=4096，真实数据）：", 13.5, INK))
    b.append(text(526, 402, "fp16入·fp32累·fp32出：rel_F = 1.17e-6", 13.5, GREEN))
    b.append(text(526, 426, "fp16入·fp32累·fp16出：rel_F = 2.02e-4（一刀）", 13.5, ORANGE))
    b.append(text(526, 448, "一刀换来结果写回带宽减半 —— 归输出旋钮管。", 12.5, SOFT))
    return svg_doc(960, 480, "".join(b))


# ---------------------------------------------------------------------------
# 图 4：六组合精度对照表（真实数据）
# ---------------------------------------------------------------------------

def fig4():
    b = []
    b.append(text(55, 48, "精度对照表：六种组合 × 两个 golden（全部真实运行）", 24))
    b.append(text(55, 76, "数据来自 python3 precision_sweep.py（Python 3.11.4 + numpy 1.26.4，aarch64）；小例子 2x3@3x2，K=3", 13.5, SOFT))

    hx = [55, 345, 475, 605, 715, 835]
    heads = ["组合（输入·累加·输出）", "max_rel vs FP64", "实现税 max_abs", "字节 入/出", "判定"]
    widths = [290, 130, 130, 110, 120]
    b.append(srect(55, 96, 870, 34, L_BLUE, INK, 2.2))
    for x, w, h_ in zip(hx, widths, heads):
        b.append(text(x + w / 2, 119, h_, 13.5, INK, "middle"))
    b.append(text(945, 119, "", 12))

    rows = [
        ("fp32入·fp32累·fp32出（基准）", "6.8e-8", "5.2e-8", "4B/4B", "PASS", GREEN, None),
        ("fp16入·fp32累·fp32出", "6.1e-5 *", "0（零！）", "2B/4B", "FAIL *", RED,
         "* 格式税超 FP32 阈值，不是实现错"),
        ("fp16入·fp32累·fp16出", "2.8e-4", "9.8e-4（一刀）", "2B/2B", "PASS", GREEN, None),
        ("fp16入·fp16累·fp16出", "5.5e-4", "9.8e-4", "2B/2B", "PASS", GREEN,
         "K=3 看不出累加税；K=4096 → 9.4e-3"),
        ("bf16入·fp32累·fp32出", "3.5e-3 *", "0（零！）", "2B/4B", "FAIL *", RED, None),
        ("bf16入·fp32累·bf16出", "4.5e-3", "3.4e-3（一刀）", "2B/2B", "PASS", GREEN, None),
    ]
    y = 130
    rh = 46
    for i, (name, rel, tax, byt, verdict, color, note) in enumerate(rows):
        special = note is not None and "格式税" in note
        fill = L_ORANGE if special else ("#f7f2e8" if i % 2 == 0 else "none")
        b.append(srect(55, y, 870, rh, fill, INK, 1.6, amp=0.9))
        b.append(text(hx[0] + 14, y + 27, name, 13, INK))
        for x, w, v in zip(hx[1:4], widths[1:4], (rel, tax, byt)):
            b.append(text(x + w / 2, y + 27, v, 13, INK, "middle"))
        b.append(srect(hx[4] + 25, y + 8, 70, rh - 16,
                       "#e5f1dc" if verdict.startswith("PASS") else "#f9dfd9",
                       color, 2.4, amp=0.8))
        b.append(text(hx[4] + 60, y + 28, verdict, 14, color, "middle"))
        if note:
            b.append(text(hx[0] + 14, y + 42, "↑ " + note, 11.5, RED if special else SOFT))
        y += rh

    # 对齐 golden 一句话
    b.append(srect(55, y + 12, 870, 30, "none", INK, 1.6, amp=0.8))
    b.append(text(71, y + 33, "换成量化输入版 golden 后，六种组合实现税全部 PASS（Day 79 的方法：格式税交给阈值表宽容，不混进实现误差）",
                  12.5, INK))
    y += 42

    # 结论框
    b.append(srect(55, y + 10, 870, 108, L_ORANGE, ORANGE, 2.4))
    b.append(text(71, y + 36, "结论（今天的“精度对照表和结论”产出）：", 14.5, INK))
    b.append(text(71, y + 60, "① 推荐配方 = 低精度输入 + FP32 累加：输入税有界（4.9e-4 / 3.9e-3）且可对齐，乘法精确，累加税 ~1e-6；", 13.5, INK))
    b.append(text(71, y + 82, "② 输出按下游选：FP16 出付一刀 ~4.9e-4 换一半写回带宽，但防 65504 溢出；", 13.5, INK))
    b.append(text(71, y + 104, "③ 字节列解释了为什么低精度值得：输入字节直接减半（4B→2B）。", 13.5, INK))
    return svg_doc(960, y + 132, "".join(b))


# ---------------------------------------------------------------------------

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    figs = {
        "01-overview.svg": fig1(),
        "02-mechanism.svg": fig2(),
        "03-ksweep.svg": fig3(),
        "04-table.svg": fig4(),
    }
    for name, content in figs.items():
        path = OUT / name
        path.write_text(content, encoding="utf-8")
        print(f"写入 {path}（{path.stat().st_size} 字节）")


if __name__ == "__main__":
    main()
