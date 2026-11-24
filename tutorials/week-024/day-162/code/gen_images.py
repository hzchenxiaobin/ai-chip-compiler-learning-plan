#!/usr/bin/env python3
"""第 162 天 3 张 SVG。种子 162。"""
from __future__ import annotations
import math, os, random
import xml.sax.saxutils as su
random.seed(162)
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
    b.append(text(W/2, 34, "三份标准回答：四段式结构（每段配本仓库实测）", 16, bold=True))
    qs = [
        ("为什么需要多层 IR", "七层对账（D119）＋分层优化的分工",
         "融合在图层（需要算子语义）｜展开在 LLVM 层（需要指令信息）"),
        ("MLIR 解决什么问题", "D57~118 的 dialect 链＋七 pass（D117）",
         "前端只写差异（mini 方言）——SSA/Pass/LLVM 复用"),
        ("SSA 有什么价值", "D113 R3（块参数→phi）＋D151 展开 8.4×",
         "fmul 1→18 的安全重排依赖 SSA 的显式数据流"),
    ]
    for i, (q, ev, note) in enumerate(qs):
        y = 60 + i * 130
        b.append(hand_rect(60, y, 960, 116, fill=BLUE, opacity=0.25))
        b.append(text(540, y + 26, q, 13.5, bold=True))
        b.append(text(540, y + 54, f"项目例子：{ev}", 10.5))
        b.append(text(540, y + 80, note, 10, fill=MUTED))
    b.append(hand_rect(60, 460, 960, 60, fill="#F5E9C8", opacity=0.85))
    b.append(text(W/2, 484, "四段式：结论（一句）→机制（类比＋技术对应）→项目例子（实测数字/IR）→限制（诚实边界）", 11.5, bold=True))
    b.append(text(W/2, 506, "「例子来自实测」是 22 周积累的面试价值——不是背概念而是复述经历", 10.5))
    save("01-answers.svg", "".join(b), h=530)

def fig2():
    b = []
    b.append(text(W/2, 34, "四段式解剖：以「为什么需要多层 IR」为例", 16, bold=True))
    segs = [
        ("① 结论", "每层只面对一类问题——领域语义与执行细节分层处理", GREEN, "10 秒"),
        ("② 机制", "翻译类比（不直译甲骨文）＋技术对应（pass 只懂本层）", BLUE, "30 秒"),
        ("③ 项目例子", "minic 七层＋两个优化的分层（融合在图/展开在 LLVM）", ORANGE, "60 秒"),
        ("④ 限制", "层多有转换开销（D119 信息守恒）——权衡不是越多越好", RED, "20 秒"),
    ]
    for i, (name, body, color, time) in enumerate(segs):
        y = 60 + i * 100
        b.append(hand_rect(60, y, 960, 86, fill=color, opacity=0.28))
        b.append(text(150, y + 26, name, 13, bold=True))
        b.append(text(150, y + 56, f"时长：{time}", 10, fill=MUTED))
        b.append(text(580, y + 40, body, 11.5))
    b.append(hand_rect(60, 470, 960, 56, fill="#F5E9C8", opacity=0.85))
    b.append(text(W/2, 494, "总时长约 2 分钟——四段的时间配比 10:30:60:20（例子最长——它是差异化所在）", 11.5, bold=True))
    b.append(text(W/2, 514, "限制段最容易被忽略但面试官最爱追——主动说限制＝展示工程成熟度", 10.5))
    save("02-anatomy.svg", "".join(b), h=540)

def fig3():
    b = []
    b.append(text(W/2, 34, "明天 D163：融合、Layout 与正确性的标准回答", 16, bold=True))
    tomorrows = [
        ("「融合为什么不一定更快」", "正例：7→5 节点（结构收益）\n反例：教学规模 HBM 流量归零\n＋多使用者不融的边界"),
        ("「如何保证 Pattern 不改语义」", "三层验证法（契约/数值/布局）\n＋位等价测试 3×10000\n＋D121 的量化语义教训"),
    ]
    for i, (q, body) in enumerate(tomorrows):
        y = 60 + i * 150
        b.append(hand_rect(60, y, 960, 136, fill=GREEN, opacity=0.28))
        b.append(text(540, y + 28, q, 13.5, bold=True))
        for j, line in enumerate(body.split("\n")):
            b.append(text(540, y + 56 + j*24, line, 10.5))
    b.append(hand_rect(60, 380, 960, 60, fill="#F5E9C8", opacity=0.85))
    b.append(text(W/2, 404, "两题各有正反例——「融合不总是更快」的反例是本仓库最硬的实测（0.3×/1.7×）", 11.5, bold=True))
    b.append(text(W/2, 426, "面试官问「你的优化什么时候失效」时的标准弹药", 10.5))
    save("03-tomorrow.svg", "".join(b), h=450)

if __name__ == "__main__":
    fig1()
    fig2()
    fig3()
