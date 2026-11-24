#!/usr/bin/env python3
"""生成第 124 天（端到端 MatMul+Bias+Relu）的 3 张手绘 sketch 风 SVG 图。

数字来自 outputs/report.txt 与 e2e-run/ 真实运行（2026-11-14，
macOS arm64，LLVM 23.1.5）。固定随机种子 124。
"""
from __future__ import annotations

import math
import os
import random
import xml.sax.saxutils as su

random.seed(124)

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


# ── 图 1：端到端全景——七个阶段全部真实 ──
def fig1():
    b = []
    b.append(text(W/2, 34, "首个完整项目可运行版本：从图 IR 到机器码到 numpy 对照", 16, bold=True))

    # 七阶段横条（全部真实）
    stages = [
        ("S0", "读入", "11 节点\n.graph", GREEN),
        ("S1", "图优化", "11→5 节点\n融合！D121", GREEN),
        ("S2", "循环生成", "点循环写全\n34 行 MLIR", BLUE),
        ("S3", "Tiling", "朴素版\n（tile 留 D125）", BLUE),
        ("S4", "LLVM Lower", "七 pass\n胶水 0", ORANGE),
        ("S5", "代码生成", ".ll 62 行\nllc .s", ORANGE),
        ("S6", "验证！", "AOT 执行\n12/12 bitwise", RED),
    ]
    sw_, sh_, sgap = 140, 108, 14
    sx0 = (W - (sw_*7 + sgap*6)) / 2
    for i, (sid, name, desc, color) in enumerate(stages):
        x = sx0 + i * (sw_ + sgap)
        b.append(hand_rect(x, 60, sw_, sh_, fill=color, opacity=0.5))
        b.append(text(x + sw_/2, 84, sid + " ✓", 12.5, bold=True))
        b.append(text(x + sw_/2, 102, name, 11))
        for j, line in enumerate(desc.split("\n")):
            b.append(text(x + sw_/2, 120 + j*15, line, 9))
        if i < 6:
            b.append(arrow(x + sw_ + 1, 114, x + sw_ + sgap - 1, 114, sw=1.4))
    b.append(text(W/2, 192, "第 18 周五天的接入在这条线上会师：D121 的 S1、D122 的 S2~S5、D123 的可观测、今天补全 S2 点循环＋S6 验证", 11, MUTED))

    # 中：验证现场
    b.append(text(W/2, 232, "S6 验证现场（12/12 bitwise 一致）", 14, bold=True))
    b.append(hand_rect(200, 252, 680, 190, fill=BG, opacity=0.95, sw=1.8))
    rows = [
        ("C[0] = 22.1250", "relu(0.125 + 0.5×1−1×4+2×7+0+1.5×13−0.5×16)", GREEN),
        ("C[1] = 24.2500", "relu(-0.25 + 0.5×2−1×5+2×8+0+1.5×14−0.5×17)  ← 手算锚点", ORANGE),
        ("C[4] = 56.7500", "relu(-0.25 + 1×2+1×5+1×8+1×11+1×14+1×17)", GREEN),
        ("C[6] = 49.1250", "relu(0.125 + (−2)×1+0.5×4+0×7+3×10−1×13+2×16)", GREEN),
        ("C[11] = 27.5000", "relu(0.5 + 0×3+0×6+0.5×9+0.5×12+0.5×15+0.5×18)", GREEN),
    ]
    y = 274
    for cv, calc, color in rows:
        b.append(hand_rect(220, y, 640, 28, fill=color, opacity=0.3))
        b.append(text(330, y + 19, cv, 10.5, mono=True))
        b.append(text(500, y + 19, calc, 9, anchor="start", fill=MUTED))
        y += 32
    b.append(text(W/2, y + 10, "每一行都能手算验证——教学数据的可验证性设计（D118 同款 A/B）", 10, MUTED))

    # 底：本周里程碑
    b.append(text(W/2, 490, "第 18 周里程碑：从 CLI 骨架到完整编译器", 14, bold=True))
    days = [
        ("D120", "CLI 骨架", "25 项合同", GREEN),
        ("D121", "S1 图优化", "11→5＋五开关", GREEN),
        ("D122", "S2~S5", "失败诊断保留", BLUE),
        ("D123", "可观测", "四级＋记录", BLUE),
        ("D124", "端到端！", "12/12 bitwise", RED),
        ("D125", "对照实验", "（明天）", PURPLE),
    ]
    dw, dh, dgap = 155, 80, 16
    dx0 = (W - (dw*6 + dgap*5)) / 2
    for i, (d, name, note, color) in enumerate(days):
        x = dx0 + i * (dw + dgap)
        b.append(hand_rect(x, 512, dw, dh, fill=color, opacity=0.45))
        b.append(text(x + dw/2, 534, d, 12, bold=True))
        b.append(text(x + dw/2, 552, name, 10.5))
        b.append(text(x + dw/2, 570, note, 9, MUTED))
        if i < 5:
            b.append(arrow(x + dw + 1, 552, x + dw + dgap - 1, 552, sw=1.3))

    b.append(hand_rect(80, 610, W - 160, 50, fill="#F5E9C8", opacity=0.8))
    b.append(text(W/2, 632, "「首个完整项目可运行版本」的准确含义：不是每层都用最重的实现——", 11.5, bold=True))
    b.append(text(W/2, 652, "而是每层都有真实实现、层层咬合、端到端可验证：图优化真融合、循环真展开、Lowering 真 pass、执行真机器码、验证真 bitwise", 10.5))
    save("01-overview.svg", "".join(b), h=680)


# ── 图 2：S2 点循环解剖 + 融合语义 ──
def fig2():
    b = []
    b.append(text(W/2, 34, "S2 点循环解剖：bias 融 k=0、relu 的 cmpf+select、k 序累加链", 16, bold=True))

    # 左：生成的 IR（关键段）
    b.append(hand_rect(50, 60, 540, 380, fill=BG, opacity=0.95, sw=1.8))
    b.append(text(320, 82, "gen_loop_ir_full 的输出（关键段）", 11.5, bold=True))
    code = [
        ("scf.for %i = %c0 to %cM step %c1 {", GREEN),
        ("  scf.for %j = %c0 to %cN step %c1 {", GREEN),
        ("    %bj = memref.load %bias[%j]        // ① bias 先装填", ORANGE),
        ("    %acc = scf.for %k = %c0 to %cK step %c1", BLUE),
        ("                iter_args(%acc = %bj) -> (f32) {   // ② 初值=bias", ORANGE),
        ("      %aij = memref.load %a[%i, %k]", BLUE),
        ("      %bkj = memref.load %b[%k, %j]", BLUE),
        ("      %p = arith.mulf %aij, %bkj : f32", BLUE),
        ("      %s = arith.addf %acc, %p : f32    // ③ k 序累加", BLUE),
        ("      scf.yield %s : f32", BLUE),
        ("    }", BLUE),
        ("    %cond = arith.cmpf ogt, %acc, %pos  // ④ relu 条件", RED),
        ("    %r = arith.select %cond, %acc, %pos // ⑤ relu 选择", RED),
        ("    memref.store %r, %c[%i, %j]", BLUE),
        ("  }", GREEN),
        ("}", GREEN),
    ]
    y = 100
    for line, color in code:
        b.append(text(70, y, line, 9.5, mono=True, anchor="start", fill=color))
        y += 21

    # 右：三个语义点
    b.append(hand_rect(620, 60, 410, 380, fill=PURPLE, opacity=0.3))
    b.append(text(825, 82, "三个语义点（对应左侧 ①②③④⑤）", 12.5, bold=True))
    points = [
        ("①② bias 融 k=0 圈",
         "iter_args 初值 = %bj（bias[j]）——k=0 圈从 bias\n开始累加，等价于「先加 bias 再乘加」\n出处：D85~D90 任务单的融合语义\nD121 图优化融的 fused 算子在这里兑现", ORANGE),
        ("③ k 序累加链",
         "acc = ((bias + a0·b0) + a1·b1) + ...\n每次 addf 都是一次 IEEE 舍入——顺序即语义\ngolden 必须按同序计算（k 序参考）\nD78~D80 的浮点课：换序≠换值", BLUE),
        ("④⑤ relu 的真身",
         "cmpf ogt（有序大于）+ select\n−0.0 走 else 分支变 +0.0（符号规整）\nD116 的 A4 模式在真实管道的重现\n「融合算子映射到循环」的具体答案", RED),
    ]
    y = 106
    for title, body, color in points:
        b.append(hand_rect(640, y, 370, 100, fill=color, opacity=0.25))
        b.append(text(825, y + 20, title, 11, bold=True))
        for j, line in enumerate(body.split("\n")):
            b.append(text(825, y + 38 + j*16, line, 8.8))
        y += 110

    # 底部
    b.append(hand_rect(50, 460, 980, 56, fill="#F5E9C8", opacity=0.8))
    b.append(text(W/2, 482, "「融合算子如何映射到实际循环」——计划第 124 天条目的原话，今天有了具体答案：", 11.5, bold=True))
    b.append(text(W/2, 502, "fused_matmul_bias_relu = 三重 scf.for＋bias 进 iter_args 初值＋k 序乘加＋cmpf/select 收尾——融合没有魔法，只是把三个节点的语义写进一个循环体", 10.5))
    save("02-mechanism.svg", "".join(b), h=540)


# ── 图 3：golden 口径与 -O0 的连锁反应 ──
def fig3():
    b = []
    b.append(text(W/2, 34, "两个深坑：golden 的浮点口径、-O0 的连锁反应", 16, bold=True))

    # 上左：golden 口径
    b.append(hand_rect(50, 60, 480, 250, fill=BLUE, opacity=0.3))
    b.append(text(290, 84, "坑 1：golden 的浮点口径", 13, bold=True))
    b.append(text(290, 106, "「与 NumPy 结果比较」——计划原话，但 numpy 的 @", 10.5))
    b.append(text(290, 124, "用分块/向量序，kernel 用 k 序——顺序不同、舍入不同。", 10.5))
    b.append(text(290, 148, "解决：golden 按 k 序手写（bias 先进 acc，逐次", 10.5))
    b.append(text(290, 166, "addf）——与 kernel 逐位同序，bitwise 判据才成立。", 10.5))
    b.append(hand_rect(70, 184, 440, 100, fill=BG, opacity=0.9))
    b.append(text(90, 206, "acc = bias[j]                    # k=0 初值", 9.5, mono=True, anchor="start"))
    b.append(text(90, 224, "for k in range(K):", 9.5, mono=True, anchor="start"))
    b.append(text(90, 242, "    acc = float32(acc + a[i,k]*b[k,j])", 9.5, mono=True, anchor="start"))
    b.append(text(90, 260, "c[i,j] = max(acc, 0)", 9.5, mono=True, anchor="start"))
    b.append(text(290, 298, "D78~D80 的课在 S6 落地：判据的口径就是语义", 10, fill="#4a7c59", bold=True))

    # 上右：-O0 连锁
    b.append(hand_rect(550, 60, 480, 250, fill=RED, opacity=0.3))
    b.append(text(790, 84, "坑 2：-O0 的连锁反应（TP6 实测）", 13, bold=True))
    b.append(text(790, 108, "直觉：-O0 只是慢一点，结果应该一样？", 10.5))
    b.append(text(790, 130, "实测：-O0 关掉 QDQ 清理 → quantize/dequantize", 10.5))
    b.append(text(790, 148, "留在图里 → S2 支持集不含 quantize → E202！", 10.5))
    b.append(hand_rect(570, 166, 440, 76, fill=BG, opacity=0.9))
    chain = [
        "-O0 → 闸1 关 → QDQ 残留 → S2 拒收",
        "（E202：不支持的算子 quantize）",
    ]
    for j, line in enumerate(chain):
        b.append(text(790, 190 + j*22, line, 10.5, mono=True))
    b.append(text(790, 264, "启示：有的优化开关不只是性能选项——", 10.5, fill=RED, bold=True))
    b.append(text(790, 284, "它是后续阶段能否工作的前提（清理创造机会，D121）", 10.5, fill=RED))

    # 下：验证的三层
    b.append(text(W/2, 344, "S6 验证的三层口径（D116 三层法的端到端版）", 14, bold=True))
    layers = [
        ("契约层", "ciface 四指针签名\n19 参数 ABI 拆包\n（D115 合同第三次独立验证）", GREEN),
        ("数值层", "12/12 点 bitwise 一致\nk 序 golden 口径\n（浮点语义逐位对齐）", ORANGE),
        ("执行层", "AOT 真实机器码\nclang -O1 编译执行\n（D118 路线 1 的自动化）", RED),
    ]
    lw, lh, lgap = 300, 130, 22
    lx0 = (W - (lw*3 + lgap*2)) / 2
    for i, (name, body, color) in enumerate(layers):
        x = lx0 + i * (lw + lgap)
        b.append(hand_rect(x, 364, lw, lh, fill=color, opacity=0.4))
        b.append(text(x + lw/2, 388, name, 12.5, bold=True))
        for j, line in enumerate(body.split("\n")):
            b.append(text(x + lw/2, 410 + j*17, line, 9.5))

    # 底部
    b.append(hand_rect(80, 520, W - 160, 66, fill="#F5E9C8", opacity=0.8))
    b.append(text(W/2, 544, "「打通目标项目整条链路，并与 NumPy 或 PyTorch 结果比较」——计划的验收标准今天达成，", 11.5, bold=True))
    b.append(text(W/2, 566, "但「与 NumPy 比较」加了口径限定：k 序参考的 numpy（不是裸 @）——浮点世界里「比较」本身就需要设计", 10.5))
    b.append(text(W/2, 582, "明天 D125 优化开关对照实验：四组开关（无优化/仅图优化/图+Tiling/全开）× 性能数据 × 阶段收益表——今天的 12/12 是正确性基线，明天开始谈性能", 10.5, MUTED))
    save("03-example.svg", "".join(b), h=610)


if __name__ == "__main__":
    fig1()
    fig2()
    fig3()
