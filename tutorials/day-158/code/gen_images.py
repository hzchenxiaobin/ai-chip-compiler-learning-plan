#!/usr/bin/env python3
"""第 158 天 3 张 SVG。种子 158。"""
from __future__ import annotations
import math, os, random
import xml.sax.saxutils as su
random.seed(158)
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
    b.append(text(W/2, 34, "怎么验证这个项目是对的：一页答案", 16, bold=True))
    layers = [
        ("L3 端到端", "输入图→执行→golden\n12/12 bitwise（D124）", "慢（秒）·总闸", RED, 300),
        ("L2 IR 文本", "D123 改写记录\n每条 pass 前后 IR", "中速·锁行为", ORANGE, 500),
        ("L1 单元", "16 例正反集＋200 组随机\n＋48 项扩展验收", "快（µs）·定位准", GREEN, 700),
    ]
    for i, (name, what, prop, color, width) in enumerate(layers):
        y = 60 + i * 110
        x = (W - width) / 2
        b.append(hand_rect(x, y, width, 96, fill=color, opacity=0.4))
        b.append(text(W/2, y + 26, name, 13, bold=True))
        b.append(text(W/2, y + 50, what, 10.5))
        b.append(text(W/2, y + 74, prop, 9.5, fill=MUTED))
    b.append(hand_rect(60, 400, 960, 60, fill="#F5E9C8", opacity=0.85))
    b.append(text(W/2, 424, "金字塔的配比 ≈ 10:3:1——大量快测试打底、少量慢总闸封顶；", 11.5, bold=True))
    b.append(text(W/2, 446, "当前项目：L1 264 例（16+200+48）｜L2 雏形（改写记录）｜L3 1 例（12/12）——底部厚顶部薄", 10.5))
    save("01-pyramid.svg", "".join(b), h=470)

def fig2():
    b = []
    b.append(text(W/2, 34, "一键回归与覆盖总账", 16, bold=True))
    # 命令
    b.append(hand_rect(60, 60, 460, 200, fill=BG, opacity=0.95, sw=1.8))
    b.append(text(290, 86, "四条一键命令", 12.5, bold=True))
    cmds = [
        "全部测试：逐日 run_all.sh",
        "核心链：day-126 干净重建 5/5",
        "性能基线：day-148 baseline.json",
        "四维验收：day-139 冻结 7/7",
    ]
    y = 112
    for c in cmds:
        b.append(text(290, y, c, 10.5, mono=True))
        y += 24
    # 覆盖
    b.append(hand_rect(560, 60, 460, 200, fill=BLUE, opacity=0.28))
    b.append(text(790, 86, "覆盖范围（六面）", 12.5, bold=True))
    covs = ["图优化 S1｜循环 S2（fuzz）", "Lowering S4（胶水 0）", "执行 S6（12/12）",
            "分发（四路径）｜内存（99%）", "性能（基准/分布/反例）", "诊断（E1/E2/E3×16 条）"]
    y = 112
    for c in covs:
        b.append(text(790, y, c, 10))
        y += 22
    # 总账
    b.append(hand_rect(60, 280, 960, 130, fill="#F5E9C8", opacity=0.85))
    b.append(text(W/2, 306, "数字总账（五周 ≈250 项 PASS 判定）", 13, bold=True))
    weeks = [("18 周", "108"), ("19 周", "40"), ("20 周", "25"), ("21 周", "48"), ("22 周", "~30")]
    for i, (w, n) in enumerate(weeks):
        x = 180 + i * 165
        b.append(hand_rect(x, 322, 150, 60, fill=GREEN, opacity=0.4))
        b.append(text(x + 75, 346, n, 15, bold=True))
        b.append(text(x + 75, 368, f"第 {w}", 9.5, MUTED))
    # 缺口
    b.append(hand_rect(60, 430, 960, 100, fill=RED, opacity=0.18))
    b.append(text(W/2, 456, "当前缺口（诚实清单×4）", 12, bold=True))
    gaps = "完整 tile 块内边界｜并发（池的锁）｜JIT 端到端｜性能回归 CI"
    b.append(text(W/2, 480, "×".join(gaps.split("｜")), 10.5))
    b.append(text(W/2, 502, "每个缺口都有出处与排期（future 清单）——已知未知是路线图不是负债表", 10, MUTED))
    save("02-coverage.svg", "".join(b), h=540)

def fig3():
    b = []
    b.append(text(W/2, 34, "明天 D159：性能材料整理", 16, bold=True))
    items = [
        ("数据汇总", "基线/分布/反例的 json 汇一表\n（baseline＋cross-shape＋counterexample）", GREEN),
        ("图表生成", "D148~153 的三张图归档引用\n＋加速分布的柱状图", BLUE),
        ("结论摘要", "五步闭环一句话版\n（20.9ms→8.4×→分布→反例→边界）", ORANGE),
    ]
    for i, (name, body, color) in enumerate(items):
        y = 60 + i * 130
        b.append(hand_rect(60, y, 960, 116, fill=color, opacity=0.28))
        b.append(text(540, y + 26, name, 13, bold=True))
        for j, line in enumerate(body.split("\n")):
            b.append(text(540, y + 52 + j*22, line, 10.5))
    b.append(hand_rect(60, 460, 960, 60, fill="#F5E9C8", opacity=0.85))
    b.append(text(W/2, 484, "性能材料的三要素：数据（json）、图（SVG）、结论（一句话）——", 11.5, bold=True))
    b.append(text(W/2, 506, "「结果必须附输入、配置、环境和统计口径」（计划 D159 原话）——今天的整理正是这一条的兑现", 10.5))
    save("03-tomorrow.svg", "".join(b), h=530)

if __name__ == "__main__":
    fig1()
    fig2()
    fig3()
