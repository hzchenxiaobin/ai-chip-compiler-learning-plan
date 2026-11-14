#!/usr/bin/env python3
"""生成第 127 天（Compiler/Runtime 职责）的 3 张 SVG 图。种子 127。"""
from __future__ import annotations

import math
import os
import random
import xml.sax.saxutils as su

random.seed(127)

BG = "#FDFBF6"; BORDER = "#E7DFCE"; INK = "#3B3B3B"; MUTED = "#6b6257"
ORANGE = "#E8A87C"; BLUE = "#A9C4D4"; GREEN = "#9CBF8E"; RED = "#C97B7B"
PURPLE = "#B8A7CE"
FONT = "'Comic Sans MS','Kaiti SC','KaiTi','STKaiti',cursive"
W, H = 1080, 760
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "images")


def jit(m=1.6):
    return random.uniform(-m, m)


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


# 图 1：overview
def fig1():
    b = []
    b.append(text(W/2, 34, "Compiler 与 Runtime 的边界：11 个决策点逐项审计", 16, bold=True))
    # 左右分界
    b.append(hand_rect(60, 60, 440, 480, fill=BLUE, opacity=0.3))
    b.append(text(280, 88, "编译期（Compiler）", 14, bold=True))
    b.append(text(280, 110, "COMPILE ×4 ——「纯静态派」", 11, fill=BLUE, bold=True))
    compile_items = [
        ("Shape 确定", "S2 从图推断（三来源）", "stage-2 签名 memref<4x6>"),
        ("Stride/布局", "行主序写死", "签名 strided<[6,1]>"),
        ("Tile 参数", "CLI 传入", "manifest.tile 记录"),
        ("Kernel 选择", "单一展开路径", "无备选——D129 引入"),
    ]
    y = 134
    for item, how, ev in compile_items:
        b.append(hand_rect(80, y, 400, 88, fill=BG, opacity=0.9))
        b.append(text(100, y + 22, item, 11.5, bold=True, anchor="start"))
        b.append(text(100, y + 42, how, 9.5, anchor="start", fill=MUTED))
        b.append(text(100, y + 62, f"证据：{ev}", 9, anchor="start", fill=MUTED))
        y += 96

    b.append(hand_rect(580, 60, 440, 480, fill=ORANGE, opacity=0.3))
    b.append(text(800, 88, "运行期（Runtime）", 14, bold=True))
    b.append(text(800, 110, "RUNTIME/CALLER/IMPLICIT ×3＋NONE ×2", 11, fill=ORANGE, bold=True))
    runtime_items = [
        ("内存分配", "RUNTIME", "kernel 内 malloc(48)（每次调用）", RED),
        ("内存释放", "NONE！", "零处 free——D131 结清", RED),
        ("输入搬运", "CALLER", "driver 构造 desc 传指针（零拷贝）", GREEN),
        ("同步", "IMPLICIT", "C 调用返回=完成（D132 显式化）", BLUE),
        ("Kernel 缓存", "NONE", "每次全管道重跑（D129 雏形）", RED),
    ]
    y = 134
    for item, owner, how, color in runtime_items:
        b.append(hand_rect(600, y, 400, 74, fill=color, opacity=0.3))
        b.append(text(620, y + 20, item, 11.5, bold=True, anchor="start"))
        b.append(text(770, y + 20, owner, 10.5, bold=True, anchor="start", fill=RED if "NONE" in owner else INK))
        b.append(text(620, y + 42, how, 9.5, anchor="start", fill=MUTED))
        y += 82
    # 中缝箭头
    b.append(arrow(504, 300, 576, 300, sw=2.2, label="边界"))
    b.append(text(540, 270, "manifest", 9, MUTED))
    b.append(text(540, 336, "stage-5.ll", 9, MUTED))
    # 底部
    b.append(hand_rect(60, 556, 960, 60, fill="#F5E9C8", opacity=0.8))
    b.append(text(W/2, 580, "审计结论：minic 把能固化的全固化了（COMPILE×4）——运行期只剩分配+搬运+隐式同步；", 11.5, bold=True))
    b.append(text(W/2, 602, "两格 NONE（释放/缓存）是真实系统不能留的空位——下周 D128~D132 逐格填上", 10.5))
    save("01-overview.svg", "".join(b), h=640)


# 图 2：运行时流程图（计划点名的交付物）
def fig2():
    b = []
    b.append(text(W/2, 34, "运行时流程图：一次推理调用在 minic 体系里的完整旅程（计划点名交付物）", 15, bold=True))
    # 泳道
    lanes = [
        ("调用方（Host）", 60, GREEN),
        ("Runtime（今天=隐式）", 320, ORANGE),
        ("Kernel（编译产物）", 640, BLUE),
    ]
    for name, x, color in lanes:
        b.append(hand_rect(x, 60, 280, 520, fill=color, opacity=0.2))
        b.append(text(x + 140, 84, name, 12.5, bold=True))
    # 步骤
    steps = [
        (1, "准备输入 A/B/bias\n构造 desc（56B×3）", "①", "host"),
        (2, "调用 _mlir_ciface\n(out, a, b, bias)", "②", "host→rt"),
        (3, "wrapper 拆描述符\n14+5 个裸参数", "③", "rt"),
        (4, "malloc(48) ←输出缓冲\n（D131 要接管的一步）", "④", "rt→kernel"),
        (5, "三重循环计算\nk 序累加+relu", "⑤", "kernel"),
        (6, "返回描述符\n(sret 写回 *out)", "⑥", "kernel→rt"),
        (7, "同步语义：调用返回\n＝结果就绪（D132）", "⑦", "rt"),
        (8, "driver 读 dc.alloc\n结果可用", "⑧", "host"),
    ]
    lane_x = {"host": 80, "rt": 340, "kernel": 660}
    y = 104
    for num, desc, badge, lane in steps:
        if lane == "host→rt":
            lx = 200
        elif lane == "rt→kernel":
            lx = 480
        elif lane == "kernel→rt":
            lx = 480
        else:
            lx = lane_x[lane] + 20
        w = 240 if lane not in ("host→rt", "rt→kernel", "kernel→rt") else 200
        b.append(hand_rect(lx, y, w, 52, fill=BG, opacity=0.95))
        b.append(text(lx + 22, y + 20, badge, 12, bold=True))
        for j, line in enumerate(desc.split("\n")):
            b.append(text(lx + 46, y + 18 + j*16, line, 9.5, anchor="start"))
        y += 60
    # 箭头连接
    for i in range(len(steps) - 1):
        y1 = 104 + i*60 + 52
        y2 = 104 + (i+1)*60
        b.append(arrow(540, y1, 540, y2 - 2, sw=1.3))
    # 职责标注
    b.append(hand_rect(950, 104, 100, 480, fill=PURPLE, opacity=0.3))
    labels = ["CALLER", "边界", "RUNTIME", "RUNTIME", "COMPILE 产物", "COMPILE 产物", "IMPLICIT", "CALLER"]
    for i, lab in enumerate(labels):
        b.append(text(1000, 130 + i*60, lab, 9, bold=True, fill=PURPLE))
    b.append(text(1000, 620, "归属", 11, bold=True, fill=PURPLE))
    save("02-runtime-flow.svg", "".join(b), h=650)


# 图 3：真实系统对照
def fig3():
    b = []
    b.append(text(W/2, 34, "三个真实系统的对照：同一张表，不同的划法", 16, bold=True))
    systems = [
        ("minic（本教程）", "纯静态派：\nShape/Stride/Tile/Kernel 全编译期\n分配运行期裸 malloc\n释放没人管（NONE）\n同步隐式（C 语义）", "教学取舍：\n能简则简，把复杂性\n留在编译器里", GREEN),
        ("TVM（生产系统）", "编译期：图优化+tiling+schedule\n运行期：TVMModule 加载执行\n内存：调用方给 TVMArray\n缓存：磁盘 cache 按 key\n同步：device stream", "全静态编译+运行时引擎\n的分工范本", BLUE),
        ("PyTorch 2.x（动态）", "编译期（JIT）：捕获 graph\n按 shape 特化编译（D129 同思想）\n缓存：按 shape 的 lru_cache\n动态 shape：回退 eager（D130！）\n同步：async stream", "动态派的工程答案：\n特化+缓存+回退三件套", ORANGE),
    ]
    cw, ch = 310, 330
    cx0 = 40
    for i, (name, body, verdict, color) in enumerate(systems):
        x = cx0 + i * (cw + 20)
        b.append(hand_rect(x, 60, cw, ch, fill=color, opacity=0.32))
        b.append(text(x + cw/2, 86, name, 13, bold=True))
        for j, line in enumerate(body.split("\n")):
            b.append(text(x + cw/2, 112 + j*20, line, 9.5))
        b.append(hand_rect(x + 15, 60 + ch - 60, cw - 30, 50, fill=BG, opacity=0.9))
        for j, line in enumerate(verdict.split("\n")):
            b.append(text(x + cw/2, 60 + ch - 42 + j*16, line, 9.5, fill=MUTED))
    # 底部
    b.append(hand_rect(40, 420, 980, 130, fill="#F5E9C8", opacity=0.8))
    b.append(text(W/2, 446, "划界的普适规律：", 12.5, bold=True))
    rules = [
        "① 越静态的划法性能越好、灵活性越差（minic 极端——编译期做完一切）",
        "② 越动态的划法越灵活、但需要「特化+缓存+回退」三件套兜底（PyTorch 2.x 的答案）",
        "③ 没有标准答案——只有「把哪些决策推给运行期」的显式选择（本周逐天做这个选择）",
    ]
    for j, r in enumerate(rules):
        b.append(text(W/2, 472 + j*24, r, 10.5))
    b.append(text(W/2, 560, "下周地图：D128 运行期参数 → D129 特化 → D130 回退 → D131 内存 → D132 同步 → D133 复盘", 11, MUTED))
    save("03-systems-compare.svg", "".join(b), h=600)


if __name__ == "__main__":
    fig1()
    fig2()
    fig3()
