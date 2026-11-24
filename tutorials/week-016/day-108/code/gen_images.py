#!/usr/bin/env python3
"""生成第 108 天的 3 张手绘 sketch 风 SVG 技术图（Excalidraw-like）。

风格约定：白板涂鸦感——线条用带抖动的贝塞尔手绘路径、马克笔笔触、
3～4 种柔和强调色（橙/蓝/绿/红）＋米白背景、简单几何形状、手写感字体。
所有数字来自 tune.py 真实运行结果（code/outputs/，2026-11-13 最终一轮：
results.jsonl 110 条 / tune-summary.json / search-cost.txt / tune-table.txt /
stability.txt / poison-timing.txt）。固定随机种子，保证图可复现。
"""

from __future__ import annotations

import math
import os
import random

random.seed(108)

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
W, H = 980, 640


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
    d = f"M {x1 + jit():.1f},{y1 + jit():.1f} Q {mx:.1f},{my:.1f} {x2 + jit():.1f},{y2 + jit():.1f}"
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


def text(x, y, s, size=13, fill=INK, anchor="middle", bold=False):
    import xml.sax.saxutils as su
    s = su.escape(s)
    wt = ' font-weight="bold"' if bold else ""
    return (f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" '
            f'text-anchor="{anchor}"{wt}>{s}</text>')


def frame(title):
    return [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
            f'font-family="{FONT}">',
            hand_rect(4, 4, W - 8, H - 8, BG, 1.0, BORDER, 2),
            text(W / 2, 36, title, 20, INK, "middle", True)]


def save(name, body):
    out = os.path.join(os.path.dirname(__file__), "..", "images", name)
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(body) + "\n</svg>\n")
    print(f"  已生成 images/{name}")


def card(b, x, y, w, h, title, lines, fill, tsize=11.5, lsize=10, opacity=0.4):
    b.append(hand_rect(x, y, w, h, fill, opacity, INK, 1.6))
    b.append(text(x + w / 2, y + 20, title, tsize, INK, "middle", True))
    for i, ln in enumerate(lines):
        b.append(text(x + w / 2, y + 40 + i * 17, ln, lsize, INK, "middle"))


# ======================= 图 1：全局定位图 =======================

def fig1():
    b = frame("第 108 天定位：Auto-tuning v0.1——候选生成与统一测量第一次接成自动循环")
    b.append(hand_line(300, 46, 680, 47, ORANGE, 3))

    # ---- 上排：调优主线 ----
    b.append(text(56, 70, "调优主线", 12.5, INK, "start", True))
    steps = [("Tiling·展开", "D92~96"), ("候选生成", "D106"),
             ("统一 Benchmark", "D107"), ("Auto-tuning v0.1", "D108 今天"),
             ("GFLOPS·Roofline", "D109"), ("Cost Model 预剪", "D110")]
    for i, (nm, day) in enumerate(steps):
        x = 56 + i * 154
        hot = day == "D108 今天"
        b.append(hand_rect(x, 78 if hot else 82, 140, 56 if hot else 50,
                           ORANGE if hot else BG, 0.85 if hot else 1.0,
                           INK, 2.2 if hot else 1.4))
        b.append(text(x + 70, 101, nm, 11, INK, "middle", True))
        b.append(text(x + 70, 121 if hot else 119, day, 10, RED if hot else MUTED))
        if i < 5:
            b.append(arrow(x + 142, 106, x + 152, 106, MUTED, 1.6))
    b.append(text(490, 152, "D106 生成候选、D107 测量候选；今天把它们接成整机——下游拿今天的记录接着算", 10.5, MUTED))

    # ---- 中排：主循环 ----
    b.append(text(56, 182, "v0.1 主循环（对每个 shape 依次：S1 64³ → S2 96³ → S3 90×96×64）", 12.5, INK, "start", True))
    b.append(hand_rect(44, 192, 892, 210, BG, 0.0, MUTED, 1.6, dash="7 5"))
    stages = [("① 定空间", "98 槽/shape", "tile×顺序×U"),
              ("② 编译", "mini Lowering", "缓存命中 36 次"),
              ("③ 正确性门", "投毒 2 条被拦", "→ 死因台账"),
              ("④ 筛选测量", "3+7 轻协议", "边测边写 JSONL"),
              ("⑤ 排名", "top-3", "∪ 缺省对照"),
              ("⑥ 决赛复测", "恢复 3+21", "→ 冠军表")]
    for i, (t1, t2, t3) in enumerate(stages):
        x = 58 + i * 147
        b.append(hand_rect(x, 206, 130, 72, [BLUE, BLUE, RED, GREEN, GREEN, ORANGE][i],
                           0.38, INK, 1.7))
        b.append(text(x + 65, 227, t1, 11, INK, "middle", True))
        b.append(text(x + 65, 245, t2, 9.5, INK))
        b.append(text(x + 65, 262, t3, 9.5, MUTED))
        if i < 5:
            b.append(arrow(x + 132, 242, x + 145, 242, MUTED, 1.6))
    card(b, 58, 292, 280, 96, "断点续跑（三道闸门之二）",
         ["results.jsonl 追加式落盘，每条 flush",
          "part1 --limit 28 测 28 条收工",
          "part2 跳过 28 条，续测 82 条到终点",
          "续跑键 = (shape, kernel, stage)"], BLUE, 11, 9.5)
    card(b, 354, 292, 280, 96, "被拒台账（fail-visible）",
         ["no-tail 投毒 ×2：max_abs_err=10.07",
          "stats=null、samples=null：不计时",
          "单独计时证明：错误版快 2.7%~7.3%",
          "没有门的排名表会把它当黑马"], RED, 11, 9.5)
    card(b, 650, 292, 274, 96, "同协议可比（D107 纪律）",
         ["决赛名单 = 筛选 top-3 ∪ 缺省配置",
          "缺省 32³ ijk U=1 每 shape 都在场",
          "冠军 vs 缺省：同进程、同 3+21 协议",
          "决赛 1~2 名差距 7.4%~8.0% 成立"], GREEN, 11, 9.5)

    # ---- 下排：输入输出账 ----
    b.append(text(56, 438, "今天的输入 → 实际落盘的输出", 12.5, INK, "start", True))
    card(b, 56, 450, 240, 160, "输入",
         ["3 个 shape，C=A·B+bias，fp32", "seed=42（固定输入）",
          "候选槽 98 个", "  = 规则 96 + 投毒 2",
          "tile：{32,64} cube + 单 tile", "顺序 6 种；U∈{1,4}",
          "筛选 3+7 / 决赛 3+21"], GRAYC, 12, 9.8, 0.7)
    b.append(arrow(300, 530, 336, 530, INK, 2.2))
    card(b, 340, 450, 200, 160, "results.jsonl · 110 条",
         ["98 筛选 + 12 决赛",
          "schema d108.tune-result/1",
          "= d107 字段 + tune 块",
          "（shape/stage/compile_ms）",
          "每条自带 env+protocol",
          "原始样本全落盘"], BLUE, 11, 9.5)
    card(b, 552, 450, 200, 160, "每 shape 冠军表",
         ["S1 64³ kij U=1   15.80 ms",
          "S2 96³ kij U=1   51.53 ms",
          "S3 90×96×64 kij U=1  32.06",
          "缺省 32³ ijk U=1 慢 17~24%",
          "被拒台账 2 条随表交付",
          "（决赛协议 3/21 中位数）"], GREEN, 11, 9.5)
    card(b, 764, 450, 180, 160, "搜索成本账 68.7 s",
         ["编译 22.9 ms（74 次）",
          "筛选测量 57.1 s",
          "决赛测量 11.5 s",
          "内核调用 1,358 次",
          "回本 N≈2,377~2,720 次",
          "外推全空间 ≈13 天"], ORANGE, 11, 9.5)
    b.append(text(490, 626, "所有数字来自 outputs/ 的真实运行（2026-11-13，Python 3.11.4 CPython，Linux aarch64）", 10, MUTED))
    save("01-overview.svg", b)


# ======================= 图 2：三种时间机制图 =======================

def fig2():
    b = frame("v0.1 循环里，三种时间各在哪里付（数字全部实测）")
    b.append(hand_line(280, 46, 700, 47, ORANGE, 3))

    # ---- 左半：一个候选的时间线 ----
    b.append(text(60, 76, "一个候选过循环（S2·96³ 为例）", 12.5, INK, "start", True))
    boxes = [("编译", "0.31 ms", "一次性", BLUE),
             ("门", "1 次调用", "逐位比对", RED),
             ("预热 ×3", "丢弃", "烧冷启动", GREEN),
             ("筛选计时 ×7", "3+7 轻协议", "median 排名", GREEN)]
    for i, (t1, t2, t3, c) in enumerate(boxes):
        x = 52 + i * 122
        b.append(hand_rect(x, 90, 108, 66, c, 0.4, INK, 1.7))
        b.append(text(x + 54, 111, t1, 11, INK, "middle", True))
        b.append(text(x + 54, 128, t2, 9.5, INK))
        b.append(text(x + 54, 145, t3, 9, MUTED))
        if i < 3:
            b.append(arrow(x + 110, 123, x + 120, 123, MUTED, 1.6))
    b.append(arrow(174, 158, 174, 196, RED, 1.8))
    b.append(hand_rect(96, 198, 156, 58, RED, 0.45, INK, 1.6))
    b.append(text(174, 219, "被拒 → 死因台账", 10.5, INK, "middle", True))
    b.append(text(174, 235, "0 次计时（投毒走这条路）", 9.5, INK))
    b.append(text(174, 249, "错误版快 2.7~7.3% 也不许进表", 9, MUTED))

    b.append(hand_line(46, 272, 520, 273, MUTED, 1.2, dash="5 5"))
    b.append(text(60, 294, "进决赛的候选（top-3 ∪ 缺省）", 12.5, INK, "start", True))
    fboxes = [("复用编译缓存", "0 ms（命中）", BLUE),
              ("门+预热×3", "同一流水线", GREEN),
              ("决赛计时 ×21", "恢复 D107 全协议", ORANGE),
              ("决赛排名", "冠军 = median 最小", ORANGE)]
    for i, (t1, t2, c) in enumerate(fboxes):
        x = 52 + i * 122
        b.append(hand_rect(x, 306, 108, 60, c, 0.4, INK, 1.7))
        b.append(text(x + 54, 326, t1, 10.5, INK, "middle", True))
        b.append(text(x + 54, 344, t2, 9.5, INK))
        b.append(text(x + 54, 358, "决赛 15.8~65.1 ms/次", 9, MUTED) if i == 2 else "")
        if i < 3:
            b.append(arrow(x + 110, 336, x + 120, 336, MUTED, 1.6))
    b.append(text(286, 388, "筛选粗：把 90+ 个进不了决赛的候选挡在 3+7 的便宜协议后面；决赛精：只在同协议下宣布冠军", 9.5, MUTED))

    # ---- 右半：三种时间的账本 ----
    b.append(text(560, 76, "三种时间的账本（今天的核心概念）", 12.5, INK, "start", True))
    card(b, 548, 90, 400, 118, "编译时间 compile time（一次性/候选）",
         ["实测均值 0.31 ms/候选 × 74 次 = 22.9 ms",
          "缓存命中 36 次：同一配置跨 shape、跨段不重编",
          "真实 MLIR/LLVM 后端 0.1~10 s/候选：Σ编译 = 74 s",
          "直接反超 Σ测量——循环结构不变，账全变"], BLUE, 11.5, 9.8)
    card(b, 548, 218, 400, 100, "执行时间 execution time（每次调用都付）",
         ["排名唯一依据：median of 21（D107 口径）",
          "决赛中位数 15.8~65.1 ms/次",
          "S2 冠军 51.53 ms；缺省 65.12 ms；每次省 13.59 ms"], GREEN, 11.5, 9.8)
    card(b, 548, 328, 400, 108, "搜索成本 search cost（整场一次性）",
         ["68.7 s = Σ编译 0.02 s + 筛选 57.1 s + 决赛 11.5 s + 记账",
          "内核调用 1,358 次（逐条记录数 = 分段记账数）",
          "按 (shape, 机器, 环境) 一次性；换 shape/换机器要重付"], ORANGE, 11.5, 9.8)

    # ---- 底部：摊销账 ----
    b.append(hand_rect(52, 452, 896, 92, GRAYC, 0.7, INK, 1.8))
    b.append(text(500, 476, "摊销账：N_break-even = 搜索成本分摊 ÷ 每次省下的执行时间", 12, INK, "middle", True))
    b.append(text(240, 500, "S1：8.0 s ÷ 3.28 ms ≈ 2,433 次", 10.5, INK))
    b.append(text(500, 500, "S2：37.0 s ÷ 13.59 ms ≈ 2,720 次", 10.5, INK))
    b.append(text(762, 500, "S3：23.7 s ÷ 9.97 ms ≈ 2,377 次", 10.5, INK))
    b.append(text(500, 528, "百万次/天的推理服务几分钟回本；一天一次的脚本永不回本——两种时间不能混着报", 10, RED))
    save("02-mechanism.svg", b)


# ======================= 图 3：实测结果对照图 =======================

def fig3():
    b = frame("实测结果：冠军 vs 缺省 17~24%、排名有效性、投毒被拦")
    b.append(hand_line(300, 46, 680, 47, ORANGE, 3))

    # ---- 左半：缺省 vs 冠军 条形图（横向，手绘条） ----
    b.append(text(56, 78, "缺省配置 vs 调优冠军（决赛协议 3/21 中位数，ms）", 12, INK, "start", True))
    data = [("S1 64×64×64", 19.08, 15.80, "64³ kij U=1", 17.2),
            ("S2 96×96×96", 65.12, 51.53, "96³ kij U=1", 20.9),
            ("S3 90×96×64", 42.02, 32.06, "90×96×64 kij U=1", 23.7)]
    x0, full, unit = 176, 330, 330 / 65.12
    for i, (shape, d, w, name, gap) in enumerate(data):
        yc = 112 + i * 118
        b.append(text(60, yc + 16, shape, 10.5, INK, "start", True))
        # 缺省（灰蓝）
        b.append(hand_rect(x0, yc, d * unit, 30, BLUE, 0.55, INK, 1.5))
        b.append(text(x0 + d * unit + 8, yc + 20, f"缺省 {d:.2f}", 10, MUTED, "start"))
        # 冠军（绿）
        b.append(hand_rect(x0, yc + 40, w * unit, 30, GREEN, 0.75, INK, 1.5))
        b.append(text(x0 + w * unit + 8, yc + 60, f"冠军 {name} {w:.2f}", 10, INK, "start"))
        b.append(text(x0 + w * unit + 8, yc + 76, f"快 {gap:.0f}%（省 {d - w:.2f} ms/次）", 9.5, RED, "start"))
    b.append(hand_line(x0, 100, x0, 452, MUTED, 1.2))
    b.append(text(x0, 468, "0 ms", 9.5, MUTED))
    b.append(text(60, 490, "回本调用数：S1 ≈2,433｜S2 ≈2,720｜S3 ≈2,377（搜索成本分摊 ÷ 每次省时）", 10, INK, "start"))

    # ---- 右半：三张结论卡 ----
    card(b, 560, 96, 392, 108, "冠军榜（每 shape 一名，per-shape 是纪律）",
         ["S1  64³ kij U=1              15.80 ms",
          "S2  96³ kij U=1              51.53 ms",
          "S3  90×96×64 kij U=1         32.06 ms",
          "冠军名相似是 CPython 成本模型的巧合（见 README 5.3）"], GREEN, 11.5, 10)
    card(b, 560, 216, 392, 92, "排名有效性（D97 规则自动判）",
         ["决赛第 1~2 名差距 7.36%~8.02%",
          "2×MAD 口径 < 0.2% → 差距远大于波动：成立",
          "同 shape 的筛选/决赛都在同一次进程内完成"], BLUE, 11.5, 10)
    card(b, 560, 320, 392, 128, "被拒台账 2 条（门先行的现场证据）",
         ["90×96×64 jki U=4/no-tail：err=10.07 → 不计时",
          "32³ jki U=4/no-tail：err=10.07 → 不计时",
          "绕过门直接计时：55.32/56.06 ms",
          "正确双胞胎：56.83/60.45 ms（错误版快 2.7~7.3%）",
          "自动搜索没有肉眼审查，门就是唯一防线"], RED, 11.5, 9.8)

    b.append(hand_rect(52, 522, 900, 84, GRAYC, 0.6, INK, 1.6))
    b.append(text(500, 546, "工程实测两条腿：断点续跑 part1（28 条收工）→ part2（跳过 28 续测 82）；", 10.5, INK, "middle", True))
    b.append(text(500, 568, "k=3/5 重算（读落盘样本，内核一次不跑）：冠军不翻、top-3 不变，中游摆 ≤3 位——", 10.5, INK))
    b.append(text(500, 588, "筛选 3+7 的保险与成本（省 36%@k=3）都在账上，口径随记录可重算", 10.5, INK))
    save("03-results.svg", b)


if __name__ == "__main__":
    fig1()
    fig2()
    fig3()
