#!/usr/bin/env python3
"""第 136 天 3 张 SVG。种子 136。"""
from __future__ import annotations
import math, os, random
import xml.sax.saxutils as su
random.seed(136)
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
        a, b = pts[i], pts[(i + 1) % 4]
        mx, my = (a[0] + b[0]) / 2 + jit(2.2), (a[1] + b[1]) / 2 + jit(2.2)
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
    b.append(text(W/2, 34, "Pass 二分定位：注入错误被精确指认到第 4 条", 16, bold=True))
    # 时间线
    passes = ["canonicalize", "scf→cf", "finalize-memref", "func→llvm",
              "cf→llvm", "arith→llvm", "index→llvm", "reconcile"]
    for i, p in enumerate(passes):
        x = 60 + i * 120
        color = GREEN if i < 3 else (RED if i == 3 else ORANGE)
        b.append(hand_rect(x, 60, 110, 60, fill=color, opacity=0.4))
        b.append(text(x + 55, 84, p, 9.5, bold=(i == 3)))
        mark = "✓" if i < 3 else "✗"
        b.append(text(x + 55, 106, f"语义{mark}", 10, bold=True,
                      fill="#4a7c59" if i < 3 else RED))
        if i == 3:
            b.append(hand_rect(x - 5, 125, 120, 26, fill=RED, opacity=0.5))
            b.append(text(x + 55, 143, "↑注入点·凶手", 9.5, bold=True, fill=RED))
    # 三阶段
    stages = [
        ("B1 基线", "八条全开不注入\n语义好——管道干净", GREEN),
        ("B2 注入", "第 4 条后 addf→subf\n八条全开语义坏", RED),
        ("B3 定位", "前缀递增 0→8\n第 4 条首次变坏\n→ 凶手=convert-func", ORANGE),
    ]
    for i, (name, body, color) in enumerate(stages):
        x = 60 + i * 330
        b.append(hand_rect(x, 180, 300, 120, fill=color, opacity=0.3))
        b.append(text(x + 150, 206, name, 13, bold=True))
        for j, line in enumerate(body.split("\n")):
            b.append(text(x + 150, 230 + j*18, line, 10))
    # 底部效率
    b.append(hand_rect(60, 320, 960, 110, fill="#F5E9C8", opacity=0.8))
    b.append(text(W/2, 346, "定位效率（B4）", 13, bold=True))
    b.append(text(W/2, 370, "暴力（逐条全管道重跑）O(n²)=64 次｜前缀法（本次）36 次｜真二分 ~24 次", 11))
    b.append(text(W/2, 394, "教学规模差距小——真实编译器几百条 pass 时，二分是唯一可行（64→log₂级）", 10.5, fill=MUTED))
    b.append(text(W/2, 446, "调试的黄金假设：错误总在某条 Pass 首次引入（最早语义破坏点）——找到它，后面的全是涟漪", 12, bold=True, fill="#4a7c59"))
    save("01-overview.svg", "".join(b), h=470)

def fig2():
    b = []
    b.append(text(W/2, 34, "前缀递增法的判定序列：✓✓✓✗✗✗✗✗——首次变坏即凶手", 16, bold=True))
    # 判定序列可视化
    seq = [("前0条", True), ("前1条", True), ("前2条", True), ("前3条", True),
           ("前4条", False), ("前5条", False), ("前6条", False), ("前7条", False), ("前8条", False)]
    for i, (label, good) in enumerate(seq):
        x = 60 + i * 108
        color = GREEN if good else RED
        b.append(hand_rect(x, 60, 96, 80, fill=color, opacity=0.4))
        b.append(text(x + 48, 86, label, 10.5, bold=True))
        b.append(text(x + 48, 110, "好 ✓" if good else "坏 ✗", 13, bold=True,
                      fill="#4a7c59" if good else RED))
        if i == 4:
            b.append(hand_rect(x - 4, 148, 104, 26, fill=RED, opacity=0.5))
            b.append(text(x + 48, 166, "首次变坏！", 10, bold=True, fill=RED))
    # 机制解释
    b.append(hand_rect(60, 200, 960, 120, fill=BLUE, opacity=0.25))
    b.append(text(W/2, 226, "为什么「首次变坏」就是凶手？", 13, bold=True))
    lines = [
        "假设：每条 Pass 独立地「保持或破坏」语义（错误不会自我修复——subf 不会变回 addf）",
        "推论：语义是单调的——一旦坏了就一直坏（✓✓✓✗✗✗...）",
        "边界：如果错误会自我修复（后面的 pass 恰好抵消），序列非单调——需要逐条二分而非前缀",
    ]
    for j, line in enumerate(lines):
        b.append(text(W/2, 252 + j*22, line, 10.5))
    # 工具化
    b.append(text(W/2, 360, "今天的工具形态（bisect.py 的复用接口）", 13.5, bold=True))
    b.append(hand_rect(150, 380, 780, 100, fill=BG, opacity=0.95, sw=1.8))
    code = [
        "run_prefix(ir, n_passes=4, inject_at=3)",
        "  → 跑前 4 条 pass；第 3 条（索引）后注入坏值",
        "  → 返回 {ok, semantics_ok, last_pass, note}",
        "调试真实 bug：inject_at=-1（不注入），对「已知坏」的输入二分",
    ]
    y = 402
    for line in code:
        b.append(text(190, y, line, 10.5, mono=True, anchor="start"))
        y += 18
    save("02-mechanism.svg", "".join(b), h=500)

def fig3():
    b = []
    b.append(text(W/2, 34, "定位记录与调试工具的进阶路线", 16, bold=True))
    # 定位记录
    b.append(hand_rect(60, 60, 460, 240, fill=BG, opacity=0.95, sw=1.8))
    b.append(text(290, 86, "定位记录（report.txt 摘录）", 12.5, bold=True))
    rec = [
        "注入：第 4 条 pass 后 addf→subf",
        "全开基线（不注入）：语义好",
        "全开＋注入：语义坏——错误存在",
        "前缀 0~3 条：语义好 ✓✓✓✓",
        "前缀 4 条：语义坏 ✗ ← 首次",
        "结论：凶手 = convert-func-to-llvm",
        "复现：run_prefix(ir, 4, inject_at=3)",
    ]
    y = 112
    for line in rec:
        b.append(text(100, y, line, 10, mono=True, anchor="start",
                      fill=RED if "坏" in line or "凶手" in line else INK,
                      bold="凶手" in line))
        y += 22
    # 进阶
    b.append(hand_rect(560, 60, 460, 240, fill=PURPLE, opacity=0.3))
    b.append(text(790, 86, "调试工具的进阶路线", 12.5, bold=True))
    adv = [
        "① 真二分（好/坏二分搜索）：",
        "   log₂(n) 次判定——pass 数百条时的选择",
        "② 逐条开关（D121 的开关矩阵复用）：",
        "   「关这条还坏吗？」——定位直接凶手",
        "③ IR 快照 diff（D123 改写记录）：",
        "   前后 IR 逐行对比——改了什么一眼见",
        "④ 明天 D137：最小失败用例——",
        "   把坏 IR shrink 到最小——好提交 bug",
    ]
    y = 112
    for line in adv:
        b.append(text(590, y, line, 10, anchor="start"))
        y += 22
    # 底部
    b.append(hand_rect(60, 320, 960, 70, fill="#F5E9C8", opacity=0.8))
    b.append(text(W/2, 346, "调试核心＝定位最早语义破坏点（计划 D140 的总结句）——", 12, bold=True))
    b.append(text(W/2, 368, "二分找到它、改写记录看清它、明天把它的用例缩到最小——三件工具构成调试的完整链条", 10.5))
    save("03-record.svg", "".join(b), h=410)

if __name__ == "__main__":
    fig1()
    fig2()
    fig3()
