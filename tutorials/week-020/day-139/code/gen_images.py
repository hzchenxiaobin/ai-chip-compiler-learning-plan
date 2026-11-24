#!/usr/bin/env python3
"""第 139 天 3 张 SVG。种子 139。"""
from __future__ import annotations
import math, os, random
import xml.sax.saxutils as su
random.seed(139)
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
    b.append(text(W/2, 34, "项目冻结检查：四维联合验收 7/7 全绿", 16, bold=True))
    dims = [
        ("A 正确性", "D134 测试集在位 ✓\nD135 随机报告在位 ✓\n200 组全对 ✓", "3/3", GREEN),
        ("B 编译时间", "D123 时间线在位 ✓\n（~394ms 教学量级）", "1/1", BLUE),
        ("C 运行性能", "D138 基准在位 ✓\n4 个 shape 基线 ✓", "2/2", ORANGE),
        ("D 文档", "day-113~138 README\n26/26 全在 ✓", "1/1", PURPLE),
    ]
    for i, (name, body, score, color) in enumerate(dims):
        x = 60 + i * 245
        b.append(hand_rect(x, 60, 225, 160, fill=color, opacity=0.35))
        b.append(text(x + 112, 88, name, 13, bold=True))
        for j, line in enumerate(body.split("\n")):
            b.append(text(x + 112, 114 + j*20, line, 9.5))
        b.append(text(x + 112, 190, score, 13, bold=True, fill="#4a7c59"))
    # 冻结版本
    b.append(hand_rect(280, 250, 520, 70, fill="#F5E9C8", opacity=0.85, sw=2.2))
    b.append(text(W/2, 278, "第五阶段版本冻结：v0.5.0-stage5", 16, bold=True))
    b.append(text(W/2, 304, "四维全绿 + must-fix 0 项 → 可以打标签发布", 11))
    # 底部
    b.append(hand_rect(60, 344, 960, 110, fill=BG, opacity=0.95, sw=1.8))
    b.append(text(W/2, 368, "「冻结」的准确含义", 12.5, bold=True))
    lines = [
        "· 不是「不再改」——是「这个基线被验证过，后续改动要过同一套闸」",
        "· 冻结的产物：问题清单（must-fix 0/future 8）＋回归报告＋版本号",
        "· 第 21~24 周的扩展全部基于这个版本——冻结是扩展的地基不是终点",
    ]
    for j, line in enumerate(lines):
        b.append(text(W/2, 392 + j*22, line, 10.5))
    save("01-freeze.svg", "".join(b), h=470)

def fig2():
    b = []
    b.append(text(W/2, 34, "问题清单：must-fix 与 future 的分界", 16, bold=True))
    # 左右
    b.append(hand_rect(60, 60, 440, 250, fill=GREEN, opacity=0.3))
    b.append(text(280, 88, "必须修复（must-fix）：0 项", 13, bold=True, fill="#4a7c59"))
    lines = [
        "判定标准：阻塞发布的缺陷",
        "  · 正确性失败（任何一个 FAIL）",
        "  · 性能回归超报警阈值",
        "  · 文档缺失关键交付",
        "",
        "现状：四维 7/7 全绿——无阻塞项",
        "这是「验收通过」的准确含义：",
        "不是「没有 bug」而是「已知的都处理了，",
        "未知的都有出口（future 清单）」",
    ]
    y = 116
    for line in lines:
        if line:
            b.append(text(280, y, line, 10.5))
        y += 22
    b.append(hand_rect(580, 60, 440, 250, fill=ORANGE, opacity=0.3))
    b.append(text(800, 88, "后续扩展（future）：8 项", 13, bold=True, fill=ORANGE))
    futures = [
        "F-01 块循环 Tiling 的 minic 化",
        "F-02 JIT 执行路线接入",
        "F-03 多算子支持集（conv/池化）",
        "F-04 跨进程缓存与失效",
        "F-05 SIGSEGV 级回退",
        "F-06 真二分定位工具化",
        "F-07 自动化 Reduce",
        "F-08 真实计时接入性能回归",
    ]
    y = 116
    for f in futures:
        b.append(text(800, y, f, 10.5, mono=True))
        y += 22
    b.append(text(800, y + 8, "每项有当日「讲不清」记录＋练习出口", 9.5, fill=MUTED))
    # 底部
    b.append(hand_rect(60, 330, 960, 90, fill="#F5E9C8", opacity=0.8))
    b.append(text(W/2, 356, "分界的判定问题：「这个不修，本版本能发吗？」", 12, bold=True))
    b.append(text(W/2, 380, "能发→future（显式排期：第 21 周起逐项做）｜不能发→must-fix（本版本内修完）", 10.5))
    b.append(text(W/2, 402, "清单的诚实性：must-fix=0 是因为四维全绿，不是因为「不想修」——每项 future 都有出处", 10.5, MUTED))
    save("02-issues.svg", "".join(b), h=440)

def fig3():
    b = []
    b.append(text(W/2, 34, "第 20 周收官与第 21~24 周的路线", 16, bold=True))
    # 20 周收官
    days = [
        ("D134", "测试整理", "16 例正反集"), ("D135", "随机 fuzz", "200 组全对"),
        ("D136", "二分定位", "注入精确指认"), ("D137", "最小用例", "19→4 节点"),
        ("D138", "性能回归", "阈值双验"), ("D139", "完整回归", "四维 7/7 冻结"),
        ("D140", "复盘", "明天"),
    ]
    for i, (d, name, note) in enumerate(days):
        x = 60 + i * 140
        color = PURPLE if d == "D140" else GREEN
        b.append(hand_rect(x, 60, 130, 90, fill=color, opacity=0.35))
        b.append(text(x + 65, 84, d, 11.5, bold=True))
        b.append(text(x + 65, 104, name, 10))
        b.append(text(x + 65, 124, note, 9, MUTED))
    # 后续四周
    b.append(text(W/2, 190, "冻结之后的路线（第 21~24 周）", 13.5, bold=True))
    weeks = [
        ("第 21 周", "扩展方向", "动态 Shape＋自动调度轻量组合\n（从 future 清单选主目标）", ORANGE),
        ("第 22 周", "性能归因", "慢用例→时间分解→瓶颈分析\n→有依据的优化→反例", RED),
        ("第 23 周", "项目整理", "架构图/Pass 文档/Lowering 文档\n/测试文档/性能材料/复现", BLUE),
        ("第 24 周", "面试转化", "六天标准回答＋20 分钟模拟讲解\n＋最终验收清单", GREEN),
    ]
    for i, (w, name, body, color) in enumerate(weeks):
        x = 60 + i * 245
        b.append(hand_rect(x, 210, 225, 140, fill=color, opacity=0.3))
        b.append(text(x + 112, 236, w, 12, bold=True))
        b.append(text(x + 112, 256, name, 11))
        for j, line in enumerate(body.split("\n")):
            b.append(text(x + 112, 278 + j*18, line, 9))
    # 底部
    b.append(hand_rect(60, 372, 960, 66, fill="#F5E9C8", opacity=0.8))
    b.append(text(W/2, 396, "第 20 周的答案：调试的核心是定位最早语义破坏点——", 12, bold=True))
    b.append(text(W/2, 420, "测试金字塔是地基、随机是军团、二分是手术刀、最小用例是标本、性能回归是底线、冻结是新的起点", 10.5))
    save("03-roadmap.svg", "".join(b), h=460)

if __name__ == "__main__":
    fig1()
    fig2()
    fig3()
