#!/usr/bin/env python3
"""生成第 106 天的 3 张手绘 sketch 风 SVG 技术图（Excalidraw-like）。

风格约定：白板涂鸦感——线条用带抖动的贝塞尔手绘路径、马克笔笔触、
3～4 种柔和强调色（橙/蓝/绿/红）＋米白背景、简单几何形状、手写感字体。
所有数字来自 search_space.py 的真实运行结果（code/outputs/）。
固定随机种子，保证图可复现。
"""

from __future__ import annotations

import math
import os
import random

random.seed(106)

BG = "#FDFBF6"
BORDER = "#E7DFCE"
INK = "#3B3B3B"
MUTED = "#6b6257"
ORANGE = "#E8A87C"
BLUE = "#A9C4D4"
GREEN = "#9CBF8E"
RED = "#C97B7B"
FONT = "'Comic Sans MS','Kaiti SC','KaiTi','STKaiti',cursive"
W, H = 980, 640


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
    d += "Z"
    return (f'<path d="{d}" stroke="{stroke}" stroke-width="{sw}" '
            f'stroke-linecap="round" stroke-linejoin="round" '
            f'fill="{fill}" fill-opacity="{opacity}"/>')


def hand_line(x1, y1, x2, y2, stroke=INK, sw=1.4, dash=None):
    dd = f' stroke-dasharray="{dash}"' if dash else ""
    mx, my = (x1 + x2) / 2 + jit(2.5), (y1 + y2) / 2 + jit(2.5)
    d = f"M {x1 + jit():.1f},{y1 + jit():.1f} Q {mx:.1f},{my:.1f} {x2 + jit():.1f},{y2 + jit():.1f}"
    return (f'<path d="{d}" stroke="{stroke}" stroke-width="{sw}" '
            f'stroke-linecap="round" fill="none"{dd}/>')


def arrow(x1, y1, x2, y2, stroke=INK, sw=1.8, dash=None):
    dd = f' stroke-dasharray="{dash}"' if dash else ""
    mx, my = (x1 + x2) / 2 + jit(2.0), (y1 + y2) / 2 + jit(2.0)
    ang = math.atan2(y2 - y1, x2 - y1)
    hx, hy = x2 - 9 * math.cos(ang), y2 - 9 * math.sin(ang)
    a1 = (hx + 5 * math.cos(ang + 2.5), hy + 5 * math.sin(ang + 2.5))
    a2 = (hx + 5 * math.cos(ang - 2.5), hy + 5 * math.sin(ang - 2.5))
    d = (f"M {x1 + jit():.1f},{y1 + jit():.1f} Q {mx:.1f},{my:.1f} "
         f"{x2:.1f},{y2:.1f} M {a1[0]:.1f},{a1[1]:.1f} L {x2:.1f},{y2:.1f} "
         f"L {a2[0]:.1f},{a2[1]:.1f}")
    return (f'<path d="{d}" stroke="{stroke}" stroke-width="{sw}" '
            f'stroke-linecap="round" fill="none"{dd}/>')


def text(x, y, s, size=13, fill=INK, anchor="middle", bold=False):
    wt = ' font-weight="bold"' if bold else ""
    return (f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" '
            f'text-anchor="{anchor}"{wt}>{s}</text>')


def frame(title):
    return [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
            f'font-family="{FONT}">',
            hand_rect(4, 4, W - 8, H - 8, BG, 1.0, BORDER, 2),
            text(W / 2, 36, title, 21, INK, "middle", True)]


def save(name, body):
    out = os.path.join(os.path.dirname(__file__), "..", "images", name)
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(body) + "\n</svg>\n")
    print(f"  已生成 images/{name}")


# ======================= 图 1：全局定位图 =======================

def fig1():
    b = frame("第 106 天定位：候选生成器——搜索空间的第一现场")
    b.append(hand_line(330, 47, 650, 48, ORANGE, 3))

    # ---- 上排：编译主线（候选生成插在 Tiling 与资源过滤之间）----
    b.append(text(60, 68, "编译主线", 13, INK, "start", True))
    steps = [("图优化·融合", "D48~56"), ("循环 Lowering", "D85~89"),
             ("Tiling", "D92~96"), ("候选生成", "D106"),
             ("资源过滤", "D104"), ("测量·调优", "D107~110"),
             ("代码生成·验收", "D111")]
    for i, (nm, day) in enumerate(steps):
        x = 60 + i * 132
        hot = day == "D106"
        b.append(hand_rect(x, 76 if hot else 80, 118, 58 if hot else 50,
                           ORANGE if hot else BG, 0.8 if hot else 1.0,
                           INK, 2.2 if hot else 1.4))
        b.append(text(x + 59, 101, nm, 11.5, INK, "middle", True))
        b.append(text(x + 59, 121 if hot else 119, day, 10, MUTED))
        if i < 6:
            b.append(arrow(x + 120, 104, x + 130, 104, MUTED, 1.6))
    b.append(text(490, 150, "今天：候选第一次被系统性地『生产』出来，再交给 D104 的闸门", 10.5, RED))

    # ---- 中排：第 16 周路线 ----
    b.append(text(60, 176, "第 16 周", 13, INK, "start", True))
    week = [("D106", "定义搜索空间"), ("D107", "Benchmark 工具"), ("D108", "Auto-tuning"),
            ("D109", "GFLOPS"), ("D110", "Cost Model"), ("D111", "集成验收"),
            ("D112", "周复盘")]
    for i, (day, topic) in enumerate(week):
        x = 60 + i * 132
        hot = day == "D106"
        b.append(hand_rect(x, 186 if hot else 190, 118, 56 if hot else 48,
                           GREEN if hot else BG, 0.7 if hot else 1.0,
                           INK, 2.2 if hot else 1.4))
        b.append(text(x + 59, 210, day, 13, INK, "middle", True))
        b.append(text(x + 59, 230 if hot else 228, topic, 10, INK if hot else MUTED))
        if i < 6:
            b.append(arrow(x + 120, 216, x + 130, 216, MUTED, 1.6))

    # ---- 下排：生成器详图（横向管线）----
    b.append(text(60, 262, "生成器详图：D105 留下的问题——候选从哪来、怎么裁", 13, INK, "start", True))

    # 左：naive（被否决的方案）
    b.append(hand_rect(46, 278, 150, 96, "#EDE7DA", 0.9, MUTED, 1.4))
    b.append(text(121, 300, "naive 枚举", 12, MUTED, "middle", True))
    b.append(text(121, 320, "1..512 全试", 10, MUTED))
    b.append(text(121, 338, "25,769,803,776", 10.5, MUTED))
    b.append(hand_line(70, 350, 172, 349, RED, 2.4))
    b.append(text(121, 366, "不配被枚举", 10, RED))

    b.append(arrow(198, 326, 224, 326, INK, 2.0))

    # 轴卡：四根轴的值域
    b.append(hand_rect(228, 272, 250, 190, BLUE, 0.3, INK, 1.8))
    b.append(text(353, 294, "四根轴 × 值域剪枝", 12.5, INK, "middle", True))
    rows = [("tile tm/tn/tk", "整除 512 ∩ 8 的倍数", "7 值/维"),
            ("order", "D92：排名随容量翻转", "6 种全留"),
            ("unroll", "D96：量到 8，16 探上界", "1/2/4/8/16"),
            ("buffering", "D103：double 换重叠", "single/double")]
    for i, (a1, a2, a3) in enumerate(rows):
        y = 316 + i * 30
        b.append(text(240, y, a1, 10.5, INK, "start", True))
        b.append(text(322, y, a2, 9.5, MUTED, "start"))
        b.append(text(472, y, a3, 9.5, INK, "end"))
    b.append(text(353, 448, "值域原始空间 20,580 = 7×7×7×6×5×2", 11, INK, "middle", True))

    b.append(arrow(480, 366, 506, 366, INK, 2.0))

    # 中：两道裁剪
    b.append(hand_rect(510, 272, 210, 88, GREEN, 0.3, INK, 1.8))
    b.append(text(615, 294, "跨轴参数约束（便宜）", 11.5, INK, "middle", True))
    b.append(text(615, 314, "U ≤ 最内层圈数", 10.5, INK))
    b.append(text(615, 332, "剪掉 588 个死代码", 10.5, INK))
    b.append(text(615, 348, "剩 19,992", 10, MUTED))
    b.append(arrow(615, 362, 615, 380, INK, 2.0))
    b.append(hand_rect(510, 384, 210, 78, ORANGE, 0.4, INK, 1.8))
    b.append(text(615, 406, "D104 资源闸门（贵）", 11.5, INK, "middle", True))
    b.append(text(615, 426, "五项家当 ≤ 256 KiB", 10.5, INK))
    b.append(text(615, 444, "剪掉 7,022 个超预算", 10.5, INK))
    b.append(text(615, 458, "记账规则一行不改", 9.5, MUTED))

    b.append(arrow(722, 423, 748, 423, INK, 2.0))

    # 右：幸存者
    b.append(hand_rect(752, 286, 182, 148, GREEN, 0.45, INK, 2.2))
    b.append(text(843, 312, "幸存候选", 13, INK, "middle", True))
    b.append(text(843, 344, "12,970 个", 20, INK, "middle", True))
    b.append(text(843, 368, "242 种 tile", 10.5, INK))
    b.append(text(843, 386, "每个都配得上被测一次", 9.5, MUTED))
    b.append(text(843, 404, "↓ 交给 D107 定协议", 9.5, MUTED))
    b.append(text(843, 420, "↓ D108 全测 / D110 只测前 K", 9.5, MUTED))

    b.append(text(490, 470, "分工边界：生成器只管『喂』，参数约束和 D104 闸门只管『裁』，排序是 D110 的事，测量是 D107/D108 的事", 10, MUTED))
    b.append(text(490, 494, "缩减比：naive → 幸存者 = 1,986,878 倍", 12, RED, "middle", True))

    # 底部一句话
    b.append(hand_rect(150, 512, 680, 56, "#F5EFE0", 1.0, BORDER, 1.4))
    b.append(text(490, 536, "昨天（D105）说：『候选从哪来、怎么裁，明天正式开工』", 11, INK))
    b.append(text(490, 556, "今天的答案：从问题的因数结构里来，用三层漏斗裁——257 亿剪成 12,970", 11, INK, "middle", True))

    save("01-overview.svg", b)


# ======================= 图 2：三层漏斗机制图 =======================

def fig2():
    b = frame("搜索空间三层漏斗：值域剪枝 → 跨轴参数约束 → D104 资源闸门")
    b.append(hand_line(330, 47, 650, 48, ORANGE, 3))

    # ---- 顶部：naive 反面教材 ----
    b.append(hand_rect(46, 62, 546, 96, "#EDE7DA", 0.9, MUTED, 1.4))
    b.append(text(70, 86, "naive 枚举（反面教材）", 12.5, MUTED, "start", True))
    b.append(text(70, 110, "25,769,803,776 = 512³ × 6 × 16 × 2", 13, MUTED, "start", True))
    b.append(text(70, 132, "随便抓一个必然踩雷：", 10, MUTED, "start"))
    b.append(text(230, 132, "奇数维 87.5% · 非整除 100% · 不满对齐 99.8% · 死展开 1.5%", 10, RED, "start"))
    b.append(text(628, 86, "它们没有错，", 11, MUTED, "start"))
    b.append(text(628, 104, "只是不配消耗一次", 11, MUTED, "start"))
    b.append(text(628, 122, "编译 ＋ 一次测量", 11, MUTED, "start"))

    # ---- 漏斗主体（左列，四层）----
    fx, fw = 120, 440  # 漏斗中轴与顶宽
    levels = [
        (170, fw, "值域剪枝（生成之前就不造傻值）", "20,580", BLUE,
         "tile 池 {8,16,32,64,128,256,512}：整除 512 ∩ 8 的倍数"),
        (276, 330, "跨轴参数约束（便宜，先跑）", "19,992", GREEN,
         "U ≤ 最内层圈数：−588 个死代码"),
        (382, 230, "D104 资源闸门（贵，后跑）", "12,970", ORANGE,
         "五项家当 ≤ 262,144 B：−7,022 个超预算"),
    ]
    for i, (cy, w, label, num, color, note) in enumerate(levels):
        x = fx - w // 2
        b.append(hand_rect(x, cy, w, 74, color, 0.45, INK, 1.8))
        b.append(text(fx, cy + 22, label, 11.5, INK, "middle", True))
        b.append(text(fx, cy + 48, num, 19, INK, "middle", True))
        if i < 2:
            nxt = levels[i + 1]
            b.append(arrow(fx, cy + 76, fx, nxt[0] - 2, INK, 2.2))
            dn = int(levels[i][3].replace(",", "")) - int(nxt[3].replace(",", ""))
            b.append(text(fx + 66, cy + 96, f"−{dn:,}", 11, RED, "middle", True))
    b.append(text(fx, 476, "幸存者：12,970 个候选，242 种 tile", 11.5, INK, "middle", True))
    b.append(text(fx, 496, "缩减比 1,986,878 倍", 11, RED, "middle", True))

    # ---- 右列：每层剪掉的实例 ----
    b.append(text(740, 66, "每层剪掉谁（真实例子）", 12.5, INK, "middle", True))
    # 值域层
    b.append(hand_rect(600, 78, 334, 60, BLUE, 0.3, INK, 1.5))
    b.append(text(767, 98, "值域层拦在门外：tm=511", 10.5, INK, "middle", True))
    b.append(text(767, 116, "奇数 → 三项 padding 税（D104 对齐扫描）", 9.5, MUTED))
    b.append(text(767, 132, "511 ∤ 512 → 凭空多一套尾部（D95）", 9.5, MUTED))
    # 参数层
    b.append(hand_rect(600, 188, 334, 74, GREEN, 0.3, INK, 1.5))
    b.append(text(767, 208, "参数层：✗ 8³ ijk U=16", 10.5, INK, "middle", True))
    b.append(text(767, 226, "U=16 > 最内层 k 的圈数 8", 9.5, MUTED))
    b.append(text(767, 244, "主循环 0 圈 + 尾部循环干全部活", 9.5, MUTED))
    b.append(text(767, 258, "= 比不展开还多背一份代码体积", 9.5, MUTED))
    # 资源层
    b.append(hand_rect(600, 312, 334, 96, ORANGE, 0.3, INK, 1.5))
    b.append(text(767, 332, "资源层：✗ 8×64×512 ijk U=1 double", 10.5, INK, "middle", True))
    b.append(text(767, 352, "A 16,384×2 + B 131,072×2 + C 2,048", 9.5, MUTED))
    b.append(text(767, 368, "+ bias 256 = 297,216 B 超 35,072 B", 9.5, MUTED))
    b.append(text(767, 392, "对照 ✓ 128×256×64 single = 230,400 B", 10, "#5a7d4e"))
    b.append(text(767, 406, "（幸存者里住得最挤，利用率 87.9%）", 9.5, MUTED))

    # ---- 底部：幸存者内部结构 ----
    b.append(hand_rect(46, 516, 888, 96, "#F5EFE0", 1.0, BORDER, 1.4))
    b.append(text(490, 538, "幸存者的内部结构（为什么差 4 个：顺序不改空间账，但参数约束按『最内层是谁』剪，而账本对三根维不对称——A/B 才 ×2、bias 只住 tn）",
                  9.5, MUTED))
    b.append(text(70, 562, "按顺序：ijk=2159  jik=2159（k 结尾各少 4）  ikj=jki=kij=kji=2163", 10.5, INK, "start"))
    b.append(text(70, 584, "按缓冲：single=7002  double=5968（×2 流入项先送命）", 10.5, INK, "start"))
    b.append(text(70, 604, "tile=128³：只剩 single 的 30 个；double 的 30 个全灭（328,192 B）", 10.5, INK, "start"))
    b.append(text(920, 584, "D107 的协议在等它们", 10, RED, "end", True))

    save("02-mechanism.svg", b)


# ======================= 图 3：shape 对照 + 预算扫描 =======================

def fig3():
    b = frame("同一个生成器，两种 shape 命运：512 整除模式，516 尾部模式")
    b.append(hand_line(330, 47, 650, 48, ORANGE, 3))

    # ---- 左板：512·div ----
    b.append(hand_rect(40, 60, 442, 330, BG, 1.0, INK, 1.8))
    b.append(text(261, 84, "512³ · div 模式", 13, INK, "middle", True))
    b.append(text(261, 104, "512 = 2⁹：因子全是 2 的幂", 10.5, MUTED))
    b.append(hand_rect(64, 116, 394, 44, BLUE, 0.4, INK, 1.5))
    b.append(text(261, 136, "tile 池（每维 7 个）", 10.5, INK, "middle", True))
    b.append(text(261, 153, "{8, 16, 32, 64, 128, 256, 512}", 11, INK, "middle", True))
    rows = [("值域原始", "20,580"), ("参数剪 588（死展开）", "19,992"),
            ("资源剪 7,022（超预算）", "12,970")]
    for i, (k, v) in enumerate(rows):
        y = 180 + i * 40
        b.append(hand_rect(84, y, 354, 32, GREEN if i == 2 else BG, 0.5 if i == 2 else 1.0,
                           INK, 1.6 if i == 2 else 1.3))
        b.append(text(96, y + 21, k, 10.5, INK, "start"))
        b.append(text(428, y + 21, v, 12, INK if i == 2 else MUTED, "end", True))
        if i < 2:
            b.append(arrow(261, y + 34, 261, y + 38, MUTED, 1.4))
    b.append(text(261, 316, "幸存 12,970 个配置 · 242 种 tile", 12, INK, "middle", True))
    b.append(text(261, 336, "128³ 只剩 single；64³ 全配置 60 个都在", 10, MUTED))
    b.append(text(261, 356, "D97 冠军 128³·ikj 留在名单（single 版；double 被 D104 拦）", 10, GREEN))

    # ---- 右板：516·tail ----
    b.append(hand_rect(498, 60, 442, 330, BG, 1.0, INK, 1.8))
    b.append(text(719, 84, "516³ · 先撞空集警报", 13, INK, "middle", True))
    b.append(text(719, 104, "516 = 2²·3·43：8 的倍数里没有它的因子", 10.5, MUTED))
    b.append(hand_rect(522, 116, 394, 44, RED, 0.35, RED, 1.8))
    b.append(text(719, 136, "div 模式 tile 池 = 空 ∅", 10.5, RED, "middle", True))
    b.append(text(719, 153, "值域剪过头不是省钱，是断粮", 9.5, RED, "middle"))
    b.append(arrow(719, 164, 719, 178, INK, 2.0))
    b.append(text(719, 192, "逃生门：降级 tail 模式（D95 尾部机制接住）", 10, INK, "middle", True))
    b.append(hand_rect(522, 200, 394, 34, BLUE, 0.4, INK, 1.5))
    b.append(text(719, 222, "tile 池 {32, 64, 96, 128, 160, 256}（6 个/维）", 10.5, INK, "middle", True))
    rows = [("值域原始 216 tile · 全带尾部", "12,960"), ("参数剪 0（最小 32 ≥ 最大 U 16）", "12,960"),
            ("资源剪 4,620（超预算）", "8,340")]
    for i, (k, v) in enumerate(rows):
        y = 248 + i * 36
        b.append(hand_rect(542, y, 354, 28, GREEN if i == 2 else BG, 0.5 if i == 2 else 1.0,
                           INK, 1.6 if i == 2 else 1.3))
        b.append(text(554, y + 19, k, 9.5, INK, "start"))
        b.append(text(886, y + 19, v, 11, INK if i == 2 else MUTED, "end", True))
    b.append(text(719, 366, "老朋友回来了：96³ = 184,704 B ✓ · 160×128×64 = 229,888 B ✓", 10, GREEN))
    b.append(text(719, 384, "D97 冠军翻转（ikj-64）的现场就在这类带尾 shape 上", 9.5, MUTED))

    # ---- 底部：预算扫描 ----
    b.append(text(60, 416, "预算扫描（512³ · div）：预算决定 tile 上限，不是直觉", 12, INK, "start", True))
    data = [(524288, 15570), (262144, 12970), (196608, 12130), (131072, 9872), (65536, 7124)]
    x0, y0, bw, gap = 90, 520, 96, 52
    for i, (budget, n) in enumerate(data):
        x = x0 + i * (bw + gap)
        h = 78 * n / 15570
        hot = budget == 262144
        b.append(hand_rect(x, y0 - h, bw, h, ORANGE if hot else BLUE, 0.6 if hot else 0.5,
                           INK, 1.8 if hot else 1.4))
        b.append(text(x + bw / 2, y0 - h - 8, f"{n:,}", 11, INK, "middle", True))
        b.append(text(x + bw / 2, y0 + 18, f"{budget // 1024} KiB", 10, INK if hot else MUTED))
    b.append(hand_line(70, y0 + 2, 930, y0 + 1, MUTED, 1.6))
    b.append(text(60, 560, "观察点：预算从 512K 砍到 64K（1/8），幸存者只砍掉 54%——", 10, MUTED, "start"))
    b.append(text(60, 578, "顺序 / 展开 / 缓冲的搭配数几乎不动；先死的永远是『住不下』，不是『跑得慢』", 10, MUTED, "start"))
    b.append(text(920, 416, "数字全部来自 outputs/budget-sweep.txt", 9.5, MUTED, "end"))

    save("03-comparison.svg", b)


if __name__ == "__main__":
    print("生成第 106 天手绘图：")
    fig1()
    fig2()
    fig3()
