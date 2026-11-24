#!/usr/bin/env python3
"""第 160 天 3 张 SVG。种子 160。"""
from __future__ import annotations
import math, os, random
import xml.sax.saxutils as su
random.seed(160)
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
    b.append(text(W/2, 34, "干净复现走查：8/8 文档与产物在位", 16, bold=True))
    rows = [
        ("架构文档", "architecture.txt", "D155"), ("Pass 文档×4", "pass-*.md", "D156"),
        ("Lowering 文档", "lowering-doc.md", "D157"), ("测试文档", "test-doc.md", "D158"),
        ("性能汇总", "perf-summary.json", "D159"), ("核心链产物", "rebuild-log.txt", "D126"),
        ("基线 json", "baseline.json", "D148"), ("冻结验收", "issue-list.txt", "D139"),
    ]
    for i, (name, file, day) in enumerate(rows):
        x = 60 + (i % 2) * 480
        y = 60 + (i // 2) * 76
        b.append(hand_rect(x, y, 450, 64, fill=GREEN, opacity=0.3))
        b.append(text(x + 130, y + 26, name, 11.5, bold=True))
        b.append(text(x + 300, y + 26, file, 10, mono=True))
        b.append(text(x + 400, y + 26, day, 9.5, fill=MUTED))
        b.append(text(x + 130, y + 48, "✓ 在位", 10, bold=True, fill="#4a7c59"))
    b.append(hand_rect(60, 400, 960, 70, fill="#F5E9C8", opacity=0.85))
    b.append(text(W/2, 426, "干净复现的意义：文档可用性的终极测试——", 12, bold=True))
    b.append(text(W/2, 450, "不是「文档写好了」而是「新人按图索骥能跑通」——每个 ✓ 都是一份「能被验证」的承诺", 10.5))
    save("01-walkthrough.svg", "".join(b), h=480)

def fig2():
    b = []
    b.append(text(W/2, 34, "复现的三层保障", 16, bold=True))
    layers = [
        ("文档层", "五份文档（架构/Pass/Lowering/测试/性能）\n——「去哪找什么」", GREEN),
        ("产物层", "每天的 outputs/ 冻结（json/txt/mlir/ll）\n——「找到了能看」", BLUE),
        ("命令层", "每天的 run_all.sh（一键重跑）\n——「想验证能跑」", ORANGE),
    ]
    for i, (name, body, color) in enumerate(layers):
        y = 60 + i * 110
        b.append(hand_rect(60, y, 960, 96, fill=color, opacity=0.3))
        b.append(text(160, y + 30, name, 13, bold=True))
        for j, line in enumerate(body.split("\n")):
            b.append(text(560, y + 30 + j*22, line, 11))
    b.append(hand_rect(60, 400, 960, 60, fill="#F5E9C8", opacity=0.85))
    b.append(text(W/2, 424, "三层缺一：只写文档不冻结产物＝纸上谈兵；只冻产物不给命令＝黑盒；", 11.5, bold=True))
    b.append(text(W/2, 446, "只给命令不写文档＝考古现场——三层齐备才是「能被他人理解和验证」", 10.5))
    save("02-three-layers.svg", "".join(b), h=470)

def fig3():
    b = []
    b.append(text(W/2, 34, "明天 D161：第 23 周复盘（新人视角）", 16, bold=True))
    b.append(hand_rect(60, 60, 960, 180, fill=PURPLE, opacity=0.25))
    b.append(text(W/2, 86, "第 23 周的五份文档＋一个测试", 13, bold=True))
    docs = [
        ("D155 架构", "六层数据流＋十模块＋三合同"),
        ("D156 Pass×4", "五要素＋前后 IR＋诚实反例"),
        ("D157 Lowering", "六阶段旅程＋信息守恒"),
        ("D158 测试", "金字塔＋四命令＋250 项＋缺口"),
        ("D159 性能", "六源＋口径＋一句话结论"),
        ("D160 复现", "8/8 走查（今天）"),
    ]
    for i, (d, note) in enumerate(docs):
        x = 90 + (i % 3) * 300
        y = 110 + (i // 3) * 56
        b.append(text(x + 140, y, f"{d}：{note}", 10))
    # 新人视角
    b.append(hand_rect(60, 260, 960, 100, fill="#F5E9C8", opacity=0.85))
    b.append(text(W/2, 286, "明天的新人视角检查", 12.5, bold=True))
    b.append(text(W/2, 310, "「以第一次接触项目的视角通读文档，删除只对自己有意义的表述」——计划条目原话", 10.5))
    b.append(text(W/2, 334, "自查问题：哪个词只有我知道什么意思？哪一步我默认了读者知道？", 10.5))
    save("03-tomorrow.svg", "".join(b), h=380)

if __name__ == "__main__":
    fig1()
    fig2()
    fig3()
