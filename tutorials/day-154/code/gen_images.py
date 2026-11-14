#!/usr/bin/env python3
"""第 154 天 3 张 SVG。种子 154。"""
from __future__ import annotations
import math, os, random
import xml.sax.saxutils as su
random.seed(154)
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
    b.append(text(W/2, 34, "第 22 周闭环：五步归因链（每步实测）", 16, bold=True))
    steps = [
        ("① 基线", "D148", "20.91ms/0.39GF\n五要素协议", GREEN),
        ("② 拆解", "D149", "首次 97.7% 编译\n稳态 100% 执行", BLUE),
        ("③ 定性", "D150", "Roofline：两屋顶都远\n→ 执行效率瓶颈＋三假设", ORANGE),
        ("④ 优化", "D151", "H1 ✓ 8.4×\nH2 ✗ 0.3×（证伪）", RED),
        ("⑤ 范围", "D152~153", "分布 1.7~14.1×\n反例是环境函数", PURPLE),
    ]
    for i, (name, day, body, color) in enumerate(steps):
        x = 50 + i * 200
        b.append(hand_rect(x, 60, 180, 150, fill=color, opacity=0.35))
        b.append(text(x + 90, 86, name, 13, bold=True))
        b.append(text(x + 90, 104, day, 10, fill=MUTED))
        for j, line in enumerate(body.split("\n")):
            b.append(text(x + 90, 126 + j*20, line, 9.5))
        if i < 4:
            b.append(hand_rect(x + 182, 120, 16, 30, fill=INK, opacity=0.4))
    # 核心数字带
    b.append(text(W/2, 250, "一周的核心数字", 13.5, bold=True))
    stats = [("20.9ms", "基线"), ("8.4×", "O2 收益（中位 9.4×）"),
             ("0.3×", "tile 反例"), ("1.7~14.1×", "跨 shape 分布"),
             ("环境戳", "反例的元发现")]
    for i, (num, label) in enumerate(stats):
        x = 70 + i * 195
        b.append(hand_rect(x, 270, 180, 70, fill=ORANGE, opacity=0.4))
        b.append(text(x + 90, 296, num, 13.5, bold=True))
        b.append(text(x + 90, 318, label, 9.5, MUTED))
    # 底部
    b.append(hand_rect(60, 366, 960, 66, fill="#F5E9C8", opacity=0.85))
    b.append(text(W/2, 390, "归因链的完整性：从「一个慢数字」到「带适用条件与环境戳的优化结论」——", 11.5, bold=True))
    b.append(text(W/2, 412, "五步每步都有实测数据、每步的输出是下一步的输入——与方法论（D140 调试五站）同构", 10.5))
    save("01-chain.svg", "".join(b), h=440)

def fig2():
    b = []
    b.append(text(W/2, 34, "口头汇报口径（5 分钟版）", 16, bold=True))
    script = [
        ("0:00~0:45 问题", "160³ 朴素 kernel 20.9ms、0.39GF——离峰值百倍。基线五要素可复现。"),
        ("0:45~1:30 拆解", "稳态执行占 100%——嫌疑唯一。首次视角编译 97.7%（JIT 冷启动）。"),
        ("1:30~2:15 定性", "Roofline：AI=0.13，两屋顶都远——执行效率瓶颈。三假设。"),
        ("2:15~3:30 验证", "O2 展开 8.4×（H1 成立）；tile 0.3×（H2 证伪——重复计算）。"),
        ("3:30~4:15 范围", "跨 7 shape：1.7~14.1×。最差解剖（K 小）。反例是环境函数。"),
        ("4:15~5:00 建议", "O2 默认开（中位 9.4×）；tile 完整版是后续；反例带环境戳。"),
    ]
    for i, (time_slot, content) in enumerate(script):
        y = 60 + i * 76
        b.append(hand_rect(60, y, 960, 66, fill=BLUE, opacity=0.25))
        b.append(text(170, y + 26, time_slot.split(" ")[0], 11.5, bold=True, mono=True))
        b.append(text(170, y + 50, time_slot.split(" ", 1)[1], 10, fill=MUTED))
        b.append(text(560, y + 38, content, 11, anchor="start"))
    b.append(hand_rect(60, 530, 960, 56, fill="#F5E9C8", opacity=0.85))
    b.append(text(W/2, 554, "汇报的纪律：每段一个数字锚点（20.9ms→8.4×→0.3×→1.7~14.1×）——", 11.5, bold=True))
    b.append(text(W/2, 574, "听者五分钟内能复述的就是这四个数字与「反例是环境函数」——准备到这个程度才算脱稿", 10.5))
    save("02-script.svg", "".join(b), h=600)

def fig3():
    b = []
    b.append(text(W/2, 34, "第 23 周预告：项目整理（D155~D161）", 16, bold=True))
    week23 = [
        ("D155", "整理项目架构", "架构图：职责与数据流\n（不是文件名堆叠）"),
        ("D156", "整理关键 Pass", "Shape/融合/Layout/Tiling\n各一份说明＋前后 IR"),
        ("D157", "整理 Lowering 文档", "MatMul 串各阶段 IR\n标注关键转换"),
        ("D158", "整理测试文档", "测试金字塔/运行命令\n/覆盖与缺口"),
        ("D159", "整理性能材料", "汇总数据＋图表\n＋结论摘要"),
        ("D160", "干净环境复现", "按 README 从零构建\n修复遗漏步骤"),
        ("D161", "第 23 周复盘", "以新人视角通读\n删除自语式表述"),
    ]
    for i, (d, name, body) in enumerate(week23):
        y = 60 + i * 82
        color = PURPLE if d == "D161" else GREEN
        b.append(hand_rect(60, y, 960, 70, fill=color, opacity=0.3))
        b.append(text(120, y + 28, d, 12, bold=True))
        b.append(text(320, y + 28, name, 11.5))
        b.append(text(320, y + 50, body.split("\n")[1] if len(body.split("\n"))>1 else "", 9.5, fill=MUTED))
        b.append(text(700, y + 38, body.split("\n")[0], 10))
    b.append(hand_rect(60, 650, 960, 56, fill="#F5E9C8", opacity=0.85))
    b.append(text(W/2, 674, "第 23 周的主题转换：从「做出来」到「讲清楚」——", 12, bold=True))
    b.append(text(W/2, 694, "22 周的积累要变成他人能理解、能验证的项目资产——整理不是美化是第二次创造", 10.5))
    save("03-week23.svg", "".join(b), h=720)

if __name__ == "__main__":
    fig1()
    fig2()
    fig3()
