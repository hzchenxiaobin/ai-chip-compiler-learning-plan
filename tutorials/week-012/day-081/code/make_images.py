#!/usr/bin/env python3
"""生成第 81 天教程的 4 张手绘风（Excalidraw-like）SVG 技术图。

运行方式：
    python3 make_images.py

输出到 ../images/ 目录：
    01-overview.svg   今天在数值精度周中的位置 + 量化五步流水线
    02-mechanism.svg  仿射映射：float 数轴 -> int8 档位轴（scale / zp / 舍入 / 饱和）
    03-sym-asym.svg   偏斜数据上对称 vs 非对称（真实实验 3 数据）
    04-matmul.svg     INT8 MatMul 预览：INT32 累加 + 反量化（真实实验 5 数据）

风格与 Day 78/79/80 保持一致：手绘抖动线条、马克笔笔触、米白背景、
蓝/橙/绿/红四种柔和强调色、简单几何形状。
图中数值全部来自 quant_lab.py 的真实运行结果。
"""

import math
import random
from pathlib import Path

random.seed(81)

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
    ang = math.atan2(y2 - y1, x2 - x1)
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
# 图 1：全局定位 + 量化五步流水线
# ---------------------------------------------------------------------------

def fig1():
    b = []
    b.append(text(55, 54, "第 81 天：INT8 量化基础", 27))
    b.append(text(55, 82, "—— 把连续刻度装进 256 个格子：Scale 定格宽、Zero Point 定原点、饱和守边界", 16, SOFT, rot=-0.4))

    # 本周日程
    b.append(text(55, 120, "本周：数值精度与量化周（第 12 周）", 13, SOFT))
    week = [
        ("Day 78", "浮点格式 + 累加误差", "误差为什么来"),
        ("Day 79", "参考实现 + 误差指标", "造出判 PASS/FAIL 的尺子"),
        ("Day 80", "FP16/BF16 三旋钮实验", "量出三笔税的单价"),
        ("Day 81 · 今天", "INT8 量化基础", "Scale / zp / 饱和"),
        ("Day 82", "量化图中的 Cast 与 QDQ", "Q→DQ 的优化边界"),
    ]
    xs = [50, 232, 414, 596, 778]
    for i, ((cap, main, sub), x) in enumerate(zip(week, xs)):
        hot = i == 3
        b.append(srect(x, 130, 172, 74,
                       L_ORANGE if hot else "none",
                       ORANGE if hot else INK, 3.0 if hot else 2.2))
        b.append(text(x + 86, 152, cap, 14, SOFT, "middle"))
        b.append(text(x + 86, 172, main, 13.5, INK, "middle"))
        b.append(text(x + 86, 194, sub, 12, RED if hot else SOFT, "middle"))
    for x in (228, 410, 592, 774):
        b.append(arrow(x, 165, x + 11, 165))

    # 五步流水线
    b.append(text(55, 250, "今天的流水线（per-tensor：一个 scale + 一个 zp 管整个张量）", 13, SOFT))
    steps = [
        ("① 校准", "min/max 或分位数", 150, None),
        ("② 选方案", "对称 / 非对称", 140, None),
        ("③ 算参数", "scale, zero_point", 170, BLUE),
        ("④ 量化", "round + 平移 + 饱和", 190, None),
        ("⑤ 反量化 + 验证", "范围内误差 ≤ 1 格", 160, None),
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

    # 三个核心概念卡片
    b.append(text(55, 368, "今天要拧的三个旋钮（例子：ReLU 后的激活 x = [0, 0.5, 1.0, 2.0, 3.5]）：", 14.5, INK))
    cards = [
        ("Scale（刻度）", "一格代表多少 float", "例：范围 [0, 3.5] → 3.5/255 = 0.0137", "范围越小格越细 —— 校准的使命", BLUE),
        ("Zero Point（零点）", "float 0 对齐哪一档", "例：zp = −128，x = 0 精确还原", "对称方案 zp = 0（255 档）", GREEN),
        ("饱和（Saturation）", "范围外的值夹到边界档", "例：5.0 → 3.5（不夹则回绕成 1.48）", "离群点被牺牲 → 分位数校准", RED),
    ]
    cx = [50, 355, 660]
    for (t1, t2, t3, t4, color), x in zip(cards, cx):
        b.append(srect(x, 382, 290, 100, "none", color, 2.6))
        b.append(text(x + 16, 408, t1, 16, color))
        b.append(text(x + 16, 432, t2, 13, INK))
        b.append(text(x + 16, 456, t3, 12.5, SOFT))
        b.append(text(x + 16, 476, t4, 12.5, SOFT))

    # 贯穿问题
    b.append(srect(50, 510, 880, 84, L_RED, RED, 2.4))
    b.append(text(66, 538, "贯穿问题：把 [0, 0.5, 1.0, 2.0, 3.5] 存进 int8（每元素 1 字节）再还原，误差能压到多少、", 15.5, INK))
    b.append(text(66, 562, "靠哪三个旋钮？—— 昨天说过：FP16 的输入税 4.9e-4 是格式给定、听天由命；", 15.5, INK))
    b.append(text(66, 584, "INT8 只有 256 档，税必须自己设计 —— 今天手算 + 12 个边界测试 + 5 个实验，全部真实运行。", 12.5, SOFT))
    return svg_doc(960, 614, "".join(b))


# ---------------------------------------------------------------------------
# 图 2：仿射映射 —— 双数轴 + 舍入 + 饱和
# ---------------------------------------------------------------------------

FX0, FX1 = 120, 760       # float 数轴像素范围
IX0, IX1 = 120, 760       # int8 数轴像素范围
XMAX = 3.5


def fx(v):
    return FX0 + v / XMAX * (FX1 - FX0)


def ix(q):
    return IX0 + (q + 128) / 255.0 * (IX1 - IX0)


def fig2():
    b = []
    b.append(text(55, 50, "仿射映射：float 数轴怎么压进 int8 的 256 档", 26))
    b.append(text(55, 78, "非对称方案，校准范围 [0, 3.5]（实验 1 真实数据：scale = 0.013725，zp = −128）", 14.5, SOFT))

    # 公式框
    b.append(srect(580, 96, 350, 56, L_BLUE, BLUE, 2.2))
    b.append(text(596, 119, "量化：q = round( x / scale ) + zp", 14.5, BLUE))
    b.append(text(596, 142, "反量化：x̂ = scale × ( q − zp )", 14.5, GREEN))

    # float 数轴
    yF = 186
    b.append(text(55, 152, "float 数轴（校准范围）", 13.5, SOFT))
    b.append(sline(FX0, yF, FX1, yF, INK, 2.6) + head(FX1, yF, 0, INK, 2.6))
    for v in (0.0, 0.5, 1.0, 1.75, 2.0, 3.5):
        x = fx(v)
        b.append(sline(x, yF - 9, x, yF + 9, INK, 2.0, amp=0.6))
        b.append(text(x, yF - 16, f"{v:g}", 12.5, SOFT, "middle"))
    b.append(dot(fx(0.0), yF, BLUE, 6))
    b.append(dot(fx(3.5), yF, ORANGE, 6))

    # 映射箭头
    yI = 372
    pairs = [(0.0, -128, BLUE, "zp：float 0 ↔ q = −128"),
             (0.5, -92, INK, "0.5/0.0137 ≈ 36 格 → q = 36−128 = −92"),
             (1.0, -55, INK, None),
             (1.75, 0, SOFT, "范围正中 → q = 0"),
             (2.0, 18, INK, None),
             (3.5, 127, ORANGE, "max 端 ↔ q = 127")]
    for v, q, color, label in pairs:
        x1, x2 = fx(v), ix(q)
        b.append(arrow(x1, yF + 14, x2, yI - 14, color, 2.0, dash="6 4" if color == SOFT else None))
        if label and v in (0.0, 0.5, 3.5):
            b.append(text(x1 + 10, yF + 44 + (26 if v == 0.5 else 0), label, 12.5, color))
    b.append(text(fx(1.75) + 8, yF + 40, "正中 → q = 0", 12, SOFT))

    # scale 标注（相邻档）
    b.append(srect(fx(2.0) + 14, yI - 84, 190, 40, "none", GREEN, 1.8, amp=0.8))
    b.append(text(fx(2.0) + 24, yI - 68, "相邻两档相差 scale", 12.5, GREEN))
    b.append(text(fx(2.0) + 24, yI - 52, "1 格 = 0.013725", 12.5, GREEN))
    b.append(carrow((fx(2.0) + 10, yI - 44), (fx(2.0) + 20, yI - 20), (ix(18), yI - 8), GREEN, 1.8))

    # int8 档位轴
    b.append(text(55, yI + 52, "int8 档位轴（256 档，每元素 1 字节）", 13.5, SOFT))
    b.append(sline(IX0, yI, IX1, yI, INK, 2.6) + head(IX1, yI, 0, INK, 2.6))
    for q in range(-128, 128, 16):
        x = ix(q)
        b.append(sline(x, yI - 6, x, yI + 6, "#d8d2c6", 1.6, amp=0.5))
    for q in (-128, -92, -55, 0, 18, 127):
        x = ix(q)
        b.append(sline(x, yI - 10, x, yI + 10, INK, 2.0, amp=0.6))
        b.append(text(x, yI + 30, str(q), 12.5, SOFT, "middle"))
    b.append(dot(ix(-128), yI, BLUE, 6))
    b.append(dot(ix(127), yI, ORANGE, 6))

    # 左下：舍入
    b.append(srect(55, yI + 66, 430, 96, L_GREEN, GREEN, 2.4))
    b.append(text(71, yI + 92, "就近舍入：误差 ≤ 半格（放大镜里的档位）", 13.5, INK))
    for i in range(4):
        x = 95 + i * 60
        b.append(sline(x, yI + 104, x, yI + 146, GREEN, 2.2, amp=0.6))
    b.append(dot(152, yI + 125, RED, 6))
    b.append(arrow(152, yI + 125, 157, yI + 125, RED, 2.0))
    b.append(text(285, yI + 122, "落在两格之间 → 就近靠档", 12.5, INK))
    b.append(text(285, yI + 142, "≤ scale/2 = 0.0069；zp 取整再添 ≤ 半格", 12.5, INK))
    b.append(text(285, yI + 158, "→ 总误差上界 1 格（scale）", 12.5, SOFT))

    # 右下：饱和
    b.append(srect(510, yI + 66, 430, 96, L_RED, RED, 2.4))
    b.append(text(526, yI + 92, "饱和：范围是一堵墙（实验 2 真实数据）", 13.5, INK))
    b.append(sline(560, yI + 140, 880, yI + 140, INK, 2.2))
    wall = ix(127) - 240 + 500  # 墙画在 3.5 档
    wall = 840
    b.append(sline(wall, yI + 118, wall, yI + 152, RED, 3.2, amp=0.6))
    for i in range(6):
        b.append(sline(wall + 6 + i * 7, yI + 152 - i * 5, wall + 12 + i * 7, yI + 156 - i * 5, RED, 1.6, amp=0.4))
    b.append(dot(800, yI + 140, RED, 6))
    b.append(text(800, yI + 134, "5.0", 12, RED, "middle"))
    b.append(carrow((802, yI + 132), (820, yI + 118), (wall - 4, yI + 134), RED, 2.0))
    b.append(text(560, yI + 122, "5.0 撞墙 → 夹到 3.5（q = 127）", 12.5, INK))
    b.append(text(560, yI + 164, "误差 = 到墙的距离 1.5；不夹会回绕成 1.48 —— 见右上图", 12, SOFT))
    return svg_doc(960, yI + 176, "".join(b))


# ---------------------------------------------------------------------------
# 图 3：对称 vs 非对称（真实实验 3 数据）
# ---------------------------------------------------------------------------

def fig3():
    b = []
    b.append(text(55, 50, "对称 vs 非对称：偏斜数据上，一半档位在白白睡觉", 26))
    b.append(text(55, 78, "真实数据（实验 3，4096 个 uniform(0,4) 模拟 ReLU 后激活，种子 81）", 14.5, SOFT))

    BAR0, BAR1 = 70, 890
    BW = BAR1 - BAR0

    # 对称条：范围 [-4, +4]，数据全在右半
    y1 = 150
    b.append(text(55, 126, "对称（zp = 0，只用 [-127,127] 共 255 档）", 13.5, INK))
    b.append(srect(BAR0, y1, BW, 40, "#efe9dd", INK, 2.2))
    b.append(srect(BAR0 + BW / 2, y1, BW / 2, 40, L_GREEN, INK, 1.8))
    b.append(text(BAR0 + 30, y1 + 25, "[-4, 0)：一半档位闲置（数据从不为负）", 12.5, SOFT))
    b.append(text(BAR0 + BW / 2 + 24, y1 + 25, "[0, +4]：128/255 档", 12.5, GREEN))
    for v in (0.0, 0.5, 1.0, 1.75, 2.0, 3.0, 3.5):
        b.append(dot(BAR0 + BW / 2 + v / 4 * (BW / 2), y1 + 20, GREEN, 5))
    for v, lab in ((-4.0, "-4"), (0.0, "0"), (4.0, "+4")):
        x = BAR0 + (v + 4) / 8 * BW
        b.append(sline(x, y1 - 8, x, y1 + 48, INK, 1.6, amp=0.5, dash="4 4"))
        b.append(text(x, y1 + 64, lab, 12, SOFT, "middle"))
    b.append(text(910, y1 + 26, "scale 0.03147", 12, RED))

    # 非对称条：范围 [0, +4]
    y2 = 262
    b.append(text(55, 238, "非对称（zp = −128，256 档全给数据用）", 13.5, INK))
    b.append(srect(BAR0, y2, BW, 40, L_BLUE, INK, 2.2))
    b.append(text(BAR0 + 24, y2 + 25, "[0, +4]：256/256 档，格子细一倍", 12.5, BLUE))
    for v in (0.0, 0.5, 1.0, 1.75, 2.0, 3.0, 3.5):
        b.append(dot(BAR0 + v / 4 * BW, y2 + 20, BLUE, 5))
    for v, lab in ((0.0, "0"), (4.0, "+4")):
        x = BAR0 + v / 4 * BW
        b.append(sline(x, y2 - 8, x, y2 + 48, INK, 1.6, amp=0.5, dash="4 4"))
        b.append(text(x, y2 + 64, lab, 12, SOFT, "middle"))
    b.append(text(910, y2 + 26, "scale 0.01567", 12, GREEN))

    # 对照表
    ty = 356
    b.append(srect(55, ty, 480, 130, "none", INK, 2.0))
    cols = [70, 200, 330, 460]
    heads = ["", "对称", "非对称", "比值"]
    for x, h_ in zip(cols, heads):
        b.append(text(x, ty + 26, h_, 13.5, INK, "middle"))
    b.append(sline(55, ty + 36, 535, ty + 36, INK, 1.6, amp=0.6))
    rows = [("scale", "0.03147", "0.01567", "2.01×"),
            ("max|err|", "0.01573", "0.00784", "2.01×"),
            ("rms", "0.00905", "0.00454", "1.99×"),
            ("档位利用", "128/255", "256/256", "50%")]
    for i, r in enumerate(rows):
        yy = ty + 60 + i * 26
        if i % 2 == 0:
            b.append(srect(55, yy - 18, 480, 24, "#f7f2e8", INK, 1.2, amp=0.6))
        b.append(text(cols[0], yy, r[0], 13, INK, "middle"))
        b.append(text(cols[1], yy, r[1], 13, RED, "middle"))
        b.append(text(cols[2], yy, r[2], 13, GREEN, "middle"))
        b.append(text(cols[3], yy, r[3], 13, SOFT, "middle"))

    # 对照框：对称数据
    b.append(srect(560, ty, 370, 62, L_GREEN, GREEN, 2.2))
    b.append(text(576, ty + 24, "对照：对称数据 uniform(−4,4) 上两者打平", 13, INK))
    b.append(text(576, ty + 46, "对称 0.0315 / 0.0157  vs  非对称 0.0313 / 0.0157", 12, SOFT))

    # 结论框
    b.append(srect(560, ty + 76, 370, 54, L_ORANGE, ORANGE, 2.2))
    b.append(text(576, ty + 100, "选型：贴 0 对称 → 对称（MatMul 反量化免修正）；", 12.5, INK))
    b.append(text(576, ty + 120, "偏向一边 → 非对称（误差省一半）。", 12.5, INK))
    b.append(text(576, ty + 138, "工程惯例：权重常对称、激活常非对称。", 12, SOFT))
    return svg_doc(960, ty + 150, "".join(b))


# ---------------------------------------------------------------------------
# 图 4：INT8 MatMul 预览（真实实验 5 数据）
# ---------------------------------------------------------------------------

def fig4():
    b = []
    b.append(text(55, 48, "INT8 MatMul 预览：整数版的「低精度输入 + 高精度累加」", 25))
    b.append(text(55, 76, "对称量化（zp=0）让反量化只需乘 sa·sb；全部真实运行（2×3 @ 3×2，Day 79 的贯穿例子）", 14, SOFT))

    y0 = 100
    # ① 量化
    b.append(srect(55, y0, 195, 150, L_BLUE, BLUE, 2.4))
    b.append(text(152, y0 + 24, "① 对称量化", 14.5, BLUE, "middle"))
    b.append(text(152, y0 + 46, "sa = sb = 3.0/127", 12.5, INK, "middle"))
    b.append(text(152, y0 + 64, "= 0.023622", 12.5, INK, "middle"))
    b.append(text(152, y0 + 88, "Qa = [ 4  8 13]", 12, INK, "middle"))
    b.append(text(152, y0 + 106, "     [42 85 127]", 12, INK, "middle"))
    b.append(text(152, y0 + 128, "Qb = [17 42; 21 85;", 12, INK, "middle"))
    b.append(text(152, y0 + 146, "      25 127]", 12, INK, "middle"))
    b.append(arrow(255, y0 + 75, 285, y0 + 75))

    # ② INT32 累加
    b.append(srect(289, y0, 200, 150, L_GREEN, GREEN, 2.6))
    b.append(text(389, y0 + 24, "② INT32 累加", 14.5, GREEN, "middle"))
    b.append(text(389, y0 + 48, "Qa@Qb =", 12.5, INK, "middle"))
    b.append(text(389, y0 + 72, "[  561   2499]", 13, INK, "middle"))
    b.append(text(389, y0 + 94, "[5674  25118]", 13, INK, "middle"))
    b.append(text(389, y0 + 124, "int8 输入进 int32 桶", 12, SOFT, "middle"))
    b.append(text(389, y0 + 142, "（乘法、加法都精确）", 12, SOFT, "middle"))
    b.append(arrow(494, y0 + 75, 524, y0 + 75))

    # ③ 反量化
    b.append(srect(528, y0, 185, 150, "none", INK, 2.2))
    b.append(text(620, y0 + 24, "③ 反量化", 14.5, INK, "middle"))
    b.append(text(620, y0 + 48, "C = sa·sb·(Qa@Qb)", 12.5, INK, "middle"))
    b.append(text(620, y0 + 72, "≈ [0.313  1.394]", 13, INK, "middle"))
    b.append(text(620, y0 + 94, "  [3.166 14.016]", 13, INK, "middle"))
    b.append(text(620, y0 + 124, "只乘一个标量", 12, SOFT, "middle"))
    b.append(text(620, y0 + 142, "（zp = 0 的红利）", 12, SOFT, "middle"))
    b.append(arrow(718, y0 + 75, 748, y0 + 75))

    # ④ 对账
    b.append(srect(752, y0, 178, 150, L_ORANGE, ORANGE, 2.4))
    b.append(text(841, y0 + 24, "④ 对账", 14.5, ORANGE, "middle"))
    b.append(text(841, y0 + 48, "golden(FP64) =", 12, INK, "middle"))
    b.append(text(841, y0 + 70, "[0.32  1.4]", 12.5, INK, "middle"))
    b.append(text(841, y0 + 88, "[3.2   14.0]", 12.5, INK, "middle"))
    b.append(text(841, y0 + 114, "max_abs = 0.0339", 12.5, RED, "middle"))
    b.append(text(841, y0 + 134, "rel_F = 0.0027", 13, RED, "middle"))

    # 溢出实测框
    y1 = 286
    b.append(srect(55, y1, 430, 150, L_RED, RED, 2.4))
    b.append(text(71, y1 + 26, "累加器位宽实测：[[127,127]] @ [[127],[127]]", 13.5, INK))
    b.append(text(71, y1 + 50, "真值 = 127×127×2 = 32258", 13.5, INK))
    b.append(text(71, y1 + 74, "int8 累加（numpy int8@int8）→ 2", 13.5, RED))
    b.append(text(160, y1 + 92, "↑ 溢出回绕：32258 mod 256 = 2", 11.5, RED))
    b.append(text(71, y1 + 114, "int32 累加（显式 cast）→ 32258 ✓", 13.5, GREEN))
    b.append(text(71, y1 + 138, "容量：单项最大 16129；int16 在 K=3 就爆，int32 可撑 K≈13.3 万", 11.5, SOFT))

    # 硬件与字节框
    b.append(srect(510, y1, 430, 150, L_BLUE, BLUE, 2.4))
    b.append(text(526, y1 + 26, "这套配方在哪？", 13.5, INK))
    b.append(text(526, y1 + 50, "昇腾 Cube / GPU Tensor Core 的 INT8 模式：", 13, INK))
    b.append(text(526, y1 + 72, "INT8 输入 + INT32 累加（Day 80 浮点配方的整数版）", 13, BLUE))
    b.append(text(526, y1 + 98, "字节账（nbytes 实测，单个 512×512 矩阵）：", 12.5, INK))
    b.append(text(526, y1 + 120, "fp32 1.00 MiB → fp16 0.50 MiB → int8 0.25 MiB", 13, GREEN))
    b.append(text(526, y1 + 142, "误差全来自输入量化档位；累加与反量化本身不添税", 11.5, SOFT))
    return svg_doc(960, y1 + 168, "".join(b))


# ---------------------------------------------------------------------------

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    figs = {
        "01-overview.svg": fig1(),
        "02-mechanism.svg": fig2(),
        "03-sym-asym.svg": fig3(),
        "04-matmul.svg": fig4(),
    }
    for name, content in figs.items():
        path = OUT / name
        path.write_text(content, encoding="utf-8")
        print(f"写入 {path}（{path.stat().st_size} 字节）")


if __name__ == "__main__":
    main()
