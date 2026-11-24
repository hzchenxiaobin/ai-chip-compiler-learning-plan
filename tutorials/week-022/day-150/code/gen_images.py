#!/usr/bin/env python3
"""第 150 天 3 张 SVG。种子 150。"""
from __future__ import annotations
import math, os, random
import xml.sax.saxutils as su
random.seed(150)
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
    b.append(text(W/2, 34, "Roofline：实测 0.39GF 离两个屋顶都远——执行效率瓶颈", 15, bold=True))
    # 理论量
    cards = [
        ("计算量", "2×160³ = 8.2 MFLOP", GREEN),
        ("访存量", "最坏 61.4MB｜cache 25.6MB", BLUE),
        ("算术强度 AI", "最坏 0.13｜cache 0.32\nFLOP/Byte", ORANGE),
        ("拐点 AI*", "50GF/50GB = 1.0\nFLOP/Byte", PURPLE),
    ]
    for i, (name, val, color) in enumerate(cards):
        x = 60 + i * 245
        b.append(hand_rect(x, 60, 225, 120, fill=color, opacity=0.35))
        b.append(text(x + 112, 88, name, 12.5, bold=True))
        for j, line in enumerate(val.split("\n")):
            b.append(text(x + 112, 112 + j*20, line, 10.5))
    # 对照
    b.append(text(W/2, 216, "实测与屋顶的对照", 13.5, bold=True))
    rows = [
        ("实测（D148 基线）", "0.392 GFLOP/s", "——", RED),
        ("计算屋顶", "50 GFLOP/s", "差距 128×", BLUE),
        ("访存屋顶（最坏 AI）", "12.4 GFLOP/s", "差距 32×", ORANGE),
        ("访存屋顶（cache AI）", "12.3 GFLOP/s", "差距 31×", PURPLE),
    ]
    y = 238
    for name, val, dist, color in rows:
        b.append(hand_rect(120, y, 840, 44, fill=color, opacity=0.28))
        b.append(text(330, y + 28, name, 11.5, bold=True))
        b.append(text(620, y + 28, val, 11.5, mono=True))
        b.append(text(860, y + 28, dist, 10.5, fill=RED if "差距" in dist else INK))
        y += 50
    # 判定
    b.append(hand_rect(60, y + 8, 960, 76, fill="#F5E9C8", opacity=0.85))
    b.append(text(W/2, y + 32, "瓶颈判定：两个屋顶都远（128× 与 32×）——不是「计算 vs 访存」二选一，", 12, bold=True))
    b.append(text(W/2, y + 54, "而是「执行效率」：循环控制/地址计算/依赖链的指令开销吞掉性能——每个乘加只用了 ~0.4GF 的有效算力", 10.5))
    save("01-roofline.svg", "".join(b), h=y + 100)

def fig2():
    b = []
    b.append(text(W/2, 34, "三个假设：瓶颈的进一步分解（D151 的实验设计）", 16, bold=True))
    hyps = [
        ("H1 循环控制开销", "三重循环每圈 ~10 条控制指令\n（cmp/br/自增）——占比高",
         "展开可救（消循环控制）\n证据：D125 的 O2 = 3.4GF（8×）\nD151 验证：-O2 对照", GREEN),
        ("H2 数据复用不足", "B 列每 (i,j) 流一遍\nL1 miss 频繁",
         "tile 化可救（块内复用）\n证据：教学 tile 已有（D143）\nD151 验证：tile 扫描", ORANGE),
        ("H3 依赖链限 ILP", "acc 串行链——fadd 依赖\n前一圈的 fadd",
         "重排可救（多 acc 并行）\n证据：教科书（教学版不做）\nD151 声明边界", RED),
    ]
    for i, (name, mech, fix, color) in enumerate(hyps):
        x = 60 + i * 330
        b.append(hand_rect(x, 60, 300, 280, fill=color, opacity=0.3))
        b.append(text(x + 150, 88, name, 13, bold=True))
        b.append(text(x + 150, 112, "机制", 10, fill=MUTED))
        for j, line in enumerate(mech.split("\n")):
            b.append(text(x + 150, 130 + j*17, line, 9.5))
        b.append(text(x + 150, 190, "对策与验证", 10, fill=MUTED))
        for j, line in enumerate(fix.split("\n")):
            b.append(text(x + 150, 208 + j*17, line, 9.5))
    # 底部
    b.append(hand_rect(60, 360, 960, 66, fill="#F5E9C8", opacity=0.85))
    b.append(text(W/2, 386, "假设的可检验性：每个假设都有「对策＋已有证据＋验证方法」——", 11.5, bold=True))
    b.append(text(W/2, 408, "D151 只做 H1（O2 展开——现成）和 H2（tile——D143 的生成器）；H3 声明不做（依赖链重排超出教学范围）", 10.5))
    save("02-hypotheses.svg", "".join(b), h=440)

def fig3():
    b = []
    b.append(text(W/2, 34, "明天 D151：有依据的优化——验证 H1 与 H2", 16, bold=True))
    exps = [
        ("实验 A：O2 展开（验 H1）", "同一 kernel：-O0 vs -O2 编译\n对照 GFLOPS：0.39 → 3.4（预期 8×）\n若成立：循环开销是主因之一", GREEN),
        ("实验 B：tile 扫描（验 H2）", "tile=(32,32,32)/(64,64,64)/…\n对照朴素版的 GFLOPS\n若成立：块内复用提升有效", ORANGE),
        ("实验 C：组合（O2＋tile）", "两个优化的叠加效果\n预期：>各自单独（正交互用）\nD152 的跨 shape 验证基础", PURPLE),
    ]
    for i, (name, body, color) in enumerate(exps):
        y = 60 + i * 130
        b.append(hand_rect(60, y, 960, 116, fill=color, opacity=0.28))
        b.append(text(540, y + 26, name, 13, bold=True))
        for j, line in enumerate(body.split("\n")):
            b.append(text(540, y + 52 + j*20, line, 10.5))
    b.append(hand_rect(60, 460, 960, 66, fill="#F5E9C8", opacity=0.85))
    b.append(text(W/2, 486, "「有依据」的含义：每个实验都对应今天的假设——不是「试试看」，", 12, bold=True))
    b.append(text(W/2, 508, "而是「假设 H1 → 预测 O2 有效 → 实验验证 → 结论」的完整推理链——失败也 informative（假设被证伪）", 10.5))
    save("03-tomorrow.svg", "".join(b), h=540)

if __name__ == "__main__":
    fig1()
    fig2()
    fig3()
