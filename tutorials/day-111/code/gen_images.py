#!/usr/bin/env python3
"""生成第 111 天的 3 张手绘 sketch 风 SVG 技术图（Excalidraw-like）。

风格约定：白板涂鸦感——线条用带抖动的贝塞尔手绘路径、马克笔笔触、
3～4 种柔和强调色（橙/蓝/绿/红）＋米白背景、简单几何形状、手写感字体。
所有数字来自 2026-11-13 13:12~13:14 最终一轮真实运行（code/outputs/）：
matmul-bias-s1~s4.txt（四份调优报告）、acceptance.txt（三道验收）、
self-test.txt（31/31）、calibration.txt（16 根单价）、tune-summary.json。
固定随机种子，图可复现。
"""

from __future__ import annotations

import math
import os
import random

random.seed(111)

BG = "#FDFBF6"
BORDER = "#E7DFCE"
INK = "#3B3B3B"
MUTED = "#6b6257"
ORANGE = "#E8A87C"
BLUE = "#A9C4D4"
GREEN = "#9CBF8E"
RED = "#C97B7B"
GRAYC = "#EDE7DA"
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


def dot(x, y, r=5.5, fill=ORANGE, stroke=INK, sw=1.3):
    return (f'<circle cx="{x + jit(0.8):.1f}" cy="{y + jit(0.8):.1f}" r="{r}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')


def text(x, y, s, size=13, fill=INK, anchor="middle", bold=False, rotate=None):
    import xml.sax.saxutils as su
    s = su.escape(s)
    wt = ' font-weight="bold"' if bold else ""
    tr = f' transform="rotate({rotate} {x} {y})"' if rotate is not None else ""
    return (f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" '
            f'text-anchor="{anchor}"{wt}{tr}>{s}</text>')


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


def card(b, x, y, w, h, title, lines, fill, tsize=11.5, lsize=10, opacity=0.42,
         tcolor=INK, anchor_left=False):
    b.append(hand_rect(x, y, w, h, fill, opacity, INK, 1.6))
    ax = x + 12 if anchor_left else x + w / 2
    aanchor = "start" if anchor_left else "middle"
    if title:
        b.append(text(ax, y + 19, title, tsize, tcolor, aanchor, True))
    for i, ln in enumerate(lines):
        b.append(text(ax, y + 38 + i * 16.5, ln, lsize, INK, aanchor))


# ======================= 图 1：全局定位图 =======================

def fig1():
    W, H = 980, 650
    b = frame(W, H, "第 111 天定位：集成验收——把第四阶段的零件装成一台机器")
    b.append(hand_line(280, 44, 700, 45, ORANGE, 3))

    # ---- 上排：第四阶段四周的链路 ----
    b.append(text(52, 68, "第四阶段的链路（D85~D112，每站都已各自验收）", 12.5, INK,
                  "start", True))
    steps = [("Lowering 骨架", "D86~90 · mini.matmul→循环"),
             ("Tiling＋循环变换", "D91~97 · 顺序/展开/尾部"),
             ("内存约束", "D98~104 · 五项记账"),
             ("搜索空间", "D106 · 值域剪枝"),
             ("测量纪律", "D107 · 3+7/3+21"),
             ("全测＋模型", "D108~110 · 实测/预筛")]
    for i, (nm, day) in enumerate(steps):
        x = 52 + i * 150
        b.append(hand_rect(x, 78, 138, 54, GRAYC, 0.5, INK, 1.2))
        b.append(text(x + 69, 99, nm, 10.5, INK, "middle"))
        b.append(text(x + 69, 118, day, 9.2, MUTED))
        if i < len(steps) - 1:
            b.append(arrow(x + 140, 105, x + 149, 105, MUTED, 1.4))
    b.append(hand_rect(52 + 6 * 150, 74, 138, 62, ORANGE, 0.75, INK, 1.8))
    b.append(text(52 + 6 * 150 + 69, 96, "集成验收", 11.5, INK, "middle", True))
    b.append(text(52 + 6 * 150 + 69, 114, "D111 今天", 10, INK))
    b.append(text(52 + 6 * 150 + 69, 128, "一条命令收口", 9.2, MUTED))

    # ---- 中排：今天的六站流水线 ----
    b.append(text(52, 172, "今天的一条流水线：mini.matmul 文本进去，冠军＋报告出来",
                  12.5, INK, "start", True))
    boxes = [("S0 前端", ["mini 图 IR 解析", "shape 推断＋语义校验", "0.1 ms"], GRAYC),
             ("S1 Lowering", ["D85~90 任务单", "六项结构证据 ✓", "kernel_gen 实现"], BLUE),
             ("S2 候选空间", ["D106 值域剪枝", "tile 池×6 顺序×U", "S1 144 / S4 2250"], BLUE),
             ("S3 资源闸门", ["D104 五项记账", "≤ 256 KiB", "S4 剪 72 个"], BLUE),
             ("S4 模型预筛", ["D110 排序 10~35 µs", "名额每家族一个", "零内核执行"], GREEN),
             ("S5 编译＋实测", ["编译计时＋bitwise 门", "3+7 筛选 / 3+21 决赛", "9 个候选"], GREEN),
             ("冠军＋报告", ["4 shape × 36 条记录", "tune-summary.json", "账本随行"], ORANGE)]
    for i, (nm, lines, fill) in enumerate(boxes):
        x = 52 + i * 129
        card(b, x, 184, 120, 86, nm, lines, fill, 10, 8.8, 0.5)
        if i < len(boxes) - 1:
            b.append(arrow(x + 121, 227, x + 128, 227, INK, 1.8))
    b.append(text(W / 2, 292, "血统纪律：kernel_gen/bench/cost_model 是 D108~D110 的逐字节副本，今天零改动",
                  10, MUTED))

    # ---- 下排：一条命令与三道验收 ----
    b.append(text(52, 322, "『一条可重复运行的调优命令』：./run_all.sh（本次真实运行 66 秒）",
                  12.5, INK, "start", True))
    card(b, 52, 334, 430, 118, "命令做什么（全部真实落盘 outputs/）",
         ["① 校准 1956 ms 落盘 → ② 四份 mini 输入逐个跑 S0~S5",
          "   （S1 64³ / S2 96³ / S3 90×96×64 / S4 160³ 新 shape）",
          "③ 验收实验 ④ 31/31 自检 ⑤ 环境记录",
          "产出 12 个文件：4 报告＋验收＋自检＋缓存＋36 条记录＋汇总"],
          BLUE, 10.5, 9.4, 0.42)
    card(b, 520, 334, 408, 118, "三道验收硬标准（acceptance.txt）",
         ["① 同进程全测对照：18 候选全测 vs 引导 top-5",
          "   冠军一致 ✓、recall@5 命中 ✓、提速 1.8×",
          "② 投毒：no-tail 内核被门拒收（err=10.1，不计时）✓",
          "③ D108 一致性：3 个 shape 近对互换（跨进程，参考口径）"],
          GREEN, 10.5, 9.4, 0.42)

    # ---- 底部：今天的核心论点 ----
    b.append(hand_line(52, 482, 928, 483, BORDER, 2))
    card(b, 100, 496, 780, 118, "集成验收的判据：不是『更快』，是『每个环节都还认账』",
         ["① 前端拒收坏 shape、闸门拒收超预算 tile、门拒收坏内核——三层 fail-closed 全点火；",
          "② 模型预筛省掉 97% 的实测（144→9 个），S4 资源闸门真剪掉 72 个超预算候选；",
          "③ 同进程对照给出 recall@5 命中的硬证据；冠军名次只在同进程内宣布（D107 纪律）。",
          "集成不改零件、只装零件——改过的零件要重新验收，这是今天最重要的工程规矩。"],
          ORANGE, 11, 10, 0.4)
    save("01-overview.svg", b)


# ======================= 图 2：核心机制图 =======================

def fig2():
    W, H = 980, 680
    b = frame(W, H, "六站流水线解剖：mini.matmul → 冠军（S1 64×64×64 真实走一遍）")
    b.append(hand_line(280, 44, 700, 45, ORANGE, 3))

    # ---- 左上：S0 前端 ----
    card(b, 40, 62, 300, 108, "S0 前端：mini 图 IR 解析（0.1 ms）",
         ["func @matmul_bias(A 64x64, B 64x64, bias 64)",
          "%mm = mini.matmul %A, %B    : -> 64x64",
          "%C  = mini.add %mm, %bias   : 广播 -> 64x64",
          "校验：K 咬合 ✓ bias 长度 ✓ 返回类型 ✓"],
         GRAYC, 10.5, 9.2, 0.5, anchor_left=True)
    b.append(arrow(190, 172, 190, 196, INK, 2))

    # ---- 左中：S1 Lowering 任务单 ----
    card(b, 40, 198, 300, 128, "S1 Lowering：D85~D90 任务单（六项证据 ✓）",
         ["输出初始化(D87)：C 以 bias 预填（alloc_c）",
          "tile 外壳(D88)＋min 钳制(D90)：8 个 tile",
          "元素循环 v1/v2/v3(D88/89) · 前奏＋尾部(D95/96)",
          "写回语句(D89) ——语义证据＝bitwise 门",
          "实现者：kernel_gen.py（D108 逐字节副本）"],
         BLUE, 10.5, 9.2, 0.45, anchor_left=True)
    b.append(arrow(190, 328, 190, 352, INK, 2))

    # ---- 左下：S2+S3 空间漏斗 ----
    card(b, 40, 354, 300, 150, "S2 空间＋S3 闸门：值域 → 参数 → 资源",
         ["naive 枚举上限 50,331,648",
          "值域（tile 池∪精确 tile×6 顺序×U）→ 144",
          "参数约束（U≤内层圈数）→ 剪 0（tile≥32 点不着火，",
          "  自检用合成 8³ U=16 验证会点火）",
          "资源闸门：五项记账 A+B+C+bias ≤ 256 KiB",
          "  S1 最大占用 49,408 B（18.8%）→ 幸存 144"],
         BLUE, 10.5, 9.2, 0.45, anchor_left=True)

    # ---- 右上：S4 模型预筛（名额规则） ----
    b.append(text(660, 78, "S4 模型预筛：静态排序＋家族名额（D110）", 12, INK,
                  "middle", True))
    b.append(text(660, 95, "144 个候选 1 ms 排完（10 µs/候选，零内核执行）", 9.4, MUTED))
    rows = [("1", "64³ ikj U=1", "18.1", True),
            ("5", "64³ kij U=1", "18.1", False),
            ("9", "64³ ijk U=1", "19.6", False),
            ("13", "64³ jik U=1", "19.6", False),
            ("17", "64³ ikj U=2", "19.8", False)]
    b.append(text(432, 120, "模型名次", 9.4, MUTED))
    b.append(text(484, 120, "配置", 9.4, MUTED))
    b.append(text(580, 120, "预测 ms", 9.4, MUTED))
    b.append(text(650, 120, "→ 进名额", 9.4, MUTED))
    b.append(hand_line(424, 126, 740, 127, BORDER, 1.4))
    for i, (rk, cfg, pred, hot) in enumerate(rows):
        y = 146 + i * 27
        b.append(hand_rect(640, y - 12, 74, 21, GREEN, 0.55, INK, 1.2))
        b.append(text(677, y + 3, "实测 ✓", 9, INK))
        b.append(text(440, y + 3, rk, 10, INK, hot))
        b.append(text(484, y + 3, cfg, 10, INK, "start", hot))
        b.append(text(592, y + 3, pred, 10, INK))
    b.append(text(660, 292, "名额规则：每个 (order,U) 家族只留最优 tile 变体", 9.8, INK,
                  "middle", True))
    b.append(text(660, 308, "——S2 的教训：模型前 9 名全是 ikj 的 tile 变体", 9.2, INK))
    b.append(text(660, 322, "（极差 0.08%），近对 kij 被挤到第 10；名额按家族分,", 9.2, INK))
    b.append(text(660, 336, "模型分不出的候选不占 recall@K 的名额", 9.2, INK))

    # ---- 右中：S5 实测 ----
    b.append(text(660, 372, "S5 编译＋验证＋实测（D107 协议）", 12, INK, "middle", True))
    b.append(text(660, 388, "编译 9 次 2.6 ms → bitwise 门 → 3+7 / 3+21", 9.4, MUTED))
    srows = [("64³ ikj U=1", "15.56", "15.70", "冠军 ★"),
             ("64³ kij U=1", "16.90", "17.10", "近对（D108 冠军）"),
             ("64³ ijk U=1", "17.38", "17.64", ""),
             ("32³ ijk U=1 缺省", "—", "18.98", "决赛陪跑")]
    b.append(text(452, 412, "配置", 9.4, MUTED, "start"))
    b.append(text(590, 412, "screen 3+7", 9.4, MUTED))
    b.append(text(668, 412, "final 3+21", 9.4, MUTED))
    b.append(text(748, 412, "备注", 9.4, MUTED))
    b.append(hand_line(444, 418, 880, 419, BORDER, 1.4))
    for i, (cfg, s1, s2, note) in enumerate(srows):
        y = 438 + i * 26
        hot = i == 0
        if hot:
            b.append(hand_rect(440, y - 13, 330, 24, ORANGE, 0.5, INK, 1.4))
        b.append(text(452, y + 4, cfg, 9.6, INK, "start", hot))
        b.append(text(598, y + 4, s1, 9.6, INK))
        b.append(text(676, y + 4, s2, 9.6, INK, hot))
        b.append(text(748, y + 4, note, 8.8, MUTED, "start"))

    # ---- 底部：S4 的闸门真剪东西 + 账本 ----
    b.append(hand_line(52, 548, 928, 549, BORDER, 2))
    card(b, 60, 560, 420, 100, "S4（160³）的资源闸门（真实剪裁现场）",
         ["160³ tile 五项 = 102,400×3 + 640 = 307,840 B",
          "  > 256 KiB 预算 → 4 组超预算 tile × 18 = 剪 72 个",
          "  （160³、160×160×128、160×128×160、128×160×160）",
          "2,250 → 幸存 2,178；模型 77 ms 排完（35 µs/候选）"],
         RED, 10.5, 9.2, 0.4)
    card(b, 520, 560, 408, 100, "S1 的账本（本进程全程，真实计时）",
         ["解析 0.1 + 空间/闸门 0.7 + 模型 1 + 编译 2.6",
          "  + 实测 Σwall 2858 = 2867 ms",
          "D108 全测基线 Σwall 7966 ms（跨进程参考）→ 提速 2.8×",
          "实测 9 个候选 vs 基线全测——省下的都靠『先算后测』"],
         GREEN, 10.5, 9.2, 0.42)
    save("02-mechanism.svg", b)


# ======================= 图 3：实验结果对照图 =======================

def fig3():
    W, H = 980, 660
    b = frame(W, H, "四份 mini 输入的战绩：空间、闸门、冠军与三道验收（全部真实运行）")
    b.append(hand_line(280, 44, 700, 45, ORANGE, 3))

    # ---- 左上：四 shape 战绩表 ----
    b.append(text(280, 74, "四个负载各跑一遍 S0~S5", 12, INK, "middle", True))
    b.append(text(280, 91, "（naive 上限 5,033 万~7.86 亿，值域剪枝后）", 9.4, MUTED))
    cols = ("负载", "空间", "闸门剪", "实测", "冠军（ms）")
    xs = (66, 176, 258, 336, 420)
    b.append(text(66, 116, cols[0], 9.4, MUTED, "start"))
    b.append(text(200, 116, cols[1], 9.4, MUTED))
    b.append(text(282, 116, cols[2], 9.4, MUTED))
    b.append(text(352, 116, cols[3], 9.4, MUTED))
    b.append(text(452, 116, cols[4], 9.4, MUTED))
    b.append(hand_line(56, 122, 520, 123, BORDER, 1.4))
    trows = [("S1 64³", "144", "0", "9", "64³ ikj U=1 = 15.70"),
             ("S2 96³", "486", "0", "9", "96³ ikj U=1 = 50.98"),
             ("S3 90×96×64", "234", "0", "9", "90×96×64 ikj U=1 = 31.56"),
             ("S4 160³ 新", "2250", "72", "9", "96×160×160 ikj U=1 = 233.68")]
    for i, (ld, sp, cut, mea, champ) in enumerate(trows):
        y = 144 + i * 30
        if i == 3:
            b.append(hand_rect(54, y - 16, 470, 27, ORANGE, 0.4, INK, 1.3))
        b.append(text(66, y, ld, 9.8, INK, "start", i == 3))
        b.append(text(200, y, sp, 9.8, INK))
        b.append(text(282, y, cut, 9.8, RED if cut != "0" else MUTED))
        b.append(text(352, y, mea, 9.8, INK))
        b.append(text(452, y, champ, 9.8, INK, "start", i == 3))
    b.append(text(280, 282, "每个负载：9 次实测拿到冠军；S4 的闸门剪掉 72 个超预算 tile", 9.6, INK))
    b.append(text(280, 298, "全部 36 条 bench 记录落盘 tune-results.jsonl（含模型预测值）", 9.6, MUTED))

    # ---- 右上：提速账 ----
    b.append(text(742, 74, "搜索时间账：bench Σwall 对比", 12, INK, "middle", True))
    b.append(text(742, 91, "（基线 = D108 全测逐条累加，跨进程参考）", 9.4, MUTED))
    bw = 250
    bars = [("S1", 7966, 2858), ("S2", 36941, 9353), ("S3", 23685, 5878)]
    for i, (sid, base, guide) in enumerate(bars):
        y = 122 + i * 56
        b.append(text(568, y + 5, f"{sid} 基线", 9.2, MUTED, "end"))
        b.append(hand_rect(576, y - 8, bw, 17, RED, 0.5, INK, 1.2))
        b.append(text(576 + bw + 6, y + 5, f"{base / 1000:.1f} s", 8.8, MUTED))
        b.append(text(568, y + 26, f"{sid} 本流水线", 9.2, INK, "end"))
        w2 = bw * guide / base
        b.append(hand_rect(576, y + 13, w2, 17, GREEN, 0.6, INK, 1.3))
        b.append(text(576 + w2 + 6, y + 26, f"{guide / 1000:.1f} s → {base / guide:.1f}×",
                      9.2, INK, "start", True))
    b.append(text(742, 298, "省下的 97% 实测全部来自『先算后测』", 9.8, INK, "middle", True))

    # ---- 左下：验收① 同进程全测对照 ----
    b.append(hand_line(52, 330, 928, 331, BORDER, 2))
    card(b, 60, 344, 420, 138, "验收①：同进程全测对照（32³，无漂移口实）",
         ["全测：18 个幸存候选 × 3+7，Σwall 598 ms",
          "  冠军 32³ ikj U=1 = 2.16 ms",
          "引导：top-5＋决赛，实测 8 个，Σwall 325 ms",
          "  冠军 32³ ikj U=1 = 2.16 ms → 一致 ✓",
          "recall@5 命中 ✓（全测冠军在模型名额里）· 提速 1.8×",
          "判定标准：同进程里『真漏』才是漏——名次分歧看 2×MAD 规则"],
         GREEN, 10.5, 9.2, 0.42)

    # ---- 右下：验收③ 近对互换现象 ----
    card(b, 520, 344, 408, 138, "验收③：近对互换——调优器对当下环境负责",
         ["本进程：ikj 15.70 vs kij 17.10（同进程，4 个 shape 一致）",
          "D108 进程：kij 15.80 vs ikj 16.99 → 冠军互换",
          "同日另一轮复现：kij 3/3 与 D108 同配置——近对随机器",
          "状态互换（D107 漂移 ~8.6%），两边读数各自自洽",
          "结论：冠军只在同进程内宣布；跨进程对照只作参考"],
         BLUE, 10.5, 9.2, 0.42)

    # ---- 底部：投毒 + 自检 ----
    card(b, 60, 500, 420, 100, "验收②：投毒（门在集成里不豁免）",
         ["32³ jki U=4/no-tail 混进 S5 实测名单",
          "（S3 边界 tile 余 26，尾部 2 圈非空才毒得起来）",
          "→ passed=False，max_abs_err=10.1，stats=None",
          "被拒不计时但留痕——fail-visible 纪律原样继承"],
         RED, 10.5, 9.2, 0.4)
    card(b, 520, 500, 408, 100, "自检：31/31 项断言（self-test.txt）",
         ["前端 8 项（坏 shape/bias/返回类型全被拒）",
          "空间/闸门 8 项 · 模型 6 项 · 门/编译 3 项",
          "端到端 32³ mini 文本 → 冠军一条调用跑完",
          "血统：results-d108.jsonl sha256 钉死才允许基线对照"],
         GREEN, 10.5, 9.2, 0.42)
    save("03-results.svg", b)


def main():
    print("生成第 111 天的 3 张 sketch 风 SVG：")
    fig1()
    fig2()
    fig3()
    print("完成。")


if __name__ == "__main__":
    main()
