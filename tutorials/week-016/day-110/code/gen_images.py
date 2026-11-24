#!/usr/bin/env python3
"""生成第 110 天的 3 张手绘 sketch 风 SVG 技术图（Excalidraw-like）。

风格约定：白板涂鸦感——线条用带抖动的贝塞尔手绘路径、马克笔笔触、
3～4 种柔和强调色（橙/蓝/绿/红）＋米白背景、简单几何形状、手写感字体。
所有数字来自 2026-11-13 12:32 最终一轮真实运行（code/outputs/）：
calibration.txt（16 根单价）、model-table.txt / accuracy.txt（排序与误差）、
guided-search.txt（3/3 冠军、20.0 s vs 68.6 s）、topk-sensitivity.txt
（K=1 慢 4.8~8.1%）、drift-a-b.txt（同进程交错 A/B）、extrapolation.txt
（外推口径）。固定随机种子，图可复现。
"""

from __future__ import annotations

import math
import os
import random

random.seed(110)

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


def hand_poly(pts, stroke=INK, sw=1.6, dash=None, fill="none"):
    dd = f' stroke-dasharray="{dash}"' if dash else ""
    d = f"M {pts[0][0] + jit():.1f},{pts[0][1] + jit():.1f} "
    for i in range(1, len(pts)):
        a, b = pts[i - 1], pts[i]
        mx, my = (a[0] + b[0]) / 2 + jit(1.8), (a[1] + b[1]) / 2 + jit(1.8)
        d += f"Q {mx:.1f},{my:.1f} {b[0] + jit():.1f},{b[1] + jit():.1f} "
    return (f'<path d="{d}" stroke="{stroke}" stroke-width="{sw}" '
            f'stroke-linecap="round" stroke-linejoin="round" fill="{fill}"{dd}/>')


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


def dot(x, y, r=5.5, fill=ORANGE, stroke=INK, sw=1.3, hollow=False):
    f = "none" if hollow else fill
    return (f'<circle cx="{x + jit(0.8):.1f}" cy="{y + jit(0.8):.1f}" r="{r}" fill="{f}" '
            f'stroke="{stroke}" stroke-width="{sw}"/>')


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
         tcolor=INK):
    b.append(hand_rect(x, y, w, h, fill, opacity, INK, 1.6))
    if title:
        b.append(text(x + w / 2, y + 19, title, tsize, tcolor, "middle", True))
    for i, ln in enumerate(lines):
        b.append(text(x + w / 2, y + 38 + i * 16.5, ln, lsize, INK, "middle"))


# ======================= 图 1：全局定位图 =======================

def fig1():
    W, H = 980, 640
    b = frame(W, H, "第 110 天定位：Cost Model 排序——把『逐个实测』换成『先算后测』")
    b.append(hand_line(250, 44, 730, 45, ORANGE, 3))

    # ---- 上排：四周脉络 ----
    b.append(text(52, 70, "调优主线（第四阶段）", 12.5, INK, "start", True))
    steps = [("候选生成", "D106 · 12,970"), ("测量纪律 3+7/3+21", "D107"),
             ("全测搜索 v0.1", "D108 · 98 槽"), ("Roofline 参照系", "D109"),
             ("Cost Model 预剪", "D110 今天"), ("集成验收", "D111 明天")]
    for i, (nm, day) in enumerate(steps):
        x = 52 + i * 150
        hot = day.startswith("D110")
        b.append(hand_rect(x, 78 if hot else 82, 138, 58 if hot else 52,
                           ORANGE if hot else GRAYC,
                           0.75 if hot else 0.5, INK, 1.6 if hot else 1.2))
        b.append(text(x + 69, 78 + 21, nm, 10.5, INK, "middle", hot))
        b.append(text(x + 69, 78 + 40, day, 10, MUTED if not hot else INK))
        if i < len(steps) - 1:
            b.append(arrow(x + 140, 106, x + 149, 106, MUTED, 1.4))

    # ---- 中排：今天的流水线 ----
    b.append(text(52, 176, "今天的流水线：排序是『算』出来的，实测只留给前几名", 12.5, INK, "start", True))
    boxes = [("候选空间", ["S1 24 / S2 36 / S3 36+2 投毒", "共 96 个正确候选"], GRAYC),
             ("① 校准（一次）", ["16 根语句行单价", "微基准 ~2 s，三 shape 共用"], BLUE),
             ("② 静态排序", ["count_ops × 单价", "28 µs/候选 · 零内核执行"], BLUE),
             ("③ 只实测 top-5", ["3+7 协议 · 过正确性门", "投毒内核由门拒收"], GREEN),
             ("④ 决赛 top-3∪缺省", ["3+21 复测", "冠军 vs 缺省同进程"], GREEN),
             ("冠军 + 账本", ["guided-results.jsonl", "预测值随记录落盘"], ORANGE)]
    for i, (nm, lines, fill) in enumerate(boxes):
        x = 52 + i * 150
        card(b, x, 188, 138, 84, nm, lines, fill, 10.5, 9.2,
             0.55 if fill is GRAYC else 0.45)
        if i < len(boxes) - 1:
            b.append(arrow(x + 139, 230, x + 149, 230, INK, 1.8))
    b.append(text(W / 2, 296, "校准和排序都不执行被测内核——『测』发生在名单被砍短之后",
                  10.5, MUTED))

    # ---- 下排：两条路线的账 ----
    b.append(text(52, 326, "两条路线的搜索成本账（同一候选空间，真实运行记录）",
                  12.5, INK, "start", True))
    # D108 全测
    card(b, 52, 338, 420, 120, "D108 路线：全测（实测 98 筛选槽 + 12 决赛）",
         ["筛选 Σwall 57.1 s ＋ 决赛 Σwall 11.5 s → 共 68.6 s",
          "外推 D106 全空间 12,970 候选：",
          "  · 96³ 口径 ≈ 12,970 × 0.86 s ≈ 3.1 小时",
          "  · 512³ 口径 ≈ 13 天（D108 第四节外推，非实测）"],
         RED, 11, 10, 0.38)
    # D110 引导
    card(b, 508, 338, 420, 120, "D110 路线：Cost Model 预剪（本次真实运行）",
         ["校准 ~2 s（一次性）＋ 静态分析 2.0 ms ＋ 实测 27 次",
          "→ 引导搜索 20.0 s，冠军与 D108 全测 3/3 同配置",
          "外推同一空间 ≈ 15 s（校准 0.2 + 分析 0.4 + 实测 15 s）",
          "搜索成本从『天』压到『分钟』——提速 3.4×（小空间）"],
         GREEN, 11, 10, 0.42)
    b.append(arrow(474, 398, 506, 398, INK, 2.2))
    b.append(text(490, 388, "换", 12, INK))

    # ---- 底部结论 ----
    b.append(hand_line(52, 486, 928, 487, BORDER, 2))
    card(b, 120, 502, 740, 106, "今天的前提与 KPI（先记两句话，正文展开）",
         ["模型把 96 个候选按预测时间排好序，只把 top-5 交给实测——",
          "模型的 KPI 不是猜中第 1 名，而是 recall@K：把真冠军留在名额里",
          "（本次三个 shape 的真冠军都在模型第 2 名，K=2 起就进名额）。",
          "错放一个近对不致命：预测只差 0.4% 的 ikj/kij，谁第 1 由同进程实测定。"],
         ORANGE, 11, 10.2, 0.4)
    save("01-overview.svg", b)


# ======================= 图 2：核心机制图 =======================

def fig2():
    W, H = 980, 660
    b = frame(W, H, "Cost Model 三层结构：数行 → 定价 → 求和（S1 冠军 64³ kij U=1 为例）")
    b.append(hand_line(250, 44, 730, 45, ORANGE, 3))

    # ---- 左：① 静态计数器 ----
    b.append(text(172, 76, "① count_ops(64,64,64, kij)：数源码行", 12.5, INK, "middle", True))
    b.append(text(172, 94, "逐行镜像 kernel_gen.py 的生成规则；", 9.5, MUTED))
    b.append(text(172, 107, "计价单位 = 源码行（Ci=C[v];Ai=A[v] 算一行）", 9.5, MUTED))
    layers = [
        ("tile 外壳", "for i0/j0/k0…：循环迭代 1×1×1", "min3 ×1 行"),
        ("v1 行提升", "k 循环体：64 次迭代", "it_v1=64 · hs1×64"),
        ("v2 行提升", "内层行 Ci=C[v1]; a=A[v1][v1]", "it_v2=4096 · hsm×4096"),
        ("v3 主循环", "Ci[v1] += a*Bv[v1]（j 内层）", "it_main=262144 行"),
    ]
    for i, (nm, desc, cnt) in enumerate(layers):
        y = 120 + i * 56
        hot = i == 3
        b.append(hand_rect(40, y, 264, 48, ORANGE if hot else GRAYC,
                           0.5 if hot else 0.4, INK, 1.5 if hot else 1.2))
        b.append(text(52, y + 19, nm, 10.5, INK, "start", hot))
        b.append(text(52, y + 34, desc, 8.8, MUTED))
        b.append(text(296, y + 27, cnt, 9.2, INK, "end", hot))
        if i < 3:
            b.append(arrow(172, y + 49, 172, y + 55, MUTED, 1.2))
    b.append(text(172, 358, "262144 行 × 60.2 ns ≈ 15.8 ms（占预测 81%）",
                  10.2, INK, "middle", True))
    b.append(arrow(310, 240, 336, 240, INK, 2.2))

    # ---- 中：② 校准单价 ----
    b.append(text(500, 76, "② calibrate()：微基准量单价（ns/行）", 12.5, INK, "middle", True))
    b.append(text(500, 94, "三尺寸最小二乘斜率，中位数×7 次重复；", 9.5, MUTED))
    b.append(text(500, 107, "镜像三纪律：局部变量 · 数据≤80KB · 下标≤96", 9.5, MUTED))
    prices = [("j0  j 内层行", 60.2, "Ci[v] += a*Bv[v]", None),
              ("k0  k 内层行", 61.2, "c += Ai[v]*B[v][v2]", None),
              ("i0  i 内层行", 92.0, "双跨步最惨家族", RED),
              ("ju  j 内层+展开", 75.6, "展开税 +15.4 ns", None),
              ("loop 循环机器", 6.7, "FOR_ITER+STORE", None),
              ("range3 三参建立", 181.1, "range(lo, lo+n, U)", None),
              ("hsm 行提升·单+双", 44.5, "Ci=C[v]; a=A[v][v1]", None),
              ("min3 外壳三连 min", 525.5, "每 tile 一行", None)]
    bar_x, bar_w = 620, 150
    for i, (nm, v, note, col) in enumerate(prices):
        y = 126 + i * 29
        b.append(text(384, y, nm, 9.6, INK, "end"))
        w = max(6, min(1, v / 525.5) * bar_w)
        b.append(hand_rect(bar_x, y - 10, w, 15, col if col else BLUE, 0.55,
                           INK, 1.1))
        b.append(text(bar_x + w + 8, y, f"{v:g}", 9.6, INK, "start", v >= 90))
    b.append(hand_line(384, 352, 770, 353, BORDER, 1.5))
    b.append(text(500, 372, "j0 与 k0 是近对：差 1.0 ns——", 10, INK, "middle", True))
    b.append(text(500, 387, "这条近对决定 j/k 家族次序，对噪声敏感", 10, INK))
    b.append(text(500, 401, "（次序若翻转，冠军在近对内互换，仍在 top-K 里）", 9.4, MUTED))
    b.append(arrow(500, 412, 500, 436, INK, 2.2))

    # ---- 右/下：③ 预测与三道验证 ----
    b.append(text(500, 456, "③ predict_ms：t = Σ 行数 × 单价", 12.5, INK, "middle", True))
    card(b, 60, 468, 400, 78, "冠军 64³ kij U=1 的求和",
         ["j0: 262144×60.2 + hsm: 4096×44.5 + loop: 266307×6.7",
          "  + range/pre/min3…（16 项）",
          "→ 预测 19.42 ms；D108 实测 15.81 ms（+22.8%，模型第 2 名）"],
         BLUE, 10.5, 9.4, 0.45)
    card(b, 520, 468, 400, 78, "流量项：只报账，不进排序（D109 纪律）",
         ["元素访问 790528 次 × 4 B ÷ C 级 2.68 GB/s = 1.18 ms",
          "≈ 预测的 6%：内存时间比解释时间低一个数量级；",
          "它与语句成本是同一批解释器事件的不同计价——不叠加"],
         GRAYC, 10.5, 9.4, 0.45)
    # 三道验证
    b.append(text(500, 586, "三道验证（全部真实运行）", 12, INK, "middle", True))
    card(b, 60, 598, 280, 52, None,
         ["settrace 真值：39 配置 × 17 项计数全部一致",
          "（静态数行 = 解释器逐行事件，口径钉死）"], GREEN, 10, 9.2, 0.4)
    card(b, 360, 598, 280, 52, None,
         ["方向自检：i0=92.0 > k0=61.2/j0=60.2；",
          "ju>j0；hsm>hs2>hs1——量级 10~200 ns"], GREEN, 10, 9.2, 0.4)
    card(b, 660, 598, 280, 52, None,
         ["Roofline 下界 9.59 ms ≤ 预测 19.42 ms ✓",
          "（flops ÷ 解释屋顶 P，与候选无关）"], GREEN, 10, 9.2, 0.4)
    save("02-mechanism.svg", b)


# ======================= 图 3：实测对照图 =======================

def fig3():
    W, H = 980, 660
    b = frame(W, H, "实测对照：排对结构、排错近对——top-K 实测兜底（S1 64×64×64）")
    b.append(hand_line(250, 44, 730, 45, ORANGE, 3))

    # ---- 左：模型名次 vs 实测名次 ----
    b.append(text(240, 74, "模型排序 vs D108 实测（24 个候选的前 5 名）",
                  12, INK, "middle", True))
    b.append(text(240, 91, "预测与实测同向吗？近对处谁对谁错？", 9.6, MUTED))
    rows = [("1", "ikj U=1", "19.34", "16.99", "实测第 2", False),
            ("2", "kij U=1", "19.42", "15.81", "实测第 1 ★冠军", True),
            ("3", "ijk U=1", "19.73", "17.48", "实测第 3", False),
            ("4", "jik U=1", "19.78", "17.83", "实测第 5", False),
            ("5", "ikj U=4", "21.05", "18.82", "实测第 7", False)]
    b.append(text(62, 116, "模型名次", 9.5, MUTED))
    b.append(text(112, 116, "配置", 9.5, MUTED))
    b.append(text(196, 116, "预测 ms", 9.5, MUTED))
    b.append(text(258, 116, "实测 ms", 9.5, MUTED))
    b.append(text(330, 116, "实测名次", 9.5, MUTED))
    b.append(hand_line(56, 122, 420, 123, BORDER, 1.4))
    for i, (rk, cfg, pred, act, tag, hot) in enumerate(rows):
        y = 142 + i * 30
        if hot:
            b.append(hand_rect(54, y - 16, 368, 27, ORANGE, 0.5, INK, 1.4))
        b.append(text(66, y, rk, 10.2, INK, hot))
        b.append(text(112, y, "64³ " + cfg, 10.2, INK, "start", hot))
        b.append(text(196, y, pred, 10.2, INK, hot))
        b.append(text(258, y, act, 10.2, INK, hot))
        b.append(text(330, y, tag, 9.4, INK if hot else MUTED, "start", hot))
    b.append(text(240, 305, "Spearman ρ = 0.967（S2 0.980 / S3 0.964）", 10.6, INK,
                  "middle", True))
    b.append(text(240, 322, "错误排序现场：预测只差 0.4% 的近对（ikj 19.34 vs kij 19.42），",
                  9.4, INK))
    b.append(text(240, 336, "模型把 ikj 排第 1；实测 kij 快 7.1%——误差 +22.8% 的一行。",
                  9.4, INK))
    b.append(text(240, 352, "教训：模型擅长砍数量（ρ 高），不擅长在近对里定名次。",
                  9.6, MUTED))

    # ---- 右上：TOP_K 敏感性 ----
    b.append(text(724, 74, "TOP_K 敏感性：名额 K 给多少才够？", 12, INK, "middle", True))
    b.append(text(724, 91, "（三 shape 同规律：K=1 = 完全相信模型）", 9.6, MUTED))
    b.append(text(560, 122, "名额 K", 9.5, MUTED, "start"))
    b.append(text(640, 122, "选中的配置", 9.5, MUTED, "start"))
    b.append(text(780, 122, "vs 真冠军", 9.5, MUTED, "start"))
    b.append(text(868, 122, "判定", 9.5, MUTED, "start"))
    b.append(hand_line(552, 128, 900, 129, BORDER, 1.4))
    krows = [("K=1", "ikj U=1", "+4.8% ~ +8.1%", "✗ 漏掉（模型误差的代价）", RED),
             ("K=2", "kij U=1", "−1.8% ~ −1.9%", "✓ 真冠军（3/3 shape）", GREEN),
             ("K=3~5", "kij U=1", "同上", "✓ 真冠军", GREEN)]
    for i, (k, cfg, delta, verdict, col) in enumerate(krows):
        y = 150 + i * 34
        b.append(hand_rect(552, y - 14, 348, 28, col, 0.4, INK, 1.2))
        b.append(text(560, y, k, 10, INK, "start", True))
        b.append(text(640, y, cfg, 10, INK, "start"))
        b.append(text(790, y, delta, 9.4, INK, "middle"))
        b.append(text(868, y, verdict, 8.8, INK, "start"))
    b.append(text(724, 272, "K=1 会锁死模型的第 1 名——慢 4.8~8.1%；", 9.8, INK))
    b.append(text(724, 287, "K=2 起真冠军进名额，交给同进程实测定名次。", 9.8, INK))
    b.append(text(724, 304, "recall@K 才是模型的 KPI，不是 precision@1。", 10, INK, "middle", True))

    # ---- 右中：搜索时间账 ----
    b.append(text(724, 340, "搜索时间账：谁的实测次数少", 12, INK, "middle", True))
    bw, bx = 300, 600
    b.append(text(585, 362, "D108 全测", 9.8, INK, "end"))
    b.append(hand_rect(bx, 352, bw, 22, RED, 0.5, INK, 1.3))
    b.append(text(bx + bw + 10, 367, "68.6 s（98 筛选+12 决赛）", 9.8, INK, "start"))
    b.append(text(585, 392, "D110 引导", 9.8, INK, "end"))
    w2 = bw * 20.0 / 68.6
    b.append(hand_rect(bx, 382, w2, 22, GREEN, 0.6, INK, 1.3))
    b.append(text(bx + w2 + 10, 397, "20.0 s（27 次实测）→ 提速 3.4×", 9.8, INK, "start", True))

    # ---- 底：引导搜索 + 漂移 A/B ----
    b.append(hand_line(52, 430, 928, 431, BORDER, 2))
    card(b, 60, 442, 420, 118, "模型引导搜索（本次运行，3 shape）",
         ["冠军 3/3 与 D108 全测同配置（kij 全胜）",
          "S1: 15.74 ms · S2: 50.95 ms · S3: 31.70 ms",
          "实测候选 27 个 vs 全测基线 110 个槽位",
          "纪律不变：每个被实测的候选都过正确性门（3+7 / 3+21）"],
         GREEN, 10.5, 9.4, 0.42)
    card(b, 520, 442, 420, 118, "漂移 A/B 复核（同进程交错 3 回合，drift-a-b.txt）",
         ["当下进程：kij 15.65 vs ikj 16.67 ms（kij 快 6.5%）",
          "D108 记录：kij 15.80 vs ikj 17.07 ms（kij 快 8.0%）→ 次序未变",
          "近对预测只差 0.4%，实测会随机器状态漂移（D107: ~8.6%）",
          "冠军分歧时：以同进程 A/B 为准，不把两个进程放进一张排名表"],
         BLUE, 10.5, 9.4, 0.42)
    save("03-results.svg", b)


def main():
    print("生成第 110 天的 3 张 sketch 风 SVG：")
    fig1()
    fig2()
    fig3()
    print("完成。")


if __name__ == "__main__":
    main()
