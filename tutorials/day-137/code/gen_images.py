#!/usr/bin/env python3
"""第 137 天 3 张 SVG。种子 137。"""
from __future__ import annotations
import math, os, random
import xml.sax.saxutils as su
random.seed(137)
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

def arrow(x1, y1, x2, y2, stroke=INK, sw=1.8, dash=None, label=None):
    dd = f' stroke-dasharray="{dash}"' if dash else ""
    mx, my = (x1 + x2) / 2 + jit(2.0), (y1 + y2) / 2 + jit(2.0)
    ang = math.atan2(y2 - y1, x2 - x1)
    hx, hy = x2 - 9 * math.cos(ang), y2 - 9 * math.sin(ang)
    a1 = (hx + 5 * math.cos(ang + 2.7), hy + 5 * math.sin(ang + 2.7))
    a2 = (hx + 5 * math.cos(ang - 2.7), hy + 5 * math.sin(ang - 2.7))
    d = (f"M {x1 + jit():.1f},{y1 + jit():.1f} Q {mx:.1f},{my:.1f} "
         f"{x2:.1f},{y2:.1f} M {a1[0]:.1f},{a1[1]:.1f} L {x2:.1f},{y2:.1f} "
         f"L {a2[0]:.1f},{a2[1]:.1f}")
    out = (f'<path d="{d}" stroke="{stroke}" stroke-width="{sw}" '
           f'stroke-linecap="round" fill="none"{dd}/>')
    if label:
        out += text((x1 + x2) / 2, (y1 + y2) / 2 - 8, label, 10.5, MUTED)
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
    b.append(text(W/2, 34, "最小失败用例：19 节点 → 4 节点（79% 缩减）", 16, bold=True))
    # 起点
    b.append(hand_rect(60, 60, 420, 280, fill=RED, opacity=0.25))
    b.append(text(270, 86, "复杂失败用例（起点）", 13, bold=True))
    lines = ["19 个节点 / 29 行", "shape 最大 64×128", "5 个 matmul / 3 个 transpose",
             "sigmoid/reshape/scale 混杂", "", "失败藏在第 8 行的深层链：", "matmul %t4, %w2 内维 64≠128",
             "→ 读者要追 6 层依赖才看到"]
    y = 112
    for line in lines:
        if line:
            b.append(text(90, y, line, 10.5, mono=("matmul" in line), anchor="start",
                          fill=RED if "失败" in line or "内维" in line else INK))
        y += 22
    # 中间箭头
    b.append(arrow(486, 200, 594, 200, sw=2.6, label="Reduce"))
    # 终点
    b.append(hand_rect(600, 60, 420, 280, fill=GREEN, opacity=0.3))
    b.append(text(810, 86, "最小失败用例（终点）", 13, bold=True))
    lines2 = ["4 个节点 / 7 行", "shape 2×3（肉眼可验算）", "1 个 matmul / 1 个 transpose",
             "", "失败一眼可见：", "transpose 输出 3×2 @ const 4×2", "→ 内维 3≠4，闸0 直接拒收",
              "", "同一问题、79% 缩减、可读性 10×"]
    y = 112
    for line in lines2:
        if line:
            b.append(text(630, y, line, 10.5, mono=("matmul" in line or "transpose" in line), anchor="start",
                          fill="#4a7c59" if "一眼" in line or "3≠4" in line else INK))
        y += 22
    # 三板斧
    b.append(text(W/2, 372, "Reduce 三板斧（每步保持失败）", 13.5, bold=True))
    axes = [
        ("R1 删节点", "与失败无关的下游剥掉\n（sigmoid 链/reshape/尾巴）", GREEN),
        ("R2 缩 shape", "64×128→2×3\n（shape 与失败无关）", BLUE),
        ("R3 简化类型", "f32 保留（问题在 shape）\n多余结构剥到触发路径", ORANGE),
    ]
    for i, (name, body, color) in enumerate(axes):
        x = 80 + i * 320
        b.append(hand_rect(x, 392, 290, 100, fill=color, opacity=0.35))
        b.append(text(x + 145, 416, name, 12, bold=True))
        for j, line in enumerate(body.split("\n")):
            b.append(text(x + 145, 438 + j*18, line, 9.5))
    # 底部
    b.append(hand_rect(60, 512, 960, 60, fill="#F5E9C8", opacity=0.8))
    b.append(text(W/2, 536, "Reduce 的铁律：每一步缩减后必须确认「仍触发同一失败」——", 11.5, bold=True))
    b.append(text(W/2, 558, "缩减到失败消失就回退一步（删多了）；最终的最小用例是「删无可删」的核", 10.5))
    save("01-overview.svg", "".join(b), h=590)

def fig2():
    b = []
    b.append(text(W/2, 34, "Delta Debugging：树形结构的缩减策略", 16, bold=True))
    # 依赖树
    b.append(text(180, 60, "原图的依赖树", 12.5, bold=True))
    nodes = [
        ("x", 90, 100, GREEN), ("w1", 170, 100, GREEN),
        ("t1=matmul", 130, 150, GREEN), ("t2=add", 130, 200, GREEN),
        ("t3=relu", 130, 250, GREEN), ("w2", 300, 100, RED),
        ("t4=transpose", 240, 150, BLUE), ("t5=matmul", 190, 200, RED),
        ("t6=sigmoid", 190, 250, GREEN), ("t7~t13 尾巴", 190, 300, MUTED),
    ]
    edges = [(0, 2), (1, 2), (2, 3), (3, 4), (4, 6), (5, 7), (6, 7), (7, 8), (8, 9)]
    for a_i, b_i in edges:
        x1, y1 = nodes[a_i][1] + 35, nodes[a_i][2]
        x2, y2 = nodes[b_i][1] + 35, nodes[b_i][2]
        stroke = RED if nodes[a_i][3] == RED or nodes[b_i][3] == RED else INK
        b.append(arrow(x1, y1, x2, y2, stroke=stroke, sw=1.2))
    for name, x, y, color in nodes:
        b.append(hand_rect(x, y - 14, 70, 28, fill=color if color != MUTED else BLUE, opacity=0.4))
        b.append(text(x + 35, y + 5, name, 9.5, mono=True, bold=color == RED))
    b.append(text(180, 340, "红＝失败路径（触发内维不匹配）", 10, fill=RED, bold=True))
    b.append(text(180, 360, "绿＝与失败无关（可删）", 10, fill="#4a7c59"))
    # 右侧：缩减过程
    b.append(text(700, 60, "删节点的顺序（自外向内）", 12.5, bold=True))
    steps = [
        ("① 删 t7~t13（尾巴）", "失败仍在 → 保留删除", GREEN),
        ("② 删 t6（sigmoid）", "失败仍在 → 保留删除", GREEN),
        ("③ 删 t4（transpose）", "失败消失！→ 回退（它在触发路径上）", RED),
        ("④ 删 t2/t3（add/relu）", "失败仍在 → 保留删除", GREEN),
        ("⑤ 删 w1/t1（旁路）", "失败仍在 → 保留删除", GREEN),
    ]
    y = 90
    for step, result, color in steps:
        b.append(hand_rect(480, y, 480, 52, fill=color, opacity=0.25))
        b.append(text(500, y + 20, step, 10.5, bold=True, anchor="start"))
        b.append(text(500, y + 40, result, 9.5, anchor="start", fill=MUTED))
        y += 60
    b.append(hand_rect(480, y + 4, 480, 44, fill="#F5E9C8", opacity=0.8))
    b.append(text(720, y + 30, "剩余：x + transpose + w2 + matmul ＝ 4 节点核", 10.5, bold=True))
    save("02-mechanism.svg", "".join(b), h=y + 70)

def fig3():
    b = []
    b.append(text(W/2, 34, "从 bug 报告到回归测试：最小用例的完整旅程", 16, bold=True))
    stages = [
        ("① bug 报告", "用户提交复杂图\n（19 节点/深层链）\n「这个图编译失败」", RED),
        ("② 定位", "D136 二分/审计\n→ 失败=内维不匹配\n（哪条 Pass/哪个闸）", ORANGE),
        ("③ Reduce", "今天的三板斧\n→ 4 节点最小用例\n（删无可删的核）", BLUE),
        ("④ 修复", "改 const shape\n[4,2]→[3,2]\n（或修 transpose 语义）", GREEN),
        ("⑤ 回归固化", "最小用例＋期望\n→ D134 正反例格式\n→ 永久守卫", PURPLE),
    ]
    for i, (name, body, color) in enumerate(stages):
        x = 50 + i * 200
        b.append(hand_rect(x, 60, 180, 150, fill=color, opacity=0.35))
        b.append(text(x + 90, 88, name, 12, bold=True))
        for j, line in enumerate(body.split("\n")):
            b.append(text(x + 90, 112 + j*18, line, 9.5))
        if i < 4:
            b.append(arrow(x + 182, 135, x + 198, 135, sw=1.5))
    # 价值
    b.append(text(W/2, 248, "最小用例的五重价值", 13.5, bold=True))
    values = [
        ("可读", "维护者一眼看懂失败形态——不用追 6 层依赖"),
        ("快", "回归测试从秒级到 µs 级——可进每次提交的 CI"),
        ("可提交", "bug 报告的黄金标准——「最小可复现」是社区礼仪"),
        ("定位助力", "小 IR 让 D136 的二分更快（pass 少、判定快）"),
        ("教学资产", "每个最小用例都是一节课——失败形态的标本"),
    ]
    y = 270
    for k, v in values:
        b.append(hand_rect(80, y, 920, 36, fill="#F5E9C8", opacity=0.7))
        b.append(text(140, y + 24, k, 11, bold=True))
        b.append(text(320, y + 24, v, 10.5, anchor="start"))
        y += 42
    # 底部
    b.append(hand_rect(80, y + 8, 920, 50, fill=PURPLE, opacity=0.25))
    b.append(text(W/2, y + 30, "「好 bug 报告会自己说话」——一个 4 节点的最小用例胜过千字描述", 11.5, bold=True))
    b.append(text(W/2, y + 48, "明天的性能回归测试（D138）会用同样的思想：固定最小基准集、拒绝噪声", 10.5, MUTED))
    save("03-journey.svg", "".join(b), h=y + 70)

if __name__ == "__main__":
    fig1()
    fig2()
    fig3()
