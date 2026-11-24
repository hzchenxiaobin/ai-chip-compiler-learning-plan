#!/usr/bin/env python3
"""第 156 天 3 张 SVG。种子 156。"""
from __future__ import annotations
import math, os, random
import xml.sax.saxutils as su
random.seed(156)
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
    b.append(text(W/2, 34, "四份 Pass 文档：五要素齐全＋前后 IR 示例", 16, bold=True))
    passes = [
        ("Shape 推导", "三来源各管一段\nconst/arg/reshape\n推断不出→E202", GREEN),
        ("融合", "结构＋收益双门\n单链 7→5 节点\nfused_matmul_bias_relu", ORANGE),
        ("布局简化", "transpose(const)\n编译期转置\n运行时零搬运", BLUE),
        ("Tiling", "tile 参数化块循环\n产物差异可 grep\n性能 0.3×（反例记录）", RED),
    ]
    for i, (name, body, color) in enumerate(passes):
        x = 60 + i * 245
        b.append(hand_rect(x, 60, 225, 160, fill=color, opacity=0.35))
        b.append(text(x + 112, 88, name, 12.5, bold=True))
        for j, line in enumerate(body.split("\n")):
            b.append(text(x + 112, 112 + j*22, line, 10))
    # 五要素
    b.append(text(W/2, 252, "Pass 文档的五要素（每份必备）", 13.5, bold=True))
    elems = [("① 输入", "吃什么"), ("② 输出", "吐什么"), ("③ 合法性", "什么时候做/不做"),
             ("④ 收益", "为什么值得"), ("⑤ 限制", "边界在哪")]
    for i, (e, q) in enumerate(elems):
        x = 60 + i * 195
        b.append(hand_rect(x, 272, 180, 60, fill="#F5E9C8", opacity=0.75))
        b.append(text(x + 90, 296, e, 12, bold=True))
        b.append(text(x + 90, 316, q, 10, fill=MUTED))
    # 底部
    b.append(hand_rect(60, 356, 960, 60, fill="#F5E9C8", opacity=0.85))
    b.append(text(W/2, 380, "五要素缺一的后果：缺输入→读者猜；缺合法性→误用；缺收益→不知道为何存在；", 11, bold=True))
    b.append(text(W/2, 400, "缺限制→在不该用的地方用了——Tiling 的 0.3× 反例正是「限制」栏的价值（诚实记录负优化）", 10.5))
    save("01-five-elems.svg", "".join(b), h=420)

def fig2():
    b = []
    b.append(text(W/2, 34, "前后 IR 示例：文档的「证据」", 16, bold=True))
    examples = [
        ("融合", "%7=matmul %6,%12\n%9=add %7,%8\n%10=relu %9", 
         "%10=fused_matmul_bias_relu\n  %6,%12,%8", GREEN),
        ("Tiling", "scf.for %i = 0 to 160 step 1",
         "scf.for %i0 = 0 to 160 step 64 {\n  scf.for %i = %i0 to 160 ...", RED),
    ]
    for i, (name, before, after, color) in enumerate(examples):
        y = 60 + i * 200
        b.append(hand_rect(60, y, 460, 180, fill=RED, opacity=0.2))
        b.append(text(290, y + 24, f"{name}：前", 11.5, bold=True))
        for j, line in enumerate(before.split("\n")):
            b.append(text(90, y + 50 + j*20, line, 9.5, mono=True, anchor="start"))
        b.append(hand_rect(560, y, 460, 180, fill=GREEN, opacity=0.25))
        b.append(text(790, y + 24, f"{name}：后", 11.5, bold=True))
        for j, line in enumerate(after.split("\n")):
            b.append(text(590, y + 50 + j*20, line, 9.5, mono=True, anchor="start"))
    b.append(hand_rect(60, 470, 960, 56, fill="#F5E9C8", opacity=0.85))
    b.append(text(W/2, 494, "前后 IR 是 Pass 文档的核心证据——比流程图更硬（可 grep 可 diff）", 11.5, bold=True))
    b.append(text(W/2, 514, "「文档的每个说法都有 IR 片段背书」——这是 Pass 文档区别于讲义的地方", 10.5))
    save("02-examples.svg", "".join(b), h=530)

def fig3():
    b = []
    b.append(text(W/2, 34, "四份文档的诚实记录：收益与限制", 16, bold=True))
    b.append(hand_rect(60, 60, 460, 260, fill=GREEN, opacity=0.3))
    b.append(text(290, 86, "收益栏的正例", 13, bold=True))
    lines = [
        "Shape 推导：不猜——三来源各管一段",
        "融合：7→5 节点（结构收益）",
        "  教学规模数值归零（cache）——",
        "  结构结论保持（诚实声明）",
        "布局：运行时零搬运（真收益）",
    ]
    y = 112
    for line in lines:
        b.append(text(290, y, line, 10.5))
        y += 22
    b.append(hand_rect(560, 60, 460, 260, fill=RED, opacity=0.25))
    b.append(text(790, 86, "限制栏的反例", 13, bold=True))
    lines2 = [
        "融合：多使用者不融（D83 T10）",
        "Tiling：教学版 0.3× 负优化！",
        "  （重复计算 ×6.25 抵消复用——",
        "   D151 实测、文档如实记录）",
        "Shape：动态 ? 走另一条路（D128）",
    ]
    y = 112
    for line in lines2:
        b.append(text(790, y, line, 10.5))
        y += 22
    b.append(hand_rect(60, 340, 960, 66, fill="#F5E9C8", opacity=0.85))
    b.append(text(W/2, 366, "Pass 文档的诚实原则：收益写数字、限制写反例——", 12, bold=True))
    b.append(text(W/2, 388, "Tiling 的 0.3× 写进限制栏不是丢脸——它阻止下一个用户在教学实现上期待收益（D153 的教训文档化）", 10.5))
    save("03-honest.svg", "".join(b), h=420)

if __name__ == "__main__":
    fig1()
    fig2()
    fig3()
