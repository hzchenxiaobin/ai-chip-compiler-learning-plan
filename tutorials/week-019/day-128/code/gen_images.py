#!/usr/bin/env python3
"""生成第 128 天（运行期参数与 Shape）的 3 张 SVG 图。种子 128。"""
from __future__ import annotations

import math
import os
import random
import xml.sax.saxutils as su

random.seed(128)

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


# 图 1：静态 vs 动态签名的对照
def fig1():
    b = []
    b.append(text(W/2, 34, "Shape 的语义翻转：从编译期常量到运行期参数", 16, bold=True))

    # 两栏对照
    b.append(hand_rect(60, 60, 460, 320, fill=GREEN, opacity=0.3))
    b.append(text(290, 86, "E1 静态基线（D124 原版）", 13.5, bold=True))
    b.append(text(290, 110, "memref<4x6xf32, strided<[6,1]>>", 11, mono=True, fill=MUTED))
    static_items = [
        ("签名", "shape 是类型的一部分（4x6 写死）"),
        ("循环边界", "icmp slt i64 %38, 4 ← 常量 4"),
        ("验证", "一个 shape 编一次 kernel"),
        (".ll 规模", "95 行 / extractvalue 17"),
    ]
    y = 134
    for k, v in static_items:
        b.append(text(100, y, k, 10.5, bold=True, anchor="start"))
        b.append(text(190, y, v, 10, anchor="start", fill=MUTED))
        y += 26
    b.append(hand_rect(80, 244, 420, 120, fill=BG, opacity=0.9))
    b.append(text(100, 266, "  %cM = arith.constant 4 : index", 9.5, mono=True, anchor="start"))
    b.append(text(100, 284, "  %39 = icmp slt i64 %38, 4", 9.5, mono=True, anchor="start", fill=RED))
    b.append(text(100, 308, "  ↑ 常量 4 直接编进指令", 9.5, anchor="start", fill=RED))

    b.append(hand_rect(560, 60, 460, 320, fill=ORANGE, opacity=0.3))
    b.append(text(800, 86, "E2 动态签名（今天实现）", 13.5, bold=True))
    b.append(text(800, 110, "memref<?x?xf32>", 11, mono=True, fill=MUTED))
    dyn_items = [
        ("签名", "shape 是描述符字段（? 占位）"),
        ("循环边界", "icmp slt i64 %44, %29 ← SSA 值"),
        ("验证", "一份 kernel 吃任意 shape"),
        (".ll 规模", "104 行 / extractvalue 23"),
    ]
    y = 134
    for k, v in dyn_items:
        b.append(text(600, y, k, 10.5, bold=True, anchor="start"))
        b.append(text(690, y, v, 10, anchor="start", fill=MUTED))
        y += 26
    b.append(hand_rect(580, 244, 420, 120, fill=BG, opacity=0.9))
    b.append(text(600, 266, "  %M = memref.dim %a, %c0", 9.5, mono=True, anchor="start"))
    b.append(text(600, 284, "  %29 = extractvalue ... 3, 0   // 读 sizes[0]", 9.5, mono=True, anchor="start"))
    b.append(text(600, 302, "  %45 = icmp slt i64 %44, %29", 9.5, mono=True, anchor="start", fill=GREEN))
    b.append(text(600, 326, "  ↑ 与运行期读回的 M 比较", 9.5, anchor="start", fill=GREEN))

    # 中间箭头
    b.append(arrow(524, 220, 556, 220, sw=2.4, label="翻转"))

    # 底：代价表
    b.append(text(W/2, 410, "翻转的代价（TP4 实测）", 14, bold=True))
    costs = [
        (".ll 行数", "95 → 104", "+9%——全是头部开销"),
        ("extractvalue", "17 → 23", "+6：3 个 dim 各读 2 处"),
        ("phi / fmul", "4 / 1 → 4 / 1", "不变！核心循环体零差异"),
        ("执行灵活性", "1 shape", "任意 shape（E3 三组验证）"),
    ]
    y = 432
    for k, v, note in costs:
        color = GREEN if "不变" in note or "任意" in note else BLUE
        b.append(hand_rect(120, y, 840, 36, fill=color, opacity=0.3))
        b.append(text(240, y + 24, k, 11, bold=True))
        b.append(text(420, y + 24, v, 11, mono=True))
        b.append(text(700, y + 24, note, 9.5, anchor="start", fill=MUTED))
        y += 42
    b.append(hand_rect(80, y + 8, 920, 44, fill="#F5E9C8", opacity=0.8))
    b.append(text(W/2, y + 28, "结论：动态化的代价是一次性的头部开销（+9%），核心循环零差异——", 11.5, bold=True))
    b.append(text(W/2, y + 46, "「为什么动态 Shape 不只是把常量改成变量」：还有描述符读回、动态 alloc、验证语义三件事", 10.5))
    save("01-overview.svg", "".join(b), h=y + 70)


# 图 2：描述符的数据流——shape 从哪来
def fig2():
    b = []
    b.append(text(W/2, 34, "运行期 shape 的数据流：从调用方数组到循环边界的三跳", 16, bold=True))

    # 三跳
    hops = [
        ("跳① 调用方", "numpy 数组 A.shape=(4,6)", "make_desc: sh[0]=4, sh[1]=6", GREEN),
        ("跳② 描述符", "56B 结构体经 ABI 传给 kernel", "ciface 拆包→14 个裸参数", BLUE),
        ("跳③ kernel", "memref.dim → extractvalue sizes[0]", "%29 = extractvalue ...3, 0", ORANGE),
    ]
    for i, (title, l1, l2, color) in enumerate(hops):
        x = 60 + i * 330
        b.append(hand_rect(x, 60, 300, 120, fill=color, opacity=0.35))
        b.append(text(x + 150, 86, title, 12.5, bold=True))
        b.append(text(x + 150, 108, l1, 10))
        b.append(text(x + 150, 128, l2, 9.5, mono=True))
        if i < 2:
            b.append(arrow(x + 302, 120, x + 328, 120, sw=1.8))

    # 循环边界的最终形态
    b.append(hand_rect(60, 200, 960, 110, fill=BG, opacity=0.95, sw=1.8))
    b.append(text(W/2, 224, "循环边界的最终形态（.ll 原文对照）", 12.5, bold=True))
    b.append(text(120, 250, "静态：%39 = icmp slt i64 %38, 4          ← 4 是编译期吃进的常量", 10.5, mono=True, anchor="start", fill=RED))
    b.append(text(120, 274, "动态：%45 = icmp slt i64 %44, %29        ← %29 是跳①②③传来的 sizes[0]", 10.5, mono=True, anchor="start", fill=GREEN))
    b.append(text(120, 298, "同一条 icmp 指令、两种操作数来源——这就是「Shape=COMPILE」与「Shape=RUNTIME」在机器码层的全部差别", 10, anchor="start", fill=MUTED))

    # 下：D114 清单的突破
    b.append(text(W/2, 344, "D114「暂不支持清单」第 1 条的正面突破", 14, bold=True))
    b.append(hand_rect(60, 364, 960, 130, fill=PURPLE, opacity=0.3))
    lines = [
        "D114 写下：动态 shape／动态 strides／动态 offset——『运行时才知道 sizes/strides，",
        "描述符填充必须搬到运行期；本周所有 shape 静态已知』——当时的判断完全正确。",
        "",
        "今天补上三件事：①签名 memref<?x?x>（? 占位）；②memref.dim 读描述符（跳③）；",
        "③memref.alloc(%M, %N) 动态分配输出——清单第 1 条从「暂不支持」变「已支持」。",
    ]
    for j, line in enumerate(lines):
        b.append(text(100, 390 + j*22, line, 10.5, anchor="start"))

    # 底：E3 的三组验证
    b.append(text(W/2, 522, "E3 三组 shape 执行验证（一份 .ll 吃三种 shape）", 14, bold=True))
    shapes = [
        ("4x6 @ 6x3", "C[0][1]=24.5 ✓", "D118 手算锚点"),
        ("3x4 @ 4x2", "C[0][1]=6.0 ✓", "非方形 shape"),
        ("8x8 @ 8x8", "C[3][5]=58.0 ✓", "更大规模"),
    ]
    for i, (s, r, note) in enumerate(shapes):
        x = 100 + i * 300
        b.append(hand_rect(x, 542, 280, 70, fill=GREEN, opacity=0.4))
        b.append(text(x + 140, 566, s, 12, bold=True, mono=True))
        b.append(text(x + 140, 586, r, 10.5, fill="#4a7c59"))
        b.append(text(x + 140, 604, note, 9.5, fill=MUTED))
    save("02-mechanism.svg", "".join(b), h=630)


# 图 3：动态的完整清单与下周预告
def fig3():
    b = []
    b.append(text(W/2, 34, "「动态 Shape 不只是把常量改成变量」——完整差异清单", 16, bold=True))

    # 六件事清单
    items = [
        ("① 签名形态", "memref<4x6, strided<[6,1]>> → memref<?x?x>", "类型里的 shape 消失、描述符扛起语义", GREEN),
        ("② shape 读回", "arith.constant 4 → memref.dim + extractvalue", "每个用 shape 的地方都要从描述符读（+6 处）", BLUE),
        ("③ 输出分配", "memref.alloc() : memref<4x3> → memref.alloc(%M, %N)", "输出 shape 也是运行期的——alloc 带 shape 参数", ORANGE),
        ("④ 循环边界", "icmp slt %38, 4 → icmp slt %44, %29", "比较的操作数从立即数变 SSA 值", BLUE),
        ("⑤ 验证语义", "一个 golden → 按 shape 参数化验证", "golden 生成器要吃 shape（E3 的三组）", PURPLE),
        ("⑥ 性能语义", "编译器优化空间缩小（边界未知→不敢展开/向量化）", "D125 的 -O2 展开在动态版会消失！", RED),
    ]
    y = 60
    for title, diff, note, color in items:
        b.append(hand_rect(60, y, 960, 76, fill=color, opacity=0.3))
        b.append(text(90, y + 24, title, 12, bold=True, anchor="start"))
        b.append(text(280, y + 24, diff, 10, mono=True, anchor="start"))
        b.append(text(90, y + 52, note, 10, anchor="start", fill=MUTED))
        y += 84

    # 底：权衡
    b.append(hand_rect(60, y + 10, 960, 90, fill="#F5E9C8", opacity=0.8))
    b.append(text(W/2, y + 34, "静态 vs 动态的权衡（今天有了实测数字）", 12.5, bold=True))
    b.append(text(W/2, y + 58, "静态：每 shape 编一次（编译成本×N）＋优化空间大（-O2 敢展开）｜动态：一份 .ll 走天下（+9% 头部）＋优化保守", 10.5))
    b.append(text(W/2, y + 80, "两全其美的路：动态签名兜底＋按热点 shape 特化（D129）＋缓存特化产物——PyTorch 2.x 的三件套明天开始搭", 10.5, fill="#4a7c59"))
    save("03-example.svg", "".join(b), h=y + 120)


if __name__ == "__main__":
    fig1()
    fig2()
    fig3()
