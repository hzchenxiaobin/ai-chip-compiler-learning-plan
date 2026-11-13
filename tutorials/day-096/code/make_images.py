#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第 96 天教程插图生成器：手绘 sketch 风（Excalidraw-like）SVG。

用法：  python3 code/make_images.py
输出：  images/01-overview.svg        第 14 周链路定位（技术信息图）
        images/02-unroll-mechanism.svg 展开的主循环+尾部机制与代码膨胀（技术信息图）
        images/03-contiguity.svg      向量化对连续访问的要求（技术信息图）
        images/04-results.svg         真实性能/代码体积结果（技术信息图）

图中所有数字（195/160/110、1167/2231/3069B、1121/2283B、3.21/14.26 GFLOPS、
116/194/372 条指令……）均来自本目录 outputs/ 下的真实运行记录，无虚构。
"""

import html
import math
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, "..", "images"))
os.makedirs(OUT, exist_ok=True)

INK = "#3b352d"      # 主文字
GRAY = "#84796a"     # 次文字
LINE = "#6b6357"     # 描边
BG = "#fdfaf2"       # 米白背景
CARD = "#ffffff"
SOFT = "#faf7ee"
BLUE, BLUE_BG = "#5d8fc9", "#f3f7fc"
ORANGE, ORANGE_BG = "#a8772e", "#fbf4e6"
GREEN, GREEN_BG = "#7d9b6a", "#f3f6f0"
RED, RED_BG = "#c9705d", "#faeded"

FONT = "Comic Sans MS, Comic Neue, Segoe Print, Kaiti SC, KaiTi, 楷体, cursive"


def esc(s):
    return html.escape(s, quote=False)


class SVG:
    def __init__(self, width, height):
        self.w, self.h = width, height
        self.parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
            f'height="{height}" viewBox="0 0 {width} {height}">',
            f'<rect width="{width}" height="{height}" fill="{BG}"/>',
        ]
        self.n = 0

    def text(self, x, y, s, size=10, fill=INK, anchor="middle", bold=False):
        self.parts.append(
            f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" '
            f'fill="{fill}" text-anchor="{anchor}" font-weight="'
            f'{"bold" if bold else "normal"}">{esc(s)}</text>')

    def _jseg(self, x1, y1, x2, y2, amp, rng, step=26.0):
        L = math.hypot(x2 - x1, y2 - y1)
        n = max(1, int(L / step))
        dx, dy = (x2 - x1) / n, (y2 - y1) / n
        L = max(L, 1e-9)
        nx, ny = -dy / L, dx / L
        pts = [(x1, y1)]
        for i in range(1, n):
            o = rng.uniform(-amp, amp)
            pts.append((x1 + dx * i + nx * o, y1 + dy * i + ny * o))
        pts.append((x2, y2))
        return "M " + " L ".join(f"{p[0]:.1f},{p[1]:.1f}" for p in pts)

    def rrect(self, x, y, w, h, fill=CARD, stroke=LINE, sw=2.2, r=None):
        rng = random.Random(1000 + self.n)
        self.n += 1
        if r is None:
            r = min(w, h) * 0.14
        V = [(x + r, y), (x + w - r, y), (x + w, y + r),
             (x + w, y + r * 0.4), (x + w, y + h - r), (x + w - r, y + h),
             (x + r, y + h), (x, y + h - r), (x, y + r)]
        segs = []
        for i in range(4):
            a, m, b = V[2 * i], V[2 * i + 1], V[2 * i + 2]
            nxt = V[2 * i + 3] if i < 3 else V[0]
            segs.append(self._jseg(a[0], a[1], m[0], m[1], 1.7, rng))
            segs.append(f"Q {b[0]:.1f},{b[1]:.1f} {b[0]:.1f},{b[1]:.1f}")
            segs.append(self._jseg(b[0], b[1], nxt[0], nxt[1], 1.7, rng))
        path = " ".join(segs) + " Z"
        self.parts.append(
            f'<path d="{path}" fill="{fill}" stroke="{stroke}" '
            f'stroke-width="{sw}" stroke-linecap="round" '
            f'stroke-linejoin="round"/>')

    def line(self, x1, y1, x2, y2, stroke=LINE, sw=1.8, amp=1.5):
        rng = random.Random(2000 + self.n)
        self.n += 1
        d = self._jseg(x1, y1, x2, y2, amp, rng)
        self.parts.append(
            f'<path d="{d}" fill="none" stroke="{stroke}" '
            f'stroke-width="{sw}" stroke-linecap="round"/>')

    def arrow(self, x1, y1, x2, y2, stroke=LINE, sw=1.8, ah=9):
        rng = random.Random(3000 + self.n)
        self.n += 1
        mx = (x1 + x2) / 2 + rng.uniform(-5, 5)
        my = (y1 + y2) / 2 + rng.uniform(-5, 5)
        d = f"M {x1},{y1} Q {mx},{my} {x2},{y2}"
        self.parts.append(
            f'<path d="{d}" fill="none" stroke="{stroke}" '
            f'stroke-width="{sw}" stroke-linecap="round"/>')
        ang = math.atan2(y2 - my, x2 - mx)
        for da in (math.radians(152), -math.radians(152)):
            hx = x2 + ah * math.cos(ang + da)
            hy = y2 + ah * math.sin(ang + da)
            self.parts.append(
                f'<path d="M {x2},{y2} L {hx:.1f},{hy:.1f}" fill="none" '
                f'stroke="{stroke}" stroke-width="{sw * 0.8:.2f}" '
                f'stroke-linecap="round"/>')

    def star(self, cx, cy, r, fill):
        rng = random.Random(4000 + self.n)
        self.n += 1
        pts = []
        for i in range(10):
            a = i * math.pi / 5 - math.pi / 2
            rr = (r if i % 2 == 0 else r * 0.45) * rng.uniform(0.85, 1.12)
            pts.append(f"{cx + rr * math.cos(a):.1f},{cy + rr * math.sin(a):.1f}")
        self.parts.append(
            f'<path d="M {" L ".join(pts)} Z" fill="{fill}" stroke="{fill}" '
            f'stroke-width="1.3" stroke-linejoin="round"/>')

    def save(self, name):
        self.parts.append("</svg>")
        path = os.path.join(OUT, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(self.parts))
        print("wrote", path, os.path.getsize(path), "bytes")


def header(s, title, sub):
    s.text(40, 38, title, size=20, fill=INK, anchor="start", bold=True)
    s.text(40, 61, sub, size=12, fill=GRAY, anchor="start")


# =====================================================================
# 图 1：第 96 天在“循环生成 → tiling → 尾部 → 展开”链路中的位置
# =====================================================================
def img_overview():
    s = SVG(1180, 800)
    header(s, "第 96 天：循环展开与向量化准备——把点循环做“规”，给向量化递入场券",
           "主例仍是 C = A(5x3)·B(3x7)：D95 的 min 钳制让点循环连续规整、体内零分支，今天在此之上做 Unroll 与内层连续性准备")

    # ---------- ① 第 14 周时间线 ----------
    s.text(60, 108, "① 第 14 周：tiling 修完正确性之后，今天的课题从“算得对”转到“跑得快”",
           size=13, fill=INK, anchor="start", bold=True)
    days = [
        (56, 130, 118, 86, CARD, LINE, "D88–89", "三重循环 + 读写", ["i/j/k 点循环", "load/store/累加"]),
        (190, 130, 118, 86, CARD, LINE, "D90", "非方形/边界 shape", ["1xN、Mx1、小 K", "8 组 shape 测试"]),
        (324, 130, 118, 86, CARD, LINE, "D92–93", "循环顺序 + 参数化", ["i/j/k 排列", "LoopOptions"]),
        (458, 130, 118, 86, CARD, LINE, "D94", "基础 Tiling", ["ceil-div 网格", "整除场景"]),
        (592, 130, 118, 86, CARD, LINE, "D95", "非整除尾部", ["min 钳制", "零越界/零重复"]),
        (726, 130, 128, 86, ORANGE_BG, ORANGE, "D96 今天", "展开 + 向量化准备", ["Unroll 收益/膨胀", "内层连续访问"]),
        (874, 130, 118, 86, SOFT, LINE, "D97", "多配置实验", ["控制变量", "性能表"]),
        (1008, 130, 110, 86, SOFT, LINE, "D98", "周复盘", ["权衡总账", "一张复盘图"]),
    ]
    for x, y, w, h, f, st, d, t, lines in days:
        s.rrect(x, y, w, h, fill=f, stroke=st, sw=2.2)
        s.text(x + w / 2, y + 20, d, size=8.8, fill=GRAY)
        s.text(x + w / 2, y + 40, t, size=10.2, bold=True,
               fill=ORANGE if f == ORANGE_BG else INK)
        for i, ln in enumerate(lines):
            s.text(x + w / 2, y + 58 + i * 14, ln, size=7.6, fill=GRAY)
    for a, b in [(174, 190), (308, 324), (442, 458), (576, 592), (710, 726),
                 (854, 874), (992, 1008)]:
        s.arrow(a, 173, b, 173, sw=1.4)

    # ---------- ② 今天动的那一格 ----------
    s.text(60, 268, "② 今天动的格子：尾部钳制定好“真实边界”之后、“编译成机器码”之前——点循环体怎么做才好向量化",
           size=13, fill=INK, anchor="start", bold=True)
    pipe = [
        (56, 290, 122, 96, CARD, LINE, "点循环(已钳制)", ["i/j/k 上界", "来自 D95 min"]),
        (196, 290, 148, 96, ORANGE_BG, ORANGE, "内层轴选择 + 展开（今天）", ["k 内 or j 内？", "Unroll U 份 + 尾部"]),
        (362, 290, 150, 96, CARD, LINE, "scf/affine IR", ["展开前后对照", "1167→2231 B"]),
        (528, 290, 146, 96, CARD, LINE, "机器码 (objdump)", ["116→372 条指令", "NEON 计数"]),
        (690, 290, 146, 96, CARD, LINE, "运行 + 计时", ["预热5+中位数15", "逐位正确性"]),
        (852, 290, 152, 96, SOFT, LINE, "给 D97 的输入", ["Tile×顺序×U", "搜索空间原料"]),
        (1020, 290, 98, 96, SOFT, LINE, "D97", ["性能表", "选最优"]),
    ]
    for x, y, w, h, f, st, t, lines in pipe:
        s.rrect(x, y, w, h, fill=f, stroke=st, sw=2.2)
        s.text(x + w / 2, y + 24, t, size=10.0, bold=True,
               fill=ORANGE if f == ORANGE_BG else INK)
        for i, ln in enumerate(lines):
            s.text(x + w / 2, y + 46 + i * 15, ln, size=8.6, fill=GRAY)
    for a, b in [(178, 196), (344, 362), (512, 528), (674, 690), (836, 852),
                 (1004, 1020)]:
        s.arrow(a, 338, b, 338, sw=1.6)

    s.text(196, 412, "橙色格要回答的问题：展开 K 还是展开内层 j？展开几份？收益在哪、膨胀在哪？——答案全在本页数字里。",
           size=9.8, fill=ORANGE, anchor="start")

    # ---------- ③ 今天的三组真实结论 ----------
    s.text(60, 472, "③ 三句话记住今天的三个结论（数字全部来自 outputs/ 真实运行）",
           size=13, fill=INK, anchor="start", bold=True)
    cards = [
        (56, 494, 332, 150, BLUE_BG, BLUE, "Unroll 的收益：砍循环控制",
         "主例 U=2：k 控制迭代 105→约 53",
         ["总控制迭代 195→160（unroll-k）", "标量实测 +1.5%（3.21→3.26 GFLOPS）",
          "收益真实但有限——控制开销本来就小"]),
        (404, 494, 332, 150, GREEN_BG, GREEN, "向量化的大头：内层连续",
         "reorder：j 放最内层（不展开）",
         ["-O3 实测 3.19→14.26 GFLOPS（4.5×）", "NEON fmul/fadd v0.4s：4 路",
          "GCC 原话：loop vectorized using 16 byte vectors"]),
        (752, 494, 332, 150, RED_BG, RED, "代码膨胀：U 越大越胖",
         "unroll-k：U=2/4/8 三档实测",
         ["机器码 194/260/372 条（基线 116）", "IR 1167→2231→3069 B；U=8 性能反降",
          "“展开越多越快”是错觉"]),
    ]
    for x, y, w, h, f, st, t, code, lines in cards:
        s.rrect(x, y, w, h, fill=f, stroke=st, sw=2.2)
        s.text(x + w / 2, y + 24, t, size=11.6, bold=True,
               fill={BLUE_BG: BLUE, GREEN_BG: GREEN, RED_BG: RED}[f])
        s.text(x + w / 2, y + 46, code, size=9.2, fill=INK, bold=True)
        for i, ln in enumerate(lines):
            s.text(x + w / 2, y + 70 + i * 16, ln, size=8.8,
                   fill=INK if i == 1 else GRAY)

    s.rrect(56, 676, 1028, 84, fill=SOFT, stroke=LINE, sw=2.0)
    s.text(570, 700, "今日产出（全部真实运行）：unroll 实现（4 内核 C++ + scf IR 生成器）＋ IR 对照（3 份 PARSE OK + 上游 affine 展开对照）＋ 性能数据（标量/向量化两张表）",
           size=10.4, fill=INK, bold=True)
    s.text(570, 722, "两句话记住今天：① 向量化吃的是“内层连续”，不是“展开”；② 展开是拿代码体积换控制开销，U 要用实验选，不能拍脑袋。",
           size=9.6, fill=GRAY)
    s.text(570, 744, "下一天（D97）：把 Tile、循环顺序、Unroll 因子放进同一张实验表，控制变量地找最优配置。",
           size=9.6, fill=GRAY)
    s.save("01-overview.svg")


# =====================================================================
# 图 2：展开的主循环 + 尾部循环机制（5x7x3, U=2）
# =====================================================================
def img_unroll_mechanism():
    s = SVG(1180, 830)
    header(s, "核心机制：主循环展开 U 份 + 尾部循环兜底——和上游 affine-loop-unroll 同一个骨架",
           "主例 5x7x3 的 k 循环 3 步、U=2：主循环盖住 k0/k1，尾部循环盖住 k2；上游 18x18x18、factor=4 也是这么拆的")

    # ---------- 左：展开前 ----------
    s.text(70, 106, "① 展开前：k 循环每次迭代做 1 份 MAC", size=12.5, fill=INK,
           anchor="start", bold=True)
    s.rrect(56, 126, 330, 240, fill=CARD, stroke=LINE, sw=2.2)
    s.text(76, 152, "for k in [0, K=3):        ← 每步先做控制", size=9.6,
           fill=INK, anchor="start")
    s.text(76, 172, "    C[i][j] += A[i][k] * B[k][j]   ← 1 份循环体", size=9.6,
           fill=INK, anchor="start")
    # 控制开销示意
    for i in range(3):
        y = 210 + i * 40
        s.rrect(86, y, 60, 26, fill=RED_BG, stroke=RED, sw=1.6)
        s.text(116, y + 17, "cmp+inc+br", size=7.2, fill=RED)
        s.rrect(166, y, 130, 26, fill=BLUE_BG, stroke=BLUE, sw=1.6)
        s.text(231, y + 17, f"1 x MAC  (k={i})", size=8.2, fill=BLUE)
        if i < 2:
            s.arrow(116, y + 26, 116, y + 40, stroke=RED, sw=1.2, ah=6)
    s.text(221, 348, "k 迭代 3 次 × 每次约 3 条控制指令", size=8.8, fill=GRAY)
    s.text(221, 336, "静态循环体：1 份", size=8.8, fill=GRAY, bold=True)

    # ---------- 中：展开后 ----------
    s.text(426, 106, "② 展开后 U=2：主循环步长 2、体内 2 份 MAC；尾部循环收零头",
           size=12.5, fill=INK, anchor="start", bold=True)
    s.rrect(412, 126, 350, 240, fill=CARD, stroke=LINE, sw=2.2)
    s.text(430, 152, "for k in [0, floor(3/2)*2=2) step 2:   ← 主循环", size=9.6,
           fill=INK, anchor="start")
    s.text(430, 170, "    2 份 MAC：k 和 k+1", size=9.6, fill=INK, anchor="start")
    s.text(430, 190, "for k in [2, K=3) step 1:              ← 尾部循环", size=9.6,
           fill=INK, anchor="start")
    # 主循环示意
    y0 = 214
    s.rrect(444, y0, 60, 26, fill=RED_BG, stroke=RED, sw=1.6)
    s.text(474, y0 + 17, "cmp+inc+br", size=7.2, fill=RED)
    s.rrect(524, y0, 216, 26, fill=BLUE_BG, stroke=BLUE, sw=1.6)
    s.text(632, y0 + 17, "2 x MAC  (k=0,1)", size=8.4, fill=BLUE)
    s.text(474, y0 + 42, "主循环 1 次迭代做 2 份计算", size=8.6, fill=GRAY)
    y1 = y0 + 66
    s.rrect(444, y1, 60, 26, fill=RED_BG, stroke=RED, sw=1.6)
    s.text(474, y1 + 17, "cmp+inc+br", size=7.2, fill=RED)
    s.rrect(524, y1, 130, 26, fill=GREEN_BG, stroke=GREEN, sw=1.6)
    s.text(589, y1 + 17, "1 x MAC  (k=2)", size=8.4, fill=GREEN)
    s.text(587, y1 + 42, "尾部循环兜住剩下的 1 步", size=8.6, fill=GRAY)
    s.text(587, 336, "静态循环体：2 + 1 = 3 份", size=8.8, fill=GRAY, bold=True)
    s.text(587, 348, "主例总控制迭代 195→160（少 35 次）", size=8.8, fill=GRAY)

    # ---------- 右：上游对照 ----------
    s.text(800, 106, "③ 上游对照：mlir-opt --affine-loop-unroll", size=12.5,
           fill=INK, anchor="start", bold=True)
    s.rrect(788, 126, 330, 240, fill=SOFT, stroke=LINE, sw=2.2)
    s.text(806, 150, "输入：18x18x18 三重 affine 循环", size=9.2, fill=INK, anchor="start")
    s.text(806, 168, "unroll-factor=4（18 % 4 = 2，有尾部）", size=9.2, fill=INK, anchor="start")
    s.text(806, 194, "affine.for %k = 0 to 16 step 4 {", size=9.0, fill=BLUE, anchor="start")
    s.text(822, 210, "… 4 份循环体（k..k+3）…", size=8.6, fill=BLUE, anchor="start")
    s.text(806, 226, "}", size=9.0, fill=BLUE, anchor="start")
    s.text(806, 244, "affine.for %k = 16 to 18 {", size=9.0, fill=GREEN, anchor="start")
    s.text(822, 260, "… 1 份循环体 …", size=8.6, fill=GREEN, anchor="start")
    s.text(806, 276, "}", size=9.0, fill=GREEN, anchor="start")
    s.line(806, 292, 1100, 292, sw=1.2)
    s.text(953, 312, "IR：1121 B / 1 份 mulf  →  2283 B / 5 份 mulf", size=9.0,
           fill=INK, bold=True)
    s.text(953, 330, "（outputs/upstream-unroll.txt）", size=8.2, fill=GRAY)
    s.text(953, 348, "主循环 + 尾部 = 所有展开实现的公共底座", size=8.8, fill=ORANGE)

    # ---------- 底部：三方账本 ----------
    s.text(60, 408, "④ 三层“代码膨胀”账本：源码份数 → IR 字节 → 机器码指令数（同一逻辑的三种长相）",
           size=12.5, fill=INK, anchor="start", bold=True)
    led = [
        (56, 430, 350, 178, CARD, LINE, "静态 MAC 份数（C++ 插桩 body_copies）",
         [("基线", 1), ("U=2", 3), ("U=4整除", 5)],
         "U 份主循环 + 1 份尾部；整除时尾部空转，体积照付"),
        (426, 430, 350, 178, CARD, LINE, "IR 大小（unrollgen.py，5x7x3，单位 B）",
         [("before", 1167), ("U=2", 2231), ("U=4整除", 3069)],
         "scf.for 5→6；MAC(算术) 1→3→5"),
        (796, 430, 322, 178, CARD, LINE, "机器码指令数（objdump，-O3）",
         [("基线", 116), ("U=2", 194), ("U=8", 372)],
         "unroll-j 更胖：420/538/480 条"),
    ]
    for x, y, w, h, f, st, t, bars, note in led:
        s.rrect(x, y, w, h, fill=f, stroke=st, sw=2.2)
        s.text(x + w / 2, y + 22, t, size=10.2, bold=True)
        maxv = max(v for _, v in bars)
        slot = (w - 60) / len(bars)
        bw = 52
        for i, (nm, v) in enumerate(bars):
            bx = x + 30 + i * slot + (slot - bw) / 2
            bh = 58 * v / maxv
            s.rrect(bx, y + 106 - bh, bw, max(bh, 6),
                    fill=BLUE_BG if i == 0 else (ORANGE_BG if i == 1 else RED_BG),
                    stroke=BLUE if i == 0 else (ORANGE if i == 1 else RED), sw=1.8)
            s.text(bx + bw / 2, y + 118, str(v), size=9.0, bold=True)
            s.text(bx + bw / 2, y + 132, nm, size=7.6, fill=GRAY)
        s.text(x + w / 2, y + 158, note, size=8.4, fill=GRAY)

    # ---------- 底部：箭头总结 ----------
    s.rrect(56, 636, 1062, 158, fill=SOFT, stroke=LINE, sw=2.0)
    s.text(76, 664, "⑤ 一笔交易的两侧（都实测过）：", size=11.5, fill=INK,
           anchor="start", bold=True)
    s.arrow(220, 700, 340, 700, stroke=GREEN, sw=2.4, ah=11)
    s.text(230, 688, "付出去的：控制迭代 ÷ U", size=9.6, fill=GREEN, anchor="start")
    s.text(280, 730, "主例 195→160（U=2）", size=8.8, fill=GREEN)
    s.arrow(620, 700, 740, 700, stroke=RED, sw=2.4, ah=11)
    s.text(636, 688, "换回来的：静态体 × (U+1)", size=9.6, fill=RED, anchor="start")
    s.text(672, 730, "IR 1167→2231 B（U=2）", size=8.8, fill=RED)
    s.text(580, 768, "收益封顶：控制开销只占小头（标量实测 +1.5%），膨胀却线性涨（U=8 时 372 条指令、性能反降）",
           size=9.6, fill=ORANGE, bold=True)
    s.text(580, 786, "所以第 97 天要把 U 放进实验表和 Cost Model，而不是当成“越大越好”的旋钮。",
           size=9.0, fill=GRAY)
    s.save("02-unroll-mechanism.svg")


# =====================================================================
# 图 3：向量化对连续访问的要求（k 内层 vs j 内层）
# =====================================================================
def img_contiguity():
    s = SVG(1180, 830)
    header(s, "向量化对连续访问的要求：内层沿 j 是“铺路”，内层沿 k 是“爬楼梯”",
           "行主序下：j 每加 1，B[k][j] 和 C[i][j] 都只挪 4 字节（同一行）；k 每加 1，B[k][j] 要跳一整行 N×4 字节")

    # ---------- 左：k 最内层 ----------
    s.text(70, 106, "① k 最内层（baseline / unroll-k）：B 沿列走 → 向量化被拒",
           size=12.5, fill=RED, anchor="start", bold=True)
    s.rrect(56, 124, 500, 300, fill=CARD, stroke=RED, sw=2.4)
    # B 矩阵图（k x j），列访问
    bx, by, cw, ch = 96, 190, 30, 26
    for r in range(5):
        for c in range(6):
            s.rrect(bx + c * cw, by + r * ch, cw, ch, fill=CARD, stroke=LINE,
                    sw=1.2, r=3)
    s.text(bx + 3 * cw, by - 14, "B (K x N，行主序)", size=9.4, fill=INK, bold=True)
    s.text(bx - 12, by + 3 * ch + 8, "k↓", size=10, fill=GRAY)
    s.text(bx + 3 * cw, by + 5 * ch + 20, "j →", size=10, fill=GRAY)
    # 列访问箭头（竖直，跨行）
    for c in (1, 3):
        s.arrow(bx + c * cw + 15, by + 6, bx + c * cw + 15, by + 5 * ch - 8,
                stroke=RED, sw=2.2)
    s.text(bx + 5 * cw - 10, by + 2 * ch, "step = N", size=8.6, fill=RED,
           anchor="start")
    s.text(bx + 5 * cw - 10, by + 2 * ch + 16, "= 384 个 float", size=8.6, fill=RED,
           anchor="start")
    s.text(bx + 5 * cw - 10, by + 2 * ch + 32, "= 1536 B", size=8.6, fill=RED,
           anchor="start")
    # 说明卡
    s.rrect(330, 176, 200, 150, fill=RED_BG, stroke=RED, sw=1.8)
    s.text(430, 196, "固定 i, j，k 每加 1：", size=9.2, fill=INK, bold=True)
    s.text(430, 214, "A[i][k] 沿行走 ✓", size=9.0, fill=GREEN)
    s.text(430, 232, "B[k][j] 跨行走 ✗", size=9.0, fill=RED)
    s.text(430, 250, "C[i][j] 不动 =", size=9.0, fill=GRAY)
    s.text(430, 268, "GCC 判定（原话）：", size=9.0, fill=INK, bold=True)
    s.text(430, 288, "“not suitable for", size=8.6, fill=RED)
    s.text(430, 304, "strided load”", size=8.6, fill=RED)
    s.text(430, 322, "（vec-report.txt :382）", size=7.8, fill=GRAY)
    s.text(300, 404, "实测：baseline/unroll-k 的机器码 NEON 向量指令 = 0 条；-O3 与 -O2 同速",
           size=9.2, fill=RED, anchor="start", bold=True)

    # ---------- 右：j 最内层 ----------
    s.text(636, 106, "② j 最内层（reorder / unroll-j）：B、C 都沿行走 → 向量化放行",
           size=12.5, fill=GREEN, anchor="start", bold=True)
    s.rrect(622, 124, 500, 300, fill=CARD, stroke=GREEN, sw=2.4)
    # B 矩阵图，行访问
    bx2, by2 = 662, 190
    for r in range(5):
        for c in range(6):
            s.rrect(bx2 + c * cw, by2 + r * ch, cw, ch, fill=CARD, stroke=LINE,
                    sw=1.2, r=3)
    s.text(bx2 + 3 * cw, by2 - 14, "B (K x N，行主序)", size=9.4, fill=INK, bold=True)
    s.text(bx2 - 12, by2 + 3 * ch + 8, "k↓", size=10, fill=GRAY)
    s.text(bx2 + 3 * cw, by2 + 5 * ch + 20, "j →", size=10, fill=GRAY)
    for r in (1, 3):
        s.arrow(bx2 + 8, by2 + r * ch + 13, bx2 + 6 * cw - 8, by2 + r * ch + 13,
                stroke=GREEN, sw=2.2)
    s.text(bx2 + 5 * cw - 10, by2 + 1 * ch, "step = 1", size=8.6, fill=GREEN,
           anchor="start")
    s.text(bx2 + 5 * cw - 10, by2 + 1 * ch + 16, "= 4 B，同一行", size=8.6,
           fill=GREEN, anchor="start")
    s.rrect(896, 176, 200, 150, fill=GREEN_BG, stroke=GREEN, sw=1.8)
    s.text(996, 196, "固定 i, k，j 每加 1：", size=9.2, fill=INK, bold=True)
    s.text(996, 214, "A[i][k] 不动 → 广播 ✓", size=9.0, fill=GREEN)
    s.text(996, 232, "B[k][j] 沿行走 ✓", size=9.0, fill=GREEN)
    s.text(996, 250, "C[i][j] 沿行走 ✓", size=9.0, fill=GREEN)
    s.text(996, 268, "GCC 判定（原话）：", size=9.0, fill=INK, bold=True)
    s.text(996, 288, "“loop vectorized using", size=8.6, fill=GREEN)
    s.text(996, 304, "16 byte vectors”", size=8.6, fill=GREEN)
    s.text(996, 322, "（vec-report.txt :398）", size=7.8, fill=GRAY)
    s.text(866, 404, "实测：reorder 的内层被编译成 ld1r + fmul v0.4s + fadd v0.4s，一次算 4 个 j",
           size=9.2, fill=GREEN, anchor="start", bold=True)

    # ---------- 中：向量化画面 ----------
    s.text(60, 468, "③ 一条 128-bit NEON 指令把 4 个 j 捆在一起算（v0.4s 的 4 个 lane）",
           size=12.5, fill=INK, anchor="start", bold=True)
    s.rrect(56, 488, 500, 190, fill=SOFT, stroke=LINE, sw=2.0)
    lane_y = 540
    s.rrect(140, lane_y, 330, 34, fill=BLUE_BG, stroke=BLUE, sw=2.2, r=8)
    lanes = ["j", "j+1", "j+2", "j+3"]
    for i, ln in enumerate(lanes):
        s.text(140 + 41 + i * 83, lane_y + 21, f"lane{i}: {ln}", size=9.4,
               fill=BLUE, bold=True)
        if i < 3:
            s.line(140 + 83 * (i + 1), lane_y + 6, 140 + 83 * (i + 1), lane_y + 28,
                   stroke=BLUE, sw=1.0)
    s.text(305, 526, "v0.4s  =  fmul(B 行的一段 128b, 广播的 A[i][k])", size=9.2,
           fill=INK)
    s.text(305, 596, "前提：这 4 个 j 的 B、C 元素必须挨着——所以“内层沿 j”不是风格偏好，",
           size=9.0, fill=GRAY)
    s.text(305, 614, "而是能不能用上这条指令的分界线。k 内层 = 4 次单独的“爬楼梯”load。",
           size=9.0, fill=GRAY)

    # ---------- 右：三档 unroll-j 与编译器的真实互动 ----------
    s.text(620, 468, "④ 别帮倒忙：手动展开可能把“好向量化”做成“差向量化”（实测）",
           size=12.5, fill=ORANGE, anchor="start", bold=True)
    s.rrect(622, 488, 500, 190, fill=CARD, stroke=ORANGE, sw=2.0)
    rows = [
        ("reorder（不展开）", "干净的 ld1r + 向量 fmul/fadd", "14.26 GFLOPS", GREEN),
        ("unroll-j U=2", "ld2/st2 交错存取（向量但绕路）", "10.74 GFLOPS", BLUE),
        ("unroll-j U=4", "ld4/st4 反交错，几乎白干", "5.48 GFLOPS", ORANGE),
        ("unroll-j U=8", "大头退回标量", "3.92 GFLOPS", RED),
    ]
    for i, (nm, why, perf, col) in enumerate(rows):
        y = 514 + i * 38
        s.text(640, y, nm, size=9.6, fill=INK, anchor="start", bold=True)
        s.text(640, y + 15, why, size=8.4, fill=GRAY, anchor="start")
        s.rrect(880, y - 12, 218, 24, fill=CARD, stroke=col, sw=1.6, r=6)
        s.text(989, y + 4, perf, size=9.4, fill=col, bold=True)
    s.text(872, 668, "结论：先保证“内层连续”，再让编译器向量化；要手动展开，用实验挑 U",
           size=9.2, fill=ORANGE, bold=True)

    # ---------- 底部结论 ----------
    s.rrect(56, 706, 1066, 92, fill=SOFT, stroke=LINE, sw=2.0)
    s.text(589, 734, "判定口诀：看最内层循环变量每 +1，谁在内存里挪一个固定小步（=元素大小），谁在跨行跳；",
           size=10.2, fill=INK, bold=True)
    s.text(589, 756, "三个矩阵（A、B、C）在“不动 / 沿走 / 跨走”里的角色，决定编译器给不给 128-bit 指令。",
           size=10.2, fill=INK)
    s.text(589, 780, "本机证据链：vec-report.txt 的两行原话 + vec-instr-count.txt 的 NEON 计数 + bench-vector.txt 的 4.5×。",
           size=9.2, fill=GRAY)
    s.save("03-contiguity.svg")


# =====================================================================
# 图 4：实测结果（性能 + 代码体积 + 验收徽章）
# =====================================================================
def img_results():
    s = SVG(1180, 850)
    header(s, "实测结果：4.5× 来自“内层连续”，不是来自展开",
           "n=384³，tile 64³，预热 5 次 + 15 次取中位数；aarch64 GCC 9.4.0，-ffp-contract=off，全部版本与参考逐位相等")

    # ---------- 左：-O3 向量化版 GFLOPS ----------
    s.text(70, 106, "① -O3（自动向量化）：8 个内核的 GFLOPS", size=12.5, fill=INK,
           anchor="start", bold=True)
    s.rrect(56, 124, 560, 400, fill=CARD, stroke=LINE, sw=2.2)
    data = [
        ("baseline i/j/k", 3.19, RED),
        ("reorder i/k/j", 14.26, GREEN),
        ("unroll-k U=2", 3.43, RED),
        ("unroll-k U=4", 3.59, RED),
        ("unroll-k U=8", 3.22, RED),
        ("unroll-j U=2", 10.74, BLUE),
        ("unroll-j U=4", 5.48, ORANGE),
        ("unroll-j U=8", 3.92, ORANGE),
    ]
    maxv = 15.5
    for i, (nm, v, col) in enumerate(data):
        y = 150 + i * 42
        bw = 400 * v / maxv
        s.text(150, y + 14, nm, size=9.0, fill=INK, anchor="start")
        s.rrect(252, y, bw, 24, fill=(GREEN_BG if col == GREEN else
                                      (BLUE_BG if col == BLUE else
                                       (ORANGE_BG if col == ORANGE else RED_BG))),
                stroke=col, sw=1.8, r=6)
        s.text(252 + bw + 8, y + 16, f"{v:.2f}", size=9.2, fill=col, bold=True)
    s.text(336, 505, "红 = 机器码 0 条 NEON 指令（没向量化）", size=8.8, fill=RED)
    s.text(336, 480, "绿 = 干净向量化（4.5×）；蓝/橙 = 向量化但绕路（见 vec-instr-count.txt）",
           size=8.8, fill=GRAY)
    s.star(452, 176, 13, GREEN)
    s.text(452, 158, "唯一 4× 以上", size=8.4, fill=GREEN)

    # ---------- 右上：标量版 ----------
    s.text(660, 106, "② -O2 -fno-tree-vectorize（纯标量）：展开的真实收益",
           size=12.5, fill=INK, anchor="start", bold=True)
    s.rrect(648, 124, 474, 190, fill=CARD, stroke=LINE, sw=2.2)
    sdata = [
        ("baseline", 3.21, GRAY),
        ("reorder", 2.88, RED),
        ("unroll-k U=2", 3.26, BLUE),
        ("unroll-j U=2", 3.78, BLUE),
        ("unroll-j U=8", 3.90, GREEN),
    ]
    smax = 4.2
    for i, (nm, v, col) in enumerate(sdata):
        y = 152 + i * 30
        bw = 240 * v / smax
        s.text(664, y + 13, nm, size=8.6, fill=INK, anchor="start")
        s.rrect(762, y, bw, 18, fill=SOFT, stroke=col, sw=1.6, r=5)
        s.text(762 + bw + 6, y + 13, f"{v:.2f}", size=8.8, fill=col, bold=True)
    s.text(885, 300, "没有向量化时：unroll 只带来 +1.5%～+21%；", size=8.8,
           fill=GRAY, anchor="start")
    s.text(885, 288, "控制开销本来就不是大头——这就是 Unroll 的收益上限", size=8.8,
           fill=GRAY, anchor="start")

    # ---------- 右中：代码体积 ----------
    s.text(660, 350, "③ 代价：unroll-k 的机器码指令数（objdump 实测）",
           size=12.5, fill=INK, anchor="start", bold=True)
    s.rrect(648, 368, 474, 156, fill=CARD, stroke=LINE, sw=2.2)
    cdata = [("baseline", 116), ("U=2", 194), ("U=4", 260), ("U=8", 372)]
    for i, (nm, v) in enumerate(cdata):
        x = 676 + i * 112
        bh = 70 * v / 372
        s.rrect(x, 466 - bh, 44, max(bh, 6), fill=RED_BG, stroke=RED, sw=1.8, r=4)
        s.text(x + 22, 480, str(v), size=9.2, fill=RED, bold=True)
        s.text(x + 22, 494, nm, size=8.0, fill=GRAY)
    s.text(885, 512, "IR 同款趋势：1167 → 2231 → 3069 B（unrollgen.py）",
           size=8.8, fill=GRAY, anchor="start")

    # ---------- 底部：验收徽章 ----------
    s.text(60, 560, "④ 防回归资产：今天留下的可复现证据（全部真实运行）", size=12.5,
           fill=INK, anchor="start", bold=True)
    badges = [
        (56, 582, 250, 96, GREEN_BG, GREEN, "主例 4/4 逐位相等",
         ["baseline / reorder /", "unroll-k / unroll-j", "k 升序 → 与参考相同"]),
        (318, 582, 250, 96, GREEN_BG, GREEN, "suite 20/20 × 2 轮",
         ["U=4 与 U=5 各 10 shape", "no-tail/overlap 同时", "标记“碰巧正确”的整除例"]),
        (580, 582, 250, 96, BLUE_BG, BLUE, "IR 3/3 PARSE OK",
         ["before / unroll_k2 /", "unroll_k4_divisible", "上游 affine 对照另计"]),
        (842, 582, 280, 96, BLUE_BG, BLUE, "bench 8/8 逐位相等",
         ["-ffp-contract=off", "无 fma 重结合", "向量版也不改语义"]),
    ]
    for x, y, w, h, f, st, t, lines in badges:
        s.rrect(x, y, w, h, fill=f, stroke=st, sw=2.2)
        s.text(x + w / 2, y + 24, t, size=11.0, bold=True, fill=st)
        for i, ln in enumerate(lines):
            s.text(x + w / 2, y + 46 + i * 15, ln, size=8.4, fill=GRAY)

    # ---------- 底部：读表结论 ----------
    s.rrect(56, 706, 1066, 108, fill=SOFT, stroke=LINE, sw=2.0)
    s.text(589, 734, "读表三问：① 为什么 -O3 的 baseline 和 unroll-k 一样慢？——0 条 NEON 指令，向量化根本没发生；",
           size=10.2, fill=INK, bold=True)
    s.text(589, 756, "② 为什么 reorder 最快却没展开？——内层连续给了编译器干净的 128-bit 循环，手动展开反而挡路（ld2/ld4 绕路）；",
           size=10.2, fill=INK, bold=True)
    s.text(589, 778, "③ U 怎么选？——收益（+1.5%）、代价（372 条指令）、风险（U=8 反降）都要进实验表：这正是第 97 天的工作。",
           size=10.2, fill=INK, bold=True)
    s.text(589, 800, "环境：aarch64 Linux，32 核，GCC 9.4.0；统计口径：15 次中位数，预热 5 次；数据文件 outputs/bench-*.txt。",
           size=9.0, fill=GRAY)
    s.save("04-results.svg")


if __name__ == "__main__":
    img_overview()
    img_unroll_mechanism()
    img_contiguity()
    img_results()
