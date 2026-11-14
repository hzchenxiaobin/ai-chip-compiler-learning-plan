#!/usr/bin/env python3
"""第 157 天 3 张 SVG。种子 157。"""
from __future__ import annotations
import math, os, random
import xml.sax.saxutils as su
random.seed(157)
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
def arrow(x1, y1, x2, y2, stroke=INK, sw=1.8, label=None):
    import math as m
    mx, my = (x1+x2)/2 + jit(2), (y1+y2)/2 + jit(2)
    ang = m.atan2(y2-y1, x2-x1)
    hx, hy = x2-9*m.cos(ang), y2-9*m.sin(ang)
    a1 = (hx+5*m.cos(ang+2.7), hy+5*m.sin(ang+2.7))
    a2 = (hx+5*m.cos(ang-2.7), hy+5*m.sin(ang-2.7))
    d = (f"M {x1+jit():.1f},{y1+jit():.1f} Q {mx:.1f},{my:.1f} "
         f"{x2:.1f},{y2:.1f} M {a1[0]:.1f},{a1[1]:.1f} L {x2:.1f},{y2:.1f} L {a2[0]:.1f},{a2[1]:.1f}")
    out = (f'<path d="{d}" stroke="{stroke}" stroke-width="{sw}" '
           f'stroke-linecap="round" fill="none"/>')
    if label:
        out += text((x1+x2)/2, (y1+y2)/2-8, label, 9.5, MUTED)
    return out
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
    b.append(text(W/2, 34, "一个 MatMul 的六阶段旅程（Lowering 文档主图）", 15, bold=True))
    stages = [
        ("①图 IR", "matmul+add+relu\n（算子语义）", GREEN),
        ("②循环 IR", "scf.for＋iter_args\n（bias 融 k=0）", GREEN),
        ("③cf 层", "块＋跳转边\n（「循环」消失）", BLUE),
        ("④LLVM 方言", "描述符＋gep\n（memref 消失）", BLUE),
        ("⑤LLVM IR", "phi＋icmp slt\n（名字/常量消失）", ORANGE),
        ("⑥机器码", "ldr/fmul（arm64）\n（SSA 消失）", RED),
    ]
    for i, (name, body, color) in enumerate(stages):
        x = 40 + i * 170
        b.append(hand_rect(x, 70, 155, 110, fill=color, opacity=0.4))
        b.append(text(x + 77, 96, name, 12, bold=True))
        for j, line in enumerate(body.split("\n")):
            b.append(text(x + 77, 120 + j*18, line, 9.5))
        if i < 5:
            b.append(arrow(x + 157, 125, x + 168, 125, sw=1.4))
    # 关键转换标注
    transforms = ["S1 融合", "scf→cf", "五 convert", "translate R1~R3", "llc 指令选择"]
    for i, t in enumerate(transforms):
        x = 40 + i * 170 + 157
        b.append(text(x + 8, 205, t, 8.5, fill=MUTED, bold=True))
    # 主线
    b.append(hand_rect(60, 230, 960, 60, fill="#F5E9C8", opacity=0.85))
    b.append(text(W/2, 254, "主线：抽象逐级消失、语义全程保持——", 13, bold=True))
    b.append(text(W/2, 276, "每一阶段的「关键转换」标注下一跳；信息守恒表（D119）在文档尾部复述", 10.5))
    save("01-journey.svg", "".join(b), h=310)

def fig2():
    b = []
    b.append(text(W/2, 34, "三个关键转换的现场（文档的证据段）", 16, bold=True))
    scenes = [
        ("②→③ scf→cf", "scf.for %k = 0 to K\n  iter_args(%acc=%bj)",
         "cf.br ^header(%c0, %bj)\n^header(%k, %acc):\n  cond_br → body/latch", GREEN),
        ("④→⑤ translate R3", "^merge(%m: i32)\n  llvm.return %m",
         "10:\n  %11 = phi [%7,%6],[%9,%8]\n  ret i32 %11", ORANGE),
        ("⑤→⑥ llc", "%53 = load float, ptr %52\n%58 = fmul %53, %57",
         "ldr s0, [x1, x8, lsl#2]\nfmul s1, s0, s2", RED),
    ]
    for i, (title, before, after, color) in enumerate(scenes):
        y = 60 + i * 180
        b.append(text(290, y + 16, f"{title}（前）", 11, bold=True))
        b.append(hand_rect(60, y + 24, 460, 130, fill=RED, opacity=0.18))
        for j, line in enumerate(before.split("\n")):
            b.append(text(90, y + 50 + j*22, line, 9.5, mono=True, anchor="start"))
        b.append(text(790, y + 16, f"{title}（后）", 11, bold=True))
        b.append(hand_rect(560, y + 24, 460, 130, fill=GREEN, opacity=0.2))
        for j, line in enumerate(after.split("\n")):
            b.append(text(590, y + 50 + j*22, line, 9.5, mono=True, anchor="start"))
        b.append(arrow(524, y + 89, 558, y + 89, sw=1.6))
    save("02-scenes.svg", "".join(b), h=610)

def fig3():
    b = []
    b.append(text(W/2, 34, "信息守恒（文档尾部）＋文档的读者", 16, bold=True))
    # 守恒表
    rows = [
        ("算子语义", "阶段 ② 消失", "三层 for 不再「是」MatMul", RED),
        ("shape 决策", "阶段 ⑤ 内联成常量", "icmp slt ..., 4 的 4=M", ORANGE),
        ("描述符合同", "阶段 ④ 新增", "D115 的 56B 契约", GREEN),
        ("正确性裁判", "阶段 ⑥ 总验", "执行＋golden 12/12", BLUE),
    ]
    y = 60
    for item, fate, note, color in rows:
        b.append(hand_rect(60, y, 960, 50, fill=color, opacity=0.25))
        b.append(text(180, y + 30, item, 11.5, bold=True))
        b.append(text(450, y + 30, fate, 11))
        b.append(text(780, y + 30, note, 9.5, fill=MUTED))
        y += 56
    # 读者
    b.append(hand_rect(60, y + 10, 960, 70, fill="#F5E9C8", opacity=0.85))
    b.append(text(W/2, y + 36, "Lowering 文档的两类读者：", 12, bold=True))
    b.append(text(W/2, y + 58, "新人（顺着六阶段读懂「数据怎么变」）＋维护者（查「哪个转换动了哪层」——debug 时的地图）", 10.5))
    save("03-conservation.svg", "".join(b), h=y + 100)

if __name__ == "__main__":
    fig1()
    fig2()
    fig3()
