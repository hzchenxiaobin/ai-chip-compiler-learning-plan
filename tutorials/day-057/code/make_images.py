#!/usr/bin/env python3
"""make_images.py —— 第 57 天教程的四张手绘 sketch 风 SVG 信息图。

风格约定（与第 8 周各天一致）：
  - 背景 #fdfaf2（米白），盒子白底 + 深灰 #6b6357 手绘描边
  - 强调色不超过 4 种柔和色：蓝 #4a7fa5 / 橙 #a8772e / 绿 #5a8a5a / 红 #b0605a
  - 线条带轻微抖动（L 段折线），圆头笔触，线宽 2 左右
  - 手写感字体栈：Comic Sans MS / Comic Neue / Kaiti SC / 楷体 / cursive

图中全部数字来自 2026-11-12 的真实运行
（layout_lab.py 的 19/19、test_layout.py 的 14/14、mlir-opt --canonicalize 的输出）。

运行: python3 make_images.py   （在 code/ 目录下，输出到 ../images/）
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

rng = random.Random(57)


def esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;")
             .replace(">", "&gt;"))


def txt(x, y, s, size=12, fill=INK, anchor="start", bold=False, opacity=1.0):
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
                bow=0.0):
    if bow:
        mx, my = (x0 + x1) / 2, (y0 + y1) / 2
        dx, dy = x1 - x0, y1 - y0
        mx, my = mx - dy * bow, my + dx * bow
        d = (f"M {x0:.1f},{y0:.1f} Q {mx:.1f},{my:.1f} "
             f"{x1:.1f},{y1:.1f}")
    else:
        d = f"M {x0:.1f},{y0:.1f} L {x1:.1f},{y1:.1f}"
    out = [f'<path d="{d}" fill="none" stroke="{stroke}" '
           f'stroke-width="{sw}" stroke-linecap="round" '
           f'stroke-linejoin="round"/>']
    if arrow:
        ang = math.atan2(y1 - y0, x1 - x0) if not bow else \
            math.atan2(y1 - my, x1 - mx)
        L = 9.0
        for da in (math.radians(152), math.radians(-152)):
            ax = x1 + L * math.cos(ang + da)
            ay = y1 + L * math.sin(ang + da)
            out.append(f'<path d="M {x1:.1f},{y1:.1f} L {ax:.1f},{ay:.1f}" '
                       f'fill="none" stroke="{stroke}" stroke-width="{sw}" '
                       f'stroke-linecap="round"/>')
    return "".join(out)


def sketch_dash(x0, y0, x1, y1, stroke=MUTED, sw=1.6):
    d = f"M {x0:.1f},{y0:.1f} L {x1:.1f},{y1:.1f}"
    return (f'<path d="{d}" fill="none" stroke="{stroke}" '
            f'stroke-width="{sw}" stroke-linecap="round" '
            f'stroke-dasharray="7 6"/>')


def header(w, h, title, sub):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" '
            f'height="{h}" viewBox="0 0 {w} {h}">\n'
            f'<rect width="{w}" height="{h}" fill="{BG}"/>\n'
            + txt(40, 38, title, 20, INK, bold=True) + "\n"
            + txt(40, 61, sub, 12, MUTED) + "\n")


def badge(x, y, s, color, w=None):
    w = w or (10 + 11.5 * max(len(s), 1) * (1 if s.isascii() else 0.95))
    p = [sketch_rect(x, y, w, 22, TINT["white"], color, 1.8, 4)]
    p.append(txt(x + w / 2, y + 15, s, 11, color, "middle", bold=True))
    return "".join(p), w


def cell(x, y, w, h, value, off, vcolor=INK, ocolor=MUTED, fill="#ffffff",
         big=False):
    """存储/网格格子：上半是值，下半是物理偏移。"""
    vs = 17 if big else 14
    os_ = 10 if not big else 11
    return "".join([
        sketch_rect(x, y, w, h, fill, STROKE, 1.8, 4),
        txt(x + w / 2, y + h / 2 - (2 if big else 1), str(value), vs,
            vcolor, "middle", bold=True),
        txt(x + w / 2, y + h - 6, f"@{off}", os_, ocolor, "middle"),
    ])


def store_strip(x, y, cw, ch, label=None, gap=8, tint_from=None, tint_to=None,
                tint_color=None):
    """底部存储条带：6 个格子，值即偏移 0..5。可高亮一段窗口。"""
    parts = []
    if label:
        parts.append(txt(x, y - 8, label, 13, INK, bold=True))
    for v in range(6):
        fill = "#ffffff"
        if tint_from is not None and tint_from <= v <= tint_to:
            fill = TINT[tint_color or "green"]
        parts.append(cell(x + v * (cw + gap), y, cw, ch, v, f"偏移{v}",
                          vcolor=INK, ocolor=MUTED, fill=fill, big=True))
    return "".join(parts), 6 * cw + 5 * gap


# ============================================================
# 图 1：全局定位——第 57 天在 168 天计划与编译链路中的位置
# ============================================================

def img1():
    W, H = 1240, 780
    p = [header(W, H,
                "第 57 天全貌：进入第三阶段，先给「图优化」打布局地基",
                "上：六阶段里程碑与第 9 周日程｜中：为什么现在学 Layout｜下：布局信息在编译链路里的去向")]

    # ---- 上：六阶段里程碑 ----
    stages = [
        ("阶段一 1-28", "C++ 与图 IR 基础", False),
        ("阶段二 29-56", "MLIR 核心能力", False),
        ("阶段三 57-84", "AI 计算图与图优化", True),
        ("阶段四 85-112", "Lowering·Tiling·调优", False),
        ("阶段五 113-140", "端到端编译与 Runtime", False),
        ("阶段六 141-168", "收口与面试转化", False),
    ]
    sx, sy, sw_, sh, gap = 40, 92, 184, 58, 9
    for i, (t1, t2, hot) in enumerate(stages):
        x = sx + i * (sw_ + gap)
        fill = TINT["blue"] if hot else "#ffffff"
        stroke_c = RED if hot else STROKE
        p.append(sketch_rect(x, sy, sw_, sh, fill, stroke_c,
                             2.6 if hot else 1.8, 5))
        p.append(txt(x + sw_ / 2, sy + 22, t1, 12,
                     RED if hot else INK, "middle", bold=hot))
        p.append(txt(x + sw_ / 2, sy + 43, t2, 10.5,
                     INK if hot else MUTED, "middle"))
        if hot:
            b, _ = badge(x + sw_ / 2 - 34, sy - 14, "今天 Day 57", RED)
            p.append(b)
        if i < 5:
            p.append(sketch_line(x + sw_ + 1, sy + sh / 2,
                                 x + sw_ + gap - 1, sy + sh / 2,
                                 MUTED, 1.5, arrow=True))
    p.append(txt(40, 178, "第 84 天里程碑：Layout 优化、融合收益判断和数值验证体系"
                           "——本周从最底下的物理布局起步", 11.5, MUTED))

    # ---- 中：第 9 周日程 ----
    p.append(txt(40, 216, "第 9 周：Tensor、Shape、Stride 与 Layout", 14,
                 INK, bold=True))
    days = [
        ("57", "Shape·Stride\nOffset·Contig.", True),
        ("58", "NCHW vs NHWC\nLayout 对比", False),
        ("59", "Reshape\n合法性", False),
        ("60", "Broadcast\n规则", False),
        ("61", "动态 Shape\n表示", False),
        ("62", "静态 Shape\n特化", False),
        ("63", "第 9 周\n复盘", False),
    ]
    dx, dy, dw, dh = 40, 230, 160, 66
    for i, (d, t, hot) in enumerate(days):
        x = dx + i * (dw + 10)
        fill = TINT["blue"] if hot else "#ffffff"
        p.append(sketch_rect(x, dy, dw, dh, fill, RED if hot else STROKE,
                             2.4 if hot else 1.8, 5))
        p.append(txt(x + 12, dy + 21, f"Day {d}", 12,
                     RED if hot else BLUE, bold=hot))
        lines = t.split("\n")
        p.append(txt(x + 12, dy + 40, lines[0], 11, INK))
        p.append(txt(x + 12, dy + 55, lines[1], 11, INK))
        if i < 6:
            p.append(sketch_line(x + dw + 1, dy + dh / 2,
                                 x + dw + 9, dy + dh / 2, MUTED, 1.5,
                                 arrow=True))

    # ---- 下：为什么现在学 + 链路去向 ----
    p.append(txt(40, 330, "为什么现在学？mini Dialect 只写了逻辑形状，"
                          "再往下走 IR 必须带上物理布局", 14, INK, bold=True))
    # 三个卡片：过去 / 今天 / 未来
    cards = [
        ("第 29-56 天留下的", "mini.matmul 等算子只声明\ntensor<2x3xf32>：\n知道形状，不知道"
         "\n数据在内存里怎么排", TINT["white"], STROKE, MUTED),
        ("第 57 天补上的视角", "同一个存储可以挂多张视图：\nshape 只是「逻辑维数」\nstride + offset 才说清"
         "\n每个元素住在哪一格", TINT["blue"], BLUE, BLUE),
        ("后续谁要用它", "Day 58 访存序列分析\nDay 64-70 转置/Reshape 消除\nDay 71-76 融合流量收益"
         "\n都要先看懂布局", TINT["white"], STROKE, MUTED),
    ]
    cx, cy, cw2, ch2 = 40, 348, 373, 132
    for i, (t, body, fill, sc, tc) in enumerate(cards):
        x = cx + i * (cw2 + 17)
        p.append(sketch_rect(x, cy, cw2, ch2, fill, sc, 2.4, 5))
        p.append(txt(x + 14, cy + 24, t, 12.5, tc, bold=True))
        for k, line in enumerate(body.split("\n")):
            p.append(txt(x + 14, cy + 46 + k * 18, line, 11.5, INK))
        if i < 2:
            p.append(sketch_line(x + cw2 + 1, cy + ch2 / 2,
                                x + cw2 + 16, cy + ch2 / 2, MUTED, 1.8,
                                arrow=True))

    # ---- 底：类型链路 ----
    p.append(txt(40, 518, "布局信息在 IR 里的形态（今天用真实 mlir-opt 验证同一件事）：",
                 13.5, INK, bold=True))
    lx, ly, lw2, lh2 = 40, 534, 360, 110
    p.append(sketch_rect(lx, ly, lw2, lh2, "#ffffff", STROKE, 2.0, 5))
    p.append(txt(lx + 14, ly + 22, "mini Dialect（逻辑层，只有形状）", 12, BLUE,
                 bold=True))
    p.append(txt(lx + 14, ly + 45, "mini.matmul %a, %b :", 11.5, INK))
    p.append(txt(lx + 14, ly + 62, "  tensor<2x3xf32> × tensor<3x2xf32>", 11.5,
                 INK))
    p.append(txt(lx + 14, ly + 84, "  → tensor<2x2xf32>   ← 不说数据怎么排", 11,
                 MUTED))
    x2 = lx + lw2 + 30
    p.append(sketch_line(x2 - 26, ly + lh2 / 2, x2 - 4, ly + lh2 / 2,
                         ORANGE, 2.4, arrow=True))
    p.append(sketch_rect(x2, ly, lw2, lh2, TINT["orange"], ORANGE, 2.0, 5))
    p.append(txt(x2 + 14, ly + 22, "memref Dialect（物理层，Lowering 补布局）",
                 12, ORANGE, bold=True))
    p.append(txt(x2 + 14, ly + 45, "memref<2x3xf32,", 11.5, INK))
    p.append(txt(x2 + 14, ly + 62, "  strided<[3, 1], offset: 0>>", 11.5, INK))
    p.append(txt(x2 + 14, ly + 84, "  ← sizes=shape + strides + offset", 11,
                 MUTED))
    x3 = x2 + lw2 + 30
    p.append(sketch_line(x3 - 26, ly + lh2 / 2, x3 - 4, ly + lh2 / 2,
                         GREEN, 2.4, arrow=True))
    p.append(sketch_rect(x3, ly, 1240 - 40 - x3, lh2, "#ffffff", GREEN, 2.0, 5))
    p.append(txt(x3 + 14, ly + 22, "图优化（用布局判收益）", 12, GREEN, bold=True))
    p.append(txt(x3 + 14, ly + 45, "转置消除 / Reshape 合并 /", 11.5, INK))
    p.append(txt(x3 + 14, ly + 62, "融合流量计算，全都先问：", 11.5, INK))
    p.append(txt(x3 + 14, ly + 84, "「这块数据连续吗？搬多少字节？」", 11, MUTED))

    p.append(txt(40, 676, "实测环境（全部真实运行）：Ubuntu 20.04.5 LTS（aarch64）· "
                          "Python 3.11.4 · numpy 1.26.4 · Ubuntu LLVM 18.1.8",
                 11, MUTED))
    p.append(txt(40, 698, "今天两个实验载体：layout_lab.py（19/19 断言通过）· "
                          "layout_views.mlir（mlir-opt 解析·验证·canonicalize 通过）",
                 11, MUTED))
    p.append("</svg>")
    (OUT / "01-overview.svg").write_text("\n".join(p), encoding="utf-8")


# ============================================================
# 图 2：核心机制——逻辑下标到物理偏移的公式
# ============================================================

def img2():
    W, H = 1240, 860
    p = [header(W, H,
                "核心机制：逻辑下标 → 物理偏移，只靠一条公式",
                "上：同一存储挂三张视图（元信息不同）｜中：唯一换算公式｜下：三个真实算例落到同一根存储条带")]

    # ---- 上：三张视图元信息卡 ----
    views = [
        ("视图 A：连续 Tensor", "store.reshape(2,3)",
         "shape=(2,3)   strides=(3,1) 元素", "storage_offset = 0",
         "C-contiguous = True", BLUE, TINT["blue"]),
        ("视图 T：转置视图", "T = A.T（零拷贝）",
         "shape=(3,2)   strides=(1,3) 元素", "storage_offset = 0",
         "C=False · F=True（按列连续）", ORANGE, TINT["orange"]),
        ("视图 B：偏移切片", "store[1:5].reshape(2,2)",
         "shape=(2,2)   strides=(2,1) 元素", "storage_offset = 1",
         "C=True（窗口内连续，偏移≠非连续）", GREEN, TINT["green"]),
    ]
    cx, cy, cw2, ch2 = 52, 92, 360, 128
    xs = []
    for i, (t, src, f1, f2, f3, c, tint) in enumerate(views):
        x = cx + i * (cw2 + 34)
        xs.append(x + cw2 / 2)
        p.append(sketch_rect(x, cy, cw2, ch2, tint, c, 2.4, 5))
        p.append(txt(x + 14, cy + 24, t, 13, c, bold=True))
        p.append(txt(x + 14, cy + 44, src, 10.5, MUTED))
        p.append(txt(x + 14, cy + 68, f1, 12, INK))
        p.append(txt(x + 14, cy + 90, f2, 12, INK))
        p.append(txt(x + 14, cy + 112, f3, 11, MUTED))
        # 虚线连到公式框
        p.append(sketch_dash(x + cw2 / 2, cy + ch2 + 2, x + cw2 / 2, 268))

    # ---- 中：公式大框 ----
    fx, fy, fw, fh = 220, 276, 800, 86
    p.append(sketch_rect(fx, fy, fw, fh, "#ffffff", RED, 3.0, 6))
    p.append(txt(fx + fw / 2, fy + 36,
                 "物理偏移 ＝ storage_offset ＋ i × strides[0] ＋ j × strides[1]",
                 20, RED, "middle", bold=True))
    p.append(txt(fx + fw / 2, fy + 66,
                 "（单位：元素。i、j 是逻辑下标；三个视图共用这同一条公式，差别只在元信息）",
                 11.5, MUTED, "middle"))

    # ---- 下：三个算例 → 存储条带 ----
    cases = [
        ("A[1,2]", "0 + 1×3 + 2×1 = 5", 5, BLUE),
        ("T[2,1]", "0 + 2×1 + 1×3 = 5", 5, ORANGE),
        ("B[1,1]", "1 + 1×2 + 1×1 = 4", 4, GREEN),
    ]
    ty = 400
    strip_x, strip_y, cw_, ch_, gap_ = 430, 520, 54, 56, 8
    for k, (idx, expr, target, c) in enumerate(cases):
        y = ty + k * 40
        p.append(txt(60, y, f"算例 {idx}", 13, c, bold=True))
        p.append(txt(150, y, expr, 13, INK))
        # 折线箭头到条带上目标格
        tx = strip_x + target * (cw_ + gap_) + cw_ / 2
        ty_ = strip_y - 8
        p.append(f'<path d="M {330:.0f},{y - 4:.0f} L {tx - 60:.0f},{y - 4:.0f} '
                 f'L {tx:.0f},{ty_:.0f}" fill="none" stroke="{c}" '
                 f'stroke-width="2.2" stroke-linecap="round" '
                 f'stroke-linejoin="round"/>')
        p.append(f'<path d="M {tx:.0f},{ty_:.0f} L {tx - 5:.0f},{ty_ - 10:.0f}" '
                 f'stroke="{c}" stroke-width="2.2" stroke-linecap="round"/>')
        p.append(f'<path d="M {tx:.0f},{ty_:.0f} L {tx + 6:.0f},{ty_ - 10:.0f}" '
                 f'stroke="{c}" stroke-width="2.2" stroke-linecap="round"/>')

    strip, _ = store_strip(strip_x, strip_y, cw_, ch_)
    p.append(txt(60, strip_y - 8,
                 "底层存储 store（6 个 f32，元素值＝物理位置）", 13, INK, bold=True))
    p.append(strip)
    p.append(txt(60, strip_y + ch_ + 24,
                 "A[1,2]、T[2,1]、B[1,1] 各自代入公式后，都准确落在自己的格子上——"
                 "编译器和 numpy 算的是同一笔账", 11.5, MUTED))

    # ---- MLIR 对照脚注 ----
    p.append(txt(60, 640, "同一公式在 MLIR 里长什么样：", 13, INK, bold=True))
    p.append(txt(60, 664, "memref<3x2xf32, strided<[1, 3], offset: 0>>  "
                          "← offset 与 strides 直接写进类型，就是公式的两个系数",
                 12, ORANGE))
    p.append(txt(60, 688, "mlir-opt --canonicalize 之后，转置视图的元数据被折成常数：",
                 12, INK))
    p.append(txt(60, 712, "return %c0, %c1, %c3 : index, index, index   "
                          "← offset=0, strides=[1,3]，与 numpy 的 T 同口径（真实输出）",
                 12, GREEN))
    p.append(txt(60, 744, "要点：转置/切片只改 (shape, strides, offset) 这张「元信息卡」，"
                          "一格数据都不搬", 13, RED, bold=True))
    p.append(txt(60, 768, "边界：这条公式只覆盖「仿射布局」——步长恒定、不依赖数据本身；"
                          "稀疏、压缩等布局不适用", 11.5, MUTED))
    p.append("</svg>")
    (OUT / "02-mechanism.svg").write_text("\n".join(p), encoding="utf-8")


# ============================================================
# 图 3：实例对照——三个视图的格子图（真实运行数据）
# ============================================================

def img3():
    W, H = 1240, 800
    p = [header(W, H,
                "实例对照：三个视图，同一块存储（layout_lab.py 真实输出）",
                "每个格子：大字是元素值，@后是物理偏移——元素值故意设成物理位置，肉眼即可核对")]

    cw_, ch_ = 76, 62
    BOX_W, BOX_H = 352, 344

    def grid(x, y, rows, meta, tint, c, title, note=None):
        p.append(sketch_rect(x, y, BOX_W, BOX_H, tint, c, 2.2, 5))
        p.append(txt(x + 16, y + 26, title, 13.5, c, bold=True))
        yy = y + 44
        for row in rows:
            xx = x + 16
            for v, off in row:
                p.append(cell(xx, yy, cw_, ch_, v, f"偏移{off}",
                              vcolor=c, ocolor=MUTED, big=True))
                xx += cw_ + 6
            yy += ch_ + 6
        p.append(txt(x + 16, yy + 10, meta[0], 12, INK))
        p.append(txt(x + 16, yy + 30, meta[1], 12, INK))
        p.append(txt(x + 16, yy + 50, meta[2], 11, MUTED))
        if note:
            p.append(txt(x + 16, yy + 74, note, 11, c, bold=True))

    # A：2×3 连续
    grid(56, 100,
         [[(0, 0), (1, 1), (2, 2)], [(3, 3), (4, 4), (5, 5)]],
         ["shape=(2,3) · strides=(3,1) · offset=0",
          "按行读：0,1,2 → 3,4,5，偏移一路 +1",
          "C-contiguous=True"],
         TINT["blue"], BLUE, "视图 A = store.reshape(2, 3)：连续 Tensor",
         "行方向相邻＝物理相邻")

    # T：3×2 转置
    grid(444, 100,
         [[(0, 0), (3, 3)], [(1, 1), (4, 4)], [(2, 2), (5, 5)]],
         ["shape=(3,2) · strides=(1,3) · offset=0",
          "同一批值换了排列：列 0＝A 的行 0",
          "C=False · F=True（按列连续）"],
         TINT["orange"], ORANGE, "视图 T = A.T：转置视图（零拷贝）",
         "行方向相邻＝物理上跳 3 格")

    # B：2×2 偏移切片
    grid(832, 100,
         [[(1, 1), (2, 2)], [(3, 3), (4, 4)]],
         ["shape=(2,2) · strides=(2,1) · offset=1",
          "窗口 [1,5) 内部仍一路 +1",
          "C-contiguous=True（窗口内连续）"],
         TINT["green"], GREEN, "视图 B = store[1:5].reshape(2, 2)",
         "偏移≠非连续：两个独立属性")

    # ---- 底：存储条带 + B 的窗口高亮 ----
    strip, _ = store_strip(56, 524, 74, 62,
                          "底层存储 store：A、T、B 三张视图都只挂在这一块上",
                          tint_from=1, tint_to=4, tint_color="green")
    p.append(strip)
    p.append(txt(56, 624,
                 "绿色格 1..4 就是 B 的窗口：它不从偏移 0 开始（storage_offset=1），"
                 "但窗口内部步长仍是 (2,1)，所以 numpy 判它 C-contiguous=True", 12, GREEN))
    p.append(txt(56, 648,
                 "同理 stride 有 0（广播）、负数（翻转切片）也都不违法——公式只是换系数，不换形状", 12,
                 MUTED))
    p.append(txt(56, 680,
                 "结论：Shape 告诉你「有几个下标」，stride+offset 才告诉你「每个下标落到哪一格」；"
                 "Contiguous 是这两者的推论，不是独立设定", 13, RED, bold=True))
    p.append(txt(56, 708,
                 "（格子里的数值、strides、offset 全部抄自 layout_lab.py 第 2~4 节的 19/19 真实断言输出）",
                 11, MUTED))
    p.append("</svg>")
    (OUT / "03-views-and-offsets.svg").write_text("\n".join(p),
                                                  encoding="utf-8")


# ============================================================
# 图 4：对照实验——reshape 的视图 vs 静默拷贝 + MLIR 折叠
# ============================================================

def img4():
    W, H = 1240, 800
    p = [header(W, H,
                "对照实验：同一句 reshape(6)，连续视图零拷贝，非连续视图静默拷贝",
                "上：A.reshape(6) 只是元信息（True）｜中：T.reshape(6) 必须搬家（False）｜下：MLIR 侧把同一份元数据折成常数")]

    cw_, ch_ = 54, 56
    y0 = 96

    # ---- 左：A.reshape(6) —— 视图 ----
    p.append(sketch_rect(52, y0, 548, 250, TINT["blue"], BLUE, 2.4, 5))
    p.append(txt(70, y0 + 26, "A.reshape(6)：A 是连续的 → 只是元信息", 13.5,
                 BLUE, bold=True))
    b, _ = badge(70, y0 + 38, "np.shares_memory(result, store) = True", BLUE)
    p.append(b)
    p.append(sketch_line(300, y0 + 62, 300, y0 + 78, BLUE, 2.0, arrow=True))
    strip, _ = store_strip(80, y0 + 88, cw_, ch_,
                           "同一块 store，没有任何新内存")
    p.append(strip)
    p.append(txt(80, y0 + 172, "逻辑读序 [0,1,2,3,4,5] ＝ 物理顺序，元信息一换就完事",
                 11.5, INK))
    p.append(txt(80, y0 + 198, "换完的元信息：shape=(6,) · strides=(1,) 元素 · offset=0",
                 11.5, INK))
    p.append(txt(80, y0 + 224, "搬了多少字节？0 个。（19/19 断言里的 True 就是它）", 11.5,
                 BLUE, bold=True))

    # ---- 右：T.reshape(6) —— 拷贝 ----
    x2 = 636
    p.append(sketch_rect(x2, y0, 548, 250, TINT["orange"], ORANGE, 2.4, 5))
    p.append(txt(x2 + 18, y0 + 26,
                 "T.reshape(6)：T 不连续 → 必须拷贝出新数组", 13.5, ORANGE,
                 bold=True))
    b, _ = badge(x2 + 18, y0 + 38, "np.shares_memory(result, store) = False", RED)
    p.append(b)
    p.append(txt(x2 + 18, y0 + 80, "旧存储（还在原地，但结果不住这了）", 11, MUTED))
    for v in range(6):
        p.append(cell(x2 + 18 + v * 86, y0 + 88, 44, 44, v,
                      "", vcolor=MUTED, ocolor=MUTED, fill=TINT["gray"]))
    p.append(sketch_line(x2 + 150, y0 + 140, x2 + 150, y0 + 166, ORANGE, 2.2,
                         arrow=True))
    p.append(txt(x2 + 164, y0 + 158, "按「按行读 T」的顺序搬过去：", 11, ORANGE))
    vals = [0, 3, 1, 4, 2, 5]
    for k, v in enumerate(vals):
        p.append(cell(x2 + 18 + k * 86, y0 + 172, 44, 44, v,
                      f"偏移{k}", vcolor=ORANGE, ocolor=MUTED,
                      fill=TINT["orange"]))
    p.append(txt(x2 + 18, y0 + 238,
                 "新数组 [0,3,1,4,2,5]：新基地址 · strides=(1,) 元素 · C-contiguous=True",
                 11.5, INK))

    # ---- 中：结论 ----
    p.append(txt(52, y0 + 286,
                 "判定「视图还是拷贝」永远别看返回值长什么样，要看内存归属（shares_memory）；"
                 "copy() 语义安全但总是搬，reshape() 语义聪明但可能静默搬", 13,
                 RED, bold=True))

    # ---- 下：MLIR 侧（上下堆叠，避免标签挤压） ----
    p.append(txt(52, y0 + 326, "MLIR 里干同一件事：让编译器把布局元数据静态读出来",
                 13.5, INK, bold=True))
    cy_ = y0 + 344
    ix, iw_ = 52, 1136
    p.append(sketch_rect(ix, cy_, iw_, 128, "#ffffff", STROKE, 2.0, 5))
    p.append(txt(ix + 14, cy_ + 22, "输入：转置视图 + 元数据抽取（layout_views.mlir）",
                 11.5, MUTED))
    p.append(txt(ix + 14, cy_ + 48, "%t = memref.transpose %s (i, j) -> (j, i)"
                 "    : memref<2x3xf32> to memref<3x2xf32, strided<[1, 3]>>", 12,
                 INK))
    p.append(txt(ix + 14, cy_ + 76, "%base, %offset, %sizes:2, %strides:2 ="
                 "    memref.extract_strided_metadata %t : ...", 12, INK))
    # 箭头 + 标签
    p.append(sketch_line(600, cy_ + 136, 600, cy_ + 158, GREEN, 2.4, arrow=True))
    p.append(txt(618, cy_ + 152, "mlir-opt --canonicalize（真实运行）", 11,
                 GREEN, bold=True))
    # 输出卡片
    oy = cy_ + 166
    p.append(sketch_rect(ix, oy, iw_, 128, TINT["green"], GREEN, 2.0, 5))
    p.append(txt(ix + 14, oy + 22, "输出：转置视图的元数据全部折成常数，编译期直接拿到",
                 11.5, MUTED))
    p.append(txt(ix + 14, oy + 50, "%c0 = arith.constant 0 : index"
                 "        // offset = 0", 12.5, GREEN))
    p.append(txt(ix + 14, oy + 74, "%c1 = arith.constant 1 : index"
                 "        // strides[0] = 1", 12.5, GREEN))
    p.append(txt(ix + 14, oy + 98, "%c3 = arith.constant 3 : index"
                 "        // strides[1] = 3", 12.5, GREEN))

    p.append(txt(52, oy + 158,
                 "两张图说的是同一件事：布局是「元数据」，可以零成本查看、零成本置换；"
                 "但一旦要求「换一种连续」，就要动真格搬数据", 13, RED, bold=True))
    p.append(txt(52, oy + 182,
                 "提前给 Day 59 埋钩子：Reshape 的合法性检查，本质就是判断「能不能只改元信息不搬家」",
                 11.5, MUTED))
    p.append("</svg>")
    (OUT / "04-reshape-view-or-copy.svg").write_text("\n".join(p),
                                                    encoding="utf-8")


if __name__ == "__main__":
    img1()
    img2()
    img3()
    img4()
    for f in sorted(OUT.glob("*.svg")):
        print(f"wrote {f} ({f.stat().st_size} bytes)")
