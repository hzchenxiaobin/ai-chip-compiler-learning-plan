#!/usr/bin/env python3
"""生成第 103 天的 3 张手绘 sketch 风 SVG 技术图（Excalidraw-like）。

风格约定：白板涂鸦感——线条用带抖动的贝塞尔手绘路径、马克笔笔触、
3～4 种柔和强调色（橙/蓝/绿/红）＋米白背景、简单几何形状、手写感字体。
所有数字来自 pipeline.py 的真实运行结果（code/outputs/）。
固定随机种子，保证图可复现。
"""

from __future__ import annotations

import os
import random

random.seed(103)

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
    import math
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
    b = frame("第 103 天定位：计算与搬运重叠——空间账和时间账在这天合流")
    b.append(hand_line(330, 47, 650, 48, ORANGE, 3))
    # 本周路线：6 个里程碑
    steps = [("D99", "活跃区间表"), ("D100", "片外规划"), ("D101", "片上空间账"),
             ("D102", "时间账·依赖"), ("D103", "双缓冲·重叠"), ("D104", "资源过滤")]
    for i, (day, topic) in enumerate(steps):
        x = 46 + i * 156
        hot = day == "D103"
        b.append(hand_rect(x, 80 if hot else 84, 128, 54 if hot else 46,
                           ORANGE if hot else BG, 0.75 if hot else 1.0,
                           INK, 2.2 if hot else 1.4))
        b.append(text(x + 64, 103, day, 13.5, INK, "middle", True))
        b.append(text(x + 64, 122, topic, 10.5, MUTED if not hot else INK))
        if i < 5:
            b.append(arrow(x + 130, 106, x + 154, 106, MUTED, 1.6))
    b.append(hand_line(202, 150, 486, 149, GREEN, 2.2))
    b.append(text(344, 165, "空间轴：数据住哪、占多大", 10.5, MUTED))
    b.append(hand_line(514, 150, 798, 149, RED, 2.2))
    b.append(text(656, 165, "时间轴：谁必须等谁", 10.5, MUTED))
    # 主图：HBM → DMA → SRAM → 计算单元
    b.append(hand_rect(40, 200, 140, 300, BLUE, 0.35, INK, 1.8))
    b.append(text(110, 226, "HBM（片外）", 13.5, INK, "middle", True))
    for i, (nm, sz) in enumerate([("A", "1 MiB"), ("B", "1 MiB"),
                                  ("C", "1 MiB"), ("bias", "2 KiB")]):
        y = 250 + i * 56
        b.append(hand_rect(56, y, 108, 36, BG, 1.0, INK, 1.2))
        b.append(text(110, y + 23, f"{nm}  {sz}", 11, INK))
    b.append(hand_rect(240, 236, 150, 104, ORANGE, 0.45, INK, 1.8))
    b.append(text(315, 264, "DMA 引擎", 13.5, INK, "middle", True))
    b.append(text(315, 288, "32.768 GB/s（示例）", 10, MUTED))
    b.append(text(315, 306, "按提交顺序执行", 10, MUTED))
    b.append(hand_rect(440, 200, 300, 300, BG, 1.0, INK, 1.8))
    b.append(text(590, 226, "SRAM 256 KiB（D101 预算）", 13, INK, "middle", True))
    for i, nm in enumerate(["A 槽 0", "A 槽 1"]):
        b.append(hand_rect(462 + i * 132, 248, 122, 38, ORANGE, 0.55))
        b.append(text(523 + i * 132, 272, nm + " 16,384 B", 10.5, INK))
    b.append(text(590, 304, "乒乓 ×2：DMA 流入项才翻倍", 10.5, RED, "middle", True))
    for i, nm in enumerate(["B 槽 0", "B 槽 1"]):
        b.append(hand_rect(462 + i * 132, 316, 122, 38, ORANGE, 0.55))
        b.append(text(523 + i * 132, 340, nm + " 16,384 B", 10.5, INK))
    b.append(hand_rect(462, 372, 254, 38, BLUE, 0.5))
    b.append(text(589, 396, "C 槽 16,384 B（累加器，单份）", 10.5, INK))
    b.append(hand_rect(462, 428, 130, 34, BLUE, 0.5))
    b.append(text(527, 450, "bias 256 B（单份）", 10, INK))
    b.append(text(590, 470, "算 c[k] 读槽 k%2 ∥ 搬 A/B[k+1] 写槽 (k+1)%2", 10, MUTED, "middle"))
    b.append(hand_rect(790, 236, 150, 104, GREEN, 0.4, INK, 1.8))
    b.append(text(865, 264, "计算单元", 13.5, INK, "middle", True))
    b.append(text(865, 288, "262,144 MAC/µs（示例）", 10, MUTED))
    b.append(text(865, 306, "C += A·B", 11, INK))
    b.append(arrow(182, 272, 238, 272, ORANGE, 2.2))
    b.append(arrow(392, 272, 438, 272, ORANGE, 2.2))
    b.append(text(310, 262, "Load 流入", 10.5, RED))
    b.append(arrow(438, 322, 392, 322, GREEN, 2.2, "5 4"))
    b.append(arrow(238, 322, 182, 322, GREEN, 2.2, "5 4"))
    b.append(text(310, 342, "Store 写回", 10.5, "#4d7c4f"))
    b.append(arrow(742, 262, 788, 262, INK, 1.5))
    b.append(arrow(788, 292, 742, 292, INK, 1.5))
    b.append(text(765, 254, "读 A/B", 9.5, MUTED))
    b.append(text(765, 312, "写 C", 9.5, MUTED))
    # 底部两本账
    b.append(hand_rect(60, 528, 400, 74, GREEN, 0.3, INK, 1.6))
    b.append(text(260, 556, "空间账：49,408 → 82,176 B（+66.3%）", 12.5, INK, "middle", True))
    b.append(text(260, 582, "×2 只加在 A/B 流入项，仍住得下 256 KiB", 11, MUTED))
    b.append(hand_rect(500, 528, 420, 74, RED, 0.25, INK, 1.6))
    b.append(text(710, 556, "时间账：1056.5 → 608.5 → 545.5 µs", 12.5, INK, "middle", True))
    b.append(text(710, 582, "逐块双缓冲 1.74×；跨块预取 1.94×（下界 544.5）", 11, MUTED))
    save("01-overview.svg", b + ["</svg>"])


# ======================= 图 2：双缓冲时间线机制图 =======================
def fig2():
    b = frame("双缓冲时间线：算第 k 圈的同时，DMA 搬第 k+1 圈（块 i0=0, j0=0）")
    b.append(hand_line(280, 47, 700, 48, GREEN, 3))
    X0, X1 = 90, 917
    T = 9.5078125
    sc = (X1 - X0) / T

    def x(t):
        return X0 + t * sc

    b.append(text(40, 118, "DMA", 14, INK, "middle", True))
    b.append(text(40, 136, "引擎", 11, MUTED))
    b.append(text(40, 214, "计算", 14, INK, "middle", True))
    b.append(text(40, 232, "单元", 11, MUTED))
    b.append(hand_rect(85, 92, 832, 52, BG, 1.0, INK, 1.6))
    b.append(hand_rect(85, 188, 832, 52, BG, 1.0, INK, 1.6))
    # 重叠边界虚线（t=1..7）
    for t in range(1, 8):
        b.append(hand_line(x(t), 82, x(t), 250, GREEN, 1.3, "4 4"))
    # DMA 泳道：bias 细条 + 8 对 Load + 空闲 + Store
    b.append(hand_rect(x(0), 98, max(2.0, x(0.0078125) - x(0)), 40, GREEN, 0.7, INK, 1.0))
    b.append(text(150, 88, "bias 0.0078 µs（窄到画不出）", 9.5, MUTED))
    for k in range(8):
        xk = x(k + 0.0078125)
        b.append(hand_rect(xk, 98, x(k + 1.0078125) - xk, 40, ORANGE, 0.6))
        b.append(text(xk + 43, 123, f"A{k}→B{k}", 10, INK, "middle", True))
    b.append(text(830, 88, "DMA 无货可搬", 9.5, RED))
    b.append(hand_rect(x(9.0078125), 98, x(T) - x(9.0078125), 40, GREEN, 0.6))
    b.append(text(x(9.25), 123, "Store", 9.5, INK, "middle", True))
    # 计算泳道：填充空隙 + 8 圈计算 + 排空
    b.append(text(x(0.5), 218, "填充：干等", 10, MUTED))
    for k in range(8):
        xk = x(k + 1.0078125)
        b.append(hand_rect(xk, 194, x(k + 2.0078125) - xk, 40, BLUE, 0.65))
        lab = "c0+bias" if k == 0 else f"c{k}"
        b.append(text(xk + 43, 219, lab, 9.5 if k == 0 else 11, INK, "middle", True))
    b.append(text(x(9.25), 218, "排空", 10, MUTED))
    b.append(text(503, 262, "每个整圈边界：S1（数据已到）与 S2（槽位已空）同时满足——无需等待", 11, "#4d7c4f"))
    # 阶段带
    b.append(hand_rect(X0, 272, x(1.0078125) - X0, 24, RED, 0.35))
    b.append(text(x(0.5), 289, "填充 1.0", 10, INK))
    b.append(hand_rect(x(1.0078125), 272, x(8.0078125) - x(1.0078125), 24, GREEN, 0.4))
    b.append(text(x(4.5), 289, "稳态 7×1.0 µs（双忙重叠）", 11, INK, "middle", True))
    b.append(hand_rect(x(8.0078125), 272, X1 - x(8.0078125), 24, ORANGE, 0.45))
    b.append(text(x(8.75), 289, "排空 1.5", 10, INK))
    # 时间轴
    b.append(hand_line(X0, 316, X1 + 18, 316, INK, 2))
    for t in range(10):
        b.append(hand_line(x(t), 311, x(t), 318, INK, 1.3))
        b.append(text(x(t), 332, str(t), 10, MUTED))
    b.append(text(x(T), 332, "9.5", 10, MUTED))
    b.append(text(945, 320, "µs", 10.5, MUTED))
    # A 槽乒乓与 S2 距离
    b.append(text(490, 368, "A 槽乒乓：S2 的复用距离从 1 拉到 2", 13, INK, "middle", True))
    b.append(hand_rect(170, 382, 250, 42, ORANGE, 0.5))
    b.append(text(295, 408, "槽 0：A0·A2·A4·A6", 11, INK))
    b.append(hand_rect(560, 382, 250, 42, ORANGE, 0.5))
    b.append(text(685, 408, "槽 1：A1·A3·A5·A7", 11, INK))
    b.append(arrow(428, 403, 552, 403, MUTED, 1.8))
    b.append(arrow(552, 403, 428, 403, MUTED, 1.8))
    b.append(text(490, 452, "算 c[k] 读槽 k%2 ∥ 搬 A/B[k+1] 写槽 (k+1)%2——两个槽永不撞车", 11.5, INK))
    b.append(text(490, 476, "S2（WAR）：『等上一圈 c[k] 读完』放松为『等上上圈 c[k−1] 读完』，白等 448 µs → 0", 11.5, RED))
    # 对照条
    b.append(hand_rect(90, 496, 390, 64, RED, 0.2, INK, 1.5))
    b.append(text(285, 521, "单缓冲（D102）：每圈 搬1.0＋算1.0＝2.0 µs", 11.5, INK, "middle", True))
    b.append(text(285, 545, "本块 16.5078 µs，两排完全错开", 10.5, MUTED))
    b.append(hand_rect(510, 496, 400, 64, GREEN, 0.25, INK, 1.5))
    b.append(text(710, 521, "双缓冲：每圈 max(搬1.0, 算1.0)＝1.0 µs", 11.5, INK, "middle", True))
    b.append(text(710, 545, "本块 9.5078 µs，省 7 µs＝7 圈重叠的搬运", 10.5, MUTED))
    b.append(text(490, 600, "填充 1.0078｜稳态 7×1.0｜排空 1.5 µs——数字来自 code/outputs/main-tile.txt 的真实运行",
                  10.5, MUTED))
    save("02-mechanism.svg", b + ["</svg>"])


# ======================= 图 3：单双缓冲对照图 =======================
def fig3():
    b = frame("单／双缓冲对照：时间账、空间账与预算红线（真实运行结果）")
    b.append(hand_line(300, 47, 680, 48, ORANGE, 3))
    # ---- 左：时间账 ----
    b.append(text(255, 76, "时间账：总时长（µs，越短越好）", 13.5, INK, "middle", True))
    lx, ls = 80, 300 / 1056.5            # px per µs
    lb_x = lx + 544.5 * ls
    b.append(hand_line(lb_x, 88, lb_x, 296, RED, 1.6, "6 4"))
    b.append(text(lb_x + 6, 100, "理想重叠下界 544.5 µs", 10, RED, "start"))
    bars = [("单缓冲（D102）", 1056.5, RED, 0.35, "1056.5 µs｜利用率 48.46%｜DMA 闲置 512 µs", False),
            ("逐块双缓冲", 608.5, ORANGE, 0.6, "608.5 µs｜84.14%｜1.74×", True),
            ("跨块预取流水线", 545.5, GREEN, 0.55, "545.5 µs｜93.86%｜1.94×", True)]
    for i, (nm, val, col, op, lab, outside) in enumerate(bars):
        y = 108 + i * 64
        w = val * ls
        b.append(hand_rect(lx, y, w, 40, col, op))
        if outside:
            b.append(text(lx + w + 10, y + 26, lab, 11, INK, "start", True))
            b.append(text(lx + 12, y + 26, nm, 11, INK, "start"))
        else:
            b.append(text(lx + w / 2, y + 26, f"{nm}  {lab}", 11, INK, "middle", True))
    b.append(text(lx + 608.5 * ls + 10, 108 + 64 + 26 + 18,
                  "距下界 64 µs＝每块 1 µs 暴露的填充", 9.5, RED, "start"))
    b.append(text(lx + 545.5 * ls + 10, 108 + 128 + 26 + 18,
                  "距下界仅 1 µs（全 kernel 一次排空）", 9.5, "#4d7c4f", "start"))
    b.append(text(255, 322, "DMA 闲置：512 → 64 → 1 µs；计算气泡：544.5 → 96.5 → 33.5 µs", 10.5, MUTED))
    # ---- 右：空间账 ----
    b.append(text(750, 76, "空间账：SRAM 占用（B）", 13.5, INK, "middle", True))
    rx, rs = 560, 240 / 262144           # px per B
    bud_x = rx + 262144 * rs
    b.append(hand_line(bud_x, 88, bud_x, 296, INK, 1.6, "6 4"))
    b.append(text(bud_x - 6, 100, "256 KiB 预算（D101）", 10, INK, "end"))
    b.append(hand_rect(rx, 108, 49408 * rs, 40, BLUE, 0.5))
    b.append(text(rx + 49408 * rs + 10, 134, "64³ 单缓冲 49,408 B", 11, INK, "start", True))
    b.append(hand_rect(rx, 172, 82176 * rs, 40, ORANGE, 0.6))
    b.append(text(rx + 82176 * rs + 10, 198, "64³ 双缓冲 82,176 B（+66.3%）", 11, INK, "start", True))
    b.append(hand_rect(rx, 236, 262144 * rs, 40, ORANGE, 0.6))
    b.append(hand_rect(bud_x, 236, (328192 - 262144) * rs, 40, RED, 0.7))
    b.append(text(rx + 140, 262, "128³ 双缓冲 328,192 B", 11, INK, "start", True))
    b.append(text(bud_x + 34, 262, "✗ 超预算被拒", 11, RED, "start", True))
    b.append(text(750, 322, "×2 只加在 A/B（DMA 流入项）；C 与 bias 保持单份", 10.5, MUTED))
    # ---- 底部结论箱 ----
    b.append(hand_rect(70, 352, 420, 92, GREEN, 0.22, INK, 1.6))
    b.append(text(280, 378, "带宽等价（对照实验一）", 12.5, INK, "middle", True))
    b.append(text(280, 402, "双缓冲 ×1 带宽：84.14% ＞ 单缓冲 ×4 带宽：79.00%", 11, INK))
    b.append(text(280, 424, "82,176 B 的空间买到约 4× 带宽的效果；", 10.5, MUTED))
    b.append(text(280, 441, "×8 带宽时双缓冲 97.7% vs 单缓冲 88.3%", 10.5, MUTED))
    b.append(hand_rect(520, 352, 400, 92, BLUE, 0.22, INK, 1.6))
    b.append(text(720, 378, "K 深度摊薄（对照实验二）", 12.5, INK, "middle", True))
    b.append(text(720, 402, "逐块流水线填充+排空占比：26.4%（K=512）→ 7.5%（K=2048）", 10.5, INK))
    b.append(text(720, 424, "跨块预取的填充+排空天生只有一份：0.28%", 10.5, MUTED))
    b.append(text(720, 441, "K 越深圈数越多，逐块方案自动逼近流水线", 10.5, MUTED))
    b.append(hand_rect(70, 466, 850, 66, RED, 0.16, INK, 1.6))
    b.append(text(495, 492, "S2 并未消失：511 → 510 次，变的只是等待时长（448 µs 白等 → 0）", 12, INK, "middle", True))
    b.append(text(495, 516, "同步语句一个都不能删——调度松了，法律还在（D102 的依赖账本依然有效）", 10.5, MUTED))
    b.append(text(490, 578, "示例参数：DMA 32,768 B/µs、计算 262,144 MAC/µs；512×512×512，tile 64³，FP32", 10.5, MUTED))
    b.append(text(490, 598, "数字来自 code/outputs/ 的真实运行（Python 3.11.4，aarch64，2026-11-13）", 10.5, MUTED))
    save("03-comparison.svg", b + ["</svg>"])


def main():
    os.makedirs(os.path.join(os.path.dirname(__file__), "..", "images"), exist_ok=True)
    fig1()
    fig2()
    fig3()


if __name__ == "__main__":
    main()
