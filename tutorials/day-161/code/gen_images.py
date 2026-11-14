#!/usr/bin/env python3
"""第 161 天 3 张 SVG。种子 161。"""
from __future__ import annotations
import math, os, random
import xml.sax.saxutils as su
random.seed(161)
BG = "#FDFBF6"; BORDER = "#E7DFCE"; INK = "#3B3B3B"; MUTED = "#6b6257"
ORANGE = "#E8A87C"; BLUE = "#A9C4D4"; GREEN = "#9CBF8E"; RED = "#C97B7B"
PURPLE = "#B8A7CE"
FONT = "'Comic Sans MS','Kaiti SC','KaiTi','STKaiti',cursive"
W, H = 1080, 760
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "images")

def jit(m=1.6): return random.uniform(-m, m)
def hand_rect(x, y, w, h, fill=BG, opacity=0.65, stroke=INK, sw=1.4):
    pts = [(x + jit(), y + jit()), (x + w + jit(), y + jit()),
           (x + w + jit(), y + h + jit()), (x + jit(), y + h + jet() if False else jit())]
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
    b.append(text(W/2, 34, "第 23 周收官：从「能跑」到「他人能理解、能验证」", 15, bold=True))
    days = [("D155", "架构"), ("D156", "Pass×4"), ("D157", "Lowering"),
            ("D158", "测试"), ("D159", "性能"), ("D160", "复现 8/8"), ("D161", "复盘·今天")]
    for i, (d, name) in enumerate(days):
        x = 60 + i * 140
        color = PURPLE if i == 6 else GREEN
        b.append(hand_rect(x, 60, 130, 80, fill=color, opacity=0.35))
        b.append(text(x + 65, 86, d, 11.5, bold=True))
        b.append(text(x + 65, 106, name, 10))
    # 对照
    b.append(hand_rect(60, 170, 460, 180, fill=RED, opacity=0.2))
    b.append(text(290, 196, "整理前（作者视角）", 12.5, bold=True))
    lines1 = ["50 个 outputs/ 目录", "产出在但没地图", "新人＝考古现场", "「我知道在哪」"]
    y = 222
    for line in lines1:
        b.append(text(290, y, line, 10.5))
        y += 22
    b.append(hand_rect(560, 170, 460, 180, fill=GREEN, opacity=0.3))
    b.append(text(790, 196, "整理后（新人视角）", 12.5, bold=True))
    lines2 = ["五份文档＋三层保障", "地图＋产物＋命令", "走查 8/8 验证可用", "「任何人都能找到」"]
    y = 222
    for line in lines2:
        b.append(text(790, y, line, 10.5))
        y += 22
    b.append(hand_rect(60, 370, 960, 60, fill="#F5E9C8", opacity=0.85))
    b.append(text(W/2, 394, "「整理不是美化是第二次创造」——把作者的记忆外化成公共资产", 12, bold=True))
    b.append(text(W/2, 416, "第 24 周的面试转化正是在这份资产上进行的——没有文档的回答是背诵、有文档的回答是复述经历", 10.5))
    save("01-review.svg", "".join(b), h=440)

def fig2():
    b = []
    b.append(text(W/2, 34, "新人视角自查五问", 16, bold=True))
    qs = [
        ("① 黑话检查", "哪个词只有我知道意思？", "「五道闸」首现处要括注"),
        ("② 跳步检查", "哪步我默认了读者知道？", "「run_s45」要说是管道名"),
        ("③ 孤数字检查", "哪个数字没有口径？", "每个数字旁要有「怎么测的」"),
        ("④ 断言检查", "哪个结论没有证据？", "每个「应该」要有 IR/数字"),
        ("⑤ 导航检查", "哪个文档找不到入口？", "README 之间的互链"),
    ]
    for i, (name, q, fix) in enumerate(qs):
        y = 60 + i * 90
        b.append(hand_rect(60, y, 960, 78, fill=BLUE, opacity=0.25))
        b.append(text(160, y + 26, name, 12, bold=True))
        b.append(text(480, y + 26, q, 11))
        b.append(text(480, y + 54, f"修复：{fix}", 10, fill=MUTED))
    b.append(hand_rect(60, 520, 960, 56, fill="#F5E9C8", opacity=0.85))
    b.append(text(W/2, 544, "五问过一遍的结论：五份文档黑话已注释、跳步有出处列缓解、口径三件套齐备", 11, bold=True))
    b.append(text(W/2, 566, "（「删除只对自己有意义的表述」不是删内容——是把私人知识翻译成公共语言）", 10.5))
    save("02-newcomer.svg", "".join(b), h=590)

def fig3():
    b = []
    b.append(text(W/2, 34, "第 24 周启动：面试转化（D162~168）", 16, bold=True))
    week24 = [
        ("D162", "多层 IR/MLIR/SSA", "「为什么需要多层 IR」等 3 题标答"),
        ("D163", "融合/Layout/正确性", "「融合为什么不总是更快」等 2 题＋正反例"),
        ("D164", "动态 Shape/Runtime", "「动态 Shape 难在哪」等 2 题＋分发流程图"),
        ("D165", "Tiling/内存/性能", "「Tile 由什么决定」等 2 题＋性能数据"),
        ("D166", "调试/数值", "「怎么定位 Pass 错误」等 2 题＋流程演示"),
        ("D167", "模拟讲解", "20 分钟项目讲解＋10 分钟问答"),
        ("D168", "最终验收", "清单执行＋下一阶段方向选择"),
    ]
    for i, (d, name, note) in enumerate(week24):
        y = 60 + i * 82
        color = PURPLE if d == "D168" else GREEN
        b.append(hand_rect(60, y, 960, 70, fill=color, opacity=0.3))
        b.append(text(120, y + 28, d, 12, bold=True))
        b.append(text(350, y + 28, name, 11.5))
        b.append(text(720, y + 28, note, 10, fill=MUTED))
    b.append(hand_rect(60, 650, 960, 56, fill="#F5E9C8", opacity=0.85))
    b.append(text(W/2, 674, "面试转化的原则：标准回答＝结论＋机制＋项目例子＋限制——四段式", 12, bold=True))
    b.append(text(W/2, 696, "「项目例子」全部来自本仓库的实测（数字/IR/反例）——这是 22 周积累的面试价值", 10.5))
    save("03-week24.svg", "".join(b), h=720)

if __name__ == "__main__":
    fig1()
    fig2()
    fig3()
