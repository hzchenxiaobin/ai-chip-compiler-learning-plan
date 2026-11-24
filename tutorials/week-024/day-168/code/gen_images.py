#!/usr/bin/env python3
"""第 168 天 3 张 SVG。种子 168。"""
from __future__ import annotations
import math, os, random
import xml.sax.saxutils as su
random.seed(168)
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
    b.append(text(W/2, 34, "最终验收：九项能力全部 ✓（9/9）", 16, bold=True))
    checks = [
        ("① 图编译器", "D57~112＋D121 五闸"),
        ("② Lowering 执行", "D113~118 七层＋12/12"),
        ("③ 统一入口", "D120~126 minic＋108 项"),
        ("④ Runtime 三件套", "D127~133 特化/回退/池化"),
        ("⑤ 测试回归体系", "D134~140 金字塔＋v0.5.0"),
        ("⑥ 扩展开发", "D141~147 块循环＋10/10"),
        ("⑦ 性能归因", "D148~154 五步＋反例"),
        ("⑧ 项目资产", "D155~161 五文档＋8/8"),
        ("⑨ 面试表达", "D162~167 标答＋五幕"),
    ]
    for i, (name, ev) in enumerate(checks):
        x = 60 + (i % 3) * 330
        y = 60 + (i // 3) * 100
        b.append(hand_rect(x, y, 300, 88, fill=GREEN, opacity=0.35))
        b.append(text(x + 150, y + 26, name, 12, bold=True))
        b.append(text(x + 150, y + 50, ev, 9.5, fill=MUTED))
        b.append(text(x + 150, y + 72, "✓", 13, bold=True, fill="#4a7c59"))
    b.append(hand_rect(60, 380, 960, 66, fill="#F5E9C8", opacity=0.85, sw=2))
    b.append(text(W/2, 406, "验收 9/9 全过——从「能写出 mini 编译器」到「能做面试表达」的完整闭环", 13, bold=True))
    b.append(text(W/2, 430, "168 篇教程｜≈250 项测试判定｜v0.5.0 冻结版｜五份文档｜十份标答", 11))
    save("01-checklist.svg", "".join(b), h=460)

def fig2():
    b = []
    b.append(text(W/2, 34, "168 天的六个阶段：能力的阶梯", 16, bold=True))
    phases = [
        ("阶段一 D1~28", "C++/编译器基础", "环境/语言基础/开源编译器概览", GREEN),
        ("阶段二 D29~56", "MLIR 核心", "Dialect/Pass/Pattern/Conversion", GREEN),
        ("阶段三 D57~84", "图算子与优化", "Shape/Layout/融合/Cost Model", BLUE),
        ("阶段四 D85~112", "Lowering/Tiling/性能", "循环/内存/调优/集成验收", ORANGE),
        ("阶段五 D113~140", "端到端与 Runtime", "Lowering 执行/入口/Runtime/质量", RED),
        ("阶段六 D141~168", "扩展/归因/文档/面试", "Tiling 扩展/性能归因/资产/表达", PURPLE),
    ]
    for i, (name, topic, note, color) in enumerate(phases):
        x = 40 + i * 170
        b.append(hand_rect(x, 60, 155, 160, fill=color, opacity=0.35))
        b.append(text(x + 77, 86, name, 11, bold=True))
        b.append(text(x + 77, 108, topic, 10))
        b.append(text(x + 77, 130, note, 8.5, fill=MUTED))
        if i < 5:
            b.append(hand_rect(x + 157, 120, 14, 30, fill=INK, opacity=0.4))
    # 阶梯上升
    b.append(hand_rect(60, 240, 960, 60, fill="#F5E9C8", opacity=0.85))
    b.append(text(W/2, 264, "能力的阶梯：每一阶段都建在前一阶段的地基上——没有跳级也没有回头", 12, bold=True))
    b.append(text(W/2, 288, "（阶段五的 Runtime 建在阶段四的 Lowering 上——正如阶段四建在阶段三的图优化上）", 10.5))
    save("02-phases.svg", "".join(b), h=320)

def fig3():
    b = []
    b.append(text(W/2, 34, "下一阶段：四选一（选定 MLIR 图编译）＋四周计划", 16, bold=True))
    dirs = [
        ("MLIR 图编译 ✓", "linalg/transform 方言\nminic 前端的工业版", GREEN),
        ("LLVM 后端", "TableGen/指令选择/调度\nD118 执行层的下一层", BLUE),
        ("自动调度", "TVM Ansor/TensorIR\nD106~111 搜索的工业版", ORANGE),
        ("芯片工具链", "特定 NPU toolchain\n教学项目的落地形态", PURPLE),
    ]
    for i, (name, body, color) in enumerate(dirs):
        x = 60 + i * 245
        b.append(hand_rect(x, 60, 225, 130, fill=color, opacity=0.35))
        b.append(text(x + 112, 88, name, 11.5, bold=True))
        for j, line in enumerate(body.split("\n")):
            b.append(text(x + 112, 110 + j*20, line, 9.5))
    # 四周计划
    b.append(text(W/2, 226, "四周计划（MLIR 图编译方向）", 13.5, bold=True))
    weeks = [
        ("第 1 周", "linalg 方言——结构化算子的官方表达"),
        ("第 2 周", "transform 方言——可组合的变换语言"),
        ("第 3 周", "tile/schedule——从 tile 参数到调度策略"),
        ("第 4 周", "完整案例——把 minic 的图优化迁移到 linalg"),
    ]
    for i, (w, note) in enumerate(weeks):
        y = 246 + i * 66
        b.append(hand_rect(60, y, 960, 56, fill=GREEN, opacity=0.28))
        b.append(text(140, y + 34, w, 12, bold=True))
        b.append(text(560, y + 34, note, 11))
    b.append(hand_rect(60, 520, 960, 70, fill="#F5E9C8", opacity=0.85, sw=2))
    b.append(text(W/2, 546, "168 天的终点是下一阶段的起点——", 13, bold=True))
    b.append(text(W/2, 570, "知道会什么（九项能力✓）、不会什么（stuck-list×3）、下一步学什么（MLIR 图编译）——完整闭环", 10.5))
    save("03-next.svg", "".join(b), h=610)

if __name__ == "__main__":
    fig1()
    fig2()
    fig3()
