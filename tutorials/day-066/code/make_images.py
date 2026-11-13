#!/usr/bin/env python3
"""make_images.py —— 第 66 天（连续 Reshape 合并）教程的四张手绘 sketch 风 SVG 信息图。

风格约定（与第 8/9/10 周各天一致，Excalidraw-like）：
  - 背景 #fdfaf2（米白），盒子白底 + 深灰 #6b6357 手绘描边
  - 强调色不超过 4 种柔和色：蓝 #4a7fa5 / 橙 #a8772e / 绿 #5a8a5a / 红 #b0605a
  - 线条带轻微抖动（L 段折线），圆头笔触，线宽 2 左右
  - 手写感字体栈：Comic Sans MS / Comic Neue / Kaiti SC / 楷体 / cursive
  - 只用矩形、格子条、括号线、箭头等简单几何形状

图中全部数字来自 2026-11-12 的真实运行（code/outputs/）：
  reshape_merge_lab 22/22；test_reshape_merge 30/30；
  tensor.reshape 链 --canonicalize 原样保留（2 个 reshape）；
  collapse/expand 连链折叠成单 op [[0, 1, 2]]；互逆对消除为 return %arg0；
  非互逆 collapse→expand 保留 2 个 op；
  判定表 12/12；随机链 300/300（944 op → 271，28.7%）；
  view/copy 现场：连续输入全视图、非连续第一跳拷贝一次；
  混 order：C∘F ≠ 任何单个 reshape（numpy 实测）。

运行：python3 make_images.py   （在 code/ 目录下，输出到 ../images/）
"""

from __future__ import annotations

import math
import random
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "images"
OUT.mkdir(parents=True, exist_ok=True)

FONT = ("Comic Sans MS, Comic Neue, Segoe Print, Kaiti SC, KaiTi, 楷体, "
        "cursive")
INK = "#3b352d"
MUTED = "#84796a"
STROKE = "#6b6357"
BG = "#fdfaf2"
BLUE, ORANGE, GREEN, RED = "#4a7fa5", "#a8772e", "#5a8a5a", "#b0605a"
TINT = {"blue": "#eef3f7", "orange": "#f8f0e2", "green": "#edf4ee",
        "red": "#f7ecea", "white": "#ffffff", "gray": "#f1efe9"}

rng = random.Random(66)


def esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;")
             .replace(">", "&gt;"))


def txt(x, y, s, size=12, fill=INK, anchor="start", bold=False, opacity=1.0):
    w = 'font-weight="bold"' if bold else 'font-weight="normal"'
    return (f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" '
            f'fill="{fill}" text-anchor="{anchor}" opacity="{opacity}" '
            f'{w}>{esc(s)}</text>')


def sketch_rect(x, y, w, h, fill="#ffffff", stroke=STROKE, sw=2.2, nseg=6):
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
                opacity=1.0, dashed=False):
    if dashed:
        main = (f'<path d="M {x0:.1f},{y0:.1f} L {x1:.1f},{y1:.1f}" '
                f'fill="none" stroke="{stroke}" stroke-width="{sw}" '
                f'stroke-linecap="round" stroke-dasharray="7 6" '
                f'opacity="{opacity}"/>')
    else:
        main = (f'<path d="M {x0:.1f},{y0:.1f} L {x1:.1f},{y1:.1f}" '
                f'fill="none" stroke="{stroke}" stroke-width="{sw}" '
                f'stroke-linecap="round" stroke-linejoin="round" '
                f'opacity="{opacity}"/>')
    out = [main]
    if arrow:
        ang = math.atan2(y1 - y0, x1 - x0)
        L, A = 11, 0.5
        ax, ay = x1 - L * math.cos(ang), y1 - L * math.sin(ang)
        out.append(f'<path d="M {x1:.1f},{y1:.1f} L {ax:.1f},{ay - 4:.1f}" '
                   f'fill="none" stroke="{stroke}" stroke-width="{sw}" '
                   f'stroke-linecap="round" opacity="{opacity}"/>')
        out.append(f'<path d="M {x1:.1f},{y1:.1f} L {ax:.1f},{ay + 4:.1f}" '
                   f'fill="none" stroke="{stroke}" stroke-width="{sw}" '
                   f'stroke-linecap="round" opacity="{opacity}"/>')
    return "".join(out)


def sketch_path(points, stroke=STROKE, sw=2.0, arrow=False, opacity=1.0,
                curved=False):
    """多点连线（可微弯），用于连接线。"""
    pts = []
    for k in range(len(points) - 1):
        (x0, y0), (x1, y1) = points[k], points[k + 1]
        n = 4
        for i in range(n + 1):
            if k > 0 and i == 0:
                continue
            t = i / n
            jx = rng.uniform(-1.5, 1.5) if 0 < i < n else 0
            jy = rng.uniform(-1.5, 1.5) if 0 < i < n else 0
            if curved:
                jx += rng.uniform(-4, 4)
            bx = x0 + (x1 - x0) * t + jx * (0.3 if curved else 1.0)
            by = y0 + (y1 - y0) * t + jy * (0.3 if curved else 1.0)
            pts.append((bx, by))
    d = f"M {pts[0][0]:.1f},{pts[0][1]:.1f} " + " ".join(
        f"L {px:.1f},{py:.1f}" for px, py in pts[1:])
    out = [f'<path d="{d}" fill="none" stroke="{stroke}" stroke-width="{sw}" '
           f'stroke-linecap="round" stroke-linejoin="round" '
           f'opacity="{opacity}"/>']
    if arrow:
        (x0, y0), (x1, y1) = points[-2], points[-1]
        ang = math.atan2(y1 - y0, x1 - x0)
        L = 11
        ax, ay = x1 - L * math.cos(ang), y1 - L * math.sin(ang)
        out.append(f'<path d="M {x1:.1f},{y1:.1f} L {ax:.1f},{ay - 4:.1f}" '
                   f'fill="none" stroke="{stroke}" stroke-width="{sw}" '
                   f'stroke-linecap="round" opacity="{opacity}"/>')
        out.append(f'<path d="M {x1:.1f},{y1:.1f} L {ax:.1f},{ay + 4:.1f}" '
                   f'fill="none" stroke="{stroke}" stroke-width="{sw}" '
                   f'stroke-linecap="round" opacity="{opacity}"/>')
    return "".join(out)


def header(w, h, title, sub):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" '
            f'height="{h}" viewBox="0 0 {w} {h}">\n'
            f'<rect width="{w}" height="{h}" fill="{BG}"/>\n'
            + txt(40, 38, title, 20, INK, bold=True) + "\n"
            + txt(40, 61, sub, 12, MUTED) + "\n")


def save(name: str, body: str) -> None:
    path = OUT / name
    path.write_text(body + "</svg>\n", encoding="utf-8")
    print(f"写出 {path}（{path.stat().st_size} B）")


def bracket(x0, x1, y, label, color, drop=10, size=9.5):
    """方括号线：|____|，label 居中在下方。"""
    out = [sketch_line(x0, y, x0, y + drop, stroke=color, sw=1.8),
           sketch_line(x0, y + drop, x1, y + drop, stroke=color, sw=1.8),
           sketch_line(x1, y + drop, x1, y, stroke=color, sw=1.8)]
    out.append(txt((x0 + x1) / 2, y + drop + 13, label, size, color,
                   "middle", bold=True))
    return "".join(out)


# ===========================================================================
# 图 1：全貌——第 10 周第 3 天 + 两个 Pattern 在优化管道中的位置
# ===========================================================================

def fig1() -> None:
    W, H = 1020, 710
    b = [header(W, H, "第 66 天全貌：连续 Reshape 合并",
                 "阶段三「AI 计算图与图优化」· 第 10 周第 3 天 · 判据从「排列组合」换成「元素数量守恒」")]

    # 顶部：阶段条
    stages = [
        ("阶段一 1–28", "C++ 与图 IR", "gray"),
        ("阶段二 29–56", "MLIR Dialect", "gray"),
        ("阶段三 57–84", "图优化 · 今天", "orange"),
        ("阶段四 85–112", "Lowering/Tiling", "gray"),
        ("阶段五 113–140", "端到端/Runtime", "gray"),
    ]
    sx, sy, sw_, sh, gap = 40, 84, 178, 46, 10
    for i, (t1, t2, col) in enumerate(stages):
        x = sx + i * (sw_ + gap)
        b.append(sketch_rect(x, sy, sw_, sh, fill=TINT[col],
                             stroke=ORANGE if col == "orange" else STROKE,
                             sw=2.6 if col == "orange" else 2.0))
        b.append(txt(x + sw_ / 2, sy + 19, t1, 12, INK, "middle", bold=True))
        b.append(txt(x + sw_ / 2, sy + 36, t2, 10.5, MUTED, "middle"))
    b.append(txt(40, sy + 66,
                 "昨天（Day 65）Transpose 链消除交付两个 Pattern → 今天：同一副骨架，判据换成 numel 守恒；边界换成「被替换 vs 被删除」",
                 11.5, MUTED))

    # 中部：reshape 链 + 两个 Pattern 的裁决
    qy = 180
    b.append(sketch_rect(40, qy, 280, 124, fill=TINT["blue"], sw=2.4))
    b.append(txt(180, qy + 24, "图里的 Reshape 链", 14, BLUE, "middle",
                 bold=True))
    b.append(txt(180, qy + 48, "%t = Reshape(%in, s1)", 11.5, INK, "middle"))
    b.append(txt(180, qy + 66, "%c = Reshape(%t, s2)", 11.5, INK, "middle"))
    b.append(txt(180, qy + 90, "中间形状 s1 有没有必要留？", 11, MUTED,
                 "middle"))
    b.append(txt(180, qy + 108, "（B(2,3,4) → (6,4) → (24,)）", 10, MUTED,
                 "middle"))

    pats = [
        ("Pattern 1 恒等消除", "Reshape(x, shape(x)) → x",
         "链尾 == 输入形状；无需唯一使用者", "blue", 370),
        ("Pattern 2 链合并", "Reshape(Reshape(x,s1),s2) → Reshape(x,s2)",
         "中间值唯一使用者才删；order 须同为 C", "green", 680),
    ]
    for title, rule, note, col, fx in pats:
        b.append(sketch_rect(fx, qy, 300, 124, fill=TINT[col], sw=2.4))
        b.append(txt(fx + 150, qy + 24, title, 13.5,
                     {"blue": BLUE, "green": GREEN}[col], "middle", bold=True))
        b.append(txt(fx + 150, qy + 52, rule, 10.8, INK, "middle", bold=True))
        b.append(txt(fx + 150, qy + 80, note, 10, MUTED, "middle"))
        b.append(txt(fx + 150, qy + 106,
                     "P1 是 P2 合成恒等的特例（同昨天）", 10, MUTED, "middle"))
        b.append(sketch_path([(320, qy + 62), (fx, qy + 62)],
                             stroke=STROKE, sw=2.0, arrow=True, curved=True))

    # 中下：PassManager 迭代
    my = 332
    b.append(sketch_rect(40, my, 940, 84, fill="#ffffff", sw=2.2))
    b.append(txt(60, my + 26, "PassManager：迭代到不动点（实测）", 13, INK,
                 bold=True))
    b.append(txt(60, my + 50,
                 "五连链 B→(6,4)→(24,)→(2,12)→(24,1)→(12,2)：5 轮 4 次应用 → 单个 Reshape(%in, [12,2])（每轮合并一对）",
                 11.5, INK))
    b.append(txt(60, my + 72,
                 "最终 op 数由链尾一刀决定：链尾 == 输入形状 → 0，否则 → 1（D1：链长 1..6 全对；判定表 12/12）",
                 10.5, MUTED))

    # 底部：MLIR 实测对照
    by = 444
    b.append(txt(40, by, "MLIR 侧真实事实（本机 LLVM 18.1.8，--canonicalize 实测）：",
                 12, INK, bold=True))
    facts = [
        ("① tensor.reshape 链", "原样保留（2 个 reshape 都在）——stock 管道没有这条规则",
          "要自己写", "red"),
        ("② collapse / expand 连链", "折叠成单 op（reassociation 组合成 [[0, 1, 2]]）；互逆对消除为 return %arg0",
          "结构化信息自带组合规则", "green"),
        ("③ collapse→expand 非互逆", "原样保留 2 个 op——组合变换无法用单个 reassociative reshape 表达",
          "表达力换来了折叠边界", "orange"),
    ]
    fy = by + 14
    for t1, t2, t3, col in facts:
        b.append(sketch_rect(40, fy, 460, 46, fill=TINT[col], sw=2.0))
        b.append(txt(56, fy + 19, t1, 11.5,
                     {"red": RED, "green": GREEN, "orange": ORANGE}[col],
                     bold=True))
        b.append(txt(56, fy + 37, t2 + "——" + t3, 9.6, INK))
        fy += 54

    # 右下：验收汇总
    ay = by + 14
    b.append(sketch_rect(530, ay, 450, 142, fill=TINT["green"], sw=2.4))
    b.append(txt(546, ay + 24, "今日验收（全部真实运行）：", 12.5, GREEN,
                 bold=True))
    lines = [
        "主实验 22/22 · 验收测试 30/30（A–G 七段）",
        "判定表 12/12 · 随机链 300/300（944 op → 271，28.7%）",
        "view/copy 现场：连续输入全视图，非连续第一跳拷贝一次",
        "混 order：C∘F ≠ 任何单个 reshape（25 组 C∘C 全部成立）",
        "mlir-opt 实测 5 项裁决全部复现（outputs/ 留档）",
    ]
    for k, ln in enumerate(lines):
        b.append(txt(546, ay + 46 + k * 18, "· " + ln, 10.3, INK))

    # 明日预告条
    ny = 612
    b.append(sketch_rect(40, ny, 940, 40, fill="#ffffff", sw=2.0))
    b.append(txt(60, ny + 25, "明天（Day 67）：", 11.5, GREEN, bold=True))
    b.append(txt(178, ny + 25,
                 "Cast 消除——只消除输入输出类型完全一致的 Cast（今天的「恒等消除」骨架直接复用）",
                 11.5, INK))
    save("01-overview.svg", "".join(b))


# ===========================================================================
# 图 2：核心机制——numel 守恒 + 线性顺序「重新画分隔线」+ 合法性边界
# ===========================================================================

def fig2() -> None:
    W, H = 1060, 800
    b = [header(W, H, "核心机制：元素数量守恒，重新画分隔线",
                 "Reshape 不动元素的线性先后顺序，只改「每行放几个」——链 = 连画两次分隔线 = 只画最后一次 · 数字全部来自真实运行")]

    # 顶部：判据推导
    b.append(sketch_rect(40, 78, 980, 96, fill=TINT["blue"], sw=2.4))
    b.append(txt(60, 104, "判据（对比昨天：没有方向陷阱）", 12.5, BLUE,
                 bold=True))
    b.append(txt(60, 128, "单个合法：prod(in_shape) == prod(out_shape)（元素数量守恒，E2 关）；三关 Verifier：E1 维度≥1 → E2 numel → E3 order",
                 11.5, INK))
    b.append(txt(60, 152, "链合并：Reshape(Reshape(x, s1), s2) == Reshape(x, s2)——s1 从判据里完全消失（C3：5 种 s1 殊途同归）",
                 11.8, INK, bold=True))
    b.append(txt(960, 104, "C∘C 25 组 ✓ · 随机 300 组 ✓", 10, GREEN, "end",
                 bold=True))

    # 中部：线性顺序条 + 三种分隔方案
    fy = 196
    b.append(sketch_rect(40, fy, 980, 286, fill="#ffffff", sw=2.2))
    b.append(txt(60, fy + 24, "线性顺序与分隔线（贯穿例子 B(2,3,4) = 0..23）：",
                 13, INK, bold=True))
    cx, cy, cw, ch = 130, fy + 40, 26, 26
    for i in range(24):
        col = TINT["blue"] if i < 12 else TINT["orange"]
        b.append(sketch_rect(cx + i * cw, cy, cw - 3, ch - 4, fill=col,
                             sw=1.6, nseg=3))
        b.append(txt(cx + i * cw + (cw - 3) / 2, cy + 16, str(i), 9.5, INK,
                     "middle", bold=True))
    b.append(txt(130, cy + 42, "线性排列（行主序 C order）：元素的先后顺序在 reshape 前后不变",
                 10, MUTED))

    # 三条「分隔方案」标尺
    ry = cy + 66
    b.append(txt(60, ry + 8, "(2,3,4)", 11, INK, bold=True))
    b.append(txt(130, ry - 6, "原始形状：粗括号 2 组 ×（细括号 3 组 × 格子 4）", 9.5, MUTED))
    for k in range(2):
        b.append(bracket(cx + k * 12 * cw, cx + (k + 1) * 12 * cw - 3, ry,
                         "12", BLUE))
    for k in range(6):
        x0 = cx + k * 4 * cw
        b.append(sketch_line(x0 + 1, ry, x0 + 1, ry - 9, stroke=MUTED,
                             sw=1.4, opacity=0.7))
    ry2 = ry + 46
    b.append(txt(60, ry2 + 8, "(6,4)", 11, INK, bold=True))
    b.append(txt(130, ry2 - 6, "中间形状 s1：6 组 × 4——只是「第一次的分隔方案」", 9.5, MUTED))
    for k in range(6):
        b.append(bracket(cx + k * 4 * cw, cx + (k + 1) * 4 * cw - 3, ry2,
                         "4", ORANGE))
    ry3 = ry2 + 46
    b.append(txt(60, ry3 + 8, "(24,)", 11, INK, bold=True))
    b.append(txt(130, ry3 - 6, "链尾形状 s2：一整条——合并 = 直接画最后一次的分隔线", 9.5, MUTED))
    b.append(bracket(cx, cx + 24 * cw - 3, ry3, "24", GREEN))
    b.append(txt(60, fy + 268,
                 "读法：链 B →(6,4)→ (24,) 是「先按 (6,4) 画、再按 (24,) 重画」——两次画线的先后不影响最终格子归属，",
                 10.5, INK))
    b.append(txt(60, fy + 284 + 8 - 6,
                 "所以没有昨天的方向陷阱；中间形状 (6,4) 只是记账，没人看它（唯一使用者）就可整段擦掉。",
                 10.5, MUTED))

    # 下部左：判定三条
    ly = 502
    b.append(sketch_rect(40, ly, 470, 218, fill="#ffffff", sw=2.2))
    b.append(txt(60, ly + 26, "判定三条（今天的规则表）：", 13, INK, bold=True))
    rules = [
        ("恒等消除", "out_shape == in_shape（与 order 无关）",
         "Reshape(x, shape(x)) → x", "green"),
        ("链合并", "两跳 numel 守恒 + 都是 C 序",
         "→ Reshape(x, s2)，s1 消失", "blue"),
        ("链尾判定", "链尾 == 输入形状 → 0，否则 → 1",
         "与链长、中间形状无关（D1）", "orange"),
    ]
    ryy = ly + 44
    for t1, t2, t3, col in rules:
        b.append(sketch_rect(60, ryy, 430, 52, fill=TINT[col], sw=2.0))
        b.append(txt(74, ryy + 20, t1, 12,
                     {"green": GREEN, "blue": BLUE, "orange": ORANGE}[col],
                     bold=True))
        b.append(txt(74, ryy + 38, t2, 9.8, INK))
        b.append(txt(470, ryy + 38, t3, 9.8, INK, "end", bold=True))
        ryy += 60

    # 下部右：合法性边界
    ry2 = 502
    b.append(sketch_rect(550, ry2, 470, 218, fill=TINT["red"], sw=2.4,
                         stroke=RED))
    b.append(txt(566, ry2 + 26, "合法性边界：被替换 ≠ 被删除", 13, RED,
                 bold=True))
    b.append(txt(566, ry2 + 52, "P1 删除 op 自身，结果被替换成输入（值相等）——",
                 10.5, INK))
    b.append(txt(580, ry2 + 70, "replaceAllUses 把所有使用者改道 → 不需要唯一使用者检查", 10.5, INK, bold=True))
    b.append(txt(566, ry2 + 96, "P2 要删除中间值 %t = Reshape(x, s1)——只有 use_count(%t) == 1 才删；",
                 10.5, INK))
    b.append(txt(580, ry2 + 114, "func.return 也是使用者（场景 F 拒绝）", 10.5, INK, bold=True))
    b.append(txt(566, ry2 + 140, "激进版：改写 outer 直读 %in 永远合法（值相等）；",
                 10.5, INK))
    b.append(txt(580, ry2 + 158, "删除才有条件——两路都直连后内部 %t 使用者归零，", 10.5, INK))
    b.append(txt(580, ry2 + 176, "连带删除（5a：3 op → 2）；只有图输出才真正「必要」", 10.5, INK))

    # 底部：混 order 警告
    by2 = 738
    b.append(sketch_rect(40, by2, 980, 44, fill=TINT["orange"], sw=2.0))
    b.append(txt(60, by2 + 19, "order 陷阱（reshape 版的「方向陷阱」）：", 11.5,
                 ORANGE, bold=True))
    b.append(txt(320, by2 + 19,
                 "F 序 reshape 会重排线性顺序——C∘F 链不等于任何单个 reshape（numpy 实测：前 8 个 0,4,8,12,16,20,1,5…）",
                 10.3, INK))
    b.append(txt(60, by2 + 36, "mini 的处置：Verifier 允许 C/F 各自合法，但 P2 要求两跳同为 C（场景 G 拒绝，值不变）",
                 10, MUTED))
    save("02-mechanism.svg", "".join(b))


# ===========================================================================
# 图 3：优化前后 IR 对照（真实输出）
# ===========================================================================

def fig3() -> None:
    W, H = 1060, 950
    b = [header(W, H, "优化前后 IR 对照：消除、合并与拒绝的五种命运",
                 "全部 IR 来自 outputs/reshape_merge_lab.txt 的真实打印（mini IR 文本格式）")]

    cases = [
        ("场景 A：恒等单跳（结果 3 处使用）→ 照样消除", GREEN, "green",
         ["%r = mini.reshape %in shape = [2, 3, 4] order = \"C\" : (2x3x4xf32) -> (2x3x4xf32)",
          "%a = mini.reshape %r shape = [24] order = \"C\" : (2x3x4xf32) -> (24xf32)",
          "%b = mini.reshape %r shape = [4, 6] order = \"C\" : (2x3x4xf32) -> (4x6xf32)",
          "func.return %a, %b"],
         ["%a = mini.reshape %in shape = [24] order = \"C\" : (2x3x4xf32) -> (24xf32)",
          "%b = mini.reshape %in shape = [4, 6] order = \"C\" : (2x3x4xf32) -> (4xf6xf32)",
          "func.return %a, %b"],
         "P1 不看使用者数：删的是 op 自身（3 op → 2），%a/%b 全部改道读 %in"),
        ("场景 B：朴素链 → 合并单 reshape", BLUE, "blue",
         ["%t = mini.reshape %in shape = [6, 4] order = \"C\" : (2x3x4xf32) -> (6x4xf32)",
          "%c = mini.reshape %t shape = [24] order = \"C\" : (6x4xf32) -> (24xf32)",
          "func.return %c"],
         ["%c = mini.reshape %in shape = [24] order = \"C\" : (2x3x4xf32) -> (24xf32)",
          "func.return %c"],
         "中间形状 [6,4] 消失（2 op → 1，2 轮 1 次应用）"),
        ("场景 C：绕回链 → 整体消除", GREEN, "green",
         ["%t = mini.reshape %in shape = [6, 4] order = \"C\" : (2x3x4xf32) -> (6x4xf32)",
          "%c = mini.reshape %t shape = [2, 3, 4] order = \"C\" : (6x4xf32) -> (2x3x4xf32)",
          "func.return %c"],
         ["func.return %in"],
         "链尾 == 输入形状：合并成恒等后整体消除（2 op → 0）"),
        ("场景 D：五连链 → 迭代到单 op", ORANGE, "orange",
         ["%t0 = mini.reshape %in shape = [6, 4] order = \"C\" : (2x3x4xf32) -> (6x4xf32)",
          "%t1 = mini.reshape %t0 shape = [24] order = \"C\" : (6x4xf32) -> (24xf32)",
          "%t2 = mini.reshape %t1 shape = [2, 12] order = \"C\" : (24xf32) -> (2x12xf32)",
          "%t3 = mini.reshape %t2 shape = [24, 1] order = \"C\" : (2x12xf32) -> (24x1xf32)",
          "%t4 = mini.reshape %t3 shape = [12, 2] order = \"C\" : (24x1xf32) -> (12x2xf32)",
          "func.return %t4"],
         ["%t4 = mini.reshape %in shape = [12, 2] order = \"C\" : (2x3x4xf32) -> (12x2xf32)",
          "func.return %t4"],
         "每轮合并一对：5 轮 4 次应用（5 op → 1，链尾判定 → 1）"),
        ("场景 E：多使用者 → 保守拒绝", RED, "red",
         ["%t = mini.reshape %in shape = [6, 4] order = \"C\" : (2x3x4xf32) -> (6x4xf32)",
          "%c = mini.reshape %t shape = [24] order = \"C\" : (6x4xf32) -> (24xf32)",
          "%u = mini.reshape %t shape = [4, 6] order = \"C\" : (6x4xf32) -> (4x6xf32)",
          "func.return %c, %u"],
         ["（图原样保留：3 个 op 不动，零应用）"],
         "%t 使用者 = 2：删了它 %u 就没了定义；激进版可两路直连 → 3 op → 2"),
    ]

    y0 = 92
    chs = [148, 128, 128, 170, 148]
    y = y0
    for (title, color, tint, before, after, note), chh in zip(cases, chs):
        b.append(txt(40, y + 4, title, 13.5, color, bold=True))
        b.append(sketch_rect(40, y + 10, 500, chh - 26, fill="#ffffff", sw=2.0))
        b.append(txt(56, y + 32, "优化前", 10.5, MUTED, bold=True))
        for j, ln in enumerate(before):
            b.append(txt(56, y + 52 + j * 17, ln, 9.3, INK))
        b.append(sketch_line(548, y + (chh - 26) / 2 + 10, 596,
                             y + (chh - 26) / 2 + 10, stroke=color, sw=2.6,
                             arrow=True))
        b.append(txt(572, y + (chh - 26) / 2 - 6, "P1/P2", 9.5, color,
                     "middle", bold=True))
        b.append(sketch_rect(600, y + 10, 420, chh - 26,
                             fill=TINT[tint], sw=2.2))
        b.append(txt(616, y + 32, "优化后", 10.5, MUTED, bold=True))
        for j, ln in enumerate(after):
            b.append(txt(616, y + 52 + j * 17, ln, 9.3, INK, bold=True))
        b.append(txt(616, y + chh - 34, note, 9.3, color))
        y += chh + 8

    save("03-before-after.svg", "".join(b))


# ===========================================================================
# 图 4：MLIR 实测裁决 + 判定表汇总
# ===========================================================================

def fig4() -> None:
    W, H = 1060, 780
    b = [header(W, H, "MLIR 实测裁决 × 判定表汇总",
                 "tensor.reshape 与结构化 reshape 的命运对照（本机 LLVM 18.1.8）· 12 场景判定表 · 随机压力对拍")]

    # 左上：tensor.reshape 原样保留
    lx, ly = 40, 92
    b.append(txt(lx, ly + 6, "现场一：普通 reshape 链，stock 管道不动", 13, INK,
                 bold=True))
    b.append(sketch_rect(lx, ly + 16, 470, 118, fill=TINT["red"], sw=2.4,
                         stroke=RED))
    b.append(txt(lx + 16, ly + 42, "B(2,3,4) --[6,4]--> (6,4) --[24]--> (24,)，"
                 "两跳 numel 都是 24", 10.5, INK))
    b.append(txt(lx + 16, ly + 64,
                 "$ mlir-opt reshape_chain.mlir --canonicalize", 10.5, MUTED))
    b.append(txt(lx + 16, ly + 86,
                 "exit=0，输出里 tensor.reshape 仍剩 2 个（原样）", 11, RED,
                 bold=True))
    b.append(txt(lx + 16, ly + 108,
                 "tensor.reshape 没注册链式合并规则——这条优化要自己写", 10, INK))

    # 左中：结构化对照
    ly2 = 244
    b.append(txt(lx, ly2 + 6, "现场二：结构化 reshape（带 reassociation）的四种命运", 13,
                 INK, bold=True))
    b.append(sketch_rect(lx, ly2 + 16, 470, 168, fill=TINT["green"], sw=2.2))
    rows = [
        ("collapse 连链 (2,3,4)→(6,4)→(24,)", "折叠成单 op [[0, 1, 2]]", GREEN),
        ("expand 连链 (24,)→(6,4)→(2,3,4)", "折叠成单 op [[0, 1, 2]]", GREEN),
        ("expand→collapse 互逆对", "整体消除 → return %arg0", GREEN),
        ("collapse→expand 非互逆 →(6,2,2)", "原样保留 2 个 op（组合变换无法用单个", ORANGE),
        ("", "reassociative reshape 表达）", ORANGE),
    ]
    ryy = ly2 + 40
    for t1, t2, col in rows:
        b.append(txt(lx + 16, ryy, t1, 10.3, INK))
        b.append(txt(lx + 250, ryy, t2, 10.3, col, bold=True))
        ryy += 20
    b.append(txt(lx + 16, ryy + 8,
                 "结论：结构化信息（分组）决定 stock 里有没有组合规则；", 10, MUTED))
    b.append(txt(lx + 16, ryy + 26,
                 "mini 的 P2 判据更宽——只要 numel 守恒，(2,3,4)→(6,2,2) 也能合并", 10, MUTED))

    # 左下：物理代价
    ly3 = 452
    b.append(txt(lx, ly3 + 6, "现场三：不合并的物理代价（numpy 实测）", 13, INK,
                 bold=True))
    b.append(sketch_rect(lx, ly3 + 16, 470, 108, fill=TINT["orange"], sw=2.2))
    b.append(txt(lx + 16, ly3 + 42,
                 "连续输入：整条链全是视图（shares_memory=True）——合并不省搬运", 10.3, INK))
    b.append(txt(lx + 16, ly3 + 62,
                 "非连续输入（如 B.T）：第一跳被迫拷贝一次，二跳又是视图", 10.3, ORANGE,
                 bold=True))
    b.append(txt(lx + 16, ly3 + 82,
                 "合并一步也是一次拷贝、值相等——物理代价相同", 10.3, INK))
    b.append(txt(lx + 16, ly3 + 102,
                 "真正的收益：节点数、调度开销、给后续 Pattern 让路（Day 68）", 10, MUTED))

    # 右：判定表
    rx, ry = 550, 92
    b.append(txt(rx, ry + 6, "判定表（12 场景，优化后 op 数 + 数值对拍全 ok）：",
                 13, INK, bold=True))
    rows = [
        ("S1  恒等单跳", "[2,3,4]", 0),
        ("S2  朴素二连", "[6,4]→[24]", 1),
        ("S3  绕回二连", "[6,4]→[2,3,4]", 0),
        ("S4  三连", "[6,4]→[24]→[4,6]", 1),
        ("S5  五连", "[6,4]→…→[12,2]（5 跳）", 1),
        ("S6  二连绕回", "[24]→[2,3,4]", 0),
        ("S7  单跳非恒等", "[24]", 1),
        ("S8  恒等 order=F", "[2,3,4]", 0),
        ("S9  4D 长链", "[6,4,5]→…→[10,12]（4 跳）", 1),
        ("S10 标量维参与", "[1,24]→[24,1]", 1),
        ("S11 分叉链", "(%t1,%t2) 阻塞·(%u,%v) 照并", 3),
        ("S12 返回分叉链", "(%b,%c) 合并成恒等消除", 1),
    ]
    ty = ry + 22
    cols_x = [rx + 8, rx + 180, rx + 425]
    b.append(txt(cols_x[0], ty, "用例", 11, MUTED, bold=True))
    b.append(txt(cols_x[1], ty, "形状链", 11, MUTED, bold=True))
    b.append(txt(cols_x[2], ty, "剩 op", 11, MUTED, bold=True))
    b.append(sketch_line(rx + 4, ty + 6, rx + 430, ty + 6, opacity=0.4))
    b.append(sketch_line(rx + 4, ty + 10, rx + 430, ty + 10, opacity=0.4))
    for i, (name, chain, ops) in enumerate(rows):
        y = ty + 24 + i * 21
        hl = ops == 0
        b.append(txt(cols_x[0], y, name, 9.8, INK))
        b.append(txt(cols_x[1], y, chain, 9.8, INK))
        b.append(txt(cols_x[2], y, str(ops), 10.5,
                     GREEN if hl else INK, "end", bold=True))
    b.append(txt(rx + 8, ty + 24 + 12 * 21 + 6,
                 "0 = 整链消除为 return %in；1 = 合并成单 reshape；3 = 多使用者边界；数值与优化前逐元素相等",
                 9.3, MUTED))

    # 右下：随机压力
    sy = ty + 24 + 12 * 21 + 24
    b.append(sketch_rect(rx, sy, 460, 100, fill=TINT["green"], sw=2.2))
    b.append(txt(rx + 14, sy + 24, "随机压力对拍 300/300：", 11.5, GREEN,
                 bold=True))
    b.append(txt(rx + 14, sy + 44,
                 "随机链（秩 1..4、链长 1..5、中间形状随机分解）优化后数值不变、",
                 10, INK))
    b.append(txt(rx + 14, sy + 62,
                 "Verifier 通过，且 op 数 = 链尾判定（0 或 1）", 10, INK))
    b.append(txt(rx + 14, sy + 84,
                 "944 个初始 reshape op → 271 个（28.7%）——几乎全部坍缩成单跳", 10,
                 INK, bold=True))

    # 底部：验收汇总
    by = 684
    b.append(sketch_rect(40, by, 980, 62, fill=TINT["gray"], sw=2.2))
    b.append(txt(60, by + 25, "今日验收（全部真实运行）：", 12, GREEN, bold=True))
    b.append(txt(240, by + 25,
                 "主实验 22/22 · 验收测试 30/30 · 判定表 12/12 · 随机 300/300 · mlir-opt 5 项裁决",
                 11.5, INK))
    b.append(txt(60, by + 48,
                 "产出：P1 恒等消除 + P2 链合并 + 激进版对照（reshape_merge_lab.py）· 静态 IR reshape_chain.mlir / reassociative_chain.mlir · outputs/ 全部留档",
                 10.3, MUTED))
    save("04-verdicts.svg", "".join(b))


if __name__ == "__main__":
    fig1()
    fig2()
    fig3()
    fig4()
