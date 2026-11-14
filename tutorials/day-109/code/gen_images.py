#!/usr/bin/env python3
"""生成第 109 天的 3 张手绘 sketch 风 SVG 技术图（Excalidraw-like）。

风格约定：白板涂鸦感——线条用带抖动的贝塞尔手绘路径、马克笔笔触、
3～4 种柔和强调色（橙/蓝/绿/红）＋米白背景、简单几何形状、手写感字体。
所有数字来自 analyze.py 真实运行结果（code/outputs/，2026-11-13 最终一轮：
perf-table.txt / roofline.txt / probes.json / mean-vs-median.txt——屋顶读数取
probes.json 缓存：P_int=0.0547 GFLOPS、BW=0.385 GB/s、BW_C=2.68 GB/s，
kernel 时间取 D108 results.jsonl 的决赛中位数）。固定随机种子，保证图可复现。
"""

from __future__ import annotations

import math
import os
import random

random.seed(109)

BG = "#FDFBF6"
BORDER = "#E7DFCE"
INK = "#3B3B3B"
MUTED = "#6b6257"
ORANGE = "#E8A87C"
BLUE = "#A9C4D4"
GREEN = "#9CBF8E"
RED = "#C97B7B"
GRAYC = "#EDE7DA"
FONT = "'Comic Sans MS','Kaiti SC','KaiTi','STKaiti',cursive"


def jit(m=1.6):
    return random.uniform(-m, m)


def hand_rect(x, y, w, h, fill=BG, opacity=0.65, stroke=INK, sw=1.4, dash=None):
    pts = [(x + jit(), y + jit()), (x + w + jit(), y + jit()),
           (x + w + jit(), y + h + jit()), (x + jit(), y + h + jit())]
    d = f"M {pts[0][0]:.1f},{pts[0][1]:.1f} "
    for i in range(4):
        a, b = pts[i], pts[(i + 1) % 4]
        mx, my = (a[0] + b[0]) / 2 + jit(2.2), (a[1] + b[1]) / 2 + jit(2.2)
        d += f"Q {mx:.1f},{my:.1f} {b[0]:.1f},{b[1]:.1f} "
    dd = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<path d="{d} Z" stroke="{stroke}" stroke-width="{sw}" '
            f'stroke-linecap="round" stroke-linejoin="round" '
            f'fill="{fill}" fill-opacity="{opacity}"{dd}/>')


def hand_line(x1, y1, x2, y2, stroke=INK, sw=1.4, dash=None):
    dd = f' stroke-dasharray="{dash}"' if dash else ""
    mx, my = (x1 + x2) / 2 + jit(2.5), (y1 + y2) / 2 + jit(2.5)
    d = f"M {x1 + jit():.1f},{y1 + jit():.1f} Q {mx:.1f},{my:.1f} {x2 + jit():.1f},{y2 + jit():.1f}"
    return (f'<path d="{d}" stroke="{stroke}" stroke-width="{sw}" '
            f'stroke-linecap="round" fill="none"{dd}/>')


def hand_poly(pts, stroke=INK, sw=1.6, dash=None, fill="none"):
    """多点手绘折线（各段带轻微抖动）。"""
    dd = f' stroke-dasharray="{dash}"' if dash else ""
    d = f"M {pts[0][0] + jit():.1f},{pts[0][1] + jit():.1f} "
    for i in range(1, len(pts)):
        a, b = pts[i - 1], pts[i]
        mx, my = (a[0] + b[0]) / 2 + jit(1.8), (a[1] + b[1]) / 2 + jit(1.8)
        d += f"Q {mx:.1f},{my:.1f} {b[0] + jit():.1f},{b[1] + jit():.1f} "
    return (f'<path d="{d}" stroke="{stroke}" stroke-width="{sw}" '
            f'stroke-linecap="round" stroke-linejoin="round" fill="{fill}"{dd}/>')


def hand_ellipse(cx, cy, rx, ry, stroke=RED, sw=1.6, dash=None):
    """手绘椭圆：八段小贝塞尔拼一圈。"""
    dd = f' stroke-dasharray="{dash}"' if dash else ""
    n = 8
    pts = [(cx + rx * math.cos(2 * math.pi * i / n) + jit(1.5),
            cy + ry * math.sin(2 * math.pi * i / n) + jit(1.5)) for i in range(n + 1)]
    d = f"M {pts[0][0]:.1f},{pts[0][1]:.1f} "
    for i in range(1, n + 1):
        d += f"Q {(pts[i-1][0]+pts[i][0])/2 + jit(1.5):.1f},{(pts[i-1][1]+pts[i][1])/2 + jit(1.5):.1f} " \
             f"{pts[i][0]:.1f},{pts[i][1]:.1f} "
    return (f'<path d="{d}" stroke="{stroke}" stroke-width="{sw}" '
            f'stroke-linecap="round" fill="none"{dd}/>')


def dot(x, y, r=5.5, fill=ORANGE, stroke=INK, sw=1.3, hollow=False):
    f = "none" if hollow else fill
    return (f'<circle cx="{x + jit(0.8):.1f}" cy="{y + jit(0.8):.1f}" r="{r}" fill="{f}" '
            f'stroke="{stroke}" stroke-width="{sw}"/>')


def arrow(x1, y1, x2, y2, stroke=INK, sw=1.8, dash=None):
    dd = f' stroke-dasharray="{dash}"' if dash else ""
    mx, my = (x1 + x2) / 2 + jit(2.0), (y1 + y2) / 2 + jit(2.0)
    ang = math.atan2(y2 - y1, x2 - x1)
    hx, hy = x2 - 9 * math.cos(ang), y2 - 9 * math.sin(ang)
    a1 = (hx + 5 * math.cos(ang + 2.5), hy + 5 * math.sin(ang + 2.5))
    a2 = (hx + 5 * math.cos(ang - 2.5), hy + 5 * math.sin(ang - 2.5))
    d = (f"M {x1 + jit():.1f},{y1 + jit():.1f} Q {mx:.1f},{my:.1f} "
         f"{x2:.1f},{y2:.1f} M {a1[0]:.1f},{a1[1]:.1f} L {x2:.1f},{y2:.1f} "
         f"L {a2[0]:.1f},{a2[1]:.1f}")
    return (f'<path d="{d}" stroke="{stroke}" stroke-width="{sw}" '
            f'stroke-linecap="round" fill="none"{dd}/>')


def text(x, y, s, size=13, fill=INK, anchor="middle", bold=False, rotate=None):
    import xml.sax.saxutils as su
    s = su.escape(s)
    wt = ' font-weight="bold"' if bold else ""
    tr = f' transform="rotate({rotate} {x} {y})"' if rotate is not None else ""
    return (f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" '
            f'text-anchor="{anchor}"{wt}{tr}>{s}</text>')


def frame(w, h, title):
    body = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
            f'font-family="{FONT}">',
            hand_rect(4, 4, w - 8, h - 8, BG, 1.0, BORDER, 2),
            text(w / 2, 34, title, 19, INK, "middle", True)]
    return body


def save(name, body):
    out = os.path.join(os.path.dirname(__file__), "..", "images", name)
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(body) + "\n</svg>\n")
    print(f"  已生成 images/{name}")


def card(b, x, y, w, h, title, lines, fill, tsize=11.5, lsize=10, opacity=0.42):
    b.append(hand_rect(x, y, w, h, fill, opacity, INK, 1.6))
    b.append(text(x + w / 2, y + 19, title, tsize, INK, "middle", True))
    for i, ln in enumerate(lines):
        b.append(text(x + w / 2, y + 38 + i * 16.5, ln, lsize, INK, "middle"))


# ======================= 图 1：全局定位图 =======================

def fig1():
    W, H = 980, 640
    b = frame(W, H, "第 109 天定位：GFLOPS 与算术强度——Auto-tuning 的冠军表第一次有了参照系")
    b.append(hand_line(300, 44, 690, 45, ORANGE, 3))

    # ---- 上排：调优主线 ----
    b.append(text(56, 68, "调优主线", 12.5, INK, "start", True))
    steps = [("Tiling·展开", "D92~96"), ("候选生成", "D106"),
             ("统一 Benchmark", "D107"), ("Auto-tuning v0.1", "D108"),
             ("GFLOPS·AI·Roofline", "D109 今天"), ("Cost Model 预剪", "D110")]
    for i, (nm, day) in enumerate(steps):
        x = 56 + i * 154
        hot = day.startswith("D109")
        b.append(hand_rect(x, 76 if hot else 80, 140, 54 if hot else 50,
                           ORANGE if hot else BG, 0.9 if hot else 1.0,
                           INK, 2.2 if hot else 1.4))
        b.append(text(x + 70, 99 if hot else 101, nm, 10.5, INK, "middle", True))
        b.append(text(x + 70, 120 if hot else 119, day, 10, RED if hot else MUTED))
        if i < 5:
            b.append(arrow(x + 142, 103, x + 152, 103, MUTED, 1.5))

    # ---- 中排：今天的分析流水线 ----
    b.append(text(56, 158, "今天的分析流水线：把 110 条记录放进三个坐标系", 12.5, INK, "start", True))
    flow = [
        ("① 读记录", ["D108 results.jsonl", "110 条 · flops_nominal", "sha256 血统校验"]),
        ("② 有效 GFLOPS", ["flops ÷ 实测 median", "毫秒 → 速率", "跨 shape 才可比"]),
        ("③ 算术强度 AI", ["flops ÷ bytes_min", "立方捷径 n/6", "算法+shape 属性"]),
        ("④ 机器模型探针", ["解释屋顶 54.7 MFLOPS", "Python 级 0.385 GB/s", "C 级 2.68 GB/s"]),
        ("⑤ 屋脊点+瓶颈标记", ["AI* = P ÷ BW ≈ 0.142", "AI 在右侧 75~113×", "全部『解释受限』"]),
    ]
    for i, (t, lines) in enumerate(flow):
        x = 56 + i * 179
        hot = i >= 3
        b.append(hand_rect(x, 170, 164, 92, ORANGE if hot else BLUE, 0.45, INK, 1.6))
        b.append(text(x + 82, 189, t, 11.5, INK, "middle", True))
        for j, ln in enumerate(lines):
            b.append(text(x + 82, 207 + j * 16, ln, 9.6, INK, "middle"))
        if i < 4:
            b.append(arrow(x + 166, 216, x + 177, 216, MUTED, 1.6))

    # ---- 下排：输入 / 机器模型 / 输出 账本卡 ----
    b.append(text(56, 292, "输入输出账（数字全部出自 outputs/）", 12.5, INK, "start", True))
    card(b, 56, 302, 284, 108, "输入：D108 的落盘记录",
         ["98 筛选 + 12 决赛 + 2 投毒被拒", "flops_nominal（2·M·N·K）随记录走",
          "kernel 时间不重测（中位数口径）", "两个 no-tail 继续不进任何性能表"], BLUE)
    card(b, 356, 302, 284, 108, "机器模型：三个探针实测（屋顶同层纪律）",
         ["A 解释屋顶 0.0547 GFLOPS（标量 FMA）", "B Python 级流读 0.385 GB/s（迭代式）",
          "C C 级扫描 2.68 GB/s（adler32·64MB）", "屋脊点 AI* = 0.0547 ÷ 0.385 ≈ 0.142"], GREEN)
    card(b, 656, 302, 284, 108, "输出：性能分析表 + Roofline 报告",
         ["108 条通过记录逐条标瓶颈", "冠军距屋顶 1.59~1.65×（六成）",
          "无一带宽受限：AI 右侧 75~113×", "解释税 861~1,248×（下界）"], ORANGE)

    # ---- 底部：结论带 ----
    b.append(hand_rect(56, 436, 884, 62, GRAYC, 0.8, INK, 1.5))
    b.append(text(498, 460, "一句话定位：D106 候选从哪来 → D107 怎么测才算数 → D108 谁是冠军，", 11.5, INK, "middle", True))
    b.append(text(498, 480, "今天回答『离极限多远、瓶颈在哪、下一步往哪推』→ D110 用这些数字给候选预剪", 11.5, INK, "middle", True))

    b.append(text(56, 540, "冠军汇总（决赛 3+21 中位数，跨 shape 只有速率可比）", 11.5, INK, "start", True))
    b.append(hand_line(56, 550, 940, 551, BORDER, 1.6))
    rows = [("S1 64×64×64", "AI 10.67", "15.80 ms → 33.2 MFLOPS", "距屋顶 1.65×"),
            ("S2 96×96×96", "AI 16.00", "51.53 ms → 34.3 MFLOPS", "距屋顶 1.59×"),
            ("S3 90×96×64", "AI 13.46", "32.06 ms → 34.5 MFLOPS", "距屋顶 1.59×")]
    rows_y = [567, 589, 611]
    for i, r in enumerate(rows):
        b.append(text(150, rows_y[i], r[0], 10.5, INK, "start", True))
        b.append(text(310, rows_y[i], r[1], 10.5, MUTED, "start"))
        b.append(text(490, rows_y[i], r[2], 10.5, INK, "start"))
        b.append(text(800, rows_y[i], r[3], 10.5, RED, "start"))
    b.append(text(498, 634, "三 shape 冠军速率几乎平——工作量差 3.4×，速率只差 4%：『解释受限』的数据指纹", 10.5, RED, "middle", True))
    save("01-overview.svg", b)


# ======================= 图 2：Roofline 机制解剖 =======================

def fig2():
    W, H = 980, 640
    b = frame(W, H, "Roofline 机制解剖：两个屋顶、一个屋脊点、两片受限区")
    b.append(hand_line(320, 44, 660, 45, BLUE, 3))

    # ---- 左半：示意图（不按比例，log-log）----
    px0, px1, py0, py1 = 90, 560, 100, 520
    b.append(hand_line(px0, py1, px1, py1, INK, 2))           # x 轴
    b.append(hand_line(px0, py0, px0, py1, INK, 2))           # y 轴
    b.append(arrow(px1 - 6, py1, px1 + 10, py1, INK, 2))
    b.append(arrow(px0, py0 + 14, px0, py0 - 6, INK, 2))
    b.append(text(px1 + 4, py1 + 22, "算术强度 AI (FLOP/B)，log", 10.5, INK, "end"))
    b.append(text(78, 96, "可达性能 (GFLOPS)，log", 10.5, INK, "start", rotate=-38))

    ridge_x, ridge_y = 330, 230
    b.append(hand_poly([(110, 500), (200, 388), (ridge_x, ridge_y)], GREEN, 3.2))   # 带宽屋顶（斜）
    b.append(hand_poly([(ridge_x, ridge_y), (450, ridge_y), (548, ridge_y + 4)], BLUE, 3.2))  # 算力屋顶（平）
    b.append(dot(ridge_x, ridge_y, 6, RED))
    b.append(text(ridge_x + 8, ridge_y - 12, "屋脊点 AI* = P ÷ BW", 11, RED, "start", True))
    b.append(hand_line(ridge_x, ridge_y + 6, ridge_x, py1, MUTED, 1.2, "5 4"))
    b.append(text(ridge_x, py1 + 16, "AI*", 10.5, RED, "middle", True))

    b.append(text(170, 470, "带宽受限区", 11, GREEN, "middle", True))
    b.append(text(170, 486, "AI < AI*：涨 AI 才涨速度", 9.5, MUTED, "middle"))
    b.append(text(455, 320, "算力受限区", 11, BLUE, "middle", True))
    b.append(text(455, 336, "AI ≥ AI*：AI 再高也没用", 9.5, MUTED, "middle"))

    kx, ky = 462, 300
    b.append(dot(kx, ky, 6, ORANGE))
    b.append(hand_line(kx, ky + 8, kx, py1, MUTED, 1.2, "5 4"))
    b.append(text(kx, py1 + 16, "内核点的 AI", 10, INK, "middle"))
    b.append(hand_line(kx, ky - 7, kx + 2, ridge_y + 4, MUTED, 1.2, "5 4"))
    b.append(text(386, 268, "离屋顶的倍数＝优化余量", 9.8, MUTED, "start"))

    b.append(text(200, 435, "带宽屋顶 = BW × AI（斜线）", 10.5, GREEN, "start", True))
    b.append(text(360, 214, "算力屋顶 P（水平线）", 10.5, BLUE, "start", True))

    # ---- 右半：三张卡 ----
    card(b, 590, 90, 350, 108, "两条公式",
         ["可达性能 attainable = min(P, BW × AI)", "屋脊点 AI* = P ÷ BW",
          "AI < AI* → 被带宽卡住；AI ≥ AI* → 被算力卡住", "速度的上限＝两个屋顶的较低者"], BLUE)
    card(b, 590, 212, 350, 108, "三步定位法",
         ["① 量屋顶：探针与内核必须同一执行层", "   （拿硬件屋顶解释 CPython 内核＝跨层归因）",
          "② 算 AI：flops ÷ 名义搬运字节（n/6）", "③ 看点：落在屋脊哪一边＋离屋顶几倍"], GREEN)
    card(b, 590, 334, 350, 108, "名义 AI 的边界（诚实条款）",
         ["名义 AI 假设每个元素只搬运一遍", "tiled 内核实际重读 → 实际 AI 更低",
          "C 的读-改-写重访也按单遍计", "余量大（75~113×）时，结论对它稳健"], ORANGE)

    # ---- 底部：本环境代入 ----
    b.append(hand_rect(56, 470, 884, 66, GRAYC, 0.85, INK, 1.5))
    b.append(text(498, 494, "本环境代入（实测）：P_int = 0.0547 GFLOPS，BW = 0.385 GB/s → AI* ≈ 0.142 FLOP/B；", 11.5, INK, "middle", True))
    b.append(text(498, 514, "matmul 的 AI = 10.67 / 13.46 / 16.00 → 全部在屋脊右侧 75~113 倍 → 统一标记『解释受限』", 11.5, INK, "middle"))
    b.append(text(498, 552, "屋脊两侧的分界只由两个屋顶的比值决定——带宽和算力谁卡住你，不是猜出来的，是 P ÷ BW 算出来的", 10.5, MUTED, "middle"))
    save("02-mechanism.svg", b)


# ======================= 图 3：实测 Roofline（真实数据点） =======================

# 坐标系：x = AI 0.01~100（log10: -2..2），y = GFLOPS 0.005~20（log10: -2.3..1.3）
X0, X1, Y0, Y1 = 120, 960, 90, 600


def px(ai):
    return X0 + (math.log10(ai) + 2) / 4 * (X1 - X0)


def py(g):
    return Y1 - (math.log10(g) + 2.3) / 3.6 * (Y1 - Y0)


def fig3():
    W, H = 1000, 700
    b = frame(W, H, "实测 Roofline：全部 108 条通过记录贴在解释屋顶之下——无一带宽受限")
    b.append(hand_line(330, 44, 680, 45, RED, 3))

    # ---- 坐标轴 ----
    b.append(hand_line(X0, Y1, X1, Y1, INK, 2.2))
    b.append(hand_line(X0, Y0 - 8, X0, Y1, INK, 2.2))
    b.append(arrow(X1 - 8, Y1, X1 + 14, Y1, INK, 2.2))
    b.append(arrow(X0, Y0 + 4, X0, Y0 - 16, INK, 2.2))
    for v, lab in ((0.01, "0.01"), (0.1, "0.1"), (1, "1"), (10, "10"), (100, "100")):
        b.append(hand_line(px(v), Y1, px(v), Y1 + 7, MUTED, 1.2))
        b.append(text(px(v), Y1 + 21, lab, 10, MUTED))
    for v, lab in ((0.01, "0.01"), (0.1, "0.1"), (1, "1"), (10, "10")):
        b.append(hand_line(X0 - 7, py(v), X0, py(v), MUTED, 1.2))
        b.append(text(X0 - 12, py(v) + 4, lab, 10, MUTED, "end"))
    b.append(text((X0 + X1) / 2, Y1 + 40, "算术强度 AI（FLOP/byte），log 轴", 12, INK, "middle", True))
    b.append(text(X0 - 44, (Y0 + Y1) / 2, "有效 / 可达 GFLOPS，log 轴", 12, INK, "middle", True, -90))

    # ---- 三个真实屋顶（探针实测，probes.json）----
    ridge_x, ridge_y = px(0.142), py(0.0547)
    b.append(hand_poly([(px(0.01299), Y1), (ridge_x, ridge_y)], GREEN, 3.4))                    # 带宽屋顶（Python 级）
    b.append(hand_poly([(ridge_x, ridge_y), (X1 - 10, ridge_y + 2)], BLUE, 3.4))              # 解释屋顶（水平）
    b.append(hand_poly([(X0, py(0.0268)), (px(7.46), Y0)], RED, 2.4, "7 5"))                   # C 级 adler32
    b.append(hand_poly([(X0, py(0.0099)), (px(20.2), Y0)], MUTED, 1.4, "3 4"))                # crc32 对照
    b.append(text(196, 512, "带宽屋顶 = 0.385 × AI", 10.5, GREEN, "start", True))
    b.append(text(180, 527, "（Python 级流读，迭代式）", 9.3, MUTED, "start"))
    b.append(text(660, ridge_y - 14, "解释屋顶 P_int = 0.0547 GFLOPS（54.7 MFLOPS）", 11, BLUE, "middle", True))
    b.append(text(368, 344, "C 级通路 2.68 GB/s", 10, RED, "start", True))
    b.append(text(368, 358, "（adler32 实测）", 9.3, MUTED, "start"))
    b.append(text(158, 586, "crc32 对照 0.99 GB/s", 9.3, MUTED, "start"))

    # ---- 屋脊点与两区标注 ----
    b.append(dot(ridge_x, ridge_y, 6.5, RED))
    b.append(text(ridge_x, ridge_y - 26, "屋脊点 AI* = 0.142", 11, RED, "middle", True))
    b.append(hand_line(ridge_x, ridge_y + 7, ridge_x, Y1, MUTED, 1.2, "5 4"))
    b.append(text(238, 560, "带宽受限区（本环境没有内核落在这里）", 9.6, GREEN, "middle"))
    b.append(text(545, 492, "算力 / 解释受限区（108 条全在这里）", 9.6, BLUE, "middle"))

    # ---- 六个真实内核点（决赛 3+21 中位数）----
    shapes = [
        ("S1", 10.667, 0.0332, 0.0275),
        ("S3", 13.458, 0.0345, 0.0263),
        ("S2", 16.0, 0.0343, 0.0272),
    ]
    for sid, ai, gf_champ, gf_def in shapes:
        x = px(ai)
        b.append(hand_line(x, Y1, x, py(gf_def) + 10, MUTED, 1.1, "2 5"))
        b.append(dot(x, py(gf_champ), 6, ORANGE))
        b.append(dot(x, py(gf_def), 5.5, "none", INK, 1.4, hollow=True))
    # 冠军簇圈注 + 缺省簇圈注（椭圆压扁，避免互相相交）
    b.append(hand_ellipse(776, 481, 44, 8, RED, 1.6))
    b.append(arrow(822, 483, 850, 528, RED, 1.4))
    b.append(text(854, 534, "冠军 0.033~0.035 GFLOPS", 10.5, INK, "start", True))
    b.append(text(854, 549, "三 shape 几乎同速", 9.6, MUTED, "start"))
    b.append(text(854, 564, "（解释受限的指纹）", 9.6, MUTED, "start"))
    b.append(hand_ellipse(776, 497, 44, 9, BLUE, 1.5))
    b.append(arrow(822, 505, 850, 583, BLUE, 1.3))
    b.append(text(854, 589, "缺省 32³ ijk 0.026~0.028", 10.5, INK, "start", True))
    b.append(text(854, 604, "同在解释屋顶下，慢 ~20%", 9.6, MUTED, "start"))
    # x 轴下方的 shape 标注（错行防重叠）
    b.append(text(px(10.667), 644, "S1  AI=10.7", 10, INK, "middle", True))
    b.append(text(px(13.458), 660, "S3  AI=13.5", 10, INK, "middle", True))
    b.append(text(px(16.0), 676, "S2  AI=16.0", 10, INK, "middle", True))

    # ---- 图例与口径卡（右上 / 左上空白区）----
    b.append(dot(139, 108, 5.5, ORANGE))
    b.append(text(150, 112, "冠军（决赛 3+21 中位数）", 9.6, INK, "start"))
    b.append(dot(139, 127, 5, "none", INK, 1.3, hollow=True))
    b.append(text(150, 131, "缺省 32³ ijk U=1（决赛）", 9.6, INK, "start"))
    b.append(text(952, 112, "口径：kernel＝D108 落盘记录（110 条）", 9.8, INK, "end"))
    b.append(text(952, 128, "屋顶＝本机探针中位数 · 2026-11-13", 9.8, MUTED, "end"))
    b.append(text(952, 144, "Python 3.11.4 · aarch64 · 32 核", 9.8, MUTED, "end"))
    b.append(hand_line(834, 152, 952, 153, BORDER, 1.2))
    b.append(text(952, 168, "冠军距屋顶 1.59~1.65×（六成）", 9.8, RED, "end", True))
    b.append(text(952, 184, "同样数据走 C 级通路：18~41 µs", 9.8, MUTED, "end"))
    b.append(text(952, 200, "解释税 861~1,248×（下界）", 9.8, RED, "end", True))

    b.append(text(500, 676, "屋脊余量 75~113×：换探针风格（下标式 0.260）只挪屋脊 1.8×，判定不动", 10.5, MUTED, "middle"))
    save("03-results.svg", b)


if __name__ == "__main__":
    print("生成第 109 天 3 张手绘图：")
    fig1()
    fig2()
    fig3()
    print("完成。")
