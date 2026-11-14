#!/usr/bin/env python3
"""生成第 121 天（minic S1 图优化接入）的 3 张手绘 sketch 风 SVG 图。

数字来自 outputs/report.txt 真实运行（2026-11-14，macOS arm64，
Python 3.9.6 + numpy 1.26.4）。固定随机种子 121。
"""
from __future__ import annotations

import math
import os
import random
import xml.sax.saxutils as su

random.seed(121)

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


# ── 图 1：S1 五道闸管道＋开关 ──
def fig1():
    b = []
    b.append(text(W/2, 34, "minic S1：五道闸接进管道——每个 Pass 一个独立开关", 16, bold=True))

    # 输入图
    b.append(hand_rect(60, 62, 200, 88, fill=GREEN, opacity=0.5))
    b.append(text(160, 88, "main.graph", 12.5, bold=True))
    b.append(text(160, 108, "11 节点：reshape 链×2", 10))
    b.append(text(160, 126, "Q/DQ、transpose", 10))
    b.append(text(160, 142, "matmul+bias+relu", 10))

    # 五道闸
    gates = [
        ("闸0", "合法性 Verifier", "matmul 内维 / reshape\n元素数 / perm 合法", "不可关", RED),
        ("闸1", "QDQ 清理", "R04: DQ(Q(const))\n→量化格点常量", "--no-qdq-clean", BLUE),
        ("闸2", "布局简化", "transpose(const)\n→编译期折叠", "--no-layout-simp", BLUE),
        ("闸3", "Reshape 合并", "reshape(reshape)\n→reshape", "--no-reshape-merge", BLUE),
        ("闸4", "融合＋CostModel", "matmul+bias+relu\n→fused（收益门）", "--no-fuse", ORANGE),
    ]
    gw, gh, ggap = 150, 120, 18
    gx0 = 290
    for i, (gid, name, desc, sw, color) in enumerate(gates):
        x = gx0 + i * (gw + ggap)
        b.append(hand_rect(x, 50, gw, gh, fill=color, opacity=0.4))
        b.append(text(x + gw/2, 72, gid, 12.5, bold=True))
        b.append(text(x + gw/2, 90, name, 10.5))
        for j, line in enumerate(desc.split("\n")):
            b.append(text(x + gw/2, 108 + j*15, line, 9))
        b.append(text(x + gw/2, 156, sw, 8.5, fill=RED if sw == "不可关" else MUTED, mono=True))
        if i < 4:
            b.append(arrow(x + gw + 1, 110, x + gw + ggap - 1, 110, sw=1.4))
    b.append(arrow(262, 106, 288, 106, sw=1.8))

    # 不动点循环
    b.append(hand_rect(gx0 + gw + 8, 186, (gw + ggap) * 3 - 26, 40,
                       fill="#F5E9C8", opacity=0.8))
    b.append(text(gx0 + gw + 8 + (gw+ggap)*1.5, 202, "闸1→2→3 不动点循环（默认上限 8 轮）", 10.5, bold=True))
    b.append(text(gx0 + gw + 8 + (gw+ggap)*1.5, 218, "--fixpoint-max N｜今天实测 2 轮收敛", 9.5, MUTED))
    # 回环箭头
    b.append(arrow(gx0 + 2*(gw+ggap) + gw/2, 178, gx0 + gw + 4, 178,
                   stroke=MUTED, sw=1.2, dash="5 4"))

    # 输出
    b.append(hand_rect(60, 250, 200, 100, fill=GREEN, opacity=0.5))
    b.append(text(160, 276, "终图 5 节点", 13, bold=True))
    b.append(text(160, 296, "arg + reshape + const×2", 10))
    b.append(text(160, 312, "+ fused_matmul_bias_relu", 10))
    b.append(text(160, 336, "（与 D83 集成验收一致）", 9.5, MUTED))
    b.append(arrow(160, 172, 160, 246, sw=1.8, label="S1 输出"))

    # 下：开关矩阵（真实数据）
    b.append(text(W/2, 390, "开关对照矩阵（TP2 实测：关一个 Pass，图退化成什么样）", 14, bold=True))
    rows = [
        ("全开（默认）", "11 → 5", "五道闸全链路", GREEN),
        ("--no-fuse", "11 → 7", "融合不做：matmul/add/relu 三个分开", ORANGE),
        ("--no-qdq-clean", "11 → 8", "QDQ 保留：quantize/dequantize 留在图上", BLUE),
        ("--no-layout-simp", "11 → 6", "转置不折叠：transpose(const) 留运行时", BLUE),
        ("--no-reshape-merge", "11 → 6", "reshape 链不合并：两次 reshape", BLUE),
        ("-O0（全关）", "11 → 11", "原样输出——图优化整体跳过", RED),
    ]
    y0 = 412
    for i, (name, result, why, color) in enumerate(rows):
        y = y0 + i * 46
        b.append(hand_rect(80, y, 920, 38, fill=color, opacity=0.35))
        b.append(text(200, y + 24, name, 11.5, bold=True, mono=True))
        b.append(text(390, y + 24, result, 11.5, bold=True))
        b.append(text(650, y + 24, why, 10))

    b.append(hand_rect(80, y0 + 6*46 + 8, 920, 48, fill="#F5E9C8", opacity=0.8))
    b.append(text(W/2, y0 + 6*46 + 28, "矩阵的意义：每行＝一次「关掉这个 Pass 会失去什么」的量化记录——D125 对照实验的实验设计直接从这里长出来", 11))
    b.append(text(W/2, y0 + 6*46 + 46, "（另：--fixpoint-max 1 → 5 节点：本图机会一轮挖尽；复杂图会暴露多轮价值）", 9.5, MUTED))
    save("01-overview.svg", "".join(b), h=740)


# ── 图 2：稳定顺序与不动点 ──
def fig2():
    b = []
    b.append(text(W/2, 34, "为什么闸1→2→3→4 的顺序不能乱：机会是上一轮创造出来的", 16, bold=True))

    # 场景1：QDQ 折叠创造转置折叠机会
    b.append(hand_rect(60, 60, 460, 190, fill=BLUE, opacity=0.3))
    b.append(text(290, 84, "场景 A：闸1 创造闸2 的机会", 13, bold=True))
    steps_a = [
        ("初始", "transpose( DQ( Q(const) ) )", "闸2 想折叠 transpose(const)——但里面不是 const！"),
        ("闸1 后", "transpose( const' )", "R04 折叠露出 const'（量化格点值）"),
        ("闸2 后", "const''", "转置折叠进编译期——运行时零搬运"),
    ]
    y = 106
    for stage, ir, why in steps_a:
        b.append(text(100, y + 12, stage, 10.5, bold=True, anchor="start"))
        b.append(text(180, y + 12, ir, 10, mono=True, anchor="start"))
        b.append(text(430, y + 12, why, 9, fill=MUTED, anchor="start"))
        y += 46
    b.append(arrow(150, y - 34, 150, y - 12, sw=1.4))
    b.append(arrow(150, y + 12 - 46, 150, y - 34 + 12, sw=1.4))

    # 场景2：reshape 合并创造融合机会
    b.append(hand_rect(560, 60, 460, 190, fill=ORANGE, opacity=0.3))
    b.append(text(790, 84, "场景 B：闸3 创造闸4 的机会", 13, bold=True))
    steps_b = [
        ("初始", "matmul(reshape(reshape(x)), W)", "融合看 matmul——输入隔两层"),
        ("闸3 后", "matmul(reshape(x), W)", "链合并后输入更干净"),
        ("闸4 后", "fused(reshape(x), W, b)", "结构门看得清：单使用者 ✓"),
    ]
    y = 106
    for stage, ir, why in steps_b:
        b.append(text(600, y + 12, stage, 10.5, bold=True, anchor="start"))
        b.append(text(680, y + 12, ir, 9.5, mono=True, anchor="start"))
        b.append(text(930, y + 12, why, 9, fill=MUTED, anchor="start"))
        y += 46

    # 中：顺序错的后果
    b.append(hand_rect(60, 270, 960, 108, fill=RED, opacity=0.3))
    b.append(text(W/2, 294, "顺序错的后果（思想实验：闸4 提前）", 13, bold=True))
    b.append(text(W/2, 316, "matmul+bias+relu 先融成 fused——但此时 QDQ 还没清、reshape 链还隔着两层", 10.5))
    b.append(text(W/2, 334, "结果：要么融合匹配失败（白跑），要么融合后 fused 挡住闸1~3 的匹配窗口（清理永远做不了）", 10.5))
    b.append(text(W/2, 356, "破坏性最强的 Pass 必须最后做——这是一条普适的管道设计规则", 10.5, fill=RED, bold=True))

    # 下：不动点
    b.append(text(W/2, 404, "不动点循环：让「清理创造机会」自动收敛", 14, bold=True))
    b.append(hand_rect(200, 424, 680, 130, fill="#F5E9C8", opacity=0.8))
    rounds = [
        ("第 1 轮", "闸1: R04 折叠 ✓｜闸2: 转置折叠 ✓｜闸3: reshape 合并 ✓", "→ 11 = 7 节点"),
        ("第 2 轮", "闸1: 无 ✓｜闸2: 无 ✓｜闸3: 无 ✓", "→ 无变化，收敛退出"),
        ("闸4", "（循环外）融合 matmul+add+relu", "→ 7 = 5 节点"),
    ]
    y = 448
    for r, detail, result in rounds:
        b.append(text(240, y, r, 11, bold=True, anchor="start"))
        b.append(text(330, y, detail, 10, anchor="start"))
        b.append(text(820, y, result, 10.5, anchor="start", fill="#4a7c59"))
        y += 30
    b.append(text(W/2, 570, "实测：本图 2 轮收敛（audit 日志可查）；--fixpoint-max 是保险丝——防 Pattern 互相触发抖动", 10.5, MUTED))

    b.append(hand_rect(80, 600, 920, 52, fill=GREEN, opacity=0.35))
    b.append(text(W/2, 622, "面试口径：Pass 管道的两个经典问题——", 12, bold=True))
    b.append(text(W/2, 642, "①顺序怎么定？破坏性从弱到强（等价改写→局部清理→结构融合）；②要不要循环？要——机会是上一轮创造的；但要加轮数保险丝", 10.5))
    save("02-mechanism.svg", "".join(b), h=680)


# ── 图 3：位等价验证与量化语义修正 ──
def fig3():
    b = []
    b.append(text(W/2, 34, "位等价：优化不许改语义——以及今天修掉的一个真 bug", 16, bold=True))

    # 上：验证框架
    b.append(hand_rect(60, 60, 960, 150, fill=BLUE, opacity=0.3))
    b.append(text(W/2, 84, "验证框架（TP6）：3×10000 随机输入，原图 vs 优化图逐位对照", 13, bold=True))
    b.append(text(110, 112, "x ~ N(0,1)，shape (2,12)", 10.5, anchor="start", mono=True))
    b.append(text(110, 132, "eval(原图)：arg→reshape→reshape→matmul→add→relu", 10.5, anchor="start", mono=True))
    b.append(text(110, 152, "eval(优化图)：arg→reshape→fused_matmul_bias_relu", 10.5, anchor="start", mono=True))
    b.append(text(110, 176, "判据：np.array_equal（容差 = 0，不是 allclose）", 11, anchor="start", bold=True, fill="#4a7c59"))
    b.append(text(700, 112, "3 批 × 10000 个随机输入", 10.5, anchor="start"))
    b.append(text(700, 132, "全部 bitwise 一致", 11, anchor="start", fill="#4a7c59", bold=True))
    b.append(text(700, 152, "耗时 ~25 秒（numpy 向量化）", 10, anchor="start", fill=MUTED))

    # 中：今天的真 bug
    b.append(text(W/2, 244, "开发过程中的真 bug：R04 折叠忘了量化语义", 14, bold=True))
    b.append(hand_rect(60, 264, 470, 190, fill=RED, opacity=0.35))
    b.append(text(295, 288, "第一版（错）", 12.5, bold=True, fill=RED))
    b.append(text(295, 312, "DQ(Q(const)) 折叠 → 直接用原值", 10.5))
    b.append(text(295, 332, "0.3 → 折叠后还是 0.3", 10.5, mono=True))
    b.append(text(295, 356, "但原图语义：Q(0.3)=round(38.4)=38", 10, mono=True))
    b.append(text(295, 374, "DQ(38)=38×0.0078125=0.296875", 10, mono=True))
    b.append(text(295, 398, "0.3 ≠ 0.296875 → 位等价炸了（批0#0 就抓住）", 10.5, fill=RED, bold=True))
    b.append(text(295, 420, "随机输入第一个就暴露——验证框架的价值", 10, fill=MUTED))

    b.append(hand_rect(550, 264, 470, 190, fill=GREEN, opacity=0.4))
    b.append(text(785, 288, "修复后（对）", 12.5, bold=True, fill="#4a7c59"))
    b.append(text(785, 312, "折叠值 = DQ(Q(v))——量化格点上的等价", 10.5))
    b.append(text(785, 336, "values = [clip(round(v/s)+zp,", 10, mono=True))
    b.append(text(785, 354, "  -128,127)-zp)*s for v in values]", 10, mono=True))
    b.append(text(785, 378, "0.3 → 0.296875（格点值）", 10.5, mono=True))
    b.append(text(785, 402, "与 D83 终图的 const 完全一致", 10.5, fill="#4a7c59", bold=True))
    b.append(text(785, 424, "（D82 规则表 R04 的语义本来如此）", 10, fill=MUTED))

    # 下：教训
    b.append(hand_rect(60, 478, 960, 110, fill="#F5E9C8", opacity=0.8))
    b.append(text(W/2, 502, "三条教训（都写进了教程 6.1/6.2）", 13, bold=True))
    b.append(text(W/2, 526, "① 「位等价」不是口号是测试——3×10000 随机输入第一个就抓住了折叠语义错；", 10.5))
    b.append(text(W/2, 546, "② 量化图的优化必须带着量化语义做——「值逐位不变」的承诺是格点意义上的（D82 的教训在 minic 里再犯一次）；", 10.5))
    b.append(text(W/2, 566, "③ 对照 D83 冻结产物是对账的第一手段——const 值 0.296875 出现在 D83 report.txt 里，diff 一下就知道折叠语义该是什么", 10.5))
    save("03-example.svg", "".join(b), h=620)


if __name__ == "__main__":
    fig1()
    fig2()
    fig3()
