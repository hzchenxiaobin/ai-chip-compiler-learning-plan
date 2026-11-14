#!/usr/bin/env python3
"""第 144 天 3 张 SVG。种子 144。"""
from __future__ import annotations
import math, os, random
import xml.sax.saxutils as su
random.seed(144)
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
    b.append(text(W/2, 34, "约束与失败路径：校验 5 负例＋边界 3 极端＋v2 生成器", 16, bold=True))
    cards = [
        ("C1 v2 生成器", "块内边界设计（min 钳制）\n教学边界：完整 addi+minsi\n留 README 详述\n七 pass 全通 ✓", GREEN),
        ("C2 参数校验", "5 个负例全拒收：\n零分量/负分量/非整数\n非元组/二元组\nE202 诊断带理由", RED),
        ("C3 边界三极端", "tile=(1,1,1) 退化 ✓\ntile=shape 单块 ✓\ntile>shape 钳制 ✓\n3/3 不许崩", ORANGE),
    ]
    for i, (name, body, color) in enumerate(cards):
        x = 60 + i * 330
        b.append(hand_rect(x, 60, 300, 190, fill=color, opacity=0.35))
        b.append(text(x + 150, 88, name, 13, bold=True))
        for j, line in enumerate(body.split("\n")):
            b.append(text(x + 150, 114 + j*22, line, 10))
    b.append(hand_rect(60, 280, 960, 90, fill="#F5E9C8", opacity=0.85))
    b.append(text(W/2, 306, "负例五连与极端三连的设计意图：", 12.5, bold=True))
    b.append(text(W/2, 330, "负例防「垃圾进垃圾出」（非法 tile 必须有结构化拒收）；极端防「边界崩」（合法但刁钻的 tile 不许崩）", 10.5))
    b.append(text(W/2, 352, "两者合起来＝「非法的拒收、合法的兜住」——D134 正反例纪律在扩展周的直接应用", 10.5, MUTED))
    save("01-three.svg", "".join(b), h=380)

def fig2():
    b = []
    b.append(text(W/2, 34, "参数校验的决策树（validate_tile）", 16, bold=True))
    b.append(hand_rect(340, 60, 400, 50, fill=BLUE, opacity=0.4))
    b.append(text(W/2, 90, "validate_tile(tile)", 13, mono=True, bold=True))
    tree = [
        ("是三元组？", "否 → E202「必须是三元组」", RED),
        ("分量是整数？", "否 → E202「必须是整数」", RED),
        ("分量 ≥ 1？", "否 → E202「必须 ≥1」", RED),
        ("全部通过", "→ 放行到生成器", GREEN),
    ]
    y = 130
    for q, branch, color in tree:
        b.append(hand_rect(360, y, 360, 56, fill=color, opacity=0.3))
        b.append(text(420, y + 22, q, 11.5, bold=True, anchor="start"))
        b.append(text(420, y + 42, branch, 10, anchor="start", fill=MUTED))
        y += 64
    b.append(hand_rect(60, 410, 960, 70, fill="#F5E9C8", opacity=0.85))
    b.append(text(W/2, 434, "校验的层次设计：类型层（元组？整数？）→ 值域层（≥1？）——", 11.5, bold=True))
    b.append(text(W/2, 456, "先查结构后查值——结构错的输入谈值域没有意义（分层校验与 E1xx 的分层同构）", 10.5))
    save("02-validate.svg", "".join(b), h=500)

def fig3():
    b = []
    b.append(text(W/2, 34, "明天 D145：与现有优化的集成", 16, bold=True))
    items = [
        ("集成点①", "minic 的 S2 接口", "gen_loop_ir_full → gen_block_v2\n（tile 参数从 CLI 一路传到生成器）", GREEN),
        ("集成点②", "D129 分发器", "不同 tile 的特化产物注册\n（(shape,tile) 二元组做 key）", BLUE),
        ("集成点③", "D135 fuzz", "200 组随机 shape×tile 组合\n正确性军团扩容", ORANGE),
        ("集成点④", "全管道", "S1→S2(tile)→S4→S5→S6\n端到端一条命令", RED),
    ]
    for i, (name, target, body, color) in enumerate(items):
        y = 60 + i * 110
        b.append(hand_rect(60, y, 960, 96, fill=color, opacity=0.3))
        b.append(text(150, y + 26, name, 12, bold=True))
        b.append(text(150, y + 52, target, 11, fill=MUTED))
        for j, line in enumerate(body.split("\n")):
            b.append(text(500, y + 28 + j*22, line, 10.5, anchor="start"))
    b.append(hand_rect(60, 510, 960, 56, fill="#F5E9C8", opacity=0.85))
    b.append(text(W/2, 534, "集成的验收：v0.5.0 冻结版的全套测试（D139 四维）＋新扩展的测试都绿——", 11.5, bold=True))
    b.append(text(W/2, 554, "「集成不改旧」——旧路径（tile=None）的行为零变化是红线", 10.5))
    save("03-integrate.svg", "".join(b), h=580)

if __name__ == "__main__":
    fig1()
    fig2()
    fig3()
