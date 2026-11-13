#!/usr/bin/env python3
"""make_images.py —— 第 68 天（Layout 转换传播）教程的四张手绘 sketch 风 SVG 信息图。

风格约定（与第 8/9/10 周各天一致，Excalidraw-like）：
  - 背景 #fdfaf2（米白），盒子白底 + 深灰 #6b6357 手绘描边
  - 强调色不超过 4 种柔和色：蓝 #4a7fa5 / 橙 #a8772e / 绿 #5a8a5a / 红 #b0605a
  - 线条带轻微抖动（L 段折线），圆头笔触，线宽 2 左右
  - 手写感字体栈：Comic Sans MS / Comic Neue / Kaiti SC / 楷体 / cursive
  - 只用矩形、格子、箭头、圆角框等简单几何形状

图中全部数字来自 2026-11-12 的真实运行（code/outputs/）：
  layout_prop_lab 39/39；test_layout_prop 37/37；
  MLIR 五探针：canonicalize 不推（1 transpose + 1 generic 原样）、
  互逆三明治保留 3 op、三明治降循环 6 for / 3 load / 3 store（每元素搬 3 遍）、
  相消后 2 for / 1 load / 1 store（每元素搬 1 遍）、
  tosa-layerwise-constant-fold 把 tosa.transpose(常量) 折成转置后的 const；
  mini 实测：三明治 2→0（搬运 24→0）、非互逆 2→1、链式 p³ 3→0（5 轮）、
  常量折叠 1→0、多使用者强推 op 3→4 转置 1→1、双向规则 2 轮振荡、
  reduce 反例 shape (3,1,4) vs (1,2,4)、reshape 反例 [[1,3,5],[2,4,6]] vs
  [[1,4,2],[5,3,6]]；压力 300/300，转置 912→165（-81.9%）。

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

rng = random.Random(68)


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
    print(f"wrote {path} ({path.stat().st_size} bytes)")


def panel_title(x, y, s, color=INK):
    return txt(x, y, s, 14, color, bold=True)


def badge(x, y, s, color, w=None):
    w = w or (len(s) * 7.2 + 14)
    return (sketch_rect(x, y, w, 22, fill=TINT["white"], stroke=color,
                        sw=1.8, nseg=4)
            + txt(x + w / 2, y + 15, s, 11.5, color, anchor="middle",
                  bold=True))


def grid(x, y, rows, cw=34, ch=24, fill=TINT["blue"], hl=None,
         hl_fill="#dce9f2", labels=None, stroke=STROKE):
    """画一个 rows×cols 的小矩阵格子；hl=(r,c) 高亮某格。"""
    nr = len(rows)
    nc = len(rows[0]) if nr else 0
    out = [sketch_rect(x, y, nc * cw, nr * ch, fill="none", sw=2.0)]
    for r in range(nr):
        for c in range(nc):
            f = hl_fill if (hl == (r, c)) else fill
            out.append(sketch_rect(x + c * cw, y + r * ch, cw, ch, fill=f,
                                   sw=1.6, nseg=3))
            if labels is not None:
                out.append(txt(x + c * cw + cw / 2, y + r * ch + ch / 2 + 4.5,
                               str(labels[r][c]), 11.5, INK,
                               anchor="middle"))
    return "".join(out)


# ============================================================
# 图 1：全貌
# ============================================================

def fig1() -> None:
    w, h = 1150, 790
    b = [header(w, h, "第 68 天全貌：Layout 转换传播",
                "第 10 周「Layout 与冗余算子消除」Day 5/6 —— 从「消贴在一起的」到「让转换动起来」"
                " ｜ 数字均为 2026-11-12 本机实测")]

    # ---- 顶部：本周时间线 ----
    b.append(txt(40, 92, "本周链路（第 10 周）", 13, MUTED, bold=True))
    days = [("D64", "转置语义"), ("D65", "转置消除"), ("D66", "Reshape 合并"),
            ("D67", "Cast 消除"), ("D68", "Layout 传播"),
            ("D69", "组合测试"), ("D70", "复盘")]
    bx, by, bw, bh, gap = 40, 102, 140, 46, 10
    for i, (d, t) in enumerate(days):
        x = bx + i * (bw + gap)
        today = d == "D68"
        b.append(sketch_rect(x, by, bw, bh,
                             fill=TINT["orange"] if today else TINT["gray"],
                             stroke=ORANGE if today else STROKE,
                             sw=3.0 if today else 2.0))
        b.append(txt(x + bw / 2, by + 19, d, 12.5,
                     ORANGE if today else MUTED, anchor="middle", bold=True))
        b.append(txt(x + bw / 2, by + 36, t, 12.5, INK, anchor="middle",
                     bold=today))
        if i < len(days) - 1:
            b.append(sketch_line(x + bw + 1, by + bh / 2, x + bw + gap - 1,
                                 by + bh / 2, arrow=True, sw=1.8))
    b.append(txt(bx + 4, by - 8,
                 "前四天：只认「贴在一起 / 同一行」的冗余", 11.5, MUTED))
    b.append(txt(bx + 4 * (bw + gap) + 2, by - 8,
                 "今天：让转换动起来去找伙伴", 11.5, ORANGE, bold=True))

    # ---- 中排：问题 / Pattern / 收益 ----
    y0 = 196
    # 问题框
    b.append(sketch_rect(40, y0, 340, 240, fill=TINT["white"]))
    b.append(panel_title(56, y0 + 24, "问题：被隔开的互逆三明治", RED))
    b.append(txt(56, y0 + 48, "NCHW 图里插一段 NHWC 逐元素计算：", 11.5, INK))
    gx, gy = 66, y0 + 62
    b.append(sketch_rect(gx, gy, 52, 30, fill=TINT["blue"]))
    b.append(txt(gx + 26, gy + 19, "NCHW", 11, BLUE, anchor="middle"))
    b.append(sketch_rect(gx + 76, gy, 56, 30, fill=TINT["orange"]))
    b.append(txt(gx + 104, gy + 19, "Relu", 11.5, ORANGE, anchor="middle"))
    b.append(sketch_rect(gx + 156, gy, 52, 30, fill=TINT["blue"]))
    b.append(txt(gx + 182, gy + 19, "NCHW", 11, BLUE, anchor="middle"))
    b.append(sketch_line(gx + 52, gy + 15, gx + 76, gy + 15, arrow=True))
    b.append(sketch_line(gx + 132, gy + 15, gx + 156, gy + 15, arrow=True))
    b.append(txt(gx + 64, gy + 8, "T_in", 11, RED, anchor="middle"))
    b.append(txt(gx + 144, gy + 8, "T_out", 11, RED, anchor="middle"))
    b.append(txt(56, y0 + 118,
                 "· T_out = T_in⁻¹，语义合计 = Relu(x)", 11.5, INK))
    b.append(txt(56, y0 + 138,
                 "· 但中间隔着 Relu —— D65 的合并够不着", 11.5, INK))
    b.append(txt(56, y0 + 158,
                 "· 运行时白搬 2 遍 O(numel)（loops 实测：", 11.5, INK))
    b.append(txt(56, y0 + 176,
                 "   6 for / 3 load / 3 store，每元素搬 3 遍）", 11.5, INK))
    b.append(badge(56, y0 + 196, "转换被「隔开」，消除规则失明", RED))

    # Pattern 框
    b.append(sketch_rect(410, y0, 320, 240, fill=TINT["white"]))
    b.append(panel_title(426, y0 + 24, "今天的受限 Pattern", BLUE))
    b.append(sketch_rect(436, y0 + 38, 268, 40, fill=TINT["blue"]))
    b.append(txt(570, y0 + 55, "T( E(x) )  →  E( T(x) )", 15, BLUE,
                 anchor="middle", bold=True))
    b.append(txt(570, y0 + 71, "Transpose 穿过逐元素算子，向生产者推",
                 11, MUTED, anchor="middle"))
    gates = [
        ("C1 语义门", "白名单只有 relu / neg（逐位置不变）"),
        ("C2 唯一使用者门", "T 是 E 结果的唯一使用者，否则增殖"),
        ("C3 方向门", "只向生产者推；双向会互相 undo"),
    ]
    for i, (g, d) in enumerate(gates):
        yy = y0 + 96 + i * 34
        b.append(sketch_rect(432, yy, 14, 22, fill=TINT["green"], sw=1.8,
                             nseg=3))
        b.append(txt(456, yy + 15, g, 12, GREEN, bold=True))
        b.append(txt(576, yy + 15, d, 11, INK))
    b.append(txt(426, y0 + 208,
                 "传播 = 移动，不是消除；收益在「会合点」兑现 →", 11.5, ORANGE,
                 bold=True))
    b.append(sketch_line(370, y0 + 120, 410, y0 + 120, arrow=True, sw=2.4))
    b.append(sketch_line(730, y0 + 120, 770, y0 + 120, arrow=True, sw=2.4))

    # 收益框
    b.append(sketch_rect(770, y0, 340, 240, fill=TINT["white"]))
    b.append(panel_title(786, y0 + 24, "收益与裁决（全部实测）", GREEN))
    rows = [
        ("会合相消", "互逆三明治：转置 2 → 0，搬运 24 → 0"),
        ("会合合并", "非互逆（r≠恒等）：转置 2 → 1"),
        ("推到常量", "T(Const) 折成 Const'：运行时 1 → 0"),
        ("链式递推", "3 个 (1,2,0)（p³=恒等）：3 → 0"),
    ]
    for i, (t, d) in enumerate(rows):
        yy = y0 + 46 + i * 32
        b.append(badge(786, yy, t, GREEN, w=74))
        b.append(txt(872, yy + 15, d, 11.5, INK))
    b.append(txt(786, y0 + 186, "挡下的反例：reduce / reshape / add /",
                 11.5, RED))
    b.append(txt(786, y0 + 204, "多使用者 / 双向振荡（见约束图）", 11.5, RED))

    # ---- 下排：MLIR 实测 / 验收 ----
    y1 = 470
    b.append(sketch_rect(40, y1, 530, 210, fill=TINT["white"]))
    b.append(panel_title(56, y1 + 24, "MLIR 实测（Ubuntu LLVM 18.1.8）", BLUE))
    facts = [
        ("push_probe --canonicalize", "不推：1 transpose + 1 generic 原样"),
        ("sandwich_probe --canonicalize", "不消：互逆三明治保留 3 个 op"),
        ("sandwich_memref --convert-linalg-to-loops",
         "6 for / 3 load / 3 store"),
        ("sandwich_after（相消后）同上", "2 for / 1 load / 1 store（3:1）"),
        ("tosa_const_probe --tosa-layerwise-constant-fold",
         "transpose(常量) 折成转置后的 const"),
    ]
    for i, (c, d) in enumerate(facts):
        yy = y1 + 48 + i * 30
        b.append(txt(60, yy, "· " + c, 11, BLUE))
        b.append(txt(330, yy, "→ " + d, 11, INK))
    b.append(txt(56, y1 + 200,
                 "结论：linalg 这条传播要自己写；tosa 做了「折常量」那一支",
                 11.5, ORANGE, bold=True))

    b.append(sketch_rect(600, y1, 510, 210, fill=TINT["white"]))
    b.append(panel_title(616, y1 + 24, "今日验收汇总", GREEN))
    acc = [
        ("layout_prop_lab.py", "39 / 39 通过"),
        ("test_layout_prop.py", "37 / 37 通过"),
        ("压力对拍 300 组随机图", "数值等价 300/300，全部收敛"),
        ("转置总数", "912 → 165（消掉 81.9%）"),
        ("语义约束说明", "1 条判据 + 裁决表 + 三道门"),
    ]
    for i, (t, d) in enumerate(acc):
        yy = y1 + 52 + i * 30
        b.append(txt(620, yy, "· " + t, 11.5, INK))
        b.append(txt(840, yy, d, 11.5, GREEN, bold=True))

    # ---- 底部：明天 ----
    y2 = 706
    b.append(sketch_rect(40, y2, 1070, 52, fill=TINT["gray"]))
    b.append(txt(60, y2 + 32, "明天（D69）图优化组合测试：", 13, INK,
                 bold=True))
    b.append(txt(310, y2 + 32,
                 "Pattern 组合后的不动点、意外无限变换、优化顺序 —— "
                 "今天方向门里那只「双向振荡」的虫子，明天正面处理",
                 12, MUTED))
    save("01-overview.svg", "".join(b))


# ============================================================
# 图 2：机制
# ============================================================

def fig2() -> None:
    w, h = 1150, 810
    b = [header(w, h, "Layout 传播机制：一行证明 + 三步收益链路 + 三道门",
                "左：为什么能穿（逐位置等价）｜中：收益链路（传播→会合→兑现）｜下：三道门（实测编号）")]

    # ---- 左：一行证明 ----
    b.append(sketch_rect(40, 88, 520, 470, fill=TINT["white"]))
    b.append(panel_title(56, 112, "① 合法性：一行证明（B, p=(1,0)）", BLUE))

    # B 矩阵
    bx, by = 66, 130
    labels = [["-1.5", "0.5", "2.0"], ["3.5", "-0.5", "-2.5"]]
    b.append(grid(bx, by, labels, cw=44, ch=26, labels=labels, hl=(1, 0),
                  hl_fill="#dce9f2"))
    b.append(txt(bx + 66, by - 8, "B (2×3)，高亮 B(1,0)=3.5", 10.5, MUTED,
                 anchor="middle"))

    # 两条路径
    # 上路：先 Relu 后 T
    b.append(txt(66, 216, "上路：先 Relu 再 T", 11.5, ORANGE, bold=True))
    b.append(sketch_rect(66, 226, 64, 28, fill=TINT["orange"], sw=2.0))
    b.append(txt(98, 245, "Relu", 11.5, ORANGE, anchor="middle", bold=True))
    b.append(sketch_line(130, 240, 166, 240, arrow=True))
    b.append(sketch_rect(166, 226, 92, 28, fill=TINT["red"], sw=2.0))
    b.append(txt(212, 245, "T (1,0)", 11.5, RED, anchor="middle", bold=True))

    # 下路：先 T 再 Relu
    b.append(txt(66, 288, "下路：先 T 再 Relu", 11.5, ORANGE, bold=True))
    b.append(sketch_rect(66, 298, 92, 28, fill=TINT["red"], sw=2.0))
    b.append(txt(112, 317, "T (1,0)", 11.5, RED, anchor="middle", bold=True))
    b.append(sketch_line(158, 312, 194, 312, arrow=True))
    b.append(sketch_rect(194, 298, 64, 28, fill=TINT["orange"], sw=2.0))
    b.append(txt(226, 317, "Relu", 11.5, ORANGE, anchor="middle", bold=True))

    # 输出矩阵（3x2），两路到达同一个
    ox, oy = 300, 240
    outl = [["0", "3.5"], ["0.5", "0"], ["2", "0"]]
    b.append(grid(ox, oy, outl, cw=40, ch=24, labels=outl, hl=(0, 1),
                  hl_fill="#dce9f2"))
    b.append(txt(ox + 40, oy - 8, "两边输出 (3×2)，高亮 (0,1)", 10.5, MUTED,
                 anchor="middle"))
    b.append(sketch_path([(258, 240), (292, 250)], arrow=True, curved=True,
                         stroke=ORANGE))
    b.append(sketch_path([(258, 312), (292, 292)], arrow=True, curved=True,
                         stroke=ORANGE))

    # 位置追踪
    b.append(sketch_rect(56, 350, 488, 56, fill=TINT["blue"]))
    b.append(txt(76, 371, "输出位置 (0,1)：两条路都取 relu( B(1,0) ) = 3.5",
                 12.5, BLUE, bold=True))
    b.append(txt(76, 392,
                 "位置追踪（q = p⁻¹）：(0,1)∘q = (1,0) —— 同源同值，顺序可交换",
                 11, INK))

    # 判据框
    b.append(sketch_rect(56, 420, 488, 58, fill=TINT["green"]))
    b.append(txt(76, 443, "判据（唯一的一条）：E(A)[idx] = e(A[idx)]",
                 13, GREEN, bold=True))
    b.append(txt(76, 465,
                 "「逐位置不变性」：输出只看同位置的输入 —— relu 换成 neg 证明一字不改",
                 10.5, INK))
    b.append(txt(56, 500,
                 "推导：T_p(Relu(x))[idx] = relu(x[idx∘q]) = Relu(T_p(x))[idx]   ∎",
                 11, MUTED))

    # ---- 右：三步链路 ----
    b.append(sketch_rect(580, 88, 530, 470, fill=TINT["white"]))
    b.append(panel_title(596, 112, "② 收益链路：传播 → 会合 → 兑现", GREEN))

    def mini_ops(x, y, items, wops=76, hops=30, gapx=14):
        for i, (lab, col) in enumerate(items):
            xx = x + i * (wops + gapx)
            b.append(sketch_rect(xx, y, wops, hops, fill=TINT[col], sw=2.0))
            b.append(txt(xx + wops / 2, y + 20, lab, 11.5,
                         {"red": RED, "orange": ORANGE, "blue": BLUE,
                          "green": GREEN}[col], anchor="middle", bold=True))
            if i < len(items) - 1:
                b.append(sketch_line(xx + wops + 1, y + hops / 2,
                                     xx + wops + gapx - 1, y + hops / 2,
                                     arrow=True, sw=1.6))

    # 步骤 1
    b.append(badge(596, 130, "步骤 1：三明治（转置被隔开）", ORANGE, w=232))
    mini_ops(596, 160, [("T_out", "red"), ("Relu", "orange"),
                        ("T_in", "red")])
    b.append(txt(596, 216, "转置 2 个 · 搬运 24 次元素移动（numel=6）",
                 10.5, MUTED))
    b.append(txt(596, 233, "D65 的合并看不见它们（隔着 Relu）", 10.5, RED))

    b.append(sketch_line(860, 258, 860, 278, arrow=True, sw=2.4))
    b.append(txt(872, 272, "传播（今天的 Pattern）", 10.5, BLUE, bold=True))

    # 步骤 2
    b.append(badge(596, 284, "步骤 2：穿过 Relu，两个转置相邻", BLUE, w=246))
    mini_ops(596, 314, [("Relu", "orange"), ("T_out", "red"),
                        ("T_in", "red")])
    b.append(txt(596, 370, "「相邻！」—— D65 的合并终于够得着输入", 10.5,
                 BLUE, bold=True))

    b.append(sketch_line(860, 392, 860, 412, arrow=True, sw=2.4))
    b.append(txt(872, 406, "合并（D65 复用）", 10.5, GREEN, bold=True))

    # 步骤 3
    b.append(badge(596, 418, "步骤 3：合并 r[i]=q[p[i]]，互逆则相消", GREEN,
                   w=268))
    mini_ops(596, 448, [("Relu", "orange"), ("T_r", "red")], wops=76)
    b.append(txt(596, 504,
                 "r = 恒等（q = p⁻¹）→ 相消：Relu(x)，转置 0，搬运 0",
                 10.5, GREEN, bold=True))
    b.append(txt(596, 522,
                 "r ≠ 恒等 → 合并：转置 2 → 1（搬运减半）；链式 p³=恒等：3 → 0（5 轮）",
                 10.5, INK))

    # ---- 下：三道门 ----
    y1 = 586
    b.append(txt(40, y1 - 8, "③ 三道门（全部有实测编号）", 13, RED, bold=True))
    gates = [
        ("C1 语义门", "白名单 = {relu, neg}", [
            "reduce ✗：同 axis 硬推 shape 抓住",
            "  (3,1,4) vs (1,2,4)；正确公式 axis→p⁻¹(k)",
            "reshape ✗：同 shape 也错值（位置重排）",
            "add △：两侧同 perm 才等价（选做挑战）"]),
        ("C2 唯一使用者门", "users(E) == [T]", [
            "多使用者强推（反面教材实测）：",
            "  数值仍对，但 op 3 → 4、转置 1 → 1",
            "  —— relu 被复制，合法但白干",
            "传播必须「移动」而不是「增殖」"]),
        ("C3 方向门", "只向生产者推", [
            "双向规则互相 undo（实测）：",
            "  2 轮后状态哈希回到起点 = 振荡",
            "单方向：300 组随机图全部收敛",
            "  （Day 69 的正题：组合与顺序）"]),
    ]
    for i, (t, sub, lines) in enumerate(gates):
        x = 40 + i * 365
        b.append(sketch_rect(x, y1, 345, 190, fill=TINT["white"]))
        b.append(badge(x + 16, y1 + 14, t, RED, w=132))
        b.append(txt(x + 162, y1 + 29, sub, 11, BLUE, bold=True))
        for j, ln in enumerate(lines):
            b.append(txt(x + 16, y1 + 60 + j * 26, ln, 11, INK))
    save("02-mechanism.svg", "".join(b))


# ============================================================
# 图 3：改写前后对照
# ============================================================

def fig3() -> None:
    w, h = 1150, 760
    b = [header(w, h, "三明治改写前后：mini IR 与 MLIR loops 的双重证据",
                "左：mini 实测（2 轮 fixpoint）｜右：MLIR 降循环实测（每元素搬 3 遍 vs 1 遍）"
                "｜右下：tosa 常量折叠实测")]

    # ---- 左：mini before/after ----
    b.append(sketch_rect(40, 88, 520, 530, fill=TINT["white"]))
    b.append(panel_title(56, 112, "① mini 侧（layout_prop_lab 实测）", BLUE))

    # before IR
    b.append(badge(56, 132, "改写前（互逆三明治）", RED, w=176))
    b.append(sketch_rect(56, 162, 240, 150, fill=TINT["gray"], sw=2.0))
    ir_before = ["%1 = arg              ; (2,3)",
                 "%2 = transpose %1, perm=[1,0]",
                 "%3 = relu %2",
                 "%4 = transpose %3, perm=[1,0]",
                 "return %4"]
    for i, ln in enumerate(ir_before):
        col = RED if "transpose" in ln else INK
        b.append(txt(70, 186 + i * 24, ln, 11.5, col))
    b.append(txt(310, 186, "op 4 · 转置 2", 12, RED, bold=True))
    b.append(txt(310, 206, "纯搬运 24 次元素移动", 11, RED))
    b.append(txt(310, 224, "= 2 × (读6 + 写6)", 10.5, MUTED))
    b.append(txt(310, 244, "（96 B，f32）", 10.5, MUTED))

    # arrow
    b.append(sketch_path([(270, 340), (270, 380)], arrow=True, sw=2.6))
    b.append(txt(284, 356, "传播 + 合并 + 相消", 11, GREEN, bold=True))
    b.append(txt(284, 372, "（run_passes 2 轮 fixpoint）", 10, MUTED))

    # after IR
    b.append(badge(56, 396, "改写后（只剩 Relu）", GREEN, w=164))
    b.append(sketch_rect(56, 426, 240, 100, fill=TINT["gray"], sw=2.0))
    ir_after = ["%1 = arg              ; (2,3)",
                "%6 = relu %1",
                "return %6"]
    for i, ln in enumerate(ir_after):
        b.append(txt(70, 450 + i * 24, ln, 11.5, INK))
    b.append(txt(310, 450, "op 2 · 转置 0", 12, GREEN, bold=True))
    b.append(txt(310, 470, "纯搬运 0 次元素移动", 11, GREEN))
    b.append(txt(310, 490, "数值对拍：逐位相等", 10.5, MUTED))
    b.append(txt(310, 510, "（3 组随机输入）", 10.5, MUTED))

    # 搬运条形对比
    b.append(txt(56, 544, "纯搬运（元素移动次数，numel=6）：", 11, INK))
    b.append(sketch_rect(56, 552, 240, 16, fill=TINT["red"], sw=1.6, nseg=4))
    b.append(txt(304, 564, "改写前 24", 11, RED, bold=True))
    b.append(sketch_rect(56, 576, 6, 16, fill=TINT["green"], sw=1.6, nseg=3))
    b.append(txt(70, 588, "改写后 0", 11, GREEN, bold=True))

    # ---- 右上：MLIR loops ----
    b.append(sketch_rect(580, 88, 530, 280, fill=TINT["white"]))
    b.append(panel_title(596, 112,
                         "② MLIR loops 侧（--convert-linalg-to-loops）", BLUE))

    b.append(badge(596, 132, "三明治（3 op，memref 版）", RED, w=196))
    b.append(txt(596, 178, "6 层 scf.for", 12, RED, bold=True))
    b.append(txt(596, 198, "3 行 memref.load", 12, RED, bold=True))
    b.append(txt(596, 218, "3 行 memref.store", 12, RED, bold=True))
    # 元素三跳示意：同一个元素依次穿过 3 个 op（各读一次写一次）
    for i in range(3):
        yy = 240 + i * 34
        b.append(sketch_rect(596, yy, 40, 22, fill=TINT["red"], sw=1.6,
                             nseg=3))
        b.append(txt(616, yy + 15, ["T_in", "Relu", "T_out"][i], 9.5, RED,
                     anchor="middle"))
        b.append(sketch_line(638, yy + 11, 686, yy + 11, arrow=True, sw=1.6))
    b.append(txt(640, 348, "↓ 同一个元素依次穿过 3 个 op", 9.5, MUTED))
    b.append(txt(700, 251, "每个元素被搬 3 遍", 11, RED, bold=True))
    b.append(txt(700, 269, "（18 次读+写 / 6 元素）", 10, MUTED))
    b.append(txt(700, 295, "→ 相消后（sandwich_after.mlir）", 11, GREEN,
                 bold=True))
    b.append(txt(700, 313, "2 层 for / 1 load / 1 store", 11, GREEN,
                 bold=True))
    b.append(txt(700, 331, "每元素只搬 1 遍（搬运 3:1）", 10.5, INK))
    b.append(txt(700, 352, "两个世界同一句话：隔开的转换白搬，", 10.5, ORANGE))
    b.append(txt(700, 366, "会合的转换才能省", 10.5, ORANGE))

    # ---- 右下：tosa 常量折叠 ----
    b.append(sketch_rect(580, 390, 530, 168, fill=TINT["white"]))
    b.append(panel_title(596, 414,
                         "③ tosa 常量折叠（--tosa-layerwise-constant-fold）",
                         GREEN))
    c1 = [["1", "-2", "3"], ["-4", "5", "-6"]]
    b.append(grid(620, 432, c1, cw=32, ch=22, labels=c1))
    b.append(txt(620, 424, "tosa.const (2×3)", 9.5, MUTED))
    b.append(txt(620, 508, "权重（常量）", 10, MUTED))
    b.append(sketch_line(724, 460, 788, 460, arrow=True, sw=2.2))
    b.append(txt(756, 450, "tosa.transpose", 10, BLUE, anchor="middle"))
    b.append(txt(756, 474, "被折掉 → 0 个", 9.5, RED, anchor="middle"))
    c2 = [["1", "-4"], ["-2", "5"], ["3", "-6"]]
    b.append(grid(800, 432, c2, cw=32, ch=22, labels=c2))
    b.append(txt(832, 424, "转置后的 const (3×2)", 9.5, MUTED))
    b.append(txt(800, 508, "编译期完成（离线转置）", 10, MUTED))
    b.append(txt(920, 452, "运行时零开销：", 11.5, GREEN, bold=True))
    b.append(txt(920, 470, "转置 1 → 0", 11, GREEN))
    b.append(txt(920, 492, "mini 同款：", 10.5, MUTED))
    b.append(txt(920, 508, "fold_transpose_", 10, MUTED))
    b.append(txt(920, 522, "into_constant", 10, MUTED))
    save("03-before-after.svg", "".join(b))


# ============================================================
# 图 4：语义约束说明
# ============================================================

def fig4() -> None:
    w, h = 1150, 800
    b = [header(w, h, "语义约束说明（今日产出）：能穿 / 不能穿 / 什么时候不许动",
                "唯一判据：逐位置不变性 ｜ 表中每一条裁决都有实测编号 ｜ 反例数值见 outputs/layout_prop_lab.txt")]

    # 判据横幅
    b.append(sketch_rect(40, 82, 700, 46, fill=TINT["green"]))
    b.append(txt(60, 110, "判据（唯一）：E(A)[idx] = e(A[idx)] —— "
                 "逐位置不变性", 14, GREEN, bold=True))
    b.append(txt(390, 110, "（shape 一致只是必要条件，不是判据）", 11, RED,
                 anchor="start"))

    # 裁决表
    tx, ty = 40, 150
    col1, col2, col3 = tx + 16, tx + 150, tx + 260
    # why 字段：字符串 = 单行；元组 = 手工分好的两行（避免中文被腰斩）
    rows = [
        ("relu", "✓ 直接穿", "逐位置同函数；白名单成员", GREEN),
        ("neg", "✓ 直接穿", "同上（ELEMENTWISE_WHITELIST）", GREEN),
        ("add", "△ 有条件", ("两侧同 perm 才等价；另一操作数",
                            "是张量则 +1 转置（收益另算）"), ORANGE),
        ("const（叶子）", "✓ 折进去", ("T(Const) → Const'；tosa 同款实测",
                                      "（运行时 1 → 0）"), GREEN),
        ("transpose", "⇒ 交给合并", ("T(T(x)) 不是传播问题：",
                                    "D65 合并 r[i]=p[q[i]]"), BLUE),
        ("reduce_sum", "✗ 需重映射", ("正确公式 axis → p⁻¹(k)；同 axis 硬推",
                                      "shape 抓住：(3,1,4) vs (1,2,4)"), RED),
        ("reshape", "✗ 反例", ("同 shape 也错值：[[1,3,5],[2,4,6]]",
                              "≠ [[1,4,2],[5,3,6]]（位置重新线性化）"), RED),
        ("conv / matmul", "✗ 不穿", ("跨位置加权混合",
                                     "（本周不展开，同属不能穿家族）"), RED),
        ("arg（图边界）", "⊥ 是墙", ("推到 arg 停下：布局由 ABI 决定，",
                                    "改签名是另一件事"), MUTED),
    ]
    rh = 52
    b.append(sketch_rect(tx, ty, 700, rh * len(rows) + 8, fill=TINT["white"]))
    for i, (op, verdict, why, col) in enumerate(rows):
        yy = ty + 8 + i * rh
        if i % 2 == 1:
            b.append(sketch_rect(tx + 4, yy, 692, rh - 4, fill=TINT["gray"],
                                 sw=1.2, nseg=3))
        b.append(txt(col1, yy + 20, op, 12.5, INK, bold=True))
        b.append(txt(col2, yy + 20, verdict, 12.5, col, bold=True))
        if isinstance(why, tuple):
            b.append(txt(col3, yy + 13, why[0], 10.5, INK))
            b.append(txt(col3, yy + 31, why[1], 10.5, INK))
        else:
            b.append(txt(col3, yy + 20, why, 10.5, INK))
        b.append(sketch_line(tx + 6, yy + rh - 4, tx + 694, yy + rh - 4,
                             sw=1.0, opacity=0.4))
    b.append(txt(tx, ty + rh * len(rows) + 26,
                 "表 = 「语义约束说明」本体：白名单从判据推出来，不靠 shape 检查",
                 11.5, MUTED))

    # 右列：三道门 + 压力汇总
    rx = 770
    b.append(sketch_rect(rx, 82, 340, 300, fill=TINT["white"]))
    b.append(panel_title(rx + 16, 106, "三道门（Pattern 里的三行 if）", RED))
    gates = [
        ("C1 语义门", "e.kind not in whitelist → 拒",
         "实测：reduce / reshape / add 全被拦下"),
        ("C2 唯一使用者门", "users(e) != [T] → 拒",
         "实测：强推则 op 3→4、转置 1→1（白干）"),
        ("C3 方向门", "Pattern 集里只有向下推",
         "实测：双向 2 轮振荡；单向 300/300 收敛"),
    ]
    for i, (g, code, ev) in enumerate(gates):
        yy = 124 + i * 84
        b.append(badge(rx + 16, yy, g, RED, w=124))
        b.append(txt(rx + 152, yy + 15, code, 10, BLUE))
        b.append(txt(rx + 16, yy + 40, ev, 10.5, INK))

    b.append(sketch_rect(rx, 402, 340, 176, fill=TINT["white"]))
    b.append(panel_title(rx + 16, 426, "压力对拍（300 组随机图）", GREEN))
    acc = [("数值等价", "300/300"), ("转置数不增", "300/300"),
           ("二次运行不动点", "300/300"), ("全部收敛", "300/300"),
           ("转置总数", "912 → 165（-81.9%）")]
    for i, (t, d) in enumerate(acc):
        yy = 446 + i * 26
        b.append(txt(rx + 16, yy, "· " + t, 11.5, INK))
        b.append(txt(rx + 176, yy, d, 11.5, GREEN, bold=True))

    b.append(sketch_rect(rx, 598, 340, 120, fill=TINT["orange"]))
    b.append(txt(rx + 16, 622, "为什么今天只做「受限」版", 12.5, ORANGE,
                 bold=True))
    b.append(txt(rx + 16, 644, "· 每扩一类算子，都要先补它的语义推导", 10.5,
                 INK))
    b.append(txt(rx + 16, 664, "  （add 两侧同 perm / reduce 重映射）", 10.5,
                 INK))
    b.append(txt(rx + 16, 684, "· 收益判断留给 Cost Model（第 11 周）", 10.5,
                 INK))
    b.append(txt(rx + 16, 704, "· 组合行为（振荡/顺序）是明天 D69 正题",
                 10.5, INK))
    save("04-constraints.svg", "".join(b))


if __name__ == "__main__":
    fig1()
    fig2()
    fig3()
    fig4()
    print("全部 4 张 SVG 生成完毕")
