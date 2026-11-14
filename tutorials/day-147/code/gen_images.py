#!/usr/bin/env python3
"""第 147 天 3 张 SVG。种子 147。"""
from __future__ import annotations
import math, os, random
import xml.sax.saxutils as su
random.seed(147)
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
    b.append(text(W/2, 34, "第 21 周复盘：扩展的完整账与主线检验", 16, bold=True))
    days = [("D141", "目标"), ("D142", "方案"), ("D143", "正向"),
            ("D144", "约束"), ("D145", "集成"), ("D146", "验收"), ("D147", "复盘·今天")]
    for i, (d, name) in enumerate(days):
        x = 60 + i * 140
        color = PURPLE if i == 6 else GREEN
        b.append(hand_rect(x, 60, 130, 80, fill=color, opacity=0.35))
        b.append(text(x + 65, 88, d, 12, bold=True))
        b.append(text(x + 65, 110, name, 10))
    # 主线检验
    b.append(text(W/2, 180, "主线检验三问（本周的核心复盘题）", 14, bold=True))
    qs = [
        ("① 能力更强了吗？", "tile 从空变量变真参数——\n产物/分发/验收全链路生效", GREEN),
        ("② 破坏已有功能了吗？", "tile=None 零变化——\nv0.5.0 全部测试不破", GREEN),
        ("③ 删掉会缺什么？", "性能差异的可测性——\nD153 性能归因的实验基础", ORANGE),
    ]
    for i, (q, a, color) in enumerate(qs):
        x = 60 + i * 330
        b.append(hand_rect(x, 200, 300, 130, fill=color, opacity=0.3))
        b.append(text(x + 150, 226, q, 12, bold=True))
        for j, line in enumerate(a.split("\n")):
            b.append(text(x + 150, 250 + j*20, line, 10))
    # 结论
    b.append(hand_rect(60, 356, 960, 70, fill="#F5E9C8", opacity=0.85))
    b.append(text(W/2, 382, "三问的答案：能力增强（是）、无破坏（否）、删掉缺实验基础（缺）——", 12, bold=True))
    b.append(text(W/2, 404, "主线判定：真正增强——块循环不是无关复杂度，是 D125 空变量的正式兑现＋第 22 周的实验素材", 10.5))
    save("01-review.svg", "".join(b), h=450)

def fig2():
    b = []
    b.append(text(W/2, 34, "删代码日：实验分支的检查与结论", 16, bold=True))
    b.append(hand_rect(60, 60, 960, 240, fill=BG, opacity=0.95, sw=1.8))
    b.append(text(W/2, 88, "检查清单（标准：文件被 README/测试引用＝保留）", 12.5, bold=True))
    rows = [
        ("block_tile.py", "D143 生成器 v1——README 5.2 引用", "保留", GREEN),
        ("constraints.py", "v2＋校验——D145/146 复用", "保留", GREEN),
        ("integrate.py", "集成验证——D145 主产出", "保留", GREEN),
        ("accept.py", "正式验收——D146 主产出", "保留", GREEN),
        ("（实验分支）", "——本周无残留", "无需删除", BLUE),
    ]
    y = 112
    for name, why, verdict, color in rows:
        b.append(hand_rect(100, y, 880, 34, fill=color, opacity=0.25))
        b.append(text(280, y + 22, name, 11, mono=True))
        b.append(text(560, y + 22, why, 10))
        b.append(text(880, y + 22, verdict, 10.5, bold=True, fill="#4a7c59"))
        y += 38
    b.append(hand_rect(60, 320, 960, 80, fill="#F5E9C8", opacity=0.85))
    b.append(text(W/2, 346, "结论：无实验分支残留——每天「完成即验收」的节奏红利", 12, bold=True))
    b.append(text(W/2, 370, "诚实声明：这是 D142「先窄后宽」纪律的直接收益——不是设计必然；如果哪周留了半成品，", 10.5))
    b.append(text(W/2, 390, "复盘日的删代码清单就是清偿日——「删除未被使用的实验分支」写进计划是有原因的", 10.5, MUTED))
    save("02-cleanup.svg", "".join(b), h=420)

def fig3():
    b = []
    b.append(text(W/2, 34, "第 22 周预告：完整性能归因（D148~D154）", 16, bold=True))
    week22 = [
        ("D148", "选择慢用例并建立基线", "输入固定、测量口径、可复现命令"),
        ("D149", "拆解编译与运行开销", "编译/搜索/launch/分配/执行的时间分解"),
        ("D150", "分析计算与访存瓶颈", "算术强度、数据复用、Roofline"),
        ("D151", "实施有依据的优化", "针对已确认瓶颈——不是随机尝试"),
        ("D152", "验证优化收益与副作用", "跨 Shape 检查、不只报最好结果"),
        ("D153", "构造性能反例", "优化失效的用例＋适用条件说明"),
        ("D154", "第 22 周复盘", "瓶颈→假设→优化→验证→范围的闭环报告"),
    ]
    for i, (d, name, note) in enumerate(week22):
        y = 60 + i * 88
        color = PURPLE if d == "D154" else (ORANGE if d in ("D151", "D153") else BLUE)
        b.append(hand_rect(60, y, 960, 76, fill=color, opacity=0.3))
        b.append(text(120, y + 28, d, 12.5, bold=True))
        b.append(text(120, y + 52, note, 9.5, fill=MUTED))
        b.append(text(500, y + 38, name, 11.5))
    b.append(hand_rect(60, 700, 960, 50, fill="#F5E9C8", opacity=0.85))
    b.append(text(W/2, 722, "块循环 Tiling 是第 22 周的现成实验素材：tile 参数扫描＝有依据优化的第一实验", 11.5, bold=True))
    b.append(text(W/2, 742, "D153 的性能反例在 D125 已有伏笔（-O2 展开反而慢 60%）——第 22 周给它完整的故事", 10.5, MUTED))
    save("03-week22.svg", "".join(b), h=770)

if __name__ == "__main__":
    fig1()
    fig2()
    fig3()
