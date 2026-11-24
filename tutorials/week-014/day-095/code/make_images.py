#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第 95 天教程插图生成器：手绘 sketch 风（Excalidraw-like）SVG。

用法：  python3 code/make_images.py
输出：  images/01-overview.svg        第 14 周链路定位（技术信息图）
        images/02-remainder-tiles.svg 5x7x3 主例的剩余 Tile 与 min 机制（技术信息图）
        images/03-strategies.svg      三种尾部策略对照（真实测量数字）（技术信息图）
        images/04-errors.svg          三个错误复现实录（技术信息图）

图中所有数字（192/87/21/8、242、30/30、56.25……）均来自本目录
outputs/ 下的真实运行记录，无虚构。
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
             (x + w, y + h - r), (x + w - r, y + h), (x + r, y + h),
             (x, y + h - r), (x, y + r), (x + r, y)]
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
# 图 1：第 95 天在“循环生成 → Tiling → 尾部 → 展开”链路中的位置
# =====================================================================
def img_overview():
    s = SVG(1180, 780)
    header(s, "第 95 天：处理非整除尾部——tiling 从“只敢整除”到“什么 shape 都算得对”",
           "主例 C = A(5x3)·B(3x7)，tile 2x4x2：12 个 tile 里只有 2 个是完整 tile，其余 10 个都咬着边界")

    # ---------- ① 第 14 周时间线 ----------
    s.text(60, 108, "① 第 14 周：从生成循环到多配置实验，今天补的是 tiling 的“最后一块正确性”",
           size=13, fill=INK, anchor="start", bold=True)
    days = [
        (56, 130, 118, 86, CARD, LINE, "D88–89", "三重循环 + 读写", ["induction var", "load/store/累加"]),
        (190, 130, 118, 86, CARD, LINE, "D90", "非方形/边界 shape", ["1xN、Mx1、小 K", "8 组 shape 测试"]),
        (324, 130, 118, 86, CARD, LINE, "D92–93", "循环顺序 + 参数化", ["i/j/k 排列", "LoopOptions"]),
        (458, 130, 118, 86, SOFT, LINE, "D94", "基础 Tiling", ["先整除场景", "Tiled IR + 测试"]),
        (592, 130, 132, 86, ORANGE_BG, ORANGE, "D95 今天", "非整除尾部", ["剩余 Tile/边界", "条件/掩码思想"]),
        (740, 130, 118, 86, CARD, LINE, "D96", "展开与向量化", ["Unroll 收益", "连续访问"]),
        (874, 130, 118, 86, CARD, LINE, "D97", "多配置实验", ["控制变量", "性能表"]),
        (1010, 130, 108, 86, SOFT, LINE, "D98", "周复盘", ["正确性报告", "一张复盘图"]),
    ]
    for x, y, w, h, f, st, d, t, lines in days:
        s.rrect(x, y, w, h, fill=f, stroke=st, sw=2.2)
        s.text(x + w / 2, y + 20, d, size=8.8, fill=GRAY)
        s.text(x + w / 2, y + 40, t, size=10.2, bold=True,
               fill=ORANGE if f == ORANGE_BG else INK)
        for i, ln in enumerate(lines):
            s.text(x + w / 2, y + 58 + i * 14, ln, size=7.6, fill=GRAY)
    s.arrow(174, 173, 190, 173, sw=1.4)
    s.arrow(308, 173, 324, 173, sw=1.4)
    s.arrow(442, 173, 458, 173, sw=1.4)
    s.arrow(576, 173, 592, 173, sw=1.4)
    s.arrow(724, 173, 740, 173, sw=1.4)
    s.arrow(858, 173, 874, 173, sw=1.4)
    s.arrow(992, 173, 1010, 173, sw=1.4)

    # ---------- ② tiling 主线流程 ----------
    s.text(60, 268, "② 今天动的格子：tile 网格画完之后、点循环跑之前——“这个 tile 实际算多宽”",
           size=13, fill=INK, anchor="start", bold=True)
    pipe = [
        (56, 290, 128, 96, CARD, LINE, "输入 shape", ["M=5 N=7 K=3", "来自 D88 循环骨架"]),
        (204, 290, 128, 96, CARD, LINE, "LoopOptions", ["tile 2x4x2", "来自 D93 参数化"]),
        (352, 290, 150, 96, SOFT, LINE, "ceil-div tile 网格", ["3x2x2 = 12 个 tile", "D94 只保证整除"]),
        (522, 290, 186, 96, ORANGE_BG, ORANGE, "每 tile 实际边界（今天）", ["min 钳制 / 掩码", "剩余 tile 自动变短"]),
        (728, 290, 146, 96, CARD, LINE, "点循环 + 读写", ["105 步全部有效", "0 次越界/重复"]),
        (890, 290, 138, 96, CARD, LINE, "结果 C 5x7", ["逐位等于参考", "suite 30/30"]),
    ]
    for x, y, w, h, f, st, t, lines in pipe:
        s.rrect(x, y, w, h, fill=f, stroke=st, sw=2.2)
        s.text(x + w / 2, y + 24, t, size=10.4, bold=True,
               fill=ORANGE if f == ORANGE_BG else INK)
        for i, ln in enumerate(lines):
            s.text(x + w / 2, y + 46 + i * 15, ln, size=8.6, fill=GRAY)
    for a, b in [(184, 204), (332, 352), (502, 522), (708, 728), (874, 890)]:
        s.arrow(a, 338, b, 338, sw=1.6)

    s.text(522, 412, "橙色格要回答的问题：i0=4 的 tile 只有 1 行、j0=4 的 tile 只有 3 列、k0=2 的 tile 只算 1 个 k——",
           size=9.8, fill=ORANGE, anchor="start")
    s.text(522, 428, "点循环上界从哪来？忘了它，越界和重复计算立刻上门（第 6 节三种复现）。",
           size=9.8, fill=ORANGE, anchor="start")

    # ---------- ③ 三种策略速览 + 产出 ----------
    s.text(60, 486, "③ 三种策略一句话 + 今天的真实产出", size=13, fill=INK,
           anchor="start", bold=True)
    strat = [
        (56, 508, 332, 118, CARD, LINE, "guard 每元素判断", "if (i<M && j<N && k<K)",
         ["掩码思想的朴素形态", "主例真实数字：192 次判断 / 87 次空转", "优点：哪里都能用；代价：每个点都付"]),
        (404, 508, 332, 118, GREEN_BG, GREEN, "minclamp 边界钳制", "上界 = min(起点+Tile, 维度)",
         ["MLIR/linalg tiling 同款思路", "主例真实数字：21 次 min / 0 空转", "每 tile 只付一次，摊到 105 个点上"]),
        (752, 508, 332, 118, CARD, LINE, "epilogue 分离尾部", "主循环整 tile + 尾部单独算",
         ["2^3 = 8 份循环体（代价是代码膨胀）", "主例真实数字：8 区域全部非空 / 0 判断", "D96 的展开将放大这个代价"]),
    ]
    for x, y, w, h, f, st, t, code, lines in strat:
        s.rrect(x, y, w, h, fill=f, stroke=st, sw=2.2)
        s.text(x + w / 2, y + 22, t, size=11.4, bold=True,
               fill=GREEN if f == GREEN_BG else INK)
        s.text(x + w / 2, y + 44, code, size=9.2, fill=GRAY)
        for i, ln in enumerate(lines):
            s.text(x + w / 2, y + 66 + i * 15, ln, size=8.6, fill=INK if i == 1 else GRAY)

    s.rrect(56, 664, 1028, 76, fill=SOFT, stroke=LINE, sw=2.0)
    s.text(570, 688, "今日产出（全部真实运行）：边界 IR x4（mlir-opt 18.1.8 解析通过）＋ 策略对照表 ＋ 30/30 shape 套件 ＋ 3 个错误复现",
           size=10.6, fill=INK, bold=True)
    s.text(570, 710, "两句话记住今天：① 尾部是规则不是事故——ceil-div 网格必有剩余 tile；② 钳制边界，别钳制索引。",
           size=9.6, fill=GRAY)
    s.save("01-overview.svg")


# =====================================================================
# 图 2：5x7x3 的剩余 Tile 与 min 钳制机制
# =====================================================================
def img_remainder():
    s = SVG(1180, 820)
    header(s, "主例解剖：5x7 输出的 12 个 tile 里，10 个咬着边界",
           "行 tile 高度 2/2/1，列 tile 宽度 4/3，K 方向 2/1——三个维度各有一个剩余 Tile；点循环上界全部由 min 修正")

    # ---------- 左：C 的 tile 网格 ----------
    s.text(70, 104, "① 输出 C（5 行 x 7 列）按 tile 2x4 切分", size=12.5,
           fill=INK, anchor="start", bold=True)
    gx, gy, cw, ch = 90, 152, 58, 50
    rowh = [2, 2, 1]          # i-tile 高度
    colw = [4, 3]             # j-tile 宽度
    rstarts = [0, 2, 4]
    cstarts = [0, 4]
    # 单元格
    for r in range(5):
        for c in range(7):
            ir = 0 if r < 2 else (1 if r < 4 else 2)
            jc = 0 if c < 4 else 1
            full = (rowh[ir] == 2 and colw[jc] == 4 and ir != 2)
            in_m_tail = (ir == 2)
            in_n_tail = (jc == 1)
            if full and not in_m_tail and not in_n_tail:
                f = GREEN_BG
            elif in_m_tail and in_n_tail:
                f = RED_BG
            elif in_m_tail or in_n_tail:
                f = ORANGE_BG
            else:
                f = GREEN_BG
            x = gx + c * cw
            y = gy + r * ch
            rng = random.Random(500 + r * 7 + c)
            s.parts.append(
                f'<rect x="{x + rng.uniform(-1, 1):.1f}" y="{y + rng.uniform(-1, 1):.1f}" '
                f'width="{cw - 4}" height="{ch - 4}" fill="{f}" stroke="{LINE}" '
                f'stroke-width="1.1"/>')
    # tile 边框（粗手绘）
    for ti, (rs, rh) in enumerate(zip(rstarts, rowh)):
        for tj, (cs, cwd) in enumerate(zip(cstarts, colw)):
            x = gx + cs * cw
            y = gy + rs * ch
            w = cwd * cw
            h = rh * ch
            stroke = GREEN if (rh == 2 and cwd == 4) else (RED if (rh == 1 and cwd == 3) else ORANGE)
            sw = 3.0 if stroke != GREEN else 2.4
            s.rrect(x + 1, y + 1, w - 2, h - 2, fill="none", stroke=stroke, sw=sw, r=6)
    # 行分组标签
    for rs, rh, lab in [(0, 2, "i0=0  高 2（完整）"), (2, 2, "i0=2  高 2（完整）"),
                        (4, 1, "i0=4  高 1 剩余")]:
        s.text(gx - 8, gy + rs * ch + rh * ch / 2 + 4, lab, size=8.6, fill=GRAY,
               anchor="end")
    for cs, cwd, lab in [(0, 4, "j0=0 宽 4（完整）"), (4, 3, "j0=4 宽 3 剩余")]:
        s.text(gx + cs * cw + cwd * cw / 2, gy - 14, lab, size=8.6, fill=GRAY)
    # tile 计数标注
    s.text(gx + 7 * cw / 2, gy + 5 * ch + 26,
           "6 个输出 tile = 2 完整(绿) + 2 咬 N 尾(橙) + 1 咬 M 尾(橙) + 1 双咬 M+N 尾(红)",
           size=9, fill=INK)
    s.text(gx + 7 * cw / 2, gy + 5 * ch + 44,
           "三个维度算上 K：3x2x2 = 12 个 tile，其中 10 个咬着至少一条边界",
           size=9, fill=GRAY)

    # ---------- 中：K 方向 ----------
    s.text(640, 104, "② K 方向也有剩余：K=3，TK=2", size=12.5, fill=INK,
           anchor="start", bold=True)
    kx, ky = 660, 140
    s.rrect(kx, ky, 172, 56, fill=GREEN_BG, stroke=GREEN, sw=2.6)
    s.text(kx + 86, ky + 26, "k0=0  长 2（完整）", size=9.2, fill=INK)
    s.rrect(kx + 172, ky, 86, 56, fill=RED_BG, stroke=RED, sw=2.6)
    s.text(kx + 215, ky + 26, "k0=2 长 1", size=9.2, fill=INK)
    s.text(kx + 215, ky + 74, "剩余", size=9.0, fill=RED)
    s.text(kx, ky + 96, "完整 tile：k ∈ [0, min(0+2, 3)) = [0, 2)", size=9.0,
           fill=GRAY, anchor="start")
    s.text(kx, ky + 114, "剩余 tile：k ∈ [2, min(2+2, 3)) = [2, 3) ← 上界被 K 钳回",
           size=9.0, fill=INK, anchor="start")
    s.text(kx, ky + 140, "A 是 5x3：i 尾 1 行 × k 尾 1 列", size=9.2, fill=GRAY,
           anchor="start")
    s.text(kx, ky + 158, "B 是 3x7：k 尾 1 行 × j 尾 3 列", size=9.2, fill=GRAY,
           anchor="start")
    s.text(kx, ky + 176, "→ A、B、C 三个矩阵都会被咬到", size=9.2, fill=RED,
           anchor="start")

    # ---------- 右：min 公式卡 ----------
    s.text(940, 104, "③ 修正规则：一条 min 顶一个维", size=12.5, fill=INK,
           anchor="start", bold=True)
    s.rrect(940, 122, 208, 200, fill=CARD, stroke=BLUE, sw=2.4)
    s.text(1044, 148, "点循环上界", size=10.6, fill=BLUE, bold=True)
    for i, ln in enumerate([
        "ihi = min(i0 + TM, M)",
        "jhi = min(j0 + TN, N)",
        "khi = min(k0 + TK, K)",
    ]):
        s.text(1044, 174 + i * 26, ln, size=10.2, fill=INK)
    s.text(1044, 258, "i0=4：min(4+2,5)=5", size=9.0, fill=GRAY)
    s.text(1044, 274, "→ 行循环只跑 4..5，1 行", size=9.0, fill=GRAY)
    s.text(1044, 294, "静态 3 条 min，动态 21 次", size=9.0, fill=BLUE)
    s.text(1044, 312, "(3 + 6 + 12，按嵌套层数摊)", size=8.4, fill=GRAY)

    # ---------- 下：点循环对照 ----------
    s.text(70, 490, "④ 同一个 tile，三种上界写法的点循环（这就是三策略的分岔口）",
           size=12.5, fill=INK, anchor="start", bold=True)
    cards = [
        (70, 512, 330, 160, CARD, LINE, "guard：循环照旧满宽，体内挡一道",
         ["for i in [i0, i0+2)   ← 满宽 2 行", "  for j in [j0, j0+4)",
          "    if (i<5 && j<7 && k<3)",
          "    每个点积步都判一次",
          "实测：192 次判断，87 次空转"]),
        (430, 512, 330, 160, GREEN_BG, GREEN, "minclamp：先把上界修短，体内零判断",
         ["ihi = min(i0+2, 5)",
          "for i in [i0, ihi)   ← 真实宽", "  for j in [j0, min(j0+4,7))",
          "    体内直接算，无 if",
          "实测：21 次 min，0 次空转"]),
        (790, 512, 330, 160, CARD, LINE, "epilogue：完整 tile 一个 nest，尾部单独写",
         ["主 nest：只跑 i0∈{0,2} 的完整 tile", "尾部 nest：i0=4 起步，边界写死",
          "2x2x2 = 8 份循环体",
          "实测：8 个区域全部非空", "代码翻倍，运行时零判断"]),
    ]
    for x, y, w, h, f, st, t, lines in cards:
        s.rrect(x, y, w, h, fill=f, stroke=st, sw=2.2)
        s.text(x + w / 2, y + 24, t, size=10.6, bold=True,
               fill=GREEN if f == GREEN_BG else INK)
        for i, ln in enumerate(lines):
            s.text(x + w / 2, y + 50 + i * 19, ln, size=8.8,
                   fill=INK if i == len(lines) - 1 else GRAY)

    # 底部结论
    s.rrect(70, 712, 1050, 66, fill=SOFT, stroke=LINE, sw=2.0)
    s.text(595, 736, "为什么钳制“边界”而不是“索引”：min 修的是循环要跑多远（一次/tile），",
           size=10.2, fill=INK, bold=True)
    s.text(595, 756, "索引钳制 min(i, M-1) 是在每次访存时拉人一把——正确性看运气、重复计算跑不掉（第 6 节错误 2 实测 13 次重复写）。",
           size=9.6, fill=GRAY)
    s.save("02-remainder-tiles.svg")


# =====================================================================
# 图 3：三种策略的真实测量对照
# =====================================================================
def img_strategies():
    s = SVG(1180, 820)
    header(s, "三策略实测：非整除 5x7x3 vs 整除 6x8x4（g++ -O2，aarch64 Linux）",
           "所有数字来自 outputs/strategy-table*.txt 的真实运行——正确性按“与参考逐位相等”判")

    # ---------- 上：非整除主例 ----------
    s.text(70, 104, "① 主例 M=5 N=7 K=3，tile 2x4x2（12 个 tile，有效 105 步）",
           size=12.5, fill=INK, anchor="start", bold=True)
    cols = [
        (70, 126, 330, 260, CARD, LINE, "guard(每元素if)", "192 次判断 / 87 次空转",
         [("inner_iters", "192"), ("guard_checks", "192"),
          ("idle（白跑）", "87"), ("boundary_ops", "0"),
          ("oob/dup", "0 / 0"), ("正确性", "逐位相等")]),
        (430, 126, 330, 260, GREEN_BG, GREEN, "minclamp(min钳制)", "21 次 min / 0 次空转",
         [("inner_iters", "105"), ("guard_checks", "0"),
          ("idle（白跑）", "0"), ("boundary_ops", "21"),
          ("oob/dup", "0 / 0"), ("正确性", "逐位相等")]),
        (790, 126, 330, 260, CARD, LINE, "epilogue(分离尾部)", "8 份循环体 / 8 区域判空",
         [("inner_iters", "105"), ("guard_checks", "0"),
          ("idle（白跑）", "0"), ("boundary_ops", "8"),
          ("静态 body", "8 份（2^3）"), ("非空区域", "8/8")]),
    ]
    for x, y, w, h, f, st, t, sub, rows in cols:
        s.rrect(x, y, w, h, fill=f, stroke=st, sw=2.4)
        s.text(x + w / 2, y + 26, t, size=11.6, bold=True,
               fill=GREEN if f == GREEN_BG else INK)
        s.text(x + w / 2, y + 48, sub, size=9.8, fill=GRAY)
        s.line(x + 16, y + 62, x + w - 16, y + 62, sw=1.2, amp=1)
        for i, (k, v) in enumerate(rows):
            s.text(x + 28, y + 88 + i * 26, k, size=9.4, fill=GRAY, anchor="start")
            s.text(x + w - 28, y + 88 + i * 26, v, size=10.0, fill=INK,
                   anchor="end", bold=True)
    s.text(70, 416, "读法：guard 的 192 次判断里 87 次落空——45% 是白判；minclamp 用 21 次 min（摊到每个点 0.2 次）",
           size=9.8, fill=GRAY, anchor="start")
    s.text(70, 434, "买到同样的正确性；epilogue 连判断都不付，代价搬进了代码体积（8 份循环体）。",
           size=9.8, fill=GRAY, anchor="start")

    # ---------- 下：整除对照 ----------
    s.text(70, 480, "② 对照：完全整除 6x8x4，同 tile 2x4x2（回归 Day 94 的世界）",
           size=12.5, fill=INK, anchor="start", bold=True)
    rows = [
        ("guard", "192", "192 / 0", "0", "0", "尾部消失：87 次空转归零，但 192 次判断照付"),
        ("minclamp", "192", "0 / 0", "21", "0", "min 照样执行 21 次——只是每次都“不咬”，白付一次比较"),
        ("epilogue", "192", "0 / 0", "8", "1", "8 个区域只剩 1 个非空（主区域），7 份 body 白编译"),
    ]
    hx = [70, 250, 350, 470, 560, 660]
    s.rrect(70, 500, 1050, 96, fill=CARD, stroke=LINE, sw=2.0)
    s.text(hx[0] + 20, 522, "strategy", size=9.6, fill=GRAY, anchor="start", bold=True)
    s.text(hx[1], 522, "inner", size=9.6, fill=GRAY, bold=True)
    s.text(hx[2], 522, "判断/空转", size=9.6, fill=GRAY, bold=True)
    s.text(hx[3] - 20, 522, "min·区域", size=9.6, fill=GRAY, anchor="end", bold=True)
    s.text(hx[4], 522, "非空区域", size=9.6, fill=GRAY, bold=True)
    s.text(hx[5] - 20, 522, "尾部消失时发生什么", size=9.6, fill=GRAY, anchor="end", bold=True)
    for i, (a, b, c, d, e, f) in enumerate(rows):
        y = 548 + i * 26
        s.text(hx[0] + 20, y, a, size=9.8, fill=INK, anchor="start", bold=True)
        s.text(hx[1], y, b, size=9.8, fill=INK)
        s.text(hx[2], y, c, size=9.8, fill=INK)
        s.text(hx[3] - 20, y, d, size=9.8, fill=INK, anchor="end")
        s.text(hx[4], y, e, size=9.8, fill=INK)
        s.text(hx[5] - 20, y, f, size=8.8, fill=GRAY, anchor="end")
    s.text(70, 630, "对照的启示：尾部的三种代价结构完全不同——guard 付“每元素”、minclamp 付“每 tile”、epilogue 付“每份代码”；",
           size=9.8, fill=GRAY, anchor="start")
    s.text(70, 648, "shape 整除时三者一个都退不了款。这就是 D97 要按 shape 分档测配置的原因。",
           size=9.8, fill=GRAY, anchor="start")

    # ---------- 右下：suite + IR 徽章 ----------
    s.rrect(70, 678, 500, 100, fill=GREEN_BG, stroke=GREEN, sw=2.2)
    s.text(320, 704, "30/30 shape 套件全过", size=11.6, fill=GREEN, bold=True)
    s.text(320, 726, "含 M=1 / N=1 / K=1 / 余 1 / tile>dim /", size=9.0, fill=GRAY)
    s.text(320, 744, "64 整除回归 / 瘦长 N / 瘦长 M（三策略逐位相等）", size=9.0, fill=GRAY)

    s.rrect(600, 678, 520, 100, fill=BLUE_BG, stroke=BLUE, sw=2.2)
    s.text(860, 704, "边界 IR x4 全部解析通过（mlir-opt 18.1.8）", size=11.2, fill=BLUE, bold=True)
    s.text(860, 726, "min_bounds / mask / danger / divisible", size=9.0, fill=GRAY)
    s.text(860, 744, "danger 也能解析——IR 合法 ≠ 访存安全", size=9.0, fill=RED)
    s.save("03-strategies.svg")


# =====================================================================
# 图 4：三个错误复现实录
# =====================================================================
def img_errors():
    s = SVG(1180, 860)
    header(s, "三个真实复现的坑：忘保护、钳索引、差一位",
           "全部在本机用 ./tiled_matmul 5 7 3 2 4 2 --mode xxx 重演，数字来自 outputs/err-*.txt")

    # 错误 1
    s.rrect(60, 100, 1060, 200, fill=RED_BG, stroke=RED, sw=2.4)
    s.text(90, 128, "错误 1：danger——忘加 min 也忘加 if", size=12.5,
           fill=RED, anchor="start", bold=True)
    s.text(90, 154, "现象：correct=NO，oob_touches=242 次，max_abs_err=56.25（pad 垃圾值 7.5 直接进了乘加）",
           size=9.8, fill=INK, anchor="start")
    s.text(90, 172, "242 的分解：A 读越界 72（i 尾 32 + k 尾 40）+ B 读越界 66（k 尾 48 + j 尾 18）+ C 读写越界 52+52",
           size=9.2, fill=GRAY, anchor="start")
    s.text(90, 196, "原因：tile 网格是 ceil-div 画的，点循环按整 tile 宽度跑，i=5、j=7、k=3 都在真实矩阵之外。",
           size=9.6, fill=INK, anchor="start")
    s.text(90, 216, "定位：不用猜——插桩的 ldA/ldB/ldC/stC 包装把每次越界都记了数；没有插桩时它会表现为段错误或“结果玄学差”。",
           size=9.6, fill=INK, anchor="start")
    s.text(90, 240, "修复：min 钳制（21 次）或掩码（192 次）任选其一；matmul_danger.mlir 本身能被 mlir-opt 解析——",
           size=9.6, fill=INK, anchor="start")
    s.text(90, 258, "语法合法性救不了访存安全，这条 IR 是留给 Day 97 正确性测试的反面教材。", size=9.6, fill=INK, anchor="start")

    # 错误 2
    s.rrect(60, 330, 1060, 200, fill=ORANGE_BG, stroke=ORANGE, sw=2.4)
    s.text(90, 358, "错误 2：clamp-store——钳制“索引”而不是“边界”", size=12.5,
           fill=ORANGE, anchor="start", bold=True)
    s.text(90, 384, "现象：correct=yes（逐位相等！）但 inner=144（多算 39 步）、48 次赋值 store、13 次重复写、单元素最多被写 4 次",
           size=9.8, fill=INK, anchor="start")
    s.text(90, 402, "原因：min(i, M-1) 让 i=5 的循环步“代替”i=4 又算了一遍——数值碰巧还是对的（两次写的是同一个正确值）。",
           size=9.6, fill=INK, anchor="start")
    s.text(90, 422, "定位：看 dup_write=13 和 max_assign_per_elem=4；单看结果你永远不会发现，这正是它危险的地方。",
           size=9.6, fill=INK, anchor="start")
    s.text(90, 446, "修复：把 min 从“每次访存”挪到“每 tile 一次”的循环上界上（策略 2）；边界一次定好，体内不再拉人。",
           size=9.6, fill=INK, anchor="start")
    s.text(90, 466, "边界：串行里它“只是浪费”；并行/多线程 tile 同时落到同一元素时，它是数据竞争 + 未定义行为。", size=9.6, fill=INK, anchor="start")

    # 错误 3
    s.rrect(60, 560, 1060, 176, fill=BLUE_BG, stroke=BLUE, sw=2.4)
    s.text(90, 588, "错误 3：off-by-one——min 上界写成了 M-1", size=12.5,
           fill=BLUE, anchor="start", bold=True)
    s.text(90, 614, "现象：correct=NO，max_abs_err=2.25，oob_touches=0（一次都没越界，安静地错）",
           size=9.8, fill=INK, anchor="start")
    s.text(90, 634, "原因：min(i0+TM, M-1) 让 i0=4 的 tile 变成 [4, 4)——空循环；第 5 行整行没算（N、K 同理：列 7、k=2 消失）。",
           size=9.6, fill=INK, anchor="start")
    s.text(90, 656, "定位：inner_iters=48（4x6x2）而合法应为 105——步数骤降就是“有 tile 被算成了空”的信号。",
           size=9.6, fill=INK, anchor="start")
    s.text(90, 678, "修复：半开区间 [lo, hi) 的 hi 是“第一个不要的位置”，所以是维度 M 本身；min 的第二个参数永远写“开边界”。",
           size=9.6, fill=INK, anchor="start")

    # 底部：三个教训
    s.rrect(60, 770, 1060, 62, fill=SOFT, stroke=LINE, sw=2.0)
    s.text(590, 792, "三个坑各踩掉一种“想当然”：尾部必须处理（不是可选）、钳制边界不是索引（不是位置）、半开区间的上界是 M（不是 M-1）。",
           size=10.2, fill=INK, bold=True)
    s.text(590, 812, "判据记三条：oob_touches 必须 0；inner_iters 应等于 M*N*K；任何元素被赋值式 store 不得超过 1 次。",
           size=9.6, fill=GRAY)
    s.save("04-errors.svg")


if __name__ == "__main__":
    img_overview()
    img_remainder()
    img_strategies()
    img_errors()
