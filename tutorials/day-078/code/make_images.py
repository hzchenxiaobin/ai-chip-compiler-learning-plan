#!/usr/bin/env python3
"""生成第 78 天教程的 4 张手绘风（Excalidraw-like）SVG 技术图。

运行方式：
    python3 make_images.py

输出到 ../images/ 目录：
    01-overview.svg  今天在整个学习链路中的位置
    02-formats.svg   FP32 / FP16 / BF16 位布局
    03-rounding.svg  对阶舍入：小数怎么被吃掉
    04-results.svg   真实实验的相对误差对照（log 刻度）
"""

import math
import random
from pathlib import Path

random.seed(78)

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
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d">'
            % (w, h, w, h)
            + f'<rect x="3" y="3" width="{w - 6}" height="{h - 6}" rx="7" fill="{BG}"/>'
            + f'<g font-family="{FONT}">' + body + "</g></svg>")


# ---------------------------------------------------------------------------
# 图 1：全局定位
# ---------------------------------------------------------------------------

def fig1():
    b = []
    b.append(text(55, 56, "第 78 天：浮点表示与累加误差", 27))
    b.append(text(55, 84, "—— 从「算子对不对」走到「数值差多少」的一站", 16, SOFT, rot=-0.4))

    b.append(text(55, 118, "算子工程主线", 13, SOFT))
    chain = [
        ("37~47 天", "算子：语义正确"),
        ("48~72 天", "融合：变得更快"),
        ("73~80 天", "数值：也要对"),
        ("81 天起", "算子验证进阶"),
    ]
    xs = [50, 270, 490, 710]
    for i, ((cap, main), x) in enumerate(zip(chain, xs)):
        hot = i == 2
        b.append(srect(x, 128, 160, 62,
                       L_ORANGE if hot else "none",
                       ORANGE if hot else INK, 3.0 if hot else 2.2))
        b.append(text(x + 80, 152, cap, 13, SOFT, "middle"))
        b.append(text(x + 80, 176, main, 16, INK, "middle"))
    for x in (215, 435, 655):
        b.append(arrow(x, 159, x + 50, 159))

    b.append(arrow(570, 194, 486, 292, SOFT, 2.0, dash="6 5"))

    week = [
        ("Day 77 · 复盘", "融合合法 / 融合正确 / 融合更快", None),
        ("Day 78 · 今天", "浮点格式 + 累加顺序", "换个求和顺序，结果就变？"),
        ("Day 79 · 明天", "参考实现 + 误差指标（ULP）", None),
    ]
    wxs = [60, 350, 640]
    for i, (t1, t2, t3) in enumerate(week):
        x = wxs[i]
        hot = i == 1
        b.append(srect(x, 296, 250, 104,
                       L_ORANGE if hot else "none",
                       ORANGE if hot else INK, 3.0 if hot else 2.2))
        b.append(text(x + 125, 326, t1, 18 if hot else 16, INK, "middle"))
        b.append(text(x + 125, 352, t2, 13.5, INK, "middle"))
        if t3:
            b.append(text(x + 125, 378, t3, 13, RED, "middle"))
    b.append(arrow(312, 348, 346, 348))
    b.append(arrow(602, 348, 636, 348))

    b.append(text(55, 452, "今天的主线（4 步）", 13, SOFT))
    steps = [
        ("① 位怎么分", "S / E / M 三段"),
        ("② 舍入", "小数怎么被吃掉"),
        ("③ 顺序", "和为什么会停住"),
        ("④ 实验", "误差到底多大"),
    ]
    sxs = [55, 275, 495, 715]
    for (t1, t2), x in zip(steps, sxs):
        b.append(srect(x, 462, 180, 58, "none", BLUE, 2.2))
        b.append(text(x + 90, 486, t1, 15.5, INK, "middle"))
        b.append(text(x + 90, 508, t2, 12.5, SOFT, "middle"))
    for x in (238, 458, 678):
        b.append(arrow(x, 491, x + 34, 491))

    b.append(text(55, 585, "贯穿问题：同一个求和，NPU 结果和 CPU golden 对不上——", 15.5, RED, rot=-0.5))
    b.append(text(55, 611, "是算子写错了，还是浮点本来就这样？今天给出判据。", 15.5, RED, rot=-0.5))
    return svg_doc(900, 640, "".join(b))


# ---------------------------------------------------------------------------
# 图 2：三种格式的位布局
# ---------------------------------------------------------------------------

def bit_row(b, gy, name, n_e, n_m, note, note_color):
    cw, step, ch = 20, 23, 34
    x0 = 130
    b.append(text(52, gy + 24, name, 20))
    cells = [("S", 1, L_RED), ("E", n_e, L_BLUE), ("M", n_m, L_ORANGE)]
    x = x0
    spans = []
    for label, n, fill in cells:
        sx = x
        for _ in range(n):
            b.append(srect(x, gy, cw, ch, fill, INK, 1.6, amp=0.8))
            x += step
        spans.append((label, sx, x - step + cw))
    for label, sx, ex in spans:
        cx = (sx + ex) / 2
        cnt = {"S": 1, "E": n_e, "M": n_m}[label]
        b.append(text(cx, gy + ch + 20, f"{label} x {cnt}", 13, SOFT, "middle"))
    b.append(text(x0, gy + ch + 44, note, 15, note_color))
    return x0 + 31 * step


def fig2():
    b = []
    b.append(text(55, 52, "三种 AI 格式：位是怎么分配的", 26))
    b.append(text(55, 80, "一个浮点数 = 符号 x 尾数 x 2^指数；指数位管范围，尾数位管精度", 15, SOFT))

    legend = [(L_RED, "符号位 S"), (L_BLUE, "指数位 E · 管范围"), (L_ORANGE, "尾数位 M · 管精度")]
    lx = 330
    for fill, lab in legend:
        b.append(srect(lx, 98, 16, 16, fill, INK, 1.5, amp=0.6))
        b.append(text(lx + 24, 111, lab, 14))
        lx += 24 + len(lab) * 15 + 26

    end32 = bit_row(b, 140, "FP32", 8, 23,
                    "32 位 ｜ 范围 ±3.4e38 ｜ 十进制有效数字约 7 位", INK)
    bit_row(b, 258, "FP16", 5, 10,
            "16 位 ｜ 范围只有 ±65504 ｜ 约 3 位 —— 大梯度 / 大 loss 会上溢", RED)
    endbf = bit_row(b, 376, "BF16", 8, 7,
                    "16 位 ｜ 范围 ±3.4e38（与 FP32 相同！）｜ 约 2~3 位", BLUE)

    cut_x = 130 + 16 * 23
    b.append(srect(cut_x, 136, end32 - cut_x + 4, 42, "none", RED, 2.0, dash="7 6"))
    b.append(text((cut_x + end32) / 2, 128, "这 16 位尾数被砍掉", 14, RED, "middle"))
    b.append(carrow((cut_x + 130, 184), (cut_x + 215, 280), (endbf + 30, 372), RED, 2.2))
    b.append(text(endbf + 150, 330, "BF16 = FP32 的前 16 位", 14, RED, "middle", rot=8))

    b.append(srect(60, 478, 840, 58, L_GREEN, GREEN, 2.4))
    b.append(text(75, 503, "尾数位数 → 精度：FP32 约 7 位十进制，FP16 约 3 位，BF16 约 2~3 位", 15.5))
    b.append(text(75, 526, "指数位数 → 范围：BF16 与 FP32 同为 8 位（范围一样大），FP16 只有 5 位", 15.5))
    return svg_doc(960, 560, "".join(b))


# ---------------------------------------------------------------------------
# 图 3：对阶与舍入
# ---------------------------------------------------------------------------

def fig3():
    b = []
    b.append(text(55, 50, "为什么换个顺序结果就不同：对阶与舍入", 25))
    b.append(text(55, 78, "浮点加法 = 先把两数对齐指数，再相加尾数；尾数窗口只有 23 位，排不下的部分被舍入", 14.5, SOFT))

    b.append(srect(270, 94, 420, 46, L_ORANGE, ORANGE, 2.2))
    b.append(text(480, 123, "同一组数：[ 1e8, +1.0, -1e8 ]　数学真值 = 1.0", 16, INK, "middle"))

    b.append(text(55, 190, "顺序 ①　(1e8 + 1.0) + (-1e8)", 15.5))
    boxes1 = [(60, 150, "1e8 + 1.0", INK, "none", None, None),
              (250, 190, "→ 1e8", RED, L_RED, "1.0 比半个间距还小，被舍掉", None),
              (470, 140, "+ (-1e8)", INK, "none", None, None),
              (640, 130, "= 0.0", RED, L_RED, "错 100%", None)]
    for x, w, t, c, fill, sub, _ in boxes1:
        b.append(srect(x, 200, w, 46, fill, c if fill != "none" else INK, 2.2))
        b.append(text(x + w / 2, 222, t, 16, c, "middle"))
        if sub:
            b.append(text(x + w / 2, 240, sub, 11.5, SOFT, "middle"))
    for x1, x2 in ((213, 247), (443, 466), (613, 636)):
        b.append(arrow(x1, 223, x2, 223))

    b.append(text(55, 300, "顺序 ②　(1e8 + (-1e8)) + 1.0", 15.5))
    boxes2 = [(60, 150, "1e8 + (-1e8)", INK, "none", None),
              (250, 190, "= 0.0", GREEN, L_GREEN, "大数先抵消，尾数没被浪费"),
              (470, 140, "+ 1.0", INK, "none", None),
              (640, 130, "= 1.0 ✓", GREEN, L_GREEN, None)]
    for x, w, t, c, fill, sub in boxes2:
        b.append(srect(x, 310, w, 46, fill, c if fill != "none" else INK, 2.2))
        b.append(text(x + w / 2, 332, t, 16, c, "middle"))
        if sub:
            b.append(text(x + w / 2, 350, sub, 11.5, SOFT, "middle"))
    for x1, x2 in ((213, 247), (443, 466), (613, 636)):
        b.append(arrow(x1, 333, x2, 333))

    b.append(text(55, 412, "同一把「浮点尺」，不同区间刻度密度不同：", 15.5, INK))
    b.append(sline(80, 448, 380, 448, BLUE, 2.2) + head(380, 448, 0, BLUE, 2.2))
    for i in range(9):
        x = 80 + i * 37.5
        b.append(sline(x, 442, x, 454, BLUE, 2.0, amp=0.6))
        if i % 2 == 0:
            b.append(text(x, 470, str(i), 12, SOFT, "middle"))
    b.append(text(400, 442, "在 1 附近：相邻两数相差约 1.2e-7", 13.5, BLUE))

    b.append(sline(80, 540, 880, 540, ORANGE, 2.4) + head(880, 540, 0, ORANGE, 2.4))
    labels = ["999999984", "999999992", "100000000", "100000008", "100000016"]
    for i, lab in enumerate(labels):
        x = 80 + i * 160
        b.append(sline(x, 533, x, 547, ORANGE, 2.2, amp=0.7))
        b.append(text(x, 566, lab, 13, SOFT, "middle"))
    b.append(text(400, 590, "在 1e8 附近：相邻两数相差 8（np.spacing(1e8) = 8）", 13.5, ORANGE))

    b.append(f'<circle cx="560" cy="527" r="8" fill="{L_ORANGE}" stroke="{ORANGE}" stroke-width="2"/>')
    bx = 560 + 20
    b.append(sline(bx - 5, 520, bx + 5, 530, RED, 2.4, amp=0.5))
    b.append(sline(bx - 5, 530, bx + 5, 520, RED, 2.4, amp=0.5))
    b.append(text(bx + 12, 516, "100000001（想得到的和）", 13, RED))
    b.append(carrow((bx, 516), (bx - 8, 494), (568, 512), RED, 2.0))
    b.append(text(700, 500, "最近的可表示数还是 1e8 → 舍回去", 13, RED, "middle"))

    b.append(text(55, 622, "尺子越往大数走刻度越稀：累加和越大，小增量越容易被舍掉；顺序决定谁先加、谁被吃。", 15.5, INK))
    return svg_doc(960, 648, "".join(b))


# ---------------------------------------------------------------------------
# 图 4：真实实验结果对照
# ---------------------------------------------------------------------------

def fig4():
    b = []
    b.append(text(55, 48, "真实实验：不同求法 / 累加器的相对误差（log 刻度）", 24))
    b.append(text(55, 76, "环境 Python 3.11 + numpy 1.26.4；数据 0.1 x 100000 与 [1e8, 0.1 x 10万, -1e8]；误差相对精确和", 13.5, SOFT))

    x0, x1 = 300, 920
    W = x1 - x0

    def px(err_log):
        return x0 + (err_log + 5) / 5 * W

    for tick in range(-5, 1):
        x = px(tick)
        b.append(sline(x, 128, x, 560, SOFT, 1.1, dash="4 5", amp=0.5))
        lab = "100%" if tick == 0 else f"1e{tick}"
        b.append(text(x, 582, lab, 13.5, SOFT, "middle"))
    b.append(text(120, 582, "相对误差：越靠右越糟 →", 13.5, SOFT))

    groups = [
        ("实验 B · FP32 混合量级求和", BLUE, L_BLUE, 150, [
            ("顺序左结合", 0.0, "100%（和 = 0，全被吃掉）", True),
            ("升序排序后再顺序", 0.0, "100%（和 = 0，排序救不了）", True),
            ("np.sum 分块两两", math.log10(4.0e-3), "0.40%", False),
            ("math.fsum 精确和", -5.0, "≈ 0", False),
        ]),
        ("实验 D · FP16 输入 0.1 x 100000", ORANGE, L_ORANGE, 292, [
            ("FP16 累加器", math.log10(0.9744), "97.4%（和停在 256）", True),
            ("FP32 累加器", math.log10(1.59e-4), "0.016%", False),
        ]),
        ("实验 E · BF16 输入 0.1 x 100000", GREEN, L_GREEN, 404, [
            ("BF16 累加器", math.log10(0.9968), "99.7%（和停在 32）", True),
            ("FP32 累加器", math.log10(8.98e-5), "0.0090%", False),
        ]),
    ]
    for title, color, fill, gy, bars in groups:
        b.append(text(x0, gy, title, 15.5, color))
        for i, (name, elog, vlabel, inside) in enumerate(bars):
            y = gy + 16 + i * 27
            w = max(6.0, px(elog) - x0)
            b.append(srect(x0, y, w, 19, fill, color, 2.0, amp=0.8))
            b.append(text(x0 - 10, y + 15, name, 14, INK, "end"))
            if inside:
                b.append(text(x0 + w - 8, y + 15, vlabel, 13, INK, "end"))
            else:
                b.append(text(x0 + w + 10, y + 15, vlabel, 13, RED if w < 60 else INK))

    b.append(srect(60, 486, 840, 74, L_ORANGE, ORANGE, 2.4))
    b.append(text(75, 512, "同一份数据：输入用 FP16 / BF16 带来的量化误差只有 1e-4 量级，", 16))
    b.append(text(75, 534, "累加器选错却能错到接近 100%——两者差 4~5 个数量级。", 16))
    b.append(text(75, 554, "这就是 AI 芯片乘加单元用 FP32 累加器的原因。", 14, SOFT))
    return svg_doc(960, 606, "".join(b))


# ---------------------------------------------------------------------------

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    figs = {
        "01-overview.svg": fig1(),
        "02-formats.svg": fig2(),
        "03-rounding.svg": fig3(),
        "04-results.svg": fig4(),
    }
    for name, content in figs.items():
        path = OUT / name
        path.write_text(content, encoding="utf-8")
        print(f"写入 {path}（{path.stat().st_size} 字节）")


if __name__ == "__main__":
    main()
