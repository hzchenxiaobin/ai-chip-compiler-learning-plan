#!/usr/bin/env python3
"""生成第 125 天（优化开关对照实验）的 3 张手绘 sketch 风 SVG 图。

数字来自 outputs/report.txt 与 benefit-table.json 真实运行
（2026-11-14，macOS arm64，LLVM 23.1.5）。固定随机种子 125。
"""
from __future__ import annotations

import math
import os
import random
import xml.sax.saxutils as su

random.seed(125)

BG = "#FDFBF6"
BORDER = "#E7DFCE"
INK = "#3B3B3B"
MUTED = "#6b6257"
ORANGE = "#E8A87C"
BLUE = "#A9C4D4"
GREEN = "#9CBF8E"
RED = "#C97B7B"
PURPLE = "#B8A7CE"
FONT = "'Comic Sans MS','Kaiti SC','KaiTi','STKaiti',cursive"

W, H = 1080, 760
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "images")


def jit(m=1.6):
    return random.uniform(-m, m)


def hand_rect(x, y, w, h, fill=BG, opacity=0.65, stroke=INK, sw=1.4, dash=None):
    pts = [(x + jit(), y + jit()), (x + w + jit(), y + jit()),
           (x + w + jit(), y + h + jit()), (x + jit(), y + h + jit())]
    d = f"M {pts[0][0]:.1f},{pts[0][1]:.1f} "
    for i in range(4):
        a, b = pts[i], pts[(i + 1) % 4]
        mx, my = (a[0] + b[0]) / 2 + jit(2.2), (a[1] + b[1]) / 2 + jit(2.2)
        d += f"Q {mx:.1f},{my:.1f} {b[0]:.1f},{b[1]:.1f} "
    dd = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<path d="{d} Z" stroke="{stroke}" stroke-width="{sw}" '
            f'stroke-linecap="round" stroke-linejoin="round" '
            f'fill="{fill}" fill-opacity="{opacity}"{dd}/>')


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


# ── 图 1：四组对照矩阵 ──
def fig1():
    b = []
    b.append(text(W/2, 34, "四组开关对照：正确性全过、规模有痕、性能有反例", 16, bold=True))

    # 四组卡片
    groups = [
        ("A 无优化", "--no-fuse", "图 7 节点\nfused ✗（matmul/add/relu 分立）\n清理保留（管道前提）", RED),
        ("B 仅图优化", "默认 S1", "图 5 节点\nfused ✓（融合生效）\nLowering 不跑 -O2", ORANGE),
        ("C 图+Tiling", "B + tile", "同 B（教学 tile=shape\n朴素循环下 tile 参数\n不影响产物——见 3.3）", BLUE),
        ("D 完整优化", "B + LLVM -O2", "图 5 节点＋opt -O2\nfmul 1→6（k 全展开）\nphi 4→1（循环变量消失）", GREEN),
    ]
    gw, gh, ggap = 240, 170, 20
    gx0 = (W - (gw*4 + ggap*3)) / 2
    for i, (name, sw, desc, color) in enumerate(groups):
        x = gx0 + i * (gw + ggap)
        b.append(hand_rect(x, 56, gw, gh, fill=color, opacity=0.42))
        b.append(text(x + gw/2, 80, name, 13, bold=True))
        b.append(text(x + gw/2, 98, sw, 9.5, mono=True, fill=MUTED))
        for j, line in enumerate(desc.split("\n")):
            b.append(text(x + gw/2, 120 + j*16, line, 9.5))
    # 正确性带
    b.append(hand_rect(gx0, 240, gw*4 + ggap*3, 40, fill=GREEN, opacity=0.5))
    b.append(text(W/2, 264, "正确性：A/B/C/D 四组全部 12/12 bitwise ✓（对照实验的合法性前提）", 12, bold=True))

    # 中：产物规模表
    b.append(text(W/2, 316, "产物规模对照（编译期的优化痕迹——benefit-table.json）", 14, bold=True))
    rows = [
        ("A 无优化", "7 节点", "111 行", "1", "4", "（add/relu 独立但同循环展开）"),
        ("B 仅图优化", "5 节点", "111 行", "1", "4", "（融合不改变循环形态）"),
        ("C 图+Tiling", "5 节点", "111 行", "1", "4", "（tile=shape 无效果）"),
        ("D 完整优化", "5 节点", "111→177 行", "1→6", "4→1", "（-O2 展开：k=6 全展开）"),
    ]
    y = 336
    b.append(text(180, y, "组", 10.5, bold=True)); b.append(text(300, y, "图节点", 10.5, bold=True))
    b.append(text(420, y, ".ll 行", 10.5, bold=True)); b.append(text(540, y, "fmul", 10.5, bold=True))
    b.append(text(620, y, "phi", 10.5, bold=True)); b.append(text(800, y, "备注", 10.5, bold=True))
    y += 16
    for name, nodes, lines, fmul, phi, note in rows:
        color = GREEN if name.startswith("D") else BLUE
        b.append(hand_rect(120, y, 840, 34, fill=color, opacity=0.3))
        b.append(text(180, y + 22, name, 10.5, bold=True))
        b.append(text(300, y + 22, nodes, 10.5))
        b.append(text(420, y + 22, lines, 10.5))
        b.append(text(540, y + 22, fmul, 10.5, mono=True))
        b.append(text(620, y + 22, phi, 10.5, mono=True))
        b.append(text(800, y + 22, note, 9, fill=MUTED))
        y += 40

    # 下：kernel 计时
    b.append(text(W/2, y + 20, "kernel 级计时（D118 挂账兑付：同进程 20000 次均值）", 14, bold=True))
    y0 = y + 40
    bars = [("O0 循环版", 0.019, GREEN), ("O2 展开版", 0.032, RED)]
    max_us = 0.035
    for i, (name, us, color) in enumerate(bars):
        bx = 260 + i * 320
        bw = (us / max_us) * 240
        b.append(hand_rect(bx, y0, bw, 28, fill=color, opacity=0.55))
        b.append(text(bx - 10, y0 + 19, name, 10.5, anchor="end"))
        b.append(text(bx + bw + 8, y0 + 19, f"{us:.3f} µs/次", 10))
    b.append(text(W/2, y0 + 52, "性能反例：展开版更慢 60%！——教学 kernel（4×6×3）太小，", 11.5, fill=RED, bold=True))
    b.append(text(W/2, y0 + 70, "循环开销本就低，展开的代码体积代价（i-cache 局部性）超过收益；详见 3.4 与图 3", 10.5, MUTED))
    save("01-overview.svg", "".join(b), h=y0 + 90)


# ── 图 2：对照实验的方法论 ──
def fig2():
    b = []
    b.append(text(W/2, 34, "对照实验方法论：控制变量、口径声明、反例的价值", 16, bold=True))

    # 左：控制变量设计
    b.append(hand_rect(50, 60, 480, 240, fill=BLUE, opacity=0.3))
    b.append(text(290, 84, "控制变量的三层设计", 13, bold=True))
    items = [
        ("层 1：管道级", "四组共享 S0/S2/S4/S5/S6 同一实现——\n唯一变量是 S1 开关与 -O2（组 D）", GREEN),
        ("层 2：数据级", "四组用同一份 A/B/bias（D118 手算友好数据）\n与同一份 golden（k 序参考）", ORANGE),
        ("层 3：环境级", "同机同进程族计时（fork 自同一 parent）、\n20000 次取均值、三轮复测", RED),
    ]
    y = 104
    for title, body, color in items:
        b.append(hand_rect(70, y, 440, 56, fill=color, opacity=0.25))
        b.append(text(90, y + 20, title, 11, bold=True, anchor="start"))
        for j, line in enumerate(body.split("\n")):
            b.append(text(90, y + 36 + j*14, line, 9))
        y += 64
    b.append(text(290, y + 12, "对照组的合法性前提：每组都必须跑通（D124 的", 10, MUTED))
    b.append(text(290, y + 28, "-O0 教训——「关到跑不了」的对照组没有数据）", 10, MUTED))

    # 右：口径清单
    b.append(hand_rect(560, 60, 470, 240, fill=ORANGE, opacity=0.3))
    b.append(text(795, 84, "每个数字的口径（今天的四份声明）", 13, bold=True))
    decls = [
        ("图节点数", "S1 终图的节点计数（census 口径）"),
        (".ll 行数/fmul/phi", "stage-5.ll 的文本统计（LLVM IR）"),
        ("kernel µs/次", "同进程 20000 次调用的均值×时钟\n（CLOCK_MONOTONIC；非 wall-clock）"),
        ("正确性", "12/12 bitwise（k 序 golden——D124 口径）"),
    ]
    y = 108
    for name, desc in decls:
        b.append(hand_rect(580, y, 430, 44, fill=BG, opacity=0.9))
        b.append(text(600, y + 18, name, 10.5, bold=True, anchor="start"))
        for j, line in enumerate(desc.split("\n")):
            b.append(text(600, y + 32 + j*13, line, 8.8, anchor="start", fill=MUTED))
        y += 50

    # 下：反例分析
    b.append(text(W/2, 330, "性能反例解剖：为什么 -O2 更慢？", 14, bold=True))
    b.append(hand_rect(50, 350, 980, 180, fill=RED, opacity=0.25))
    left = [
        "事实：O2（fmul 1→6 全展开）= 0.032 µs",
        "      O0（循环版）       = 0.019 µs",
        "      展开版慢 60%，三轮复测稳定",
        "",
        "原因 ①：kernel 太小（72 MAC）",
        "  循环控制开销 ~10 条指令/圈，占比本就低",
        "  展开省下的 < 代码体积增加的 i-cache 代价",
        "",
        "原因 ②：fmul 链串行依赖（acc 链）",
        "  展开不创造 ILP；向量化需要无依赖的相邻乘法",
    ]
    right = [
        "证据：汇编 129 行（循环）→ 169 行（展开）",
        "      代码膨胀 +31%",
        "",
        "教学边界（诚实声明）：",
        "  这不是「-O2 无用」——是「小 kernel 上展开的",
        "  代价 > 收益」。真实规模（256³）下循环开销",
        "  占比高且可向量化，方向相反。",
        "",
        "判据永远「量出来的相对差」，",
        "不是「级别越高越好」——D96/D153 的主题。",
    ]
    for j, line in enumerate(left):
        b.append(text(90, 374 + j*18, line, 10, anchor="start"))
    for j, line in enumerate(right):
        b.append(text(560, 374 + j*18, line, 10, anchor="start"))
    b.append(arrow(500, 440, 550, 440, sw=1.4))

    b.append(hand_rect(50, 548, 980, 48, fill="#F5E9C8", opacity=0.8))
    b.append(text(W/2, 570, "对照实验的最大收获不是「哪组快」——是反例本身：优化不是免费的，每层收益都要量出来", 11.5, bold=True))
    b.append(text(W/2, 590, "面试口径：做过的优化里，有没有量出来是负收益的？（有——今天这例，说明你真的量过）", 10.5, MUTED))
    save("02-mechanism.svg", "".join(b), h=620)


# ── 图 3：阶段收益表与本周收官 ──
def fig3():
    b = []
    b.append(text(W/2, 34, "阶段收益表：四组×四指标——以及第 18 周收官预览", 16, bold=True))

    # 收益表
    b.append(text(W/2, 62, "阶段收益表（benefit-table.json 的可视化）", 13.5, bold=True))
    cols = ["组", "开关配置", "图节点", ".ll 行", "fmul", "phi", "kernel µs"]
    data = [
        ("A", "--no-fuse", "7", "111", "1", "4", "0.019"),
        ("B", "融合开", "5", "111", "1", "4", "0.020"),
        ("C", "B+tile", "5", "111", "1", "4", "0.018"),
        ("D", "B+O2", "5", "111→177", "1→6", "4→1", "0.032*"),
    ]
    x0, y0 = 100, 84
    cw = [50, 150, 90, 110, 80, 60, 100]
    # 表头
    xx = x0
    for i, c in enumerate(cols):
        b.append(hand_rect(xx, y0, cw[i], 30, fill=BLUE, opacity=0.5))
        b.append(text(xx + cw[i]/2, y0 + 20, c, 10.5, bold=True))
        xx += cw[i] + 4
    # 数据行
    for r, row in enumerate(data):
        xx = x0
        color = GREEN if row[0] == "D" else (RED if row[0] == "A" else BLUE)
        for i, cell in enumerate(row):
            b.append(hand_rect(xx, y0 + 34 + r*36, cw[i], 32, fill=color, opacity=0.3))
            b.append(text(xx + cw[i]/2, y0 + 34 + r*36 + 21, cell, 10,
                          mono=(i >= 2), bold=(i == 0)))
            xx += cw[i] + 4
    b.append(text(W/2, y0 + 34 + 4*36 + 22, "* D 组的 kernel µs 是 O2 展开版——比循环版慢（性能反例，见图 2）；tile=shape 下 C 组与 B 组同产物", 10, fill=MUTED))

    # 中：三个结论
    b.append(text(W/2, y0 + 210, "从收益表读出的三个结论", 13.5, bold=True))
    conclusions = [
        ("① 融合的收益在图不在循环", "A→B：图 7→5 节点（少两个中间结果），\n但 .ll 规模不变（融合不改变循环形态）——\n融合收益是「少存取中间缓冲」，教学规模\n没有 HBM 流量可省（D72 的账本）", GREEN),
        ("② 教学规模下 tile 是空变量", "B→C：tile=shape（2,3,6 vs 4,3,6）在\n朴素循环下产物相同——tile 的收益需要\n「块级复用」才有（真实 Tiling D91~97）", BLUE),
        ("③ -O2 的双刃剑", "C→D：fmul 1→6（编译器确实更努力了），\n但 kernel 更慢——展开的代码体积代价\n在小 kernel 上超过循环开销节省", RED),
    ]
    y = y0 + 230
    for title, body, color in conclusions:
        b.append(hand_rect(70, y, 940, 76, fill=color, opacity=0.3))
        b.append(text(100, y + 22, title, 11.5, bold=True, anchor="start"))
        for j, line in enumerate(body.split("\n")):
            b.append(text(360, y + 20 + j*15, line, 9.5, anchor="start"))
        y += 84

    # 底：第 18 周收官
    b.append(text(W/2, y + 16, "第 18 周收官：统一编译入口完成", 13.5, bold=True))
    week = [("D120", "CLI 骨架", "25/25"), ("D121", "S1 图优化", "25/25"),
            ("D122", "S2~S5", "25/25"), ("D123", "可观测", "12/12"),
            ("D124", "端到端", "11/11"), ("D125", "对照实验", "10/10"),
            ("D126", "复盘", "明天")]
    dw, dgap = 130, 14
    dx0 = (W - (dw*7 + dgap*6)) / 2
    for i, (d, name, note) in enumerate(week):
        x = dx0 + i * (dw + dgap)
        color = PURPLE if d == "D126" else GREEN
        b.append(hand_rect(x, y + 36, dw, 60, fill=color, opacity=0.4))
        b.append(text(x + dw/2, y + 56, d, 11.5, bold=True))
        b.append(text(x + dw/2, y + 72, name, 9.5))
        b.append(text(x + dw/2, y + 88, note, 9, MUTED))
    save("03-example.svg", "".join(b), h=y + 110)


if __name__ == "__main__":
    fig1()
    fig2()
    fig3()
