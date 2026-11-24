#!/usr/bin/env python3
"""第 143 天 3 张 SVG。种子 143。"""
from __future__ import annotations
import math, os, random
import xml.sax.saxutils as su
random.seed(143)
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
def arrow(x1, y1, x2, y2, stroke=INK, sw=1.8, label=None):
    mx, my = (x1+x2)/2 + jit(2), (y1+y2)/2 + jit(2)
    import math as m
    ang = m.atan2(y2-y1, x2-x1)
    hx, hy = x2-9*m.cos(ang), y2-9*m.sin(ang)
    a1 = (hx+5*m.cos(ang+2.7), hy+5*m.sin(ang+2.7))
    a2 = (hx+5*m.cos(ang-2.7), hy+5*m.sin(ang-2.7))
    d = (f"M {x1+jit():.1f},{y1+jit():.1f} Q {mx:.1f},{my:.1f} "
         f"{x2:.1f},{y2:.1f} M {a1[0]:.1f},{a1[1]:.1f} L {x2:.1f},{y2:.1f} L {a2[0]:.1f},{a2[1]:.1f}")
    out = (f'<path d="{d}" stroke="{stroke}" stroke-width="{sw}" '
           f'stroke-linecap="round" fill="none"/>')
    if label:
        out += text((x1+x2)/2, (y1+y2)/2-8, label, 10.5, MUTED)
    return out
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
    b.append(text(W/2, 34, "最小正向路径：生成器→七 pass→差异可 grep（三证到手）", 16, bold=True))
    steps = [
        ("① 生成", "gen_block_ir(g, tile=(2,2,3))\n55 行块循环 IR\ntile 壳三层＋点循环", GREEN),
        ("② 管道", "七 pass 全通 ✓\n胶水 0\n蓝图形态合法（D142 已验）", GREEN),
        ("③ 差异", "phi 计数：tile 版 7\nvs 朴素版 4（差 3=\ntile 壳循环变量）", ORANGE),
        ("④ 参数", "%cTM = arith.constant 2\n在 IR 里 ✓\ntile 参数真实生效", RED),
    ]
    for i, (name, body, color) in enumerate(steps):
        x = 50 + i * 250
        b.append(hand_rect(x, 60, 230, 160, fill=color, opacity=0.35))
        b.append(text(x + 115, 88, name, 13, bold=True))
        for j, line in enumerate(body.split("\n")):
            b.append(text(x + 115, 114 + j*22, line, 10))
    b.append(hand_rect(60, 250, 960, 90, fill="#F5E9C8", opacity=0.85))
    b.append(text(W/2, 276, "「tile 参数真实生效」的两个证据今天齐了：", 12.5, bold=True))
    b.append(text(W/2, 300, "①产物差异可 grep（phi 7 vs 4——tile 壳的多余循环变量是指纹）②tile 常量进 IR（%cTM=2 可直接看到）", 10.5))
    b.append(text(W/2, 322, "正确性（bitwise）留 D144/D146 的 S6 接入——今天的形态验证：迭代覆盖与朴素版一一对应（幂等写）", 10.5, MUTED))
    save("01-forward.svg", "".join(b), h=350)

def fig2():
    b = []
    b.append(text(W/2, 34, "生成器解剖：块循环的四层嵌套", 16, bold=True))
    b.append(hand_rect(60, 60, 560, 420, fill=BG, opacity=0.95, sw=1.8))
    code = [
        ("scf.for %i0 = %c0 to %cM step %cTM {", "外层 tile 壳 M", GREEN),
        ("  scf.for %j0 = %c0 to %cN step %cTN {", "tile 壳 N", GREEN),
        ("    scf.for %k0 = %c0 to %cK step %cTK {", "tile 壳 K", GREEN),
        ("      scf.for %i = %i0 to %cM step %c1 {", "点循环 i（块内起点）", BLUE),
        ("        scf.for %j = %j0 to %cN step %c1 {", "点循环 j", BLUE),
        ("          %acc = scf.for %k = %k0 to %cK ...", "点循环 k（累加）", ORANGE),
        ("            %aij = load %a[%i, %k]", "", BLUE),
        ("            %p = mulf %aij, %bkj", "", BLUE),
        ("            %s = addf %acc, %p", "", BLUE),
        ("          memref.store %r, %c[%i, %j]", "写回", RED),
        ("}}}}}}", "", MUTED),
    ]
    y = 90
    for line, note, color in code:
        b.append(text(90, y, line, 10.5, mono=True, anchor="start",
                      fill=color if color != MUTED else INK))
        if note:
            b.append(text(560, y, note, 9.5, fill=MUTED))
        y += 32
    # 右侧解读
    b.append(hand_rect(660, 60, 360, 420, fill=PURPLE, opacity=0.28))
    b.append(text(840, 86, "四层的语义", 13, bold=True))
    notes = [
        "外三层（壳）：以 tile 为步长扫过\nM/N/K——决定「块边界」",
        "内三层（点）：块内起点出发、\n全局边界结束——算每个点",
        "教学简化：点循环用全局边界\n（而非 min(i0+TM,M)）——",
        "正确性保证：每点恰好算一次\n（重复块写同值＝幂等）",
        "效率取舍：完整版应块内边界\n（少算重复点）——D146 对照",
    ]
    y = 112
    for note in notes:
        for line in note.split("\n"):
            b.append(text(840, y, line, 10))
            y += 18
        y += 8
    b.append(hand_rect(60, 500, 960, 60, fill="#F5E9C8", opacity=0.85))
    b.append(text(W/2, 524, "教学取舍的诚实声明：块内边界（min 钳制）是完整版——今天先全局边界保正确，", 11.5, bold=True))
    b.append(text(W/2, 546, "幂等写让任何 tile 组合都算对（重复计算写同值）；效率差异留 D146 的性能对照诚实呈现", 10.5))
    save("02-anatomy.svg", "".join(b), h=580)

def fig3():
    b = []
    b.append(text(W/2, 34, "从蓝图到生成器：今天的增量与明天的路", 16, bold=True))
    # 今天增量
    b.append(hand_rect(60, 60, 460, 240, fill=GREEN, opacity=0.3))
    b.append(text(290, 88, "今天的增量（~120 行）", 13, bold=True))
    incs = [
        "gen_block_ir(g, tile) 生成器",
        "  · shape 推断复用（_shape_of）",
        "  · tile 常量三连（%cTM/TN/TK）",
        "  · 四层嵌套的字符串模板",
        "  · bias/relu 语义与朴素版一致",
        "蓝图（D142 手写样例）→ 生成器",
        "  （任意 shape×tile 组合）",
    ]
    y = 114
    for line in incs:
        b.append(text(290, y, line, 10, mono=("gen_" in line or "%" in line)))
        y += 20
    # 明天
    b.append(hand_rect(560, 60, 460, 240, fill=ORANGE, opacity=0.3))
    b.append(text(790, 88, "明天 D144：约束与失败路径", 13, bold=True))
    tomorrows = [
        "· 块内边界 min(i0+TM, M) 完整版",
        "  （消除重复计算——效率正确性双赢）",
        "· 负例测试：tile=(0,2,3) 拒收",
        "  tile 负数拒收、非整拒收",
        "· 边界三极端：tile=(1,1,1)/",
        "  tile=shape/tile>shape",
        "· fuzz 接入：200 组×多 tile",
    ]
    y = 114
    for line in tomorrows:
        b.append(text(790, y, line, 10))
        y += 20
    # 底部
    b.append(hand_rect(60, 320, 960, 70, fill="#F5E9C8", opacity=0.85))
    b.append(text(W/2, 346, "扩展周的第三天节奏检查：最小正向已通——没有提前做 D144 的约束（忍住了）", 11.5, bold=True))
    b.append(text(W/2, 368, "「先窄后宽」的纪律：今天只求「能跑出差异」，约束/边界/优化全部后置——一天一步", 10.5))
    save("03-next.svg", "".join(b), h=400)

if __name__ == "__main__":
    fig1()
    fig2()
    fig3()
