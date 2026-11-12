#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第 50 天教程插图生成器：手绘 sketch 风（Excalidraw-like）SVG。

用法：  python3 code/make_images.py
输出：  images/01-overview.svg       融合周全局定位（技术信息图）
        images/02-semantics.svg      假融合 vs 真融合 + SSA 对照（技术信息图）
        images/03-rule-union.svg      Verifier 规则并集机制（技术信息图）
        images/04-verifier-tests.svg 15 个测试与错误复现实录（技术信息图）

图中所有数字（rc、报错文案、op 计数、CMake/ODS 错误）都来自本目录
outputs/test-summary.txt 与教程第 5/6 节的真实运行记录，无虚构。
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
# 图 1：融合周全局定位
# =====================================================================
def img_overview():
    s = SVG(1180, 880)
    header(s, "第 50 天（第 8 周开局）：定义融合算子——融合周的地基",
           "上：mini 算子家族编年史（今天 +2 个新算子）｜中：今天的产出住在 mini-opt 的哪一格｜下：融合周 6 天的分工")

    # ---------- ① 算子编年史 ----------
    s.text(60, 100, "① mini 方言算子编年史：每个新算子都是注册表里的普通公民", size=13,
           fill=INK, anchor="start", bold=True)
    ops = [
        (56, 122, 150, 92, CARD, LINE, "Day 37", "mini.matmul",
         ["Mini_F32Tensor2DPlus", "手写 Verifier（Day 39）"]),
        (224, 122, 158, 92, CARD, LINE, "Day 38", "add / relu / constant",
         ["constant 首次用属性", "装数据（Day 38）"]),
        (400, 122, 148, 92, CARD, LINE, "Day 42", "mini.mul",
         ["复盘新增，3 个文件", "搞定一个新算子"]),
        (564, 122, 168, 92, CARD, LINE, "Day 45~47", "Pattern ×3 + Fold",
         ["relu(relu)、x+(-0)、", "x*1、add 常量折叠"]),
        (748, 122, 372, 92, GREEN_BG, GREEN, "Day 50（今天）",
         "mini.fused_add_relu ＋ mini.fused_matmul_bias_relu",
         ["语义写进公式、零属性、Verifier 规则求并集", "——本教程主角"]),
    ]
    for x, y, w, h, f, st, d, t, lines in ops:
        s.rrect(x, y, w, h, fill=f, stroke=st, sw=2.2)
        s.text(x + w / 2, y + 22, d, size=8.6, fill=GRAY)
        s.text(x + w / 2, y + 44, t, size=10.4, bold=True)
        for i, ln in enumerate(lines):
            s.text(x + w / 2, y + 62 + i * 14, ln, size=7.8, fill=GRAY)
    s.line(206, 168, 224, 168, sw=1.4, amp=1)
    s.line(382, 168, 400, 168, sw=1.4, amp=1)
    s.line(548, 168, 564, 168, sw=1.4, amp=1)
    s.line(732, 168, 748, 168, sw=1.4, amp=1)

    # ---------- ② mini-opt 流水线定位 ----------
    s.text(60, 264, "② 今天动的是“验证”这一格：一个 Pattern 都没写", size=13,
           fill=INK, anchor="start", bold=True)
    pipe = [
        (56, 286, 130, 92, CARD, LINE, ".mlir 文本",
         ["fused_add_relu_ok", ".mlir 等测试文件"]),
        (206, 286, 150, 92, CARD, LINE, "解析 + ODS 约束",
         ["Mini_F32Tensor*", "Mini_F32ElementsAttr"]),
        (380, 286, 190, 92, ORANGE_BG, ORANGE, "verify()（今天的主场）",
         ["FusedAddReluVerifier.cpp", "FusedMatmulBiasReluVerifier.cpp", "规则求并集（图 3）"]),
        (594, 286, 150, 92, SOFT, LINE, "Pass 流水线",
         ["-cse / -canonicalize", "今天不碰（Day 51 起）"]),
        (766, 286, 150, 92, CARD, LINE, "round-trip 打印",
         ["0.5 → 5.000000e-01", "类型原样保留"]),
    ]
    for x, y, w, h, f, st, t, lines in pipe:
        s.rrect(x, y, w, h, fill=f, stroke=st, sw=2.2)
        s.text(x + w / 2, y + 24, t, size=10.6, bold=True,
               fill=ORANGE if f == ORANGE_BG else INK)
        for i, ln in enumerate(lines):
            s.text(x + w / 2, y + 46 + i * 15, ln, size=8.4, fill=GRAY)
    s.arrow(186, 332, 206, 332, sw=1.6)
    s.arrow(356, 332, 380, 332, sw=1.6)
    s.arrow(570, 332, 594, 332, sw=1.6)
    s.arrow(744, 332, 766, 332, sw=1.6)

    s.rrect(940, 286, 180, 92, fill=GREEN_BG, stroke=GREEN, sw=2.2)
    s.text(1030, 308, "今天验收（15/15）", size=10.4, fill=GREEN, bold=True)
    s.text(1030, 330, "7 正例 rc=0", size=9.2, fill=INK)
    s.text(1030, 347, "8 负例 rc=1", size=9.2, fill=INK)
    s.text(1030, 364, "run_tests.sh 一键回归", size=7.8, fill=GRAY)
    s.arrow(916, 332, 940, 332, sw=1.6)

    s.text(380, 404, "Verifier 的身份：只拦“能证明非法”的 IR；证明不了的（动态维 ?）保守放行，",
           size=9.6, fill=ORANGE, anchor="start")
    s.text(380, 420, "交给 Shape 推导或运行期——动态正例 ?x3·3x2→?x2 全部 rc=0。",
           size=9.6, fill=ORANGE, anchor="start")

    # ---------- ③ 融合周分工 ----------
    s.text(60, 464, "③ 融合周 6 天的分工：今天是地基，Pattern 从明天开始盖楼", size=13,
           fill=INK, anchor="start", bold=True)
    week = [
        (56, 486, 170, 150, GREEN, GREEN_BG, "Day 50 定义＋验证",
         ["融合成什么：公式、", "操作数、零属性", "", "Verifier：规则并集", "+ bias 增量", "", "产出：2 op、15 测试"], True),
        (244, 486, 170, 150, BLUE, BLUE_BG, "Day 51 Add＋Relu Pattern",
         ["RewritePattern 匹配", "链式结构，", "改写成 fused_add_relu", "", "今天定义的 op", "就是它的改写目标", "（右配方就位）"], False),
        (432, 486, 170, 150, CARD, LINE, "Day 52 多使用者",
         ["中间结果有多个", "使用者怎么办", "", "反例 + 融合边界", "说明", ""], False),
        (620, 486, 170, 150, CARD, LINE, "Day 53 MatMul＋Bias",
         ["两算子融合先走", "通，再处理可选", "Relu 组合", "", "bias 规则 5 今天", "已铺好路", ""], False),
        (808, 486, 170, 150, CARD, LINE, "Day 54 三算子融合",
         ["Pattern 优先级、", "重复匹配、稳定", "的最终融合形式", "", "", ""], False),
        (996, 486, 168, 150, CARD, LINE, "Day 55 负例验收",
         ["全部融合负例", "汇总：多使用者、", "Shape、类型、", "使用约束", "", ""], False),
    ]
    for x, y, w, h, c, cbg, t, lines, today in week:
        s.rrect(x, y, w, h, fill=cbg, stroke=c, sw=2.4 if today else 1.8)
        s.text(x + w / 2, y + 26, t, size=10, fill=c, bold=True)
        s.line(x + 16, y + 40, x + w - 16, y + 40, stroke=c, sw=1.1, amp=0.8)
        for i, ln in enumerate(lines):
            if ln:
                s.text(x + w / 2, y + 60 + i * 16, ln, size=8.6, fill=INK)
        if today:
            s.star(x + w - 18, y + 18, 11, GREEN)

    # ---------- ④ 底部主问题 ----------
    s.rrect(56, 676, 1108, 170, fill=CARD, stroke=LINE, sw=2.2)
    s.star(86, 710, 13, ORANGE)
    s.text(112, 706, "今天回答的核心问题：融合的第一步为什么不是写 Pattern，而是先定义算子？",
           size=11.5, bold=True, anchor="start")
    for i, ln in enumerate([
            "① 改写要有目标：Day 51 的 Pattern 是一条左边匹配 Add+Relu、右边生成本日算子的规则——右边这个 op 得先存在、",
            "    先有明确语义，Pattern 才有“写成什么样”的答案；",
            "② 改写要有人把关：融合后的 IR 是否合法，第一道防线就是今天这两个 Verifier——“融合不放松验证”不是口号，",
            "    是第 6 节错误 3 实测过的教训（漏一条规则，坏 IR 立刻 rc=0 溜进来）；",
            "③ 改写要有理由：fused_add_relu 的 description 写着“中间和不再成为 SSA 值”——这是 Day 72 算融合收益的伏笔。"]):
        s.text(112, 734 + i * 21, ln, size=9.8, fill=INK, anchor="start",
               bold=(i in (0, 2)))
    s.save("01-overview.svg")


# =====================================================================
# 图 2：假融合 vs 真融合 + SSA 对照
# =====================================================================
def img_semantics():
    s = SVG(1180, 800)
    header(s, "假融合 vs 真融合：语义要长在公式和类型里，不长在名字和字符串里",
           "左：只改名字的“假融合”（反例）｜右：今天的两个算子（公式、操作数、零属性）｜下：同一个计算的两种 SSA 形态")

    # ---------- 左：假融合 ----------
    s.rrect(56, 100, 460, 330, fill=RED_BG, stroke=RED, sw=2.4)
    s.text(286, 128, "✗ 假融合：一个 op 名字 ＋ kind 字符串属性", size=12.5,
           fill=RED, bold=True)
    s.rrect(88, 150, 396, 58, fill="#ffffff", stroke=RED, sw=1.6, r=8)
    s.text(96, 172, "%r = mini.fused %a, %b", size=9.6, fill=INK, anchor="start", bold=True)
    s.text(96, 190, '         {kind = "add_relu"} : ...', size=9.6, fill=INK, anchor="start")
    s.text(96, 212, '名字融合了，语义呢？藏在字符串 "add_relu" 里', size=8.8,
           fill=RED, anchor="start")
    for i, (t, d1, d2) in enumerate([
            ("Verifier 无从验证", "kind 是任意字符串：写 add_relu、addrelu 还是 AddReLU？",
             "Shape 规则没法挂在一个字符串值上，只能每个分支手写"),
            ("Lowering 变成解释器", "翻译到循环时要 switch(kind)：每加一种融合都要",
             "回到同一个 op 的 Lowering 里加分支——扩展点全堵死"),
            ("下游分析认不出它", "CSE / 收益分析拿到 op 只知道它叫 mini.fused，",
             "它等价于 Add+Relu 还是 MatMul+Bias？字符串说了不算")]):
        y = 236 + i * 62
        s.text(88, y, f"· {t}", size=9.8, fill=INK, anchor="start", bold=True)
        s.text(88, y + 16, d1, size=8.6, fill=GRAY, anchor="start")
        s.text(88, y + 32, d2, size=8.6, fill=GRAY, anchor="start")

    # ---------- 右：真融合 ----------
    s.rrect(546, 100, 618, 330, fill=GREEN_BG, stroke=GREEN, sw=2.4)
    s.text(855, 128, "✓ 真融合：公式 ＋ 操作数 ＋ 零属性", size=12.5,
           fill=GREEN, bold=True)

    s.rrect(576, 150, 276, 128, fill="#ffffff", stroke=GREEN, sw=2)
    s.text(714, 172, "mini.fused_add_relu", size=10.8, fill=GREEN, bold=True)
    s.text(714, 190, "res = relu(lhs + rhs)", size=9.6, fill=INK, bold=True)
    for i, ln in enumerate(["逐元素；中间和不再是 SSA 值", "操作数：lhs、rhs（ranked f32）",
                            "结果：res（ranked f32）", "属性：无（零个，一个都没有）"]):
        s.text(714, 210 + i * 16, ln, size=8.6, fill=GRAY)

    s.rrect(868, 150, 272, 128, fill="#ffffff", stroke=GREEN, sw=2)
    s.text(1004, 172, "mini.fused_matmul_bias_relu", size=9.8, fill=GREEN, bold=True)
    s.text(1004, 190, "res[m,n] = relu(", size=8.8, fill=INK, bold=True)
    s.text(1004, 204, "  sum_k lhs[m,k]*rhs[k,n] + bias[m,n])", size=8.8, fill=INK, bold=True)
    for i, ln in enumerate(["矩阵乘、加偏置、ReLU 一趟完成", "操作数：lhs、rhs、bias",
                            "乘积与带偏置的和都不落 SSA", "属性：无"]):
        s.text(1004, 224 + i * 14, ln, size=8.2, fill=GRAY)

    s.text(855, 306, "description 里写数学公式，不只换个名字——名称表达真实语义", size=9.4,
           fill=INK, bold=True)
    for i, ln in enumerate([
            "两个 op 是注册表里的普通公民：ODS 约束、verify()、round-trip 打印全都有；",
            "Day 51 的 Pattern 右边要生成本日算子时，不需要任何字符串约定——类型和公式就是契约；",
            "今天的 bias 特意用宽约束 Mini_F32Tensor（不限秩）：[N] 风格 bias 让它进 Verifier，",
            "    拿到“would broadcast ... see Day 60”的指引，而不是 ODS 一句干巴巴的 rank 报错。"]):
        s.text(576, 328 + i * 17, ln, size=9.2, fill=INK if i < 2 else GRAY, anchor="start")
    s.line(576, 320, 1140, 320, stroke=GREEN, sw=1.1, amp=0.8)

    # ---------- 下：SSA 对照 ----------
    s.text(60, 472, "同一个计算 res = relu(a + b) 的两种 SSA 形态：中间和的下落是融合的全部意义", size=12.5,
           fill=INK, anchor="start", bold=True)

    # 左：未融合
    s.rrect(56, 492, 470, 210, fill=CARD, stroke=LINE, sw=2.2)
    s.text(120, 516, "未融合：Add → Relu 两个 op", size=10.4, fill=INK, bold=True)
    nodes = [
        (76, 536, 96, 44, "a, b", "函数入参"),
        (200, 536, 118, 44, "s = add(a, b)", "中间和：SSA 值"),
        (350, 536, 96, 44, "r = relu(s)", "结果"),
    ]
    for x, y, w, h, t, sub in nodes:
        f, st = (ORANGE_BG, ORANGE) if t.startswith("s =") else (CARD, LINE)
        s.rrect(x, y, w, h, fill=f, stroke=st, sw=2.2)
        s.text(x + w / 2, y + h / 2 - 4, t, size=9.2, bold=True)
        s.text(x + w / 2, y + h / 2 + 13, sub, size=7.8, fill=GRAY)
    s.arrow(172, 558, 200, 558, sw=1.6)
    s.arrow(318, 558, 350, 558, sw=1.6)
    s.text(76, 620, "%s 活在 SSA 世界里：只要有一个使用者，它就必须存在；", size=9, fill=INK, anchor="start")
    s.text(76, 636, "将来 Lowering 到循环时，%s 是先写回内存再读出来的候选。", size=9, fill=INK, anchor="start")
    s.text(76, 656, "（第 51 天的 Pattern 消除的就是这个“中间节点”）", size=8.4, fill=GRAY, anchor="start")
    s.text(76, 676, "return %r", size=8, fill=GRAY, anchor="start")

    # 右：融合
    s.rrect(546, 492, 618, 210, fill=GREEN_BG, stroke=GREEN, sw=2.2)
    s.text(700, 516, "融合：fused_add_relu 一个 op", size=10.4, fill=GREEN, bold=True)
    s.rrect(576, 536, 160, 44, fill="#ffffff", stroke=GREEN, sw=2.2)
    s.text(656, 552, "r = fused_add_relu(a, b)", size=8.6, bold=True)
    s.text(656, 568, "公式：res = relu(a + b)", size=7.8, fill=GRAY)
    s.arrow(736, 522, 656, 536, stroke=GREEN, sw=1.4, ah=7)
    s.text(786, 560, "中间和呢？", size=9.4, fill=GREEN, bold=True, anchor="start")
    s.text(786, 578, "不存在。它不是 SSA 值，没有任何", size=8.6, fill=INK, anchor="start")
    s.text(786, 594, "使用者能引用它——语义上它只出现", size=8.6, fill=INK, anchor="start")
    s.text(786, 610, "在公式里。", size=8.6, fill=INK, anchor="start")
    for i, ln in enumerate([
            "→ 将来 Lowering 可以让中间和只活在寄存器/片上缓冲里，不落盘；",
            "→ 少一次中间张量的写回＋读回，正是融合收益的主要来源；",
            "→ 收益值多少钱？第 72 天用字节账本量化（今天先把语义钉死）。"]):
        s.text(786, 632 + i * 16, ln, size=8.8, fill=INK if i < 2 else GRAY, anchor="start")
    s.text(616, 656, "验证规则与 add 完全一致（图 3）：融合不是规则的化简，只是节点数的化简。",
           size=8.8, fill=GRAY, anchor="start")

    # 底部小结
    s.rrect(56, 724, 1108, 56, fill=CARD, stroke=LINE, sw=2)
    s.star(86, 752, 12, ORANGE)
    s.text(112, 748, "判断标准（计划原文的翻译）：一个融合算子必须“表达真实语义”——读它的公式就能推出等价的算子链，",
           size=10.2, fill=INK, anchor="start")
    s.text(112, 766, "而不需要读实现代码、更不需要读一个字符串属性的值。今天两个算子各一条公式，读者自查即可。", size=10.2,
           fill=INK, anchor="start")
    s.save("02-semantics.svg")


# =====================================================================
# 图 3：规则并集机制
# =====================================================================
def img_rule_union():
    s = SVG(1180, 840)
    header(s, "规则求并集：融合算子的 Verifier ＝ 成员规则并集 ＋ 自己的增量",
           "左：fused_add_relu = add 的两条（relu 零增量）｜右：fused_matmul_bias_relu = matmul 四条 + bias 第五条｜下：bias 三分类真实报错")

    # ---------- 左：fused_add_relu ----------
    s.rrect(56, 100, 500, 286, fill=BLUE_BG, stroke=BLUE, sw=2.4)
    s.text(306, 128, "mini.fused_add_relu：两条规则，全部继承", size=12, fill=BLUE, bold=True)
    rows = [
        ("规则 1", "lhs 与 rhs shape 完全一致", "= mini.add 规则 1（ShapeRelation.h）", False),
        ("规则 2", "res 与操作数 shape 完全一致", "= mini.add 规则 2", False),
        ("relu 的规则", "shape 恒等映射：零条新增", "并集 = add 的两条，一条不多一条不少", True),
    ]
    for i, (tag, txt, note, is_note) in enumerate(rows):
        y = 150 + i * 74
        s.rrect(80, y, 452, 60, fill="#ffffff" if not is_note else "#eef4fb",
                stroke=BLUE if not is_note else GRAY, sw=1.8, r=8)
        s.text(104, y + 24, tag, size=9.6, fill=BLUE if not is_note else GRAY, bold=True, anchor="start")
        s.text(104, y + 42, txt, size=9.2, fill=INK, anchor="start")
        s.text(330, y + 24, note, size=8.2, fill=GRAY, anchor="start")
    s.text(306, 306, "物理复用：verifyElementwiseOperands() ——与 mini.add 调用同一个函数，",
           size=8.8, fill=INK)
    s.text(306, 322, "不是抄一份。融合算子一旦少查一条，Day 51 改写前后的 IR 等价性就缺了基石。",
           size=8.8, fill=INK)
    s.text(306, 348, "hasVerifier = 1，不开 SameOperandsAndResultType trait（Day 40 的教训：",
           size=8.4, fill=GRAY)
    s.text(306, 364, "trait 分不清“永久不匹配”和“只差 broadcast”，还会误拒合法的 ?x3+2x3→2x3）", size=8.4, fill=GRAY)

    # ---------- 右：fused_matmul_bias_relu ----------
    s.rrect(584, 100, 580, 286, fill=ORANGE_BG, stroke=ORANGE, sw=2.4)
    s.text(874, 128, "mini.fused_matmul_bias_relu：4＋1 条规则", size=12, fill=ORANGE, bold=True)
    rules = [
        ("规则 1~4", "秩相等 / batch 对齐 / 内维匹配 / 结果 [M,N]", "＝ mini.matmul 全部，一行转发："),
        ("", "verifyMatmulShapes()（MatmulRules.h，今天新提取）", "MatmulVerifier.cpp 从此只是它的调用者"),
    ]
    s.rrect(608, 146, 532, 66, fill="#ffffff", stroke=ORANGE, sw=1.8, r=8)
    s.text(628, 168, "规则 1~4  ＝ mini.matmul 的全部", size=9.8, fill=ORANGE, bold=True, anchor="start")
    s.text(628, 186, "秩相等 / batch 对齐 / 内维匹配 / 结果 [M,N]", size=9, fill=INK, anchor="start")
    s.text(628, 204, "一行转发 verifyMatmulShapes()——共享头文件 MatmulRules.h 今天刚从", size=8.4, fill=GRAY, anchor="start")

    s.rrect(608, 224, 532, 82, fill="#ffffff", stroke=ORANGE, sw=1.8, r=8)
    s.text(628, 246, "规则 5（自己的增量）：bias shape ＝ 结果 shape", size=9.8, fill=ORANGE, bold=True, anchor="start")
    s.text(628, 264, "为什么不直接比 [M,N]？规则 4 刚查过 res = [M,N]，bias 对上 res", size=8.4, fill=GRAY, anchor="start")
    s.text(628, 280, "就等价于对上 [M,N]；顺序也自然：res 写错先报规则 4，res 对了才轮到", size=8.4, fill=GRAY, anchor="start")
    s.text(628, 296, "规则 5——每个坏 IR 只收到一条最有用的诊断。", size=8.4, fill=GRAY, anchor="start")

    s.text(874, 330, "口诀：成员规则的并集，叠加自己的增量；共享实现，不抄两份。", size=9.6, fill=INK, bold=True)
    s.text(874, 356, "将来 Day 60 支持广播、Day 61 改动态维：规则改一处，两个算子同步生效。",
           size=8.4, fill=GRAY)

    # ---------- 下：bias 三分类 ----------
    s.text(60, 428, "bias 三分类实验（真实运行，results 来自 outputs/test-summary.txt）", size=12.5,
           fill=INK, anchor="start", bold=True)
    cases = [
        (56, 450, 350, 108, GREEN, GREEN_BG, "bias = tensor<2x2xf32>（Same）",
         "%y = mini.fused_matmul_bias_relu %a, %b, %bias :",
         "  2x3 · 3x2 + 2x2 → 2x2  ✓  rc=0",
         "逐维相等——通过，round-trip 原样打印"),
        (424, 450, 350, 108, ORANGE, ORANGE_BG, "bias = tensor<2xf32>（BroadcastOnly）",
         "error: ... requires bias to have exactly",
         "  the result shape: bias is 'tensor<2xf32>',",
         "  result is 'tensor<2x2xf32>', which would broadcast; ... (see Day 60)"),
        (792, 450, 372, 108, RED, RED_BG, "bias = tensor<3x2xf32>（Mismatch）",
         "error: ... requires bias to have exactly",
         "  the result shape: bias is 'tensor<3x2xf32>',",
         "  but result is 'tensor<2x2xf32>', which do not match ..."),
    ]
    for x, y, w, h, c, cbg, t, l1, l2, l3 in cases:
        s.rrect(x, y, w, h, fill=cbg, stroke=c, sw=2.2)
        s.text(x + w / 2, y + 22, t, size=10.2, fill=c, bold=True)
        s.text(x + 18, y + 44, l1, size=7.8, fill=INK, anchor="start")
        s.text(x + 18, y + 58, l2, size=7.8, fill=INK, anchor="start")
        s.text(x + 18, y + 72, l3, size=7.8, fill=INK, anchor="start")
        s.text(x + w / 2, y + 94, {"bias = tensor<2x2xf32>（Same）": "合法语义，今天通过",
                                   "bias = tensor<2xf32>（BroadcastOnly）": "合法语义，今天不支持，Day 60 放开",
                                   "bias = tensor<3x2xf32>（Mismatch）": "永久非法，谁也救不了"}[t],
               size=8.6, fill=GRAY)

    # ---------- 分类器 + 底部结论 ----------
    s.rrect(56, 586, 640, 120, fill=CARD, stroke=LINE, sw=2.2)
    s.text(376, 610, "classifyShapePair(bias, res) 三分类（ShapeRelation.h，Day 40 原件）", size=10.6, bold=True)
    for i, ln in enumerate([
            "从右往左逐维对齐；秩小的一方缺位补 1；动态维 ? 视为“无法反驳”，跳过；",
            "出现“维为 1”或缺位 → BroadcastOnly；双方静态且不等且无 1 → Mismatch；",
            "Day 60 的升级路径：验收政策从“只收 Same”放宽为“收 Same 和 BroadcastOnly”，",
            "    报错骨架与右对齐比较逻辑原样复用——三分类就是为那天留的接缝。"]):
        s.text(376, 632 + i * 18, ln, size=9, fill=INK if i < 2 else GRAY)

    s.rrect(716, 586, 448, 120, fill=RED_BG, stroke=RED, sw=2.2)
    s.text(940, 610, "反面教材（第 6 节错误 3 实测）", size=10.6, fill=RED, bold=True)
    for i, ln in enumerate([
            "把规则 5 注释掉再构建：bias 3x2 和 2xf32 的测试全部 rc=0——",
            "坏 IR 大摇大摆通过验证。融合放松验证的代价不是报错难看，",
            "是根本不报错；Day 51 的 Pattern 若把这种 op 写进图里，",
            "错误要拖到执行期才爆炸。回归测试 + 规则并集，一个都不能少。"]):
        s.text(940, 632 + i * 17, ln, size=8.8, fill=INK)

    s.rrect(56, 736, 1108, 76, fill=CARD, stroke=LINE, sw=2)
    s.star(86, 774, 13, GREEN)
    s.text(112, 762, "读图要点：两个 Verifier 的全部规则都能在成员算子的 Verifier 里找到出处（add 两条 / matmul 四条），",
           size=10.2, fill=INK, anchor="start")
    s.text(112, 782, "唯一的新规则是 bias 的第五条——融合可以增加算子，但绝不发明新语义、绝不放松旧约束。",
           size=10.2, fill=INK, anchor="start")
    s.save("03-rule-union.svg")


# =====================================================================
# 图 4：测试实录与错误复现
# =====================================================================
def img_tests():
    s = SVG(1180, 880)
    header(s, "实测实录：15 个 IR 测试全通过 ＋ 3 个错误复现",
           "数据全部来自本机真实运行（outputs/test-summary.txt 与第 6 节复现实验）；环境：MLIR 18.1.8 / GCC 9.4 / aarch64 Linux")

    # ---------- 左：正例 ----------
    s.text(60, 100, "① 正例 7 个（rc=0，round-trip 原样通过）", size=12, fill=INK,
           anchor="start", bold=True)
    pos = [
        ("fused_add_relu_ok", "2x2 + 2x2 → 2x2"),
        ("fused_add_relu_dynamic_ok", "?x3 + 2x3 → 2x3（动态维放行）"),
        ("fused_matmul_bias_relu_ok", "2x3·3x2 + 2x2 → 2x2（旗舰例）"),
        ("fused_matmul_bias_relu_ok_batched", "2x2x3·2x3x2 + 2x2x2（batch 维走规则 2）"),
        ("fused_matmul_bias_relu_dynamic_ok", "?x3·3x2 + ?x2 → ?x2"),
        ("target_graph_unfused", "回归：MatMul→Add→Relu 原样通过"),
        ("integration_chain", "融合算子与老算子同图共处"),
    ]
    for i, (f, note) in enumerate(pos):
        y = 118 + i * 30
        s.rrect(56, y, 520, 26, fill=CARD if i % 2 else "#f8f5ec", stroke=LINE, sw=1.4, r=6)
        s.text(68, y + 17, f, size=8.8, anchor="start")
        s.text(330, y + 17, note, size=8.2, fill=GRAY, anchor="start")
        s.text(560, y + 17, "rc=0", size=8.8, fill=GREEN, bold=True, anchor="start")

    # ---------- 右：负例 ----------
    s.text(630, 100, "② 负例 8 个（rc=1，每条违反的规则都有专属诊断）", size=12, fill=INK,
           anchor="start", bold=True)
    neg = [
        ("fused_add_relu_mismatch", "add 规则 1", "2x2 vs 2x3：Mismatch"),
        ("fused_add_relu_broadcast", "add 规则 1", "2x2 vs 1x2：BroadcastOnly → Day 60"),
        ("fused_add_relu_bad_result", "add 规则 2", "结果写成 3x3"),
        ("fused_matmul_bias_relu_inner_dim", "matmul 规则 3", "2x3·2x2：内维 3≠2"),
        ("fused_matmul_bias_relu_bad_result", "matmul 规则 4", "期望 [2,2] 实得 3x3"),
        ("fused_matmul_bias_relu_bias_mismatch", "规则 5（bias）", "bias 3x2 vs 结果 2x2"),
        ("fused_matmul_bias_relu_bias_broadcast", "规则 5（bias）", "bias 2xf32：[N] 风格 → Day 60"),
        ("fused_matmul_bias_relu_dynamic_bad_inner", "matmul 规则 3", "?x3·4x2：静态铁证 3≠4"),
    ]
    for i, (f, rule, note) in enumerate(neg):
        y = 118 + i * 30
        s.rrect(626, y, 520, 26, fill=CARD if i % 2 else "#f8f5ec", stroke=LINE, sw=1.4, r=6)
        s.text(638, y + 17, f, size=8.4, anchor="start")
        s.text(850, y + 17, rule, size=8.2, fill=ORANGE, anchor="start", bold=True)
        s.text(960, y + 17, note, size=8.0, fill=GRAY, anchor="start")
        s.text(1130, y + 17, "rc=1", size=8.8, fill=RED, bold=True, anchor="start")

    # ---------- ③ op 计数 ----------
    s.text(60, 388, "③ op 计数实验：同一个计算，融合形态少两个数据算子（mini-count-ops 实测）", size=12,
           fill=INK, anchor="start", bold=True)
    s.rrect(56, 406, 540, 118, fill=CARD, stroke=LINE, sw=2.2)
    s.text(96, 430, "未融合（target_graph_unfused）", size=9.6, bold=True, anchor="start")
    s.text(96, 450, "6 ops = func.func 1 + func.return 1", size=8.6, fill=INK, anchor="start")
    s.text(96, 466, "         + matmul 1 + constant 1 + add 1 + relu 1", size=8.6, fill=INK, anchor="start")
    s.text(96, 488, "数据算子 4 个；中间结果 %mm（2x2）与 %s（2x2）都是 SSA 值", size=8.2, fill=GRAY, anchor="start")
    s.text(96, 508, "round-trip rc=0：今天没有 Pattern，图原样通过（回归测试）", size=8.2, fill=GRAY, anchor="start")

    s.arrow(596, 465, 626, 465, stroke=GREEN, sw=2.4, ah=10)

    s.rrect(626, 406, 540, 118, fill=GREEN_BG, stroke=GREEN, sw=2.2)
    s.text(666, 430, "手写融合（fused_matmul_bias_relu_ok）", size=9.6, bold=True, anchor="start")
    s.text(666, 450, "4 ops = func.func 1 + func.return 1", size=8.6, fill=INK, anchor="start")
    s.text(666, 466, "         + constant 1 + fused_matmul_bias_relu 1", size=8.6, fill=INK, anchor="start")
    s.text(666, 488, "数据算子 2 个；乘积与带偏置的和不再是 SSA 值", size=8.2, fill=GRAY, anchor="start")
    s.text(666, 508, "Day 51 的 Pattern 要自动完成的正是这个改写（不含 bias，分两步走）", size=8.2, fill=GRAY, anchor="start")

    # ---------- ④ 三个错误复现 ----------
    s.text(60, 556, "④ 三个真实错误复现（第 6 节，都在本机跑过）", size=12, fill=INK,
           anchor="start", bold=True)
    errs = [
        (56, 576, 360, 150, RED, RED_BG, "错误 1：新 Verifier 忘记登记",
         ["现象：cmake 直接配置失败",
          "CMake Error at LLVMProcessSources.cmake:",
          "  Found erroneous configuration for",
          "  source file FusedAddReluVerifier.cpp",
          "原因：LLVM 构建系统强制“目录里的",
          "  源文件必须都属于某个 target”；",
          "修复：lib/CMakeLists.txt 的 MLIRMini",
          "  列表里加回这一行，重新 cmake"]),
        (436, 576, 360, 150, RED, RED_BG, "错误 2：bias 在 ODS 层用窄约束",
         ["现象：rank-1 bias 被干巴巴拦下",
          "error: operand #2 must be ranked f32",
          "  tensor with rank >= 2 ... but got",
          "  'tensor<2xf32>'",
          "原因：把 bias 也写成 2DPlus，报错只剩",
          "  “秩不够”，丢失 Day 60 指引；",
          "修复：bias 用宽约束 Mini_F32Tensor，",
          "  交给规则 5 出高质量诊断"]),
        (816, 576, 408, 150, RED, RED_BG, "错误 3：Verifier 漏掉规则 5",
         ["现象：bias 3x2 / 2xf32 的坏 IR 全部 rc=0！",
          "  融合放松了验证，Verifier 变成摆设；",
          "原因：只转发 verifyMatmulShapes()，忘了 bias 是",
          "  fused 独有的操作数，成员算子的并集不含它——",
          "  并集覆盖的是“成员共有的部分”，增量必须自己补；",
          "修复：恢复规则 5，两个 bias 负例立刻回到 rc=1。"]),
    ]
    for x, y, w, h, c, cbg, t, lines in errs:
        s.rrect(x, y, w, h, fill=cbg, stroke=c, sw=2.2)
        s.text(x + w / 2, y + 24, t, size=10.4, fill=c, bold=True)
        for i, ln in enumerate(lines):
            s.text(x + 20, y + 46 + i * 15, ln, size=8.2, fill=INK, anchor="start")

    # ---------- 底部结论 ----------
    s.rrect(56, 756, 1168, 92, fill=CARD, stroke=LINE, sw=2.2)
    s.star(86, 800, 13, GREEN)
    for i, ln in enumerate([
            "验收口径：7 正例 + 8 负例 + 1 张老图回归 = 15/15 全通过（bash run_tests.sh 一键复跑）；",
            "每个负例的报错都能指出违反的规则编号——Verifier 的价值不在“拦住了”，而在“告诉你错在哪、该怎么办”；",
            "错误 3 的教训是今天的主线：融合算子可以比成员算子多查规则（bias），但绝不能少查规则。"]):
        s.text(112, 780 + i * 20, ln, size=9.8, fill=INK, anchor="start", bold=(i == 2))
    s.save("04-verifier-tests.svg")


if __name__ == "__main__":
    img_overview()
    img_semantics()
    img_rule_union()
    img_tests()
