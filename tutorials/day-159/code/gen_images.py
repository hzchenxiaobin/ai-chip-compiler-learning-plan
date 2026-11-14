#!/usr/bin/env python3
"""第 159 天 3 张 SVG。种子 159。"""
from __future__ import annotations
import math, os, random
import xml.sax.saxutils as su
random.seed(159)
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
    b.append(text(W/2, 34, "性能材料汇总：六份数据源＋结论一句话", 16, bold=True))
    sources = [
        ("基线 baseline.json", "20.9ms/0.39GF＋五要素", GREEN),
        ("拆解 breakdown.json", "首次 97.7% 编译/稳态 100%", BLUE),
        ("Roofline roofline.json", "AI 0.13｜两屋顶都远", ORANGE),
        ("优化 optimize.json", "8.4×/0.3×/2.5×", RED),
        ("分布 cross-shape.json", "7 shape 1.7~14.1×", PURPLE),
        ("反例 counterexample.json", "三候选＋环境戳", RED),
    ]
    for i, (name, note, color) in enumerate(sources):
        x = 60 + (i % 3) * 330
        y = 60 + (i // 3) * 100
        b.append(hand_rect(x, y, 300, 84, fill=color, opacity=0.3))
        b.append(text(x + 150, y + 24, name, 11, bold=True, mono=True))
        b.append(text(x + 150, y + 48, note, 10))
    # 结论
    b.append(hand_rect(60, 280, 960, 100, fill="#F5E9C8", opacity=0.85))
    b.append(text(W/2, 306, "结论摘要（五步一句话版）", 13, bold=True))
    b.append(text(W/2, 330, "160³ 基线 20.9ms/0.39GF（离峰值百倍）→ 稳态执行 100% → Roofline 两屋顶都远", 10.5))
    b.append(text(W/2, 352, "→ O2 8.4×（H1 ✓）/ tile 0.3×（H2 ✗）→ 分布 1.7~14.1× → 反例是环境函数", 10.5))
    # 底部
    b.append(hand_rect(60, 400, 960, 60, fill=PURPLE, opacity=0.22))
    b.append(text(W/2, 424, "「性能结果必须附输入、配置、环境和统计口径」——计划条目原话", 11.5, bold=True))
    b.append(text(W/2, 446, "六份数据全部带口径（基线五要素/中位数口径/环境戳）——今天的汇总是这句的兑现", 10.5))
    save("01-summary.svg", "".join(b), h=470)

def fig2():
    b = []
    b.append(text(W/2, 34, "口径声明：每个数字的「出生证明」", 16, bold=True))
    decls = [
        ("基线五要素", "shape/kernel/配置/口径/环境——缺一即轶事", GREEN),
        ("统计口径", "中位数抗离群＋P90 尾部＋两层统计", BLUE),
        ("环境戳", "版本/平台——反例跨环境复用与优化同样危险", RED),
    ]
    for i, (name, body, color) in enumerate(decls):
        y = 60 + i * 110
        b.append(hand_rect(60, y, 960, 96, fill=color, opacity=0.25))
        b.append(text(200, y + 30, name, 13, bold=True))
        b.append(text(560, y + 30, body, 11))
        b.append(text(560, y + 60, f"出处：{'D148' if i==0 else 'D138' if i==1 else 'D153'}", 9.5, fill=MUTED))
    b.append(hand_rect(60, 400, 960, 60, fill="#F5E9C8", opacity=0.85))
    b.append(text(W/2, 424, "口径是数字的可信度来源——没有口径的数字是噪声", 12, bold=True))
    b.append(text(W/2, 446, "汇总文档把口径与数据并列——读者先看口径再看数字（信任的顺序）", 10.5))
    save("02-declarations.svg", "".join(b), h=470)

def fig3():
    b = []
    b.append(text(W/2, 34, "第 23 周收官与最后两周预告", 16, bold=True))
    week23 = [("D155", "架构", "✓"), ("D156", "Pass 文档", "✓"), ("D157", "Lowering", "✓"),
              ("D158", "测试", "✓"), ("D159", "性能材料", "✓ 今天"), ("D160", "干净复现", "明天"), ("D161", "复盘", "后天")]
    for i, (d, name, s) in enumerate(week23):
        x = 60 + i * 140
        color = GREEN if s == "✓" else ORANGE
        b.append(hand_rect(x, 60, 130, 80, fill=color, opacity=0.35))
        b.append(text(x + 65, 86, d, 11, bold=True))
        b.append(text(x + 65, 106, name, 9.5))
        b.append(text(x + 65, 126, s, 11, bold=True, fill="#4a7c59" if s == "✓" else ORANGE))
    # 最后两周
    b.append(hand_rect(60, 170, 460, 200, fill=BLUE, opacity=0.25))
    b.append(text(290, 196, "第 24 周（D162~168）面试转化", 13, bold=True))
    lines = ["D162 多层 IR/MLIR/SSA 标答", "D163 融合/Layout/正确性标答",
             "D164 动态 Shape/Runtime 标答", "D165 Tiling/内存/性能标答",
             "D166 调试/数值标答", "D167 20 分钟模拟讲解", "D168 最终验收"]
    y = 222
    for line in lines:
        b.append(text(290, y, line, 10))
        y += 20
    b.append(hand_rect(560, 170, 460, 200, fill=PURPLE, opacity=0.22))
    b.append(text(790, 196, "第 23 周的成果（五份文档）", 13, bold=True))
    docs = ["architecture.txt（架构）", "pass-*.md ×4（Pass 文档）",
            "lowering-doc.md（Lowering）", "test-doc.md（测试）",
            "perf-summary.json（性能）", "——「他人能理解、能验证」"]
    y = 222
    for line in docs:
        b.append(text(790, y, line, 10))
        y += 20
    b.append(hand_rect(60, 390, 960, 56, fill="#F5E9C8", opacity=0.85))
    b.append(text(W/2, 414, "168 天的最后冲刺：第 23 周把项目变成资产、第 24 周把能力变成表达", 12, bold=True))
    b.append(text(W/2, 436, "——面试转化不是背答案，是把 22 周的实测经历组织成可复述的标准回答", 10.5))
    save("03-final.svg", "".join(b), h=460)

if __name__ == "__main__":
    fig1()
    fig2()
    fig3()
