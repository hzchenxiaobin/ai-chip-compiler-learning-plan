#!/usr/bin/env python3
"""生成第 84 天教程的 4 张手绘风（Excalidraw-like）SVG 技术图。

运行方式：
    python3 make_images.py

输出到 ../images/ 目录：
    01-overview.svg       第 84 天在第三阶段与编译链路中的位置 + 中心论点 + 三件产出
    02-checklist.svg      优化正确性检查清单 v1.0：五组 16 项 + 探针矩阵（真实结果）
    03-layout-gap.svg     补讲 1：同一块 24 元素存储的三种身份（真实 shares_memory 数据）
    04-quant-gap.svg      补讲 2：非 2 幂 scale 的半格分叉解剖（真实分叉数据）

风格与 Day 78~83 保持一致：手绘抖动线条、马克笔笔触、米白背景、
蓝/橙/绿/红四种柔和强调色、简单几何形状。
图中数值全部来自 stage3_review.py 的真实运行结果（outputs/report.txt）。
"""

import math
import random
from pathlib import Path

random.seed(84)

INK = "#3b3b3b"
SOFT = "#6b6459"
BLUE = "#5f8fcb"
ORANGE = "#e8973f"
GREEN = "#79b26a"
RED = "#d96c5c"
BG = "#fdf9f0"
L_BLUE = "#dbe7f6"
L_ORANGE = "#fdead3"
L_GREEN = "#e5f1dc"
L_RED = "#f9dfd9"
FONT = "'Comic Sans MS','Segoe Print','Bradley Hand','Kaiti SC','KaiTi','STKaiti',cursive"

OUT = Path(__file__).resolve().parent.parent / "images"


def jseg(x1, y1, x2, y2, amp=1.3):
    dx, dy = (x2 - x1) / 2.0, (y2 - y1) / 2.0
    a = random.uniform(-amp, amp)
    b = random.uniform(-amp, amp)
    c = random.uniform(-amp, amp)
    d = random.uniform(-amp, amp)
    e = random.uniform(-amp, amp)
    f = random.uniform(-amp, amp)
    return (f"M {x1 + a:.1f},{y1 + b:.1f} Q {x1 + dx + c:.1f},{y1 + dy + d:.1f} "
            f"{x2 + e:.1f},{y2 + f:.1f}")


def style(fill="none", stroke=INK, sw=2.2, dash=None):
    s = (f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}" '
         f'stroke-linecap="round" stroke-linejoin="round"')
    if dash:
        s += f' stroke-dasharray="{dash}"'
    return s


def srect(x, y, w, h, fill="none", stroke=INK, sw=2.2, amp=1.3, dash=None):
    pts = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
    d = " ".join(jseg(*p, *q, amp) for p, q in zip(pts, pts[1:] + pts[:1]))
    return f'<path d="{d} Z" {style(fill, stroke, sw, dash)}/>'


def sline(x1, y1, x2, y2, stroke=INK, sw=2.2, dash=None, amp=1.3):
    return f'<path d="{jseg(x1, y1, x2, y2, amp)}" {style("none", stroke, sw, dash)}/>'


def head(x, y, ang, stroke, sw, l=13, spread=0.46):
    a1 = (x - l * math.cos(ang - spread), y - l * math.sin(ang - spread))
    a2 = (x - l * math.cos(ang + spread), y - l * math.sin(ang + spread))
    return (f'<path d="{jseg(x, y, a1[0], a1[1], 0.7)}" {style("none", stroke, sw)}/>'
            f'<path d="{jseg(x, y, a2[0], a2[1], 0.7)}" {style("none", stroke, sw)}/>')


def arrow(x1, y1, x2, y2, stroke=INK, sw=2.2, dash=None):
    ang = math.atan2(y2 - y1, x2 - x1)
    return (f'<path d="{jseg(x1, y1, x2, y2)}" {style("none", stroke, sw, dash)}/>'
            + head(x2, y2, ang, stroke, sw))


def carrow(p0, ctrl, p1, stroke=INK, sw=2.2, dash=None):
    d = f"M {p0[0]:.1f},{p0[1]:.1f} Q {ctrl[0]:.1f},{ctrl[1]:.1f} {p1[0]:.1f},{p1[1]:.1f}"
    ang = math.atan2(p1[1] - ctrl[1], p1[0] - ctrl[0])
    return f'<path d="{d}" {style("none", stroke, sw, dash)}/>' + head(p1[0], p1[1], ang, stroke, sw)


def text(x, y, s, size=16, fill=INK, anchor="start", rot=None):
    t = (f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-size="{size}" '
         f'fill="{fill}"')
    if rot:
        t += f' transform="rotate({rot} {x} {y})"'
    return t + f">{s}</text>"


def svg_doc(w, h, body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
            f'width="{w}" height="{h}">'
            f'<rect x="3" y="3" width="{w - 6}" height="{h - 6}" rx="7" fill="{BG}"/>'
            f'<g font-family="{FONT}">' + body + "</g></svg>")


def chip(x, y, label, fill, w=None, h=26, size=14):
    w = w or (len(label) * (size * 0.62) + 18)
    body = srect(x, y, w, h, fill=fill, stroke=fill, sw=1.6, amp=0.9)
    body += text(x + w / 2, y + h * 0.72, label, size, INK, "middle")
    return body


def title_block(w, title, sub=None):
    body = text(30, 44, title, 25, INK)
    if sub:
        body += text(30, 72, sub, 15, SOFT)
    body += sline(30, 84, w - 30, 84, SOFT, 1.6, dash="7 6")
    return body


# ============================================================
# 图 1：全貌——第三阶段弧线 + 中心论点 + 三件产出
# ============================================================

def img1() -> str:
    W, H = 1200, 762
    b = title_block(W, "第 84 天全貌：第三阶段收官——四周弧线汇入今天",
                    "图编译器 = 模式匹配（手） ＋ 布局 / 资源 / 数值语义（三位管理员）")

    # 上排：四周弧线（D57~84）
    weeks = [
        ("W9  D57~63", "Shape/Stride/Layout 地基", "「Shape 相同 ≠ 布局相同」", L_BLUE, BLUE),
        ("W10  D64~70", "布局与冗余消除", "「图结构相同 ≠ 内存语义」", L_GREEN, GREEN),
        ("W11  D71~77", "融合收益与代价", "「合法·正确·更快三本账」", L_ORANGE, ORANGE),
        ("W12  D78~84", "数值精度与量化", "「位等价与 golden 两本账」", L_RED, RED),
    ]
    x0, y0, bw, bh, gap = 40, 100, 265, 112, 22
    for i, (t, m, quote, lf, lc) in enumerate(weeks):
        x = x0 + i * (bw + gap)
        b += srect(x, y0, bw, bh, fill=lf, stroke=lc, sw=2.4, amp=1.1)
        b += text(x + 14, y0 + 28, t, 15.5, INK)
        b += text(x + 14, y0 + 54, m, 14, INK)
        b += text(x + 14, y0 + 86, quote, 12.5, SOFT)
        if i < 3:
            b += arrow(x + bw + 1, y0 + bh / 2, x + bw + gap - 1, y0 + bh / 2, SOFT, 2.0)

    # 第二带：D83 → D84（今天）→ D85 ＋ 位置说明
    y1 = 244
    b += srect(40, y1, 210, 84, fill="white", stroke=SOFT, sw=2.0, dash="6 5")
    b += text(52, y1 + 30, "D83 集成验收", 15.5, INK)
    b += text(52, y1 + 58, "五道闸管道：11 → 5", 13, SOFT)
    b += arrow(251, y1 + 42, 279, y1 + 42, SOFT, 2.0)
    b += srect(282, y1 - 6, 250, 96, fill=L_ORANGE, stroke=ORANGE, sw=3.0, amp=1.5)
    b += text(296, y1 + 24, "D84 今天：复盘收官", 16.5, INK)
    b += text(296, y1 + 50, "第 12 周复盘 ＋ 第三阶段总结", 13, INK)
    b += text(296, y1 + 74, "论点 · 讲稿 · 补讲 · 清单", 13, INK)
    b += arrow(533, y1 + 42, 561, y1 + 42, SOFT, 2.0, dash="5 5")
    b += srect(564, y1, 230, 84, fill="white", stroke=SOFT, sw=2.0, dash="6 5")
    b += text(576, y1 + 30, "D85 起：第四阶段", 15, INK)
    b += text(576, y1 + 58, "Lowering（设计转换路线）", 13, SOFT)
    b += srect(820, y1, 346, 84, fill="white", stroke=INK, sw=2.0)
    b += text(834, y1 + 30, "今天的位置：图优化阶段的收口", 14, INK)
    b += text(834, y1 + 58, "吐出的干净图正是 Lowering 的输入", 13, SOFT)

    # 中排：中心论点
    y2 = 366
    b += srect(40, y2, 330, 178, fill="white", stroke=INK, sw=2.4)
    b += text(60, y2 + 32, "模式匹配", 19, INK)
    b += chip(160, y2 + 14, "是「手」，不是「身份」", L_BLUE, h=28, size=13.5)
    b += text(60, y2 + 68, "消除 / 融合 / 折叠……", 14, SOFT)
    b += text(60, y2 + 92, "只是改写图的动作本身；", 14, SOFT)
    b += text(60, y2 + 116, "决定「能不能动」的，是右边", 14, SOFT)
    b += text(60, y2 + 140, "三位管理员管的语义资源", 14, SOFT)
    b += text(60, y2 + 164, "（学习计划今日点名的论点）", 12.5, SOFT)

    managers = [
        ("布局管理", "B 组", "同一块存储的多种读法；", "Shape 相同 ≠ 内存相同；",
         "元信息改写的前提是连续", BLUE, L_BLUE, "W9/W10"),
        ("资源管理", "C 组", "融合不是免费的：工作集", "对标片上容量，spill 一票",
         "否决；ΔB 是账，不是速度", ORANGE, L_ORANGE, "W11"),
        ("数值管理", "D 组", "位等价（容差=0）与 golden", "（误差账本）是两本账；",
         "量化改写各有安全边界", GREEN, L_GREEN, "W12"),
    ]
    mx = 400
    for name, grp, l1, l2, l3, lc, lf, src in managers:
        b += srect(mx, y2, 250, 178, fill=lf, stroke=lc, sw=2.4, amp=1.1)
        b += text(mx + 16, y2 + 34, name, 18, INK)
        b += chip(mx + 118, y2 + 16, grp, "white", h=26, size=13)
        b += text(mx + 16, y2 + 68, l1, 13.5, INK)
        b += text(mx + 16, y2 + 92, l2, 13.5, INK)
        b += text(mx + 16, y2 + 116, l3, 13.5, INK)
        b += text(mx + 16, y2 + 152, f"来源：{src}", 12.5, SOFT)
        b += arrow(mx - 2, y2 + 89, mx - 22, y2 + 89, SOFT, 2.0)
        mx += 268
    b += text(40, y2 + 192, "两位「流程管家」（A 结构 / E 流程）管剩下的：Verifier、rewire 纪律、审计与拒绝——五组合起来就是检查清单 v1.0", 13, SOFT)

    # 下排：三件产出
    y3 = 598
    b += text(40, y3 - 14, "今日三件产出（学习计划点名：第三阶段总结 ＋ 优化正确性检查清单）：", 15.5, INK)
    outs = [
        ("20 分钟讲稿", "四乐章：噪声图 → 四周武器 →", "现场演示 11→5 → 边界与拒绝；",
         "每乐章一句「这展示了 XX 管理」", L_BLUE, BLUE),
        ("补讲 ×2（排练卡壳点）", "Layout：残留 reshape 三句话；", "量化：非 2 幂 scale 半格分叉；",
         "全部 numpy 实测，不是口头补丁", L_GREEN, GREEN),
        ("检查清单 v1.0", "五组 16 项，项项可执行；", "2 正例全绿 ＋ 3 探针各就位；",
         "review-onepage.md ＋ stage3_review.py", L_ORANGE, ORANGE),
    ]
    ox = 40
    for t, l1, l2, l3, lf, lc in outs:
        b += srect(ox, y3, 360, 140, fill=lf, stroke=lc, sw=2.4, amp=1.1)
        b += text(ox + 16, y3 + 32, t, 16.5, INK)
        b += text(ox + 16, y3 + 62, l1, 13.5, INK)
        b += text(ox + 16, y3 + 86, l2, 13.5, INK)
        b += text(ox + 16, y3 + 116, l3, 12.5, SOFT)
        ox += 382
    return svg_doc(W, H, b)


# ============================================================
# 图 2：检查清单 v1.0 五组 + 探针矩阵
# ============================================================

def img2() -> str:
    W, H = 1200, 780
    b = title_block(W, "优化正确性检查清单 v1.0：从备忘录到测试套件",
                    "五组 16 项，每项一个可执行函数；三个负例探针验证清单本身（数据全部来自 stage3_review.py 实测）")

    groups = [
        ("A 结构", "合法性", BLUE, L_BLUE, [
            ("A1", "终图过 Verifier"),
            ("A2", "删除即无主（rewire）"),
            ("A3", "清理不动点收敛"),
        ], "D12/39/59/60/64/69/52"),
        ("B 布局", "元信息前提", GREEN, L_GREEN, [
            ("B1", "reshape 不吃非连续生产者"),
            ("B2", "无漏折的编译期数据移动"),
            ("B3", "reshape 链深度 ≤ 1"),
        ], "D57/59/64/65/66"),
        ("C 资源", "账本与红线", ORANGE, L_ORANGE, [
            ("C1", "融合有账（ΔB+工作集）"),
            ("C2", "判融合 ⇒ 无 spill 且 ΔB>0"),
            ("C3", "1024³ 必须判拒绝"),
        ], "D72/73/74/76"),
        ("D 数值", "两本账＋量化", RED, L_RED, [
            ("D1", "位等价：容差 = 0"),
            ("D2", "golden：账本 atol 内"),
            ("D3", "Q/DQ scale 为 2 的幂"),
            ("D4", "融合核 bias 形状门"),
        ], "D78/79/81/82/83"),
        ("E 流程", "纪律", INK, "white", [
            ("E1", "原图不动（副本上改）"),
            ("E2", "审计先于动作"),
            ("E3", "拒绝也是决策"),
        ], "D69/75/82/83"),
    ]
    gx, gy, gw, gh = 40, 104, 216, 268
    for name, sub, lc, lf, items, src in groups:
        b += srect(gx, gy, gw, gh, fill=lf, stroke=lc, sw=2.6, amp=1.1)
        b += text(gx + 14, gy + 32, name, 18, INK)
        b += text(gx + 92, gy + 32, sub, 13.5, SOFT)
        iy = gy + 62
        for cid, it in items:
            b += chip(gx + 12, iy, cid, "white", h=22, size=12.5)
            head_txt, tail_txt = it[:10], it[10:]
            b += text(gx + 52, iy + 16, head_txt, 12.8, INK)
            if tail_txt:
                b += text(gx + 12, iy + 34, tail_txt, 12.8, INK)
                iy += 44
            else:
                iy += 32
        b += text(gx + 12, gy + gh - 12, f"出处 {src}", 11.5, SOFT)
        gx += 232

    # 探针矩阵
    my = 420
    b += text(40, my - 14, "探针 × 清单组矩阵（✓=该组全过；✗=该组红项——真实运行结果）：", 15.5, INK)
    cols = ["A 结构", "B 布局", "C 资源", "D 数值", "E 流程"]
    cx0, cw = 320, 122
    b += srect(40, my, 1120, 264, fill="white", stroke=INK, sw=2.2)
    b += sline(40, my + 36, 1160, my + 36, INK, 1.8)
    b += sline(cx0, my, cx0, my + 264, INK, 1.8)
    for i, c in enumerate(cols):
        b += text(cx0 + 16 + i * cw, my + 25, c, 14, INK)
    rows = [
        ("主图 11→5（该融就融）", ["✓", "✓", "✓", "✓", "✓"], "16/16 全绿", GREEN),
        ("多使用者 11→7（该拒就拒）", ["✓", "✓", "✓", "✓", "✓"], "16/16 全绿", GREEN),
        ("P1 删尾部 QDQ（数值）", ["✓", "✓", "✓", "✗D1", "✓"], "max|diff| = 0.0625 = s/2", RED),
        ("P2 断链融合（结构）", ["✗A1,A2", "✓", "✗C1", "✗D1,D2", "✗E2"], "返回值 %7 未定义", RED),
        ("P3 1024³ 强融（资源）", ["✓", "✓", "✗C2", "✓", "✓"], "spill=True 仍判「融合」", RED),
    ]
    ry = my + 64
    for label, cells, note, color in rows:
        b += text(52, ry, label, 13.8, INK)
        for i, cell in enumerate(cells):
            cx = cx0 + 22 + i * cw
            if cell.startswith("✗"):
                b += srect(cx - 8, ry - 18, cw - 34, 26, fill=L_RED, stroke=RED, sw=1.6, amp=0.8)
                b += text(cx, ry, cell, 13.5, RED)
            else:
                b += text(cx, ry, cell, 14.5, GREEN)
        b += text(952, ry, note, 12.3, color)
        ry += 40
    b += text(52, my + 244, "主图/多使用者两行全绿；三枚探针红在各自的列：", 13, SOFT)
    b += text(52, my + 260, "P1 结构全过、图能跑、就是数不对——只有 D1 抓得住；P2 第一时间红在 A（D 连出场机会都没有）；P3 只红 C（图没坏，坏的是决策记录）", 12.5, SOFT)

    # 底部一句
    b += srect(40, 706, 1120, 46, fill=L_BLUE, stroke=BLUE, sw=2.0, amp=1.0)
    b += text(58, 734, "读法：列与列互不代劳——Day 77 的三张 certificate，在阶段收官长成五组清单；「清单全绿」是结果，「探针能红」才是清单被验证过的证据", 13.5, INK)
    return svg_doc(W, H, b)


# ============================================================
# 图 3：补讲 1（Layout）——同一块存储的三种身份
# ============================================================

def img3() -> str:
    W, H = 1200, 720
    b = title_block(W, "补讲 1（Layout）：剩下的 reshape(2,12→4,6) 贵不贵？",
                    "同一块 24 元素存储的三种读法＋一个反例（shares_memory 全部实测）")

    # ① 物理存储 (2,12)
    b += text(40, 118, "① 物理存储 buf：shape (2,12)，C 连续", 15.5, INK)
    cell_w, cell_h = 22, 26
    gx, gy = 44, 130
    for idx in range(24):
        r, c = divmod(idx, 12)
        x, y = gx + c * cell_w, gy + r * cell_h
        b += srect(x, y, cell_w, cell_h, fill="white", stroke=SOFT, sw=1.5, amp=0.7)
        b += text(x + cell_w / 2, y + 18, str(idx), 11.5, SOFT, "middle")
    b += text(44, gy + 2 * cell_h + 22, "一维线性序 0..23（24 个 fp32）", 12.5, SOFT)
    b += text(44, gy + 2 * cell_h + 44, "元素 (i,j) 的物理偏移 = 12i + j", 13, INK)

    # ② 逻辑视图 (4,6)
    b += text(360, 118, "② 逻辑视图 v = buf.reshape(4,6)：零拷贝", 15.5, INK)
    cw2, ch2 = 30, 30
    gx2, gy2 = 366, 130
    for idx in range(24):
        r, c = divmod(idx, 6)
        x, y = gx2 + c * cw2, gy2 + r * ch2
        fill = L_BLUE if r % 2 == 0 else "white"
        b += srect(x, y, cw2, ch2, fill=fill, stroke=BLUE, sw=1.6, amp=0.7)
        b += text(x + cw2 / 2, y + 20, str(idx), 12, INK, "middle")
    b += text(366, gy2 + 4 * ch2 + 24, "元素 (p,q) 的物理偏移 = 6p + q", 13, INK)
    b += text(366, gy2 + 4 * ch2 + 46, "两套公式扫过同一条线性序（实测相等）", 12.5, GREEN)
    b += text(366, gy2 + 4 * ch2 + 68, "shares_memory = True，strides = (24,4) B", 13, INK)
    b += arrow(330, 240, 358, 240, SOFT, 2.0)
    b += text(292, 224, "同一块内存", 12, SOFT)
    b += text(296, 258, "换个记法", 12, SOFT)

    # ③ stride 描述符 ④ 物化拷贝
    rx = 620
    b += srect(rx, 106, 540, 118, fill=L_GREEN, stroke=GREEN, sw=2.4, amp=1.1)
    b += text(rx + 16, 134, "③ stride 描述符（第四阶段 Lowering 的预演）", 15, INK)
    b += text(rx + 16, 160, "as_strided(buf, shape=(4,6), strides=(24,4)B)：不搬数据，", 13, INK)
    b += text(rx + 16, 182, "只告诉硬件「按 (6,1) 步长把这块 (2,12) 缓冲当 (4,6) 读」", 13, INK)
    b += text(rx + 16, 208, "实测：view@Ŵᵀ == stride@Ŵᵀ == copy@Ŵᵀ（位等价 True）", 13, GREEN)
    b += carrow((rx + 500, 224), (rx + 520, 258), (rx + 470, 288), GREEN, 2.2, dash="6 5")
    b += text(rx + 300, 300, "D85 起：Lowering 用 stride 描述符吸收它", 13, SOFT)

    b += srect(rx, 316, 540, 84, fill="white", stroke=SOFT, sw=2.0)
    b += text(rx + 16, 344, "④ 老老实实物化拷贝：v.copy()", 14.5, INK)
    b += text(rx + 16, 370, "shares_memory = False（新分配 96 B）——数据真的搬了家", 13, INK)

    # 反例 + 结论
    by = 430
    b += srect(40, by, 560, 122, fill=L_RED, stroke=RED, sw=2.4, amp=1.1)
    b += text(56, by + 30, "反例：连续性前提不是免费的", 15.5, INK)
    b += text(56, by + 58, "t = buf.T（(12,2)，非连续）→ t.reshape(2,12)：", 13, INK)
    b += text(56, by + 82, "shares_memory = False —— 元信息改写退化为", 13, INK)
    b += text(56, by + 106, "真实的物理搬运（B1 检查项的由来）", 13, INK)

    b += srect(620, by, 540, 122, fill=L_ORANGE, stroke=ORANGE, sw=2.4, amp=1.1)
    b += text(636, by + 28, "补讲 1 的标准答案（三句话）", 15.5, INK)
    b += text(636, by + 54, "① 图层面必须保留：matmul 的 Shape 契约要求 (M,K)，", 12.8, INK)
    b += text(636, by + 76, "    删掉图就不合法；按 stride 读缓冲是 Lowering 的能力；", 12.8, INK)
    b += text(636, by + 98, "② 物理层面免费：连续输入上零拷贝；③ 前提进清单：B1", 12.8, INK)

    # 底部：三种读法喂 GEMM
    b += srect(40, 574, 1120, 108, fill="white", stroke=INK, sw=2.2)
    b += text(58, 604, "三种读法喂同一个 GEMM（用终图折叠好的常量 Ŵᵀ(6,3)）：", 14.5, INK)
    b += text(58, 632, "reshape 视图 @ Ŵᵀ ＝ stride 描述符 @ Ŵᵀ ＝ 物化拷贝 @ Ŵᵀ → 逐位相等（np.array_equal True）", 13.5, INK)
    b += text(58, 660, "终图的「运行时算子」数是 2（reshape + fused）；Lowering 把 reshape 折进 fused 的地址计算后，落到硬件的只有 1 个核", 13, SOFT)
    return svg_doc(W, H, b)


# ============================================================
# 图 4：补讲 2（量化）——半格分叉解剖
# ============================================================

def img4() -> str:
    W, H = 1200, 700
    b = title_block(W, "补讲 2（量化）：非 2 幂 scale 的半格分叉——golden「无缘无故」差一个码的解剖",
                    "实弹数据：s = 0.7/127 = 0.005512，w = 0.0082677165…（定向扫描第一发）")

    # 主面板：w/s 数轴
    px, py, pw = 70, 300, 620
    b += srect(40, 106, 700, 350, fill="white", stroke=INK, sw=2.2)
    b += text(58, 138, "数轴：商 w/s（量化前除法的结果）", 15, INK)

    # 数轴线：0.9 到 2.1
    x1, x2 = px + 20, px + pw - 20
    def vx(v):
        return x1 + (v - 0.9) / (2.1 - 0.9) * (x2 - x1)
    b += sline(x1, py, x2, py, INK, 2.6)
    for v, lab in [(1.0, "码 1"), (1.5, "半格 1.5"), (2.0, "码 2")]:
        b += sline(vx(v), py - 10, vx(v), py + 10, INK, 2.2)
        b += text(vx(v), py + 34, lab, 13.5, INK, "middle")
    b += sline(vx(1.5), py - 10, vx(1.5), py - 96, SOFT, 1.8, dash="6 5")

    # fp32 商：恰在 1.5
    b += chip(vx(1.5) - 62, py - 176, "fp32 商 = 1.5", L_BLUE, h=28, size=13.5)
    b += arrow(vx(1.5), py - 146, vx(1.5), py - 100, BLUE, 2.4)
    b += text(vx(1.5) + 8, py - 66, "除法把商舍到了半格上", 12.5, BLUE)
    b += carrow((vx(1.5), py - 12), (vx(1.5) + 34, py + 66), (vx(2.0) - 4, py + 66), BLUE, 2.4)
    b += text(vx(2.0) - 12, py + 92, "round-half-even 进到码 2", 13, BLUE, "end")

    # fp64 商：1.4999999944
    b += chip(vx(1.32), py - 176, "fp64 商 = 1.4999999944", L_ORANGE, h=28, size=13.5)
    b += arrow(vx(1.42), py - 146, vx(1.4994), py - 12, ORANGE, 2.4)
    b += text(vx(1.1), py - 66, "真商在半格下方 5.6e-09", 12.5, ORANGE)
    b += carrow((vx(1.4994), py - 12), (vx(1.3), py + 66), (vx(1.0) + 6, py + 66), ORANGE, 2.4)
    b += text(vx(1.0) + 10, py + 92, "退回码 1", 13, ORANGE)

    # 结果
    b += srect(58, 400, 664, 40, fill=L_RED, stroke=RED, sw=2.0, amp=1.0)
    b += text(70, 426, "码差 1 → 反量化值差 = 一个 scale = 0.00551（w = 0.0082677165…，s = 0.7/127）", 13.5, INK)

    # 分叉概率
    b += text(58, 168, "同一个 w，两种精度各算各的 w/s：", 13.5, INK)
    b += text(58, 192, "随机压测 2,000,000 个权重：分叉 5 个（0.00025%——半格是道窄门）", 13, INK)
    b += text(58, 216, "定向扫描 k=1..127 每条半格 (k+0.5)·s 的 fp32 邻域：命中 62 个", 13, INK)
    b += text(58, 240, "→ 不是都市传说，是窄概率事件：随机测难命中，半格边上密密麻麻", 13, SOFT)

    # 右侧：两个修正 + D3
    rx = 772
    b += srect(rx, 106, 388, 168, fill=L_GREEN, stroke=GREEN, sw=2.4, amp=1.1)
    b += text(rx + 16, 136, "修正 A：scale 取 2 的幂", 15.5, INK)
    b += text(rx + 16, 164, "s = 2⁻⁷ = 1/128（Day 83 主图的纪律）", 13, INK)
    b += text(rx + 16, 190, "同一批 2,000,000 权重：随机 0 ＋ 定向 0 个分叉", 13, INK)
    b += text(rx + 16, 216, "除以 2 的幂是精确操作——两种精度看到", 13, INK)
    b += text(rx + 16, 240, "同一个商，round 永远落在同一格", 13, INK)

    b += srect(rx, 296, 388, 160, fill=L_BLUE, stroke=BLUE, sw=2.4, amp=1.1)
    b += text(rx + 16, 326, "修正 B：golden 的量化同精度", 15.5, INK)
    b += text(rx + 16, 354, "参考实现也用 fp32 口径做量化：分叉 0 个", 13, INK)
    b += text(rx + 16, 380, "账本只记执行误差；若必须保留非 2 幂 scale，", 13, INK)
    b += text(rx + 16, 404, "atol 放宽一个 scale 并写明理由", 13, INK)

    b += srect(rx, 478, 388, 118, fill=L_ORANGE, stroke=ORANGE, sw=2.4, amp=1.1)
    b += text(rx + 16, 508, "对照清单 D3（声明层检查）", 15, INK)
    b += text(rx + 16, 536, "5.4 节实测：scale 换 3.2/127 后 D3 立刻红；", 12.8, INK)
    b += text(rx + 16, 560, "D2 在 5 组输入上没踩中半格（窄门）仍绿——", 12.8, INK)
    b += text(rx + 16, 584, "确定性报警 > 概率性事故，不等事故发生", 12.8, INK)

    # 底部结论
    b += srect(40, 620, 1120, 46, fill="white", stroke=INK, sw=2.0)
    b += text(58, 648, "结论：「无缘无故差一个码」= fp32 的除法自己制造了一个半格点——数值管理的意思是：连除法的舍入都要在账本里", 13.5, INK)
    return svg_doc(W, H, b)


def main() -> int:
    OUT.mkdir(exist_ok=True)
    for name, fn in [("01-overview.svg", img1), ("02-checklist.svg", img2),
                     ("03-layout-gap.svg", img3), ("04-quant-gap.svg", img4)]:
        path = OUT / name
        path.write_text(fn(), encoding="utf-8")
        print(f"生成 {path}（{path.stat().st_size} B）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
