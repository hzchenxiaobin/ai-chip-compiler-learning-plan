#!/usr/bin/env python3
"""第 145 天 3 张 SVG。种子 145。"""
from __future__ import annotations
import math, os, random
import xml.sax.saxutils as su
random.seed(145)
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
    b.append(text(W/2, 34, "四个集成点全通＋一个真 bug 的发现与修复", 16, bold=True))
    cards = [
        ("I1 tile 端到端", "CLI→生成器→IR\n三种 tile 全过", GREEN),
        ("I2 分发 key 扩展", "(shape,tile) 二元组\n3 特化全对", GREEN),
        ("I3 fuzz 扩容", "30 组随机×轮换 tile\n30/30 全对", GREEN),
        ("I4 全管道数值", "IR→pass→执行→golden\nallclose 全过", GREEN),
    ]
    for i, (name, body, color) in enumerate(cards):
        x = 60 + i * 245
        b.append(hand_rect(x, 60, 225, 130, fill=color, opacity=0.35))
        b.append(text(x + 112, 88, name, 12.5, bold=True))
        for j, line in enumerate(body.split("\n")):
            b.append(text(x + 112, 112 + j*22, line, 10))
    # bug 卡
    b.append(hand_rect(60, 220, 960, 180, fill=RED, opacity=0.25))
    b.append(text(W/2, 248, "集成测试抓到的真 bug：k0 块的部分和覆盖", 13.5, bold=True, fill=RED))
    lines = [
        "现象：数值全错（out[0][0]=11.6 vs golden 22.1——差值恰好是部分和）",
        "根因：内层 k 循环从 %k0 出发（块内起点）——每个 k0 块只算 k≥k0 的尾巴，",
        "      多个 k0 块重复写同一点、最后写的块只含部分 k → 部分和覆盖完整和！",
        "修复：内层 k 从 %c0（完整 K 累加）——每点独立完整算，重复块写同值（幂等成立）",
        "教训：D143 的幂等论证有漏洞（「重复写同值」要求每块算出同值——k0 起点破坏了这一点）",
    ]
    y = 274
    for line in lines:
        b.append(text(100, y, line, 10.5, anchor="start",
                      fill=RED if "根因" in line or "覆盖" in line else INK))
        y += 22
    b.append(hand_rect(60, 420, 960, 56, fill="#F5E9C8", opacity=0.85))
    b.append(text(W/2, 444, "「集成不改旧」红线检查：tile=None 朴素路径零变化（D124 测试不受影响）", 11.5, bold=True))
    b.append(text(W/2, 464, "组合测试的价值：单独测生成器全对、接进全管道立刻抓到 k0 bug——组合是新的失败面", 10.5))
    save("01-integrate.svg", "".join(b), h=490)

def fig2():
    b = []
    b.append(text(W/2, 34, "bug 解剖：部分和覆盖的机制", 16, bold=True))
    # 循环结构对比
    b.append(hand_rect(60, 60, 460, 260, fill=RED, opacity=0.25))
    b.append(text(290, 86, "错误版（D143~144）", 13, bold=True, fill=RED))
    wrong = [
        "scf.for %k0 = ... step %cTK {      // k0 外层块",
        "  scf.for %i ... {",
        "    %acc = scf.for %k = %k0 to %cK  // ← 从 k0 出发！",
        "    // k0=0 块：算 k=0..5（完整）",
        "    // k0=3 块：算 k=3..5（尾巴！）",
        "    // store ← 每块都写！",
        "}}",
        "→ 最后写的 k0=3 块只含 k≥3 的部分和",
    ]
    y = 112
    for line in wrong:
        b.append(text(90, y, line, 10, mono=True, anchor="start",
                      fill=RED if "尾巴" in line or "部分" in line or "←" in line else INK))
        y += 22
    b.append(hand_rect(560, 60, 460, 260, fill=GREEN, opacity=0.3))
    b.append(text(790, 86, "修复版（今天）", 13, bold=True, fill="#4a7c59"))
    fixed = [
        "scf.for %k0 = ... step %cTK {      // k0 外层块仍在",
        "  scf.for %i ... {",
        "    %acc = scf.for %k = %c0 to %cK  // ← 从 0 出发！",
        "    // 每个块都算完整 K",
        "    // store ← 重复块写同值",
        "}}",
        "",
        "→ 幂等成立：任何块写出同值＝正确",
    ]
    y = 112
    for line in fixed:
        if line:
            b.append(text(590, y, line, 10, mono=True, anchor="start",
                          fill="#4a7c59" if "同值" in line or "正确" in line or "0 出发" in line else INK))
        y += 22
    # 底部
    b.append(hand_rect(60, 340, 960, 80, fill="#F5E9C8", opacity=0.85))
    b.append(text(W/2, 366, "幂等论证的正确前提：每个块必须「独立算出与朴素版相同的值」", 12, bold=True))
    b.append(text(W/2, 390, "k 从 k0 出发破坏前提（每块算不同的部分）；k 从 0 出发恢复前提（每块算完整值）——D143 的论证漏洞今天补上", 10.5))
    save("02-bug.svg", "".join(b), h=440)

def fig3():
    b = []
    b.append(text(W/2, 34, "第 21 周进度：D146 验收前夜", 16, bold=True))
    week = [
        ("D141", "唯一目标", "块循环 Tiling 选定", "✓"),
        ("D142", "实现方案", "蓝图过管道＋三零修改", "✓"),
        ("D143", "最小正向", "生成器＋差异可 grep", "✓"),
        ("D144", "约束失败", "5 负例＋3 极端全过", "✓"),
        ("D145", "集成", "四点全通＋k0 bug 修复", "✓ 今天"),
        ("D146", "验收", "5正/3负/2边界", "明天"),
        ("D147", "复盘", "删分支＋可维护", "后天"),
    ]
    for i, (d, name, note, status) in enumerate(week):
        y = 60 + i * 82
        color = GREEN if status == "✓" else (ORANGE if "今天" in status else PURPLE)
        b.append(hand_rect(60, y, 960, 70, fill=color, opacity=0.3))
        b.append(text(120, y + 28, d, 12.5, bold=True))
        b.append(text(120, y + 50, status, 11, bold=True,
                      fill="#4a7c59" if status == "✓" else ORANGE))
        b.append(text(380, y + 30, name, 11.5))
        b.append(text(680, y + 30, note, 10, fill=MUTED))
    b.append(hand_rect(60, 660, 960, 60, fill="#F5E9C8", opacity=0.85))
    b.append(text(W/2, 684, "五天连续绿——扩展周的纪律兑现中；明天的验收清单已定（D141 的完成标准 5 条）", 11.5, bold=True))
    b.append(text(W/2, 706, "k0 bug 的教训也进验收：D146 的负例要含「k 起点回归测试」——bug 修复必须配免疫", 10.5))
    save("03-progress.svg", "".join(b), h=740)

if __name__ == "__main__":
    fig1()
    fig2()
    fig3()
