#!/usr/bin/env python3
"""make_images.py —— 第 64 天（Transpose 的语义）教程的四张手绘 sketch 风 SVG 信息图。

风格约定（与第 8/9/10 周各天一致，Excalidraw-like）：
  - 背景 #fdfaf2（米白），盒子白底 + 深灰 #6b6357 手绘描边
  - 强调色不超过 4 种柔和色：蓝 #4a7fa5 / 橙 #a8772e / 绿 #5a8a5a / 红 #b0605a
  - 线条带轻微抖动（L 段折线），圆头笔触，线宽 2 左右
  - 手写感字体栈：Comic Sans MS / Comic Neue / Kaiti SC / 楷体 / cursive
  - 只用矩形、网格、箭头等简单几何形状

图中全部数字来自 2026-11-12 的真实运行（code/outputs/）：
  transpose_lab 21/21；test_transpose 63/63；随机对拍 200/200；
  视图 0.22 µs vs 搬家 42.293 ms（约 1.9×10⁵ 倍）；
  linalg.transpose 8 案例 exit = 0/0/1/1/1/1/1/0；
  M6 越界排列两次乱码值 187651783086528 与 187652031675040。

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

rng = random.Random(64)


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
            mx, my = (x0 + x1) / 2, (y0 + y1) / 2
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


def cell(x, y, w, h, label, fill="#ffffff", stroke=STROKE, size=13,
         fill_color=INK, sw=2.0):
    out = [sketch_rect(x, y, w, h, fill=fill, stroke=stroke, sw=sw)]
    out.append(txt(x + w / 2, y + h / 2 + 4.5, label, size, fill_color,
                   anchor="middle", bold=True))
    return "".join(out)


def tgrid(x, y, cw, ch, rows, cols, values, tintmap=None, size=14):
    """手绘张量网格：rows×cols 格，values 按行主序填入。"""
    out = []
    k = 0
    for r in range(rows):
        for c in range(cols):
            fill = "#ffffff"
            if tintmap and k in tintmap:
                fill = TINT[tintmap[k]]
            out.append(cell(x + c * cw, y + r * ch, cw, ch,
                            str(values[k]), fill=fill, size=size))
            k += 1
    return "".join(out)


def save(name: str, body: str) -> None:
    path = OUT / name
    path.write_text(body + "</svg>\n", encoding="utf-8")
    print(f"写出 {path}（{path.stat().st_size} B）")


# ===========================================================================
# 图 1：全貌——今天在第 10 周的位置 + 转置需求的三种命运路线
# ===========================================================================

def fig1() -> None:
    W, H = 1020, 700
    b = [header(W, H, "第 64 天全貌：Transpose 的语义",
                "阶段三「AI 计算图与图优化」· 第 10 周第 1 天 · 三种命运的路线图")]

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
                 "第 9 周（Shape·Layout 地基）→ 今天开第 10 周：Layout 与冗余算子消除——先弄清一个算子的语义，才谈消除它",
                 11.5, MUTED))

    # 中部：转置需求（居中）→ 三种命运（下一排扇形展开）
    qy = 178
    b.append(sketch_rect(370, qy, 280, 76, fill=TINT["blue"], sw=2.4))
    b.append(txt(510, qy + 22, "转置需求", 14, BLUE, "middle", bold=True))
    b.append(txt(510, qy + 42, "给 A(2,3) 一个 (3,2) 的视角", 11, INK, "middle"))
    b.append(txt(510, qy + 60, "A = [[1,2,3],[4,5,6]]", 11, INK, "middle"))
    b.append(txt(510, qy - 6, "（Day 63 复盘里 A.T 那一对，今天正式立案）",
                 9.5, MUTED, "middle"))

    fates = [
        ("命运① 视图", "A.T", "strides (3,1) → (1,3)",
         "只改账本：存储一字节不动", "O(1) · 0.22 µs", "blue", 40),
        ("命运② 搬家", "ascontiguousarray(A.T)",
         "存储 [1..6] → [1,4,2,5,3,6]", "真实数据移动（重排字节）",
         "O(numel) · 42.293 ms", "orange", 360),
        ("命运③ 不落地", "消费方交换下标", "load %a[j, i]",
         "语义活在索引里，无中间张量", "linalg 降级循环的形态", "green", 680),
    ]
    fy0 = 318
    for title, act, change, note, cost, col, fx in fates:
        fw, fh = 300, 128
        b.append(sketch_rect(fx, fy0, fw, fh, fill=TINT[col], sw=2.4))
        b.append(txt(fx + 16, fy0 + 26, title, 14,
                     {"blue": BLUE, "orange": ORANGE, "green": GREEN}[col],
                     bold=True))
        b.append(txt(fx + 16, fy0 + 50, act, 11.5, INK))
        b.append(txt(fx + 16, fy0 + 70, change, 11, INK))
        b.append(txt(fx + 16, fy0 + 90, note, 10.5, MUTED))
        b.append(txt(fx + 16, fy0 + 112, cost, 10.5,
                     {"blue": BLUE, "orange": ORANGE, "green": GREEN}[col]))
        tx = fx + fw / 2
        b.append(sketch_path([(510, qy + 76), (tx, fy0 - 4)],
                             stroke=STROKE, sw=2.0, arrow=True, curved=True))

    # 底部：编译链路位置
    by = 486
    b.append(txt(40, by, "今天的内容在编译链路里的位置：", 12, INK, bold=True))
    steps = [
        ("① 算子定义 + Verifier", "permutation 属性 / 四关检查（今天）", "orange"),
        ("② 图优化", "Day 65 连续转置消除 · Day 68 Layout 传播", "white"),
        ("③ Lowering", "Day 85+ 降成循环（读写下标交换）", "white"),
        ("④ 执行", "视图零拷贝 / 搬家搬字节", "white"),
    ]
    bw, bh, bgap = 224, 62, 18
    for i, (t1, t2, col) in enumerate(steps):
        x = 40 + i * (bw + bgap)
        b.append(sketch_rect(x, by + 10, bw, bh, fill=TINT[col],
                             stroke=ORANGE if col == "orange" else STROKE,
                             sw=2.6 if col == "orange" else 2.0))
        b.append(txt(x + bw / 2, by + 34, t1, 12, INK, "middle", bold=True))
        b.append(txt(x + bw / 2, by + 52, t2, 9.5, MUTED, "middle"))
        if i < 3:
            b.append(sketch_line(x + bw + 2, by + 41, x + bw + bgap - 4,
                                 by + 41, arrow=True))

    # 底部结论条
    cy = 590
    b.append(sketch_rect(40, cy, 940, 50, fill=TINT["gray"], sw=2.0))
    b.append(txt(510, cy + 21, "三种命运的逻辑值完全相同（语义不变），物理代价天差地别——"
                 "编译器的职责是选对命运，而不是把转置一律降成搬家",
                 12, INK, "middle", bold=True))
    b.append(txt(510, cy + 40, "实测（2048×2048 f32）：视图 0.22 µs vs 搬家 42.293 ms，"
                 "差约 1.9×10⁵ 倍（outputs/transpose_lab.txt）",
                 10.5, MUTED, "middle"))

    # 明日预告条
    ny = cy + 66
    b.append(sketch_rect(40, ny, 940, 40, fill="#ffffff", sw=2.0))
    b.append(txt(60, ny + 25, "明天（Day 65）：", 11.5, GREEN, bold=True))
    b.append(txt(178, ny + 25,
                 "连续 Transpose 消除——两次 Permutation 的组合：恒等消除 + 一般合并"
                 "（今天的逆排列 / 阶就是它的原料）", 11.5, INK))
    save("01-overview.svg", "".join(b))


# ===========================================================================
# 图 2：核心机制——排列规则 + 视图路径 + 搬家路径 + 3D 陷阱
# ===========================================================================

def fig2() -> None:
    W, H = 1060, 800
    b = [header(W, H, "核心机制：一条排列规则，两条实现路径",
                "out_shape[i] = in_shape[perm[i]] · 视图版 out_strides[i] = in_strides[perm[i]]（全部数字来自真实运行）")]

    # 顶部规则卡
    b.append(sketch_rect(40, 78, 980, 64, fill=TINT["blue"], sw=2.4))
    b.append(txt(64, 104, "排列规则（约定）", 13, BLUE, bold=True))
    b.append(txt(64, 126,
                 "out_shape[i] = in_shape[perm[i]]（输出第 i 维拽输入第 perm[i] 维）"
                 "    视图版：out_strides[i] = in_strides[perm[i]]    perm = [1, 0]",
                 12, INK))
    b.append(txt(940, 104, "与 numpy / linalg 一致", 10, MUTED, "end"))
    b.append(txt(940, 120, "（本机双侧实测，见教程 5.3）", 10, MUTED, "end"))

    # ---------- 左面板：视图 ----------
    lx, ly = 40, 168
    b.append(sketch_rect(lx, ly, 470, 380, fill="#ffffff", sw=2.2))
    b.append(txt(lx + 20, ly + 30, "命运① 视图：只改账本（零拷贝）", 14, BLUE,
                 bold=True))

    b.append(txt(lx + 28, ly + 62, "A  shape (2,3)  strides (3,1)", 12, INK,
                 bold=True))
    b.append(tgrid(lx + 28, ly + 72, 44, 38, 2, 3, [1, 2, 3, 4, 5, 6],
                   tintmap={0: "blue", 3: "green", 5: "red"}))
    b.append(txt(lx + 200, ly + 64, "perm", 10, ORANGE, "middle"))
    b.append(txt(lx + 200, ly + 77, "[1,0]", 10.5, ORANGE, "middle", bold=True))
    b.append(sketch_line(lx + 172, ly + 96, lx + 228, ly + 96, stroke=ORANGE,
                         sw=2.2, arrow=True))
    b.append(txt(lx + 240, ly + 62, "A.T  shape (3,2)  strides (1,3)", 12, INK,
                 bold=True))
    b.append(tgrid(lx + 240, ly + 72, 44, 38, 3, 2, [1, 4, 2, 5, 3, 6],
                   tintmap={0: "blue", 1: "green", 5: "red"}))

    # 共享存储条
    sy = ly + 236
    b.append(txt(lx + 28, sy - 12, "同一份底层存储（视图与 A 共享，一字节不动）：",
                 11.5, INK))
    for i in range(6):
        b.append(cell(lx + 28 + i * 52, sy, 50, 36, str([1, 2, 3, 4, 5, 6][i]),
                      fill=TINT["gray"], size=13))
        b.append(txt(lx + 53 + i * 52, sy + 50, f"@{i}", 9, MUTED, "middle"))

    # 连线：A.T 的格子 → 存储格子（值1→0, 值4→3, 值6→5）
    links = [(0, 0, "blue"), (1, 3, "green"), (5, 5, "red")]
    at_cells = [(lx + 240 + c * 44, ly + 72 + r * 38) for r, c in
                [(0, 0), (0, 1), (0, 2), (1, 0), (1, 1), (1, 2)]]
    for val_idx, store_idx, col in links:
        cx0, cy0 = at_cells[val_idx]
        b.append(sketch_path([(cx0 + 44, cy0 + 19),
                              (lx + 28 + store_idx * 52 + 25, sy)],
                             stroke={"blue": BLUE, "green": GREEN,
                                     "red": RED}[col], sw=1.8,
                             opacity=0.85, curved=True))
    b.append(txt(lx + 28, sy + 68,
                 "A.T[0,1]=4 → 存储@3（= A[1,0]）；A.T[2,0]=3 → 存储@2", 10.5, INK))
    b.append(txt(lx + 28, sy + 86,
                 "读序偏移：A 连续 [0,1,2,3,4,5] → A.T 蹦着走 [0,3,1,4,2,5]", 10.5,
                 INK))
    b.append(txt(lx + 28, sy + 104,
                 "写穿联动实测：V[0,1]=99 后 A[1,0] 同步变 99（共享存储）", 10.5, INK))

    # ---------- 右面板：搬家 ----------
    rx, ry = 550, 168
    b.append(sketch_rect(rx, ry, 470, 380, fill="#ffffff", sw=2.2))
    b.append(txt(rx + 20, ry + 30, "命运② 搬家：存储真的重排", 14, ORANGE,
                 bold=True))
    b.append(txt(rx + 28, ry + 62, "A.T 视图（输入同左）", 12, INK, bold=True))
    b.append(tgrid(rx + 28, ry + 72, 44, 38, 3, 2, [1, 4, 2, 5, 3, 6]))
    b.append(txt(rx + 200, ry + 64, "ascontiguous-", 9.5, ORANGE, "middle"))
    b.append(txt(rx + 200, ry + 77, "array", 9.5, ORANGE, "middle"))
    b.append(sketch_line(rx + 160, ry + 96, rx + 240, ry + 96, stroke=ORANGE,
                         sw=2.2, arrow=True))
    b.append(txt(rx + 260, ry + 62, "副本  strides (2,1)", 12, INK, bold=True))
    b.append(tgrid(rx + 260, ry + 72, 44, 38, 3, 2, [1, 4, 2, 5, 3, 6]))

    sy2 = ry + 236
    b.append(txt(rx + 28, sy2 - 12, "搬家后的新存储（读序规整 0..5）：", 11.5,
                 INK))
    for i, v in enumerate([1, 4, 2, 5, 3, 6]):
        b.append(cell(rx + 28 + i * 52, sy2, 50, 36, str(v),
                      fill=TINT["orange"], size=13))
        b.append(txt(rx + 53 + i * 52, sy2 + 50, f"@{i}", 9, MUTED, "middle"))
    b.append(txt(rx + 28, sy2 + 68,
                 "值与视图版完全一致（语义不变），但内存独立、C-连续", 10.5, INK))
    b.append(txt(rx + 28, sy2 + 86,
                 "实测 2048×2048 f32：42.293 ms/次（视图 0.22 µs，差约 19 万倍）",
                 10.5, INK))
    b.append(txt(rx + 28, sy2 + 104,
                 "下游权利：连续副本可零拷贝 reshape；视图会被迫拷贝（Day 59）",
                 10.5, MUTED))

    # ---------- 底部：3D 非对合陷阱 ----------
    ty = 572
    b.append(sketch_rect(40, ty, 980, 178, fill=TINT["gray"], sw=2.2))
    b.append(txt(60, ty + 28, "3D 非对合陷阱：shape/strides 按 perm 拉，下标按逆排列走",
                 13.5, INK, bold=True))
    b.append(txt(60, ty + 54,
                 "B(2,3,4)  strides (12,4,1)  --perm (1,2,0)-->  (3,4,2)  strides (4,1,12)",
                 12, INK))
    b.append(txt(60, ty + 78,
                 "再做一次同款转置：(3,4,2) --(1,2,0)--> (4,2,3) ≠ 回到 B！必须用逆排列 (2,0,1) 才回去",
                 12, RED))
    b.append(txt(60, ty + 102,
                 "out[idx] = in[inv(idx)]，inv = (2,0,1)：输出下标元组到输入下标元组走的是逆排列",
                 11, INK))
    b.append(txt(60, ty + 126,
                 "2D 交换是「对合」：perm == inv == (1,0)，两个方向重合——这正是 3D 才暴露约定差异的原因",
                 11, MUTED))
    b.append(txt(60, ty + 152,
                 "排列的阶（实测）：恒等 1 · (1,0) 2 · (1,2,0) 3 · (1,2,3,0) 4——转 k 次回恒等，k 由循环节决定",
                 11, MUTED))
    save("02-mechanism.svg", "".join(b))


# ===========================================================================
# 图 3：三种命运实测对照
# ===========================================================================

def fig3() -> None:
    W, H = 1060, 700
    b = [header(W, H, "三种命运实测对照：同一个转置需求，三种代价",
                "贯穿例子 A(2,3) + 计时基准 2048×2048 f32（16 MiB）· 全部数字来自 outputs/transpose_lab.txt")]

    cols = [
        ("命运① 视图", "V = A.T", BLUE, "blue",
         [("shape / strides", "(3,2) / (1,3)"),
          ("存储", "与 A 共享（零拷贝 ✓）"),
          ("读序偏移", "[0,3,1,4,2,5] 蹦着走"),
          ("写穿联动", "V[0,1]=99 → A[1,0]=99"),
          ("连续性", "被破坏（非 C-连续）"),
          ("代价（实测）", "0.22 µs（O(1) 改账本）")]),
        ("命运② 搬家", "C = ascontiguousarray(A.T)", ORANGE, "orange",
         [("shape / strides", "(3,2) / (2,1) 规整"),
          ("存储", "独立新存储 [1,4,2,5,3,6]"),
          ("读序偏移", "[0,1,2,3,4,5] 规整"),
          ("写穿联动", "无（互不影响）"),
          ("连续性", "C-连续 ✓（可零拷贝 reshape）"),
          ("代价（实测）", "42.293 ms（O(numel) 搬字节）")]),
        ("命运③ 不落地", "消费方交换下标", GREEN, "green",
         [("形态", "linalg 降级后的双循环"),
          ("中间张量", "不存在转置结果"),
          ("语义位置", "活在索引里，不在数据里"),
          ("适用", "消费方能按 strided 读时")]),
    ]
    x0, y0, cw, ch = 40, 92, 316, 400
    for i, (title, act, color, tint, rows) in enumerate(cols):
        x = x0 + i * (cw + 26)
        b.append(sketch_rect(x, y0, cw, ch, fill=TINT[tint], sw=2.4))
        b.append(txt(x + 16, y0 + 28, title, 15, color, bold=True))
        b.append(txt(x + 16, y0 + 50, act, 11, INK))
        ry = y0 + 76
        for k, (label, val) in enumerate(rows):
            b.append(txt(x + 16, ry + 14, label, 10.5, MUTED))
            b.append(txt(x + 16, ry + 32, val, 11.5, INK, bold=True))
            ry += 52
            if k < len(rows) - 1:
                b.append(sketch_line(x + 14, ry - 8, x + cw - 14, ry - 8,
                                     opacity=0.25))

    # ③ 的代码片段
    cx, cy = x0 + 2 * (cw + 26) + 16, y0 + 306
    code = ["scf.for %i = 0 to 3", "  scf.for %j = 0 to 2",
            "    %v = load %a[%j, %i]", "    store %v, %b[%i, %j]"]
    for k, ln in enumerate(code):
        b.append(txt(cx, cy + k * 19, ln, 11.5,
                     GREEN if ("load" in ln or "store" in ln) else INK,
                     bold=("load" in ln or "store" in ln)))

    # 底部对比条
    by = 516
    b.append(sketch_rect(40, by, 980, 56, fill=TINT["red"], sw=2.2))
    b.append(txt(530, by + 24,
                 "视图改账本 · 搬家搬字节 · 不落地改索引——三者逻辑值完全相同，物理代价 0.22 µs : 42.293 ms : 0",
                 12.5, INK, "middle", bold=True))
    b.append(txt(530, by + 44,
                 "差约 1.9×10⁵ 倍（best-of-20，aarch64 / numpy 1.26.4 / Python 3.11.4，2026-11-12 实测）",
                 10.5, MUTED, "middle"))

    # 关键提醒
    by2 = 590
    b.append(sketch_rect(40, by2, 980, 66, fill="#ffffff", sw=2.0))
    b.append(txt(60, by2 + 26, "选错命运的后果：", 12, RED, bold=True))
    b.append(txt(180, by2 + 26,
                 "把②当①用 → 白付 19 万倍代价；把①当②用 → 下游拿非连续输入，reshape/向量化路径变慢或被迫再拷贝",
                 11.5, INK))
    b.append(txt(60, by2 + 50,
                 "编译器视角：mini.transpose 的语义只承诺「逻辑视角」，物理命运由下游需求（是否要连续）决定——这正是后面 Layout 传播的动机",
                 11.5, MUTED))
    save("03-fates.svg", "".join(b))


# ===========================================================================
# 图 4：Verifier 四关 × linalg 实测裁决
# ===========================================================================

def fig4() -> None:
    W, H = 1060, 780
    b = [header(W, H, "Verifier 四关 × linalg.transpose 实测：检查顺序决定报错质量",
                "mini：E1→E2→E3→E4，值域检查在「拿 perm[i] 索引 shape」之前 · MLIR：本机 LLVM 18.1.8 真实裁决")]

    # ---------- 左：mini 四关 ----------
    lx, ly = 40, 92
    b.append(txt(lx, ly + 6, "mini.transpose 四关（顺序是设计决策）：", 13, INK,
                 bold=True))
    gates = [
        ("E1 长度", "len(perm) == rank", "perm [0,1,2] 对 2 维输入 → 拒绝", "blue"),
        ("E2 值域", "0 ≤ perm[i] < rank", "perm [2,0] 对 2 维输入 → 拒绝（不许拿 2 去查维度）", "red"),
        ("E3 双射", "sorted(perm) == 0..rank-1", "perm [1,1]：维 1 用两次 → 拒绝", "blue"),
        ("E4 形状", "result[i] == in[perm[i]]", "结果写 2x3（应 3x2）→ 拒绝并写明约定", "blue"),
    ]
    gy = ly + 22
    for i, (tag, rule, sample, col) in enumerate(gates):
        y = gy + i * 74
        hl = col == "red"
        b.append(sketch_rect(lx, y, 400, 62, fill=TINT[col],
                             stroke=RED if hl else STROKE,
                             sw=2.6 if hl else 2.0))
        b.append(txt(lx + 14, y + 23, f"{tag}", 13,
                     RED if hl else BLUE, bold=True))
        b.append(txt(lx + 100, y + 23, rule, 12, INK, bold=True))
        b.append(txt(lx + 14, y + 47, sample, 10.5, MUTED))
        if i < 3:
            b.append(sketch_line(lx + 200, y + 62, lx + 200, y + 74,
                                 arrow=True))
    b.append(txt(lx, gy + 4 * 74 + 8,
                 "每条报错写明「哪一关 / 期望 / 实际」；E2 先于一切索引——", 11, INK))
    b.append(txt(lx, gy + 4 * 74 + 26,
                 "对照右侧 M6：linalg 缺值域检查，越界的 2 直接被拿去查 dim，读出乱码",
                 11, RED))

    # mini 报错样例（真实输出）
    ey = gy + 4 * 74 + 46
    b.append(sketch_rect(lx, ey, 400, 182, fill="#ffffff", sw=2.0))
    b.append(txt(lx + 14, ey + 24, "mini 报错样例（真实输出，可对照 M4–M7）：",
                 11, INK, bold=True))
    samples = [
        (RED, ["[E2] 排列第 0 项 2 超出输入秩 2 的",
               "合法范围 0..1：拒绝，而不是拿它去查维度"]),
        (BLUE, ["[E4] 结果第 0 维应为 3（= 输入第 1 维），",
                "实际写的 2：约定 out_shape[i] = in_shape[perm[i]]"]),
    ]
    yy = ey + 48
    for color, lines in samples:
        for ln in lines:
            b.append(txt(lx + 14, yy, ln, 10, color))
            yy += 18
        yy += 8
    b.append(txt(lx + 14, ey + 160,
                 "检查顺序：长度 → 值域 → 双射 → 形状（每步失败即返回）", 10,
                 MUTED))

    # ---------- 右：linalg 8 案例表 ----------
    rx, ry = 490, 92
    b.append(txt(rx, ry + 6, "linalg.transpose 真实裁决（8 案例实测）：", 13,
                 INK, bold=True))
    cases = [
        ("M1", "2x3 → 3x2", "[1,0]", 0, ""),
        ("M2", "2x3x4 → 4x2x3", "[2,0,1]", 0, "约定钉死 ✓"),
        ("M3", "2x3x4 → 3x4x2", "[2,0,1]", 1, "维序写反"),
        ("M4", "2x3 → 3x2", "[0,1,2]", 1, "E1 长度"),
        ("M5", "2x3 → 3x3", "[1,1]", 1, "E3 重复"),
        ("M6", "2x3 → 3x2", "[2,0]", 1, "E2 值域→乱码"),
        ("M7", "2x3 → 2x3", "[1,0]", 1, "E4 形状"),
        ("M8", "2x3 → 2x3", "[0,1]", 0, "恒等合法"),
    ]
    ty = ry + 22
    cols_x = [rx + 8, rx + 48, rx + 190, rx + 300, rx + 372]
    b.append(txt(cols_x[0], ty, "案", 11, MUTED, bold=True))
    b.append(txt(cols_x[1], ty, "in → out", 11, MUTED, bold=True))
    b.append(txt(cols_x[2], ty, "perm", 11, MUTED, bold=True))
    b.append(txt(cols_x[3], ty, "exit", 11, MUTED, bold=True))
    b.append(txt(cols_x[4], ty, "备注", 11, MUTED, bold=True))
    for i, (mid, io, pm, code, note) in enumerate(cases):
        y = ty + 16 + i * 26
        hl = mid in ("M2", "M3", "M6")
        b.append(txt(cols_x[0], y, mid, 11.5,
                     RED if mid == "M6" else (ORANGE if hl else INK),
                     bold=hl))
        b.append(txt(cols_x[1], y, io, 11, INK))
        b.append(txt(cols_x[2], y, pm, 11, INK))
        b.append(txt(cols_x[3], y, str(code), 12,
                     GREEN if code == 0 else RED, bold=True))
        b.append(txt(cols_x[4], y, note, 10, MUTED))
    b.append(sketch_line(rx + 4, ty + 8, rx + 460, ty + 8, opacity=0.4))
    b.append(sketch_line(rx + 4, ty + 12, rx + 460, ty + 12, opacity=0.4))

    # M2/M3 约定框
    cy = ty + 16 + 8 * 26 + 14
    b.append(sketch_rect(rx, cy, 464, 58, fill=TINT["orange"], sw=2.2))
    b.append(txt(rx + 14, cy + 22, "M2 vs M3 约定钉死（只差输出维序）：", 11.5,
                 ORANGE, bold=True))
    b.append(txt(rx + 14, cy + 42,
                 "报错原文即约定：dim(result, 0) = 3 doesn't match dim(input, permutation[0]) = 4",
                 10.5, INK))

    # M6 乱码框
    gy2 = cy + 72
    b.append(sketch_rect(rx, gy2, 464, 86, fill=TINT["red"],
                         stroke=RED, sw=2.6))
    b.append(txt(rx + 14, gy2 + 22, "M6 现场：值域检查缺失 → 越界读乱码（两次运行）",
                 11.5, RED, bold=True))
    b.append(txt(rx + 14, gy2 + 43,
                 "… permutation[0]) = 187651783086528", 10.5, INK))
    b.append(txt(rx + 14, gy2 + 60,
                 "… permutation[0]) = 187652031675040", 10.5, INK))
    b.append(txt(rx + 14, gy2 + 79,
                 "操作仍被拒（exit=1），但『维度』是未定义值——mini 的 E2 关为此而生",
                 10, MUTED))

    # ---------- 底部：验收汇总 ----------
    by = 668
    b.append(sketch_rect(40, by, 980, 62, fill=TINT["green"], sw=2.2))
    b.append(txt(60, by + 25, "今日验收（全部真实运行）：", 12, GREEN, bold=True))
    b.append(txt(240, by + 25,
                 "主实验 21/21 · 验收测试 63/63（A–H 八段）· 随机对拍 200/200 · 视图零拷贝 100/100 · MLIR 8 案例 exit 全符合",
                 11.5, INK))
    b.append(txt(60, by + 48,
                 "产出：mini.transpose Operation（IR 文本 + permutation 属性）· 四关 Verifier · transpose_2d.mlir / bad_transpose.mlir · outputs/ 全部留档",
                 11, MUTED))
    save("04-verdicts.svg", "".join(b))


if __name__ == "__main__":
    fig1()
    fig2()
    fig3()
    fig4()
