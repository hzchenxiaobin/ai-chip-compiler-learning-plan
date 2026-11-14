#!/usr/bin/env python3
"""生成第 105 天的 3 张手绘 sketch 风 SVG 技术图（Excalidraw-like）。

风格约定与 D103/D104 一致：白板涂鸦感——带抖动的贝塞尔手绘路径、
马克笔笔触、3～4 种柔和强调色（橙/蓝/绿/红）＋米白背景、简单几何
形状、手写感字体。所有数字来自 tile_story.py 的真实运行结果
（code/outputs/）。固定随机种子，保证图可复现。
"""

from __future__ import annotations

import math
import os
import random

random.seed(105)

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


def badge(x, y, label, fill=ORANGE):
    """手绘圆圈编号（旅程阶段徽章）。"""
    d = (f"M {x + 9 + jit():.1f},{y + jit():.1f} "
         f"C {x + 16},{y - 8} {x + 16},{y + 8} {x + 9 + jit():.1f},{y + jit():.1f} "
         f"C {x + 2},{y + 8} {x + 2},{y - 8} {x + 9 + jit():.1f},{y + jit():.1f} Z")
    return [f'<path d="{d}" stroke="{INK}" stroke-width="1.5" fill="{fill}" '
            f'fill-opacity="0.85"/>',
            text(x + 9, y + 5, label, 13, INK, "middle", True)]


def frame(title):
    return [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
            f'font-family="{FONT}">',
            hand_rect(4, 4, W - 8, H - 8, BG, 1.0, BORDER, 2),
            text(W / 2, 36, title, 21, INK, "middle", True)]


def save(name, body):
    body.append("</svg>")
    out = os.path.join(os.path.dirname(__file__), "..", "images", name)
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(body) + "\n")
    print(f"  已生成 images/{name}")


# ================= 图 1：第 15 周知识地图（地铁线） =================
def fig1():
    b = frame("第 15 周知识地图：六件工具，串成一个 Tile 的完整旅程")
    # 两个尺度的大背景带
    b.append(hand_rect(30, 64, 330, 210, BLUE, 0.28, INK, 1.2))
    b.append(text(195, 88, "编译期·图级（片外 HBM，单位 MiB）", 13, INK, "middle", True))
    b.append(hand_rect(610, 64, 340, 210, GREEN, 0.28, INK, 1.2))
    b.append(text(780, 88, "运行期·块级（片上 SRAM，单位 KiB / µs）", 13, INK, "middle", True))
    # 地铁主线
    b.append(hand_line(60, 250, 920, 251, MUTED, 4))
    stations = [
        (118, "D99", "活跃区间", "谁在何时活着\n峰值 320/416", BLUE, False),
        (288, "D100", "片外房间", "workspace 2 MiB\n= 峰值下界", BLUE, False),
        (452, "D101+104", "闸门", "82,176 B ✓\n328,192 B ✗", ORANGE, True),
        (614, "D102", "搬运依赖", "S1~S4\n谁必须等谁", GREEN, False),
        (780, "D103", "流水线", "1.74× / 1.94×\n重叠＋摊薄", GREEN, False),
        (918, "D105", "完整故事", "今天", ORANGE, True),
    ]
    for x, day, name, note, col, hot in stations:
        b.append(f'<path d="M {x + jit():.1f},{244 + jit():.1f} '
                 f'C {x + 9},{230} {x + 9},{258} {x + jit():.1f},{244 + jit():.1f} Z" '
                 f'stroke="{INK}" stroke-width="2" fill="{col}" fill-opacity="0.9"/>')
        b.append(text(x, 276, day, 14, INK, "middle", True))
        b.append(text(x, 294, name, 12.5, INK if hot else MUTED, "middle", not hot))
        for i, ln in enumerate(note.split("\n")):
            b.append(text(x, 311 + i * 15, ln, 10.5, MUTED))
    # 主角小车
    b.append(hand_rect(96, 216, 74, 22, RED, 0.8, INK, 1.6))
    b.append(text(133, 231, "C[0,0] 出发", 11, INK, "middle", True))
    # 尺度之间的桥
    b.append(arrow(362, 250, 444, 250, MUTED, 2.2))
    b.append(text(403, 232, "过闸才发车", 10.5, RED))
    b.append(arrow(546, 250, 608, 250, MUTED, 2.2))
    b.append(text(577, 232, "变成代码", 10.5, MUTED))
    # 下半部：今天的三件交付物
    b.append(hand_line(80, 360, 900, 361, ORANGE, 3))
    b.append(text(490, 382, "今天的三个交付物（都在本文可以验证）", 13.5, INK, "middle", True))
    cards = [
        (110, "旅程事件日志", "outputs/story.txt", "四幕：房间→闸门→\n9.5078 µs 时间线→总账", BLUE),
        (410, "硬件映射一页图", "本文图 2", "HBM↔DMA↔SRAM↔计算单元\n①~⑥ 六阶段＋S1~S4", ORANGE),
        (710, "本周测试 12 题", "weekly_test.py", "D99~D104 每天两题\n自动判分＋参考答案", GREEN),
    ]
    for x, t1, t2, t3, col in cards:
        b.append(hand_rect(x, 402, 210, 118, col, 0.4, INK, 1.8))
        b.append(text(x + 105, 430, t1, 14.5, INK, "middle", True))
        b.append(hand_line(x + 40, 442, x + 170, 443, MUTED, 1.2))
        b.append(text(x + 105, 462, t2, 11, MUTED, "middle"))
        for i, ln in enumerate(t3.split("\n")):
            b.append(text(x + 105, 483 + i * 16, ln, 11, INK))
    # 底部一句串联
    b.append(text(W / 2, 566, "一条规律贯穿两个尺度：谁不用了，谁退场——", 13, INK, "middle", True))
    b.append(text(W / 2, 588, "图级（区间不重叠→共享房间） · 槽级（WAR 距离 1→2） · 块级（S4 写回即让位）",
                  11.5, MUTED, "middle"))
    b.append(hand_line(300, 600, 680, 601, RED, 2))
    save("01-overview.svg", b)


# ============ 图 2：硬件映射一页图（计划点名的交付物） ============
def fig2():
    b = frame("硬件映射一页图：块 C[0,0] 从片外加载到结果写回")
    # ---------- 左：HBM ----------
    b.append(hand_rect(36, 66, 232, 420, BLUE, 0.3, INK, 1.8))
    b.append(text(152, 90, "HBM（片外）", 14, INK, "middle", True))
    for i, (nm, sz) in enumerate([("x  512×512", "1 MiB"),
                                  ("w  512×512", "1 MiB · 常驻"),
                                  ("bias  512", "2 KiB")]):
        y = 104 + i * 52
        b.append(hand_rect(52, y, 200, 40, BG, 1.0, INK, 1.2))
        b.append(text(152, y + 18, nm, 11.5, INK))
        b.append(text(152, y + 32, sz, 10, MUTED))
    # workspace：x→y 共享 + t 的房间
    b.append(hand_rect(52, 262, 200, 130, BG, 1.0, INK, 1.4))
    b.append(text(152, 280, "workspace 2 MiB（D100）", 11.5, INK, "middle", True))
    b.append(hand_rect(64, 290, 176, 38, GREEN, 0.5, INK, 1.2))
    b.append(text(152, 307, "x → y 共享（区间不重叠）", 10.5, INK))
    b.append(text(152, 321, "偏移 0，各 1 MiB", 9.5, MUTED))
    b.append(hand_rect(64, 334, 176, 48, ORANGE, 0.55, INK, 1.4))
    b.append(text(152, 351, "t 的房间（偏移 1 MiB）", 10.5, INK, "middle", True))
    b.append(hand_rect(70, 358, 84, 18, RED, 0.8, INK, 1.2))
    b.append(text(112, 371, "C[0,0]→16,384 B", 8.5, INK, "middle", True))
    b.append(text(205, 371, "开头", 9.5, MUTED))
    b.append(text(152, 438, "③ 末圈算完 → S3 → 写回这里", 10.5, RED, "middle", True))
    b.append(text(152, 456, "64 个块轮流住进这 1 MiB", 10, MUTED))
    # ---------- 中：DMA 引擎 ----------
    b.append(hand_rect(300, 150, 130, 96, ORANGE, 0.5, INK, 1.8))
    b.append(text(365, 182, "DMA 引擎", 13.5, INK, "middle", True))
    b.append(text(365, 201, "32,768 B/µs", 11, MUTED))
    b.append(text(365, 219, "单引擎·按提交顺序", 9.5, MUTED))
    # load/store 箭头
    b.append(arrow(268, 190, 348, 176, BLUE, 3))
    b.append(text(300, 158, "② Load 流入", 10.5, INK, "middle", True))
    b.append(arrow(352, 244, 272, 258, ORANGE, 3))
    b.append(text(306, 272, "④ Store 写回", 10.5, INK, "middle", True))
    # ---------- 右上：SRAM ----------
    b.append(hand_rect(470, 66, 300, 252, GREEN, 0.3, INK, 1.8))
    b.append(text(620, 90, "SRAM（片上，预算 256 KiB）", 13.5, INK, "middle", True))
    slots = [("A 槽0   16,384 B", "乒乓←A 偶数圈"), ("A 槽1   16,384 B", "乒乓←A 奇数圈"),
             ("B 槽0   16,384 B", "乒乓←B 偶数圈"), ("B 槽1   16,384 B", "乒乓←B 奇数圈"),
             ("C 槽    16,384 B", "累加器·常驻 ×1"), ("bias    256 B", "k=0 圈加一次")]
    for i, (nm, note) in enumerate(slots):
        y = 102 + i * 34
        b.append(hand_rect(486, y, 190, 28, BG, 1.0, INK, 1.1))
        b.append(text(496, y + 19, nm, 10.5, INK, "start", True))
        b.append(text(690, y + 19, note, 9.5, MUTED, "end"))
    b.append(hand_rect(486, 306, 130, 10, RED, 0.7, INK, 1))
    b.append(hand_rect(486, 306, 60, 10, GREEN, 0.9, INK, 0))
    b.append(text(700, 314, "合计 82,176 B = 预算的 31.3%", 11, INK, "start", True))
    b.append(hand_line(616, 296, 616, 322, RED, 1.5, "5 4"))
    b.append(text(620, 300, "预算 262,144 B", 9.5, RED, "start"))
    # ---------- 右：计算单元 ----------
    b.append(hand_rect(810, 130, 138, 130, GREEN, 0.45, INK, 1.8))
    b.append(text(879, 160, "计算单元", 13.5, INK, "middle", True))
    b.append(text(879, 180, "262,144 MAC/µs", 10.5, MUTED))
    b.append(text(879, 200, "每圈 64³=1 µs", 10, MUTED))
    b.append(text(879, 219, "读槽 k%2 → 累加进 C", 9.5, MUTED))
    # SRAM <-> 计算单元 箭头 + 同步点
    b.append(arrow(774, 176, 856, 176, GREEN, 3))
    b.append(text(812, 160, "S1", 11, RED, "middle", True))
    b.append(arrow(856, 214, 774, 214, RED, 2, "5 4"))
    b.append(text(815, 233, "S2", 11, RED, "middle", True))
    # 同步点小抄（DMA 与 SRAM 之间的空档）
    b.append(hand_rect(284, 318, 176, 92, BG, 1.0, INK, 1.3))
    b.append(text(372, 336, "四个同步点（D102）", 10.5, INK, "middle", True))
    b.append(hand_line(300, 344, 444, 345, MUTED, 1))
    b.append(text(292, 362, "S1 RAW：计算等搬运完工", 9.5, INK, "start"))
    b.append(text(292, 378, "S2 WAR：覆盖槽前等上上圈", 9.5, INK, "start"))
    b.append(text(292, 392, "     读者（距离 1→2）", 9.5, INK, "start"))
    b.append(text(292, 408, "S3 RAW：写回等累加完工", 9.5, INK, "start"))
    b.append(text(292, 424, "S4 WAR：C 槽复用等写回", 9.5, INK, "start"))
    # 阶段徽章 ① ~ ⑥
    for (x, y, lab) in [(152, 480, "①"), (300, 120, "②"), (879, 100, "③"),
                        (276, 292, "④"), (556, 342, "⑤"), (656, 342, "⑥")]:
        b += badge(x, y, lab)
    b.append(text(815, 247, "白等 448 µs → 0", 9, MUTED, "start"))
    b.append(text(178, 486, "出生：清单排好（bias+A/B 切片+C 槽）", 10.5, MUTED, "start"))
    b.append(text(322, 126, "入住：搬 bias＋首圈 A/B（填充 1.0078 µs）", 10.5, MUTED, "start"))
    b.append(text(879, 118, "成长：8 圈累加", 10.5, MUTED, "middle"))
    b.append(text(292, 298, "写回：S3→Store 0.5 µs", 10.5, MUTED, "start"))
    b.append(text(575, 348, "让位：S4 后 C 槽交给块 1", 10.5, MUTED, "start"))
    # ⑥ 交班说明
    b.append(hand_rect(470, 368, 300, 58, BG, 1.0, INK, 1.4))
    b.append(text(620, 388, "⑥ 交班：末圈计算时，DMA 已在预取块 1 的 A[1,0]/B[1,0]", 10, INK, "middle", True))
    b.append(text(620, 404, "填充/排空从每块一次 → 全 kernel 一次（26.38%→0.28%）", 9.5, MUTED))
    b.append(text(620, 418, "块 0 让位时刻：store[0] 9.0078–9.5078 ‖ 预取 8.0078 起", 9.5, MUTED))
    # 底部时间账条
    b.append(hand_rect(36, 494, 912, 118, BG, 1.0, INK, 1.4))
    b.append(text(492, 516, "时间账（真实运行，µs）：块 C[0,0]", 13, INK, "middle", True))
    # 双缓冲块条：填充 | 8×1 双忙 | 写回
    x0, w_total = 96, 700
    b.append(hand_rect(x0, 528, int(w_total * 1.0078 / 9.5078), 26, ORANGE, 0.8, INK, 1.2))
    b.append(hand_rect(x0 + int(w_total * 1.0078 / 9.5078), 528,
                       int(w_total * 8.0 / 9.5078), 26, GREEN, 0.7, INK, 1.2))
    b.append(hand_rect(x0 + int(w_total * 9.0078 / 9.5078), 528,
                       int(w_total * 0.5 / 9.5078), 26, BLUE, 0.9, INK, 1.2))
    b.append(text(x0 + 18, 545, "填充 1.0078", 9.5, INK, "start", True))
    b.append(text(x0 + 350, 545, "稳态 8×1.0 双忙（算 k 圈 ‖ 搬 k+1 圈）", 10, INK, "middle", True))
    b.append(text(x0 + w_total, 545, "写回 0.5", 9.5, INK, "end", True))
    b.append(text(x0, 572, "单缓冲同块 16.5078（轮流值班）；内核总账 1056.5 / 608.5 / 545.5 µs → 1.74× / 1.94×，距理想下界 544.5 仅 1 µs", 10.5, MUTED, "start"))
    b.append(text(x0, 592, "空间账：82,176 B 全程不变——住得下就一直住着；闸门在第二幕就判完，运行期不再变", 10.5, MUTED, "start"))
    save("02-hardware-map.svg", b)


# ============ 图 3：C[0,0] 的一生——时间线对照 + 内核总账 ============
def fig3():
    b = frame("块 C[0,0] 的一生：两种缓冲的时间线对照与内核总账")
    # ---- 上：单缓冲 ----
    def lane(y, label):
        b.append(hand_rect(150, y, 660, 34, BG, 1.0, INK, 1.1))
        b.append(text(140, y + 21, label, 11, INK, "end", True))

    b.append(text(70, 82, "单缓冲（D102）：轮流值班——搬完才算，算完才搬", 13, INK, "start", True))
    lane(92, "DMA")
    lane(132, "计算")
    # DMA: b A B | A B | ... (8 组) + store；计算空档
    x0, u = 160, 72   # 每 µs ≈ 72/u 太宽；用示意格：16.5078 µs → 640 px ⇒ 38.8 px/µs
    u = 640 / 16.5078
    # DMA 条
    b.append(hand_rect(150 + 0 * u, 96, 0.0078 * u, 26, ORANGE, 0.9, INK, 0))
    for k in range(8):
        lx = (1.0078 + 2 * k) * u
        b.append(hand_rect(150 + lx, 96, 2 * 0.5 * u, 26, BLUE, 0.8, INK, 1))
        b.append(text(150 + lx + 19 * u / 19.0, 92, "", 8))
    b.append(hand_rect(150 + 16.0078 * u, 96, 0.5 * u, 26, ORANGE, 0.9, INK, 1))
    # 计算条
    for k in range(8):
        cx = (1.0078 + 2 * k + 1) * u
        b.append(hand_rect(150 + cx, 136, 1.0 * u, 26, GREEN, 0.8, INK, 1))
    b.append(text(820, 112, "块 16.5078 µs", 11.5, RED, "start", True))
    b.append(text(820, 130, "S2 让 DMA 白等", 9.5, MUTED, "start"))
    b.append(text(820, 146, "448 µs（全 kernel）", 9.5, MUTED, "start"))
    # ---- 中：双缓冲 ----
    b.append(text(70, 210, "双缓冲（D103）：双忙——算 k 圈 ‖ 搬 k+1 圈", 13, INK, "start", True))
    lane(220, "DMA")
    lane(260, "计算")
    u2 = 640 / 9.5078
    b.append(hand_rect(150, 224, 0.0078 * u2, 26, ORANGE, 0.9, INK, 0))
    b.append(hand_rect(150 + 0.0078 * u2, 224, 1.0 * u2, 26, BLUE, 0.8, INK, 1))
    for k in range(1, 8):
        lx = k * u2
        b.append(hand_rect(150 + lx, 224, 1.0 * u2, 26, BLUE, 0.8, INK, 1))
    b.append(hand_rect(150 + 9.0078 * u2, 224, 0.5 * u2, 26, ORANGE, 0.9, INK, 1))
    for k in range(8):
        cx = (1.0078 + k) * u2
        b.append(hand_rect(150 + cx, 264, 1.0 * u2, 26, GREEN, 0.8, INK, 1))
    b.append(text(820, 240, "块 9.5078 µs", 11.5, RED, "start", True))
    b.append(text(820, 258, "S2 白等 = 0", 9.5, MUTED, "start"))
    # 阶段标注（双缓冲行）
    b.append(badge(150 + 0.5 * u2 - 9, 306, "②")[0])
    b.append(text(150 + 0.5 * u2 + 6, 311, "填充 1.0078", 9.5, MUTED, "start"))
    b.append(badge(150 + 5 * u2 - 9, 306, "③")[0])
    b.append(text(150 + 5 * u2 + 6, 311, "稳态 8×1 双忙（乒乓槽 k%2）", 9.5, MUTED, "start"))
    b.append(badge(150 + 9.25 * u2 - 9, 306, "④")[0])
    b.append(text(150 + 9.25 * u2 + 6, 311, "写回 0.5 → S4 让位", 9.5, MUTED, "start"))
    # ---- 下：内核总账三根条 ----
    b.append(text(70, 360, "内核总账（64 块，真实运行）", 13, INK, "start", True))
    bars = [("单缓冲", 1056.5, "48.46% / 51.54%", "1.00×", RED),
            ("双缓冲", 608.5, "84.14% / 89.48%", "1.74×", ORANGE),
            ("流水线", 545.5, "93.86% / 99.82%", "1.94×", GREEN)]
    scale = 620 / 1056.5
    for i, (nm, v, util, sp, col) in enumerate(bars):
        y = 378 + i * 56
        b.append(text(140, y + 20, nm, 11.5, INK, "end", True))
        b.append(hand_rect(150, y, int(v * scale), 30, col, 0.8, INK, 1.4))
        b.append(text(158 + int(v * scale), y + 20, f"{v:.1f} µs", 11, INK, "start", True))
        b.append(text(158 + int(v * scale), y + 20 - 0, "", 9))
        b.append(text(158 + int(v * scale) + 76, y + 20, f"{sp}   利用率 {util}", 10, MUTED, "start"))
    # 理想下界虚线
    lx = 150 + int(544.5 * scale)
    b.append(hand_line(lx, 370, lx, 556, RED, 1.6, "7 5"))
    b.append(text(lx, 366, "理想下界 544.5 = max(DMA忙, 计算忙)", 10, RED, "middle", True))
    # 底部注解
    b.append(hand_rect(36, 552, 912, 62, BG, 1.0, INK, 1.2))
    b.append(text(492, 574, "同一块 C[0,0]，同一份数据依赖——差别只在『槽位几个、何时许覆盖』：", 11.5, INK, "middle", True))
    b.append(text(492, 592, "WAR 距离 1（一个槽）→ 2（乒乓）→ 预取跨块 → 白等 448 µs → 0 → 填充/排空摊薄（26.38%→0.28%）", 10.5, MUTED, "middle"))
    save("03-journey-timeline.svg", b)


if __name__ == "__main__":
    print("生成第 105 天手绘图（seed=105）：")
    fig1()
    fig2()
    fig3()
