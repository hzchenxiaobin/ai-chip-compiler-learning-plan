#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第 53 天教程插图生成器：手绘 sketch 风（Excalidraw-like）SVG。

用法：  python3 make_images.py
输出：  images/01-overview.svg       融合周定位 + 目标链（技术信息图）
        images/02-shape-types.svg    Bias Shape 三分类 + 输出类型（技术信息图）
        images/03-pattern-flow.svg   融合 Pattern 决策流（技术信息图）
        images/04-results.svg        本机真实运行结果对照（技术信息图）

图中所有数字、IR、报错文案均来自本目录 outputs/ 与教程 §5 的真实运行
记录（2026-11-12，MLIR 18.1.8 / g++ 9.4.0 / aarch64 Linux），无虚构。
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

    def text(self, x, y, s, size=10, fill=INK, anchor="middle", bold=False,
             opacity=1.0):
        self.parts.append(
            f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" '
            f'fill="{fill}" text-anchor="{anchor}" opacity="{opacity}" '
            f'font-weight="{"bold" if bold else "normal"}">{esc(s)}</text>')

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


def chip(s, x, y, w, label, fill, stroke, tsize=10):
    s.rrect(x, y, w, 26, fill=fill, stroke=stroke, sw=2.0, r=10)
    s.text(x + w / 2, y + 17, label, size=tsize, fill=INK, bold=True)


def mono(s, x, y, txt, size=9.6, fill=INK, anchor="start"):
    s.text(x, y, txt, size=size, fill=fill, anchor=anchor)


# =====================================================================
# 图 1：全局定位 + 目标链
# =====================================================================
def img_overview():
    s = SVG(1180, 850)
    header(s, "第 53 天：MatMul＋Bias 融合——bias 的形状对上了，输出类型听谁的？",
           "上：目标链与两个融合产物｜中：mini-opt 管道定位｜下：第 8 周路线（今天是第 4 格）")

    # ---------- ① 目标链 ----------
    s.text(60, 102, "① 目标链（第 13 天起的最终项目图，今天第一次真正动它）",
           size=13, fill=INK, anchor="start", bold=True)
    chain = [
        (60, 126, 128, 74, CARD, LINE, "mini.matmul",
         ["%a: 2x3", "%b: 3x2 → %m: 2x2"]),
        (250, 126, 128, 74, CARD, LINE, "mini.add",
         ["%m + %bias", "bias: 2x2 → %s: 2x2"]),
        (440, 126, 108, 74, CARD, LINE, "mini.relu",
         ["%s → %r", "（可选）"]),
    ]
    for x, y, w, h, f, st, t, lines in chain:
        s.rrect(x, y, w, h, fill=f, stroke=st, sw=2.2)
        s.text(x + w / 2, y + 30, t, size=11.4, bold=True)
        for i, ln in enumerate(lines):
            s.text(x + w / 2, y + 50 + i * 15, ln, size=8.8, fill=GRAY)
    s.arrow(188, 163, 250, 163, sw=1.8)
    s.arrow(378, 163, 440, 163, sw=1.8)
    s.text(219, 150, "%m", size=9, fill=ORANGE, bold=True)
    s.text(409, 150, "%s", size=9, fill=ORANGE, bold=True)

    # 两个融合产物
    s.rrect(610, 118, 268, 46, fill=GREEN_BG, stroke=GREEN, sw=2.2)
    s.text(744, 137, "mini.fused_matmul_bias", size=11.2, bold=True, fill=INK)
    s.text(744, 155, "今天新定义：res = A·B + bias（两算子目标）",
           size=8.6, fill=GRAY)
    s.rrect(610, 172, 268, 46, fill=BLUE_BG, stroke=BLUE, sw=2.2)
    s.text(744, 191, "mini.fused_matmul_bias_relu", size=11.2, bold=True, fill=INK)
    s.text(744, 209, "第 50 天定义：res = relu(A·B + bias)（Relu 被吸收时）",
           size=8.6, fill=GRAY)
    s.arrow(560, 145, 610, 141, sw=1.8, stroke=GREEN)
    s.arrow(560, 180, 610, 190, sw=1.8, stroke=BLUE)

    # 中间值不落盘标注
    s.rrect(920, 126, 200, 92, fill=SOFT, stroke=LINE, sw=1.8)
    s.text(1020, 148, "融合的收益", size=10.6, bold=True, fill=ORANGE)
    for i, ln in enumerate([
            "%m、%s 不再是 SSA 值", "（不落盘、不重读）", "乘积 2x2 时省 4 遍读写",
            "4096x4096 时省的是 64MB", "中间张量的一个来回"]):
        s.text(1020, 168 + i * 14.5, ln, size=8.4, fill=GRAY)
    s.star(910, 130, 9, ORANGE)

    # ---------- ② mini-opt 管道定位 ----------
    s.text(60, 262, "② 今天动的是「融合 Pass」：第 3 个 Pattern 进驻",
           size=13, fill=INK, anchor="start", bold=True)
    pipe = [
        (60, 286, 118, 66, CARD, LINE, "解析 + verify",
         ["bias 三分类在这拦", "非法 shape（实验 H~K）"]),
        (202, 286, 118, 66, CARD, LINE, "Shape 推导",
         ["Day 43~44", "今天不碰"]),
        (344, 286, 118, 66, CARD, LINE, "化简",
         ["Day 45~48", "-canonicalize"]),
        (486, 286, 152, 66, ORANGE_BG, ORANGE, "融合 Pass（今天）",
         ["Day 51 add+relu", "Day 52 多使用者", "Day 53 matmul+bias ←"]),
        (662, 286, 118, 66, CARD, LINE, "Layout 优化",
         ["Day 57 起", "今天不碰"]),
        (804, 286, 118, 66, CARD, LINE, "Lowering",
         ["Day 85 起", "循环生成"]),
    ]
    for x, y, w, h, f, st, t, lines in pipe:
        s.rrect(x, y, w, h, fill=f, stroke=st, sw=2.2)
        s.text(x + w / 2, y + 24, t, size=10.4, bold=True,
               fill=ORANGE if f == ORANGE_BG else INK)
        for i, ln in enumerate(lines):
            s.text(x + w / 2, y + 43 + i * 14, ln, size=7.9, fill=GRAY)
    for x1, x2 in ((178, 202), (320, 344), (462, 486), (638, 662), (780, 804)):
        s.arrow(x1, 319, x2, 319, sw=1.6)
    s.rrect(950, 286, 176, 66, fill=SOFT, stroke=LINE, sw=1.8)
    s.text(1038, 308, "锚定规则不变", size=10.2, bold=True, fill=INK)
    s.text(1038, 326, "Pattern 长在消费者", size=8.4, fill=GRAY)
    s.text(1038, 340, "（mini.add）上——区域", size=8.4, fill=GRAY)
    s.text(1038, 354, "的出口是 %s 的使用者", size=8.4, fill=GRAY)

    # ---------- ③ 第 8 周路线 ----------
    s.text(60, 410, "③ 第 8 周（算子融合）路线：今天的上游是昨天的多使用者规则",
           size=13, fill=INK, anchor="start", bold=True)
    week = [
        (60, 434, 158, 92, CARD, LINE, "Day 50",
         ["定义融合算子", "fused_add_relu", "fused_matmul_bias_relu"]),
        (240, 434, 158, 92, CARD, LINE, "Day 51",
         ["Add + Relu 融合", "四步改写机制", "擦除顺序"]),
        (420, 434, 158, 92, CARD, LINE, "Day 52",
         ["多使用者限制", "hasOneUse 闸门", "reject / keep"]),
        (600, 434, 176, 92, ORANGE_BG, ORANGE, "Day 53（今天）",
         ["MatMul + Bias 融合", "bias 形状三分类", "输出类型跟 matmul"]),
        (792, 434, 158, 92, CARD, LINE, "Day 54",
         ["三算子与优先级", "两阶段 vs 直接", "（F 实验留了入口）"]),
        (972, 434, 158, 92, CARD, LINE, "Day 55",
         ["正确性与负例", "融合验收", "回归测试"]),
    ]
    for x, y, w, h, f, st, t, lines in week:
        s.rrect(x, y, w, h, fill=f, stroke=st, sw=2.2)
        s.text(x + w / 2, y + 24, t, size=11, bold=True,
               fill=ORANGE if f == ORANGE_BG else INK)
        for i, ln in enumerate(lines):
            s.text(x + w / 2, y + 46 + i * 15, ln, size=8.6, fill=GRAY)
    for x1, x2 in ((218, 240), (398, 420), (578, 600), (776, 792), (956, 972)):
        s.arrow(x1, 480, x2, 480, sw=1.6)

    # ---------- ④ 今天的三个新问题 ----------
    s.text(60, 570, "④ Add + Relu 的机制原样复用，但 matmul 带来三个新问题",
           size=13, fill=INK, anchor="start", bold=True)
    qs = [
        (60, 594, 340, 108, BLUE_BG, BLUE, "Bias Shape",
         ["add 有两个操作数，谁是 bias？",
          "[N] 向量（torch.nn.Linear 的经典写法）",
          "今天合法吗？——三分类 Same / BroadcastOnly /",
          "Mismatch，今天只放 Same（第 60 天放行广播）"]),
        (420, 594, 340, 108, GREEN_BG, GREEN, "输出类型",
         ["融合算子的结果类型听谁的？lhs 是",
          "tensor<2x3>，bias 和乘积是 tensor<2x2>——",
          "照抄 lhs 会得到 2x3（实验 J 被 Verifier 拦下）。",
          "答案：跟 matmul 的输出 [M,N] 走"]),
        (780, 594, 340, 108, RED_BG, RED, "重算的代价",
         ["乘积 %m 多使用者时 keep 策略保留 matmul，",
          "重算一次 = 2·M·N·K 次乘加（Day 52 只亏",
          "M·N 次加法）。K 大 1 个量级，matmul 就贵",
          "一个量级——这就是「更致命」"]),
    ]
    for x, y, w, h, f, st, t, lines in qs:
        s.rrect(x, y, w, h, fill=f, stroke=st, sw=2.2)
        s.text(x + w / 2, y + 26, t, size=12.4, bold=True)
        for i, ln in enumerate(lines):
            s.text(x + w / 2, y + 50 + i * 15.5, ln, size=8.9, fill=INK)

    s.text(590, 740,
           "一句话：昨天的规则（先采样使用者、失败无副作用、先擦消费者）一行不改；",
           size=11.5, fill=INK)
    s.text(590, 760,
           "今天新增的三件事全部来自「matmul 的形状和代价不再是逐元素的」。",
           size=11.5, fill=INK)
    s.text(590, 792, "（图中数字来自教程 §1/§5 的真实运行，2026-11-12）",
           size=9, fill=GRAY)
    s.save("01-overview.svg")


# =====================================================================
# 图 2：Bias Shape 三分类 + 输出类型
# =====================================================================
def img_shape_types():
    s = SVG(1180, 860)
    header(s, "核心机制 ①：Bias Shape 三分类与输出类型的归属",
           "左：形状从哪来｜中：三分类怎么判（MiniRules.h，与 Verifier 物理共享）｜右：结果类型跟 matmul 走")

    # ---------- 左：matmul 形状 ----------
    s.text(60, 102, "① 乘积的形状由 matmul 决定：M·K · K·N → M·N",
           size=13, fill=INK, anchor="start", bold=True)

    def cell_grid(x, y, rows, cols, label, dim, color=BLUE):
        cw, ch = 22, 22
        for r in range(rows):
            for c in range(cols):
                s.rrect(x + c * cw, y + r * ch, cw - 3, ch - 3,
                        fill="#ffffff", stroke=color, sw=1.5, r=4)
        s.text(x + cols * cw / 2 - 1, y + rows * ch + 18, label,
               size=10.4, bold=True)
        s.text(x + cols * cw / 2 - 1, y + rows * ch + 33, dim,
               size=8.8, fill=GRAY)

    cell_grid(80, 130, 2, 3, "%a（lhs）", "2 × 3（M×K）")
    s.text(262, 180, "·", size=26, fill=INK, bold=True)
    cell_grid(290, 130, 3, 2, "%b（rhs）", "3 × 2（K×N）")
    s.text(432, 180, "=", size=22, fill=INK, bold=True)
    cell_grid(460, 130, 2, 2, "%m（乘积）", "2 × 2（M×N）", color=ORANGE)
    s.text(300, 232, "K 必须对上：lhs 的第 2 维 = rhs 的第 1 维（3 = 3）",
           size=8.8, fill=GRAY)

    # bias 与乘积同形
    s.rrect(80, 268, 250, 106, fill=GREEN_BG, stroke=GREEN, sw=2.2)
    s.text(205, 292, "bias 的合法形状（今天）", size=11.4, bold=True)
    cell_grid(120, 306, 2, 2, "", "", color=GREEN)
    s.text(240, 330, "与乘积同形", size=10.4, bold=True)
    s.text(240, 347, "tensor<2x2xf32>", size=9.4, fill=INK)
    s.text(240, 362, "= Same（第 40 天口径）", size=8.6, fill=GRAY)

    # ---------- 中：三分类 ----------
    s.text(400, 102, "② classifyBias(bias, out)：三分类",
           size=13, fill=INK, anchor="start", bold=True)
    rows = [
        (400, 126, 340, 76, GREEN_BG, GREEN, "Same —— 放行",
         ["bias.getShape() == out.getShape()", "今天唯一能融合的形状"]),
        (400, 214, 340, 76, ORANGE_BG, ORANGE, "BroadcastOnly —— 拒绝（暂时）",
         ["bias 是 [N]，out 末维是 N：按行广播", "第 40 天起故意不支持，第 60 天放行"]),
        (400, 302, 340, 76, RED_BG, RED, "Mismatch —— 拒绝（永远）",
         ["连广播都对不上（如 1x2 对 2x2）", "语义上就没定义，谁来都不行"]),
    ]
    for x, y, w, h, f, st, t, lines in rows:
        s.rrect(x, y, w, h, fill=f, stroke=st, sw=2.2)
        s.text(x + w / 2, y + 26, t, size=11.6, bold=True)
        for i, ln in enumerate(lines):
            s.text(x + w / 2, y + 47 + i * 15, ln, size=8.9, fill=INK)
    s.arrow(570, 214, 570, 200, sw=1.6, stroke=GRAY)
    s.text(600, 212, "out = 乘积形状 [M,N]", size=8.6, fill=GRAY)

    # [N] 的语义说明（numpy 对照，来自 Python 版场景 F 的真实输出）
    s.rrect(400, 396, 340, 118, fill=SOFT, stroke=LINE, sw=1.8)
    s.text(570, 418, "BroadcastOnly 为什么「暂时」拒绝？", size=10.4,
           bold=True, fill=ORANGE)
    for i, ln in enumerate([
            "numpy 会按行广播，算出",
            "[[22,-23],[-17,18]]（Python 版场景 F 实测）",
            "——求值器「能算」≠ 方言规则「允许算」；",
            "真实 MLIR 里这张图在 Verifier 就被拦下",
            "（实验 H：rc=1，报「需要广播，第 60 天放行」）"]):
        s.text(570, 438 + i * 15, ln, size=8.6, fill=GRAY)

    # ---------- 右：输出类型 ----------
    s.text(790, 102, "③ 融合算子的结果类型：跟 matmul 走",
           size=13, fill=INK, anchor="start", bold=True)
    s.rrect(790, 126, 330, 88, fill=GREEN_BG, stroke=GREEN, sw=2.2)
    s.text(955, 150, "正确来源", size=11.4, bold=True, fill=GREEN)
    mono(s, 830, 172, "rewriter.create<mini::FusedMatmulBiasOp>(", size=9)
    mono(s, 830, 186, "    add.getLoc(), m.getType(),   // ← [M,N]", size=9,
         fill=GREEN)
    mono(s, 830, 200, "    mm.getLhs(), mm.getRhs(), bias);", size=9)
    s.text(955, 218, "m.getType() = 乘积类型 = tensor<2x2xf32>", size=8.6,
           fill=GRAY)

    s.rrect(790, 230, 330, 96, fill=RED_BG, stroke=RED, sw=2.2)
    s.text(955, 252, "两个错误来源", size=11.4, bold=True, fill=RED)
    s.text(955, 272, "✗ 照抄 lhs：tensor<2x3xf32>", size=9.4, fill=INK)
    s.text(955, 288, "  （Python 版沿用 Day 52 的 inputs[0].type 就会这样）", size=8.2,
           fill=GRAY)
    s.text(955, 305, "✗ 照抄 bias：第 60 天 [N] 放行后会错成 tensor<2xf32>",
           size=9.4, fill=INK)
    s.text(955, 318, "  （bias 形状 ≠ 输出形状，永远不是类型来源）", size=8.2,
           fill=GRAY)

    # 实验 J 的真实报错（fused_bad_result_type.mlir）
    s.rrect(790, 342, 330, 84, fill=CARD, stroke=LINE, sw=1.8)
    s.text(955, 362, "实验 J（Verifier 兜底，本机真实报错）：", size=9.2,
           bold=True, fill=INK)
    mono(s, 812, 380, "error: 'mini.fused_matmul_bias' op", size=8.4,
         fill=RED)
    mono(s, 812, 394, " 结果 shape 应为 [2,2]（跟 matmul 走），", size=8.4,
         fill=RED)
    mono(s, 812, 408, " 实际 [2,3]", size=8.4, fill=RED)
    s.text(955, 424, "rc=1 —— 类型错在 Verifier 就被拦下，轮不到执行", size=8.2,
           fill=GRAY)

    # ---------- 底部：Verifier 与 Pattern 共用同一份规则 ----------
    s.rrect(60, 540, 1060, 120, fill=CARD, stroke=LINE, sw=2.2)
    s.text(590, 566, "同一条规则，两处上岗（MiniRules.h 物理共享，方法同第 50 天 MatmulRules.h）",
           size=11.6, bold=True, fill=INK)
    s.rrect(100, 586, 300, 56, fill=BLUE_BG, stroke=BLUE, sw=2.0)
    s.text(250, 606, "第一道闸门：mini.add 的 Verifier", size=9.8, bold=True)
    s.text(250, 623, "非法 bias 的图根本进不了管道", size=8.4, fill=GRAY)
    s.text(250, 636, "（实验 H/I：解析阶段就 rc=1）", size=8.4, fill=GRAY)
    s.rrect(440, 586, 300, 56, fill=GREEN_BG, stroke=GREEN, sw=2.0)
    s.text(590, 606, "第二道闸门：Pattern 自己 classifyBias", size=9.8, bold=True)
    s.text(590, 623, "防的是绕过 Verifier 的图和第 60 天广播", size=8.4, fill=GRAY)
    s.text(590, 636, "放行后 N 对不上的情形", size=8.4, fill=GRAY)
    s.rrect(780, 586, 300, 56, fill=ORANGE_BG, stroke=ORANGE, sw=2.0)
    s.text(930, 606, "第三道闸门：融合算子自己的 Verifier", size=9.8, bold=True)
    s.text(930, 623, "fused_* 的 bias 规则与成员规则求并集", size=8.4, fill=GRAY)
    s.text(930, 636, "（实验 J/K：生成端也不能少查，Day 50 教训）", size=8.4,
           fill=GRAY)
    s.arrow(400, 614, 440, 614, sw=1.6, stroke=GRAY)
    s.arrow(740, 614, 780, 614, sw=1.6, stroke=GRAY)

    s.text(590, 690, "三分类的口径与第 40/50 天逐字相同：BiasKind::Same / BroadcastOnly / Mismatch；",
           size=10.5, fill=INK)
    s.text(590, 710, "今天的故事是「同一份规则第一次同时服务 Verifier 和 RewritePattern」。",
           size=10.5, fill=INK)
    s.text(590, 742, "（图中 IR/报错均来自 outputs/ 的真实运行记录）", size=9,
           fill=GRAY)
    s.save("02-shape-types.svg")


# =====================================================================
# 图 3：Pattern 决策流
# =====================================================================
def img_pattern_flow():
    s = SVG(1180, 900)
    header(s, "核心机制 ②：FuseMatmulBiasPattern 的决策流（mini-fuse-bias.cpp）",
           "锚在 mini.add 上；每一步检查失败都必须「一笔未改」地返回 failure（第 45/52 天铁律）")

    # 主干
    def flowbox(x, y, w, h, title, lines, fill=CARD, stroke=LINE,
                tsize=10.8):
        s.rrect(x, y, w, h, fill=fill, stroke=stroke, sw=2.2)
        s.text(x + w / 2, y + 22, title, size=tsize, bold=True,
               fill=ORANGE if fill == ORANGE_BG else INK)
        for i, ln in enumerate(lines):
            s.text(x + w / 2, y + 42 + i * 14.5, ln, size=8.6, fill=INK)

    flowbox(60, 96, 220, 88, "(1) 匹配根：mini.add",
            ["为什么不是 matmul？区域的出口是", "add 的结果 %s——Pattern 长在",
             "消费者上（第 51 天的结论）"], fill=BLUE_BG, stroke=BLUE)
    flowbox(340, 96, 250, 88, "(2) 找乘积：先 lhs 后 rhs",
            ["lhs.getDefiningOp<MatmulOp>()", "不行再看 rhs——bias 左右都认",
             "两侧都是 → 拒绝（实验 G）"])
    flowbox(650, 96, 250, 88, "(3) Bias Shape 三分类",
            ["classifyBias(bias, m)：Same 才继续", "BroadcastOnly / Mismatch →",
             "拒绝（第二道防线）"])
    flowbox(960, 96, 160, 88, "(4) 乘积 %m 使用者",
            ["hasOneUse() 在改写", "前采样（Day 52", "错误 3 的教训）"])
    s.arrow(280, 140, 340, 140, sw=1.7)
    s.arrow(590, 140, 650, 140, sw=1.7)
    s.arrow(900, 140, 960, 140, sw=1.7)

    # (4) 的三条出路（正交走线：先下后分再落，避免长箭头穿箱）
    flowbox(60, 240, 240, 86, "%m 单使用者",
            ["默认路径：融合后", "eraseOp(mm)，乘积随之消失", "（Day 51 的原样行为）"],
            fill=GREEN_BG, stroke=GREEN)
    flowbox(330, 240, 240, 86, "%m 多使用者 × reject",
            ["return failure()——图原样", "（恒等变换，实验 D：IR 一字未动）"],
            fill=CARD, stroke=RED)
    flowbox(600, 240, 260, 86, "%m 多使用者 × keep",
            ["融合分支，保留 mini.matmul", "给其他使用者——整次 matmul 在",
             "融合算子里重算（2·M·N·K 乘加）"], fill=ORANGE_BG, stroke=ORANGE)
    s.line(1040, 184, 1040, 208, sw=1.6)
    s.line(1040, 208, 180, 208, sw=1.5, amp=1.0)
    for tx, color, lbl in ((180, GREEN, "单用"),
                           (450, RED, "× reject"),
                           (730, ORANGE, "× keep")):
        s.arrow(tx, 208, tx, 236, sw=1.6, stroke=color)
        s.text(tx + 8, 228, lbl, size=8.4, fill=color, anchor="start")

    # (5) 可选 Relu
    flowbox(60, 372, 300, 108, "(5) 可选 Relu：%s 的唯一使用者是谁？",
            ["%s.hasOneUse() 且 user 是 mini.relu：", "  → Relu 直接吸收进 fused_matmul_bias_relu",
             "（实验 A：三算子一次到位）", "否则（含 %s 被 return 共用，实验 F）：",
             "  → 只做两算子融合 fused_matmul_bias", "Relu 留在图上——第 54 天的入口"],
            fill=BLUE_BG, stroke=BLUE)
    flowbox(400, 372, 300, 108, "(6) 改写四步（顺序即正确性）",
            ["① setInsertionPoint(add)，create 融合算子", "   （结果类型 = m.getType()）",
             "② RAUW：relu.result / add.result → 融合结果", "③ erase：先 Relu（若有）→ 再 Add",
             "④ 乘积单用 → erase MatMul；keep → 保留", "每一步中间状态都是合法图"],
            fill=GREEN_BG, stroke=GREEN)
    flowbox(740, 372, 380, 108, "擦除顺序为什么是 Relu → Add → MatMul",
            ["谁的结果先没人用，谁才能先走：擦 Relu 前 %r 的使用者",
             "已全部改接；擦 Add 前 %s 同理；MatMul 最后看 %m。",
             "反过来（先删生产者）= 悬空指针（Day 51 实验 C 的段错误）；",
             "「先改接 %s 再吸收」= 语义悄悄变错（本日错误 4）"],
            fill=SOFT, stroke=LINE)
    s.arrow(360, 426, 400, 426, sw=1.7)
    s.arrow(700, 426, 740, 426, sw=1.7)

    # 决策日志（真实输出）
    s.rrect(60, 530, 1060, 190, fill=CARD, stroke=LINE, sw=2.2)
    s.text(590, 554, "决策日志（stderr，本机真实输出节选——「为什么融合」必须说得出口）",
           size=11.2, bold=True, fill=INK)
    logs = [
        (GREEN, "实验 A（主线图）", [
            "[fuse3] 匹配 MatMul + Add + Relu（乘积使用者 1）",
            "         -> fused_matmul_bias_relu，Relu 直接吸收"]),
        (RED, "实验 D（乘积 2 使用者，默认）", [
            "[reject] 匹配 Add：乘积 %m 使用者 2 -> 拒绝融合",
            "         （Day 52 规则原样适用），保留整条链"]),
        (ORANGE, "实验 E（--strategy=keep）", [
            "[fuse3] 匹配 MatMul + Add + Relu（乘积使用者 2）",
            "[keep] 乘积还有 2 个使用者，保留 mini.matmul",
            "       —— 整次 matmul 将重算（2·M·N·K 次乘加）"]),
    ]
    x0 = 90
    for color, title, lines in logs:
        s.text(x0, 580, title, size=9.4, bold=True, fill=color)
        for i, ln in enumerate(lines):
            mono(s, x0, 598 + i * 14, ln, size=8.2, fill=INK)
        x0 += 350

    s.text(590, 756, "失败无副作用 + 先采样 + 先擦消费者：三条 Day 51/52 的铁律一行未改；",
           size=11, fill=INK)
    s.text(590, 776, "新增的只有「找乘积、判 bias、选融合目标」——因为 matmul 不再是逐元素算子。",
           size=11, fill=INK)
    s.text(590, 808, "（日志摘自 outputs/bias_relu.err、multi_user_reject.err、multi_user_keep.err）",
           size=9, fill=GRAY)
    s.save("03-pattern-flow.svg")


# =====================================================================
# 图 4：真实运行结果对照
# =====================================================================
def img_results():
    s = SVG(1180, 880)
    header(s, "本机真实运行对照（2026-11-12：g++ 9.4.0 / MLIR 18.1.8 / aarch64 Linux）",
           "五个最有信息量的下场：三合一、keep 重算、Relu 留守、Verifier 拦截、上游半程融合")

    def col(x, w, title, color, color_bg, ir_lines, note, note_color):
        s.rrect(x, 96, w, 30, fill=color_bg, stroke=color, sw=2.0, r=10)
        s.text(x + w / 2, 116, title, size=10.6, bold=True, fill=INK)
        s.rrect(x, 136, w, 216, fill=CARD, stroke=LINE, sw=1.8)
        for i, ln in enumerate(ir_lines):
            mono(s, x + 14, 158 + i * 14.6, ln, size=8.1, fill=INK)
        s.rrect(x, 364, w, 96, fill=SOFT, stroke=color, sw=1.8)
        for i, ln in enumerate(note):
            s.text(x + w / 2, 386 + i * 15, ln, size=8.7, fill=note_color)

    # 实验 A
    col(56, 212, "实验 A：主线图（默认策略）", GREEN, GREEN_BG,
        ["func @graph_bias_relu(...) {",
         "  // 融合前：3 个算子",
         "  %0 = mini.matmul %arg0, %arg1",
         "  %1 = mini.add %0, %arg2",
         "  %2 = mini.relu %1",
         "",
         "  // 融合后（真实输出）：1 个",
         "  %0 = mini.fused_matmul_bias_relu",
         "      %arg0, %arg1, %arg2",
         "      : tensor<2x3xf32>,",
         "        tensor<3x2xf32>,",
         "        tensor<2x2xf32>",
         "      -> tensor<2x2xf32>",
         "  return %0",
         "}"],
        ["rc=0，verify 通过", "数值验证（Python 版同图）：",
         "%r = [[22,0],[0,8]] ✓", "3 算子 → 1 算子，%m/%s 消失",
         "张量遍数 8 → 4（省 4 遍）"], GREEN)

    # 实验 E (keep)
    col(288, 212, "实验 E：--strategy=keep", ORANGE, ORANGE_BG,
        ["func @graph_multi_product(...) {",
         "  %0 = mini.matmul %arg0, %arg1",
         "  %1 = mini.fused_matmul_bias_relu",
         "      %arg0, %arg1, %arg2",
         "  %2 = mini.relu %0",
         "  return %1, %2",
         "}",
         "",
         "// 乘积 %m 有 2 个使用者：",
         "//   [keep] 保留 mini.matmul",
         "//   —— 整次 matmul 将重算",
         "",
         "// Python 版代价账本（同图）：",
         "matmul 执行 1→2 次",
         "FLOPs 36 → 60（亏 24）",
         "张量遍数 10 → 9（赚 1）"],
        ["rc=0，语义不变", "keep 在访存上小赢、计算上大亏",
         "K 大一个量级，matmul 就贵", "一个量级——合法 ≠ 有收益",
         "（收益判断留给 Day 74~75）"], ORANGE)

    # 实验 F (shared)
    col(520, 212, "实验 F：%s 被 return 共用", BLUE, BLUE_BG,
        ["func @graph_shared_result(...) {",
         "  // 融合前：matmul/add/relu",
         "  //   return %r, %s",
         "",
         "  // 融合后（真实输出）：",
         "  %0 = mini.fused_matmul_bias",
         "      %arg0, %arg1, %arg2",
         "      : ... -> tensor<2x2xf32>",
         "  %1 = mini.relu %0",
         "  return %1, %0",
         "}",
         "",
         "// Relu 没有被吸收！",
         "// %s 还有 return 这个使用者，",
         "//   它要 A·B+bias，不是 relu 后的值",
         "// return %0 = [[22,-23],[-7,8]] ✓"],
        ["rc=0，两个输出数值都对", "只做两算子融合，Relu 留守",
         "relu(fused_matmul_bias) 正是", "第 54 天「两阶段融合」的入口",
         "（对照：错吸收会让 return 拿到", " [[22,0],[0,8]] ——错误 4）"], BLUE)

    # 实验 H (rank1)
    col(752, 212, "实验 H：bias 是 [N] 向量", RED, RED_BG,
        ["%bias: tensor<2xf32>",
         "%s = mini.add %m, %bias",
         "      : tensor<2x2xf32>,",
         "        tensor<2xf32>",
         "      -> tensor<2x2xf32>",
         "",
         "// 连 Pattern 都没轮到，",
         "// 解析后的自动 verify 就拦下：",
         "",
         "error: 'mini.add' op rhs shape",
         "       对 lhs 需要广播——",
         "       第 40 天起故意不支持",
         "       （第 60 天放行）",
         "rc=1（解析/验证失败）",
         "",
         "// numpy 能按行广播算出",
         "   [[22,-23],[-17,18]]",
         "   ——「能算」≠「允许算」"],
        ["torch.nn.Linear 的经典 bias 写法", "语义合理、规则未到",
         "同族负例：错形 bias（实验 I）、", "融合算子结果写 2x3（实验 J）、",
         "融合算子带 [N]（实验 K）全部 rc=1"], RED)

    # 上游 linalg
    col(984, 196, "上游 linalg 对照", GRAY, SOFT,
        ["mlir-opt matmul_bias_relu_linalg.mlir",
         "  --convert-elementwise-to-linalg",
         "  --linalg-fuse-elementwise-ops",
         "",
         "// 输出（节选）：",
         "%1 = linalg.matmul",
         "     ins(%arg0, %arg1)",
         "     outs(%0) -> tensor<2x2xf32>",
         "%3 = linalg.generic {",
         "  ins(%1, %arg2 : ...)  {",
         "    %4 = arith.addf %in, %in_0",
         "    %5 = arith.maximumf",
         "        %4, %cst : f32",
         "    linalg.yield %5",
         "  }} -> tensor<2x2xf32>",
         "",
         "// matmul 没动；bias+relu 融成",
         "// 一个 generic，乘积 %1 仍落盘"],
        ["半程融合：逐元素部分到位，", "matmul 的 epilogue 融合要靠",
         "tile-and-fuse（第 94 天起）", "——我们的 fused_matmul_bias 是",
         "「先在 IR 层说清语义」的那一半"], GRAY)

    # 底部总结条
    s.rrect(56, 486, 1124, 96, fill=CARD, stroke=LINE, sw=2.2)
    s.text(618, 512, "全部 11 组 mini 实验 + 上游对照 rc 与期望一致（outputs/test-summary.txt）",
           size=11.4, bold=True, fill=INK)
    s.text(618, 534, "正例 7：A 三合一 / B 两算子 / C bias 在左 / D 拒绝恒等 / E keep / F Relu 留守 / G 双侧 matmul 拒绝",
           size=9.4, fill=GRAY)
    s.text(618, 552, "负例 4：H [N] bias / I 错形 bias / J 融合结果类型 / K 融合算子 [N] bias —— 全部 Verifier 拦截",
           size=9.4, fill=GRAY)
    s.text(618, 570, "Python 版另有 10 个类型/Shape 测试全绿（test_matmul_bias.py）",
           size=9.4, fill=GRAY)

    s.text(618, 620, "看图要点：融合的「正确」从来不是一种样子——A 是理想态，E 付了重算的钱，",
           size=11, fill=INK)
    s.text(618, 640, "F 保守地留下半融合，H 干脆不融合。共同点只有一个：语义都没变（数值验证说了算）。",
           size=11, fill=INK)
    s.text(618, 672, "（本图 IR 与 rc 均摘自 outputs/ 下 .out/.err 文件，数值来自 Python 版同图验证）",
           size=9, fill=GRAY)
    s.save("04-results.svg")


if __name__ == "__main__":
    img_overview()
    img_shape_types()
    img_pattern_flow()
    img_results()
