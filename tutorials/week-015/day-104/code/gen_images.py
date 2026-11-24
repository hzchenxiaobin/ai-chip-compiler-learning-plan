#!/usr/bin/env python3
"""生成第 104 天的 3 张手绘 sketch 风 SVG 技术图（Excalidraw-like）。

风格约定：白板涂鸦感——线条用带抖动的贝塞尔手绘路径、马克笔笔触、
3～4 种柔和强调色（橙/蓝/绿/红）＋米白背景、简单几何形状、手写感字体。
所有数字来自 resource_filter.py 的真实运行结果（code/outputs/）。
固定随机种子，保证图可复现。
"""

from __future__ import annotations

import math
import os
import random

random.seed(104)

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
        f.write("\n".join(body) + "\n")
    print(f"  已生成 images/{name}")


# ======================= 图 1：全局定位图 =======================
def fig1():
    b = frame("第 104 天定位：资源过滤器——站在代码生成之前的闸门")
    b.append(hand_line(330, 47, 650, 48, ORANGE, 3))

    # ---- 上排：编译主线 ----
    b.append(text(70, 72, "编译主线", 13, INK, "start", True))
    steps = [("图优化·融合", "D48~56"), ("循环 Lowering", "D85~89"),
             ("Tiling", "D92~96"), ("资源过滤", "D104"),
             ("代码生成", "D111"), ("搜索·调优", "D106+")]
    for i, (nm, day) in enumerate(steps):
        x = 150 + i * 138
        hot = day == "D104"
        b.append(hand_rect(x, 82 if hot else 86, 118, 56 if hot else 48,
                           ORANGE if hot else BG, 0.8 if hot else 1.0,
                           INK, 2.2 if hot else 1.4))
        b.append(text(x + 59, 106 if hot else 106, nm, 11.5, INK, "middle", True))
        b.append(text(x + 59, 126 if hot else 122, day, 10, MUTED))
        if i < 5:
            b.append(arrow(x + 120, 108, x + 136, 108, MUTED, 1.6))
    b.append(text(611, 150, "今天的位置：候选在变成代码之前过闸", 10.5, RED))

    # ---- 中排：本周路线 ----
    b.append(text(70, 176, "本周路线", 13, INK, "start", True))
    week = [("D99", "活跃区间表"), ("D100", "片外规划"), ("D101", "片上空间账"),
            ("D102", "时间账·依赖"), ("D103", "双缓冲·重叠"), ("D104", "资源过滤")]
    for i, (day, topic) in enumerate(week):
        x = 150 + i * 138
        hot = day == "D104"
        b.append(hand_rect(x, 186 if hot else 190, 118, 54 if hot else 46,
                           GREEN if hot else BG, 0.7 if hot else 1.0,
                           INK, 2.2 if hot else 1.4))
        b.append(text(x + 59, 209, day, 13, INK, "middle", True))
        b.append(text(x + 59, 228, topic, 10.5, INK if hot else MUTED))
        if i < 5:
            b.append(arrow(x + 120, 212, x + 136, 212, MUTED, 1.6))
    b.append(hand_line(208, 250, 498, 251, GREEN, 2.2))
    b.append(text(353, 264, "空间轴（D99~101）", 10, MUTED))
    b.append(hand_line(528, 250, 742, 251, RED, 2.2))
    b.append(text(635, 264, "时间轴（D102~103）", 10, MUTED))
    b.append(text(798, 264, "两本账在 D104 合流", 10.5, RED, "start", True))

    # ---- 下排：闸门详图 ----
    # 左：候选来源
    b.append(hand_rect(46, 292, 180, 60, BLUE, 0.3, INK, 1.5))
    b.append(text(136, 315, "候选从哪来", 12, INK, "middle", True))
    b.append(text(136, 336, "LoopOptions（D93）／搜索空间（D106）", 9.5, MUTED))
    b.append(arrow(136, 354, 136, 386, MUTED, 1.6))
    b.append(hand_rect(46, 390, 180, 128, BG, 1.0, INK, 1.6))
    b.append(text(136, 412, "12 个候选（本文实验）", 11, INK, "middle", True))
    for i, nm in enumerate(["32³ / 64³ / 96³", "128³ fp32·single",
                            "128³ fp32·double ←", "128³ bf16 / int8",
                            "160×128×64", "256³ fp32·single ←"]):
        b.append(text(64, 430 + i * 16, nm, 9.5,
                      RED if "←" in nm else INK, "start"))
    b.append(text(136, 548, "候选是数据：构造不校验", 9.5, MUTED))
    b.append(text(136, 564, "非法值也照样喂进来", 9.5, MUTED))

    # 中：过滤器闸门
    b.append(arrow(230, 450, 292, 450, INK, 2.2))
    b.append(hand_rect(296, 292, 320, 300, ORANGE, 0.35, INK, 2.2))
    b.append(text(456, 320, "ResourceFilter（今天的交付物）", 13.5, INK, "middle", True))
    b.append(hand_rect(316, 338, 280, 56, BG, 1.0, INK, 1.4))
    b.append(text(456, 360, "① 参数校验（O(1)，fail-closed）", 11, INK, "middle", True))
    b.append(text(456, 380, "正整数？已知 dtype？已知缓冲策略？", 10, MUTED))
    b.append(arrow(456, 396, 456, 408, INK, 1.5))
    b.append(hand_rect(316, 410, 280, 56, BG, 1.0, INK, 1.4))
    b.append(text(456, 432, "② 空间估算（D101 五项家当）", 11, INK, "middle", True))
    b.append(text(456, 452, "×2 只加流入项｜align 32｜C 恒 4 B", 10, MUTED))
    b.append(arrow(456, 468, 456, 480, INK, 1.5))
    b.append(hand_rect(316, 482, 280, 56, BG, 1.0, INK, 1.4))
    b.append(text(456, 504, "③ 预算判定：合计 ≤ 262,144 B", 11, INK, "middle", True))
    b.append(text(456, 524, "短路：①挂了②就不跑（可观测）", 10, MUTED))
    b.append(text(456, 570, "只判『能不能跑』，不判『值不值得』（D74 分离）", 10, RED))

    # 右：两种结果
    b.append(arrow(618, 380, 682, 380, INK, 2.2))
    b.append(hand_rect(686, 296, 258, 110, GREEN, 0.3, INK, 1.8))
    b.append(text(815, 322, "✓ 10 个放行", 14, "#4d7c4f", "middle", True))
    b.append(text(815, 346, "走向代码生成（合法候选）", 11, INK))
    b.append(text(815, 370, "纸面最优被拒 ≠ 过滤器有意见，", 9.5, MUTED))
    b.append(text(815, 386, "是预算的意见", 9.5, MUTED))
    b.append(arrow(618, 500, 682, 500, INK, 2.2))
    b.append(hand_rect(686, 418, 258, 164, RED, 0.28, INK, 1.8))
    b.append(text(815, 444, "✗ 2 个拒绝", 14, RED, "middle", True))
    b.append(text(815, 468, "128³ fp32·double  328,192 B", 10.5, INK))
    b.append(text(815, 486, "超 66,048 B（25.2%）", 10, RED))
    b.append(text(815, 508, "256³ fp32·single  787,456 B", 10.5, INK))
    b.append(text(815, 526, "超 525,312 B（300%）", 10, RED))
    b.append(text(815, 552, "诊断+出路，不再走到代码生成", 10, MUTED))
    b.append(text(815, 572, "fail-closed：拒绝即终点", 10, MUTED))

    b.append(text(490, 612, "数字来自 code/outputs/filter-table.txt 的真实运行（12 进 → 10 过 2 拒，预算 256 KiB）",
                  10.5, MUTED))
    save("01-overview.svg", b + ["</svg>"])


# ======================= 图 2：检查链机制图 =======================
def fig2():
    b = frame("过滤器内部：纸面最优 128³ fp32·double 走完一遍检查链")
    b.append(hand_line(310, 47, 670, 48, GREEN, 3))

    # ---- 左：候选卡片 ----
    b.append(hand_rect(44, 88, 210, 240, BLUE, 0.3, INK, 1.8))
    b.append(text(149, 114, "候选卡片", 13.5, INK, "middle", True))
    for i, (k, v) in enumerate([("tm / tn / tk", "128 / 128 / 128"),
                                ("dtype_in", "fp32"),
                                ("buffering", "double"),
                                ("bias", "True"),
                                ("staging", "False")]):
        y = 140 + i * 22
        b.append(text(60, y, k, 10.5, MUTED, "start"))
        b.append(text(244, y, v, 10.5, INK, "end", True))
    b.append(hand_line(60, 246, 238, 247, MUTED, 1.2, "4 4"))
    b.append(text(149, 266, "D97 的 CPU 冠军", 10.5, RED, "middle", True))
    b.append(text(149, 284, "D103 量出 1.32× 纸面加速", 10, MUTED))
    b.append(text(149, 302, "搜索空间（D106）会喂来更多", 9.5, MUTED))

    # ---- 中：检查链 ----
    b.append(arrow(258, 195, 306, 195, INK, 2))
    b.append(hand_rect(310, 92, 330, 66, GREEN, 0.25, INK, 1.8))
    b.append(text(475, 116, "① 参数校验（便宜，先跑）", 12, INK, "middle", True))
    b.append(text(475, 138, "全是正整数？dtype 认识？缓冲策略认识？→ ✓ 通过", 9.5, MUTED))
    b.append(arrow(475, 160, 475, 176, INK, 1.6))

    b.append(hand_rect(310, 178, 330, 92, BLUE, 0.25, INK, 1.8))
    b.append(text(475, 202, "② 空间估算（贵，后跑）", 12, INK, "middle", True))
    b.append(text(475, 222, "A 65,536×2 + B 65,536×2 + C 65,536", 10, INK))
    b.append(text(475, 240, "+ bias 512  =  合计 328,192 B", 10, INK, "middle", True))
    b.append(text(475, 258, "×2 只加在 A/B 流入项；C 恒按 4 B 记", 9.5, MUTED))
    b.append(arrow(475, 272, 475, 288, INK, 1.6))

    b.append(hand_rect(310, 290, 330, 116, RED, 0.18, INK, 1.8))
    b.append(text(475, 314, "③ 预算判定（≤，绝不约等于）", 12, INK, "middle", True))
    bx, scale = 330, 260 / 350000
    bud = bx + 262144 * scale
    tot = bx + 328192 * scale
    b.append(hand_rect(bx, 330, tot - bx, 22, ORANGE, 0.6))
    b.append(hand_rect(bud, 330, tot - bud, 22, RED, 0.8))
    b.append(hand_line(bud, 324, bud, 360, INK, 1.6, "6 4"))
    b.append(text(bud, 326, "预算 262,144 B", 9.5, INK, "end"))
    b.append(text(bx + 14, 346, "合计 328,192 B", 9.5, INK, "start", True))
    b.append(text(tot + 8, 346, "超 66,048", 9.5, RED, "start", True))
    b.append(text(475, 380, "贴线也是放行：合计 == 预算 → ✓（判定用 ≤）", 9.5, MUTED))

    # ---- 右：Verdict 卡 ----
    b.append(arrow(644, 350, 690, 350, INK, 2))
    b.append(hand_rect(694, 92, 250, 314, RED, 0.15, INK, 2.0))
    b.append(text(819, 118, "Verdict：✗ 拒绝", 14, RED, "middle", True))
    b.append(text(819, 140, "拒绝码 SRAM_OVERFLOW", 11, INK))
    for i, (k, v) in enumerate([("合计", "328,192 B"), ("预算", "262,144 B"),
                                ("超出", "66,048 B（25.2%）")]):
        y = 166 + i * 24
        b.append(text(712, y, k, 10, MUTED, "start"))
        b.append(text(926, y, v, 10, INK, "end", True))
    b.append(hand_line(712, 244, 926, 245, MUTED, 1.2, "4 4"))
    b.append(text(819, 266, "出路（每条重新过同一道闸门）", 10.5, INK, "middle", True))
    for i, (lab, val, axis, note) in enumerate([
            ("a) 退单缓冲", "197,120 B ✓", "时间", "丢 D103 的重叠"),
            ("b) 缩 tile 64³", "82,176 B ✓", "空间", "复用↓ HBM 流量↑"),
            ("c) 降 dtype bf16", "197,120 B ✓", "精度", "D78~81 把关")]):
        y = 290 + i * 40
        b.append(text(712, y, lab, 10.5, INK, "start", True))
        b.append(text(926, y, val, 10, "#4d7c4f", "end", True))
        b.append(text(712, y + 16, f"代价轴={axis}（{note}）", 9.5, MUTED, "start"))

    # ---- 底部：fail-closed 与分离原则 ----
    b.append(hand_rect(70, 442, 420, 96, RED, 0.2, INK, 1.6))
    b.append(text(280, 468, "fail-closed：不认识的输入一律拒绝", 12.5, INK, "middle", True))
    b.append(text(280, 490, "p3 dtype=fp64 → ✗ BAD_PARAM，列出 5 个可选值", 10, INK))
    b.append(text(280, 510, "绝不静默猜默认值继续编译（D95 消费门同款）", 10, MUTED))
    b.append(hand_rect(510, 442, 420, 96, GREEN, 0.2, INK, 1.6))
    b.append(text(720, 468, "短路可观测：便宜先行", 12.5, INK, "middle", True))
    b.append(text(720, 490, "4 个非法参数：参数校验 4 次，空间估算 0 次", 10, INK))
    b.append(text(720, 510, "贵的检查往后追加，前面的结论不变", 10, MUTED))
    b.append(text(490, 572, "诊断必须带数字：拒绝码＋明细＋超出字节＋三条出路；排序留给 D110 Cost Model（D74 分离原则）",
                  10.5, MUTED))
    b.append(text(490, 598, "数字来自 code/outputs/filter-table.txt 与 fallback.txt 的真实运行", 10.5, MUTED))
    save("02-mechanism.svg", b + ["</svg>"])


# ======================= 图 3：候选对照图 =======================
def fig3():
    b = frame("12 个候选 × 256 KiB：纸面最优被一票否决（真实运行结果）")
    b.append(hand_line(330, 47, 650, 48, ORANGE, 3))

    rows = [
        ("32³ fp32·single", 12416, "4.7%", True, ""),
        ("32³ fp32·double", 20608, "7.9%", True, ""),
        ("64³ fp32·single", 49408, "18.8%", True, ""),
        ("64³ fp32·double", 82176, "31.3%", True, ""),
        ("96³ fp32·single", 110976, "42.3%", True, ""),
        ("96³ fp32·double", 184704, "70.5%", True, ""),
        ("128³ fp32·single", 197120, "75.2%", True, ""),
        ("128³ fp32·double", 328192, "125.2%", False, "纸面最优（D97 冠军）"),
        ("128³ bf16·double", 197120, "75.2%", True, ""),
        ("128³ int8·double", 131584, "50.2%", True, ""),
        ("160×128×64 fp32·db", 229888, "87.7%", True, ""),
        ("256³ fp32·single", 787456, "300.4%", False, "超预算 3 倍"),
    ]
    X0, BW = 216, 690
    scale = BW / 787456
    bud_x = X0 + 262144 * scale
    y_top = 74
    b.append(hand_line(bud_x, y_top, bud_x, 586, INK, 1.8, "7 5"))
    b.append(text(bud_x - 6, y_top - 6, "256 KiB 预算红线 262,144 B", 10.5, INK, "end"))

    b.append(text(40, y_top + 12, "候选", 10.5, INK, "start", True))
    for i, (nm, val, util, ok, note) in enumerate(rows):
        y = y_top + 18 + i * 30
        w = val * scale
        col = GREEN if ok else RED
        b.append(hand_rect(X0, y, max(w, 3), 20, col, 0.55 if ok else 0.75, INK, 1.1))
        b.append(text(40, y + 15, nm, 10, INK, "start"))
        if ok:
            b.append(text(X0 + w + 8, y + 15, f"{val:,} B  {util}  ✓", 9.5, "#4d7c4f", "start", True))
        else:
            over = val - 262144
            lab = f"{val:,} B  {util}  ✗ 超 {over:,} B"
            if X0 + w + 180 < 972:
                b.append(text(X0 + w + 8, y + 15, lab, 9.5, RED, "start", True))
            else:
                b.append(text(X0 + w - 10, y + 15, lab, 9.5, INK, "end", True))
        if note:
            if val == 328192:
                b.append(text(X0 + w + 200, y + 32, note, 9.5, RED, "start", True))
            else:
                b.append(text(X0 + 240, y + 15, note, 9.5, INK, "start", True))

    # ---- 底部：三条出路 ----
    b.append(hand_line(40, 452, 940, 453, MUTED, 1.2, "4 4"))
    b.append(text(490, 476, "被拒冠军的三条出路：都住得下，但各花一本账（代价轴不同）", 12.5, INK, "middle", True))
    alts = [("a) 退单缓冲", 197120, "时间", "丢 D103 的重叠，回到轮流值班"),
            ("b) 缩 tile 64³", 82176, "空间", "片上复用↓ → HBM 流量↑（D101）"),
            ("c) 降 dtype bf16", 197120, "精度", "数值风险交给 D78~81 阈值")]
    for i, (nm, val, axis, note) in enumerate(alts):
        y = 496 + i * 32
        w = val * scale
        b.append(hand_rect(X0, y, w, 20, GREEN, 0.5, INK, 1.1))
        b.append(text(40, y + 15, nm, 10, INK, "start", True))
        b.append(text(X0 + w + 8, y + 15, f"{val:,} B  ✓  代价轴={axis}", 9.5, INK, "start", True))
        b.append(text(X0 + w + 210, y + 15, note, 9.5, MUTED, "start"))
    b.append(text(490, 612, "数字来自 code/outputs/filter-table.txt 与 fallback.txt 的真实运行"
                  "（Python 3.11.4，aarch64，2026-11-13）", 10.5, MUTED))
    save("03-comparison.svg", b + ["</svg>"])


def main():
    os.makedirs(os.path.join(os.path.dirname(__file__), "..", "images"), exist_ok=True)
    fig1()
    fig2()
    fig3()


if __name__ == "__main__":
    main()
