#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第 49 天教程插图生成器：手绘 sketch 风（Excalidraw-like）SVG。

用法：  python3 code/make_images.py
输出：  images/01-overview.svg    三种机制的职责分工（技术信息图）
        images/02-combo-chain.svg combo.mlir 的三步接力（技术信息图）
        images/03-shape-unlock.svg 类型护栏关卡（技术信息图）
        images/04-worklist.svg    贪婪驱动工作清单循环（技术信息图）

图中所有数字（op 计数、命令行、输出形态）都来自本目录下真实运行
记录（outputs/ 与教程第 5 节），无虚构。
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
            f'stroke-width="{sw}" stroke-linecap="round" '
            f'stroke-linejoin="round"/>')

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
# 图 1：三种机制的职责分工（全局信息图）
# =====================================================================
def img_overview():
    s = SVG(1180, 880)
    header(s, "第 49 天（第 7 周复盘）：Shape 推导、Fold、RewritePattern 的分工与接力",
           "上：三个机制挂在流水线的哪一格｜中：三张职责对照卡｜下：今天的两个组合实验（全部真实运行）")

    # ---------- ① 流水线条 ----------
    s.text(60, 100, "① 三个机制都住在 mini-opt 的同一条流水线上，但身份完全不同", size=13,
           fill=INK, anchor="start", bold=True)
    boxes = [
        (50, 120, 120, 110, CARD, LINE, ".mlir 文本",
         ["%one = mini.add", "  %c0, %c1", "%rr = mini.relu %m"]),
        (206, 120, 130, 110, CARD, LINE, "mini-opt",
         ["解析 → ODS 约束", "→ verify()", "注册表决定谁能进"]),
    ]
    for x, y, w, h, f, st, t, lines in boxes:
        s.rrect(x, y, w, h, fill=f, stroke=st)
        s.text(x + w / 2, y + 24, t, size=11.5, bold=True)
        for i, ln in enumerate(lines):
            s.text(x + w / 2, y + 46 + i * 15, ln, size=8.6, fill=GRAY)
    s.arrow(180, 175, 206, 175)

    # Pass 流水线大框
    s.rrect(366, 116, 500, 320, fill=SOFT, stroke=LINE, sw=2.2)
    s.text(616, 138, "Pass 流水线（按命令行顺序执行）", size=11.5, bold=True)

    s.rrect(390, 156, 150, 88, fill=BLUE_BG, stroke=BLUE, sw=2)
    s.text(465, 178, "-mini-infer-shape", size=10, fill=INK, bold=True)
    s.text(465, 196, "Day 44 的 Pass", size=8.4, fill=GRAY)
    s.text(465, 212, "只细化结果类型：", size=8.4, fill=INK)
    s.text(465, 226, "? → 数字", size=9.6, fill=BLUE, bold=True)

    s.rrect(566, 156, 170, 150, fill=ORANGE_BG, stroke=ORANGE, sw=2.6)
    s.text(651, 178, "-canonicalize", size=10.5, fill=ORANGE, bold=True)
    s.text(651, 196, "贪婪驱动：收集钩子", size=8.4, fill=INK)
    s.text(651, 211, "迭代到不动点", size=8.4, fill=INK)
    s.line(580, 222, 722, 222, stroke=ORANGE, sw=1.2, amp=0.8)
    s.text(651, 238, "fold 钩子（Day 47）", size=8.4, fill=INK)
    s.text(651, 252, "只做纯计算，值由驱动", size=8.2, fill=GRAY)
    s.text(651, 265, "物化成 mini.constant", size=8.2, fill=GRAY)
    s.text(651, 284, "Pattern（Day 45/46）", size=8.4, fill=INK)
    s.text(651, 298, "拿 PatternRewriter", size=8.2, fill=GRAY)
    s.text(651, 311, "亲手改图", size=8.2, fill=GRAY)

    s.rrect(762, 156, 90, 88, fill=CARD, stroke=LINE, sw=1.8)
    s.text(807, 190, "-cse 等", size=9, fill=INK)
    s.text(807, 208, "老朋友", size=8, fill=GRAY)
    s.arrow(540, 200, 566, 200, sw=1.6)
    s.arrow(736, 200, 762, 200, sw=1.6)

    s.arrow(866, 175, 900, 175, sw=1.6)
    s.rrect(900, 120, 190, 110, fill=CARD, stroke=LINE, sw=2.2)
    s.text(995, 146, "打印优化后 IR", size=11, bold=True)
    s.text(995, 168, "今天验收：", size=8.6, fill=GRAY)
    s.text(995, 186, "combo：8 ops → 3 ops", size=9, fill=GREEN, bold=True)
    s.text(995, 204, "combo_shape：9 → 6 vs 9 → 4", size=9, fill=RED, bold=True)

    s.arrow(651, 306, 651, 330, stroke=ORANGE, sw=1.4, ah=7)
    s.text(616, 352, "两种钩子都不是 Pass：它们挂在算子上，由 -canonicalize 这个现成驱动来收集——",
           size=9.5, fill=ORANGE, anchor="start")
    s.text(616, 368, "这解释了为什么第 47/49 天改 Pattern 与 fold 时 mini-opt 一行不动",
           size=9.5, fill=ORANGE, anchor="start")
    s.line(770, 330, 770, 430, stroke=ORANGE, sw=1.2, amp=1)

    # ---------- ② 三张职责卡 ----------
    s.text(60, 470, "② 职责对照卡：改不改 IR、动谁的类型、谁说了算", size=13,
           fill=INK, anchor="start", bold=True)
    cards = [
        (56, 492, 340, 286, BLUE, BLUE_BG, "Shape Inference（Pass）",
         ["-mini-infer-shape，Day 43 规则 + Day 44 Pass",
          "runOnOperation 里 walk 整个函数",
          "",
          "输入：操作数的 shape",
          "输出：结果类型里的 ? 变成数字",
          "",
          "改 IR 吗：只 setType 细化，",
          "绝不删除任何算子、绝不改已有数字",
          "",
          "口诀：补信息，不动图"],
         "细节化是信息增量，语义必然保持"),
        (424, 492, 340, 286, ORANGE, ORANGE_BG, "Fold（fold 钩子）",
         ["mini.add / mini.constant，Day 47",
          "驱动收集操作数常量后调用",
          "",
          "输入：FoldAdaptor 送来的属性",
          "输出：算好的属性（OpFoldResult）",
          "",
          "改 IR 吗：绝不！没有 Rewriter 可拿",
          "物化常量是驱动的活，走",
          "materializeConstant 钩子",
          "",
          "口诀：只算值，不碰图"],
         "还能顺手 uniquing 重复常量"),
        (792, 492, 340, 286, GREEN, GREEN_BG, "RewritePattern（Pattern）",
         ["getCanonicalizationPatterns，Day 45/46",
          "-canonicalize 收集后按收益调度",
          "",
          "输入：根算子 + 局部 def-use 形状",
          "输出：success / failure",
          "",
          "改 IR 吗：亲手改，必须经",
          "PatternRewriter（改边 + 擦除），",
          "绕过它驱动的工作清单会失效",
          "",
          "口诀：认形状，改结构"],
         "今天起三条 Pattern 都有标签，可单独开关"),
    ]
    for x, y, w, h, c, cbg, t, lines, foot in cards:
        s.rrect(x, y, w, h, fill=cbg, stroke=c, sw=2.4)
        s.text(x + w / 2, y + 28, t, size=12.5, fill=c, bold=True)
        s.line(x + 24, y + 44, x + w - 24, y + 44, stroke=c, sw=1.2, amp=0.8)
        for i, ln in enumerate(lines):
            if ln:
                s.text(x + w / 2, y + 68 + i * 19, ln, size=9.3,
                       fill=INK if not ln.startswith("口诀") else c,
                       bold=ln.startswith("口诀"))
        s.text(x + w / 2, y + h - 16, foot, size=8.6, fill=GRAY)

    # ---------- ③ 今天的问题 ----------
    s.rrect(56, 800, 1076, 62, fill=CARD, stroke=LINE, sw=2)
    s.star(84, 831, 12, ORANGE)
    s.text(110, 826, "复盘主问题：只跑一种机制为什么到不了最简 IR？——重写会互相解锁：fold 造出常量 1.0，Mul(x,1)→x 才有得匹配；",
           size=10.5, fill=INK, anchor="start")
    s.text(110, 844, "乘一塌缩后 Relu(Relu) 才能配对；combo_shape 还证明：类型信息不齐时，Pattern 的护栏连迭代到不动点也冲不过去。",
           size=10.5, fill=INK, anchor="start")
    s.save("01-overview.svg")


# =====================================================================
# 图 2：combo.mlir 三步接力
# =====================================================================
def img_combo_chain():
    s = SVG(1180, 900)
    header(s, "combo.mlir 接力赛：三步环环相扣，抽掉任何一步都停在半路",
           "左侧为起点数据流图（8 ops）；三支箭头是三次解锁；右侧矩阵为 --enable/disable-patterns 实测（含 func 两个壳）")

    # ---------- 起点 SSA 图 ----------
    s.text(70, 100, "起点（mini-count-ops：8 ops）", size=12.5, fill=INK,
           anchor="start", bold=True)
    # 节点： (x, y, w, h, fill, stroke, title, sub)
    nodes = [
        (60, 130, 108, 52, CARD, LINE, "c0, c1", "constant 0.5 ×2"),
        (60, 210, 108, 52, ORANGE_BG, ORANGE, "one = add(c0,c1)", "0.5 + 0.5"),
        (60, 300, 108, 52, CARD, LINE, "x", "函数入参"),
        (60, 380, 108, 52, CARD, LINE, "r = relu(x)", "max(0, x)"),
        (60, 470, 108, 52, GREEN_BG, GREEN, "m = mul(r, one)", "等 one 变 1.0"),
        (60, 560, 108, 52, BLUE_BG, BLUE, "rr = relu(m)", "等 m 变 relu"),
        (60, 650, 108, 52, CARD, LINE, "return rr", ""),
    ]
    for x, y, w, h, f, st, t, sub in nodes:
        s.rrect(x, y, w, h, fill=f, stroke=st, sw=2.2)
        s.text(x + w / 2, y + h / 2 - 4, t, size=9.6, bold=True)
        if sub:
            s.text(x + w / 2, y + h / 2 + 14, sub, size=8.2, fill=GRAY)
    s.arrow(114, 182, 114, 210, sw=1.6)
    s.arrow(114, 262, 114, 300, stroke=GRAY, sw=1.4)
    s.arrow(114, 352, 114, 380, sw=1.6)
    s.arrow(114, 432, 114, 470, sw=1.6)
    s.arrow(114, 522, 114, 560, sw=1.6)
    s.arrow(114, 612, 114, 650, sw=1.6)

    # ---------- 三步解锁（中间列） ----------
    steps = [
        (ORANGE, ORANGE_BG, "① fold（Day 47 的钩子）",
         ["add(0.5, 0.5) → constant 1.0", "两个 0.5 常量变死代码，被驱动清走",
          "→ 6 ops（constant 1.0 + relu×2 + mul）"],
         "只有 fold 能把 add 变成常量；两条代数 Pattern 都造不出 1.0"),
        (GREEN, GREEN_BG, "② mini-mul-one（Day 46 的 Pattern）",
         ["mul(r, 1.0) → r", "护栏：1.0 必须是 splat 常量才匹配",
          "→ 4 ops（relu×2）"],
         "① 没跑，mul 的操作数还是 add，这条 Pattern 一次都匹配不上"),
        (BLUE, BLUE_BG, "③ mini-double-relu（Day 45 的 Pattern）",
         ["relu(relu(x)) → relu(x)", "护栏：输入必须由另一个 relu 定义",
          "→ 3 ops（只剩 relu，最简）"],
         "② 没跑，外层 relu 的输入是 mul，这条 Pattern 干等"),
    ]
    y0 = 140
    for i, (c, cbg, t, lines, foot) in enumerate(steps):
        y = y0 + i * 190
        s.rrect(250, y, 330, 158, fill=cbg, stroke=c, sw=2.4)
        s.text(415, y + 26, t, size=11.5, fill=c, bold=True)
        s.line(274, y + 40, 556, y + 40, stroke=c, sw=1.1, amp=0.8)
        for j, ln in enumerate(lines):
            s.text(274, y + 62 + j * 19, ln, size=9.4, fill=INK,
                   anchor="start", bold=(j == 0))
        s.text(415, y + 140, foot, size=8.6, fill=GRAY)
        # 指向下一步的小箭头
        if i < 2:
            s.arrow(415, y + 158, 415, y + 190, stroke=c, sw=2.0, ah=10)

    # 起点到步骤①、步骤之间的连线
    s.arrow(168, 236, 250, 240, stroke=ORANGE, sw=2.2, ah=10)

    # ---------- 右侧实验矩阵 ----------
    s.text(626, 100, "③ 实测矩阵（-mini-count-ops 计数）", size=12.5, fill=INK,
           anchor="start", bold=True)
    rows = [
        ("配置（canonicalize 的过滤参数）", "剩余", "谁没出手", True),
        ("只 fold（disable 三条 Pattern）", "6 ops", "三条全关", False),
        ("fold + 双 relu（disable 乘一）", "6 ops", "双 relu 干等！", False),
        ("fold + 加负零（enable add-neg-zero）", "6 ops", "负零救不了 0.5+0.5", False),
        ("fold + 乘一（enable mul-one）", "4 ops", "双 relu 缺席", False),
        ("fold + 乘一 + 双 relu", "3 ops", "全链跑通 ✓", False),
        ("默认 -canonicalize（不过滤）", "3 ops", "同上——工作清单自动接力 ✓", False),
    ]
    rx, ry, rw, rh = 626, 118, 510, 26
    for i, (cfg, left, note, head) in enumerate(rows):
        y = ry + i * rh
        fill = SOFT if head else (CARD if i % 2 else "#f8f5ec")
        s.rrect(rx, y, rw, rh - 4, fill=fill, stroke=LINE, sw=1.6, r=6)
        if head:
            s.text(rx + 16, y + 17, cfg, size=9.5, bold=True, anchor="start")
            s.text(rx + 330, y + 17, left, size=9.5, bold=True, anchor="start")
            s.text(rx + 390, y + 17, note, size=9.5, bold=True, anchor="start")
        else:
            hot = ("干等" in note) or ("全链" in note)
            s.text(rx + 16, y + 17, cfg, size=9.2, anchor="start")
            s.text(rx + 330, y + 17, left, size=9.4, bold=True, anchor="start",
                   fill=GREEN if "3 ops" in left else (RED if "6 ops" in left else ORANGE))
            s.text(rx + 390, y + 17, note, size=9.0, anchor="start",
                   fill=GREEN if "✓" in note else (RED if "干等" in note else GRAY))
    s.text(626, 322, "读法：中间两行是关键证据——“开了双 relu 却一次没出手”，因为它在等 ②；",
           size=9.4, fill=INK, anchor="start")
    s.text(626, 340, "“开了加负零也白开”，因为 0.5+0.5 不是 -0.0 恒等式——恒等式 Pattern 造不出常量。",
           size=9.4, fill=INK, anchor="start")

    # 命令行语法提示
    s.rrect(626, 366, 510, 118, fill=RED_BG, stroke=RED, sw=2.2)
    s.text(881, 390, "命令行坑：过滤列表不要加方括号！", size=11, fill=RED, bold=True)
    s.text(646, 412, "enable-patterns=[mini-mul-one]  ✗", size=9.4, fill=INK,
           anchor="start")
    s.text(646, 430, "  列表解析把 [..] 当成一个受保护的整串，标签永远对不上；", size=9.0,
           fill=GRAY, anchor="start")
    s.text(646, 447, "  enable 侧会悄悄过滤掉所有 Pattern，disable 侧则谁也禁不掉", size=9.0,
           fill=GRAY, anchor="start")
    s.text(646, 468, "enable-patterns=mini-mul-one,mini-double-relu  ✓", size=9.4,
           fill=GREEN, anchor="start", bold=True)

    # 底部最终对照
    s.rrect(250, 700, 330, 158, fill=CARD, stroke=BLUE, sw=2.2)
    s.text(415, 726, "终点：3 ops", size=12, fill=BLUE, bold=True)
    for i, ln in enumerate(["func.func @combo(%x: tensor<2x2xf32>) {",
                            "  %0 = mini.relu %x : ...",
                            "  return %0 : tensor<2x2xf32>", "}"]):
        s.text(274, 752 + i * 18, ln, size=8.8, fill=INK, anchor="start")
    s.text(415, 836, "六条指令塌成一条，语义分毫未变", size=9, fill=GRAY)
    s.arrow(580, 779, 626, 420, stroke=GRAY, sw=1.2, ah=8)
    s.save("02-combo-chain.svg")


# =====================================================================
# 图 3：类型护栏关卡（combo_shape）
# =====================================================================
def img_shape_unlock():
    s = SVG(1180, 760)
    header(s, "combo_shape.mlir：信息关卡——类型不齐，Pattern 的护栏不放行",
           "两个 -canonicalize 都跑到不动点，差别只在前面有没有 -mini-infer-shape 先补类型（数字为真实计数）")

    # 起点
    s.rrect(50, 100, 250, 200, fill=CARD, stroke=LINE, sw=2.2)
    s.text(175, 126, "起点（9 ops）", size=12, bold=True)
    for i, ln in enumerate(["%one = add(c0, c1)   → 2x2",
                            "%mm  = matmul(a, b)  → ?x2",
                            "%m   = mul(%mm, %one) → 2x2",
                            "%r1  = relu(%m), %r2 = relu(%r1)"]):
        s.text(175, 152 + i * 19, ln, size=8.8, anchor="start" if i > 0 else "middle",
               fill=INK)
    s.text(175, 240, "结果类型故意写成 ?x2：", size=9.2, fill=RED, bold=True)
    s.text(175, 257, "留给 Shape 推导去细化的空位", size=8.8, fill=GRAY)
    s.text(175, 278, "(Verifier 对 ? 保守放行)", size=8.2, fill=GRAY)

    # 中间关卡
    s.rrect(360, 96, 240, 210, fill=SOFT, stroke=LINE, sw=2.2)
    s.text(480, 122, "代数 Pattern 的类型护栏", size=11.5, bold=True)
    s.text(480, 148, "if (x.getType() !=", size=9.6, anchor="start")
    s.text(480, 166, "    mul.getRes().getType())", size=9.6, anchor="start")
    s.text(480, 184, "  return failure();", size=9.6, anchor="start")
    s.text(480, 212, "把 2x2 的结果换成 ?x2 的值，", size=8.8, fill=GRAY)
    s.text(480, 227, "使用者的类型就对不上——", size=8.8, fill=GRAY)
    s.text(480, 242, "护栏拦的不是合法重写，", size=8.8, fill=GRAY)
    s.text(480, 257, "是信息不足的重写", size=8.8, fill=GRAY)
    s.text(480, 286, "（第 46 天实测过的坑）", size=8.2, fill=GRAY)

    # 两条路径
    s.arrow(300, 170, 360, 170, sw=1.8)

    # 上路：只 canonicalize
    s.rrect(660, 90, 500, 152, fill=RED_BG, stroke=RED, sw=2.4)
    s.text(910, 116, "只跑 -canonicalize（6 ops，卡住）", size=11.5, fill=RED, bold=True)
    for i, ln in enumerate([
            "fold：add → constant 1.0 ✓    双 relu：r2 消失 ✓",
            "mul-one：护栏处 x 是 ?x2 ≠ res 2x2 → 放弃 ✗",
            "mul 留在图里，跑到不动点也推不走"]):
        s.text(910, 142 + i * 20, ln, size=9.2, fill=INK)
    s.text(910, 218, "不动点 ≠ 最简：迭代再多次，信息缺口自己长不出数字", size=9,
           fill=RED, bold=True)

    # 下路：先 infer-shape
    s.rrect(660, 262, 500, 176, fill=GREEN_BG, stroke=GREEN, sw=2.4)
    s.text(910, 288, "先 -mini-infer-shape 再 -canonicalize（4 ops ✓）", size=11.5,
           fill=GREEN, bold=True)
    for i, ln in enumerate([
            "infer-shape：matmul 的 ?x2 → 2x2（只细化，不删算子）",
            "mul-one：护栏处 x 是 2x2 == res 2x2 → 放行 ✓",
            "mul → %mm，双 relu 随后接力 → 只剩 matmul + relu"]):
        s.text(910, 314 + i * 20, ln, size=9.2, fill=INK)
    s.text(910, 392, "同一条命令补上 -mini-infer-shape：6 ops → 4 ops", size=9,
           fill=GREEN, bold=True)

    s.arrow(600, 160, 660, 160, stroke=RED, sw=2.2, ah=10)
    s.arrow(600, 240, 660, 340, stroke=GREEN, sw=2.2, ah=10)
    # 下路绕行：起点 → infer 卡
    s.rrect(360, 330, 240, 108, fill=BLUE_BG, stroke=BLUE, sw=2.4)
    s.text(480, 356, "-mini-infer-shape", size=11, fill=BLUE, bold=True)
    s.text(480, 378, "refineShape：old=? 采纳推导值", size=8.8, fill=INK)
    s.text(480, 395, "old=数字 原样保留（承诺优先）", size=8.8, fill=INK)
    s.text(480, 418, "细化的类型所有使用者同时可见", size=8.4, fill=GRAY)
    s.arrow(300, 240, 360, 370, stroke=BLUE, sw=2.2, ah=10)
    s.arrow(600, 384, 660, 350, stroke=GREEN, sw=1.6, ah=8)

    # 底部结论
    s.rrect(50, 560, 1080, 168, fill=CARD, stroke=LINE, sw=2.2)
    s.star(80, 596, 13, ORANGE)
    s.text(108, 592, "复盘答案（对应计划的问题“为什么一次 Pattern 遍历不一定得到最简 IR”）",
           size=11.5, bold=True, anchor="start")
    for i, ln in enumerate([
            "一层：图会变。每次重写都可能制造新的匹配机会（常量出现了、下游变短了），只扫一遍必然漏掉“晚到的机会”——",
            "        所以驱动要靠工作清单回头重看，迭代到不动点（图 4）。",
            "二层：信息要齐。类型护栏拦下的重写，迭代一万次也放不了行——缺的不是遍数，是类型信息，",
            "        而补信息是 Shape 推导（Pass）的职责，不是 Pattern 的职责。三种机制必须接力，缺一不可。"]):
        s.text(108, 622 + i * 22, ln, size=9.8, fill=INK, anchor="start",
               bold=(i == 0 or i == 2))
    s.save("03-shape-unlock.svg")


# =====================================================================
# 图 4：贪婪驱动的工作清单
# =====================================================================
def img_worklist():
    s = SVG(1180, 820)
    header(s, "图解：贪婪驱动的工作清单——“回头重看”是怎么发生的",
           "依据 MLIR 18 GreedyPatternRewriteDriver.cpp 画制；右侧标注为本次真实实验（outputs/13）")

    # 主流程
    s.rrect(60, 100, 150, 60, fill=CARD, stroke=LINE, sw=2)
    s.text(135, 124, "初始入队", size=10.5, bold=True)
    s.text(135, 142, "walk 全部算子", size=8.6, fill=GRAY)

    s.rrect(60, 200, 150, 60, fill=SOFT, stroke=LINE, sw=2)
    s.text(135, 224, "弹出一个 op", size=10.5, bold=True)
    s.text(135, 242, "工作清单 LIFO", size=8.6, fill=GRAY)
    s.arrow(135, 160, 135, 200, sw=1.8)

    s.rrect(60, 300, 150, 58, fill=RED_BG, stroke=RED, sw=2)
    s.text(135, 324, "死算子？", size=10.5, fill=RED, bold=True)
    s.text(135, 342, "无使用 + Pure", size=8.6, fill=GRAY)
    s.arrow(135, 260, 135, 300, sw=1.8)
    s.text(158, 285, "是 → 擦除（不占预算）", size=8.6, fill=RED, anchor="start")

    s.rrect(60, 390, 150, 58, fill=ORANGE_BG, stroke=ORANGE, sw=2)
    s.text(135, 414, "试 fold", size=10.5, fill=ORANGE, bold=True)
    s.text(135, 432, "纯计算，不占预算", size=8.6, fill=GRAY)
    s.arrow(135, 358, 135, 390, sw=1.8)
    s.text(158, 380, "成功 → 物化常量+改边+擦除", size=8.6, fill=ORANGE, anchor="start")

    s.rrect(60, 480, 150, 58, fill=GREEN_BG, stroke=GREEN, sw=2)
    s.text(135, 504, "试 Pattern", size=10.5, fill=GREEN, bold=True)
    s.text(135, 522, "按收益排序，逐个试", size=8.6, fill=GRAY)
    s.arrow(135, 448, 135, 480, sw=1.8)
    s.text(158, 470, "成功 → 改边+擦除，预算 +1", size=8.6, fill=GREEN, anchor="start")

    # 回环：改动了谁就重新入队
    s.rrect(330, 430, 300, 150, fill=CARD, stroke=BLUE, sw=2.4)
    s.text(480, 456, "改动了就重新入队（回头路）", size=11, fill=BLUE, bold=True)
    for i, ln in enumerate([
            "改边 → notifyOperationModified(使用者)",
            "擦除 → 操作数定义者重回清单",
            "物化新常量 → 新算子入队",
            "（combo：fold 完 add，mul 重回清单；）",
            "（乘一塌完 mul，外层 relu 重回清单）"]):
        s.text(480, 480 + i * 19, ln, size=8.9, fill=INK)
    s.arrow(210, 510, 330, 510, stroke=BLUE, sw=2.0, ah=9)
    s.arrow(330, 470, 210, 240, stroke=BLUE, sw=2.0, ah=9)
    s.text(258, 330, "重看", size=9.6, fill=BLUE, bold=True)

    # 外圈：迭代
    s.rrect(700, 200, 200, 74, fill=SOFT, stroke=LINE, sw=2)
    s.text(800, 226, "本轮清单跑空了", size=10.5, bold=True)
    s.text(800, 246, "本轮有过改动吗？", size=9, fill=GRAY)
    s.arrow(480, 430, 700, 240, stroke=LINE, sw=1.8, ah=9)
    s.rrect(700, 320, 200, 74, fill=GREEN_BG, stroke=GREEN, sw=2.2)
    s.text(800, 346, "有 → 再来一轮", size=10.5, fill=GREEN, bold=True)
    s.text(800, 366, "清单重填（预算重置！）", size=9, fill=GRAY)
    s.arrow(800, 274, 800, 320, stroke=GREEN, sw=2.0, ah=9)
    s.arrow(700, 357, 135, 232, stroke=GREEN, sw=1.8, ah=9)
    s.rrect(700, 440, 200, 74, fill=BLUE_BG, stroke=BLUE, sw=2.2)
    s.text(800, 466, "无 → 不动点", size=10.5, fill=BLUE, bold=True)
    s.text(800, 486, "收工：本轮一无所获", size=9, fill=GRAY)
    s.arrow(800, 274, 800, 320, stroke=GREEN, sw=0.1, ah=0.1)
    s.line(900, 240, 940, 240, stroke=LINE, sw=1.6)
    s.arrow(940, 240, 940, 470, stroke=LINE, sw=1.6, ah=9)
    s.text(952, 356, "否", size=9.6, fill=BLUE)

    # 右侧注解：预算实验
    s.rrect(950, 540, 200, 150, fill=ORANGE_BG, stroke=ORANGE, sw=2.2)
    s.text(1050, 566, "实测：预算拆轮", size=10.5, fill=ORANGE, bold=True)
    s.text(1050, 588, "max-num-rewrites=1：", size=8.8, fill=INK)
    s.text(1050, 605, "每轮只许 1 次 Pattern 重写，", size=8.4, fill=INK)
    s.text(1050, 620, "外圈循环把活拆成更多轮；", size=8.4, fill=INK)
    s.text(1050, 635, "最终 IR 与默认运行", size=8.4, fill=INK)
    s.text(1050, 650, "逐字节相同（outputs/13", size=8.4, fill=INK)
    s.text(1050, 665, "与 07 diff 为空）", size=8.4, fill=INK)
    s.text(1050, 686, "fold / 擦死代码不占预算", size=8.2, fill=GRAY)

    # 底部结论
    s.rrect(60, 600, 570, 180, fill=CARD, stroke=LINE, sw=2.2)
    s.text(345, 628, "一次遍历为什么不够：三个“晚到的机会”", size=11.5, bold=True)
    for i, ln in enumerate([
            "① 常量晚到：fold 在 add 上造出 1.0 时，mul 早已被扫过——",
            "   不回头重看，Mul(x,1)→x 永远匹配不上；",
            "② 下游晚到：乘一塌缩 mul 之后，外层 relu 的输入才变成 relu——",
            "   Relu(Relu) 的机会这才出现；",
            "③ 类型晚到（图 3）：? 细化成 2x2 之后护栏才放行——",
            "   这种机会连迭代都等不来，必须换机制（Pass）先补信息。"]):
        s.text(345, 654 + i * 20, ln, size=9.2, fill=INK, anchor="start",
               bold=(i in (0, 2, 4)))
    s.save("04-worklist.svg")


if __name__ == "__main__":
    img_overview()
    img_combo_chain()
    img_shape_unlock()
    img_worklist()
