#!/usr/bin/env python3
"""make_images.py —— 第 63 天（第 9 周复盘）教程的四张手绘 sketch 风 SVG 信息图。

风格约定（与第 8/9 周各天一致，Excalidraw-like）：
  - 背景 #fdfaf2（米白），盒子白底 + 深灰 #6b6357 手绘描边
  - 强调色不超过 4 种柔和色：蓝 #4a7fa5 / 橙 #a8772e / 绿 #5a8a5a / 红 #b0605a
  - 线条带轻微抖动（L 段折线），圆头笔触，线宽 2 左右
  - 手写感字体栈：Comic Sans MS / Comic Neue / Kaiti SC / 楷体 / cursive
  - 只用矩形、网格、箭头等简单几何形状

图中全部数字来自 2026-11-12 的真实运行（outputs/ 目录）：
  review_lab 24/24；行主序读序 [0,1,2,3,4,5]、列主序 [0,2,4,1,3,5]；
  NCHW strides (32,8,4,1) vs NHWC (32,1,16,4)；broadcast strides (0,1)；
  三房间 exit=0/1/0；特化链 exit=3 → exit=4；
  本周测试 Day57–63：14/20/26/48/41/28/29，合计 206/206。

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

rng = random.Random(63)


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
                opacity=1.0):
    out = [f'<path d="M {x0:.1f},{y0:.1f} L {x1:.1f},{y1:.1f}" '
           f'fill="none" stroke="{stroke}" stroke-width="{sw}" '
           f'stroke-linecap="round" stroke-linejoin="round" '
           f'opacity="{opacity}"/>']
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


def header(w, h, title, sub):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" '
            f'height="{h}" viewBox="0 0 {w} {h}">\n'
            f'<rect width="{w}" height="{h}" fill="{BG}"/>\n'
            + txt(40, 38, title, 20, INK, bold=True) + "\n"
            + txt(40, 61, sub, 12, MUTED) + "\n")


def cell(x, y, w, h, label, fill="#ffffff", stroke=STROKE, size=13,
         fill_color=INK, sw=2.0, sub=None):
    out = [sketch_rect(x, y, w, h, fill=fill, stroke=stroke, sw=sw)]
    out.append(txt(x + w / 2, y + h / 2 + (4 if not sub else 0), label,
                   size, fill_color, anchor="middle", bold=True))
    if sub is not None:
        out.append(txt(x + w / 2, y + h / 2 + 15, sub, 8.5, MUTED,
                       anchor="middle"))
    return "".join(out)


def save(name: str, body: str) -> None:
    path = OUT / name
    path.write_text(body + "</svg>\n", encoding="utf-8")
    print(f"写出 {path}（{path.stat().st_size} B）")


# ===========================================================================
# 图 1：全貌——六天日程条 + 两条暗线（周公式 / 知识时间线）+ 两个命题
# ===========================================================================

def fig1() -> None:
    s = header(1240, 830,
               "第 63 天全貌：第 9 周复盘——六天汇成「一个张量＋一条公式＋一张时间线」",
               "上：第 9 周日程（今天收官）｜中：本周两条暗线——周公式与知识时间线"
               "｜下：今天要收口的两个命题")

    s += txt(40, 96, "第 9 周：Tensor、Shape、Stride 与 Layout（前六天各发一件工具，"
                     "今天全部串起来）：", 13.5, INK, bold=True) + "\n"
    days = [
        ("Day 57", "逻辑 Shape", "与物理布局"),
        ("Day 58", "NCHW/NHWC", "编译器 Layout"),
        ("Day 59", "Reshape", "合法性"),
        ("Day 60", "Broadcast", "规则"),
        ("Day 61", "动态 Shape", "三种表示"),
        ("Day 62", "特化入口", "静态化"),
    ]
    x = 40
    for i, (d, t1, t2) in enumerate(days):
        s += sketch_rect(x, 110, 150, 62, fill="#ffffff", sw=2.0)
        s += txt(x + 75, 129, d, 12, INK, anchor="middle", bold=True) + "\n"
        s += txt(x + 75, 146, t1, 10, MUTED, anchor="middle") + "\n"
        s += txt(x + 75, 161, t2, 10, MUTED, anchor="middle") + "\n"
        if i < 5:
            s += sketch_line(x + 150, 141, x + 162, 141, sw=2.0, arrow=True)
        x += 162
    # 复盘盒（橙）
    s += sketch_rect(1020, 104, 180, 74, fill=TINT["orange"], stroke=ORANGE,
                     sw=2.6)
    s += txt(1110, 126, "Day 63", 12, ORANGE, anchor="middle", bold=True)
    s += txt(1110, 144, "周复盘", 11, INK, anchor="middle", bold=True)
    s += txt(1110, 160, "（今天）", 10, MUTED, anchor="middle")
    s += sketch_line(1000, 141, 1014, 141, stroke=ORANGE, sw=2.4,
                     arrow=True)
    s += txt(560, 196, "六天的工具，今天用同一个张量 A = [[1,2,3],[4,5,6]]"
                       "（第 61/62 天 MatMul 的左操作数）全部串成一条线",
             11.5, MUTED, anchor="middle") + "\n"

    # ---- 暗线一：周公式 ----
    s += sketch_rect(40, 218, 560, 306, fill="#ffffff", sw=2.2)
    s += txt(60, 244, "暗线一：周公式（第 57 天的偏移公式，升格为全周内核）",
             13, BLUE, bold=True) + "\n"
    s += sketch_rect(70, 258, 500, 46, fill=TINT["blue"], stroke=BLUE, sw=2.2)
    s += txt(320, 287, "物理偏移(idx) = storage_offset + Σ idx[i] × strides[i]",
             14.5, BLUE, anchor="middle", bold=True) + "\n"
    rows = [
        ("Day 57", "定义公式：Shape / Stride / Offset 三件套"),
        ("Day 58", "NCHW/NHWC：同一个 Shape 换一整套 strides"),
        ("Day 59", "Reshape：Shape 变、存储不动（只改元信息）"),
        ("Day 60", "Broadcast：stride 出现新取值 0（虚拟复制）"),
        ("Day 61", "动态维度：数值未知，公式照常记账"),
        ("Day 62", "特化：运行期观测值钉回类型"),
    ]
    y = 322
    for d, t in rows:
        s += txt(84, y, d, 11, MUTED, bold=True) + "\n"
        s += txt(146, y, t, 11.5, INK) + "\n"
        y += 27

    # ---- 暗线二：知识时间线 ----
    s += sketch_rect(630, 218, 570, 306, fill="#ffffff", sw=2.2)
    s += txt(650, 244, "暗线二：知识时间线——每一维的数值由谁、何时知道",
             13, RED, bold=True) + "\n"
    states = [
        ("静态 static", "编译期写死", "Verifier 可查", BLUE),
        ("符号 sym", "编译期只有名字", "同名同值对账", GREEN),
        ("未知 runtime", "运行期描述符 sizes[]", "放行但欠账", ORANGE),
        ("特化 specialized", "观测后钉回类型", "重推＋重验", RED),
    ]
    bx, by, bw, bh = 648, 262, 126, 84
    for i, (t1, t2, t3, c) in enumerate(states):
        s += sketch_rect(bx, by, bw, bh, fill=TINT[
            {BLUE: "blue", GREEN: "green", ORANGE: "orange",
             RED: "red"}[c]], stroke=c, sw=2.2)
        s += txt(bx + bw / 2, by + 24, t1, 10.5, c, anchor="middle",
                 bold=True) + "\n"
        s += txt(bx + bw / 2, by + 44, t2, 9.5, INK, anchor="middle") + "\n"
        s += txt(bx + bw / 2, by + 64, t3, 9.5, INK, anchor="middle") + "\n"
        if i < 3:
            s += sketch_line(bx + bw, by + bh / 2, bx + bw + 16,
                             by + bh / 2, sw=2.0, arrow=True)
        bx += bw + 16
    s += txt(650, 380, "A 的 dim0（M）的四档状态，对应四套检查方式：", 11.5,
             INK) + "\n"
    notes = [
        "房间 2 实测：全静态 K 失配 → mlir-opt exit=1（编译期拦截）",
        "房间 1/3 实测：带 ? → exit=0 放行，约束退到运行期",
        "特化复验实测：blind_k 特化 → mini exit=3 / mlir-opt exit=4",
    ]
    y = 402
    for n in notes:
        s += txt(664, y, "· " + n, 10.5, MUTED) + "\n"
        y += 24
    s += txt(650, 486, "约束没有消失，只是换了检查时机与检查者——命题二的全部内容",
             11.5, RED, bold=True) + "\n"
    s += sketch_line(630, 500, 1190, 500, stroke=RED, sw=1.2, opacity=0.25)

    # ---- 两个命题 ----
    s += sketch_rect(40, 548, 560, 150, fill=TINT["blue"], stroke=BLUE, sw=2.4)
    s += txt(60, 576, "命题一：Shape 相同 ≠ 内存布局相同", 14, BLUE,
             bold=True) + "\n"
    s += txt(60, 600, "同一个逻辑形状 (2,3)：行主序 strides (3,1)，列主序 (1,2)",
             11.5, INK) + "\n"
    s += txt(60, 622, "物理读序 0→1→2→3→4→5（连续） vs 0→2→4→1→3→5（跳跃）",
             11.5, INK) + "\n"
    s += txt(60, 646, "4D 放大版：NCHW (32,8,4,1) vs NHWC (32,1,16,4)",
             11.5, INK) + "\n"
    s += txt(60, 672, "证人：Day 57 / 58 / 59 / 60（今天 17 组现场复验）",
             11, MUTED) + "\n"

    s += sketch_rect(630, 548, 570, 150, fill=TINT["red"], stroke=RED, sw=2.4)
    s += txt(650, 576, "命题二：动态维度 ≠ 没有约束", 14, RED, bold=True) + "\n"
    s += txt(650, 600, "memref<?x3xf32>：M 的数值未知，但 rank=2、K=3 钉死",
             11.5, INK) + "\n"
    s += txt(650, 622, "? 的代价：一处未知让一串静态检查失明（?x4·3x2 放行）",
             11.5, INK) + "\n"
    s += txt(650, 646, "约束搬家链：静态拦截 → 动态放行 → 特化后拦截回归",
             11.5, INK) + "\n"
    s += txt(650, 672, "证人：Day 61 / 62（今天三房间 + 特化链复验）", 11,
             MUTED) + "\n"

    # ---- 明天预告 ----
    s += sketch_rect(40, 726, 1160, 62, fill=TINT["green"], stroke=GREEN,
                     sw=2.2)
    s += txt(620, 750, "明天（Day 64）：Transpose 的语义——维度排列、物理数据移动"
                       "与视图的差别", 12.5, GREEN, anchor="middle",
             bold=True) + "\n"
    s += txt(620, 772, "正是今天「A.T 视图（strides (1,3)，零拷贝） vs A.T 副本"
                       "（strides (2,1)，真重排）」这一对身份的正式立案",
             11, MUTED, anchor="middle") + "\n"

    save("01-overview.svg", s)


# ===========================================================================
# 图 2：核心机制——一条公式，两种走法（行主序 vs 列主序 + stride-0）
# ===========================================================================

def fig2() -> None:
    s = header(1240, 800,
               "核心机制：一条公式，两种走法——同一个 A(2,3) 在内存里的两条路径",
               "上：周公式｜中：行主序 vs 列主序的格子映射（箭头＝逻辑元素到物理字节）"
               "｜下：stride-0 的虚拟复制")

    s += sketch_rect(40, 78, 1160, 58, fill=TINT["blue"], stroke=BLUE, sw=2.4)
    s += txt(620, 103, "周公式：物理偏移(i,j) = storage_offset + i×s₀ + j×s₁",
             16, BLUE, anchor="middle", bold=True) + "\n"
    s += txt(620, 124, "Shape 管逻辑走多远 · Stride 管每步跨多大 · Offset 管从哪出发"
                       "（本周六天的全部概念都在改这三个数的「谁说了算」）",
             11, INK, anchor="middle") + "\n"

    def panel(px, tag, strides, store, seq, seq_note, tint, stroke_c):
        out = ""
        out += sketch_rect(px, 158, 570, 400, fill="#ffffff", sw=2.2)
        out += txt(px + 20, 186, tag, 13.5, stroke_c, bold=True) + "\n"
        out += txt(px + 20, 208, f"strides = {strides}    "
                                 f"存储 = {store}", 12, INK) + "\n"
        # 逻辑矩阵 2×3
        mx, my, cw, ch = px + 120, 226, 56, 46
        out += txt(px + 76, my + 30, "逻辑视图", 10.5, MUTED) + "\n"
        for i in range(2):
            for j in range(3):
                v = i * 3 + j + 1
                out += cell(mx + j * (cw + 8), my + i * (ch + 8), cw, ch,
                            f"{v}", fill=tint, stroke=stroke_c, size=14)
                out += txt(mx + j * (cw + 8) + 6, my + i * (ch + 8) + 14,
                           f"A[{i},{j}]", 8, MUTED)
        out += txt(mx - 12, my + ch / 2 + 4, "i=0", 9, MUTED,
                   anchor="end") + "\n"
        out += txt(mx - 12, my + ch + 8 + ch / 2 + 4, "i=1", 9, MUTED,
                   anchor="end") + "\n"
        for j in range(3):
            out += txt(mx + j * (cw + 8) + cw / 2, my - 8, f"j={j}", 9,
                       MUTED, anchor="middle") + "\n"
        # 物理存储条
        sy = 432
        out += txt(px + 76, sy + 24, "物理存储", 10.5, MUTED) + "\n"
        for k, v in enumerate(store):
            out += cell(px + 118 + k * 56, sy, 48, 40, f"{v}",
                        fill="#ffffff", stroke=STROKE, size=13)
            out += txt(px + 118 + k * 56 + 24, sy + 54, f"{k}", 9, MUTED,
                       anchor="middle") + "\n"
        out += txt(px + 118, sy + 70, "物理偏移 →", 9, MUTED) + "\n"
        # 箭头：逻辑元素 → 物理格子（值定格子，两面板的连线形状天然不同）
        for i in range(2):
            for j in range(3):
                v = i * 3 + j + 1
                k = store.index(v)
                x0 = mx + j * (cw + 8) + cw / 2
                y0 = my + i * (ch + 8) + ch
                x1 = px + 118 + k * 56 + 24
                out += sketch_line(x0, y0 + 4, x1, sy - 6, stroke=stroke_c,
                                   sw=1.4, opacity=0.55)
        out += txt(px + 20, 522, seq_note, 10.5, MUTED) + "\n"
        out += txt(px + 20, 544, f"逻辑读序偏移：{seq}", 12.5, stroke_c,
                   bold=True) + "\n"
        return out

    s += panel(40, "行主序（身份 1）——连续，缓存友好",
               "(3, 1)", [1, 2, 3, 4, 5, 6],
               "0 → 1 → 2 → 3 → 4 → 5",
               "相邻逻辑元素在内存里也相邻；A[1,2] = 1×3+2×1 = 偏移 5",
               TINT["blue"], BLUE)
    s += panel(630, "列主序（身份 2）——跳跃，物理上蹦着走",
               "(1, 2)", [1, 4, 2, 5, 3, 6],
               "0 → 2 → 4 → 1 → 3 → 5",
               "同样的逻辑读序走另一条路；A[1,2] = 1×1+2×2 = 偏移 5（值仍是 6）",
               TINT["green"], GREEN)

    # ---- 底部：stride-0 ----
    s += sketch_rect(40, 576, 1160, 180, fill="#ffffff", sw=2.2)
    s += txt(60, 604, "stride 的第三种戏法：0 —— Broadcast 的虚拟复制（Day 60）",
             13.5, ORANGE, bold=True) + "\n"
    s += txt(60, 628, "r = [7, 8, 9]，broadcast_to(r, (2,3))：逻辑 shape (2,3)，"
                      "元素 strides = (0, 1)", 11.5, INK) + "\n"
    for row, yy in ((0, 650), (1, 700)):
        s += txt(80, yy + 24, f"R[{row},:]", 10.5, MUTED) + "\n"
        for k, v in enumerate((7, 8, 9)):
            s += cell(130 + k * 56, yy, 48, 38, f"{v}",
                      fill=TINT["orange"], stroke=ORANGE, size=13)
        ty2 = 686 if row == 0 else 702
        s += sketch_line(352, yy + 19, 424, ty2, stroke=ORANGE, sw=1.8,
                         arrow=True, opacity=0.8)
    for k, v in enumerate((7, 8, 9)):
        s += cell(430 + k * 56, 675, 48, 38, f"{v}", fill="#ffffff",
                  stroke=STROKE, size=13)
    s += txt(604, 697, "r 的 3 个字节", 10, MUTED) + "\n"
    s += txt(660, 654, "第 0 行与第 1 行的物理偏移完全相同 [0,1,2]：", 11.5,
             INK) + "\n"
    s += txt(660, 676, "6 个逻辑元素只占 3 个物理位置——stride-0 是「记账上的复制」，",
             11.5, INK) + "\n"
    s += txt(660, 698, "不是字节上的复制；视图只读（写它抛 ValueError）", 11.5,
             INK) + "\n"
    s += txt(660, 724, "A + r = [[8,10,12],[11,13,15]]：广播后逻辑上像复制了"
                       "两行再相加", 11.5, MUTED) + "\n"

    save("02-mechanism.svg", s)


# ===========================================================================
# 图 3：实例对照——六种身份 + 三房间裁决（真实实验数字）
# ===========================================================================

def fig3() -> None:
    s = header(1240, 880,
               "实例对照：同一份数据的六种身份，与「动态不等于没约束」的三房间裁决",
               "左：6 个数字的六种记账方式（review_lab 段 1–5，全部真实输出）"
               "｜右：命题二的 Verifier 裁决与特化复验（段 6）")

    # ---- 左：存储 + 六身份 ----
    s += txt(40, 100, "两份底层存储（都是 6 个 f32，排列不同）：", 12, INK,
             bold=True) + "\n"
    for k, v in enumerate((1, 2, 3, 4, 5, 6)):
        s += cell(60 + k * 48, 112, 42, 36, f"{v}", fill=TINT["blue"],
                  stroke=BLUE, size=13)
    s += txt(356, 134, "S_row（行主序的家）", 10, MUTED) + "\n"
    for k, v in enumerate((1, 4, 2, 5, 3, 6)):
        s += cell(60 + k * 48, 162, 42, 36, f"{v}", fill=TINT["green"],
                  stroke=GREEN, size=13)
    s += txt(356, 184, "S_col（列主序的家）", 10, MUTED) + "\n"

    cards = [
        ("① 行主序视图", "shape (2,3) · strides (3,1) · offset 0",
         "共享 S_row · 连续，reshape 可零拷贝", BLUE, "blue"),
        ("② 列主序视图", "shape (2,3) · strides (1,2)",
         "共享 S_col · 读序 [0,2,4,1,3,5] 跳跃", GREEN, "green"),
        ("③ A.T 视图", "shape (3,2) · strides (1,3)",
         "共享 S_row · 零拷贝转置（改一处联动）", BLUE, "blue"),
        ("④ A.T 副本", "shape (3,2) · strides (2,1)",
         "自有存储 [1,4,2,5,3,6] · reshape 仍零拷贝", STROKE, "gray"),
        ("⑤ reshape 家族", "(6,) (2,3) (3,2) (1,6) (6,1) (1,2,3)",
         "全是 S_row 的零拷贝视图（数量不变⇒只改元信息）", BLUE, "blue"),
        ("⑥ broadcast 视图", "r=(3,) → (2,3) · strides (0,1)",
         "共享 r · 只读 · 6 个逻辑元素占 3 个物理位", ORANGE, "orange"),
    ]
    cw2, ch2 = 288, 118
    for idx, (t1, t2, t3, c, tint) in enumerate(cards):
        col, row = idx % 2, idx // 2
        x = 40 + col * (cw2 + 14)
        y = 220 + row * (ch2 + 14)
        s += sketch_rect(x, y, cw2, ch2, fill=TINT[tint], stroke=c, sw=2.2)
        s += txt(x + 14, y + 24, t1, 12.5, c if c != STROKE else INK,
                 bold=True) + "\n"
        s += txt(x + 14, y + 48, t2, 10.5, INK) + "\n"
        s += txt(x + 14, y + 72, t3, 10, MUTED) + "\n"
        if row == 2:
            pass
    s += txt(40, 640, "六种身份共用一条周公式，逻辑值全部等于 A = [[1,2,3],"
                      "[4,5,6]]——", 11.5, INK, bold=True) + "\n"
    s += txt(40, 662, "差别只在（shape, strides, offset）这本账，和账本背后"
                      "是不是同一份字节。", 11.5, INK, bold=True) + "\n"
    s += sketch_rect(40, 680, 590, 60, fill="#ffffff", sw=2.0)
    s += txt(335, 705, "真实读序对照（按逻辑行优先序走过 S_row / S_col）：",
             11, INK, anchor="middle") + "\n"
    s += txt(335, 726, "身份① [0,1,2,3,4,5]  vs  身份② [0,2,4,1,3,5]",
             11.5, RED, anchor="middle", bold=True) + "\n"

    # ---- 右：三房间 + 特化链 ----
    rx = 660
    s += sketch_rect(rx, 88, 540, 396, fill="#ffffff", sw=2.2)
    s += txt(rx + 20, 114, "命题二现场：三房间 Verifier 裁决（mlir-opt 18.1.8 实测）",
             12.5, RED, bold=True) + "\n"
    rooms = [
        ("房间 1 合法动态", "memref<?x3xf32> · memref<3x2xf32> → memref<?x2xf32>",
         "exit = 0 放行", "M 未知但 rank=2、K=3 静态可查；约束退到运行期",
         GREEN, "green"),
        ("房间 2 全静态失配", "memref<2x4xf32> · memref<3x2xf32> → memref<2x2xf32>",
         "exit = 1 拦截", "K = 4 vs 3 无处可藏——编译期当场抓住",
         RED, "red"),
        ("房间 3 失明现场", "memref<?x4xf32> · memref<3x2xf32> → memref<?x2xf32>",
         "exit = 0 放行", "K 明明静态失配，M 的 ? 拖瞎了整串静态检查",
         ORANGE, "orange"),
    ]
    ry = 130
    for t1, t2, t3, t4, c, tint in rooms:
        s += sketch_rect(rx + 20, ry, 500, 100, fill=TINT[tint], stroke=c,
                         sw=2.2)
        s += txt(rx + 36, ry + 22, t1, 12, c, bold=True) + "\n"
        s += txt(rx + 36, ry + 44, t2, 10, INK) + "\n"
        s += txt(rx + 36, ry + 66, t3, 11.5, c, bold=True) + "\n"
        s += txt(rx + 36, ry + 88, t4, 9.5, MUTED) + "\n"
        ry += 112

    s += sketch_rect(rx, 500, 540, 240, fill="#ffffff", sw=2.2)
    s += txt(rx + 20, 526, "特化复验：同一份 blind_k.mlir（Day 62 工具）",
             12.5, RED, bold=True) + "\n"
    s += sketch_rect(rx + 20, 540, 500, 66, fill=TINT["red"], stroke=RED,
                     sw=2.0)
    s += txt(rx + 36, 562, "第 1 步  --specialize-shape \"a=2x4,b=3x2\"（不加 force）",
             10.5, INK) + "\n"
    s += txt(rx + 36, 584, "exit = 3 —— mini 层 K 对账点名拒绝：%a 的 dim1=4，"
                            "%b 的 dim0=3", 10.5, RED, bold=True) + "\n"
    s += sketch_rect(rx + 20, 616, 500, 66, fill=TINT["red"], stroke=RED,
                     sw=2.0)
    s += txt(rx + 36, 638, "第 2 步  加 --force：写出产物，交给外部 Verifier",
             10.5, INK) + "\n"
    s += txt(rx + 36, 660, "exit = 4 —— mlir-opt 拦下：operand #1 ... to be 4, "
                            "but found 3", 10.5, RED, bold=True) + "\n"
    s += txt(rx + 20, 706, "约束搬家链闭环：", 11.5, INK, bold=True) + "\n"
    s += txt(rx + 150, 706, "静态拦截 (exit=1) → 动态放行 (exit=0) → "
                            "特化后拦截回归 (exit=3/4)", 11.5, RED,
             bold=True) + "\n"
    s += txt(rx + 20, 728, "? 只隐瞒「数值」，从不豁免「规矩」——检查可以搬家，"
                            "不会消失。", 10.5, MUTED) + "\n"

    # ---- 底部结论条 ----
    s += sketch_rect(40, 770, 1160, 74, fill=TINT["gray"], stroke=STROKE,
                     sw=2.0)
    s += txt(620, 796, "主实验 review_lab.py：24/24 PASS（含 17 组命题一现场、"
                       "三房间裁决、特化链、知识四档表）", 12, INK,
             anchor="middle", bold=True) + "\n"
    s += txt(620, 820, "验收测试 test_review.py：29/29 PASS（含 120 组随机视图"
                       "公式对账、100 组同 shape 不同布局对拍）", 12, INK,
             anchor="middle", bold=True) + "\n"

    save("03-identities.svg", s)


# ===========================================================================
# 图 4：本周全部测试汇总板（真实数字 206/206）
# ===========================================================================

def fig4() -> None:
    s = header(1240, 720,
               "本周全部测试：7 套 206 个测试点全部通过（2026-11-12 本机实测）",
               "Day 57–62 六套验收测试 + 今天复盘测试，一键复跑："
               "bash run_week_tests.sh（日志存 outputs/week_tests/）")

    s += txt(40, 96, "逐日结果（退出码全为 0）：", 12.5, INK, bold=True) + "\n"
    rows = [
        ("Day 57", "test_layout.py", 14, BLUE, "blue"),
        ("Day 58", "test_layout.py", 20, GREEN, "green"),
        ("Day 59", "test_reshape.py", 26, BLUE, "blue"),
        ("Day 60", "test_broadcast.py", 48, GREEN, "green"),
        ("Day 61", "test_dynamic.py", 41, BLUE, "blue"),
        ("Day 62", "test_specialize.py", 28, GREEN, "green"),
        ("Day 63", "test_review.py", 29, ORANGE, "orange"),
    ]
    # 左：表格
    tx, ty, rh = 40, 108, 52
    s += txt(tx + 66, ty + 20, "Day", 11, MUTED, anchor="middle", bold=True)
    s += txt(tx + 220, ty + 20, "测试文件", 11, MUTED, anchor="middle",
             bold=True)
    s += txt(tx + 360, ty + 20, "测试点", 11, MUTED, anchor="middle",
             bold=True)
    s += txt(tx + 460, ty + 20, "退出码", 11, MUTED, anchor="middle",
             bold=True)
    y = ty + 30
    for d, f, n, c, tint in rows:
        s += sketch_rect(tx, y, 520, rh - 8, fill=TINT[tint], stroke=c,
                         sw=1.8)
        s += txt(tx + 66, y + 30, d, 12, c, anchor="middle", bold=True)
        s += txt(tx + 220, y + 30, f, 11.5, INK, anchor="middle")
        s += txt(tx + 360, y + 30, f"{n} PASS", 12, c, anchor="middle",
                 bold=True)
        s += txt(tx + 460, y + 30, "0", 12, GREEN, anchor="middle", bold=True)
        y += rh

    # 右：手绘条形图
    bx, by = 640, 108
    s += txt(bx, by - 4, "各套测试点数量（共 206）：", 12.5, INK,
             bold=True) + "\n"
    max_n, max_w = 48, 380
    yy = by + 24
    for d, f, n, c, tint in rows:
        w = max_w * n / max_n
        s += txt(bx, yy + 16, f"{d}", 10.5, MUTED) + "\n"
        s += sketch_rect(bx + 62, yy, w, 26, fill=TINT[tint], stroke=c,
                         sw=1.8)
        s += txt(bx + 62 + w + 12, yy + 18, f"{n}", 11.5, c, bold=True) + "\n"
        yy += 42
    s += txt(bx + 62, yy + 8, "一套一天，独立验收——今天再加一层「全周回归」",
             10.5, MUTED) + "\n"

    # 底部：两个命题 + 一页复盘
    s += sketch_rect(40, 560, 560, 86, fill=TINT["blue"], stroke=BLUE, sw=2.2)
    s += txt(60, 588, "命题一结论：Shape 相同但内存布局不同", 12.5, BLUE,
             bold=True) + "\n"
    s += txt(60, 612, "shape/strides/offset 三件套各自记账；判断「同一个张量」"
                      "要同时看三本账", 11, INK) + "\n"
    s += txt(60, 634, "（shares_memory / contiguous，而不是只比 shape）", 11,
             MUTED) + "\n"
    s += sketch_rect(630, 560, 570, 86, fill=TINT["red"], stroke=RED, sw=2.2)
    s += txt(650, 588, "命题二结论：动态维度不等于没有约束", 12.5, RED,
             bold=True) + "\n"
    s += txt(650, 612, "rank、静态维、取值合法性一条没少；? 的代价是让一部分"
                      "静态检查失明", 11, INK) + "\n"
    s += txt(650, 634, "（解法：运行期检查兜底 + 特化把检查钉回编译期）", 11,
             MUTED) + "\n"

    s += txt(620, 678, "一页复盘见 code/review-onepage.md · 环境：Python 3.11.4 · "
                       "numpy 1.26.4 · Ubuntu LLVM 18.1.8 · aarch64",
             11, MUTED, anchor="middle") + "\n"

    save("04-week-tests.svg", s)


if __name__ == "__main__":
    fig1()
    fig2()
    fig3()
    fig4()
    print("4 张 SVG 生成完毕")
