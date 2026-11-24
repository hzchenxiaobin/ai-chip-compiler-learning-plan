#!/usr/bin/env python3
"""生成第 117 天的 3 张手绘 sketch 风 SVG 技术图（Excalidraw-like）。

风格与 D110~D116 一致：白板涂鸦感——带抖动的贝塞尔手绘路径、马克笔笔触、
3～4 种柔和强调色（蓝/橙/绿/红）＋米白背景、简单几何形状、手写感字体。
所有数字来自 outputs/ 的真实冻结运行（report.txt，2026-11-13，
aarch64 Linux，Ubuntu LLVM 18.1.8，Python 3.11.4）。
固定随机种子 117，图可复现。
"""

from __future__ import annotations

import math
import os
import random
import xml.sax.saxutils as su

random.seed(117)

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


def frame(w, h, title):
    body = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
            f'font-family="{FONT}">',
            hand_rect(4, 4, w - 8, h - 8, BG, 1.0, BORDER, 2),
            text(w / 2, 34, title, 17.5, INK, "middle", True)]
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
        b.append(text(ax, y + 36 + i * 16, ln, lsize, INK, aanchor))
    for i, ln in enumerate(mono_lines or []):
        b.append(text(ax, y + 36 + len(lines) * 16 + i * 14.5, ln, 9.3,
                      MUTED, aanchor, mono=True))


# ======================= 图 1：全局定位＋管道全景 =======================

def fig1():
    W, H = 1020, 760
    b = frame(W, H, "第 117 天定位：完整 Lowering 管道＋导出——C1 落地、胶水清零，真 mlir-translate 接管手工翻译线")
    b.append(hand_line(300, 44, 720, 45, ORANGE, 3))

    # 上排：编译链路
    b.append(text(48, 68, "编译链路：今天走到哪一站？", 12.5, INK, "start", True))
    chain = [
        (60, 150, "图 IR", "mini 方言", BG, "已完成"),
        (165, 275, "循环＋内存 IR", "scf·memref", BG, "D85~D105"),
        (290, 450, "函数与类型", "F1/R1/A1", BG, "D115 ✓"),
        (465, 625, "算子与内存", "M1~M3/A2~A4", BG, "D116 ✓"),
        (640, 780, "今天：完整管道＋导出", "C1＋reconcile→.ll", GREEN, "D117 ★"),
        (795, 965, "执行", "JIT / AOT", BG, "D118"),
    ]
    y0 = 86
    for x1, x2, name, sub, fill, sched in chain:
        b.append(hand_rect(x1, y0, x2 - x1, 52, fill, 0.55, INK, 1.6))
        b.append(text((x1 + x2) / 2, y0 + 22, name, 11.5, INK, "middle", True))
        b.append(text((x1 + x2) / 2, y0 + 40, sub, 9.5, MUTED, "middle"))
        b.append(text((x1 + x2) / 2, y0 + 62, sched, 9.5,
                      GREEN if fill == GREEN else MUTED, "middle"))
    for i in range(5):
        x1, x2 = chain[i][1], chain[i + 1][0]
        b.append(arrow(x1 + 3, y0 + 26, x2 - 3, y0 + 26, INK, 1.8))
    b.append(text(510, y0 + 82, "D113~D116 的翻译线是教学仿真——今天起，每个环节都是真 MLIR 工具（/usr/lib/llvm-18/bin）",
                  10.5, MUTED))

    # 中排：管道流水线（真实命令）
    b.append(text(48, 210, "完整 Lowering 管道（lower.sh 的 5 个阶段，命令原样）", 12.5, INK, "start", True))
    b.append(hand_rect(55, 222, 150, 58, ORANGE, 0.45, INK, 1.6))
    b.append(text(130, 244, "gemm.mlir", 12, INK, "middle", True))
    b.append(text(130, 262, "朴素前端 21 op", 9.5, MUTED, "middle"))
    b.append(text(130, 275, "strided 签名＋emit_c_interface", 8.3, MUTED, "middle"))

    stages = [
        (225, 360, "阶段 0 优化", "canonicalize＋cse", "21 op → 18 op", ORANGE),
        (370, 515, "阶段 1 C1 落地", "convert-scf-to-cf", "for 拆四块＋块参数", BLUE),
        (525, 670, "阶段 2 五 pass 转换", "memref·func·cf·arith·index", "＋reconcile 胶水 6→0", BLUE),
        (680, 830, "阶段 3 导出", "mlir-translate", "LLVM 方言→.ll", GREEN),
        (835, 965, "阶段 4 验证", "llvm-as·opt·llc＋llvmlite", "双线全过", GREEN),
    ]
    for x1, x2, name, cmd, num, fill in stages:
        b.append(hand_rect(x1, 222, x2 - x1, 58, fill, 0.5, INK, 1.6))
        b.append(text((x1 + x2) / 2, 244, name, 11, INK, "middle", True))
        b.append(text((x1 + x2) / 2, 262, cmd, 9.3, MUTED, "middle", mono=True))
        b.append(text((x1 + x2) / 2, 275, num, 9.5, INK, "middle"))
    for x in (205, 350, 505, 660, 815):
        b.append(arrow(x, 251, x + 20, 251, INK, 2))

    # 中下：pass 与模式 ID 的接管关系
    b.append(text(48, 316, "每条 pass 接管 D114 清单的哪一行？（右列＝模式 ID）", 12.5, INK, "start", True))
    rows = [
        ("--convert-scf-to-cf", "scf.for×3＋scf.yield×1", "C1（D116 欠账 4 条，今天清零）", RED),
        ("--finalize-memref-to-llvm", "load×2/store/alloc", "M1/M2/M3（D116 已仿真，今天真身）", BLUE),
        ("--convert-func-to-llvm", "func.func 签名", "F1（memref 参数按 7 字段拆包）", BLUE),
        ("--convert-arith-to-llvm", "addi/muli/addf/mulf/cmpi", "A2/A3（词汇映射）", BLUE),
        ("--convert-index-to-llvm", "index→i64", "清 i64↔index 胶水的前半", BLUE),
        ("--reconcile-unrealized-casts", "unrealized_conversion_cast", "胶水清零：6→0（D115 的 5 条同族）", RED),
    ]
    for i, (cmd, ops, note, col) in enumerate(rows):
        x = 55 + (i % 3) * 315
        y = 328 + (i // 3) * 56
        b.append(hand_rect(x, y, 300, 48, col, 0.35, INK, 1.4))
        b.append(text(x + 150, y + 18, cmd, 9.3, INK, "middle", mono=True))
        b.append(text(x + 150, y + 33, ops + "  ←  " + note, 8.6, MUTED, "middle"))

    # 下排：三组文件＋账本
    b.append(text(48, 468, "今日三组产出（全部真实冻结在 outputs/）", 12.5, INK, "start", True))
    card(b, 55, 480, 290, 96, "组 1：优化前后 MLIR", [],
         ORANGE, mono_lines=[
            "gemm.mlir（21 op，含朴素冗余）",
            "gemm-0-optimized.mlir（18 op）",
            "subi/muli/addi 全折叠·常量去重"])
    card(b, 360, 480, 290, 96, "组 2：LLVM Dialect", [],
         BLUE, mono_lines=[
            "gemm-2-llvm-dialect.mlir",
            "残账 0·胶水 0·纯 llvm.*",
            "（noreconcile 版留 6 条胶水证据）"])
    card(b, 665, 480, 290, 96, "组 3：LLVM IR", [],
         GREEN, mono_lines=[
            "gemm-3.ll：62 条 SSA·4 个 phi",
            "@gemm＋_mlir_ciface_gemm＋malloc",
            "llvm-as/opt/llc＋llvmlite 双线验证 ✓"])

    b.append(hand_rect(55, 606, 900, 108, GREEN, 0.28, INK, 1.8))
    b.append(text(505, 630, "D116 账本今天清零（真机实测）", 13, INK, "middle", True))
    b.append(text(505, 652, "14/18＋残账 C1×4  →  18/18 清零：scf.for×3＋scf.yield×1 全部由 --convert-scf-to-cf 转掉", 10.8, INK))
    b.append(text(505, 670, "胶水 6→0（i64→index ×3＋struct→memref ×3）·tight 版过同管道残账 0", 10.8, INK))
    b.append(text(505, 690, "phi 4 条——R3（块参数→phi）在真 .ll 里兑现；R2（常量内联）同过", 10.8, MUTED))

    save("01-overview.svg", b)


# ======================= 图 2：核心机制（C1 与 ABI） =======================

def fig2():
    W, H = 1020, 780
    b = frame(W, H, "机制：C1 落地——scf.for 拆四块变 phi；签名 ABI——memref 按 7 字段拆包；胶水 6→0")
    b.append(hand_line(280, 44, 740, 45, ORANGE, 3))

    # 左侧：C1 落地
    b.append(text(48, 74, "① 一层 scf.for → 四个块（gemm-1-scf-to-cf.mlir 原文）", 12.5, INK, "start", True))
    b.append(hand_rect(55, 86, 240, 64, RED, 0.35, INK, 1.6))
    b.append(text(175, 108, "scf.for %k = %lb to %c6", 10.3, INK, "middle", mono=True))
    b.append(text(175, 124, "iter_args(%acc = %cst) -> f32", 10.3, INK, "middle", mono=True))
    b.append(text(175, 140, "（k 循环：归纳变量＋携带值）", 9.3, MUTED, "middle"))

    blocks = [
        (70, 188, "init（进入）", "cf.br ^bb5(%c0, %cst", "  : index, f32)", "把初值打包跳进 header"),
        (70, 262, "header ^bb5(%4: index, %5: f32)", "// 2 preds: ^bb4, ^bb6", "cmpi slt %4, %c6", "cond_br → body / 出口"),
        (70, 336, "body ^bb6", "load×2 · mulf · addf", "addi %4, %c1", "干活＋自增"),
        (70, 410, "latch（回跳）", "cf.br ^bb5(%11, %10", "  : index, f32)", "新值送回 header"),
    ]
    for x, y, name, l1, l2, note in blocks:
        b.append(hand_rect(x, y, 210, 62, BLUE, 0.4, INK, 1.5))
        b.append(text(x + 105, y + 17, name, 9.8, INK, "middle", True))
        b.append(text(x + 105, y + 32, l1, 8.8, MUTED, "middle", mono=True))
        b.append(text(x + 105, y + 44, l2, 8.8, MUTED, "middle", mono=True))
        b.append(text(x + 105, y + 57, note, 8.3, MUTED, "middle"))
    b.append(arrow(175, 150, 175, 186, INK, 1.8))
    b.append(arrow(175, 248, 175, 260, INK, 1.8, label="带初值"))
    b.append(arrow(120, 324, 120, 335, INK, 1.8))
    b.append(arrow(240, 335, 240, 324, INK, 1.8, dash="4,4"))
    b.append(arrow(175, 398, 175, 409, INK, 1.8))
    b.append(hand_line(280, 441, 280, 300, RED, 2, dash="6,5"))
    b.append(arrow(280, 300, 282, 292, RED, 2))
    b.append(text(287, 380, "回跳边＝块参数有两个前驱", 9, RED, "start"))
    b.append(text(287, 394, "＝.ll 里的 phi", 9, RED, "start"))

    b.append(hand_rect(55, 488, 500, 60, GREEN, 0.32, INK, 1.6))
    b.append(text(305, 508, "导出后（gemm-3.ll 第 46~47 行，原文）：", 10.5, INK, "middle", True))
    b.append(text(305, 526, "%46 = phi i64 [ %60, %49 ], [ 0, %44 ]", 10, INK, "middle", mono=True))
    b.append(text(305, 540, "%47 = phi float [ %59, %49 ], [ 0.000000e+00, %44 ]  ← %acc 的真身", 10, INK, "middle", mono=True))
    b.append(text(305, 558, "R3（块参数→phi）在真工具上兑现——D113 的三条导出规则全部命中", 9.3, MUTED, "middle"))

    # 右侧：签名 ABI 拆包
    b.append(text(580, 74, "② 一个 memref 参数 → 7 个标量（真 ABI）", 12.5, INK, "start", True))
    b.append(hand_rect(588, 86, 380, 56, ORANGE, 0.4, INK, 1.6))
    b.append(text(778, 106, "%a : memref<4x6xf32, strided<[6, 1]>>", 10.3, INK, "middle", mono=True))
    b.append(text(778, 128, "（D115 的 56B 描述符契约，原样保留在签名里）", 9, MUTED, "middle"))
    b.append(arrow(778, 142, 778, 156, INK, 2, label="拆包"))

    fields = [
        "ptr  allocated   （分配起点）",
        "ptr  aligned     （对齐起点）",
        "i64  offset      （元素偏移）",
        "i64  size0=4, size1=6",
        "i64  stride0=6, stride1=1",
    ]
    b.append(hand_rect(588, 158, 380, 128, BLUE, 0.35, INK, 1.6))
    for i, f in enumerate(fields):
        b.append(text(604, 180 + i * 19, f, 9.8, INK, "start", mono=True))
    b.append(text(778, 280, "llvm.func 的 14 个裸参数＝2 个 memref × 7 字段", 9.3, MUTED, "middle"))
    b.append(arrow(778, 290, 778, 304, INK, 2, label="insertvalue ×7"))
    b.append(hand_rect(588, 306, 380, 44, GREEN, 0.35, INK, 1.6))
    b.append(text(778, 324, "函数体开头重新打包成", 9.8, INK, "middle"))
    b.append(text(778, 340, "!llvm.struct<(ptr, ptr, i64, array<2xi64>, array<2xi64>)>", 9.6, INK, "middle", mono=True))

    b.append(hand_rect(588, 366, 380, 58, ORANGE, 0.3, INK, 1.5))
    b.append(text(778, 386, "attributes { llvm.emit_c_interface }", 9.8, INK, "middle", mono=True))
    b.append(text(778, 404, "→ mlir-translate 自动生成 C 包装：", 9.5, INK, "middle"))
    b.append(text(778, 418, "define void @_mlir_ciface_gemm(ptr, ptr, ptr)", 9.3, INK, "middle", mono=True))
    b.append(text(778, 436, "D116 手写包装的真工具版——D118 按 C 合同调它", 9, MUTED, "middle"))

    # 底部：胶水
    b.append(text(48, 588, "③ 胶水 6→0：reconcile-unrealized-casts 的账（管道中间态实测）", 12.5, INK, "start", True))
    b.append(hand_rect(55, 600, 290, 64, RED, 0.32, INK, 1.6))
    b.append(text(200, 622, "i64 → index  × 3", 10.5, INK, "middle", True))
    b.append(text(200, 640, "cf 块的归纳变量在等 index 收尾", 9.3, MUTED, "middle"))
    b.append(text(200, 654, "（D115 的 5 条 i64→index 同族）", 9, MUTED, "middle"))
    b.append(hand_rect(360, 600, 290, 64, RED, 0.32, INK, 1.6))
    b.append(text(505, 622, "struct → memref  × 3", 10.5, INK, "middle", True))
    b.append(text(505, 640, "签名重建的描述符值在等消费方", 9.3, MUTED, "middle"))
    b.append(text(505, 654, "（D115 的 3 条 desc↔memref 同族）", 9, MUTED, "middle"))
    b.append(arrow(655, 632, 700, 632, INK, 2, label="reconcile"))
    b.append(hand_rect(705, 600, 250, 64, GREEN, 0.4, INK, 1.6))
    b.append(text(830, 622, "0 条", 13, INK, "middle", True))
    b.append(text(830, 640, "纯 LLVM 方言＝可导出形态", 9.3, MUTED, "middle"))
    b.append(text(830, 654, "不清零则 mlir-translate 直接报错", 9, MUTED, "middle"))
    b.append(text(505, 690, "忘记 reconcile 的真实报错：LLVM Translation failed for operation: builtin.unrealized_conversion_cast（outputs/errors-3-glue.txt）",
                  9.6, RED, "middle"))
    b.append(text(505, 712, "对应到 D115 的预言：胶水留到导出那天，mlir-translate 会当场报错——今天原样发生", 9.3, MUTED, "middle"))

    save("02-mechanism.svg", b)


# ======================= 图 3：实验与账本对照 =======================

def fig3():
    W, H = 1020, 780
    b = frame(W, H, "真实运行结果：优化前后、两条路收敛、O2 展开、账本清零与四个错误的层")
    b.append(hand_line(300, 44, 720, 45, ORANGE, 3))

    # 面板①：优化前后
    b.append(text(48, 74, "① 优化前后 MLIR（组 1）——canonicalize＋cse 真实折叠", 12.5, INK, "start", True))
    b.append(hand_rect(55, 86, 200, 92, ORANGE, 0.4, INK, 1.6))
    b.append(text(155, 108, "gemm.mlir（前）", 11, INK, "middle", True))
    b.append(text(155, 128, "21 op", 15, INK, "middle", True))
    b.append(text(155, 148, "下界 6−6·上界 2×2", 9, MUTED, "middle"))
    b.append(text(155, 162, "3+(6−6)·重复常量 %c1a/%c1b", 8.6, MUTED, "middle"))
    b.append(arrow(260, 132, 305, 132, INK, 2, label="折叠"))
    b.append(hand_rect(310, 86, 200, 92, GREEN, 0.4, INK, 1.6))
    b.append(text(410, 108, "gemm-0-optimized（后）", 11, INK, "middle", True))
    b.append(text(410, 128, "18 op", 15, INK, "middle", True))
    b.append(text(410, 148, "subi/muli/addi 全消失", 9, MUTED, "middle"))
    b.append(text(410, 162, "常量只剩 0/4/3/6/1/0.0", 8.6, MUTED, "middle"))
    b.append(hand_rect(525, 86, 430, 92, BLUE, 0.25, INK, 1.5))
    b.append(text(740, 106, "为什么值得单独存两份文件？", 10.8, INK, "middle", True))
    b.append(text(740, 126, "优化在 MLIR 层真实发生（21→18 op）；对照 A 证明：跳过它直接转换，", 9.6, INK, "middle"))
    b.append(text(740, 144, "两条路的 .ll 逐字节一致——转换 pass（arith/index）自带常量折叠，", 9.6, INK, "middle"))
    b.append(text(740, 162, "但 MLIR 优化层仍更早暴露形态（消冗余不是只在最后一层兜底）", 9.6, INK, "middle"))

    # 面板②：两条路收敛＋O2
    b.append(text(48, 214, "② 两条路收敛·③ opt -O2 之后（gemm-3.ll → gemm-O2.ll）", 12.5, INK, "start", True))
    b.append(hand_rect(55, 226, 430, 108, GREEN, 0.3, INK, 1.6))
    b.append(text(270, 248, "导出物体检阅（62 条 SSA 指令）", 11, INK, "middle", True))
    b.append(text(270, 270, "define 2 个：@gemm（14 参数）＋_mlir_ciface_gemm（3 指针）", 9.6, INK, "middle"))
    b.append(text(270, 288, "declare @malloc＋call malloc（M3 真身）＋insertvalue×7（描述符）", 9.6, INK, "middle"))
    b.append(text(270, 306, "phi×4：3 个循环变量＋1 个 f32 累加器", 9.6, INK, "middle"))
    b.append(text(270, 324, "先优化/不优化两条路：.ll diff 为空（逐字节一致）", 9.6, GREEN, "middle", True))
    b.append(hand_rect(525, 226, 430, 108, ORANGE, 0.3, INK, 1.6))
    b.append(text(740, 248, "opt -O2（LLVM 优化器的世界）", 11, INK, "middle", True))
    b.append(text(740, 270, "SSA 62 → 67 条；fmul 1 → 18·fadd 1 → 18", 9.8, INK, "middle"))
    b.append(text(740, 288, "小循环被展开：指令变多、循环开销与分支变少", 9.4, MUTED, "middle"))
    b.append(text(740, 306, "malloc 标注 noalias＋dereferenceable_or_null(48)", 9.4, MUTED, "middle"))
    b.append(text(740, 324, "对比：MLIR 折叠常量·LLVM 展开循环——两层优化各管一段", 9.4, MUTED, "middle"))

    # 面板④：账本
    b.append(text(48, 362, "④ 账本清零（D116 排期 → D117 兑现）", 12.5, INK, "start", True))
    b.append(hand_rect(55, 374, 900, 92, GREEN, 0.3, INK, 1.8))
    b.append(text(505, 396, "14/18＋残账 C1×4＋胶水 5 条（D116 结束时）", 11, INK, "middle", True))
    b.append(arrow(505, 404, 505, 418, INK, 2))
    b.append(text(505, 436, "18/18：C1×4（scf.for×3＋scf.yield×1）由 --convert-scf-to-cf 转掉；i64↔index 胶水由 index 转换＋reconcile 清零", 10.2, INK))
    b.append(text(505, 456, "tight 版（18 op）过同一条管道：纯 LLVM 方言 74 op·残账 0·胶水 0——两个源在同一条真管道上都清零", 10.2, INK))

    # 面板⑤：四个错误
    b.append(text(48, 496, "⑤ 四个真实错误的层（outputs/errors-*.txt 存档）", 12.5, INK, "start", True))
    errs = [
        (55, "strided alloc·多 pass", "finalize-memref 拒绝非 identity 布局的 alloc",
         "failed to legalize cast", "转换层当场抓"),
        (283, "strided alloc·one-shot", "convert-to-llvm 静默漏掉 memref.alloc",
         "Dialect 'memref' not found", "translate 层才抓"),
        (511, "忘 reconcile", "胶水 6 条留在纯度门口",
         "LLVM Translation failed", "导出层抓"),
        (739, "pass 顺序错", "func 先于 scf/memref 跑",
         "failed to legalize", "中途翻车"),
    ]
    for x, name, cause, msg, where in errs:
        b.append(hand_rect(x, 508, 216, 96, RED, 0.3, INK, 1.5))
        b.append(text(x + 108, 528, name, 10.3, INK, "middle", True))
        b.append(text(x + 108, 548, cause, 8.8, MUTED, "middle"))
        b.append(text(x + 108, 566, "“" + msg + "”", 8.4, RED, "middle", mono=True))
        b.append(text(x + 108, 586, where, 8.8, INK, "middle"))
    b.append(text(505, 626, "共同教训：多 pass 手排顺序＝让每个转换 pass 自带类型转换器——胶水在 pass 之间堆积，顺序错一处就翻车；", 9.8, INK))
    b.append(text(505, 644, "一次成型（--convert-to-llvm 或 Toy 教程的单一 full conversion）能躲开大部分顺序问题，但 alloc 的 identity 检查躲不开", 9.8, INK))

    b.append(text(505, 684, "三组文件入口：gemm.mlir＋gemm-0-optimized.mlir（组1）·gemm-2-llvm-dialect.mlir（组2）·gemm-3.ll（组3）", 10, INK, "middle", True))
    b.append(text(505, 704, "双线验证：llvm-as＋opt -passes=verify＋llc（18.1.8）＋llvmlite parse/verify（22.1）全部通过", 9.6, MUTED, "middle"))
    b.append(text(505, 724, "复现：cd code && ./run_all.sh —— 22/22 PASS（2026-11-13 冻结）", 9.6, GREEN, "middle", True))

    save("03-example.svg", b)


if __name__ == "__main__":
    print("生成第 117 天的 3 张图（随机种子 117，数字来自 outputs/ 冻结运行）：")
    fig1()
    fig2()
    fig3()
