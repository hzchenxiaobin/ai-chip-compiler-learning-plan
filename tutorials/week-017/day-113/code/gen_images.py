#!/usr/bin/env python3
"""生成第 113 天的 3 张手绘 sketch 风 SVG 技术图（Excalidraw-like）。

风格与 D110~D112 一致：白板涂鸦感——带抖动的贝塞尔手绘路径、
马克笔笔触、3～4 种柔和强调色（蓝/橙/绿/红）＋米白背景、简单几何
形状、手写感字体。所有数字来自 outputs/ 的真实冻结运行
（stats_step.json / step.ll / step_aarch64.s / step_x86_64.s，
2026-11-13，llvmlite 内嵌 LLVM 22.1.0）。固定随机种子，图可复现。
"""

from __future__ import annotations

import json
import math
import os
import random
import xml.sax.saxutils as su

random.seed(113)

BG = "#FDFBF6"
BORDER = "#E7DFCE"
INK = "#3B3B3B"
MUTED = "#6b6257"
ORANGE = "#E8A87C"
BLUE = "#A9C4D4"
GREEN = "#9CBF8E"
RED = "#C97B7B"
FONT = "'Comic Sans MS','Kaiti SC','KaiTi','STKaiti',cursive"


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


def hand_line(x1, y1, x2, y2, stroke=INK, sw=1.4, dash=None):
    dd = f' stroke-dasharray="{dash}"' if dash else ""
    mx, my = (x1 + x2) / 2 + jit(2.5), (y1 + y2) / 2 + jit(2.5)
    d = (f"M {x1 + jit():.1f},{y1 + jit():.1f} Q {mx:.1f},{my:.1f} "
         f"{x2 + jit():.1f},{y2 + jit():.1f}")
    return (f'<path d="{d}" stroke="{stroke}" stroke-width="{sw}" '
            f'stroke-linecap="round" fill="none"{dd}/>')


def arrow(x1, y1, x2, y2, stroke=INK, sw=1.8, dash=None):
    dd = f' stroke-dasharray="{dash}"' if dash else ""
    mx, my = (x1 + x2) / 2 + jit(2.0), (y1 + y2) / 2 + jit(2.0)
    ang = math.atan2(y2 - y1, x2 - x1)
    hx, hy = x2 - 9 * math.cos(ang), y2 - 9 * math.sin(ang)
    a1 = (hx + 5 * math.cos(ang + 2.5), hy + 5 * math.sin(ang + 2.5))
    a2 = (hx + 5 * math.cos(ang - 2.5), hy + 5 * math.sin(ang - 2.5))
    d = (f"M {x1 + jit():.1f},{y1 + jit():.1f} Q {mx:.1f},{my:.1f} "
         f"{x2:.1f},{y2:.1f} M {a1[0]:.1f},{a1[1]:.1f} L {x2:.1f},{y2:.1f} "
         f"L {a2[0]:.1f},{a2[1]:.1f}")
    return (f'<path d="{d}" stroke="{stroke}" stroke-width="{sw}" '
            f'stroke-linecap="round" fill="none"{dd}/>')


def text(x, y, s, size=13, fill=INK, anchor="middle", bold=False, mono=False):
    s = su.escape(s)
    wt = ' font-weight="bold"' if bold else ""
    fam = "'Courier New',monospace" if mono else FONT
    return (f'<text x="{x}" y="{y}" font-family="{fam}" font-size="{size}" '
            f'fill="{fill}" text-anchor="{anchor}"{wt}>{s}</text>')


def frame(w, h, title):
    body = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
            f'font-family="{FONT}">',
            hand_rect(4, 4, w - 8, h - 8, BG, 1.0, BORDER, 2),
            text(w / 2, 34, title, 18, INK, "middle", True)]
    return body


def save(name, body):
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "..", "images", name)
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(body) + "\n</svg>\n")
    print(f"  已生成 images/{name}")


def card(b, x, y, w, h, title, lines, fill, tsize=11.5, lsize=10,
         opacity=0.42, anchor_left=False, mono_lines=None):
    b.append(hand_rect(x, y, w, h, fill, opacity, INK, 1.6))
    ax = x + 12 if anchor_left else x + w / 2
    aanchor = "start" if anchor_left else "middle"
    if title:
        b.append(text(ax, y + 19, title, tsize, INK, aanchor, True))
    for i, ln in enumerate(lines):
        b.append(text(ax, y + 38 + i * 16.5, ln, lsize, INK, aanchor))
    for i, ln in enumerate(mono_lines or []):
        b.append(text(ax, y + 38 + len(lines) * 16.5 + i * 15, ln, 9.5,
                      MUTED, aanchor, mono=True))


# ======================= 图 1：全局定位图 =======================

def fig1():
    W, H = 1020, 700
    b = frame(W, H, "第 113 天定位：从 MLIR 的最后一层跨进 LLVM 的世界")
    b.append(hand_line(320, 44, 700, 45, ORANGE, 3))

    # 上排：前四个阶段的 MLIR 层（领域信息逐层减少）
    b.append(text(48, 70, "前 16 周：mini 编译器的 MLIR 各层（离硬件越近，领域信息越少）",
                  12.5, INK, "start", True))
    layers = [
        ("图 IR（mini 方言）", BLUE,
         ["mini.matmul / mini.relu", "Shape、广播等语义约束", "D12~D48 建成"]),
        ("循环层", GREEN,
         ["三重循环 + Tiling 外壳", "循环序 / 展开等结构", "D85~D96 Lowering"]),
        ("内存层", ORANGE,
         ["生命周期 / 缓冲复用", "片上空间闸门", "D97~D105 规划"]),
        ("调优层（search）", RED,
         ["候选空间 25.77B→12,970", "Cost Model + 实测决赛", "D106~D112 选择"]),
    ]
    x0, y0, cw, ch, gap = 48, 82, 214, 112, 20
    for i, (title, col, lines) in enumerate(layers):
        x = x0 + i * (cw + gap)
        card(b, x, y0, cw, ch, title, lines, col, 10.5, 9.5, 0.4)
        if i < 3:
            arrow(x + cw + 2, y0 + ch / 2, x + cw + gap - 2, y0 + ch / 2, INK, 2)

    # 中间：LLVM Dialect（今天）
    cx, cy, cw2, ch2 = 200, 244, 620, 118
    b.append(hand_rect(cx, cy, cw2, ch2, BG, 1.0, ORANGE, 2.6))
    b.append(text(cx + cw2 / 2, cy + 22, "D113（今天）：LLVM Dialect——MLIR 里长得最像 LLVM 的一层",
                  13, INK, "middle", True))
    b.append(text(cx + cw2 / 2, cy + 44,
                  "llvm.func / llvm.add / llvm.cond_br …（还是 MLIR 的 Operation，还能被 Pass 改写）",
                  10.5, INK))
    b.append(text(cx + cw2 / 2, cy + 63,
                  "学习重点①：它和 LLVM IR 是什么关系（读写对照）",
                  10.5, INK))
    b.append(text(cx + cw2 / 2, cy + 82,
                  "学习重点②：目标无关优化和目标相关编译的分界在哪（下两层）",
                  10.5, INK))
    b.append(text(cx + cw2 / 2, cy + 104,
                  "实践：读 step 函数的两侧形态，标注参数 / 返回值 / 基本块",
                  10.5, MUTED))
    arrow(500, 196, 500, 240, ORANGE, 2.4)

    # 下排：LLVM IR → 汇编
    y2 = 414
    card(b, 170, y2, 300, 128, "LLVM IR（另一个世界）", [
        "define i32 @step(i32 %0) { … }",
        "真实 LLVM 的中间表示：", "SSA + 基本块 + phi",
        "目标无关优化在这里做", "（instcombine / sccp / simplifycfg）"],
        BLUE, 11, 9.6, 0.45)
    card(b, 550, y2, 300, 128, "汇编 / 机器码", [
        "aarch64: csel w0, w8, w9, gt",
        "x86_64:  cmovll %ecx, %eax",
        "目标相关编译的产物：", "指令选择 + 寄存器分配 + 调度",
        "换目标 = 换指令集"],
        GREEN, 11, 9.6, 0.45)
    arrow(478, y2 + 64, 544, y2 + 64, INK, 2.2)
    b.append(text(510, y2 + 52, "指令选择", 9.5, MUTED))
    arrow(500, 366, 500, 410, ORANGE, 2.4)
    b.append(text(512, 392, "mlir-translate --mlir-to-llvmir（今天用教学版复刻）", 9.5,
                  MUTED))

    # 底部：本周路线
    y3 = 590
    b.append(text(48, y3 - 12, "第 17 周路线：把 mini 一路降到能跑", 12, INK,
                  "start", True))
    days = [
        ("D113 今天", ORANGE, "理解 LLVM Dialect", "↔ LLVM IR"),
        ("D114", BLUE, "设计最终", "Lowering 路径"),
        ("D115", GREEN, "转换函数", "与类型"),
        ("D116", BLUE, "转换 elementwise", "算子"),
        ("D117", GREEN, "导出", "LLVM IR"),
        ("D118", RED, "JIT / AOT", "执行"),
    ]
    x0, cw3, gap = 48, 148, 14
    for i, (t, col, sub, sub2) in enumerate(days):
        x = x0 + i * (cw3 + gap)
        b.append(hand_rect(x, y3, cw3, 66, col, 0.42 if i else 0.62,
                           ORANGE if i == 0 else INK, 1.6))
        b.append(text(x + cw3 / 2, y3 + 18, t, 11, INK, "middle", True))
        b.append(text(x + cw3 / 2, y3 + 36, sub, 8.8, INK, "middle"))
        b.append(text(x + cw3 / 2, y3 + 52, sub2, 8.8, INK, "middle"))
        if i < 5:
            arrow(x + cw3 + 1, y3 + 33, x + cw3 + gap - 1, y3 + 33, MUTED, 1.6)
    b.append(text(48, 682, "一句话：LLVM Dialect 是桥——左边还能用 MLIR 的 Pass 生态，右边一步就跨进 LLVM 的优化与代码生成。",
                  10.5, MUTED, "start"))

    save("01-overview.svg", b)


# ======================= 图 2：核心机制图 =======================

def fig2():
    W, H = 1020, 740
    b = frame(W, H, "核心机制：同一个 step 函数的两种写法（数据全部来自真实导出）")

    # 左栏：LLVM Dialect
    b.append(hand_rect(30, 60, 430, 500, BLUE, 0.30, INK, 1.8))
    b.append(text(245, 84, "LLVM Dialect（MLIR 侧）", 13.5, INK, "middle", True))
    b.append(text(245, 104, "step.mlir——值和块都有名字，常量是显式 Operation",
                  9.5, MUTED))
    mlir_lines = [
        "llvm.func @step(%arg0: i32) -> i32 {",
        "  %c2  = llvm.mlir.constant(2 : i32) : i32",
        "  %c3  = llvm.mlir.constant(3 : i32) : i32",
        "  %c4  = llvm.mlir.constant(4 : i32) : i32",
        "  %c0  = llvm.mlir.constant(0 : i32) : i32",
        "  %five = llvm.add %c2, %c3 : i32",
        "  %s20  = llvm.mul %five, %c4 : i32",
        "  %z    = llvm.add %arg0, %c0 : i32",
        "  %cond = llvm.icmp \"sgt\" %z, %s20 : i32",
        "  llvm.cond_br %cond, ^hi, ^lo",
        "^hi:",
        "  %x1 = llvm.add %z, %s20 : i32",
        "  llvm.br ^merge(%x1 : i32)",
        "^lo:",
        "  %x2 = llvm.sub %z, %s20 : i32",
        "  llvm.br ^merge(%x2 : i32)",
        "^merge(%m: i32):",
        "  llvm.return %m : i32",
        "}",
    ]
    for i, ln in enumerate(mlir_lines):
        b.append(text(50, 128 + i * 22, ln, 9.2, INK, "start", mono=True))

    # 右栏：LLVM IR
    b.append(hand_rect(560, 60, 430, 500, GREEN, 0.28, INK, 1.8))
    b.append(text(775, 84, "LLVM IR（导出后）", 13.5, INK, "middle", True))
    b.append(text(775, 104, "step.ll——名字消失，槽位编号；常量内联；phi 出现",
                  9.5, MUTED))
    ll_lines = [
        "define i32 @step(i32 %0) {",
        "  %2 = add i32 2, 3",
        "  %3 = mul i32 %2, 4",
        "  %4 = add i32 %0, 0",
        "  %5 = icmp sgt i32 %4, %3",
        "  br i1 %5, label %6, label %8",
        "6:",
        "  %7 = add i32 %4, %3",
        "  br label %10",
        "8:",
        "  %9 = sub i32 %4, %3",
        "  br label %10",
        "10:",
        "  %11 = phi i32 [ %7, %6 ], [ %9, %8 ]",
        "  ret i32 %11",
        "}",
    ]
    for i, ln in enumerate(ll_lines):
        b.append(text(580, 128 + i * 25, ln, 9.8, INK, "start", mono=True))
    b.append(text(775, 540, "（; preds 注释是真实 LLVM 打印时自动加的，", 8.6, MUTED))
    b.append(text(775, 554, "见 outputs/opt_before_step.ll）", 8.6, MUTED))

    # 中缝：三条规则的徽章 + 双向箭头
    rules_pos = [
        ("R1", 128),   # 靠函数签名行
        ("R2", 230),   # 靠常量行
        ("R3", 430),   # 靠 phi 行
    ]
    for tag, y in rules_pos:
        b.append(hand_rect(487, y - 14, 46, 28, ORANGE, 0.75, INK, 1.6))
        b.append(text(510, y + 5, tag, 11, INK, "middle", True))
        arrow(483, y, 462, y, RED, 1.8)
        arrow(537, y, 558, y, RED, 1.8)

    # 底部：三条规则的完整解释（横排三卡）
    rule_cards = [
        ("R1 重编号", [
            "%arg0→%0；^hi→6:、^lo→8:、^merge→10:",
            "值名/块名不跨语言保留；未命名的",
            "基本块和指令结果共用一个编号池"]),
        ("R2 常量内联", [
            "%c2~%c0 四条常量 op 全部消失，",
            "2、3、4、0 直接写进操作数位置，",
            "不占槽位、不产生指令"]),
        ("R3 块参数→phi", [
            "^merge(%m:i32) → %11 = phi …",
            "MLIR 在块边界传值（llvm.br 带参）；",
            "LLVM IR 在块首用 phi 汇合"]),
    ]
    for i, (t, lines) in enumerate(rule_cards):
        x = 60 + i * 310
        b.append(hand_rect(x, 586, 290, 96, ORANGE, 0.5, INK, 1.5))
        b.append(text(x + 145, 604, t, 11, INK, "middle", True))
        for j, ln in enumerate(lines):
            b.append(text(x + 145, 624 + j * 16, ln, 8.4, INK, "middle"))
    b.append(text(510, 700, "同一层语义、两种书写系统：MLIR 用『Operation + 块参数』组织，LLVM IR 用『指令 + phi』组织——跨过去以后 LLVM 的优化器和后端接管。",
                  10.5, INK, "middle", True))
    b.append(text(510, 720, "教学版 mini_translate.py 复刻真实 mlir-translate --mlir-to-llvmir 的三条关键规则。",
                  9, MUTED, "middle"))

    save("02-mechanism.svg", b)


# ======================= 图 3：实例对照图 =======================

def fig3():
    stats = json.load(open(os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "outputs", "stats_step.json"), encoding="utf-8"))
    before = stats["before"][0]
    after = stats["after"][0]

    W, H = 1020, 700
    b = frame(W, H, "实例对照：目标无关优化 → 目标相关编译（真实运行结果）")

    # 上半：优化前后
    b.append(text(48, 66, "① 目标无关优化（IR → IR）：只看 IR 能证明的事实，不看任何 CPU",
                  12.5, INK, "start", True))
    card(b, 60, 80, 380, 190, "优化前（step.ll 导出后）", [
        f"基本块 {before['blocks']} 个（entry / 6: / 8: / 10:）",
        f"指令 {before['instructions']} 条 / SSA 值 {before['ssa_values']} 个",
        "2+3 没折、×4 没折、a+0 没消",
        "四个块、一个 phi 汇合"],
        RED, 10.5, 9.6, 0.4, anchor_left=True,
        mono_lines=["  %3 = mul i32 %2, 4", "  %4 = add i32 %0, 0",
                    "  br i1 %5, label %6, label %8",
                    "  %11 = phi i32 [ %7, %6 ], …"])
    card(b, 580, 80, 380, 190, "优化后（同一份 IR，3 个 pass 之后）", [
        f"基本块 {after['blocks']} 个（只剩 entry！）",
        f"指令 {after['instructions']} 条 / SSA 值 {after['ssa_values']} 个",
        "2+3 → 5、5×4 → 20、a+0 → a",
        "分支+phi 折成 select"],
        GREEN, 10.5, 9.6, 0.4, anchor_left=True,
        mono_lines=["  %2 = icmp sgt i32 %0, 20",
                    "  %5 = select i1 %2, i32 %3, i32 %4",
                    "  ret i32 %5"])
    arrow(452, 172, 570, 172, INK, 2.4)
    b.append(text(510, 150, "instcombine + sccp", 9.5, MUTED))
    b.append(text(510, 164, "+ simplifycfg", 9.5, MUTED))
    b.append(hand_line(40, 300, 980, 302, ORANGE, 2.5))
    b.append(text(510, 292, "目标无关 | 目标相关的分界线：上面不看 CPU，下面必须选 CPU",
                  10, MUTED))

    # 下半：两个目标
    b.append(text(48, 336, "② 目标相关编译（IR → 汇编）：同一份优化后 IR，交给两个目标",
                  12.5, INK, "start", True))
    card(b, 60, 350, 380, 210, "aarch64（-O2，4 条指令）", [
        "指令选择：csel（条件选择）",
        "寄存器：w0/w8/w9（32 位）",
        "常数直接当立即数 #20"],
        BLUE, 10.5, 9.8, 0.4, anchor_left=True,
        mono_lines=["  add   w8, w0, #20", "  subs  w9, w0, #20",
                    "  csel  w0, w8, w9, gt", "  ret"])
    card(b, 580, 350, 380, 210, "x86_64（-O2，5 条指令）", [
        "指令选择：leal 算地址式加法 + cmovll",
        "寄存器：edi/ecx/eax（32 位视图）",
        "比较写成 cmpl $21（= 20+1 的无溢出写法）"],
        BLUE, 10.5, 9.8, 0.4, anchor_left=True,
        mono_lines=["  leal   -20(%rdi), %ecx",
                    "  leal    20(%rdi), %eax",
                    "  cmpl   $21, %edi",
                    "  cmovll %ecx, %eax", "  retq"])
    arrow(470, 200, 250, 348, INK, 1.8, dash="6 5")
    arrow(540, 200, 770, 348, INK, 1.8, dash="6 5")
    b.append(text(300, 300, "同一份 IR", 9.5, MUTED))
    b.append(text(720, 300, "同一份 IR", 9.5, MUTED))

    # 底部：对照实验结论
    b.append(hand_rect(60, 592, 900, 84, ORANGE, 0.35, INK, 1.8))
    b.append(text(510, 614, "5.4 节的两组对照实验（真实复现）", 11, INK, "middle", True))
    b.append(text(510, 634, "A. 乘数 4→5：优化后 IR 的 20 全变 25，aarch64 立即数 #25、x86 leal ±25——源码常量一路流到机器码",
                  9.6, INK))
    b.append(text(510, 652, "B. 加一条从未使用的 %dead：优化前 12 条指令，优化后回到 5 条——『没用到的计算』不看 CPU 就能删",
                  9.6, INK))
    b.append(text(510, 670, f"环境：Python {stats['python']} / llvmlite 内嵌 LLVM {stats['llvm_version']} / {stats['machine']}，2026-11-13 冻结运行",
                  9, MUTED))

    save("03-example.svg", b)


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    os.makedirs(os.path.join(here, "..", "images"), exist_ok=True)
    print("生成第 113 天的 3 张图：")
    fig1()
    fig2()
    fig3()


if __name__ == "__main__":
    main()
