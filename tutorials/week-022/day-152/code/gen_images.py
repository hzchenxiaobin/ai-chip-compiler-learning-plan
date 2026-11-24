#!/usr/bin/env python3
"""第 152 天 3 张 SVG。种子 152。"""
from __future__ import annotations
import math, os, random
import xml.sax.saxutils as su
random.seed(152)
BG = "#FDFBF6"; BORDER = "#E7DFCE"; INK = "#3B3B3B"; MUTED = "#6b6257"
ORANGE = "#E8A87C"; BLUE = "#A9C4D4"; GREEN = "#9CBF8E"; RED = "#C97B7B"
PURPLE = "#B8A7CE"
FONT = "'Comic Sans MS','Kaiti SC','KaiTi','STKaiti',cursive"
W, H = 1080, 760
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "images")

def jit(m=1.6): return random.uniform(-m, m)
def hand_rect(x, y, w, h, fill=BG, opacity=0.65, stroke=INK, sw=1.4):
    pts = [(x + jit(), y + jit()), (x + w + jit(), y + jit()),
           (x + w + jit(), y + h + jit()), (x + jit(), y + h + jit())]
    d = f"M {pts[0][0]:.1f},{pts[0][1]:.1f} "
    for i in range(4):
        a, b = pts[i], pts[(i+1) % 4]
        mx, my = (a[0]+b[0])/2 + jit(2.2), (a[1]+b[1])/2 + jit(2.2)
        d += f"Q {mx:.1f},{my:.1f} {b[0]:.1f},{b[1]:.1f} "
    return (f'<path d="{d} Z" stroke="{stroke}" stroke-width="{sw}" '
            f'stroke-linecap="round" stroke-linejoin="round" '
            f'fill="{fill}" fill-opacity="{opacity}"/>')
def text(x, y, s, size=13, fill=INK, anchor="middle", bold=False, mono=False):
    s = su.escape(s)
    wt = ' font-weight="bold"' if bold else ""
    fam = "'Courier New',monospace" if mono else FONT
    return (f'<text x="{x}" y="{y}" font-family="{fam}" font-size="{size}" '
            f'fill="{fill}" text-anchor="{anchor}"{wt}>{s}</text>')
def svg_open(w=W, h=H):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
            f'viewBox="0 0 {w} {h}">'
            f'<rect x="4" y="4" width="{w-8}" height="{h-8}" rx="14" '
            f'fill="{BG}" stroke="{BORDER}" stroke-width="2"/>')
def save(name, body, w=W, h=H):
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
        f.write(svg_open(w, h) + body + "</svg>\n")
    print("生成", name)

def fig1():
    b = []
    b.append(text(W/2, 34, "跨 Shape 验证：O2 加速的分布（7 shape）", 16, bold=True))
    rows = [
        ("32×32×32", "0.13", "0.01", "9.8×", GREEN),
        ("64×64×64", "1.19", "0.13", "9.2×", GREEN),
        ("96×96×96", "9.49", "1.01", "9.4×", GREEN),
        ("128×128×128", "15.34", "1.27", "12.0×", GREEN),
        ("160×160×160", "33.81", "4.84", "7.0×", ORANGE),
        ("64×160×32", "2.30", "1.37", "1.7×", RED),
        ("32×32×160", "1.01", "0.07", "14.1×", GREEN),
    ]
    y = 60
    b.append(text(200, y, "shape", 11, bold=True))
    b.append(text(420, y, "O0 ms", 11, bold=True))
    b.append(text(560, y, "O2 ms", 11, bold=True))
    b.append(text(730, y, "加速", 11, bold=True))
    b.append(text(880, y, "判定", 11, bold=True))
    y += 18
    for shape, o0, o2, sp, color in rows:
        b.append(hand_rect(120, y, 840, 36, fill=color, opacity=0.3))
        b.append(text(200, y + 24, shape, 10.5, mono=True))
        b.append(text(420, y + 24, o0, 10.5, mono=True))
        b.append(text(560, y + 24, o2, 10.5, mono=True))
        b.append(text(730, y + 24, sp, 11.5, bold=True, mono=True))
        b.append(text(880, y + 24, "✓", 11, bold=True, fill="#4a7c59"))
        y += 42
    # 分布
    b.append(hand_rect(60, y + 8, 960, 70, fill="#F5E9C8", opacity=0.85))
    b.append(text(W/2, y + 34, "加速分布：最小 1.7×｜中位 9.4×｜最大 14.1×——三个数都要报", 12.5, bold=True))
    b.append(text(W/2, y + 58, "最差的 64×160×32（1.7×）：K=32 太小展开收益递减＋N=160 的 j 循环长——D125 反例的放大版", 10.5))
    save("01-distribution.svg", "".join(b), h=y + 90)

def fig2():
    b = []
    b.append(text(W/2, 34, "最差用例解剖：64×160×32 为什么只有 1.7×？", 16, bold=True))
    b.append(hand_rect(60, 60, 960, 220, fill=RED, opacity=0.2))
    b.append(text(W/2, 88, "三个因素的叠加", 13, bold=True))
    factors = [
        ("K=32 太小", "k 循环只有 32 圈——展开省的循环控制少\n（160³ 的 K=160 有 160 圈可省）", RED),
        ("N=160 的 j 循环长", "外层 j 循环 160 次每次进 k——O2 对外层\n的优化空间受 i/j 循环形态限制", ORANGE),
        ("M=64 中等", "整体计算量 0.65 MFLOP 小——固定开销占比高", BLUE),
    ]
    y = 110
    for name, body, color in factors:
        b.append(hand_rect(90, y, 900, 50, fill=color, opacity=0.3))
        b.append(text(180, y + 20, name, 11, bold=True))
        b.append(text(180, y + 38, body.split("\n")[0], 9.5))
        y += 56
    b.append(hand_rect(60, 300, 960, 70, fill="#F5E9C8", opacity=0.85))
    b.append(text(W/2, 326, "教训：优化的收益不是常数——它依赖 shape 的结构（K 的大小决定展开空间）", 12, bold=True))
    b.append(text(W/2, 350, "「平均 9.4×」掩盖了 1.7×~14.1× 的 8 倍离散——适用范围的申报（D153）因此必要", 10.5))
    save("02-worst.svg", "".join(b), h=390)

def fig3():
    b = []
    b.append(text(W/2, 34, "明天 D153：性能反例——完整的故事", 16, bold=True))
    # 已有的反例素材
    b.append(text(W/2, 60, "本周已积累的两个反例素材", 13.5, bold=True))
    cases = [
        ("tile 反例（D151）", "教学 tile 0.3×——重复计算（×6.25~100）\n吃掉复用收益\n方向对、实现不完整→更慢", RED),
        ("O2 的 shape 反例（今天）", "64×160×32 只 1.7×——K=32 太小\n展开收益递减\n同优化不同 shape→失效", ORANGE),
    ]
    for i, (name, body, color) in enumerate(cases):
        x = 60 + i * 480
        b.append(hand_rect(x, 80, 440, 140, fill=color, opacity=0.3))
        b.append(text(x + 220, 108, name, 12.5, bold=True))
        for j, line in enumerate(body.split("\n")):
            b.append(text(x + 220, 132 + j*22, line, 10))
    # 明天任务
    b.append(hand_rect(60, 240, 960, 120, fill="#F5E9C8", opacity=0.85))
    b.append(text(W/2, 266, "D153 的任务：反例的正式化", 12.5, bold=True))
    lines = [
        "① 选一个反例做完整解剖（现象→机制→适用条件）",
        "② D125 的 -O2 小 kernel 反例（4³ 慢 60%）也是候选——伏笔兑现",
        "③ 产出：性能反例＋适用条件说明——「什么时候不该用这个优化」的边界文档",
    ]
    for j, line in enumerate(lines):
        b.append(text(W/2, 292 + j*22, line, 10.5))
    b.append(hand_rect(60, 380, 960, 60, fill=PURPLE, opacity=0.25))
    b.append(text(W/2, 404, "反例的价值：它划清了优化的领土——没有反例的优化报告是广告，有反例的才是工程", 11.5, bold=True))
    b.append(text(W/2, 424, "（面试金句：「你做过的优化里，什么时候会失效？」——答得出反例才是真懂）", 10.5, MUTED))
    save("03-tomorrow.svg", "".join(b), h=450)

if __name__ == "__main__":
    fig1()
    fig2()
    fig3()
