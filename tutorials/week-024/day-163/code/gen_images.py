#!/usr/bin/env python3
"""第 163 天 3 张 SVG。种子 163。"""
from __future__ import annotations
import math, os, random
import xml.sax.saxutils as su
random.seed(163)
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
    b.append(text(W/2, 34, "两份标答：融合收益的条件性与语义保证的三层法", 16, bold=True))
    qs = [
        ("融合为什么不一定更快", "正例 7→5（D121）｜反例×3", "归零（D125）/不融（D83）/0.3×（D151）"),
        ("如何保证 Pattern 不改语义", "三层验证＋位等价＋fuzz", "P1 探针（D116）/量化 bug（D121）/200 组（D135）"),
    ]
    for i, (q, ev, note) in enumerate(qs):
        y = 60 + i * 140
        b.append(hand_rect(60, y, 960, 126, fill=BLUE, opacity=0.25))
        b.append(text(540, y + 28, q, 14, bold=True))
        b.append(text(540, y + 58, f"证据：{ev}", 11))
        b.append(text(540, y + 86, note, 10, fill=MUTED))
    b.append(hand_rect(60, 360, 960, 60, fill="#F5E9C8", opacity=0.85))
    b.append(text(W/2, 384, "两题的共同武器：正反例——「什么时候失效」的答案就在反例里", 11.5, bold=True))
    b.append(text(W/2, 406, "0.3×/1.7×/归零——本仓库最硬的反例实测是面试的差异化弹药", 10.5))
    save("01-two-answers.svg", "".join(b), h=430)

def fig2():
    b = []
    b.append(text(W/2, 34, "反例弹药库：四个实测的「优化失效」", 16, bold=True))
    cases = [
        ("融合收益归零", "D125", ".ll 完全不变——cache 命中使 HBM 流量收益=0", ORANGE),
        ("多使用者不融", "D83 T10", "matmul 输出被两个下游用——融了破坏语义", RED),
        ("tile 负优化", "D151", "0.3×——重复计算 ×6.25 吃掉复用收益", RED),
        ("O2 的 shape 依赖", "D152", "64×160×32 只 1.7×——K=32 展开空间受限", PURPLE),
    ]
    for i, (name, day, note, color) in enumerate(cases):
        y = 60 + i * 100
        b.append(hand_rect(60, y, 960, 86, fill=color, opacity=0.28))
        b.append(text(200, y + 26, name, 12.5, bold=True))
        b.append(text(200, y + 54, day, 10, fill=MUTED))
        b.append(text(620, y + 40, note, 11))
    b.append(hand_rect(60, 470, 960, 56, fill="#F5E9C8", opacity=0.85))
    b.append(text(W/2, 494, "面试官问「你的优化什么时候失效？」——四个反例各有机制解释", 11.5, bold=True))
    b.append(text(W/2, 516, "答得出反例才是真懂——背概念的人给不出 0.3× 这种数字", 10.5))
    save("02-cases.svg", "".join(b), h=540)

def fig3():
    b = []
    b.append(text(W/2, 34, "三层验证法的解剖（第二题的核心）", 16, bold=True))
    layers = [
        ("契约层", "结构对——desc 56B 布局/字段名/签名", "grep 可断言", GREEN),
        ("数值层", "结果对——k 序 golden bitwise", "逐点对照", BLUE),
        ("布局层", "内存对——按裸内存行主序读回", "抓 strides 填反", ORANGE),
    ]
    for i, (name, what, how, color) in enumerate(layers):
        y = 60 + i * 100
        b.append(hand_rect(60, y, 960, 86, fill=color, opacity=0.28))
        b.append(text(160, y + 26, name, 13, bold=True))
        b.append(text(500, y + 26, what, 11))
        b.append(text(500, y + 56, f"方法：{how}", 10, fill=MUTED))
    b.append(hand_rect(60, 370, 960, 90, fill="#F5E9C8", opacity=0.85))
    b.append(text(W/2, 396, "P1 探针的故事（D116）：strides 填反在 2×2 上是缓冲区双射——", 11.5, bold=True))
    b.append(text(W/2, 420, "数值层 4/4 全对照样放走 bug；布局层 2/4 咬住——三层缺一即漏", 10.5))
    b.append(text(W/2, 442, "＋量化语义教训（D121）：DQ(Q(0.3))=0.296875——位等价第一个随机输入就抓到", 10.5))
    save("03-three-layers.svg", "".join(b), h=470)

if __name__ == "__main__":
    fig1()
    fig2()
    fig3()
