#!/usr/bin/env python3
"""第 151 天 3 张 SVG。种子 151。"""
from __future__ import annotations
import math, os, random
import xml.sax.saxutils as su
random.seed(151)
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
    b.append(text(W/2, 34, "三实验结果：H1 成立 8.4×、H2 反例 0.3×、组合非正交 2.5×", 15, bold=True))
    rows = [
        ("基线（朴素 O0）", "25.36 ms", "0.323 GF", "——", BLUE),
        ("实验 A：O2 展开", "3.00 ms", "2.727 GF", "8.4× ✓H1 成立", GREEN),
        ("实验 B：tile(64,64)", "93.95 ms", "0.087 GF", "0.3× ✗H2 反例", RED),
        ("实验 C：O2＋tile", "9.96 ms", "0.823 GF", "2.5× 非正交", ORANGE),
    ]
    y = 60
    for name, ms, gf, verdict, color in rows:
        b.append(hand_rect(60, y, 960, 76, fill=color, opacity=0.3))
        b.append(text(220, y + 26, name, 12, bold=True))
        b.append(text(480, y + 26, ms, 12, mono=True))
        b.append(text(650, y + 26, gf, 11, mono=True))
        b.append(text(860, y + 26, verdict, 11, bold=True,
                      fill="#4a7c59" if "✓" in verdict else RED))
        b.append(text(220, y + 54, "正确性 ✓" if "基线" not in name else "D148 口径复现", 9.5, fill=MUTED))
        y += 84
    # 底部
    b.append(hand_rect(60, y + 6, 960, 70, fill="#F5E9C8", opacity=0.85))
    b.append(text(W/2, y + 32, "假设检验的完整闭环：H1 成立（循环开销是主因）、H2 被证伪（教学 tile 的重复计算抵消复用收益）——", 11.5, bold=True))
    b.append(text(W/2, y + 54, "证伪同样是结论：它告诉我们「这个 tile 实现不能带来收益」——D153 的反例素材已就位", 10.5))
    save("01-results.svg", "".join(b), h=y + 90)

def fig2():
    b = []
    b.append(text(W/2, 34, "H2 反例的解剖：教学 tile 为什么慢 3 倍？", 16, bold=True))
    # 机制
    b.append(hand_rect(60, 60, 960, 200, fill=RED, opacity=0.22))
    b.append(text(W/2, 86, "重复计算——D145 已知的教学取舍在今天显形", 13, bold=True, fill=RED))
    lines = [
        "教学 tile（D143~D146）：点循环从块内起点到全局边界——重复块写同值（幂等正确）",
        "代价：tile=(64,64) 下每个点被 (160/64)² ≈ 6.25 个块重复计算——计算量 ×6.25！",
        "tile=(16,16) 更惨：(160/16)² = 100 个块重复——每点算 100 次 → 645ms（25×慢）",
        "",
        "复用的收益（省访存）< 重复的代价（多计算）——净效果：慢 3~25 倍",
    ]
    y = 112
    for line in lines:
        if line:
            b.append(text(100, y, line, 10.5, anchor="start",
                          fill=RED if "×" in line or "慢" in line else INK))
        y += 22
    # 完整版对照
    b.append(hand_rect(60, 280, 960, 140, fill="#F5E9C8", opacity=0.85))
    b.append(text(W/2, 306, "如果做完整版（块内边界 min 钳制）会怎样？", 12.5, bold=True))
    lines2 = [
        "完整版：内层 i/j 只跑 [i0, min(i0+TM,M))——每点恰好算一次（无重复）",
        "此时 tile 的收益（B 块在 L1 的复用）才能兑现——教学取舍的性能账今天结清",
        "诚实结论：教学版验证了「tile 机制正确」（D146 的 10/10），但性能验证需要完整版",
        "——这是 D153 反例的核心素材：「优化方向对、实现不完整时可能更慢」",
    ]
    y = 330
    for line in lines2:
        b.append(text(100, y, line, 10.5, anchor="start"))
        y += 22
    save("02-h2-anatomy.svg", "".join(b), h=440)

def fig3():
    b = []
    b.append(text(W/2, 34, "明天 D152：跨 Shape 验证——不只报最好结果", 16, bold=True))
    # 今天 vs 明天
    b.append(hand_rect(60, 60, 460, 220, fill=GREEN, opacity=0.3))
    b.append(text(290, 88, "今天（单 shape 160³）", 12.5, bold=True))
    lines1 = ["O2 展开：8.4× ✓", "tile：0.3× ✗", "组合：2.5×（tile 拖累）", "", "结论只对 160³ 成立"]
    y = 114
    for line in lines1:
        if line:
            b.append(text(290, y, line, 11))
        y += 22
    b.append(hand_rect(560, 60, 460, 220, fill=ORANGE, opacity=0.3))
    b.append(text(790, 88, "明天（≥6 个 shape）", 12.5, bold=True))
    lines2 = ["O2 的 8.4× 在小 shape 还成立吗？", "（K 小时展开收益递减——D125 的 4³ 反例）",
              "tile 的 0.3× 在哪些 shape 反转？", "（重复率 = (M/TM)² 随 M 变）", "",
              "跨 shape 表 = 优化的适用范围图"]
    y = 114
    for line in lines2:
        if line:
            b.append(text(790, y, line, 10.5))
        y += 22
    # 底部
    b.append(hand_rect(60, 300, 960, 70, fill="#F5E9C8", opacity=0.85))
    b.append(text(W/2, 326, "「不能只报最好结果」的含义：", 12, bold=True))
    b.append(text(W/2, 350, "单一 shape 的加速比是轶事；跨 shape 的加速比分布才是结论——范围、均值、最差值三个数都要报", 10.5))
    save("03-tomorrow.svg", "".join(b), h=390)

if __name__ == "__main__":
    fig1()
    fig2()
    fig3()
