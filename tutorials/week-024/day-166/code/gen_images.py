#!/usr/bin/env python3
"""第 166 天 3 张 SVG。种子 166。"""
from __future__ import annotations
import math, os, random
import xml.sax.saxutils as su
random.seed(166)
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
    b.append(text(W/2, 34, "两份标答：调试的五站流水线与数值差异的误差界", 16, bold=True))
    qs = [
        ("如何定位 Pass 错误", "五站流水线（D135~140）", "首次变坏＝凶手＋19→4 节点"),
        ("数值差异都是浮点误差吗", "误差界＋序差（D78~129）", "1~2 ULP 合法 vs 系统性偏移是 bug"),
    ]
    for i, (q, ev, note) in enumerate(qs):
        y = 60 + i * 140
        b.append(hand_rect(60, y, 960, 126, fill=BLUE, opacity=0.25))
        b.append(text(540, y + 28, q, 14, bold=True))
        b.append(text(540, y + 58, f"证据：{ev}", 11))
        b.append(text(540, y + 86, note, 10, fill=MUTED))
    b.append(hand_rect(60, 360, 960, 60, fill="#F5E9C8", opacity=0.85))
    b.append(text(W/2, 384, "两题的共同点：都有踩坑故事——k0 bug 与量化语义 bug 是活的教材", 11.5, bold=True))
    b.append(text(W/2, 406, "「最早语义破坏点」是调试的核心——五站流水线的口诀", 10.5))
    save("01-two-answers.svg", "".join(b), h=430)

def fig2():
    b = []
    b.append(text(W/2, 34, "五站流水线：发现→看清→锁定→缩小→修死", 16, bold=True))
    cases = [
        ("① 发现", "D134/135", "正反集守已知的坑｜fuzz 探未知", GREEN),
        ("② 看清", "D123", "--dump-ir=full｜改写记录", BLUE),
        ("③ 锁定", "D136", "前缀递增｜首次变坏＝凶手", ORANGE),
        ("④ 缩小＋⑤ 修死", "D137/D134", "19→4 节点｜固化免疫", RED),
    ]
    for i, (name, day, note, color) in enumerate(cases):
        y = 60 + i * 100
        b.append(hand_rect(60, y, 960, 86, fill=color, opacity=0.28))
        b.append(text(200, y + 26, name, 12.5, bold=True))
        b.append(text(200, y + 54, day, 10, fill=MUTED))
        b.append(text(620, y + 40, note, 11))
    b.append(hand_rect(60, 470, 960, 56, fill="#F5E9C8", opacity=0.85))
    b.append(text(W/2, 494, "每站的输出是下一站的输入——流水线的接口设计", 11.5, bold=True))
    b.append(text(W/2, 516, "调试核心＝定位最早语义破坏点——后面的全是涟漪", 10.5))
    save("02-cases.svg", "".join(b), h=540)

def fig3():
    b = []
    b.append(text(W/2, 34, "数值差异的三分法：bug/序差/界内误差", 16, bold=True))
    layers = [
        ("真 bug", "超误差界", "系统性偏移/全错——修代码", RED),
        ("序差（合法）", "同量级不同值", "k 序 vs BLAS 序——判据升级 allclose", BLUE),
        ("界内误差", "< (2K+2)·eps·Σ|a·b|", "浮点舍入的合法范围——可通过", GREEN),
    ]
    for i, (name, what, how, color) in enumerate(layers):
        y = 60 + i * 100
        b.append(hand_rect(60, y, 960, 86, fill=color, opacity=0.28))
        b.append(text(160, y + 26, name, 13, bold=True))
        b.append(text(500, y + 26, what, 11))
        b.append(text(500, y + 56, f"方法：{how}", 10, fill=MUTED))
    b.append(hand_rect(60, 370, 960, 90, fill="#F5E9C8", opacity=0.85))
    b.append(text(W/2, 396, "判据的口径决定结论——「差多少才算错」要先定义：", 11.5, bold=True))
    b.append(text(W/2, 420, "D121 的量化 bug（0.3≠0.296875）被位等价抓住——不是浮点误差是语义错", 10.5))
    b.append(text(W/2, 442, "＋D78~80 的浮点课：换序≠换值——序差的量级是 1~2 ULP 不是任意", 10.5))
    save("03-three-layers.svg", "".join(b), h=470)

if __name__ == "__main__":
    fig1()
    fig2()
    fig3()
