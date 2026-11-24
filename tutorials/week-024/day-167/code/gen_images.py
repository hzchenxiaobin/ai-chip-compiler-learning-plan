#!/usr/bin/env python3
"""第 167 天 3 张 SVG。种子 167。"""
from __future__ import annotations
import math, os, random
import xml.sax.saxutils as su
random.seed(167)
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
    b.append(text(W/2, 34, "20 分钟讲解的时间轴（五幕＋Q&A）", 16, bold=True))
    acts = [
        ("开场 2'", "问题背景＋一句话定位", GREEN),
        ("第一幕 5'", "架构主线＋数字锚点", GREEN),
        ("第二幕 5'", "三个技术难点", ORANGE),
        ("第三幕 5'", "量化结果＋反例", BLUE),
        ("收尾 3'", "限制＋下一步", RED),
        ("Q&A 10'", "六题标答索引", PURPLE),
    ]
    # 时间轴
    b.append(hand_rect(60, 60, 960, 20, fill=BG, opacity=0.9))
    widths = [(0, 120), (120, 420), (420, 720), (720, 1020), (1020, 960)]
    colors = [GREEN, GREEN, ORANGE, BLUE, RED]
    for (x1, x2), color in zip(widths, colors):
        w = x2 - x1
        b.append(hand_rect(60 + x1, 58, w, 24, fill=color, opacity=0.5))
    for i, (name, note, color) in enumerate(acts):
        y = 110 + i * 88
        b.append(hand_rect(60, y, 960, 76, fill=color, opacity=0.28))
        b.append(text(170, y + 28, name, 13, bold=True))
        b.append(text(560, y + 28, note, 12))
        b.append(text(560, y + 54, f"时长 {name.split(' ')[1]}", 10, fill=MUTED))
    b.append(hand_rect(60, 660, 960, 56, fill="#F5E9C8", opacity=0.85))
    b.append(text(W/2, 684, "讲解的纪律：每一幕至少一个数字锚点——听者记住的是数字不是形容词", 11.5, bold=True))
    b.append(text(W/2, 706, "（12/12｜8.4×｜1.7~14.1×｜250 项——四个数字讲完全项目）", 10.5))
    save("01-timeline.svg", "".join(b), h=730)

def fig2():
    b = []
    b.append(text(W/2, 34, "Q&A 预案：六题标答的索引＋卡壳预案", 16, bold=True))
    qs = [
        ("为什么多层 IR", "D162"), ("融合什么时候失效", "D163"),
        ("动态 Shape 难在哪", "D164"), ("Tile 怎么选", "D165"),
        ("怎么调试 Pass 错", "D166"), ("数值差异怎么判", "D166"),
    ]
    for i, (q, day) in enumerate(qs):
        x = 60 + (i % 3) * 330
        y = 60 + (i // 3) * 90
        b.append(hand_rect(x, y, 300, 78, fill=GREEN, opacity=0.3))
        b.append(text(x + 150, y + 26, q, 11.5, bold=True))
        b.append(text(x + 150, y + 52, f"标答索引：{day}", 10, fill=MUTED))
    # 卡壳预案
    b.append(hand_rect(60, 260, 960, 120, fill=RED, opacity=0.2))
    b.append(text(W/2, 286, "卡壳预案（不知道的问题）", 13, bold=True, fill=RED))
    lines = [
        "答法：「这个我没测过——我的推测是……（给出最接近的已学概念）但需要实验验证」",
        "三个诚实卡壳（stuck-list）：SIMD 细节｜rewrite 生命周期｜多线程编译",
        "原则：诚实承认边界比编造答案加分——编造会连环追问崩盘",
    ]
    for j, line in enumerate(lines):
        b.append(text(W/2, 312 + j*22, line, 10.5))
    b.append(hand_rect(60, 400, 960, 56, fill="#F5E9C8", opacity=0.85))
    b.append(text(W/2, 424, "Q&A 的准备度＝标答索引（六题有备）＋卡壳清单（三题有诚）", 11.5, bold=True))
    b.append(text(W/2, 446, "「没测过」不丢人——「没测过但推测合理且指出验证方法」是工程师的成熟回答", 10.5))
    save("02-qa.svg", "".join(b), h=470)

def fig3():
    b = []
    b.append(text(W/2, 34, "明天 D168：最终验收——168 天的收官", 16, bold=True))
    items = [
        ("最终验收清单", "计划文档 1136~1178 行的逐项勾\n（从「能写出 mini 编译器」到「能选深入方向」）"),
        ("四选一深入方向", "MLIR 图编译｜LLVM 后端｜自动调度｜芯片工具链\n——选一个、说理由、给四周计划"),
        ("168 天的能力总结", "从 C++/MLIR 基础到端到端项目＋性能归因\n＋文档＋面试表达——完整闭环"),
        ("下一阶段学习重点", "把教学版的每个「教学取舍」换成真实版\n（SIMD/多线程/GPU/真实 workload）"),
    ]
    for i, (name, body) in enumerate(items):
        y = 60 + i * 110
        b.append(hand_rect(60, y, 960, 96, fill=PURPLE, opacity=0.25))
        b.append(text(200, y + 28, name, 12.5, bold=True))
        for j, line in enumerate(body.split("\n")):
            b.append(text(560, y + 26 + j*24, line, 10.5))
    b.append(hand_rect(60, 510, 960, 60, fill="#F5E9C8", opacity=0.85))
    b.append(text(W/2, 534, "最终验收的本质：不是「都学会了」而是「知道自己会什么、不会什么、下一步学什么」", 12, bold=True))
    b.append(text(W/2, 556, "168 天的终点是下一阶段的起点——能力清单＋差距清单＋唯一方向", 10.5))
    save("03-final.svg", "".join(b), h=580)

if __name__ == "__main__":
    fig1()
    fig2()
    fig3()
