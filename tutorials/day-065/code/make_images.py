#!/usr/bin/env python3
"""make_images.py —— 第 65 天（连续 Transpose 消除）教程的四张手绘 sketch 风 SVG 信息图。

风格约定（与第 8/9/10 周各天一致，Excalidraw-like）：
  - 背景 #fdfaf2（米白），盒子白底 + 深灰 #6b6357 手绘描边
  - 强调色不超过 4 种柔和色：蓝 #4a7fa5 / 橙 #a8772e / 绿 #5a8a5a / 红 #b0605a
  - 线条带轻微抖动（L 段折线），圆头笔触，线宽 2 左右
  - 手写感字体栈：Comic Sans MS / Comic Neue / Kaiti SC / 楷体 / cursive
  - 只用矩形、网格、箭头等简单几何形状

图中全部数字来自 2026-11-12 的真实运行（code/outputs/）：
  transpose_elim_lab 16/16；test_transpose_elim 33/33；
  linalg 互逆链 --canonicalize 原样保留（2 个 transpose）；
  链降级 6 层 scf.for、2 行 load、2 行 store（48+48 次访存）；
  单转置降级 3 层循环；随机对拍 300/300（900 op → 254，28.2%）；
  方向反了的错误合并：正确 (1,0,2) vs 错误 (2,1,0)，链终点 (3,2,4)。

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

rng = random.Random(65)


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


# ===========================================================================
# 图 1：全貌——第 10 周第 2 天 + 两个 Pattern 在优化管道中的位置
# ===========================================================================

def fig1() -> None:
    W, H = 1020, 700
    b = [header(W, H, "第 65 天全貌：连续 Transpose 消除",
                "阶段三「AI 计算图与图优化」· 第 10 周第 2 天 · 两个 RewritePattern 的位置图")]

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
                 "第 9 周 Shape/Stride 地基 → 第 64 天 transpose 语义（昨天）→ 今天：图优化第一刀——冗余转置链",
                 11.5, MUTED))

    # 中部：转置链 + 两个 Pattern 的裁决
    qy = 178
    b.append(sketch_rect(40, qy, 280, 120, fill=TINT["blue"], sw=2.4))
    b.append(txt(180, qy + 24, "图里的转置链", 14, BLUE, "middle", bold=True))
    b.append(txt(180, qy + 48, "%t = T_p(%in)", 11.5, INK, "middle"))
    b.append(txt(180, qy + 66, "%c = T_q(%t)", 11.5, INK, "middle"))
    b.append(txt(180, qy + 90, "「谁把它消掉？」", 11, MUTED, "middle"))
    b.append(txt(180, qy + 108, "（连续转置 = 排列的组合）", 10, MUTED, "middle"))

    pats = [
        ("Pattern 1 互逆消除", "T_q(T_p(x)) → x",
         "判据 q == inv(p)（compose 为恒等）", "blue", 370),
        ("Pattern 2 一般合并", "T_q(T_p(x)) → T_{p∘q}(x)",
         "r[i] = p[q[i]]；合成恒等则消除", "green", 680),
    ]
    for title, rule, note, col, fx in pats:
        b.append(sketch_rect(fx, qy, 300, 120, fill=TINT[col], sw=2.4))
        b.append(txt(fx + 150, qy + 24, title, 13.5,
                     {"blue": BLUE, "green": GREEN}[col], "middle", bold=True))
        b.append(txt(fx + 150, qy + 50, rule, 12.5, INK, "middle", bold=True))
        b.append(txt(fx + 150, qy + 76, note, 10.5, MUTED, "middle"))
        b.append(txt(fx + 150, qy + 100,
                     "中间值唯一使用者才允许删", 10.5, MUTED, "middle"))
        b.append(sketch_path([(320, qy + 60), (fx, qy + 60)],
                             stroke=STROKE, sw=2.0, arrow=True, curved=True))

    # 中下：PassManager 迭代
    my = 330
    b.append(sketch_rect(40, my, 940, 84, fill="#ffffff", sw=2.2))
    b.append(txt(60, my + 26, "PassManager：迭代到不动点（实测）", 13, INK,
                 bold=True))
    b.append(txt(60, my + 50,
                 "三连链 T T T（3-循环，阶 3）→ 第 1 轮合并成 T T → 第 2 轮合成恒等消除 → return %in（2 次应用、3 轮收敛）",
                 11.5, INK))
    b.append(txt(60, my + 72,
                 "长链先合并哪一对都不影响终点——排列组合满足结合律（A5：729 组三元组验证）",
                 10.5, MUTED))

    # 底部：MLIR 实测对照
    by = 442
    b.append(txt(40, by, "MLIR 侧真实事实（本机 LLVM 18.1.8 实测）：", 12,
                 INK, bold=True))
    facts = [
        ("① --canonicalize", "互逆转置对原样保留（2 个 linalg.transpose 都在）",
         "stock 管道里没有这条规则", "red"),
        ("② --convert-linalg-to-loops", "6 层 scf.for、2 行 load、2 行 store",
         "24 元素 × 2 遍 = 96 次访存", "orange"),
        ("③ 单个转置对照", "3 层 scf.for、1 行 load（24 次访存）",
         "互逆对白付一整次搬运", "gray"),
    ]
    fy = by + 14
    for t1, t2, t3, col in facts:
        b.append(sketch_rect(40, fy, 460, 44, fill=TINT[col], sw=2.0))
        b.append(txt(56, fy + 19, t1, 11.5,
                     {"red": RED, "orange": ORANGE, "gray": MUTED}[col],
                     bold=True))
        b.append(txt(56, fy + 36, t2 + "——" + t3, 10.5, INK))
        fy += 52

    # 右下：验收汇总
    ay = by + 14
    b.append(sketch_rect(530, ay, 450, 138, fill=TINT["green"], sw=2.4))
    b.append(txt(546, ay + 24, "今日验收（全部真实运行）：", 12.5, GREEN,
                 bold=True))
    lines = [
        "主实验 16/16 · 验收测试 33/33（A–G 七段）",
        "组合对拍：36 对全排列 + 结合律 729 组",
        "判定表 12/12 · 随机链 300/300",
        "300 组随机链：900 个转置 op → 254 个（28.2%）",
        "mlir-opt 实测：canonicalize 不动 / loops 6 层循环",
    ]
    for k, ln in enumerate(lines):
        b.append(txt(546, ay + 46 + k * 18, "· " + ln, 10.5, INK))

    # 明日预告条
    ny = 600
    b.append(sketch_rect(40, ny, 940, 40, fill="#ffffff", sw=2.0))
    b.append(txt(60, ny + 25, "明天（Day 66）：", 11.5, GREEN, bold=True))
    b.append(txt(178, ny + 25,
                 "连续 Reshape 合并——Reshape 链、元素数量与中间使用者约束（今天的多使用者判据直接复用）",
                 11.5, INK))
    save("01-overview.svg", "".join(b))


# ===========================================================================
# 图 2：核心机制——两个排列的组合 + 维度流推导 + 三条性质
# ===========================================================================

def fig2() -> None:
    W, H = 1060, 780
    b = [header(W, H, "核心机制：两个排列怎么组合成一个",
                "C = T_q(T_p(A)) ⟹ C.shape[i] = A.shape[p[q[i]]]，r = compose(p, q)（内层先作用）· 数字全部来自真实运行")]

    # 顶部：推导链
    b.append(sketch_rect(40, 78, 980, 96, fill=TINT["blue"], sw=2.4))
    b.append(txt(60, 104, "一步推导（约定来自第 64 天：out_shape[i] = in_shape[perm[i]]）",
                 12.5, BLUE, bold=True))
    b.append(txt(60, 130, "B = T_p(A)：B.shape[i] = A.shape[p[i]]", 12, INK))
    b.append(txt(60, 152, "C = T_q(B)：C.shape[i] = B.shape[q[i]] = A.shape[ p[ q[i] ] ]  →  r = compose(p, q)，r[i] = p[q[i]]",
                 12, INK, bold=True))
    b.append(txt(960, 104, "36 对全排列对拍 ✓", 10, GREEN, "end", bold=True))

    # 中部：维度流图（3D 具体例子）
    fy = 196
    b.append(sketch_rect(40, fy, 980, 190, fill="#ffffff", sw=2.2))
    b.append(txt(60, fy + 24, "维度流（贯穿例子 B(2,3,4)，3-循环 p = (1,2,0)）：",
                 13, INK, bold=True))
    boxes = [
        ("A", "(2,3,4)", "strides (12,4,1)", "gray", 70),
        ("T_p", "p=(1,2,0)", "拽第 1,2,0 维", "orange", 280),
        ("B", "(3,4,2)", "strides (4,1,12)", "gray", 470),
        ("T_p", "p=(1,2,0)", "再来一次", "orange", 680),
        ("C", "(4,2,3)", "≠ A！", "red", 870),
    ]
    for label, l2, l3, col, fx in boxes:
        fw, fh = 140, 62
        b.append(sketch_rect(fx, fy + 38, fw, fh,
                             fill=TINT[col], sw=2.4 if col != "gray" else 2.0))
        b.append(txt(fx + fw / 2, fy + 60, label, 13, INK, "middle", bold=True))
        b.append(txt(fx + fw / 2, fy + 76, l2, 11, INK, "middle"))
        b.append(txt(fx + fw / 2, fy + 92, l3, 9.5, MUTED, "middle"))
    b.append(sketch_line(212, fy + 69, 278, fy + 69, arrow=True))
    b.append(sketch_line(412, fy + 69, 478, fy + 69, arrow=True))
    b.append(sketch_line(622, fy + 69, 688, fy + 69, arrow=True))
    b.append(txt(60, fy + 130,
                 "转两次 ≠ 原样（p² = (2,0,1) ≠ 恒等）；转三次才回 (2,3,4)——「阶」= 3。撤销一次转置要逆排列，不是再转一次。",
                 11.5, RED))
    b.append(txt(60, fy + 155,
                 "compose(p,p) = (2,0,1) = inv(p)——3-循环的平方恰好是它的逆；compose(p, inv(p)) = (0,1,2) 恒等 → 互逆对可整体消除。",
                 11.5, INK))
    b.append(txt(60, fy + 178,
                 "实测：B 经 p 三连 (2,3,4) → (3,4,2) → (4,2,3) → (2,3,4)，值逐元素相等（T_p³ == x）。",
                 10.5, MUTED))

    # 下部左：三条性质
    ly = 410
    b.append(sketch_rect(40, ly, 470, 250, fill="#ffffff", sw=2.2))
    b.append(txt(60, ly + 26, "判定三条（今天的规则表）：", 13, INK, bold=True))
    rules = [
        ("互逆消除", "q == inv(p) ⟺ compose(p,q) == 恒等", "T_q(T_p(x)) → x", "green"),
        ("一般合并", "r = compose(p, q) = p[q[i]]", "T_q(T_p(x)) → T_r(x)", "blue"),
        ("链式自乘", "p 的阶 k：p^k = 恒等", "T_p 连做 k 次 → x", "orange"),
    ]
    ry = ly + 44
    for t1, t2, t3, col in rules:
        b.append(sketch_rect(60, ry, 430, 58, fill=TINT[col], sw=2.0))
        b.append(txt(74, ry + 22, t1, 12,
                     {"green": GREEN, "blue": BLUE, "orange": ORANGE}[col],
                     bold=True))
        b.append(txt(74, ry + 41, t2, 10.5, INK))
        b.append(txt(470, ry + 41, t3, 10.5, INK, "end", bold=True))
        ry += 68

    # 下部右：方向陷阱
    ry2 = 410
    b.append(sketch_rect(550, ry2, 470, 250, fill=TINT["red"], sw=2.4,
                         stroke=RED))
    b.append(txt(566, ry2 + 26, "方向陷阱：r[i] = q[p[i]] 就错了", 13, RED,
                 bold=True))
    b.append(txt(566, ry2 + 52, "2D p=q=(1,0)：正确 (0,1) = 错误 (0,1)——对合"
                 "两个方向重合，2D 测试永远全绿", 10.5, INK))
    b.append(txt(566, ry2 + 74, "3D p=(1,2,0), q=(0,2,1)：", 10.5, INK))
    b.append(txt(580, ry2 + 92, "正确 r = (1,0,2) → 合并 shape (3,2,4) == 链终点 ✓",
                 10.5, GREEN))
    b.append(txt(580, ry2 + 110, "错误 r = (2,1,0) → 合并 shape (4,3,2) ≠ 链终点 (3,2,4) ✗",
                 10.5, RED))
    b.append(txt(566, ry2 + 140, "为什么 p 在外圈？内层 T_p 先作用：C.shape[i] 先"
                 "被 q 拽到 B 的第 q[i] 维，", 10.5, INK))
    b.append(txt(566, ry2 + 158, "再被 p 拽到 A 的第 p[q[i]] 维——「后写的先读」",
                 10.5, INK))
    b.append(txt(566, ry2 + 184, "防御：用 3D 非对合链对拍 numpy（np.transpose 两步 vs 一步），",
                 10, MUTED))
    b.append(txt(566, ry2 + 202, "2D 全绿不能证明方向对（错误现场的完整输出在 outputs/）",
                 10, MUTED))

    # 底部：结合律
    by2 = 686
    b.append(sketch_rect(40, by2, 980, 56, fill=TINT["gray"], sw=2.0))
    b.append(txt(60, by2 + 24, "结合律 (p∘q)∘s == p∘(q∘s)：", 12, INK, bold=True))
    b.append(txt(280, by2 + 24,
                 "729 组 3 元三元组验证——PassManager 长链先合并哪一对，终点都一样（E 节 8 连链 4 轮收敛）",
                 11.5, INK))
    b.append(txt(60, by2 + 44,
                 "Pattern 只减 op 数（2→1 或 →0），不会振荡——迭代必然终止；max_rounds 只是防御上限",
                 10.5, MUTED))
    save("02-mechanism.svg", "".join(b))


# ===========================================================================
# 图 3：优化前后 IR 对照（真实输出）
# ===========================================================================

def fig3() -> None:
    W, H = 1060, 800
    b = [header(W, H, "优化前后 IR 对照：消除、合并与拒绝的四种命运",
                 "全部 IR 来自 outputs/transpose_elim_lab.txt 的真实打印（mini IR 文本格式）")]

    cases = [
        ("场景 B：3D 互逆对 → 整体消除", GREEN, "green",
         ["%t = mini.transpose %in permutation = [1, 2, 0] : (2x3x4xf32) -> (3x4x2xf32)",
          "%c = mini.transpose %t permutation = [2, 0, 1] : (3x4x2xf32) -> (2x3x4xf32)",
          "func.return %c"],
         ["func.return %in"],
         "q == inv(p)：2 op → 0；B1–B3/B2 断言数值不变"),
        ("场景 C：3D 一般对 → 合并单转置", BLUE, "blue",
         ["%t = mini.transpose %in permutation = [1, 2, 0] : (2x3x4xf32) -> (3x4x2xf32)",
          "%c = mini.transpose %t permutation = [1, 2, 0] : (3x4x2xf32) -> (4x2x3xf32)",
          "func.return %c"],
         ["%c = mini.transpose %in permutation = [2, 0, 1] : (2x3x4xf32) -> (4x2x3xf32)",
          "func.return %c"],
         "compose(p,p) = (2,0,1)：2 op → 1，链尾直改接 %in"),
        ("场景 D：三连链 → 两轮消除", ORANGE, "orange",
         ["%t1 = mini.transpose %in permutation = [1, 2, 0] : (2x3x4xf32) -> (3x4x2xf32)",
          "%t2 = mini.transpose %t1 permutation = [1, 2, 0] : (3x4x2xf32) -> (4x2x3xf32)",
          "%c  = mini.transpose %t2 permutation = [1, 2, 0] : (4x2x3xf32) -> (2x3x4xf32)",
          "func.return %c"],
         ["func.return %in"],
         "阶 3：p³ = 恒等；第 1 轮合并 → 第 2 轮消除（2 次应用）"),
        ("场景 E：多使用者 → 保守拒绝", RED, "red",
         ["%t = mini.transpose %in permutation = [1, 2, 0] : (2x3x4xf32) -> (3x4x2xf32)",
          "%c = mini.transpose %t permutation = [2, 0, 1] : (3x4x2xf32) -> (2x3x4xf32)",
          "%u = mini.transpose %t permutation = [0, 2, 1] : (3x4x2xf32) -> (3x2x4xf32)",
          "func.return %c, %u"],
         ["（图原样保留：3 个 op 不动）"],
         "%t 的使用者 = 2：删了它 %u 就没了定义"),
    ]

    y0 = 92
    ch = 172
    for k, (title, color, tint, before, after, note) in enumerate(cases):
        y = y0 + k * (ch + 8)
        b.append(txt(40, y + 4, title, 13.5, color, bold=True))
        # 左：优化前
        b.append(sketch_rect(40, y + 10, 500, ch - 26, fill="#ffffff", sw=2.0))
        b.append(txt(56, y + 32, "优化前", 10.5, MUTED, bold=True))
        for j, ln in enumerate(before):
            b.append(txt(56, y + 52 + j * 17, ln, 9.5, INK))
        # 箭头
        b.append(sketch_line(548, y + (ch - 26) / 2 + 10, 596,
                             y + (ch - 26) / 2 + 10, stroke=color, sw=2.6,
                             arrow=True))
        b.append(txt(572, y + (ch - 26) / 2 - 6, "P1/P2", 9.5, color,
                     "middle", bold=True))
        # 右：优化后
        b.append(sketch_rect(600, y + 10, 420, ch - 26,
                             fill=TINT[tint], sw=2.2))
        b.append(txt(616, y + 32, "优化后", 10.5, MUTED, bold=True))
        for j, ln in enumerate(after):
            b.append(txt(616, y + 52 + j * 17, ln, 9.5, INK, bold=True))
        b.append(txt(616, y + ch - 34, note, 9.5, color))

    save("03-before-after.svg", "".join(b))


# ===========================================================================
# 图 4：MLIR 实测裁决 + 判定表汇总
# ===========================================================================

def fig4() -> None:
    W, H = 1060, 760
    b = [header(W, H, "MLIR 实测裁决 × 判定表汇总",
                 "linalg 互逆转置链的真实命运（本机 LLVM 18.1.8）· 12 场景判定表 · 随机压力对拍")]

    # 左上：canonicalize 现场
    lx, ly = 40, 92
    b.append(txt(lx, ly + 6, "现场一：stock 管道不动这条链", 13, INK, bold=True))
    b.append(sketch_rect(lx, ly + 16, 470, 150, fill=TINT["red"], sw=2.4,
                         stroke=RED))
    b.append(txt(lx + 16, ly + 42, "互逆转置对（合计零语义）：", 11.5, INK))
    b.append(txt(lx + 16, ly + 62,
                 "in 2x3x4 --[1,2,0]--> 3x4x2 --[2,0,1]--> 2x3x4", 11, INK,
                 bold=True))
    b.append(txt(lx + 16, ly + 88,
                 "$ mlir-opt transpose_chain.mlir --canonicalize", 10.5, MUTED))
    b.append(txt(lx + 16, ly + 108,
                 "exit=0，输出里 linalg.transpose 仍剩 2 个（原样）", 11, RED,
                 bold=True))
    b.append(txt(lx + 16, ly + 132,
                 "linalg.transpose 没注册这类 canonicalization——这条优化"
                 "要自己写（mini 的两个 Pattern 就是练习场）", 10, INK))

    # 左下：loops 代价
    ly2 = 276
    b.append(txt(lx, ly2 + 6, "现场二：不消除的物理代价", 13, INK, bold=True))
    b.append(sketch_rect(lx, ly2 + 16, 470, 130, fill=TINT["orange"], sw=2.2))
    b.append(txt(lx + 16, ly2 + 42,
                 "链 --convert-linalg-to-loops：6 层 scf.for、2 行 load、2 行 store",
                 11, INK, bold=True))
    b.append(txt(lx + 16, ly2 + 62,
                 "每行在循环里执行 24 次 → 48 读 + 48 写（数据搬两遍）", 11, ORANGE,
                 bold=True))
    b.append(txt(lx + 16, ly2 + 88,
                 "对照：单个转置降级 3 层循环、1 行 load（24 次访存）", 10.5, INK))
    b.append(txt(lx + 16, ly2 + 108,
                 "一对「什么都没做」的转置 = 白付一整次 O(numel) 搬运", 10.5,
                 MUTED))
    b.append(txt(lx + 16, ly2 + 128,
                 "load %arg0[%arg3, %arg1, %arg2]  ← 两个转置各自的读端（完整 IR 存 outputs/）",
                 9.5, MUTED))

    # 右：判定表
    rx, ry = 550, 92
    b.append(txt(rx, ry + 6, "判定表（12 场景，优化后 op 数 + 数值对拍全 ok）：",
                 13, INK, bold=True))
    rows = [
        ("S1  2D TT（对合）", "[1,0]→[1,0]", 0),
        ("S2  2D 恒等对", "[0,1]→[1,0]", 1),
        ("S3  3D 互逆对", "[1,2,0]→[2,0,1]", 0),
        ("S4  3D 一般对 p=q", "[1,2,0]→[1,2,0]", 1),
        ("S5  3D 一般对 p≠q", "[1,2,0]→[0,2,1]", 1),
        ("S6  3D 三连链（阶 3）", "[1,2,0]×3", 0),
        ("S7  3D 四连链", "[1,2,0]×4", 1),
        ("S8  4D 互逆对", "[3,2,1,0]×2", 0),
        ("S9  4D 长链 5 个", "[1,2,3,0]×5", 1),
        ("S10 单转置", "[1,0]", 1),
        ("S11 恒等单转置", "[0,1]", 1),
        ("S12 交错链 4 个", "4 个不同排列", 1),
    ]
    ty = ry + 22
    cols_x = [rx + 8, rx + 200, rx + 330]
    b.append(txt(cols_x[0], ty, "用例", 11, MUTED, bold=True))
    b.append(txt(cols_x[1], ty, "排列链", 11, MUTED, bold=True))
    b.append(txt(cols_x[2], ty, "剩 op", 11, MUTED, bold=True))
    b.append(sketch_line(rx + 4, ty + 6, rx + 430, ty + 6, opacity=0.4))
    b.append(sketch_line(rx + 4, ty + 10, rx + 430, ty + 10, opacity=0.4))
    for i, (name, chain, ops) in enumerate(rows):
        y = ty + 24 + i * 22
        hl = ops == 0
        b.append(txt(cols_x[0], y, name, 10.5, INK))
        b.append(txt(cols_x[1], y, chain, 10.5, INK))
        b.append(txt(cols_x[2], y, str(ops), 11,
                     GREEN if hl else INK, bold=True))
    b.append(txt(rx + 8, ty + 24 + 12 * 22 + 4,
                 "0 = 整链消除为 return %in；1 = 合并成单转置；数值全部与优化前逐元素相等",
                 9.5, MUTED))

    # 右下：随机压力 + 错误方向
    sy = ty + 24 + 12 * 22 + 22
    b.append(sketch_rect(rx, sy, 460, 96, fill=TINT["green"], sw=2.2))
    b.append(txt(rx + 14, sy + 24, "随机压力对拍 300/300：", 11.5, GREEN,
                 bold=True))
    b.append(txt(rx + 14, sy + 44,
                 "随机链（秩 1..5、链长 1..5）优化后数值不变、Verifier 通过、op 数不增",
                 10, INK))
    b.append(txt(rx + 14, sy + 64,
                 "900 个初始转置 op → 254 个（28.2%）——消除与合并都在干活", 10,
                 INK, bold=True))
    b.append(txt(rx + 14, sy + 84,
                 "256 组合并后剩单转置的用例：排列恰好等价整条链（F3）", 9.5,
                 MUTED))

    # 底部：验收汇总
    by = 660
    b.append(sketch_rect(40, by, 980, 62, fill=TINT["gray"], sw=2.2))
    b.append(txt(60, by + 25, "今日验收（全部真实运行）：", 12, GREEN, bold=True))
    b.append(txt(240, by + 25,
                 "主实验 16/16 · 验收测试 33/33 · 判定表 12/12 · 随机 300/300 · 结合律 729 组 · mlir-opt 实测 5 项",
                 11.5, INK))
    b.append(txt(60, by + 48,
                 "产出：P1 互逆消除 + P2 一般合并（transpose_elim_lab.py）· PassManager 不动点 · 静态 IR transpose_chain.mlir · outputs/ 全部留档",
                 10.5, MUTED))
    save("04-verdicts.svg", "".join(b))


if __name__ == "__main__":
    fig1()
    fig2()
    fig3()
    fig4()
