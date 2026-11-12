#!/usr/bin/env python3
"""make_images.py —— 第 56 天教程的四张手绘 sketch 风 SVG 信息图。

风格约定（与第 8 周前几天一致）：
  - 背景 #fdfaf2（米白），盒子白底 + 深灰 #6b6357 手绘描边
  - 强调色不超过 4 种柔和色：蓝 #4a7fa5 / 橙 #a8772e / 绿 #5a8a5a / 红 #b0605a
  - 线条带轻微抖动（Q/L 混合路径），圆头笔触，线宽 2 左右
  - 手写感字体栈：Comic Sans MS / Comic Neue / Kaiti SC / 楷体 / cursive

图中全部数字来自 2026-11-12 的真实运行
（mlir-mini/run_all.sh 的 14/14 断言、code/test_journey.py 的 22/22 测试）。

运行: python3 make_images.py   （在 code/ 目录下，输出到 ../images/）
"""

from __future__ import annotations

import math
import random
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "images"
OUT.mkdir(parents=True, exist_ok=True)

FONT = ("Comic Sans MS, Comic Neue, Segoe Print, Kaiti SC, KaiTi, 楷体, "
        "cursive")
INK = "#3b352d"          # 主文字色
MUTED = "#84796a"        # 次要文字色
STROKE = "#6b6357"       # 手绘描边
BG = "#fdfaf2"           # 米白背景
BLUE, ORANGE, GREEN, RED = "#4a7fa5", "#a8772e", "#5a8a5a", "#b0605a"
TINT = {"blue": "#eef3f7", "orange": "#f8f0e2", "green": "#edf4ee",
        "red": "#f7ecea", "white": "#ffffff", "gray": "#f1efe9"}

rng = random.Random(56)


def esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;")
             .replace(">", "&gt;"))


def txt(x, y, s, size=12, fill=INK, anchor="start", bold=False,
        opacity=1.0):
    w = 'font-weight="bold"' if bold else 'font-weight="normal"'
    return (f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" '
            f'fill="{fill}" text-anchor="{anchor}" opacity="{opacity}" '
            f'{w}>{esc(s)}</text>')


def sketch_rect(x, y, w, h, fill="#ffffff", stroke=STROKE, sw=2.2, nseg=6):
    """带抖动的手绘矩形：每条边拆成 nseg 段，节点随机偏移 1~2px。"""
    pts = []
    def seg(x0, y0, x1, y1):
        for i in range(nseg + 1):
            t = i / nseg
            jx = rng.uniform(-1.2, 1.2) if 0 < i < nseg else 0
            jy = rng.uniform(-1.2, 1.2) if 0 < i < nseg else 0
            pts.append((x0 + (x1 - x0) * t + jx, y0 + (y1 - y0) * t + jy))
    seg(x, y, x + w, y)
    seg(x + w, y, x + w, y + h)
    seg(x + w, y + h, x, y + h)
    seg(x, y + h, x, y)
    d = f"M {pts[0][0]:.1f},{pts[0][1]:.1f} " + " ".join(
        f"L {px:.1f},{py:.1f}" for px, py in pts[1:])
    return (f'<path d="{d}" fill="{fill}" stroke="{stroke}" '
            f'stroke-width="{sw}" stroke-linecap="round" '
            f'stroke-linejoin="round"/>')


def sketch_line(x0, y0, x1, y1, stroke=STROKE, sw=2.0, arrow=False,
                bow=0.0):
    """手绘直线（可带弧度与箭头）。bow>0 时用二次贝塞尔做轻微弯曲。"""
    if bow:
        mx, my = (x0 + x1) / 2, (y0 + y1) / 2
        dx, dy = x1 - x0, y1 - y0
        mx, my = mx - dy * bow, my + dx * bow
        d = (f"M {x0:.1f},{y0:.1f} Q {mx:.1f},{my:.1f} "
             f"{x1:.1f},{y1:.1f}")
    else:
        d = f"M {x0:.1f},{y0:.1f} L {x1:.1f},{y1:.1f}"
    out = [f'<path d="{d}" fill="none" stroke="{stroke}" '
           f'stroke-width="{sw}" stroke-linecap="round" '
           f'stroke-linejoin="round"/>']
    if arrow:
        ang = math.atan2(y1 - y0, x1 - x0) if not bow else \
            math.atan2(y1 - my, x1 - mx)
        L = 9.0
        for da in (math.radians(152), math.radians(-152)):
            ax = x1 + L * math.cos(ang + da)
            ay = y1 + L * math.sin(ang + da)
            out.append(f'<path d="M {x1:.1f},{y1:.1f} L {ax:.1f},{ay:.1f}" '
                       f'fill="none" stroke="{stroke}" stroke-width="{sw}" '
                       f'stroke-linecap="round"/>')
    return "".join(out)


def sketch_dash(x0, y0, x1, y1, stroke=MUTED, sw=1.6):
    d = f"M {x0:.1f},{y0:.1f} L {x1:.1f},{y1:.1f}"
    return (f'<path d="{d}" fill="none" stroke="{stroke}" '
            f'stroke-width="{sw}" stroke-linecap="round" '
            f'stroke-dasharray="7 6"/>')


def header(w, h, title, sub):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" '
            f'height="{h}" viewBox="0 0 {w} {h}">\n'
            f'<rect width="{w}" height="{h}" fill="{BG}"/>\n'
            + txt(40, 38, title, 20, INK, bold=True) + "\n"
            + txt(40, 61, sub, 12, MUTED) + "\n")


def badge(x, y, s, color, w=None):
    """小圆角标签（手绘矩形 + 居中文字）。"""
    w = w or (10 + 11.5 * max(len(s), 1) * (1 if s.isascii() else 0.95))
    p = [sketch_rect(x, y, w, 22, TINT["white"], color, 1.8, 4)]
    p.append(txt(x + w / 2, y + 15, s, 11, color, "middle", bold=True))
    return "".join(p), w


def save(name: str, parts: list[str]) -> None:
    svg = "".join(parts) + "</svg>\n"
    (OUT / name).write_text(svg, encoding="utf-8")
    print(f"written {name} ({len(svg)} bytes)")


# ===================== 图 1：全局定位（第二阶段地图 + 四站管道） =====================

def img_overview() -> list[str]:
    W, H = 1200, 900
    p = [header(W, H,
                "第 56 天：第 8 周复盘——从 Dialect 定义到图优化，一条 IR 的四站旅程",
                "上：第二阶段（Day 29~56）四周能力地图｜中：今天串起来的四站管道｜下：两个复盘问题")]
    # ---- 上：四周能力地图 ----
    p.append(txt(40, 100, "① 第二阶段地图：四周攒下的能力，今天第一次串成一条管道", 13, INK, bold=True))
    weeks = [
        ("第 5 周 Day 29~35", "MLIR 的 IR 结构",
         ["Operation / Value / Region", "Type / Attribute / Dialect", "跑通 Toy 示例"], "blue"),
        ("第 6 周 Day 36~42", "定义 mini Dialect",
         ["ODS 定义 6+ 个算子", "手写 Verifier 闸门", "mini-opt 能解析验证"], "blue"),
        ("第 7 周 Day 43~49", "Shape 推导与规范化",
         ["Shape Inference Pass", "Fold 常量折叠", "RewritePattern 三步接力"], "orange"),
        ("第 8 周 Day 50~56", "算子融合",
         ["fused 算子两大家族", "Pattern 集最终形态", "正负例总验收（D55）"], "green"),
    ]
    x0, y0, cw, ch, gap = 48, 116, 262, 172, 18
    for i, (wk, theme, items, col) in enumerate(weeks):
        x = x0 + i * (cw + gap)
        today = (i == 3)
        p.append(sketch_rect(x, y0, cw, ch, TINT["white"],
                             GREEN if today else STROKE, 2.6 if today else 2.0))
        p.append(txt(x + 14, y0 + 26, wk, 12.5, GREEN if today else MUTED, bold=True))
        p.append(txt(x + 14, y0 + 50, theme, 14.5, INK, bold=True))
        for j, it in enumerate(items):
            p.append(txt(x + 16, y0 + 76 + j * 22, "· " + it, 11.5, INK))
        if i < 3:
            p.append(sketch_line(x + cw, y0 + ch / 2, x + cw + gap,
                                 y0 + ch / 2, STROKE, 2.0, arrow=True))
    # 里程碑标注
    p.append(sketch_rect(48, 306, 1104, 40, TINT["green"], GREEN, 1.8, 5))
    p.append(txt(600, 331,
                 "第 56 天里程碑（计划原文）：自定义 MLIR Dialect、Shape 推导、常量折叠和算子融合 —— 今天全部接进同一条管道",
                 12, GREEN, "middle", bold=True))
    # ---- 中：四站管道 ----
    p.append(txt(40, 392, "② 今天的旅程管道：一张 IR（journey.mlir，8 个 mini.* 算子）顺序过四站", 13, INK, bold=True))
    stations = [
        ("站 1 验证", "parse + verify", "守合法性：结构/形状/f32", "只裁决，不改图", "red"),
        ("站 2 推导", "Shape 推导", "补信息：?x2 细化为 2x2", "只补类型，不删算子", "orange"),
        ("站 3 折叠", "fold + 死常量收尾", "算值：add(0.5,0.5)→1.0", "fold 不碰图，DCE 收尸", "blue"),
        ("站 4 融合", "P1/P2/P51g/P3", "改结构：3+2 算子并成 2 个", "先查后改 + use 表铁律", "green"),
    ]
    sx, sy, sw_, sh, sgap = 48, 408, 204, 130, 14
    p.append(sketch_rect(sx, sy + 18, 76, 94, TINT["gray"], STROKE, 2.0))
    p.append(txt(sx + 38, sy + 58, "输入 IR", 11.5, INK, "middle", bold=True))
    p.append(txt(sx + 38, sy + 78, "8 个算子", 10.5, MUTED, "middle"))
    p.append(txt(sx + 38, sy + 96, "?x2 待细化", 10, RED, "middle"))
    p.append(sketch_line(sx + 76, sy + 65, sx + 76 + sgap - 4, sy + 65,
                         STROKE, 2.0, arrow=True))
    for i, (name, mech, duty, note, col) in enumerate(stations):
        x = sx + 94 + sgap + i * (sw_ + sgap)
        p.append(sketch_rect(x, sy, sw_, sh, TINT["white"], STROKE, 2.0))
        bw, _ = badge(x + 12, sy + 10, name, {"red": RED, "orange": ORANGE,
                                              "blue": BLUE, "green": GREEN}[col])
        p.append(txt(x + 12, sy + 56, mech, 11.5, INK, bold=True))
        p.append(txt(x + 12, sy + 78, duty, 11, INK))
        p.append(txt(x + 12, sy + 98, note, 10, MUTED))
        p.append(sketch_line(x + sw_, sy + sh / 2, x + sw_ + sgap,
                             sy + sh / 2, STROKE, 2.0, arrow=True))
    ox = sx + 94 + sgap + 4 * (sw_ + sgap)
    p.append(sketch_rect(ox, sy + 18, 96, 94, TINT["green"], GREEN, 2.2))
    p.append(txt(ox + 48, sy + 58, "终点 IR", 11.5, INK, "middle", bold=True))
    p.append(txt(ox + 48, sy + 78, "3 个算子", 10.5, GREEN, "middle", bold=True))
    p.append(txt(ox + 48, sy + 96, "类型全静态", 10, GREEN, "middle"))
    p.append(txt(40, 578,
                 "每一站出口都复查 verify（真实记录：主线四站全部「通过」）——失败即短路，不让坏图流到下一站",
                 11.5, MUTED))
    # ---- 下：两个复盘问题 ----
    p.append(txt(40, 620, "③ 今天的两个复盘问题（计划原文的两个产出要求）", 13, INK, bold=True))
    q = [
        ("复盘一问：完整流程", "一个输入 IR 如何经过验证、Shape 推导、折叠和融合？",
         "用 mini-journey 把四站跑给读者看：8 → 8 → 8 → 6 → 3，每站 dump IR + 计数 + 决策日志",
         "＋ 15 分钟讲解时间轴（工具自动生成，数字来自本次运行）", "blue"),
        ("复盘二问：融合的本质", "「融合为什么不仅是图模式替换？」",
         "结构匹配只是入场券：还要 use-def 守恒（shared 卡在半融合）、信息前置（? 护栏）、数值语义（f32 闸门）",
         "＋ 收益判断是第 74 天的账，今天只画线不判账", "orange"),
    ]
    for i, (t, q1, q2, q3, col) in enumerate(q):
        x = 48 + i * 560
        p.append(sketch_rect(x, 636, 544, 150, TINT["white"], STROKE, 2.2))
        p.append(txt(x + 18, 664, t, 13.5,
                     {"blue": BLUE, "orange": ORANGE}[col], bold=True))
        p.append(txt(x + 18, 692, "Q: " + q1, 12, INK, bold=True))
        p.append(txt(x + 18, 718, "A: " + q2, 11.5, INK))
        p.append(txt(x + 18, 744, q3, 11, MUTED))
    p.append(txt(40, 830,
                 "下一天预告：Day 57 进入第三阶段——逻辑 Shape 与物理布局（Stride / Offset / Contiguous），图结构之外的新维度",
                 11.5, MUTED))
    return p


# ===================== 图 2：核心机制（四站旅程的逐步演化） =====================

def img_journey_stations() -> list[str]:
    W, H = 1240, 960
    p = [header(W, H,
                "图解机制：journey.mlir 的四站旅程（全部数字来自真实运行）",
                "上：起点与终点的数据流图｜中：四张站卡——每站做什么、为什么、剩几个算子｜下：计数条 8→8→8→6→3")]
    # ---- 上左：起点 ----
    p.append(txt(48, 96, "起点：journey.mlir（8 个 mini.*，两条链）", 12.5, INK, bold=True))
    bx, by = 48, 106
    p.append(sketch_rect(bx, by, 556, 240, TINT["white"], STROKE, 2.2))
    # 链 1（上排）：c0,c1 -> add(one) ；a,b -> matmul -> add -> relu
    def node(x, y, label, w=66, h=26, color=STROKE, fill="#ffffff", fs=10.5):
        p.append(sketch_rect(x, y, w, h, fill, color, 1.8, 4))
        p.append(txt(x + w / 2, y + 17, label, fs, INK, "middle"))
    node(bx + 22, by + 34, "c0 = 0.5", 62)
    node(bx + 22, by + 78, "c1 = 0.5", 62)
    node(bx + 126, by + 56, "add", 48)
    node(bx + 232, by + 24, "matmul", 60, 26, ORANGE)
    node(bx + 336, by + 56, "add", 48)
    node(bx + 440, by + 56, "relu", 48)
    p.append(sketch_line(bx + 84, by + 47, bx + 126, by + 60, STROKE, 1.6, arrow=True))
    p.append(sketch_line(bx + 84, by + 91, bx + 126, by + 72, STROKE, 1.6, arrow=True))
    p.append(sketch_line(bx + 174, by + 69, bx + 232, by + 42, STROKE, 1.6, arrow=True, bow=0.05))
    p.append(txt(bx + 238, by + 14, "a(2x3) · b(3x2)", 10, MUTED))
    p.append(txt(bx + 296, by + 42, "?x2", 11, RED, bold=True))
    p.append(sketch_line(bx + 292, by + 37, bx + 336, by + 66, STROKE, 1.6, arrow=True))
    p.append(sketch_line(bx + 384, by + 69, bx + 440, by + 69, STROKE, 1.6, arrow=True))
    p.append(txt(bx + 408, by + 86, "%one", 9.5, MUTED, "middle"))
    p.append(sketch_line(bx + 152, by + 69, bx + 152, by + 66, STROKE, 1.2))
    p.append(txt(bx + 490, by + 69, "→ out1", 10, MUTED))
    # 链 2（下排）
    p.append(sketch_dash(bx + 30, by + 128, bx + 520, by + 128, "#d8d2c6", 1.4))
    node(bx + 60, by + 152, "add", 48)
    node(bx + 164, by + 152, "relu", 48)
    p.append(txt(bx + 66, by + 142, "x · w (2x2)", 10, MUTED))
    p.append(sketch_line(bx + 108, by + 165, bx + 164, by + 165, STROKE, 1.6, arrow=True))
    p.append(txt(bx + 218, by + 165, "→ out2", 10, MUTED))
    p.append(txt(bx + 290, by + 172,
                 "看点：matmul 结果类型故意写 ?x2（待推导）；", 11, INK))
    p.append(txt(bx + 290, by + 190,
                 "add(0.5,0.5) 是折叠站的原料；两条链分别是", 11, INK))
    p.append(txt(bx + 290, by + 208,
                 "大融合（matmul+bias+relu）与小融合（add+relu）的目标。", 11, INK))
    # ---- 上右：终点 ----
    p.append(txt(652, 96, "终点：3 个 mini.*，类型全静态", 12.5, INK, bold=True))
    ex, ey = 652, 106
    p.append(sketch_rect(ex, ey, 540, 240, TINT["green"], GREEN, 2.2))
    node(ex + 40, ey + 40, "constant 1.0", 96, 28, GREEN, TINT["green"])
    node(ex + 40, ey + 110, "fused_matmul_bias_relu", 208, 30, GREEN, TINT["green"], 11)
    node(ex + 40, ey + 170, "fused_add_relu", 130, 28, GREEN, TINT["green"])
    p.append(txt(ex + 70, ey + 96,
                 "a · b · one(=1.0)  →  relu(a·b + 1.0)", 10.5, MUTED))
    p.append(txt(ex + 190, ey + 156, "x · w  →  relu(x + w)", 10.5, MUTED))
    p.append(txt(ex + 272, ey + 55, "站 3 的产物", 10, ORANGE))
    p.append(txt(ex + 272, ey + 128, "站 4 大融合（P3）", 10, GREEN))
    p.append(txt(ex + 272, ey + 188, "站 4 小融合（P51g）", 10, GREEN))
    p.append(txt(ex + 300, ey + 216, "8 → 3，verify 复查通过", 12, GREEN, bold=True))
    # ---- 中：四张站卡 ----
    cards = [
        ("站 1 验证", "8 → 8", RED,
         ["parse：文本按注册表变 IR", "verify：结构/形状/f32 裁决",
          "? 维保守放行（待推导）", "f64/错形状在此拦截短路"],
         "守合法性，只裁决不改图"),
        ("站 2 推导", "8 → 8", ORANGE,
         ["matmul：?x2 细化为 2x2", "add/relu：结果类型跟随",
          "函数签名：返回类型同步", "refine：数字保留，? 才采纳"],
         "补信息，不动图"),
        ("站 3 折叠", "8 → 6", BLUE,
         ["fold：add(0.5,0.5) → 1.0", "物化：属性变回 constant",
          "DCE：死掉的 c0/c1 收走", "护栏：类型不一致就收手"],
         "只算值，不碰图"),
        ("站 4 融合", "6 → 3", GREEN,
         ["P3：matmul+add+relu 并一", "P51g：add+relu 并一（让位版）",
          "先查后改：use 表/闸门/护栏", "替换使用者，再擦旧算子"],
         "改结构，语义不变"),
    ]
    cw, chh, cy = 274, 320, 470
    for i, (name, cnt, col, items, motto) in enumerate(cards):
        x = 48 + i * (cw + 14)
        p.append(sketch_rect(x, cy, cw, chh, TINT["white"], STROKE, 2.2))
        p.append(sketch_rect(x + 12, cy + 12, cw - 24, 34, TINT["white"], col, 2.0, 4))
        p.append(txt(x + cw / 2, cy + 34, name + "   " + cnt, 13.5, col, "middle", bold=True))
        for j, it in enumerate(items):
            p.append(txt(x + 18, cy + 70 + j * 26, "· " + it, 11.5, INK))
        p.append(txt(x + 18, cy + 70 + 4 * 26 + 6, "口诀: " + motto, 11, col, bold=True))
        # 站与站之间的箭头
        if i < 3:
            p.append(sketch_line(x + cw, cy + 30, x + cw + 14, cy + 30,
                                 STROKE, 2.2, arrow=True))
    # ---- 下：计数条 ----
    p.append(txt(48, 830, "四站计数条（真实运行：journey-main.out 的汇总表）", 12.5, INK, bold=True))
    steps = [("输入", 8, MUTED), ("站1 验证", 8, RED), ("站2 推导", 8, ORANGE),
             ("站3 折叠", 6, BLUE), ("站4 融合", 3, GREEN)]
    bx2, by2 = 60, 846
    for i, (name, n, col) in enumerate(steps):
        x = bx2 + i * 232
        p.append(sketch_rect(x, by2, 200, 64, TINT["white"], col, 2.2))
        p.append(txt(x + 100, by2 + 28, str(n), 22, col, "middle", bold=True))
        p.append(txt(x + 100, by2 + 50, name, 11, INK, "middle"))
        if i < 4:
            p.append(sketch_line(x + 200, by2 + 32, x + 232, by2 + 32,
                                 STROKE, 2.0, arrow=True))
    p.append(txt(60, 938,
                 "每站出口复查 verify：主线四站全部通过——坏图不流到下一站（journey_bad 在站 1 就被拦下）",
                 11, MUTED))
    return p


# ===================== 图 3：融合为什么不仅是图模式替换 =====================

def img_fusion_duties() -> list[str]:
    W, H = 1240, 900
    p = [header(W, H,
                "复盘核心问答：融合为什么不仅是图模式替换？",
                "左：你以为的融合＝图同构替换｜右：模式替换不管、但缺一不可的四件事（各配今天的真实负例）")]
    # ---- 左：模式替换视角 ----
    lx, ly = 48, 96
    p.append(sketch_rect(lx, ly, 380, 470, TINT["white"], STROKE, 2.2))
    p.append(txt(lx + 20, ly + 32, "「只是模式替换」的世界观", 14, RED, bold=True))
    # 三个小盒竖排（左）
    for i, name in enumerate(["matmul", "add", "relu"]):
        yy = ly + 56 + i * 58
        p.append(sketch_rect(lx + 36, yy, 120, 40, "#ffffff", STROKE, 1.8, 4))
        p.append(txt(lx + 96, yy + 25, name, 12, INK, "middle"))
    # 右侧大盒（fused）
    p.append(sketch_rect(lx + 212, ly + 70, 140, 172, TINT["red"], RED, 2.2, 5))
    p.append(txt(lx + 282, ly + 130, "fused_", 12, INK, "middle"))
    p.append(txt(lx + 282, ly + 150, "matmul_bias", 11, INK, "middle"))
    p.append(txt(lx + 282, ly + 170, "_relu", 11, INK, "middle"))
    # 汇流箭头：三个盒子的输出并成一支，指向大盒
    midy = ly + 142
    p.append(sketch_line(lx + 156, ly + 76, lx + 184, midy, STROKE, 1.8))
    p.append(sketch_line(lx + 156, ly + 134, lx + 184, midy, STROKE, 1.8))
    p.append(sketch_line(lx + 156, ly + 192, lx + 184, midy, STROKE, 1.8))
    p.append(sketch_line(lx + 184, midy, lx + 212, midy, RED, 2.4, arrow=True))
    p.append(txt(lx + 170, midy - 8, "重写为", 10.5, RED, "middle"))
    p.append(txt(lx + 36, ly + 268, "结构匹配 ✓  这一步只是「图同构匹配」：", 12, INK, bold=True))
    p.append(txt(lx + 20, ly + 294, "左边的链长得像模板，就换成一个等", 11.5, INK))
    p.append(txt(lx + 20, ly + 314, "价的大算子。它一个字都不用多说，", 11.5, INK))
    p.append(txt(lx + 20, ly + 334, "但也回答不了右边四个问题：", 11.5, INK))
    for j, s in enumerate(["· 中间结果还有人用，删得掉吗？",
                           "· 类型/形状信息齐了吗？",
                           "· 换完之后数值还对吗？",
                           "· 换完真的更快吗？"]):
        p.append(txt(lx + 20, ly + 364 + j * 24, s, 11.5, RED))
    p.append(txt(lx + 20, ly + 452, "—— 右边四件事，才是融合的另外半条命", 11, MUTED))
    # ---- 右：四件事 ----
    duties = [
        ("① use-def 守恒", "删除的前提是 use 表为空（第 52 天铁律）", BLUE,
         "shared 用例：加法结果被 return 共用",
         "日志：融合结果有 2 个使用者 -> 不能吸收 Relu",
         "终点停在半融合不动点（fused_matmul_bias + relu）"),
        ("② 信息前置", "重写被护栏拦下时，缺的不是遍数，是信息", ORANGE,
         "skip-infer 用例：?x2 没人细化",
         "日志：乘积类型含动态维（?）-> 拒绝",
         "大融合缺席，终点 5 个算子、? 残留（8→5 而非 8→3）"),
        ("③ 数值语义", "融合算子的语义要有人担保（第 55 天闸门）", GREEN,
         "f64 用例：fused* 语义只对 f32 验证过",
         "闸门：元素类型非全 f32 -> 拒绝",
         "叠加验证：融合前后 evaluate 对账（Python 层 R3）"),
        ("④ 收益判断", "「更快」是另一本账（今天只画线不判账）", MUTED,
         "第 74 天的 CostModel",
         "融合省下中间张量的读写（记账 8→4）",
         "布局/流水线/bank 冲突都还没进模型，先别下结论"),
    ]
    dx, dy, dw, dh = 470, 96, 722, 118
    for i, (name, key, col, case, log, note) in enumerate(duties):
        y = dy + i * (dh + 12)
        p.append(sketch_rect(dx, y, dw, dh, TINT["white"], STROKE, 2.0))
        p.append(txt(dx + 18, y + 26, name, 13.5, col, bold=True))
        p.append(txt(dx + 18, y + 47, key, 11, MUTED))
        p.append(txt(dx + 18, y + 68, "负例: " + case, 11.5, INK, bold=True))
        p.append(txt(dx + 18, y + 87, log, 11, col if col != MUTED else INK,
                     opacity=0.95))
        p.append(txt(dx + 18, y + 105, note, 11, INK))
    # 底部结论
    p.append(sketch_rect(48, 620, 1144, 52, TINT["green"], GREEN, 2.0, 5))
    p.append(txt(620, 651,
                 "一句话：结构匹配只是入场券——删得掉（use 表）、算得出（信息齐）、算得对（语义担保）、（将来）划得来（CostModel），缺一不可",
                 12.5, GREEN, "middle", bold=True))
    # 底部补充：今天四个用例怎么对应这四件事
    p.append(txt(48, 706, "今天的四个用例正好把这四件事各验一遍（全部真实运行）：", 12.5, INK, bold=True))
    rows = [
        ("main", "8 → 3", "四关全过：验证→推导→折叠→融合一路绿灯", GREEN),
        ("shared", "3 → 2", "第①关把守：use 表不答应，停在半融合", BLUE),
        ("skip-infer", "8 → 5", "第②关把守：? 护栏拒绝，大融合缺席", ORANGE),
        ("bad", "站 1 拦截", "第③关的 Verifier 侧：f64 图根本进不了管道", RED),
    ]
    for i, (name, res, why, col) in enumerate(rows):
        x = 48 + (i % 2) * 578
        y = 720 + (i // 2) * 74
        p.append(sketch_rect(x, y, 566, 62, TINT["white"], col, 2.0))
        p.append(txt(x + 16, y + 26, name, 13, col, bold=True))
        p.append(txt(x + 16, y + 48, res, 12.5, INK, bold=True))
        p.append(txt(x + 150, y + 37, why, 11.5, INK))
    return p


# ===================== 图 4：真实结果对照 =====================

def img_results() -> list[str]:
    W, H = 1200, 860
    p = [header(W, H,
                "真实结果：四站计数、三个对照实验与验收记录（2026-11-12 实测）",
                "左：主线各站计数表｜中：三个对照的判决与日志｜右：14/14 断言 + 22/22 测试 + 复跑命令")]
    # ---- 左：计数表 ----
    p.append(txt(48, 96, "① 主线：journey.mlir 四站计数（真实）", 12.5, INK, bold=True))
    tx, ty = 48, 108
    rows = [
        ("站点", "mini.*", "这一站发生的事", True),
        ("输入", "8", "两条链：大融合原料 + 小融合原料", False),
        ("站 1 验证", "8", "parse+verify 通过（只裁决）", False),
        ("站 2 推导", "8", "?x2 → 2x2；签名同步细化（类型变）", False),
        ("站 3 折叠", "6", "add(0.5,0.5)→1.0；死常量被收走", False),
        ("站 4 融合", "3", "P3 三算子 + P51g 小融合", False),
    ]
    col2 = [MUTED, GREEN, RED, ORANGE, BLUE, GREEN]
    for i, (a, b, c, is_head) in enumerate(rows):
        y = ty + i * 40
        if is_head:
            p.append(sketch_rect(tx, y, 500, 34, TINT["gray"], STROKE, 1.8, 4))
        elif i % 2 == 0:
            p.append(sketch_rect(tx, y, 500, 34, TINT["white"], "#00000000", 0.001, 4))
        p.append(txt(tx + 16, y + 22, a, 11.5, INK if not is_head else MUTED, bold=not is_head))
        p.append(txt(tx + 130, y + 22, b, 12.5, col2[i] if not is_head else MUTED,
                     bold=not is_head))
        p.append(txt(tx + 176, y + 22, c, 11, INK if not is_head else MUTED))
    p.append(txt(48, 372, "类型演化：?x2 ──站2──> 2x2（三个值 + 函数签名）", 11.5, ORANGE, bold=True))
    p.append(txt(48, 394, "每站 verify 复查：通过 × 4；终点形态：", 11.5, INK))
    p.append(txt(48, 416, "constant(1.0) + fused_matmul_bias_relu + fused_add_relu", 11, GREEN, bold=True))
    # ---- 中：三个对照 ----
    p.append(txt(580, 96, "② 三个对照实验（同一工具、同一管道）", 12.5, INK, bold=True))
    cases = [
        ("skip-infer", "8 → 5 · verdict=fused", ORANGE,
         ["大融合被 ? 护栏拦下（日志：乘积类型含动态维（?）→ 拒绝）",
          "小融合照常（静态类型不受影响）",
          "终点仍含 ?x2 —— 信息不齐，迭代再多也放不了行"]),
        ("shared", "3 → 2 · verdict=fused", BLUE,
         ["P3 融合 matmul+add，但不吸收 relu（%s 有两个使用者）",
          "P2 复查：融合结果有 2 个使用者 → 不能吸收 Relu",
          "半融合不动点：fused_matmul_bias + relu"]),
        ("bad", "站 1 拦截 · verifier_reject", RED,
         ["f64 的 matmul 在 parse+verify 就报错（元素类型必须是 f32）",
          "后续三站短路 —— 验证站在最前面",
          "报错留在 outputs/journey-bad.err，有据可查"]),
    ]
    for i, (name, res, col, items) in enumerate(cases):
        y = 108 + i * 120
        p.append(sketch_rect(580, y, 572, 108, TINT["white"], col, 2.2))
        p.append(txt(598, y + 26, name, 13, col, bold=True))
        p.append(txt(700, y + 26, res, 11.5, INK, bold=True))
        for j, it in enumerate(items):
            p.append(txt(598, y + 50 + j * 20, "· " + it, 10.8, INK))
    # ---- 右下：验收记录 ----
    p.append(txt(48, 480, "③ 验收记录（全部本次实测）", 12.5, INK, bold=True))
    p.append(sketch_rect(48, 492, 1104, 156, TINT["white"], STROKE, 2.2))
    p.append(txt(70, 522, "run_all.sh 断言：14 通过 / 0 失败", 13, GREEN, bold=True))
    p.append(txt(70, 548, "test_journey.py：22 通过 / 0 失败（T1 主线 9 + T2 对照 5 + T3 半融合 3 + T4 拦截 3 + T5 职责 2）", 12, GREEN, bold=True))
    p.append(txt(70, 574, "四站 verify 复查 ×4、判决与期望全部吻合（verdict=accept=PASS）", 12, INK))
    p.append(txt(70, 600, "拆闸门对照（--skip-infer）：融合确实卡住、日志确实报警 —— 管道是活的", 12, INK))
    p.append(txt(70, 630, "复跑命令：", 12, INK, bold=True))
    p.append(txt(70, 654, "cd tutorials/day-056/code/mlir-mini && ninja -C build && bash run_all.sh", 11, BLUE))
    p.append(txt(70, 676, "cd tutorials/day-056/code && python3 test_journey.py", 11, BLUE))
    # ---- 底部：环境 ----
    p.append(sketch_rect(48, 700, 1104, 40, TINT["gray"], STROKE, 1.8, 5))
    p.append(txt(600, 725,
                 "环境：g++ 9.4.0 · Ubuntu LLVM 18.1.8（mlir-tblgen / MLIRConfig）· aarch64 Linux · Python 3.11.4 —— 与 Day 29~55 记录一致",
                 11, MUTED, "middle"))
    # 底部一句话
    p.append(txt(48, 780,
                 "复盘结论：第 55 天把「能融的边界」画完；今天把四周的能力接进同一条管道，", 12, INK))
    p.append(txt(48, 802,
                 "让 8 → 3 的每一步都有据可查——这才是「从 Dialect 定义到图优化的完整流程」的可运行版本。", 12, INK))
    return p


def main() -> None:
    save("01-overview.svg", img_overview())
    save("02-journey-stations.svg", img_journey_stations())
    save("03-fusion-three-duties.svg", img_fusion_duties())
    save("04-results.svg", img_results())


if __name__ == "__main__":
    main()
