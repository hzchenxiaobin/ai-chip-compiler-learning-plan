#!/usr/bin/env python3
"""第 165 天 3 张 SVG。种子 165。"""
from __future__ import annotations
import math, os, random
import xml.sax.saxutils as su
random.seed(165)
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
    b.append(text(W/2, 34, "两份标答：Tile 的三角决定与瓶颈判断的 Roofline 三分支", 16, bold=True))
    qs = [
        ("Tile 由什么决定", "三角：容量/复用/边界（D101~151）", "五项记账＋闸门拒收＋0.3× 反例"),
        ("如何判断计算或访存瓶颈", "Roofline AI＋拐点（D150）", "两屋顶都远→第三种：执行效率"),
    ]
    for i, (q, ev, note) in enumerate(qs):
        y = 60 + i * 140
        b.append(hand_rect(60, y, 960, 126, fill=BLUE, opacity=0.25))
        b.append(text(540, y + 28, q, 14, bold=True))
        b.append(text(540, y + 58, f"证据：{ev}", 11))
        b.append(text(540, y + 86, note, 10, fill=MUTED))
    b.append(hand_rect(60, 360, 960, 60, fill="#F5E9C8", opacity=0.85))
    b.append(text(W/2, 384, "两题的共同点：都有实测框架——三角有五项记账、瓶颈有 Roofline", 11.5, bold=True))
    b.append(text(W/2, 406, "第三种瓶颈（执行效率）是本仓库的独特发现——D150 的实测贡献", 10.5))
    save("01-two-answers.svg", "".join(b), h=430)

def fig2():
    b = []
    b.append(text(W/2, 34, "Tile 三角的三个约束：各自的决定作用", 16, bold=True))
    cases = [
        ("片上容量", "D101/104", "五项记账≤256KiB｜128³ 328KB 拒收", GREEN),
        ("数据复用", "D72/D151", "ΔB 账本｜tile 复用的收益与反例", BLUE),
        ("边界代价", "D90/D143", "min 钳制｜余数 tile 的额外开销", ORANGE),
        ("综合决策", "D106~111", "搜索空间＋cost model＋实测冠军", RED),
    ]
    for i, (name, day, note, color) in enumerate(cases):
        y = 60 + i * 100
        b.append(hand_rect(60, y, 960, 86, fill=color, opacity=0.28))
        b.append(text(200, y + 26, name, 12.5, bold=True))
        b.append(text(200, y + 54, day, 10, fill=MUTED))
        b.append(text(620, y + 40, note, 11))
    b.append(hand_rect(60, 470, 960, 56, fill="#F5E9C8", opacity=0.85))
    b.append(text(W/2, 494, "三角缺一不可——容量是硬约束、复用是收益、边界是代价", 11.5, bold=True))
    b.append(text(W/2, 516, "Tile 是三者的平衡点——不是「越大越好」也不是「有 tile 就快」", 10.5))
    save("02-cases.svg", "".join(b), h=540)

def fig3():
    b = []
    b.append(text(W/2, 34, "Roofline 三分支：计算/访存/执行效率", 16, bold=True))
    layers = [
        ("计算受限", "AI > 拐点", "乘加是瓶颈——提算力/向量化", GREEN),
        ("访存受限", "AI < 拐点", "搬运是瓶颈——tile 提复用/提带宽", BLUE),
        ("执行效率（第三种）", "两屋顶都远", "开销稀释算力——展开/消除指令", RED),
    ]
    for i, (name, what, how, color) in enumerate(layers):
        y = 60 + i * 100
        b.append(hand_rect(60, y, 960, 86, fill=color, opacity=0.28))
        b.append(text(160, y + 26, name, 13, bold=True))
        b.append(text(500, y + 26, what, 11))
        b.append(text(500, y + 56, f"方法：{how}", 10, fill=MUTED))
    b.append(hand_rect(60, 370, 960, 90, fill="#F5E9C8", opacity=0.85))
    b.append(text(W/2, 396, "两屋顶都远的判定是本仓库的实测发现——", 11.5, bold=True))
    b.append(text(W/2, 420, "D150：0.39GF 离两屋顶 128×/32×——循环控制指令稀释有效算力", 10.5))
    b.append(text(W/2, 442, "＋D151 的 O2 8.4× 验证了定性——消除开销的收益证明判断正确", 10.5))
    save("03-three-layers.svg", "".join(b), h=470)

if __name__ == "__main__":
    fig1()
    fig2()
    fig3()
