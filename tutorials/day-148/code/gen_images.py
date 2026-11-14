#!/usr/bin/env python3
"""第 148 天 3 张 SVG。种子 148。"""
from __future__ import annotations
import math, os, random
import xml.sax.saxutils as su
random.seed(148)
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
    b.append(text(W/2, 34, "慢用例选定：160×160×160 朴素 kernel 20.9ms / 0.39 GFLOPS", 15, bold=True))
    # 选型表
    b.append(text(W/2, 66, "B1 候选扫描（朴素 O0 kernel）", 13.5, bold=True))
    rows = [("128×128×128", "10.8 ms", "0.388 GFLOPS"),
            ("160×160×160", "22.5 ms", "0.364 GFLOPS ← 选定"),
            ("96×160×160", "12.3 ms", "0.398 GFLOPS")]
    y = 86
    for shape, ms, gf in rows:
        color = RED if "选定" in gf else BLUE
        b.append(hand_rect(200, y, 680, 36, fill=color, opacity=0.3))
        b.append(text(340, y + 24, shape, 11.5, mono=True))
        b.append(text(520, y + 24, ms, 11))
        b.append(text(720, y + 24, gf, 10.5, bold="选定" in gf))
        y += 42
    # 基线
    b.append(text(W/2, y + 16, "B2 基线（7 轮×3 次取中位）", 13.5, bold=True))
    b.append(hand_rect(160, y + 36, 760, 100, fill=GREEN, opacity=0.3))
    stats = [("20.91 ms", "中位数（7 轮中位）"), ("0.392 GFLOPS", "吞吐（远低于峰值）"),
             ("arm64 Darwin", "环境（clang 23.1.5）"), ("7×3", "口径（轮×次）")]
    for i, (num, label) in enumerate(stats):
        x = 210 + i * 180
        b.append(text(x + 70, y + 66, num, 13, bold=True))
        b.append(text(x + 70, y + 90, label, 9.5, MUTED))
    # 底部
    b.append(hand_rect(60, y + 152, 960, 70, fill="#F5E9C8", opacity=0.85))
    b.append(text(W/2, y + 176, "「明显慢」的判据：GFLOPS 0.39 vs M 系峰值（~50+）——差百倍", 12, bold=True))
    b.append(text(W/2, y + 200, "朴素三重循环＋O0 编译（不优化）——保留原始形态作为归因起点；D151 的优化空间由此定义", 10.5))
    save("01-baseline.svg", "".join(b), h=y + 240)

def fig2():
    b = []
    b.append(text(W/2, 34, "基线的口径设计：每项都有理由", 16, bold=True))
    items = [
        ("shape 160³", "计算量 2×160³=8.2 MFLOP——\n足够慢到可测（>10ms），\n又不至于每轮等太久", GREEN),
        ("朴素＋O0", "保留三重循环的原始形态——\n优化空间最大化；\nO2 版已有（D125 的 3.4 GFLOPS）", RED),
        ("7 轮×3 次", "外层中位数抗轮级噪声；\n内层均值压调用级波动——\nD138 的两层统计口径", BLUE),
        ("GFLOPS 口径", "FLOP=2MNK（乘加各一）；\n跨 shape 可比（时间不可比\n——shape 不同计算量不同）", ORANGE),
    ]
    for i, (name, body, color) in enumerate(items):
        x = 60 + (i % 2) * 480
        y = 60 + (i // 2) * 170
        b.append(hand_rect(x, y, 440, 150, fill=color, opacity=0.3))
        b.append(text(x + 220, y + 28, name, 13, bold=True))
        for j, line in enumerate(body.split("\n")):
            b.append(text(x + 220, y + 54 + j*22, line, 10))
    b.append(hand_rect(60, 410, 960, 66, fill="#F5E9C8", opacity=0.85))
    b.append(text(W/2, 436, "基线的本质：不是「一个数字」而是「一个可复现的测量协议」——", 12, bold=True))
    b.append(text(W/2, 458, "shape/kernel/编译配置/口径/环境五要素齐备，任何人任何时候重跑都能得到同一个数（±噪声）", 10.5))
    save("02-protocol.svg", "".join(b), h=490)

def fig3():
    b = []
    b.append(text(W/2, 34, "第 22 周的归因路线：从基线到反例", 16, bold=True))
    steps = [
        ("D148 今天", "基线 20.9ms/0.39GF", "问题定义：什么算慢、怎么复现", GREEN),
        ("D149", "时间分解", "编译/搜索/launch/分配/执行\n各占多少——主要开销在哪", BLUE),
        ("D150", "Roofline", "算术强度 vs 屋顶——\n计算瓶颈还是访存瓶颈", ORANGE),
        ("D151", "有依据优化", "针对 D150 确认的瓶颈——\n不是随机试", RED),
        ("D152", "跨 Shape 验证", "不只报最好——\n5+ shape 的收益表", PURPLE),
        ("D153", "反例", "优化失效的场景＋\n适用条件（D125 伏笔）", RED),
        ("D154", "闭环报告", "瓶颈→假设→优化→验证→\n范围的完整链条", BLUE),
    ]
    for i, (d, name, note, color) in enumerate(steps):
        y = 60 + i * 82
        b.append(hand_rect(60, y, 960, 70, fill=color, opacity=0.28))
        b.append(text(130, y + 26, d, 12, bold=True))
        b.append(text(130, y + 50, note.split("\n")[0][:22], 9.5, fill=MUTED))
        b.append(text(420, y + 34, name, 12))
        if len(note.split("\n")) > 1:
            b.append(text(700, y + 26, note.split("\n")[1], 10))
    b.append(hand_rect(60, 650, 960, 56, fill="#F5E9C8", opacity=0.85))
    b.append(text(W/2, 674, "归因的方法论：每一步都从上一步的结论出发——基线定义问题、分解找嫌疑、Roofline 定性质、", 11, bold=True))
    b.append(text(W/2, 694, "优化验证假设、跨 Shape 界定范围、反例诚实边界——没有一步是「感觉应该」", 10.5))
    save("03-roadmap.svg", "".join(b), h=720)

if __name__ == "__main__":
    fig1()
    fig2()
    fig3()
