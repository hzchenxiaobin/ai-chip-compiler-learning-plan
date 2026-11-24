#!/usr/bin/env python3
"""第 141 天 3 张 SVG。种子 141。"""
from __future__ import annotations
import math, os, random
import xml.sax.saxutils as su
random.seed(141)
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
    b.append(text(W/2, 34, "四选一：候选对比与唯一目标的选定", 16, bold=True))
    cands = [
        ("动态 Shape＋自动调度", "高", "中", "三件套已就位，缺块循环", "✓ 选定", GREEN),
        ("INT8 量化", "中高", "高", "kernel 侧断裂", "×", RED),
        ("Conv 算子", "中", "高", "循环结构差异大", "×", RED),
        ("自动调优搜索", "高", "中高", "搜索器在、接口未通", "×（并入调度）", ORANGE),
    ]
    for i, (name, rel, cost, link, verdict, color) in enumerate(cands):
        y = 60 + i * 100
        b.append(hand_rect(60, y, 960, 88, fill=color, opacity=0.25))
        b.append(text(240, y + 26, name, 13, bold=True))
        b.append(text(240, y + 50, f"相关性 {rel}｜成本 {cost}", 10.5))
        b.append(text(240, y + 72, f"衔接：{link}", 9.5, fill=MUTED))
        b.append(text(800, y + 48, verdict, 15, bold=True,
                      fill="#4a7c59" if "✓" in verdict else RED))
    b.append(hand_rect(60, 470, 960, 60, fill="#F5E9C8", opacity=0.85))
    b.append(text(W/2, 494, "选定的判据：衔接＞相关性＞成本——已经修好的路（D128/D129）延伸一米，", 11.5, bold=True))
    b.append(text(W/2, 516, "比从零铺一条新路（INT8 kernel/Conv 结构）便宜十倍；「相关性高但衔接断裂」是诱惑型陷阱", 10.5))
    save("01-choice.svg", "".join(b), h=540)

def fig2():
    b = []
    b.append(text(W/2, 34, "一页扩展设计：输入、输出、完成标准、明确不做", 16, bold=True))
    quads = [
        ("输入", "main.graph＋--tile M,N,K\n（CLI 参数 D120 已有）", GREEN),
        ("输出", "块循环 kernel＋可测的\n产物/性能差异", BLUE),
        ("完成标准（5 条）", "块循环 IR 生成／tile 改变→\n产物改变／fuzz 200 组过／\n性能差异可测／接入分发器", ORANGE),
        ("明确不做（4 条）", "自动搜索×／双缓冲×／\n依赖重排×／GPU×", RED),
    ]
    for i, (name, body, color) in enumerate(quads):
        x = 60 + (i % 2) * 480
        y = 60 + (i // 2) * 180
        b.append(hand_rect(x, y, 440, 160, fill=color, opacity=0.3))
        b.append(text(x + 220, y + 28, name, 13, bold=True))
        for j, line in enumerate(body.split("\n")):
            b.append(text(x + 220, y + 56 + j*22, line, 10.5))
    b.append(hand_rect(60, 430, 960, 90, fill="#F5E9C8", opacity=0.8))
    b.append(text(W/2, 456, "「明确不做」是防火墙——范围失控是扩展周的第一死因：", 12, bold=True))
    b.append(text(W/2, 480, "每一条 × 都对应一个「下周可能会想加」的诱惑；写下来的作用是——周四凌晨两点想加的时候有东西拦你", 10.5))
    b.append(text(W/2, 502, "风险预案：边界钳制写错→fuzz 抓住；tile 太小反超→性能反例是合法结果（D153 伏笔）", 10.5, MUTED))
    save("02-design.svg", "".join(b), h=530)

def fig3():
    b = []
    b.append(text(W/2, 34, "第 21 周七天节奏：从设计到验收", 16, bold=True))
    days = [
        ("D141 今天", "唯一目标＋设计一页", "四选一完成"),
        ("D142", "实现方案", "接口/文件/测试计划"),
        ("D143", "最小正向路径", "块循环 IR 首次生成"),
        ("D144", "约束与失败路径", "边界钳制＋负例"),
        ("D145", "与现有优化集成", "接分发器＋全管道"),
        ("D146", "扩展验收", "5正/3负/2边界"),
        ("D147", "复盘＋删分支", "可维护版本"),
    ]
    for i, (d, name, note) in enumerate(days):
        y = 60 + i * 88
        color = GREEN if i == 0 else (PURPLE if i == 6 else BLUE)
        b.append(hand_rect(60, y, 960, 76, fill=color, opacity=0.3))
        b.append(text(140, y + 26, d, 13, bold=True))
        b.append(text(140, y + 50, note, 10))
        b.append(text(480, y + 38, name, 12))
    b.append(hand_rect(60, 690, 960, 50, fill="#F5E9C8", opacity=0.8))
    b.append(text(W/2, 712, "节奏的设计逻辑：先窄后宽（143 最小→144 约束→145 集成）——每步都可停、可验收", 11, bold=True))
    b.append(text(W/2, 732, "（第一死因是范围失控、第二死因是「第一天就想做完」）", 10, MUTED))
    save("03-week21.svg", "".join(b), h=760)

if __name__ == "__main__":
    fig1()
    fig2()
    fig3()
