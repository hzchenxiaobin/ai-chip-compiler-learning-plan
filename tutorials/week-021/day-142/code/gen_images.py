#!/usr/bin/env python3
"""第 142 天 3 张 SVG。种子 142。"""
from __future__ import annotations
import math, os, random
import xml.sax.saxutils as su
random.seed(142)
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
    b.append(text(W/2, 34, "实现方案：五个面的影响分析（三个零修改）", 16, bold=True))
    faces = [
        ("IR", "S2 生成新形态：\n块循环壳＋点循环\n（新增代码的主战场）", ORANGE),
        ("Pass", "零修改！\nscf→cf/memref/func\n对循环层数无感", GREEN),
        ("Lowering", "零修改\n（同上——pass 不挑循环）", GREEN),
        ("Runtime", "零修改\nciface 签名不变\ntile 是编译期决策", GREEN),
        ("测试", "fuzz 沿用（块循环也过）\n＋tile 对照新增", BLUE),
    ]
    for i, (name, body, color) in enumerate(faces):
        x = 50 + i * 200
        b.append(hand_rect(x, 60, 180, 150, fill=color, opacity=0.35))
        b.append(text(x + 90, 88, name, 13, bold=True))
        for j, line in enumerate(body.split("\n")):
            b.append(text(x + 90, 112 + j*20, line, 9.5))
    b.append(hand_rect(60, 240, 960, 80, fill="#F5E9C8", opacity=0.85))
    b.append(text(W/2, 266, "三个零修改是本周最大的好消息：块循环只动 S2 生成器一个文件——", 12, bold=True))
    b.append(text(W/2, 288, "「新 IR 形态落在已有 pass 的能力圈内」是设计阶段的最重要的验证（今天蓝图已过管道证明这一点）", 10.5))
    # 蓝图
    b.append(text(W/2, 356, "蓝图样例（4x6x3, tile=2,2,3）——今天已过七 pass", 13.5, bold=True))
    b.append(hand_rect(150, 376, 780, 140, fill=BG, opacity=0.95, sw=1.8))
    code = [
        "scf.for %i0 = %c0 to %cM step %cTM {     // 外层 tile 壳",
        "  scf.for %j0 = ... step %cTN {",
        "    scf.for %k0 = ... step %cTK {",
        "      scf.for %i = %i0 to %ihi step %c1 {   // 内层点循环",
        "        ... load/mulf/addf/store ...",
        "}}}}                                      // 四层嵌套（朴素版两层）",
    ]
    y = 398
    for line in code:
        b.append(text(180, y, line, 10, mono=True, anchor="start"))
        y += 19
    save("01-faces.svg", "".join(b), h=540)

def fig2():
    b = []
    b.append(text(W/2, 34, "修改点与数据流：只动一个文件的一个函数", 16, bold=True))
    b.append(hand_rect(60, 60, 960, 200, fill=BG, opacity=0.95, sw=1.8))
    b.append(text(540, 88, "数据流（不变）与修改点（唯一）", 12.5, bold=True))
    flow = [("graph", GREEN), ("→S1", GREEN), ("→S2 ★唯一修改", RED), ("→S4", GREEN), ("→S5", GREEN), ("→S6", GREEN)]
    x = 130
    for name, color in flow:
        w = 170 if "★" in name else 90
        b.append(hand_rect(x, 110, w, 40, fill=color, opacity=0.4 if "★" not in name else 0.6))
        b.append(text(x + w/2, 135, name, 10.5, bold=True))
        x += w + 18
    b.append(text(540, 190, "e2e.py 的 gen_loop_ir_full(g, tile=None)：", 11, mono=True, anchor="start"))
    b.append(text(540, 212, "  tile=None 或 tile==shape → 朴素版（向后兼容，D124 的全部测试不破）", 10, anchor="start"))
    b.append(text(540, 234, "  tile 给定 → 块循环版（外层壳＋min 钳制边界）", 10, anchor="start"))
    # 切片
    b.append(text(W/2, 300, "最小可运行切片（D143 的目标）", 13.5, bold=True))
    b.append(hand_rect(200, 320, 680, 100, fill=ORANGE, opacity=0.3))
    lines = [
        "① gen_loop_ir_full(g, tile=(2,2,3)) 生成蓝图形态",
        "② 七 pass 全通（今天蓝图已验证）",
        "③ 与朴素版 bitwise 对照（同 golden）——正确性第一关",
    ]
    y = 346
    for line in lines:
        b.append(text(540, y, line, 11, anchor="start"))
        y += 24
    b.append(hand_rect(60, 446, 960, 56, fill="#F5E9C8", opacity=0.85))
    b.append(text(W/2, 470, "切片的设计原则：最小切片=「能看到端到端差异的最短路径」——", 11.5, bold=True))
    b.append(text(W/2, 490, "tile=(2,2,3) 的产物与朴素版有 grep 可见的差异＋bitwise 一致——两个证据一起到手", 10.5))
    save("02-modify.svg", "".join(b), h=520)

def fig3():
    b = []
    b.append(text(W/2, 34, "测试计划：正确性、边界、性能三线", 16, bold=True))
    lines_ = [
        ("正确性线（D135 沿用）", "fuzz 200 组随机 shape×多组 tile——全部 bitwise；\n任何 tile 组合的正确性与朴素版等价", GREEN),
        ("边界线（三个极端）", "tile=(1,1,1)（退化＝朴素）／tile=shape（单块）／\ntile>shape（钳制生效）——三种边界的产物与正确性", ORANGE),
        ("性能线（D146 验收）", "kernel_timing 对照：朴素 vs tile 版——教学规模预期：\n差异小、方向不定；反例是合法结果（D153 伏笔）", RED),
    ]
    y = 60
    for name, body, color in lines_:
        b.append(hand_rect(60, y, 960, 130, fill=color, opacity=0.3))
        b.append(text(540, y + 26, name, 13, bold=True))
        for j, line in enumerate(body.split("\n")):
            b.append(text(540, y + 54 + j*22, line, 10.5))
        y += 140
    b.append(hand_rect(60, y + 6, 960, 60, fill="#F5E9C8", opacity=0.85))
    b.append(text(W/2, y + 30, "测试计划的早定原则：正确性线是门（不过不谈性能）、边界线是墙（", 11.5, bold=True))
    b.append(text(W/2, y + 50, "极端 tile 不许崩）、性能线是窗（教学规模的诚实——差异小是预期不是失败）", 10.5))
    save("03-testplan.svg", "".join(b), h=y + 80)

if __name__ == "__main__":
    fig1()
    fig2()
    fig3()
