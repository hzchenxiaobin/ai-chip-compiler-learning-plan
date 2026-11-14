#!/usr/bin/env python3
"""第 164 天 3 张 SVG。种子 164。"""
from __future__ import annotations
import math, os, random
import xml.sax.saxutils as su
random.seed(164)
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
    b.append(text(W/2, 34, "两份标答：动态 Shape 的完整成本与运行期决策的光谱", 16, bold=True))
    qs = [
        ("动态 Shape 难在哪里", "六件事＋三件套（D128~131）", "fmul 18→2 收缩｜2→18 特化补回"),
        ("哪些决策应放到运行期", "11 决策点＋光谱（D127/133）", "翻转五格各配实测｜保持三格有理由"),
    ]
    for i, (q, ev, note) in enumerate(qs):
        y = 60 + i * 140
        b.append(hand_rect(60, y, 960, 126, fill=BLUE, opacity=0.25))
        b.append(text(540, y + 28, q, 14, bold=True))
        b.append(text(540, y + 58, f"证据：{ev}", 11))
        b.append(text(540, y + 86, note, 10, fill=MUTED))
    b.append(hand_rect(60, 360, 960, 60, fill="#F5E9C8", opacity=0.85))
    b.append(text(W/2, 384, "两题的共同框架：光谱思维——每个决策在 COMPILE~RUNTIME 上有位置", 11.5, bold=True))
    b.append(text(W/2, 406, "动态化的完整成本是整个 Runtime 层——这是第 19 周的标准回答（D133）", 10.5))
    save("01-two-answers.svg", "".join(b), h=430)

def fig2():
    b = []
    b.append(text(W/2, 34, "动态 Shape 六件事：一串涟漪的逐件对照", 16, bold=True))
    cases = [
        ("① 签名 ?占位", "D128", "memref<4x6>→<?x?x>——shape 从类型搬进描述符", GREEN),
        ("② 读回 extractvalue", "D128", "dim+extractvalue——+6 处描述符读回", BLUE),
        ("③ 动态 alloc", "D128", "memref.alloc(%M,%N)——输出 shape 运行期", ORANGE),
        ("④ 循环边界", "D128", "icmp 常量4→SSA%29——两种归属的全部差别", RED),
    ]
    for i, (name, day, note, color) in enumerate(cases):
        y = 60 + i * 100
        b.append(hand_rect(60, y, 960, 86, fill=color, opacity=0.28))
        b.append(text(200, y + 26, name, 12.5, bold=True))
        b.append(text(200, y + 54, day, 10, fill=MUTED))
        b.append(text(620, y + 40, note, 11))
    b.append(hand_rect(60, 470, 960, 56, fill="#F5E9C8", opacity=0.85))
    b.append(text(W/2, 494, "六件事是 D128 一天的完整涟漪——改一个类型标注、六处联动", 11.5, bold=True))
    b.append(text(W/2, 516, "「不只是把常量改成变量」——完整成本是整个 Runtime 层", 10.5))
    save("02-cases.svg", "".join(b), h=540)

def fig3():
    b = []
    b.append(text(W/2, 34, "三件套的解剖（特化＋回退＋池化）", 16, bold=True))
    layers = [
        ("特化 D129", "静态签名给优化器确定性", "fmul 2→18（9 倍）", GREEN),
        ("回退 D130", "四级降级链兜正确性", "E301/302/303", BLUE),
        ("池化 D131", "管内存生命周期", "99% 复用", ORANGE),
    ]
    for i, (name, what, how, color) in enumerate(layers):
        y = 60 + i * 100
        b.append(hand_rect(60, y, 960, 86, fill=color, opacity=0.28))
        b.append(text(160, y + 26, name, 13, bold=True))
        b.append(text(500, y + 26, what, 11))
        b.append(text(500, y + 56, f"方法：{how}", 10, fill=MUTED))
    b.append(hand_rect(60, 370, 960, 90, fill="#F5E9C8", opacity=0.85))
    b.append(text(W/2, 396, "三件套缺一：性能/正确性/内存三缺一——", 11.5, bold=True))
    b.append(text(W/2, 420, "动态化的安全网不完整——PyTorch 2.x 的工程答案就是三件套", 10.5))
    b.append(text(W/2, 442, "＋D127 审计表是决策光谱的操作化——11 决策点每格显式选择", 10.5))
    save("03-three-layers.svg", "".join(b), h=470)

if __name__ == "__main__":
    fig1()
    fig2()
    fig3()
