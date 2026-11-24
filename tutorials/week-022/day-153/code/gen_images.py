#!/usr/bin/env python3
"""第 153 天 3 张 SVG。种子 153。"""
from __future__ import annotations
import math, os, random
import xml.sax.saxutils as su
random.seed(153)
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
    b.append(text(W/2, 34, "性能反例：三个候选与一个意外发现（反例是环境函数）", 15, bold=True))
    ces = [
        ("CE1 O2 小 shape 反例", "D125（LLVM 18）：慢 60% ✓\n本机（LLVM 23）：快 22% ✗\n→ 反例是版本函数！", ORANGE),
        ("CE2 K 太小收益存疑", "64×160×32：1.7×\n（中位 9.4× 的 1/5）\n→ 收益存疑但不为负", BLUE),
        ("CE3 tile 负优化", "160³ tile(64,64)：0.3×\n重复计算 ×6.25\n→ 比朴素慢 3 倍（铁证）", RED),
    ]
    for i, (name, body, color) in enumerate(ces):
        x = 60 + i * 330
        b.append(hand_rect(x, 60, 300, 170, fill=color, opacity=0.32))
        b.append(text(x + 150, 88, name, 12, bold=True))
        for j, line in enumerate(body.split("\n")):
            b.append(text(x + 150, 112 + j*22, line, 10))
    # 意外发现
    b.append(hand_rect(60, 250, 960, 130, fill="#F5E9C8", opacity=0.85))
    b.append(text(W/2, 276, "今天最大的发现：反例本身是环境函数", 13.5, bold=True))
    lines = [
        "D125 的 -O2 小 kernel 反例（LLVM 18/aarch64 Linux：慢 60%）在今天的 LLVM 23/macOS arm64 上不复现（反而快 22%）——",
        "编译器版本的展开启发式不同——LLVM 23 对小 kernel 的展开收敛了。",
        "教训：反例的适用条件必须带环境声明——「LLVM 18 的小 kernel 展开反例」≠「所有环境的小 kernel 反例」",
    ]
    for j, line in enumerate(lines):
        b.append(text(W/2, 302 + j*22, line, 10.5))
    # 底部
    b.append(hand_rect(60, 400, 960, 66, fill=PURPLE, opacity=0.25))
    b.append(text(W/2, 424, "没有反例的优化报告是广告，有反例的才是工程——", 12, bold=True))
    b.append(text(W/2, 448, "今天再加半句：反例也要带环境戳（版本/平台）——跨环境复用反例与复用优化一样危险", 10.5))
    save("01-three-ces.svg", "".join(b), h=480)

def fig2():
    b = []
    b.append(text(W/2, 34, "CE3 主案例解剖：教学 tile 为什么负优化", 16, bold=True))
    b.append(hand_rect(60, 60, 460, 280, fill=RED, opacity=0.25))
    b.append(text(290, 86, "现象与机制", 13, bold=True))
    lines = [
        "现象：160³ tile(64,64) = 93.95ms",
        "      朴素 O0 = 25.36ms → 0.3×（慢 3 倍）",
        "",
        "机制：点循环从块内起点到全局边界",
        "      每点被 (M/TM)² 个块重复计算",
        "      tile=(64,64)：160/64≈2.5 → 6.25×",
        "      tile=(16,16)：160/16=10 → 100×！",
        "",
        "代价对比：复用省的访存（~2×）",
        "          < 重复付的计算（6.25~100×）",
    ]
    y = 112
    for line in lines:
        if line:
            b.append(text(290, y, line, 10.5, mono=("×" in line or "ms" in line),
                          fill=RED if "×" in line and "复用" not in line else INK))
        y += 22
    b.append(hand_rect(560, 60, 460, 280, fill="#F5E9C8", opacity=0.85))
    b.append(text(790, 86, "适用条件与教训", 13, bold=True))
    lines2 = [
        "适用条件（tile 化有益的前提）：",
        "  ① 块内边界完整（min 钳制——无重复）",
        "  ② 块内数据装得下 cache（复用真实发生）",
        "  ③ 重复率 = 1（每点恰好一次）",
        "",
        "教学版的教训：",
        "  · D146 验收 10/10 全过——机制正确",
        "  · D151 实测 0.3×——性能负优化",
        "  · 「正确」与「快」是两个独立维度",
        "  · 性能验收（D146 ④）当时用产物差异",
        "    代替了性能对照——这个妥协的账今天结清",
    ]
    y = 112
    for line in lines2:
        if line:
            b.append(text(790, y, line, 10.5))
        y += 22
    save("02-ce3-anatomy.svg", "".join(b), h=370)

def fig3():
    b = []
    b.append(text(W/2, 34, "适用条件文档（applicability.txt 的精华）", 16, bold=True))
    zones = [
        ("收益区（建议开）", "K ≥ 64｜计算量 ≥ 1 MFLOP\n实测：64³+ 方阵 7~14×", GREEN),
        ("存疑区（测了再定）", "K ∈ [16, 64]\n实测：64×160×32 只 1.7×", ORANGE),
        ("反例区（环境依赖）", "K < 16＋小计算量\nLLVM 18 慢 60%｜LLVM 23 快 22%\n→ 带环境戳！", RED),
    ]
    for i, (name, body, color) in enumerate(zones):
        x = 60 + i * 330
        b.append(hand_rect(x, 60, 300, 160, fill=color, opacity=0.32))
        b.append(text(x + 150, 88, name, 12.5, bold=True))
        for j, line in enumerate(body.split("\n")):
            b.append(text(x + 150, 112 + j*22, line, 10))
    # 判据
    b.append(hand_rect(60, 240, 960, 100, fill="#F5E9C8", opacity=0.85))
    b.append(text(W/2, 266, "一行判据", 13, bold=True))
    b.append(text(W/2, 290, "展开的收益 ≈ K × 每圈控制开销；展开的代价 ≈ 代码体积增量 × 取指/缓存代价", 11.5))
    b.append(text(W/2, 316, "K 大且计算密集 → 收益胜；K 小且计算稀疏 → 代价胜——而「大/小」的边界本身随编译器版本漂移", 10.5))
    # 明天
    b.append(hand_rect(60, 360, 960, 70, fill=BLUE, opacity=0.28))
    b.append(text(W/2, 386, "明天 D154 第 22 周复盘：瓶颈→假设→优化→验证→范围的完整闭环报告", 12, bold=True))
    b.append(text(W/2, 410, "本周的归因链全部走完——五步每步都有实测数据，从 20.9ms 到「什么时候不该优化」的边界文档", 10.5))
    save("03-applicability.svg", "".join(b), h=450)

if __name__ == "__main__":
    fig1()
    fig2()
    fig3()
