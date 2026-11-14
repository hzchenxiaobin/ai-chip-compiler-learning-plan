#!/usr/bin/env python3
"""生成第 123 天（IR Dump 与可观测性）的 3 张手绘 sketch 风 SVG 图。

数字来自 outputs/report.txt 与 timeline.txt 真实运行（2026-11-14，
macOS arm64，LLVM 23.1.5）。固定随机种子 123。
"""
from __future__ import annotations

import math
import os
import random
import xml.sax.saxutils as su

random.seed(123)

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


# ── 图 1：四级粒度全景 ──
def fig1():
    b = []
    b.append(text(W/2, 34, "可观测性四级粒度：从「零文件」到「每条 pass 的改写记录」", 16, bold=True))

    # 四级阶梯
    levels = [
        ("off", "零文件", "0 个 stage 文件\n只留 manifest\n（CI 常规跑）", RED),
        ("stages", "阶段级", "2 个文件\nstage-5.ll/.s\n（默认：够回答\n「结果对不对」）", ORANGE),
        ("passes", "pass 级", "11 个文件\n每条 pass 落盘\n（D122 行为）\n+8 条改写记录", BLUE),
        ("full", "全量", "11 文件+记录\n+diff 统计\n+时间线\n（「为什么长这样」）", GREEN),
    ]
    lw, lh, lgap = 240, 170, 20
    lx0 = (W - (lw*4 + lgap*3)) / 2
    for i, (name, tag, desc, color) in enumerate(levels):
        x = lx0 + i * (lw + lgap)
        y = 60 + (3 - i) * 24   # 阶梯上升
        b.append(hand_rect(x, y, lw, lh, fill=color, opacity=0.42))
        b.append(text(x + lw/2, y + 26, f"--dump-ir={name}", 12.5, bold=True, mono=True))
        b.append(text(x + lw/2, y + 46, tag, 11, fill=MUTED))
        for j, line in enumerate(desc.split("\n")):
            b.append(text(x + lw/2, y + 68 + j*17, line, 9.5))
        if i < 3:
            b.append(arrow(x + lw + 2, y + lh/2, x + lw + lgap - 2, y + lh/2 - 10, sw=1.6))

    # 底：三级调试问题的对应
    b.append(text(W/2, 310, "每个观测点对应一个真实调试问题（设计立场）", 14, bold=True))
    qa = [
        ("「结果对不对？」", "stages 级就够\nstage-5.ll 拿去 diff/执行\nD118 的四条路线直接可用", GREEN),
        ("「哪一步出的问题？」", "需要 passes 级\n逐条 pass 的 IR 链\nD136 Pass 二分定位的地基", BLUE),
        ("「为什么长这样？」", "需要 full 级\n改写记录：每条 pass\n改了什么（op 增删）", ORANGE),
        ("「哪一步最贵？」", "时间线（全级别）\n11 个计时点\nD125 对照实验要报各阶段开销", RED),
    ]
    qw, qh, qgap = 240, 130, 20
    qx0 = (W - (qw*4 + qgap*3)) / 2
    for i, (q, a, color) in enumerate(qa):
        x = qx0 + i * (qw + qgap)
        b.append(hand_rect(x, 330, qw, qh, fill=color, opacity=0.4))
        b.append(text(x + qw/2, 354, q, 11.5, bold=True))
        for j, line in enumerate(a.split("\n")):
            b.append(text(x + qw/2, 376 + j*16, line, 9.5))

    # 底部：文件数与记录数实测
    b.append(hand_rect(120, 486, 840, 84, fill="#F5E9C8", opacity=0.8))
    b.append(text(W/2, 510, "实测（level-matrix.json）：off=0 文件｜stages=2 文件｜passes=11 文件＋8 条改写｜full 同＋时间线", 11.5, bold=True))
    b.append(text(W/2, 532, "文件数不是越多越好——每个文件都要有人读；粒度选择的本质是「为最常问的问题备好答案」", 10.5, MUTED))
    b.append(text(W/2, 554, "时间线实测：S2 生成 3.7ms｜八条 pass 各 ~40ms（进程启动为主）｜translate 42ms｜llc 30ms｜总 ≈394ms", 10.5, MUTED))
    save("01-overview.svg", "".join(b), h=600)


# ── 图 2：改写记录机制 ──
def fig2():
    b = []
    b.append(text(W/2, 34, "改写记录：每条 pass 前后 IR 的 diff，压缩成一句话", 16, bold=True))

    # 机制流程
    b.append(hand_rect(60, 60, 960, 130, fill=BLUE, opacity=0.3))
    b.append(text(W/2, 84, "记录机制（observability.py 的 rewrite()）", 13.5, bold=True))
    steps = [
        ("① pass 前 IR", "op_distribution()\n方言级 op 计数"),
        ("② pass 后 IR", "同一函数\n再数一遍"),
        ("③ 分布 diff", "diff_dist()\n[(op, ±Δ), ...]\n按绝对值降序"),
        ("④ 一句话", "\"canonicalize: 16→3 op\n（arith.constant -9,\nscf.for -4, ...）\""),
    ]
    for i, (t, d) in enumerate(steps):
        x = 100 + i * 240
        b.append(hand_rect(x, 100, 210, 76, fill=BG, opacity=0.9))
        b.append(text(x + 105, 120, t, 11, bold=True))
        for j, line in enumerate(d.split("\n")):
            b.append(text(x + 105, 136 + j*13, line, 9))
        if i < 3:
            b.append(arrow(x + 212, 138, x + 238, 138, sw=1.4))

    # 八条 pass 的真实记录
    b.append(text(W/2, 226, "八条 pass 的真实改写记录（TP2 实测，main.graph 全管道）", 14, bold=True))
    records = [
        ("canonicalize+csi", "16 → 3 op", "arith.constant -9, scf.for -4, func.return -1", RED),
        ("convert-scf-to-cf", "3 → 3 op", "结构无变化（教学版点循环是注释）", MUTED),
        ("finalize-memref-to-llvm", "3 → 21 op", "llvm.struct +9, insertvalue +7, ptr +6, constant +5", ORANGE),
        ("convert-func-to-llvm", "21 → 48 op", "struct +26, ptr +20, extractvalue +19, load +3", ORANGE),
        ("convert-cf-to-llvm", "48 → 48 op", "结构无变化（cf 已无残留）", MUTED),
        ("convert-arith-to-llvm", "48 → 48 op", "结构无变化（arith 已被前面吸收）", MUTED),
        ("convert-index-to-llvm", "48 → 48 op", "结构无变化（index 已被 memref 转换带走）", MUTED),
        ("reconcile-unrealized-casts", "48 → 47 op", "llvm.struct -1（胶水清零的最后一步）", GREEN),
    ]
    y = 248
    for name, ops, detail, color in records:
        b.append(hand_rect(80, y, 920, 40, fill=color if color != MUTED else BLUE, opacity=0.3))
        b.append(text(240, y + 25, name, 10.5, mono=True, anchor="start"))
        b.append(text(430, y + 25, ops, 10.5, bold=True))
        b.append(text(480, y + 25, detail, 9, anchor="start", fill=MUTED))
        y += 46

    # 底部解读
    b.append(hand_rect(80, y + 6, 920, 56, fill="#F5E9C8", opacity=0.8))
    b.append(text(W/2, y + 28, "读记录的三个收获：", 11.5, bold=True))
    b.append(text(W/2, y + 48, "① canonicalize 一条就砍 13 op（教学版循环壳的常量全折叠）；② memref→LLVM 膨胀 3→21（描述符展开——D115 的 5 字段×多次 insertvalue）；③ 五条 convert 里三条「无变化」——", 10))
    b.append(text(W/2, y + 64, "它们是按需转换（本图没有对应残留），「无变化」也是信息：说明前面的 pass 已把工作做完", 10, MUTED))
    save("02-mechanism.svg", "".join(b), h=y + 90)


# ── 图 3：时间线与「无变化也是信息」 ──
def fig3():
    b = []
    b.append(text(W/2, 34, "时间线：11 个计时点——以及「无变化也是信息」的解读", 16, bold=True))

    # 左：时间线条形
    b.append(hand_rect(50, 60, 500, 420, fill=GREEN, opacity=0.3))
    b.append(text(300, 84, "管道时间线（timeline.txt，实测一次）", 13, bold=True))
    bars = [
        ("S2 循环生成", 3.7, GREEN),
        ("pass canonicalize", 42.7, BLUE),
        ("pass scf→cf", 38.8, BLUE),
        ("pass finalize-memref", 43.9, BLUE),
        ("pass func→llvm", 44.4, ORANGE),
        ("pass cf→llvm", 41.2, BLUE),
        ("pass arith→llvm", 42.6, BLUE),
        ("pass index→llvm", 44.3, BLUE),
        ("pass reconcile", 40.1, BLUE),
        ("mlir-translate", 42.0, RED),
        ("llc", 30.2, RED),
    ]
    max_ms = 46
    y = 100
    for name, ms, color in bars:
        bw = (ms / max_ms) * 260
        b.append(hand_rect(200, y, bw, 18, fill=color, opacity=0.5))
        b.append(text(190, y + 14, name, 9.5, anchor="end"))
        b.append(text(200 + bw + 6, y + 14, f"{ms:.1f}ms", 9))
        y += 30
    b.append(text(300, y + 16, "总 ≈394ms｜量级说明：每条 pass 的 ~40ms 主要是", 10, MUTED))
    b.append(text(300, y + 32, "进程启动成本（八次 fork+exec）；in-process PassManager", 10, MUTED))
    b.append(text(300, y + 48, "（真实 MLIR）会把它压到 µs 级——教学取舍见 3.3", 10, MUTED))

    # 右上：无变化也是信息
    b.append(hand_rect(580, 60, 450, 200, fill=ORANGE, opacity=0.35))
    b.append(text(805, 84, "「结构无变化」也是信息", 13, bold=True))
    b.append(text(805, 108, "八条 pass 里三条记录「无变化」：", 10.5))
    b.append(text(805, 128, "cf→llvm / arith→llvm / index→llvm", 10.5, mono=True, fill=MUTED))
    lines = [
        "为什么无变化？不是 pass 没干活——",
        "是前面的 pass（canonicalize/memref/func）",
        "已把本图的全部残留清干净了。",
        "",
        "这就是「按需转换」的可见证据：",
        "转换 pass 只处理存在的残留；",
        "记录「无变化」＝宣告「这条防线",
        "本次没有敌人」。",
    ]
    for j, line in enumerate(lines):
        if line:
            b.append(text(805, 152 + j*17, line, 9.5))
    b.append(text(805, 152 + 8*17 + 4, "→ 对 D136 的价值：二分定位时", 9.5, fill="#4a7c59"))
    b.append(text(805, 152 + 9*17 + 4, "「无变化」的 pass 可以直接排除", 9.5, fill="#4a7c59"))

    # 右下：粒度×代价
    b.append(hand_rect(580, 280, 450, 200, fill=PURPLE, opacity=0.35))
    b.append(text(805, 304, "粒度 × 代价 × 用户矩阵", 13, bold=True))
    rows = [
        ("off", "0 文件", "CI 回归：只看 exit code"),
        ("stages", "2 文件", "开发日常：结果 diff"),
        ("passes", "11 文件", "调试 Lowering：IR 链"),
        ("full", "11+记录", "教学/复盘：改写叙事"),
    ]
    y = 326
    for name, cost, who in rows:
        b.append(hand_rect(600, y, 410, 32, fill=BG, opacity=0.85))
        b.append(text(620, y + 20, name, 10.5, bold=True, mono=True, anchor="start"))
        b.append(text(700, y + 20, cost, 10.5, anchor="start"))
        b.append(text(830, y + 20, who, 9.5, anchor="start", fill=MUTED))
        y += 38
    b.append(text(805, y + 14, "默认给 stages：最常问的问题（结果对不对）", 9.5, MUTED))
    b.append(text(805, y + 30, "配最低代价的答案——可观测性的经济学", 9.5, MUTED))

    # 底部
    b.append(hand_rect(50, 500, 980, 56, fill="#F5E9C8", opacity=0.8))
    b.append(text(W/2, 522, "与 D122 的关系：那天的 11 个 stage 文件回答「每步长什么样」；", 11.5, bold=True))
    b.append(text(W/2, 544, "今天补的是「每步改了什么（rewrite）＋每步多贵（timing）＋要不要留（levels）」——从有文件到可观测", 10.5))
    save("03-example.svg", "".join(b), h=580)


if __name__ == "__main__":
    fig1()
    fig2()
    fig3()
