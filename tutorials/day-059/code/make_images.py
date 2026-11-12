#!/usr/bin/env python3
"""make_images.py —— 第 59 天教程的四张手绘 sketch 风 SVG 信息图。

风格约定（与第 8/9 周各天一致）：
  - 背景 #fdfaf2（米白），盒子白底 + 深灰 #6b6357 手绘描边
  - 强调色不超过 4 种柔和色：蓝 #4a7fa5 / 橙 #a8772e / 绿 #5a8a5a / 红 #b0605a
  - 线条带轻微抖动（L 段折线），圆头笔触，线宽 2 左右
  - 手写感字体栈：Comic Sans MS / Comic Neue / Kaiti SC / 楷体 / cursive

图中全部数字来自 2026-11-12 的真实运行：
  reshape_lab.py 23/23、test_reshape.py 26/26（随机对拍 view=139 copy=39 error=22）、
  mlir-opt --canonicalize 折叠 (0,3,2,2,4,2,1) 与 (0,6,2)、roundtrip 折成恒等、
  mlir-cpu-runner 输出 6/8/10、计时 0.34 µs vs 42.133 ms vs 41.909 ms。

运行: python3 make_images.py   （在 code/ 目录下，输出到 ../images/）
"""

from __future__ import annotations

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

rng = random.Random(59)

# 真实数据（reshape_lab.py / run_all.sh 于 2026-11-12 运行）
XT_READ = [0, 4, 8, 1, 5, 9, 2, 6, 10, 3, 7, 11]
Z_READ = list(range(0, 24, 2))


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
        import math
        ang = math.atan2(y1 - y0, x1 - x0)
        L, A = 11, 0.5
        ax, ay = x1 - L * math.cos(ang), y1 - L * math.sin(ang)
        out.append(f'<path d="M {x1:.1f},{y1:.1f} L {ax:.1f},{ay - 4:.1f}" '
                   f'fill="none" stroke="{stroke}" stroke-width="{sw}" '
                   f'stroke-linecap="round"/>')
        out.append(f'<path d="M {x1:.1f},{y1:.1f} L {ax:.1f},{ay + 4:.1f}" '
                   f'fill="none" stroke="{stroke}" stroke-width="{sw}" '
                   f'stroke-linecap="round"/>')
    return "".join(out)


def sketch_poly(points, stroke=STROKE, sw=2.0, arrow=False):
    d = ("M " + " L ".join(f"{px:.1f},{py:.1f}" for px, py in points))
    out = [f'<path d="{d}" fill="none" stroke="{stroke}" '
           f'stroke-width="{sw}" stroke-linecap="round" '
           f'stroke-linejoin="round"/>']
    if arrow:
        (x0, y0), (x1, y1) = points[-2], points[-1]
        out.append(sketch_line(x0, y0, x1, y1, stroke, sw, arrow=True))
    return "".join(out)


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


# ============================================================
# 图 1：全貌——第 59 天在六阶段与第 9 周中的位置
# ============================================================

def img1():
    W, H = 1240, 790
    p = [header(W, H,
                "第 59 天全貌：Reshape 合法性——免费换标签，还是必须搬家？",
                "上：六阶段里程碑与第 9 周日程（今天第 3 天）｜中：昨天到今天的衔接｜下：合法性检查发生在编译链路的哪一站")]

    # ---- 上：里程碑 ----
    p.append(txt(40, 92, "168 天六阶段（今天是阶段三·第 9 周的第 3 天）：", 13.5,
                 INK, bold=True))
    miles = [
        ("阶段一\nC++/工具链", "Day 1-14", TINT["white"], STROKE, MUTED),
        ("阶段二\nMLIR 基础", "Day 15-56", TINT["white"], STROKE, MUTED),
        ("阶段三\nmini 编译器\n(进行中)", "Day 57-112", TINT["orange"], ORANGE, ORANGE),
        ("阶段四\n算子与调度", "Day 113-140", TINT["white"], STROKE, MUTED),
        ("阶段五\n性能与集成", "Day 141-154", TINT["white"], STROKE, MUTED),
        ("阶段六\n综合项目", "Day 155-168", TINT["white"], STROKE, MUTED),
    ]
    mw, mh, gap = 180, 74, 12
    for i, (t, d, fill, sc, tc) in enumerate(miles):
        x = 40 + i * (mw + gap)
        p.append(sketch_rect(x, 104, mw, mh, fill, sc,
                             2.6 if i == 2 else 1.8, 5))
        lines = t.split("\n")
        for k, line in enumerate(lines):
            p.append(txt(x + mw / 2, 122 + k * 16, line, 11.5, tc,
                         "middle", bold=(i == 2)))
        p.append(txt(x + mw / 2, 122 + len(lines) * 16 + 8, d, 10.5, MUTED,
                     "middle"))

    # 第 9 周日程
    p.append(txt(40, 214, "第 9 周（Shape/Layout 语义周）的日程：", 13.5, INK,
                 bold=True))
    week = [
        ("Day 57", "Shape / Stride /\nOffset / Contiguous\n四件套词汇表",
         TINT["white"], STROKE, MUTED),
        ("Day 58", "NCHW vs NHWC\n两套 Strides 各成全\n哪类访问模式",
         TINT["white"], STROKE, MUTED),
        ("Day 59", "Reshape 合法性：\n什么时候零拷贝？\n（今天）",
         TINT["orange"], ORANGE, ORANGE),
        ("Day 60", "Broadcast 规则\n（右对齐比较）", TINT["white"], STROKE, MUTED),
        ("Day 61+", "切片 / 广播进阶\n与算子接入……", TINT["white"], STROKE, MUTED),
    ]
    cw2, ch2 = 226, 96
    for i, (d, body, fill, sc, tc) in enumerate(week):
        x = 40 + i * (cw2 + 12)
        p.append(sketch_rect(x, 228, cw2, ch2, fill, sc, 2.6 if i == 2 else 1.8, 5))
        p.append(txt(x + 12, 250, d, 12.5, tc, bold=True))
        for k, line in enumerate(body.split("\n")):
            p.append(txt(x + 12, 272 + k * 18, line, 11.5, INK))
        if i < 4:
            p.append(sketch_line(x + cw2 + 1, 228 + ch2 / 2, x + cw2 + 11,
                                 228 + ch2 / 2, MUTED, 1.8, arrow=True))

    # ---- 中：衔接卡片 ----
    p.append(txt(40, 362, "昨天到今天：从「看懂布局」到「给 Reshape 定规则」", 14,
                 INK, bold=True))
    cards = [
        ("第 57-58 天打好的地基", "偏移公式 Σ idx×stride、\n视图 vs 重排两档代价、\nstrided<[...]> 这把尺子",
         TINT["white"], STROKE, MUTED),
        ("第 59 天要回答的", "同一条 reshape：\n什么时候只改元信息（view）？\n什么时候必须搬家（reject/copy）？",
         TINT["blue"], BLUE, BLUE),
        ("后续谁要用它", "Day 60 Broadcast 形状推导、\nDay 64-70 布局转换消除，\n都以今天的判定为前提",
         TINT["white"], STROKE, MUTED),
    ]
    cx, cy, cw3, ch3 = 40, 380, 373, 118
    for i, (t, body, fill, sc, tc) in enumerate(cards):
        x = cx + i * (cw3 + 17)
        p.append(sketch_rect(x, cy, cw3, ch3, fill, sc, 2.4, 5))
        p.append(txt(x + 14, cy + 24, t, 12.5, tc, bold=True))
        for k, line in enumerate(body.split("\n")):
            p.append(txt(x + 14, cy + 50 + k * 20, line, 11.5, INK))
        if i < 2:
            p.append(sketch_line(x + cw3 + 1, cy + ch3 / 2,
                                 x + cw3 + 16, cy + ch3 / 2, MUTED, 1.8,
                                 arrow=True))

    # ---- 下：编译链路 ----
    p.append(txt(40, 542, "合法性检查发生在编译链路的哪一站（今天用真实 mlir-opt / "
                          "mlir-cpu-runner 验证 Verifier 与执行这一环）：",
                 13.5, INK, bold=True))
    lx, ly, lw2, lh2 = 40, 558, 360, 120
    p.append(sketch_rect(lx, ly, lw2, lh2, "#ffffff", STROKE, 2.0, 5))
    p.append(txt(lx + 14, ly + 22, "框架图：reshape 只写形状", 12, BLUE, bold=True))
    p.append(txt(lx + 14, ly + 45, "x.reshape(3, 2, 2)  /  torch.flatten", 11.5, INK))
    p.append(txt(lx + 14, ly + 62, "  逻辑形状是类型的一部分", 11.5, INK))
    p.append(txt(lx + 14, ly + 84, "  但「能不能零拷贝」取决于源 strides", 11, MUTED))
    p.append(txt(lx + 14, ly + 106, "→ 用户视角：只声明目标形状", 11, MUTED))
    x2 = lx + lw2 + 30
    p.append(sketch_line(x2 - 26, ly + lh2 / 2, x2 - 4, ly + lh2 / 2,
                         ORANGE, 2.4, arrow=True))
    p.append(sketch_rect(x2, ly, lw2, lh2, TINT["orange"], ORANGE, 2.4, 5))
    p.append(txt(x2 + 14, ly + 22, "mini 编译器：Verifier（今天的位置）", 12,
                 ORANGE, bold=True))
    p.append(txt(x2 + 14, ly + 45, "第一关 infer_shape：元素数守恒 + -1", 11.5, INK))
    p.append(txt(x2 + 14, ly + 62, "第二关 try_view：读序能否仿射表达", 11.5, INK))
    p.append(txt(x2 + 14, ly + 84, "三出口：view（免费）/ reject（要 repack）", 11,
                 MUTED))
    p.append(txt(x2 + 14, ly + 106, "  / error（形状非法）", 11, MUTED))
    x3 = x2 + lw2 + 30
    p.append(sketch_line(x3 - 26, ly + lh2 / 2, x3 - 4, ly + lh2 / 2,
                         GREEN, 2.4, arrow=True))
    p.append(sketch_rect(x3, ly, 1240 - 40 - x3, lh2, "#ffffff", GREEN, 2.0, 5))
    p.append(txt(x3 + 14, ly + 22, "后端：只信通过验证的元信息", 12, GREEN, bold=True))
    p.append(txt(x3 + 14, ly + 45, "视图 → 指针不动，只换 strides", 11.5, INK))
    p.append(txt(x3 + 14, ly + 62, "repack → 显式插入搬运循环", 11.5, INK))
    p.append(txt(x3 + 14, ly + 84, "MLIR 对照：expand/collapse_shape", 11, MUTED))
    p.append(txt(x3 + 14, ly + 106, "  的 Verifier 就做这两关检查", 11, MUTED))

    p.append(txt(40, 716, "实测环境（全部真实运行）：Linux aarch64 · Python 3.11.4 · "
                          "numpy 1.26.4 · Ubuntu LLVM 18.1.8（mlir-opt + mlir-cpu-runner）",
                 11, MUTED))
    p.append(txt(40, 738, "今日战绩：reshape_lab 23/23 · test_reshape 26/26（含 200 组随机对拍 "
                          "view=139 copy=39 error=22）· canonicalize 折出 (0,3,2,2,4,2,1)、"
                          "(0,6,2) 与恒等 · cpu-runner 输出 6 / 8 / 10", 11, MUTED))
    p.append(txt(40, 760, "边界说明：计时为 best-of-30（0.34 µs vs 42.133 ms）；"
                          "「昇腾侧 repack 成本」未在 NPU 上实测，仅作背景", 11, MUTED))
    p.append("</svg>")
    (OUT / "01-overview.svg").write_text("\n".join(p), encoding="utf-8")


# ============================================================
# 图 2：核心机制——两关检查与 try_view 装箱算法
# ============================================================

def img2():
    W, H = 1240, 980
    p = [header(W, H,
                "核心机制：Reshape Verifier 的两关——元素数量守恒 + 读序的仿射可表达性",
                "上：两关三出口的判定流程｜中：try_view 三步装箱（真实例子 (3,4)→(3,2,2)）｜下：装箱失败的反例 (4,3)→(12,)")]

    # ---- 上：判定流程 ----
    p.append(txt(40, 92, "mini.reshape Verifier 的判定流程（reshape_lab.py 的 mini_reshape）：",
                 13.5, INK, bold=True))
    # 输入
    p.append(sketch_rect(40, 106, 200, 60, TINT["white"], STROKE, 2.0, 5))
    p.append(txt(140, 130, "输入：源 + new_shape", 12, INK, "middle", bold=True))
    p.append(txt(140, 152, "例：(3,4)/(4,1) + (3,2,2)", 10.5, MUTED, "middle"))
    # 第一关
    p.append(sketch_line(240, 136, 288, 136, STROKE, 2.2, arrow=True))
    p.append(sketch_rect(290, 106, 290, 60, TINT["blue"], BLUE, 2.4, 5))
    p.append(txt(435, 130, "第一关 infer_shape", 12.5, BLUE, "middle", bold=True))
    p.append(txt(435, 152, "元素数守恒？-1 至多一个？", 11, INK, "middle"))
    # error 出口
    p.append(sketch_line(580, 136, 622, 136, RED, 2.2, arrow=True))
    p.append(txt(592, 126, "否", 10.5, RED, "middle"))
    p.append(sketch_rect(624, 112, 200, 48, TINT["red"], RED, 2.2, 5))
    p.append(txt(724, 132, "error", 13, RED, "middle", bold=True))
    p.append(txt(724, 150, "cannot reshape array of size 12...", 9.5, MUTED, "middle"))
    # 第二关
    p.append(sketch_line(510, 166, 510, 208, STROKE, 2.2, arrow=True))
    p.append(txt(520, 194, "是", 10.5, MUTED))
    p.append(sketch_rect(290, 210, 290, 62, TINT["green"], GREEN, 2.4, 5))
    p.append(txt(435, 234, "第二关 try_view（装箱）", 12.5, GREEN, "middle", bold=True))
    p.append(txt(435, 256, "新读序能否用仿射 strides 表达？", 11, INK, "middle"))
    # reject / view 出口
    p.append(sketch_line(580, 241, 622, 241, RED, 2.2, arrow=True))
    p.append(txt(592, 231, "否", 10.5, RED, "middle"))
    p.append(sketch_rect(624, 217, 268, 48, TINT["red"], RED, 2.2, 5))
    p.append(txt(758, 237, "reject：要 repack", 12.5, RED, "middle", bold=True))
    p.append(txt(758, 255, "numpy 此时静默 copy（搬家）", 9.5, MUTED, "middle"))
    p.append(sketch_line(290, 241, 248, 241, GREEN, 2.2, arrow=True))
    p.append(txt(268, 231, "是", 10.5, GREEN, "middle"))
    p.append(sketch_rect(44, 217, 202, 48, TINT["green"], GREEN, 2.2, 5))
    p.append(txt(145, 237, "view：零拷贝", 12.5, GREEN, "middle", bold=True))
    p.append(txt(145, 255, "只发新 strides，数据不动", 9.5, MUTED, "middle"))

    # ---- 中：装箱三步 ----
    p.append(txt(40, 312, "第二关 try_view 的三步装箱（例子：x (3,4)/(4,1) → (3,2,2)，"
                          "真实输出 strides (4,2,1)）：", 13.5, INK, bold=True))
    steps = [
        ("第 1 步：剥掉源的 size-1 维", BLUE,
         "src 维 = [(3, stride 4), (4, stride 1)]\n（本例没有 size-1 维，原样保留）\nsize-1 维对偏移无贡献，先剔除"),
        ("第 2 步：源维合并成「可折叠块」", ORANGE,
         "自内向外：内维 (4, stride 1) 成块 [E=4, b=1]\n外维 stride 4 == E×b = 4×1 ✓ 并入\n→ 只剩一块 [E=12, b=1]"),
        ("第 3 步：目标维自内向外装箱", GREEN,
         "目标 (3,2,2)：2×2=4 个装进块（stride 1）\n目标第 m 维 stride = 块内已装容量 × b\n→ out = (4, 2, 1)，恰好装满 ✓"),
    ]
    sw, sh = 373, 118
    for i, (t, c, body) in enumerate(steps):
        x = 40 + i * (sw + 17)
        p.append(sketch_rect(x, 328, sw, sh, "#ffffff", c, 2.4, 5))
        p.append(txt(x + 14, 350, t, 12.5, c, bold=True))
        for k, line in enumerate(body.split("\n")):
            p.append(txt(x + 14, 374 + k * 20, line, 11, INK))
        if i < 2:
            p.append(sketch_line(x + sw + 1, 328 + sh / 2, x + sw + 16,
                                 328 + sh / 2, MUTED, 1.8, arrow=True))

    # 装箱可视化：源块 vs 目标装箱
    p.append(txt(40, 486, "装箱可视化（同一块 12 格连续内存，换三种切法，格子里是元素值）：",
                 13, INK, bold=True))
    cw_, ch_, gap = 78, 40, 4
    # 源 (3,4)
    p.append(txt(40, 516, "源 x：1 块 [E=12, b=1]，切成 3 行 × 4 列", 12, BLUE,
                 bold=True))
    for r in range(3):
        for c in range(4):
            x = 40 + c * (cw_ + gap)
            y = 524 + r * (ch_ + gap)
            fill = TINT["blue"] if r == 0 else "#ffffff"
            p.append(sketch_rect(x, y, cw_, ch_, fill, BLUE, 1.4, 3))
            p.append(txt(x + cw_ / 2, y + ch_ / 2 + 5, str(r * 4 + c), 13, INK,
                         "middle"))
    p.append(txt(40, 676, "↑ 高亮的一行 = 第 0 维 (i) +1 跨过的 4 格（stride 4）",
                 11, BLUE, bold=True))
    # 目标 (3,2,2)
    tx0 = 420
    p.append(txt(tx0, 516, "目标 (3,2,2)：每行拆成 2×2 两个小盒", 12, GREEN, bold=True))
    for r in range(3):
        for c in range(2):
            for k in range(2):
                x = tx0 + (c * 2 + k) * (58 + gap)
                y = 524 + r * (ch_ + gap)
                p.append(sketch_rect(x, y, 58, ch_, "#ffffff", GREEN, 1.4, 3))
                p.append(txt(x + 29, y + ch_ / 2 + 5, str(r * 4 + c * 2 + k), 12,
                             INK, "middle"))
            # 小盒套组框
            p.append(sketch_rect(tx0 + c * 2 * (58 + gap) - 2, 522 + r * (ch_ + gap) - 2,
                                 2 * 58 + gap + 4, ch_ + 4, TINT["green"], GREEN,
                                 1.2, 3))
    p.append(txt(840, 516, "新 strides = (4, 2, 1)：", 12, RED, bold=True))
    p.append(txt(840, 540, "第 0 维 +1 → 跳 4 格（一行）", 11.5, INK))
    p.append(txt(840, 560, "第 1 维 +1 → 跳 2 格（半个小盒）", 11.5, INK))
    p.append(txt(840, 580, "第 2 维 +1 → 跳 1 格（紧邻）", 11.5, INK))
    p.append(txt(840, 604, "下标 (1,1,0)：4 + 2 + 0 = 6 号格，", 11.5, RED))
    p.append(txt(840, 622, "住在 6 号格的值正是 6（cpu-runner 实测）", 11.5, RED,
                 bold=True))

    # ---- 下：反例 ----
    p.append(txt(40, 686, "装箱失败的反例：xT (4,3)/(1,4) → (12,)——目标维跨界，仿射性破产：",
                 13.5, INK, bold=True))
    # xT 的 12 格与蛇形读序
    cw2_, ch2_ = 62, 40
    for i in range(12):
        x = 40 + i * (cw2_ + 4)
        p.append(sketch_rect(x, 702, cw2_, ch2_, "#ffffff", STROKE, 1.4, 3))
        p.append(txt(x + cw2_ / 2, 702 + ch2_ / 2 + 5, str(i), 12.5, INK, "middle"))
    # 蛇形箭头：读序 [0,4,8,1,5,9,2,6,10,3,7,11]
    seq = XT_READ
    for k in range(len(seq) - 1):
        a, b = seq[k], seq[k + 1]
        xa = 40 + a * (cw2_ + 4) + cw2_ / 2
        xb = 40 + b * (cw2_ + 4) + cw2_ / 2
        yy = 702 + (ch2_ / 2 if k % 3 != 2 else 702 + 14)
        p.append(sketch_line(xa, 702 - 8 + (k % 3) * 6, xb, 702 - 8 + ((k + 1) % 3) * 6,
                             RED, 1.6, arrow=(k == len(seq) - 2)))
    p.append(txt(40, 772, "xT 的线性读序偏移 = [0,4,8,1,5,9,2,6,10,3,7,11]（真实输出）——"
                          "不是等差数列！", 12, RED, bold=True))
    boxes = [
        ("一维 (12,) 要求", "读序必须是等差：\noffset(i+1) - offset(i) 恒定\n= 仿射映射 strided<[s]>"),
        ("装箱怎么失败的", "块 1：[E=3, b=4]（内维 3 格，步长 4）\n外维 stride 1 ≠ 3×4=12，并不成块\n目标维 12 > E=3 → 跨界 → None"),
        ("两种结局", "mini.reshape：reject（要求显式 repack）\nnumpy：静默 copy——读序被规整成\n[0..11]，数据搬了家（图 3 有实测代价）"),
    ]
    for i, (t, body) in enumerate(boxes):
        x = 40 + i * (373 + 17)
        p.append(sketch_rect(x, 790, 373, 100, "#ffffff",
                             [RED, ORANGE, BLUE][i], 2.2, 5))
        p.append(txt(x + 14, 812, t, 12.5, [RED, ORANGE, BLUE][i], bold=True))
        for k, line in enumerate(body.split("\n")):
            p.append(txt(x + 14, 834 + k * 19, line, 11, INK))

    p.append(txt(40, 930, "要点：合法 reshape 的充要条件不是「源连续」而是「新读序仿射可表达」——"
                          "非连续的 z (12,2) 拍扁成 (12,) 也能 view（等差步长 2）", 12.5, RED,
                 bold=True))
    p.append(txt(40, 952, "MLIR 同口径：expand_shape / collapse_shape 的 Verifier 按 reassociation "
                          "分组检查打包条件；memref.reshape 要求源是 identity 布局", 11, MUTED))
    p.append("</svg>")
    (OUT / "02-mechanism.svg").write_text("\n".join(p), encoding="utf-8")


# ============================================================
# 图 3：实例对照——同一条 reshape 的三种命运
# ============================================================

def img3():
    W, H = 1240, 1000
    p = [header(W, H,
                "实例对照：同一批数据的 reshape，三种命运（全部来自 reshape_lab.py 真实输出）",
                "条带格号 = 物理偏移，格里的字 = 元素值；箭头是「按行主序读一遍」的物理轨迹")]

    # ---- 命运 1：x.reshape(12) → view ----
    p.append(txt(40, 96, "命运 ① 连续源 x (3,4)/(4,1) → (12,)：view（改元信息，0.34 µs/次）",
                 13.5, BLUE, bold=True))
    cw_, ch_ = 62, 40
    for i in range(12):
        x = 40 + i * (cw_ + 4)
        p.append(sketch_rect(x, 110, cw_, ch_, TINT["blue"] if i < 3 else "#ffffff",
                             BLUE, 1.4, 3))
        p.append(txt(x + cw_ / 2, 110 + ch_ / 2 + 5, str(i), 12.5, INK, "middle"))
    p.append(sketch_line(40 + 6, 100, 40 + 11 * (cw_ + 4) + 40, 100, BLUE, 2.2,
                         arrow=True))
    p.append(txt(40, 178, "读序偏移 [0,1,2,...,11]：等差（步长 1）→ 新 strides = (1,)，"
                          "数据一格未动", 11.5, INK))
    p.append(txt(40, 198, "np.shares_memory(x, x.reshape(12)) = True · "
                          "等价 MLIR：memref<3x4xf32> 上的 collapse_shape [[0,1]]", 11, MUTED))

    # ---- 命运 2：xT.reshape(12) → copy ----
    p.append(txt(40, 246, "命运 ② 转置视图 xT (4,3)/(1,4) → (12,)：numpy 静默 copy"
                          "（42.133 ms/次，约 12 万倍差距）", 13.5, RED, bold=True))
    for i in range(12):
        x = 40 + i * (cw_ + 4)
        p.append(sketch_rect(x, 260, cw_, ch_, "#ffffff", RED, 1.4, 3))
        p.append(txt(x + cw_ / 2, 260 + ch_ / 2 + 5, str(XT_READ[i]), 12.5, INK,
                     "middle"))
    # 蛇形读序
    for k in range(11):
        a, b = XT_READ[k], XT_READ[k + 1]
        xa = 40 + a * (cw_ + 4) + cw_ / 2
        xb = 40 + b * (cw_ + 4) + cw_ / 2
        p.append(sketch_line(xa, 252 + (k % 3) * 5, xb, 252 + ((k + 1) % 3) * 5,
                             RED, 1.5, arrow=(k == 10)))
    p.append(txt(40, 328, "读序偏移 [0,4,8,1,5,9,2,6,10,3,7,11]：非等差 → 装不下任何 strided<[s]>", 11.5, INK))
    p.append(txt(40, 348, "numpy 的解法：悄悄搬一次家——拷贝后的读序被规整成 [0..11]（上排格子已按新读序摆好）",
                 11.5, INK))
    p.append(txt(40, 368, "np.shares_memory(xT, xT.reshape(12)) = False · "
                          "mini.reshape 的策略：reject 并要求显式 repack（拒绝静默拷贝）", 11, MUTED))

    # ---- 命运 3：z.reshape(12) → 跨步 view ----
    p.append(txt(40, 416, "命运 ③ 跨步切片 z (2,6)/(12,2) → (12,)：view（非连续也能零拷贝，0.34 µs 级）",
                 13.5, GREEN, bold=True))
    cw2_, ch2_ = 40, 40
    for i in range(24):
        x = 40 + i * (cw2_ + 3)
        fill = TINT["green"] if i % 2 == 0 else "#ffffff"
        p.append(sketch_rect(x, 430, cw2_, ch2_, fill, GREEN if i % 2 == 0 else STROKE,
                             1.4, 3))
        if i % 2 == 0:
            p.append(txt(x + cw2_ / 2, 430 + ch2_ / 2 + 5, str(i), 11, INK, "middle"))
    p.append(sketch_line(40 + 4, 422, 40 + 23 * (cw2_ + 3) + 30, 422, GREEN, 2.2,
                         arrow=True))
    p.append(txt(40, 498, "读序偏移 [0,2,4,...,22]：等差（步长 2）→ 新 strides = (2,)，"
                          "绿色格 = z 真正占用的 12 格", 11.5, INK))
    p.append(txt(40, 518, "关键结论：合法性的判据是「读序等差（仿射）」，不是「源连续」——"
                          "z 并不连续，照样零拷贝", 11.5, RED, bold=True))
    p.append(txt(40, 538, "等价 MLIR：memref.collapse_shape … into memref<6xf32, strided<[2]>>"
                          "（非连续源只要满足打包条件，Verifier 放行）", 11, MUTED))

    # ---- 底：计时与语义对照 ----
    p.append(txt(40, 586, "实测计时（2048×2048 f32 ≈ 16 MiB，best-of-30，2026-11-12）：",
                 13.5, INK, bold=True))
    rows = [
        ("连续源  big.reshape(1,-1)", "视图：改元信息", "0.34 µs/次", GREEN),
        ("非连续源 bigT.reshape(-1)", "numpy 静默拷贝", "42.133 ms/次", RED),
        ("显式重排 ascontiguousarray(bigT)", "对照：搬家", "41.909 ms/次", ORANGE),
    ]
    for i, (a, b, c, col) in enumerate(rows):
        y = 600 + i * 44
        p.append(sketch_rect(40, y, 520, 36, "#ffffff", col, 1.8, 4))
        p.append(txt(54, y + 24, a, 12, INK))
        p.append(txt(330, y + 24, b, 11.5, MUTED))
        p.append(txt(500, y + 24, c, 12.5, col, "end", bold=True))
    p.append(txt(40, 746, "视图与拷贝差距约 123605 倍——同一条 reshape 语句，"
                          "输入连续性不同，代价差 4~5 个数量级", 12.5, RED, bold=True))

    # 右侧：语义不变 + 判定表要点
    p.append(sketch_rect(620, 586, 580, 160, TINT["white"], STROKE, 2.0, 5))
    p.append(txt(634, 610, "无论哪种命运，逻辑内容都不变（判定表的语义底座）：", 12.5, INK,
                 bold=True))
    p.append(txt(634, 634, "· view / copy 结果都逐元素 == 源展开（lab 断言 PASS）", 11.5, INK))
    p.append(txt(634, 656, "· view 与源共享存储；copy 不共享（np.shares_memory）", 11.5, INK))
    p.append(txt(634, 678, "· error 只在元素数违规时出现（5,3）、(-1,5)、(-1,-1)", 11.5, INK))
    p.append(txt(634, 704, "15/15 组判定表用例：mini 预测与 numpy 实测完全一致", 12,
                 GREEN, bold=True))
    p.append(txt(634, 726, "200 组随机对拍：view=139 · copy=39 · error=22，零失配", 12,
                 GREEN, bold=True))

    p.append(txt(40, 782, "同一条 reshape 的决策树（编译器视角）：", 13.5, INK, bold=True))
    tree = [
        ("目标读序仿射可表达？", BLUE, "是 → 发新 strides（view）\n指针不动，O(1)", GREEN),
        ("", STROKE, "否 → 必须真重排（reject/repack）\n代价 O(N)，见上面 42 ms 那行", RED),
        ("元素数守恒？", ORANGE, "否 → error\n静态拦住，别等运行期越界", RED),
    ]
    for i, (q, qc, body, bc) in enumerate(tree[:2]):
        x = 40 + i * 410
        p.append(sketch_rect(x, 798, 176, 56, TINT["blue"] if i == 0 else TINT["red"], qc, 2.0, 4))
        p.append(txt(x + 88, 822, q if q else "否", 11.5, qc, "middle", bold=True))
        p.append(txt(x + 88, 842, "（try_view 的装箱判定）" if i == 0 else "", 10, MUTED, "middle"))
        p.append(sketch_line(x + 176, 826, x + 196, 826, qc, 2.0, arrow=True))
        p.append(sketch_rect(x + 198, 798, 190, 56, "#ffffff", bc, 2.0, 4))
        for k, line in enumerate(body.split("\n")):
            p.append(txt(x + 210, 818 + k * 18, line, 10.5, INK))
    p.append(sketch_rect(40, 866, 176, 56, TINT["orange"], ORANGE, 2.0, 4))
    p.append(txt(128, 890, "元素数守恒？", 11.5, ORANGE, "middle", bold=True))
    p.append(txt(128, 910, "（infer_shape 第一关）", 10, MUTED, "middle"))
    p.append(sketch_line(216, 894, 236, 894, ORANGE, 2.0, arrow=True))
    p.append(sketch_rect(238, 866, 190, 56, "#ffffff", RED, 2.0, 4))
    p.append(txt(250, 886, "否 → error：静态拦住", 10.5, INK))
    p.append(txt(250, 904, "（12 ≠ 5×3，直接报错）", 10.5, INK))
    p.append(txt(460, 890, "顺序：先查元素数（便宜、静态），再查仿射性（稍贵）。"
                            "reshape_gap.mlir 证明 memref.reshape 漏了第一关——"
                            "mini.reshape 必须补上（见教程 5.4 节）", 11.5, INK))
    p.append("</svg>")
    (OUT / "03-three-fates.svg").write_text("\n".join(p), encoding="utf-8")


# ============================================================
# 图 4：判定表与 MLIR 三操作对照
# ============================================================

def img4():
    W, H = 1240, 950
    p = [header(W, H,
                "判定表与 MLIR 对照：mini vs numpy 全部一致；expand/collapse/reshape 各管一段",
                "上：15 组判定表的浓缩版（真实输出，完整表见 code/outputs/reshape_lab.txt）｜下：MLIR 三操作、折叠结果与 Verifier 缺口")]

    # ---- 上：判定表 ----
    p.append(txt(40, 92, "判定表（浓缩 9 行，C1–C15 全表 15/15 ok）：", 13.5, INK, bold=True))
    cols = [(40, "用例"), (210, "源 (strides)"), (370, "目标"),
            (470, "mini 预测"), (650, "numpy 实测"), (830, "对拍结论")]
    p.append(sketch_rect(40, 100, 1160, 26, TINT["gray"], STROKE, 1.6, 4))
    for x, t in cols:
        p.append(txt(x + 6, 118, t, 11.5, MUTED, bold=True))
    rows = [
        ("C1  连续源拍扁", "(3,4) (4,1)", "(12,)", "view (1,)", "view (1,)", "ok", GREEN),
        ("C3  连续源拆维", "(3,4) (4,1)", "(3,2,2)", "view (4,2,1)", "view (4,2,1)", "ok", GREEN),
        ("C6  转置视图拍扁", "(4,3) (1,4)", "(12,)", "reject", "copy", "ok", ORANGE),
        ("C8  转置尾部加1", "(4,3) (1,4)", "(4,3,1)", "view (1,4,0)", "view (1,4,4)", "ok", GREEN),
        ("C10 转置整回原形", "(4,3) (1,4)", "(3,4)", "reject", "copy", "ok", ORANGE),
        ("C11 列切片拍扁", "(3,2) (4,1)", "(6,)", "reject", "copy", "ok", ORANGE),
        ("C12 跨步切片拍扁", "(2,6) (12,2)", "(12,)", "view (2,)", "view (2,)", "ok", GREEN),
        ("C13 跨步切片换块", "(2,6) (12,2)", "(3,4)", "view (8,2)", "view (8,2)", "ok", GREEN),
        ("C14 元素数不守恒", "(3,4) (4,1)", "(5,3)", "error", "error", "ok", RED),
    ]
    for i, (a, b, c, d, e, f, col) in enumerate(rows):
        y = 130 + i * 30
        p.append(sketch_rect(40, y, 1160, 26, "#ffffff", STROKE, 1.2, 3))
        p.append(txt(46, y + 19, a, 11, INK))
        p.append(txt(216, y + 19, b, 11, INK))
        p.append(txt(376, y + 19, c, 11, INK))
        p.append(txt(476, y + 19, d, 11, BLUE if d.startswith("view") else (RED if d == "error" else ORANGE)))
        p.append(txt(656, y + 19, e, 11, GREEN if e.startswith("view") else (RED if e == "error" else ORANGE)))
        p.append(txt(836, y + 19, f, 11, col, bold=True))
    p.append(txt(40, 404, "注：mini 的 reject 与 numpy 的 copy 是同一事实的两种策略——都意味着「必须搬家」，"
                          "区别是 mini 拒绝、numpy 静默替你搬。size-1 维 stride 不唯一，对拍时跳过。",
                 11, MUTED))

    # ---- 下：MLIR 三操作 ----
    p.append(txt(40, 438, "MLIR 把 reshape 拆成三个操作（reshape_views.mlir，全部真实运行）：",
                 13.5, INK, bold=True))
    ops = [
        ("memref.expand_shape", BLUE, "拆维：一维拆成多维",
         "reassociation [[0],[1,2]]：\n(3,4) → (3,2,2)\nVerifier 静态查分组尺寸：\n4 ≠ 3×2 直接拒（bad 房间 3）"),
        ("memref.collapse_shape", ORANGE, "合维：多维并成一维",
         "非连续源也可：\nsubview (3,2)/(4,2) → (6,)/(2)\nVerifier 查打包条件：\n外 stride 4 == 2×2 ✓"),
        ("memref.reshape", GREEN, "通用：形状来自运行期",
         "%shape 操作数 [2,6]：\n(3,4) → (2,6)\n只收 identity 布局的源\n（bad 房间 2 拒转置源）"),
    ]
    ow, oh = 373, 150
    for i, (op, c, what, body) in enumerate(ops):
        x = 40 + i * (ow + 17)
        p.append(sketch_rect(x, 454, ow, oh, "#ffffff", c, 2.4, 5))
        p.append(txt(x + 14, 478, op, 12.5, c, bold=True))
        p.append(txt(x + 14, 498, what, 11, MUTED))
        for k, line in enumerate(body.split("\n")):
            p.append(txt(x + 14, 522 + k * 20, line, 11, INK))

    # ---- 实测战绩 ----
    p.append(txt(40, 640, "四连实测战绩（run_all.sh 真实输出，已存 code/outputs/）：",
                 13.5, INK, bold=True))
    results = [
        ("① --canonicalize：元数据折成常数", BLUE,
         "expand_shape → return %c0,%c3,%c2,%c2,%c4,%c2,%c1\n即 (offset=0, sizes=3,2,2, strides=4,2,1)\ncollapse_shape → (0, 6, 2)：offset 0、size 6、stride 2"),
        ("② 往返折叠：expand 后 collapse 回原形", GREEN,
         "canonicalize 直接折成 return %arg0（恒等）\n「仅修改元信息」的变换编译期免费抵消\n——Day 64-70 消除冗余转换的同款机制"),
        ("③ mlir-cpu-runner 真实执行", ORANGE,
         "拆维视图取 (1,1,0) → 打印 6\n合维视图取 (4) → 打印 8\n运行期 reshape [2,6] 取 (1,4) → 打印 10"),
        ("④ Verifier 的缺口：reshape_gap.mlir", RED,
         "源 3×4（12 元素）→ 结果类型静态写 5×3（15）\nmemref.reshape 居然放行（exit=0）！\nmini.reshape 的 infer_shape 必须补上这一关"),
    ]
    rw, rh = 574, 96
    for i, (t, c, body) in enumerate(results):
        x = 40 + (i % 2) * (rw + 12)
        y = 654 + (i // 2) * (rh + 14)
        p.append(sketch_rect(x, y, rw, rh, "#ffffff", c, 2.2, 5))
        p.append(txt(x + 14, y + 22, t, 12.5, c, bold=True))
        for k, line in enumerate(body.split("\n")):
            p.append(txt(x + 14, y + 44 + k * 17, line, 10.5, INK))

    p.append(txt(40, 880, "要点：expand/collapse 的 Verifier 把「元素数量」和「打包条件」都静态拦住；"
                          "memref.reshape 因形状来自运行期，静态检查最弱——", 12.5, RED, bold=True))
    p.append(txt(40, 902, "这正是学习计划让 mini.reshape「增加元素数量和 Shape 检查」的工程动机："
                          "静态可见的约束，就该在 Verifier 静态拦住。", 12.5, RED, bold=True))
    p.append(txt(40, 926, "实测环境：Linux aarch64 · Python 3.11.4 · numpy 1.26.4 · "
                          "Ubuntu LLVM 18.1.8 · reshape_lab 23/23 · test_reshape 26/26", 11, MUTED))
    p.append("</svg>")
    (OUT / "04-verdict-and-mlir.svg").write_text("\n".join(p), encoding="utf-8")


if __name__ == "__main__":
    img1()
    img2()
    img3()
    img4()
    for f in sorted(OUT.glob("*.svg")):
        print(f"{f.name}: {f.stat().st_size} bytes")
