#!/usr/bin/env python3
"""make_images.py —— 第 58 天教程的四张手绘 sketch 风 SVG 信息图。

风格约定（与第 8 周各天一致）：
  - 背景 #fdfaf2（米白），盒子白底 + 深灰 #6b6357 手绘描边
  - 强调色不超过 4 种柔和色：蓝 #4a7fa5 / 橙 #a8772e / 绿 #5a8a5a / 红 #b0605a
  - 线条带轻微抖动（L 段折线），圆头笔触，线宽 2 左右
  - 手写感字体栈：Comic Sans MS / Comic Neue / Kaiti SC / 楷体 / cursive

图中全部数字来自 2026-11-12 的真实运行：
  layout_lab.py 的 20/20、test_layout.py 的 20/20、
  mlir-opt --canonicalize 的 (0,32,4,1,8) 与 (23,30)、
  mlir-cpu-runner 的输出 23/23、计时 0.4µs vs 0.215ms。

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

rng = random.Random(58)

# 真实数据（layout_lab.py / run_all.sh 于 2026-11-12 运行）
NHWC_FLAT = [0, 8, 16, 24, 1, 9, 17, 25, 2, 10, 18, 26, 3, 11, 19, 27,
             4, 12, 20, 28, 5, 13, 21, 29, 6, 14, 22, 30, 7, 15, 23, 31]


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


def sketch_line(x0, y0, x1, y1, stroke=STROKE, sw=2.0, arrow=False):
    d = f"M {x0:.1f},{y0:.1f} L {x1:.1f},{y1:.1f}"
    out = [f'<path d="{d}" fill="none" stroke="{stroke}" '
           f'stroke-width="{sw}" stroke-linecap="round" '
           f'stroke-linejoin="round"/>']
    if arrow:
        ang = math.atan2(y1 - y0, x1 - x0)
        for da in (math.radians(152), math.radians(-152)):
            ax = x1 + 9.0 * math.cos(ang + da)
            ay = y1 + 9.0 * math.sin(ang + da)
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


def strip32(x, y, cw, ch, values, tint_idx=None, tint_color="blue",
            label=None, note=None):
    """32 格存储条带：格子序号 = 物理偏移，格子里的字 = 元素值。"""
    parts = []
    gap = 2
    if label:
        parts.append(txt(x, y - 7, label, 12.5, INK, bold=True))
    for i, v in enumerate(values):
        fill = TINT[tint_color] if tint_idx and i in tint_idx else "#ffffff"
        parts.append(sketch_rect(x + i * (cw + gap), y, cw, ch, fill,
                                 STROKE, 1.4, 3))
        parts.append(txt(x + i * (cw + gap) + cw / 2, y + ch / 2 + 4,
                         str(v), 10.5, INK, "middle"))
    if note:
        parts.append(txt(x, y + ch + 16, note, 11, MUTED))
    return "".join(parts)


# ============================================================
# 图 1：全局定位——第 58 天在计划与编译链路中的位置
# ============================================================

def img1():
    W, H = 1240, 790
    p = [header(W, H,
                "第 58 天全貌：NCHW vs NHWC——布局顺序是图优化的第一批决策",
                "上：六阶段里程碑与第 9 周日程｜中：昨天到今天的衔接｜下：Layout 选择在编译链路里的位置")]

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
            b, _ = badge(x + sw_ / 2 - 36, sy - 14, "今天 Day 58", RED)
            p.append(b)
        if i < 5:
            p.append(sketch_line(x + sw_ + 1, sy + sh / 2,
                                 x + sw_ + gap - 1, sy + sh / 2,
                                 MUTED, 1.5, arrow=True))
    p.append(txt(40, 178, "第 84 天里程碑：Layout 优化、融合收益判断和数值验证体系"
                          "——昨天学会描述布局，今天开始按布局做决策", 11.5, MUTED))

    # ---- 中：第 9 周日程 ----
    p.append(txt(40, 216, "第 9 周：Tensor、Shape、Stride 与 Layout", 14,
                 INK, bold=True))
    days = [
        ("57", "Shape·Stride\nOffset·Contig.", False),
        ("58", "NCHW vs NHWC\n访存序列对比", True),
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

    # ---- 中下：衔接卡片 ----
    p.append(txt(40, 330, "昨天到今天：从「能描述布局」到「按布局做决策」", 14,
                 INK, bold=True))
    cards = [
        ("第 57 天打好的地基", "Shape / Stride / Offset /\nContiguous 四件套\n= 描述任何视图的"
         "「登记表」", TINT["white"], STROKE, MUTED),
        ("第 58 天要回答的", "NCHW 与 NHWC 两种物理摆法\n各自成全哪类访问模式？\n换布局是换登记表"
         "还是搬家？", TINT["blue"], BLUE, BLUE),
        ("后续谁要用它", "Day 59 Reshape 合法性\nDay 64-70 转置消除与融合\n都要先看懂布局与"
         "访存序列", TINT["white"], STROKE, MUTED),
    ]
    cx, cy, cw2, ch2 = 40, 348, 373, 128
    for i, (t, body, fill, sc, tc) in enumerate(cards):
        x = cx + i * (cw2 + 17)
        p.append(sketch_rect(x, cy, cw2, ch2, fill, sc, 2.4, 5))
        p.append(txt(x + 14, cy + 24, t, 12.5, tc, bold=True))
        for k, line in enumerate(body.split("\n")):
            p.append(txt(x + 14, cy + 48 + k * 19, line, 11.5, INK))
        if i < 2:
            p.append(sketch_line(x + cw2 + 1, cy + ch2 / 2,
                                 x + cw2 + 16, cy + ch2 / 2, MUTED, 1.8,
                                 arrow=True))

    # ---- 下：编译链路 ----
    p.append(txt(40, 518, "Layout 选择发生在编译链路的哪一站（今天用真实 mlir-opt / "
                          "mlir-cpu-runner 验证元数据这一环）：", 13.5, INK, bold=True))
    lx, ly, lw2, lh2 = 40, 534, 360, 116
    p.append(sketch_rect(lx, ly, lw2, lh2, "#ffffff", STROKE, 2.0, 5))
    p.append(txt(lx + 14, ly + 22, "框架图：NCHW 传统默认", 12, BLUE, bold=True))
    p.append(txt(lx + 14, ly + 45, "PyTorch / ONNX 的 tensor", 11.5, INK))
    p.append(txt(lx + 14, ly + 62, "  tensor<1x4x2x4xf32>", 11.5, INK))
    p.append(txt(lx + 14, ly + 84, "  只声明逻辑形状，不说数据怎么排", 11, MUTED))
    p.append(txt(lx + 14, ly + 103, "→ 用户视角：下标 (n,c,h,w)", 11, MUTED))
    x2 = lx + lw2 + 30
    p.append(sketch_line(x2 - 26, ly + lh2 / 2, x2 - 4, ly + lh2 / 2,
                         ORANGE, 2.4, arrow=True))
    p.append(sketch_rect(x2, ly, lw2, lh2, TINT["orange"], ORANGE, 2.4, 5))
    p.append(txt(x2 + 14, ly + 22, "图优化：Layout 决策（今天的位置）", 12, ORANGE,
                 bold=True))
    p.append(txt(x2 + 14, ly + 45, "问每个算子：沿哪维归约/扫描？", 11.5, INK))
    p.append(txt(x2 + 14, ly + 62, "整图选一种摆法，算转换收益", 11.5, INK))
    p.append(txt(x2 + 14, ly + 84, "布局是 memref 类型上的常数元数据", 11, MUTED))
    p.append(txt(x2 + 14, ly + 103, "→ strided<[32, 4, 1, 8]>", 11, MUTED))
    x3 = x2 + lw2 + 30
    p.append(sketch_line(x3 - 26, ly + lh2 / 2, x3 - 4, ly + lh2 / 2,
                         GREEN, 2.4, arrow=True))
    p.append(sketch_rect(x3, ly, 1240 - 40 - x3, lh2, "#ffffff", GREEN, 2.0, 5))
    p.append(txt(x3 + 14, ly + 22, "设备：只吃连续数据", 12, GREEN, bold=True))
    p.append(txt(x3 + 14, ly + 45, "向量单元：128 位一次吞 4×f32", 11.5, INK))
    p.append(txt(x3 + 14, ly + 62, "Cube/矩阵单元偏好 NHWC 摆法", 11.5, INK))
    p.append(txt(x3 + 14, ly + 84, "（昇腾/GPU 上 channels_last 常是", 11, MUTED))
    p.append(txt(x3 + 14, ly + 103, "  卷积类算子的更快路径）", 11, MUTED))

    p.append(txt(40, 686, "实测环境（全部真实运行）：Linux aarch64 · Python 3.11.4 · "
                          "numpy 1.26.4 · Ubuntu LLVM 18.1.8（mlir-opt + mlir-cpu-runner）· "
                          "torch 2.7.1+cpu", 11, MUTED))
    p.append(txt(40, 708, "今日战绩：layout_lab 20/20 · test_layout 20/20 · "
                          "canonicalize 折叠出 (0,32,4,1,8) 与 (23,30) · cpu-runner 双布局取数输出 23 / 23",
                 11, MUTED))
    p.append(txt(40, 730, "边界说明：设备偏好一句是背景知识（本机无 NPU 硬件，未在 NPU 上运行）；"
                          "访存序列与元数据结论全部来自本机实测", 11, MUTED))
    p.append("</svg>")
    (OUT / "01-overview.svg").write_text("\n".join(p), encoding="utf-8")


# ============================================================
# 图 2：核心机制——4D 偏移公式与两种摆法的嵌套结构
# ============================================================

def img2():
    W, H = 1240, 965
    p = [header(W, H,
                "核心机制：NCHW / NHWC 只是两套不同的 Strides，套娃结构决定谁挨着谁",
                "上：同一逻辑张量的两张元信息卡｜中：4D 偏移公式与同一像素的两个家｜下：两种嵌套结构与 MLIR 类型对照")]

    # ---- 上：两张元信息卡 ----
    cards = [
        ("物理 NCHW（框架默认）", "nchw = arange(32).reshape(1,4,2,4)",
         "逻辑形状 (1, 4, 2, 4)  下标 (n, c, h, w)",
         "元素 strides = (32, 8, 4, 1)   最内维 = W",
         "C-contiguous = True（W 方向相邻=物理相邻）", BLUE, TINT["blue"]),
        ("物理 NHWC（重排之后）", "nhwc = ascontiguousarray(nchw.transpose(0,2,3,1))",
         "逻辑形状 (1, 2, 4, 4)  下标 (n, h, w, c)",
         "元素 strides = (32, 16, 4, 1)   最内维 = C",
         "C-contiguous = True（C 方向相邻=物理相邻）", ORANGE, TINT["orange"]),
    ]
    cx, cy, cw2, ch2 = 52, 92, 560, 118
    for i, (t, src, f1, f2, f3, c, tint) in enumerate(cards):
        x = cx + i * (cw2 + 16)
        p.append(sketch_rect(x, cy, cw2, ch2, tint, c, 2.4, 5))
        p.append(txt(x + 14, cy + 22, t, 13, c, bold=True))
        p.append(txt(x + 14, cy + 42, src, 10, MUTED))
        p.append(txt(x + 14, cy + 64, f1, 12, INK))
        p.append(txt(x + 14, cy + 84, f2, 12, INK, bold=True))
        p.append(txt(x + 14, cy + 104, f3, 11, MUTED))

    # ---- 中：公式 + 算例 ----
    fx, fy, fw, fh = 52, 234, 1136, 64
    p.append(sketch_rect(fx, fy, fw, fh, "#ffffff", RED, 3.0, 6))
    p.append(txt(fx + fw / 2, fy + 27,
                 "物理偏移 = Σ idx_k × strides_k （4D 也一样：把每个下标乘自己的步长再相加）",
                 17, RED, "middle", bold=True))
    p.append(txt(fx + fw / 2, fy + 52,
                 "（两条卡的字完全相同，差别只在 strides 那一行的四个数——布局的全部秘密就是这四个数）",
                 11.5, MUTED, "middle"))

    p.append(txt(52, 336, "算例：取同一个逻辑像素 (n=0, c=2, h=1, w=3)，逻辑值 v = 2×8 + 1×4 + 3 = 23：",
                 13, INK, bold=True))
    ex_y = 350
    p.append(sketch_rect(52, ex_y, 548, 92, TINT["blue"], BLUE, 2.0, 5))
    p.append(txt(66, ex_y + 24, "在 NCHW 里：offset = 2×8 + 1×4 + 3×1", 13, INK))
    p.append(txt(66, ex_y + 48, "= 23   ← 住在 23 号格，那格放着 23", 14, BLUE,
                 bold=True))
    p.append(txt(66, ex_y + 76, "memref.load %nchw[0, 2, 1, 3]", 10.5, MUTED))
    p.append(sketch_rect(640, ex_y, 548, 92, TINT["orange"], ORANGE, 2.0, 5))
    p.append(txt(654, ex_y + 24, "在 NHWC 里：offset = 1×16 + 3×4 + 2×1", 13, INK))
    p.append(txt(654, ex_y + 48, "= 30   ← 住在 30 号格，那格也放着 23", 14, ORANGE,
                 bold=True))
    p.append(txt(654, ex_y + 76, "memref.load %nhwc[0, 1, 3, 2]", 10.5, MUTED))
    p.append(txt(52, ex_y + 116,
                 "同一逻辑像素，两个家（23 号 vs 30 号）——cpu-runner 真实执行两次 load，都取回 23",
                 12.5, RED, bold=True))

    # ---- 下：嵌套结构图 ----
    p.append(txt(52, 500, "套娃视角：4D 摆法 = 谁套在谁里面（最里那一排才是内存里真正挨着的元素）",
                 13.5, INK, bold=True))

    # 左：NCHW 嵌套 N⊃C⊃H⊃W
    nx, ny, nw, nh = 52, 516, 548, 300
    p.append(sketch_rect(nx, ny, nw, nh, "#ffffff", STROKE, 2.2, 5))
    p.append(txt(nx + 12, ny + 20, "NCHW：N ⊃ C ⊃ H ⊃ W", 13, BLUE, bold=True))
    cw3 = (nw - 40) / 2  # 每个C框内两个H框
    for c in range(4):
        cy2 = ny + 30 + c * 64
        p.append(sketch_rect(nx + 14, cy2, nw - 28, 58, TINT["blue"], BLUE, 1.5, 4))
        p.append(txt(nx + 22, cy2 + 16, f"C{c}", 10, BLUE, bold=True))
        for h in range(2):
            hx = nx + 50 + h * ((nw - 78) / 2 + 6)
            p.append(sketch_rect(hx, cy2 + 6, (nw - 78) / 2 - 4, 46,
                                 "#ffffff", STROKE, 1.3, 4))
            p.append(txt(hx + 4, cy2 + 18, f"h{h}", 9, MUTED))
            for w in range(4):
                wx = hx + 22 + w * (((nw - 78) / 2 - 30) / 4)
                p.append(sketch_rect(wx, cy2 + 20, ((nw - 78) / 2 - 34) / 4, 26,
                                     "#ffffff", BLUE, 1.2, 3))
                p.append(txt(wx + ((nw - 78) / 2 - 34) / 8, cy2 + 37, f"w{w}",
                             9, BLUE, "middle"))
    p.append(txt(nx + 14, ny + nh + 22, "最内一排 4 格 = 一行像素（固定 c、h，w=0..3）",
                 11.5, BLUE, bold=True))
    p.append(txt(nx + 14, ny + nh + 40, "→ 逐通道的空间扫描（pooling）友好", 11, MUTED))

    # 右：NHWC 嵌套 N⊃H⊃W⊃C
    nx2, ny2 = 640, 516
    p.append(sketch_rect(nx2, ny, nw, nh, "#ffffff", STROKE, 2.2, 5))
    p.append(txt(nx2 + 12, ny + 20, "NHWC：N ⊃ H ⊃ W ⊃ C", 13, ORANGE, bold=True))
    for h in range(2):
        hy = ny + 30 + h * 132
        p.append(sketch_rect(nx2 + 14, hy, nw - 28, 126, TINT["orange"], ORANGE,
                             1.5, 4))
        p.append(txt(nx2 + 22, hy + 16, f"H{h}", 10, ORANGE, bold=True))
        for w in range(4):
            wx = nx2 + 46 + w * ((nw - 92) / 4)
            p.append(sketch_rect(wx, hy + 6, (nw - 100) / 4, 112,
                                 "#ffffff", STROKE, 1.3, 4))
            p.append(txt(wx + 5, hy + 20, f"w{w}", 9, MUTED))
            for c in range(4):
                cyy = hy + 26 + c * 22
                p.append(sketch_rect(wx + 4, cyy, (nw - 100) / 4 - 8, 18,
                                     "#ffffff", ORANGE, 1.2, 3))
                p.append(txt(wx + 4 + ((nw - 100) / 4 - 8) / 2, cyy + 13, f"c{c}",
                             9, ORANGE, "middle"))
    p.append(txt(nx2 + 14, ny + nh + 22, "最内一排 4 格 = 一个像素的全部通道（固定 h、w）",
                 11.5, ORANGE, bold=True))
    p.append(txt(nx2 + 14, ny + nh + 40, "→ 通道归约（卷积/全连接）与向量装载友好", 11, MUTED))

    # ---- MLIR 脚注 ----
    p.append(txt(52, 898, "MLIR 类型对照（真实 IR）：物理 NCHW = memref<1x4x2x4xf32>（隐式 strides (32,8,4,1)）· "
                          "物理 NHWC = memref<1x2x4x4xf32>（隐式 (32,16,4,1)）", 11, MUTED))
    p.append(txt(52, 920, "NCHW 存储上的零拷贝 NHWC 视图 = memref.transpose → "
                          "memref<1x2x4x4xf32, strided<[32, 4, 1, 8]>>，--canonicalize 折成常数 (0,32,4,1,8)",
                 11, MUTED))
    p.append(txt(52, 942, "要点：布局 = strides 四元组；换元信息免费（transpose），换物理顺序才要搬数据（下一张图的对照实验）",
                 12, RED, bold=True))
    p.append("</svg>")
    (OUT / "02-mechanism.svg").write_text("\n".join(p), encoding="utf-8")


# ============================================================
# 图 3：访存序列对照——同一访问模式，两种物理摆法
# ============================================================

def img3():
    W, H = 1240, 1040
    p = [header(W, H,
                "访存序列对照：同一访问模式，两种摆法（全部取自 layout_lab.py 真实输出）",
                "每条条带 32 格：格子序号 = 物理偏移，格里的字 = 元素值（值 = 该元素的 NCHW 编号）")]

    cw_, ch_ = 26, 34
    sx = 100

    # 顶部：两条主条带
    p.append(txt(52, 92, "先认识两条存储条带：同一批 32 个值，两种物理顺序", 13, INK,
                 bold=True))
    p.append(strip32(sx, 122, cw_, ch_, list(range(32)), label="NCHW 物理（值恰好=物理位置）"))
    p.append(strip32(sx, 188, cw_, ch_, NHWC_FLAT,
                     label="NHWC 物理（重排后：0,8,16,24,1,9,17,25,…）"))

    # P1
    p.append(txt(52, 262, "P1 读一行像素：固定 c=0、h=0，w=0..3（空间扫描 / pooling 内层）", 13,
                 INK, bold=True))
    p.append(strip32(sx, 274, cw_, ch_, list(range(32)),
                     tint_idx={0, 1, 2, 3}, tint_color="blue"))
    p.append(txt(sx, 274 + ch_ + 15,
                 "NCHW 偏移 [0,1,2,3] → 连续段 [0..3]×4 · 1 个缓存行 · 128 位向量一次装载：可以",
                 11.5, BLUE, bold=True))
    p.append(strip32(sx, 340, cw_, ch_, NHWC_FLAT,
                     tint_idx={0, 4, 8, 12}, tint_color="orange"))
    p.append(txt(sx, 340 + ch_ + 15,
                 "NHWC 偏移 [0,4,8,12] → w 步长 = C = 4，四散 · 向量装载：不行",
                 11.5, ORANGE, bold=True))

    # P2
    p.append(txt(52, 428, "P2 取一个像素的全部通道：固定 h=0、w=0，c=0..3（通道归约 / 卷积内层）",
                 13, INK, bold=True))
    p.append(strip32(sx, 440, cw_, ch_, list(range(32)),
                     tint_idx={0, 8, 16, 24}, tint_color="orange"))
    p.append(txt(sx, 440 + ch_ + 15,
                 "NCHW 偏移 [0,8,16,24] → c 步长 = H·W = 8，四散 · 2 个缓存行 · 向量装载：不行",
                 11.5, ORANGE, bold=True))
    p.append(strip32(sx, 506, cw_, ch_, NHWC_FLAT,
                     tint_idx={0, 1, 2, 3}, tint_color="blue"))
    p.append(txt(sx, 506 + ch_ + 15,
                 "NHWC 偏移 [0,1,2,3] → 连续段 [0..3]×4 · 1 个缓存行 · 128 位向量一次装载：可以",
                 11.5, BLUE, bold=True))

    # P3
    p.append(txt(52, 594, "P3 取 c=1 的整幅空间平面：(h,w) 行优先（逐通道算子的全量输入）", 13,
                 INK, bold=True))
    p.append(strip32(sx, 606, cw_, ch_, list(range(32)),
                     tint_idx=set(range(8, 16)), tint_color="blue"))
    p.append(txt(sx, 606 + ch_ + 15,
                 "NCHW 偏移 [8..15] → 连续段 ×8 · 1 个缓存行 · 向量装载：可以",
                 11.5, BLUE, bold=True))
    p.append(strip32(sx, 672, cw_, ch_, NHWC_FLAT,
                     tint_idx={1, 5, 9, 13, 17, 21, 25, 29}, tint_color="orange"))
    p.append(txt(sx, 672 + ch_ + 15,
                 "NHWC 偏移 [1,5,9,13,17,21,25,29] → 步长 4，八散 · 2 个缓存行 · 向量装载：不行",
                 11.5, ORANGE, bold=True))

    # 底部：Layout 对照表（手绘版）
    p.append(txt(52, 752, "Layout 对照表（今日产出之一，数据全部实测）：", 13, INK, bold=True))
    tx0, ty0, rh = 52, 764, 30
    cols = [("", 130), ("NCHW（沿 W 连续）", 330), ("NHWC（沿 C 连续）", 330),
            ("谁占优", 160)]
    rows = [
        ("元素 strides", "(32, 8, 4, 1)", "(32, 16, 4, 1)", "—"),
        ("一行像素 w=0..3", "[0,1,2,3] 连续 ✓", "[0,4,8,12] 跳格", "NCHW"),
        ("像素全部通道 c=0..3", "[0,8,16,24] 跳格", "[0,1,2,3] 连续 ✓", "NHWC"),
        ("通道空间平面 c=1", "[8..15] 连续 ✓", "[1,5,…,29] 跳格", "NCHW"),
        ("128 位向量沿哪维", "沿 W（4×f32）", "沿 C（4×f32）", "各成全一类"),
        ("整体 memcpy", "连续 ✓", "连续 ✓", "打平"),
    ]
    # 表头
    xcur = tx0
    for (name, cwid) in cols:
        p.append(sketch_rect(xcur, ty0, cwid, rh, TINT["gray"], STROKE, 1.6, 4))
        p.append(txt(xcur + 10, ty0 + 20, name, 11.5, INK, bold=True))
        xcur += cwid
    for r, row in enumerate(rows):
        y = ty0 + (r + 1) * rh
        xcur = tx0
        for k, ((name, cwid), val) in enumerate(zip(cols, row)):
            fill = "#ffffff"
            if k == 2 and "✓" in val:
                fill = TINT["orange"]
            if k == 1 and "✓" in val:
                fill = TINT["blue"]
            p.append(sketch_rect(xcur, y, cwid, rh, fill, STROKE, 1.4, 4))
            color = INK
            if k in (1, 2):
                color = BLUE if "✓" in val else ORANGE
            if k == 3 and val == "NCHW":
                color = BLUE
            elif k == 3 and val == "NHWC":
                color = ORANGE
            p.append(txt(xcur + 10, y + 20, val, 11.5, color,
                         bold=("✓" in val or k == 3)))
            xcur += cwid
    p.append(txt(52, ty0 + (len(rows) + 1) * rh + 24,
                 "结论：没有「更好的布局」，只有「更配访问模式的布局」——NCHW 成全逐通道空间算子，"
                 "NHWC 成全通道归约与向量装载", 12.5, RED, bold=True))
    p.append(txt(52, ty0 + (len(rows) + 1) * rh + 44,
                 "（✓ 标记 = 该访问模式在此布局下物理连续；缓存行按 64B / 16×f32 计）", 11, MUTED))
    p.append("</svg>")
    (OUT / "03-access-sequences.svg").write_text("\n".join(p),
                                                 encoding="utf-8")


# ============================================================
# 图 4：对照实验——视图零收益 vs 重排真搬家 + MLIR 三连
# ============================================================

def img4():
    W, H = 1240, 880
    p = [header(W, H,
                "对照实验：NHWC 视图零成本但零收益，重排有成本才有收益",
                "上：同一句 transpose 的两种结局｜下：MLIR 三连（折叠元数据 / 折叠地址 / 真实执行）")]

    cw_, ch_ = 22, 30
    y0 = 96

    # ---- 左：视图 ----
    p.append(sketch_rect(52, y0, 548, 252, TINT["blue"], BLUE, 2.4, 5))
    p.append(txt(70, y0 + 26, "走法一：transpose(0,2,3,1) —— 只换索引习惯", 13.5,
                 BLUE, bold=True))
    b, _ = badge(70, y0 + 38, "np.shares_memory(nhwc_view, nchw) = True", BLUE)
    p.append(b)
    p.append(txt(70, y0 + 78, "元信息：shape=(1,2,4,4) · strides=(32,4,1,8) · C-contig=False",
                 11.5, INK))
    p.append(txt(70, y0 + 98, "P2（取像素全部通道）经视图的偏移：", 11.5, INK))
    p.append(strip32(70, y0 + 108, cw_, ch_, list(range(32)),
                     tint_idx={0, 8, 16, 24}, tint_color="orange"))
    p.append(txt(70, y0 + 148, "[0, 8, 16, 24] —— 与直接用 NCHW 索引一字不差！", 12,
                 ORANGE, bold=True))
    p.append(txt(70, y0 + 174, "代价（实测，588 KiB 张量）：0.4 µs/次 —— 换登记表", 11.5,
                 INK))
    p.append(txt(70, y0 + 196, "收益：访存序列没变，向量装载还是不行", 11.5, INK))
    p.append(txt(70, y0 + 224, "结论：零成本，也零收益（改善的是 API 不是物理）", 12.5,
                 BLUE, bold=True))

    # ---- 右：重排 ----
    x2 = 636
    p.append(sketch_rect(x2, y0, 548, 252, TINT["orange"], ORANGE, 2.4, 5))
    p.append(txt(x2 + 18, y0 + 26, "走法二：ascontiguousarray —— 真搬家", 13.5,
                 ORANGE, bold=True))
    b, _ = badge(x2 + 18, y0 + 38, "np.shares_memory(nhwc, nchw) = False", RED)
    p.append(b)
    p.append(txt(x2 + 18, y0 + 78, "元信息：shape=(1,2,4,4) · strides=(32,16,4,1) · C-contig=True",
                 11.5, INK))
    p.append(txt(x2 + 18, y0 + 98, "P2（取像素全部通道）经重排数组的偏移：", 11.5, INK))
    p.append(strip32(x2 + 18, y0 + 108, cw_, ch_, NHWC_FLAT,
                     tint_idx={0, 1, 2, 3}, tint_color="blue"))
    p.append(txt(x2 + 18, y0 + 148, "[0, 1, 2, 3] —— 一次 128 位向量装载搞定", 12,
                 BLUE, bold=True))
    p.append(txt(x2 + 18, y0 + 174, "代价（实测，1×3×224×224 f32）：0.215 ms/次 —— 搬家",
                 11.5, INK))
    p.append(txt(x2 + 18, y0 + 196, "收益：通道连续、缓存行 2→1、可向量化", 11.5, INK))
    p.append(txt(x2 + 18, y0 + 224, "结论：代价差约三个数量级（best-of-30，逐次略有波动），换来物理访存的真正改变", 12.5,
                 ORANGE, bold=True))

    # ---- 中：结论 ----
    p.append(txt(52, y0 + 286,
                 "编译器的活儿：判断这 0.215 ms 换来的连续性能不能在后续算子上赚回来——赚得回就插转换，赚不回就保持原布局",
                 13, RED, bold=True))

    # ---- 下：MLIR 三连 ----
    p.append(txt(52, y0 + 322, "MLIR 三连：同一件事，编译器零成本读出布局（全部真实输出）",
                 13.5, INK, bold=True))
    iy = y0 + 340
    iw_ = 1136
    p.append(sketch_rect(52, iy, iw_, 108, "#ffffff", STROKE, 2.0, 5))
    p.append(txt(66, iy + 22, "① 折叠元数据：transpose 视图的 (offset, strides) → 常数"
                 "（--canonicalize）", 11.5, MUTED))
    p.append(txt(66, iy + 48, "%t = memref.transpose %x (n,c,h,w) -> (n,h,w,c)"
                 "  :  memref<1x4x2x4xf32> to memref<1x2x4x4xf32, strided<[32, 4, 1, 8]>>",
                 11, INK))
    p.append(txt(66, iy + 74, "return %c0, %c32, %c4, %c1, %c8"
                 "        // offset=0, strides=(32,4,1,8) —— 与 numpy 视图同口径", 12,
                 GREEN))
    iy2 = iy + 124
    p.append(sketch_rect(52, iy2, iw_, 108, "#ffffff", STROKE, 2.0, 5))
    p.append(txt(66, iy2 + 22, "② 折叠地址：同一逻辑像素 (c=2,h=1,w=3) 在两种布局里的家"
                 "（--canonicalize）", 11.5, MUTED))
    p.append(txt(66, iy2 + 48, "@same_pixel_two_offsets  →  NCHW: 2×8+1×4+3 = 23"
                 "     NHWC: 1×16+3×4+2 = 30", 11, INK))
    p.append(txt(66, iy2 + 74, "return %c23, %c30"
                 "        // 两个家编译期就算出来了，不需要运行任何代码", 12, GREEN))
    iy3 = iy2 + 124
    p.append(sketch_rect(52, iy3, iw_, 108, TINT["green"], GREEN, 2.0, 5))
    p.append(txt(66, iy3 + 22, "③ 真实执行：mlir-cpu-runner 跑 @main，两种布局各取一次数",
                 11.5, MUTED))
    p.append(txt(66, iy3 + 48, "%va = memref.load %nchw[0, 2, 1, 3]"
                 "     %vb = memref.load %nhwc[0, 1, 3, 2]", 11, INK))
    p.append(txt(66, iy3 + 74, "输出： 23  /  23"
                 "        // 同一逻辑像素，两个家，取回同一个值（本机真实运行）", 12,
                 GREEN))

    p.append(txt(52, iy3 + 136,
                 "给 Day 59 埋钩子：reshape 的合法性检查，本质就是判断「新读序能不能用一组 strides 表达」"
                 "——今天看到的 strided<[...]> 就是那把尺子", 11.5, MUTED))
    p.append("</svg>")
    (OUT / "04-view-vs-repack.svg").write_text("\n".join(p),
                                               encoding="utf-8")


if __name__ == "__main__":
    img1()
    img2()
    img3()
    img4()
    for f in sorted(OUT.glob("*.svg")):
        print(f"wrote {f} ({f.stat().st_size} bytes)")
