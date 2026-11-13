#!/usr/bin/env python3
"""生成第 92 天教程的 4 张手绘风（Excalidraw-like）SVG 技术图。

运行方式：
    python3 make_images.py

输出到 ../images/ 目录：
    01-overview.svg           第 92 天在第 14 周与编译链路中的位置 + 输入与产出
    02-innermost-anatomy.svg  核心机制：最内层下标决定步长；k 的位置决定累加器住哪
    03-trace-compare.svg      实例对照：i-j-k / i-k-j / j-k-i 的真实访存脚印（种子 92）
    04-results-table.svg      实测结果：对照表 + 缓存模拟柱图（真实轨迹回放）

风格与 Day 78~91 保持一致：手绘抖动线条、马克笔笔触、米白背景、
蓝/橙/绿/红四种柔和强调色、简单几何形状。
图中文字与数字全部来自 order_pass.py 的真实运行结果（OT1~OT5）。
"""

import math
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent.parent / "day-090" / "code"))

import order_pass as op_   # noqa: E402  （真实数据来源）

random.seed(92)

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
GREY = "#e9e4d8"
FONT = "'Comic Sans MS','Segoe Print','Bradley Hand','Kaiti SC','KaiTi','STKaiti',cursive"

OUT = HERE.parent / "images"
OUT.mkdir(exist_ok=True)


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


def srect(x, y, w, h, fill="none", stroke=INK, sw=2.2, amp=1.3, dash=None, rx=0):
    pts = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
    d = " ".join(jseg(*p, *q, amp) for p, q in zip(pts, pts[1:] + pts[:1]))
    r = f' rx="{rx}"' if rx else ""
    return f'<path d="{d} Z" {style(fill, stroke, sw, dash)}{r}/>'


def scirc(x, y, r, fill="white", stroke=INK, sw=2.0):
    wob = random.uniform(-0.8, 0.8)
    return (f'<path d="M {x - r},{y + wob} C {x - r},{y - r} {x + r},{y - r} '
            f'{x + r},{y} C {x + r},{y + r} {x - r},{y + r} {x - r},{y + wob}" '
            f'{style(fill, stroke, sw)}/>')


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


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def text(x, y, s, size=16, fill=INK, anchor="start", rot=None, bold=False):
    t = (f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-size="{size}" '
         f'fill="{fill}"')
    if bold:
        t += ' font-weight="bold"'
    if rot:
        t += f' transform="rotate({rot} {x} {y})"'
    return t + f">{esc(s)}</text>"


def mtext(x, y, lines, size=12.5, fill=INK, anchor="start", lh=None):
    lh = lh or size + 4.5
    return "".join(text(x, y + i * lh, ln, size, fill, anchor) for i, ln in enumerate(lines))


def svg_doc(w, h, body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
            f'width="{w}" height="{h}">'
            f'<rect x="3" y="3" width="{w - 6}" height="{h - 6}" rx="7" fill="{BG}"/>'
            f'<g font-family="{FONT}">' + body + "</g></svg>")


def title_block(w, title, sub=None):
    body = text(30, 44, title, 25, INK)
    if sub:
        body += text(30, 70, sub, 14.5, SOFT)
    body += sline(30, 82, w - 30, 82, SOFT, 1.6, dash="7 6")
    return body


def save(name, w, h, body):
    (OUT / name).write_text(svg_doc(w, h, body), encoding="utf-8")
    print(f"{name} 已生成（{w}×{h}）")


# ============================================================
# 真实数据：与 order_pass.py 同源（import 复跑，不是手抄）
# ============================================================

RUNS = {op_.oname(o): op_.run_order(o, op_.M, op_.K, op_.N) for o in op_.ORDERS}
SIM_RUNS = {op_.oname(o): op_.run_order(o, *op_.SIM_SHAPE) for o in op_.ORDERS}
SIMS = {}
for o in op_.ORDERS:
    log = SIM_RUNS[op_.oname(o)]["interp"].access_log
    for ln in op_.SIM_CACHES:
        SIMS[(op_.oname(o), ln)] = op_.cache_sim(log, *op_.SIM_SHAPE, lines=ln)
STRM, TRAF, REUSE = {}, {}, {}
for nm, r in RUNS.items():
    STRM[nm], TRAF[nm], REUSE[nm] = op_.measured_streams(r, op_.M, op_.K, op_.N)


# ============================================================
# 图 1：全局定位
# ============================================================

def fig1():
    w, h = 1180, 700
    b = title_block(w, "第 92 天 · 循环顺序与局部性：换一个排列，换一种访存命运",
                    "输入是 Day 87~91 的四件工具，产出是 6 份 IR、一张对照表和一份缓存模拟明细")

    # —— 上排：第 14 周链路 ——
    b += text(30, 116, "① 第 14 周（D92~D98）：循环变换与 Tiling——一切循环变换的第一问：改了之后访存行为怎么变？",
              15.5, BLUE, bold=True)
    days = [("D92", "循环顺序\n与局部性", True), ("D93", "参数化\nLoopOptions", False),
            ("D94", "基础\nTiling", False), ("D95", "非整除\n尾部", False),
            ("D96", "展开与\n向量化", False), ("D97", "多配置\n实验", False),
            ("D98", "周复盘", False)]
    bw, bh, y0 = 146, 74, 128
    for i, (d, lab, hot) in enumerate(days):
        x = 30 + i * 162
        fill, st = (L_RED, RED) if hot else (L_BLUE if i < 6 else GREY, BLUE if i < 6 else SOFT)
        b += srect(x, y0, bw, bh, fill, st, 2.6 if hot else 2.0, rx=6)
        b += text(x + bw / 2, y0 + 24, d, 16, st, "middle", bold=True)
        b += mtext(x + bw / 2, y0 + 42, lab.split("\n"), 11.5, INK, "middle", 15)
        if hot:
            b += text(x + bw / 2, y0 - 8, "今天", 13, RED, "middle", bold=True)
        if i < 6:
            b += arrow(x + bw + 4, y0 + bh / 2, x + 158, y0 + bh / 2, SOFT, 2.0)

    # —— 中排：编译链路与本周变换空间 ——
    b += text(30, 248, "② 编译链路上：Lowering 之后，同一层 IR 内部还有一整面「循环变换」的墙",
              15.5, ORANGE, bold=True)
    y1, bh1 = 262, 96
    b += srect(30, y1, 250, bh1, L_BLUE, BLUE, 2.2, rx=6)
    b += mtext(155, y1 + 26, ["图算子层（Day 85 前）", "mini.matmul＋tensor 值语义",
                              "语义浓缩在 1 个 op 里"], 12.5, INK, "middle", 17)
    b += arrow(284, y1 + bh1 / 2, 356, y1 + bh1 / 2, INK, 2.4)
    b += text(320, y1 + bh1 / 2 - 26, "Lowering", 13, INK, "middle", bold=True)
    b += mtext(320, y1 + bh1 / 2 + 12, ["D85~91 已验证", "语义保持"], 10.5, SOFT, "middle", 13)
    b += srect(360, y1, 268, bh1, L_GREEN, GREEN, 2.2, rx=6)
    b += mtext(494, y1 + 26, ["循环 / 内存层（Day 87~89）", "scf.for 三重循环＋memref",
                              "18 op：alloc/zero/load/store"], 12.5, INK, "middle", 17)
    b += arrow(632, y1 + bh1 / 2, 704, y1 + bh1 / 2, INK, 2.4)
    b += text(668, y1 + bh1 / 2 - 26, "循环变换", 13, INK, "middle", bold=True)
    b += mtext(668, y1 + bh1 / 2 + 12, ["重排·分块·展开", "每步重验语义"], 10.5, SOFT, "middle", 13)
    b += srect(708, y1, 442, bh1, "none", ORANGE, 2.2, dash="8 6", rx=6)
    b += mtext(728, y1 + 24, ["本周打开的变换空间：", "重排（D92 今天）→ 分块（D94）→ 展开（D96）"],
               12.5, INK, "start", 17)
    b += srect(728, y1 + 62, 402, 24, L_RED, RED, 1.8, rx=4)
    b += text(930, y1 + 79, "不变式：语义不变（位等价）· 行为改变（访存）", 12.5, RED, "middle", bold=True)

    # —— 下排：输入 → 今天 → 产出 ——
    b += text(30, 402, "③ 今天的输入、加工与产出（全部真实可复跑）", 15.5, GREEN, bold=True)
    y2 = 416
    ins = [("%zero 归约单位元（D87）", "k 内层时是 iter_args 初值"),
           ("LoopSpec 出生证明（D88）", "上界来源 M / N / K"),
           ("访存日志探针（D89）", "(kind, mem, 下标, 地址, 值)"),
           ("位等价口径（D89~91）", "与同序参考逐位相同")]
    for i, (t1, t2) in enumerate(ins):
        y = y2 + i * 62
        b += srect(30, y, 320, 52, L_BLUE, BLUE, 1.9, rx=5)
        b += text(44, y + 22, t1, 12, INK, bold=True)
        b += text(44, y + 40, t2, 11, SOFT)
    for i in range(4):
        b += arrow(354, y2 + 26 + i * 62, 380, y2 + 130, BLUE, 1.6)

    b += srect(386, y2, 340, 262, L_GREEN, GREEN, 2.6, rx=7)
    b += text(556, y2 + 28, "今天 D92：order_pass.py", 15, GREEN, "middle", bold=True)
    b += mtext(402, y2 + 52, ["· LoopOrderPattern(order)：一个元组",
                              "   决定嵌套，6 种排列全部真实转换",
                              "   成 IR（18 / 21 op）",
                              "· 手工分析预测表：最内层 / 步长 /",
                              "   流量 / 复用，与真实日志对账（OT2）",
                              "· 直接映射缓存回放：16³ 真实轨迹",
                              "   × 4 种容量，数缺失（OT3）",
                              "· 语义先行：6/6 位等价（OT1）",
                              "   ＋ 忘清零回归（OT5）"],
               11.5, INK, "start", 24)

    outs = [("order-table.txt", "循环顺序 × 访存行为对照表（交付物）"),
            ("cache-sim.txt", "4 容量 × 6 顺序模拟明细"),
            ("ir-{i-j-k, i-k-j, k-i-j}.txt", "三种代表顺序的真实 IR"),
            ("no-init-check.txt", "忘清零回归（垃圾值进了累加链）")]
    for i, (t1, t2) in enumerate(outs):
        y = y2 + i * 62
        b += srect(744, y, 406, 52, L_ORANGE, ORANGE, 1.9, rx=5)
        b += text(758, y + 22, t1, 12, INK, bold=True)
        b += text(758, y + 40, t2, 11, SOFT)
    b += arrow(730, y2 + 130, 742, y2 + 130, GREEN, 2.0)
    save("01-overview.svg", w, h, b)


# ============================================================
# 图 2：核心机制——最内层下标决定步长；k 的位置决定累加器住哪
# ============================================================

def grid(x, y, rows, cols, cell, fill_map, stroke=INK, sw=1.8):
    """画一个 rows×cols 网格；fill_map: {(r,c): (fill, label)}"""
    parts = [srect(x, y, cols * cell, rows * cell, "white", stroke, sw, amp=0.9)]
    for r in range(1, rows):
        parts.append(sline(x, y + r * cell, x + cols * cell, y + r * cell, stroke, 1.2, amp=0.8))
    for c in range(1, cols):
        parts.append(sline(x + c * cell, y, x + c * cell, y + rows * cell, stroke, 1.2, amp=0.8))
    for (r, c), (fl, lab) in fill_map.items():
        cx, cy = x + c * cell + cell / 2, y + r * cell + cell / 2
        if fl:
            parts.append(srect(x + c * cell + 1.5, y + r * cell + 1.5, cell - 3, cell - 3,
                               fl, "none", 1.0, amp=0.6))
        if lab:
            parts.append(text(cx, cy + 4.5, lab, 11, INK, "middle"))
    return "".join(parts)


def fig2():
    w, h = 1180, 790
    b = title_block(w, "核心机制：最内层下标决定步长；k 的位置决定累加器住哪",
                    "贯穿例 A(2,3)@B(3,2)：同样 12 次 A-load、12 次 B-load，命运不同的只有「落在哪」与「何时再来」")
    cell = 30
    panels = [
        dict(name="i-j-k", nest="for i { for j { for k } }", inner="k",
             sub="k 最内层（Day 89/90 原顺序）",
             A_note="沿行连续 +1", B_note="跳 N=2（跨行）", C_note="不进循环体",
             acc="寄存器 iter_args %acc ← %zero（D87）",
             cflow="C 流量：0 读 ＋ 4 写（每格 1 次终值）", zero="清零：免（%zero 出门）"),
        dict(name="i-k-j", nest="for i { for k { for j } }", inner="j",
             sub="j 最内层（B、C 沿行；A 不动）",
             A_note="下标不含 j → 体不变", B_note="沿行连续 +1", C_note="逐趟读-改-写（连续 +1）",
             acc="内存：部分和住在 C[i,j] 里",
             cflow="C 流量：12 读 ＋ 12 写 ＋ 4 清零（7 倍）", zero="清零：要（init nest 3 op）"),
        dict(name="j-k-i", nest="for j { for k { for i } }", inner="i",
             sub="i 最内层（A、C 跨行；B 不动）",
             A_note="跳 K=3（跨行）", B_note="下标不含 i → 体不变", C_note="逐趟读-改-写（跳 N=2）",
             acc="内存：部分和住在 C[i,j] 里",
             cflow="C 流量：12 读 ＋ 12 写 ＋ 4 清零（7 倍）", zero="清零：要（init nest 3 op）"),
    ]
    for pi, p in enumerate(panels):
        px = 30 + pi * 385
        hot = p["name"] == "i-k-j"
        b += srect(px, 96, 355, 560, L_ORANGE if hot else "none", ORANGE if hot else INK,
                   2.4 if hot else 2.0, rx=7)
        b += text(px + 177, 122, p["name"] + "（" + p["inner"] + " 最内层）", 17,
                  RED if hot else INK, "middle", bold=True)
        b += text(px + 177, 144, p["nest"], 13, SOFT, "middle")
        b += text(px + 177, 162, p["sub"], 12, SOFT, "middle")
        gy = 186
        # A 网格 2×3
        b += grid(px + 22, gy, 2, 3, cell, {(0, 0): (L_BLUE, "0"), (0, 1): (L_BLUE, "1"),
                                            (0, 2): (L_BLUE, "2"), (1, 0): ("", "3"),
                                            (1, 1): ("", "4"), (1, 2): ("", "5")}, BLUE)
        b += text(px + 22 + 45, gy - 10, "A (2×3)", 13, BLUE, "middle", bold=True)
        # B 网格 3×2
        bx = px + 165
        b += grid(bx, gy, 3, 2, cell, {}, ORANGE)
        b += text(bx + 30, gy - 10, "B (3×2)", 13, ORANGE, "middle", bold=True)
        # C 网格 2×2
        cx0 = px + 258
        if p["inner"] == "k":
            b += grid(cx0, gy, 2, 2, cell, {}, GREEN)
        else:
            b += grid(cx0, gy, 2, 2, cell, {}, GREEN)
        b += text(cx0 + 30, gy - 10, "C (2×2)", 13, GREEN, "middle", bold=True)

        # —— 走法箭头 ——
        if p["name"] == "i-j-k":
            for c in range(2):
                x1, y1 = px + 22 + c * cell + cell, gy + cell / 2
                b += arrow(x1, y1, x1 + cell - 5, y1, BLUE, 2.4)
            b += text(px + 22, gy + 88, "A：0→1→2（+1 连续）", 12, BLUE, bold=True)
            for r in range(2):
                x1, y1 = bx + cell / 2, gy + r * cell + cell / 2
                x2, y2 = bx + cell / 2, gy + (r + 1) * cell + cell / 2
                b += carrow((x1 - 8, y1), (x1 - 26, (y1 + y2) / 2), (x2 - 8, y2), ORANGE, 2.4)
            b += text(bx - 14, gy + 88, "B：0→2→4（跳 N）", 12, ORANGE, bold=True)
            b += scirc(cx0 + 30, gy + 30, 24, L_GREEN, GREEN, 2.2)
            b += text(cx0 + 30, gy + 27, "%acc", 11.5, GREEN, "middle", bold=True)
            b += text(cx0 + 30, gy + 40, "寄存器", 10.5, GREEN, "middle")
            b += arrow(cx0 + 30, gy + 56, cx0 + 30, gy + 66, GREEN, 2.0)
            b += text(cx0 + 30, gy + 84, "store ×4", 11, INK, "middle")
            b += text(cx0 - 24, gy + 30, "k 扫完\n一趟", 10.5, SOFT, "middle")
        elif p["name"] == "i-k-j":
            b += scirc(px + 22 + cell / 2, gy + cell / 2, 15, L_BLUE, BLUE, 2.2)
            b += carrow((px + 22 + 4, gy + 8), (px + 22 - 12, gy + 15), (px + 22 + 6, gy + 24),
                        BLUE, 2.2)
            b += text(px + 22 - 2, gy + 88, "A[0,0] 不变：\n每体重读（距离 4）", 11.5, BLUE, bold=True)
            for r in range(3):
                b += scirc(bx + cell / 2, gy + r * cell + cell / 2, 15, L_ORANGE, ORANGE, 2.2)
            b += arrow(bx + cell - 2, gy + cell / 2, bx + 2 * cell - 5, gy + cell / 2, ORANGE, 2.4)
            b += text(bx - 14, gy + 118, "B[k,·]：0→1（+1 连续）", 11.5, ORANGE, bold=True)
            for cc in range(2):
                b += scirc(cx0 + cc * cell + cell / 2, gy + cell / 2, 15, L_GREEN, GREEN, 2.2)
                b += carrow((cx0 + cc * cell + 12, gy + 12), (cx0 + cc * cell + 30, gy + 15),
                            (cx0 + cc * cell + 12, gy + 22), GREEN, 2.0)
            b += text(cx0 - 24, gy + 118, "C[i,·]：读-改-写", 11.5, GREEN, bold=True)
            b += srect(px + 22, gy + 132, 311, 26, L_RED, RED, 1.8, rx=4)
            b += text(px + 177, gy + 150, "先清零：init nest 铺 4 次 store（＋3 op）", 11.5, RED,
                      "middle", bold=True)
        else:  # j-k-i
            b += carrow((px + 22 + cell / 2 - 8, gy + 6), (px + 22 - 20, gy + cell / 2),
                        (px + 22 + cell / 2 - 8, gy + cell + 4), BLUE, 2.4)
            b += text(px + 22 - 6, gy + 88, "A[·,0]：0→3（跳 K）", 11.5, BLUE, bold=True)
            b += scirc(bx + cell / 2, gy + cell / 2, 15, L_ORANGE, ORANGE, 2.2)
            b += carrow((bx + 6, gy + 8), (bx - 10, gy + 15), (bx + 8, gy + 24), ORANGE, 2.2)
            b += text(bx - 14, gy + 88, "B[0,0] 不变：\n每体重读（距离 4）", 11.5, ORANGE, bold=True)
            b += scirc(cx0 + cell / 2, gy + cell / 2, 15, L_GREEN, GREEN, 2.2)
            b += scirc(cx0 + cell / 2, gy + cell + cell / 2, 15, L_GREEN, GREEN, 2.2)
            b += carrow((cx0 + 12, gy + 8), (cx0 - 8, gy + cell / 2), (cx0 + 12, gy + cell + 4),
                        GREEN, 2.2)
            b += text(cx0 - 24, gy + 88, "C[·,0]：0→2（跳 N）\n读-改-写", 11.5, GREEN, bold=True)
            b += srect(px + 22, gy + 132, 311, 26, L_RED, RED, 1.8, rx=4)
            b += text(px + 177, gy + 150, "先清零：init nest 铺 4 次 store（＋3 op）", 11.5, RED,
                      "middle", bold=True)

        # —— 底部结论 ——
        by = 610
        b += srect(px + 22, by, 311, 34, L_GREEN if p["inner"] == "k" else L_RED,
                   GREEN if p["inner"] == "k" else RED, 2.0, rx=5)
        b += text(px + 177, by + 22, p["acc"], 12, INK, "middle", bold=True)
        b += text(px + 22, by + 56, p["cflow"], 12, INK, bold=True)
        b += text(px + 22, by + 76, p["zero"], 12, SOFT)
        b += text(px + 22, by + 100, "复用距离（实测）：A " + f"{REUSE[p['name']]['a']:.0f}"
                  + " / B " + f"{REUSE[p['name']]['b']:.0f}" + " 次访问", 12, SOFT)
    save("02-innermost-anatomy.svg", w, h, b)


# ============================================================
# 图 3：实例对照——真实访存脚印
# ============================================================

def tok(x, y, lab, color, fill, hot=False):
    return (srect(x, y, 62, 26, fill, color, 2.2 if hot else 1.7, rx=4)
            + text(x + 31, y + 18, lab, 12, INK, "middle", bold=hot))


def fig3():
    w, h = 1180, 880
    b = title_block(w, "同一份语义的脚印对照：i-j-k vs i-k-j vs j-k-i（真实访存日志，种子 92）",
                    "每个方块是一次访存（L=load，S=store，方括号内是线性地址）；两行 = 最内层扫描走两趟")

    def band(y0, name, note, toks, arcs, foot):
        b_ = srect(30, y0, 1120, 218, "none", INK, 1.8, rx=7)
        b_ += text(48, y0 + 30, name, 16, INK, bold=True)
        b_ += text(48 + 150, y0 + 30, note, 12.5, SOFT)
        tx0, ty0, dx, dy = 48, y0 + 48, 72, 40
        pos = {}
        for i, (lab, color, fill, hot) in enumerate(toks):
            r, c = divmod(i, 14)
            x, y = tx0 + c * dx, ty0 + r * dy
            b_ += tok(x, y, lab, color, fill, hot)
            pos[i] = (x + 31, y, x, y)   # 中心、左上
        for (i, j, lab, color) in arcs:
            x1, y1 = pos[i][0], pos[i][1] + 26
            x2, y2 = pos[j][0], pos[j][1]
            mid = (x1 + x2) / 2
            b_ += carrow((x1, y1 + 2), (mid, y1 + 30), (x2, y2 - 2), color, 2.0)
            b_ += text(mid, y1 + 44, lab, 11, color, "middle", bold=True)
        b_ += text(48, y0 + 196, foot, 12, SOFT)
        return b_

    # —— i-j-k：日志 t0..t13（两个 j 趟）——
    toks = [("La[0]", BLUE, L_BLUE, True), ("Lb[0]", ORANGE, L_ORANGE, False),
            ("La[1]", BLUE, L_BLUE, False), ("Lb[2]", ORANGE, L_ORANGE, False),
            ("La[2]", BLUE, L_BLUE, False), ("Lb[4]", ORANGE, L_ORANGE, False),
            ("Sc[0]", GREEN, L_GREEN, False),
            ("La[0]", BLUE, L_BLUE, True), ("Lb[1]", ORANGE, L_ORANGE, False),
            ("La[1]", BLUE, L_BLUE, False), ("Lb[3]", ORANGE, L_ORANGE, False),
            ("La[2]", BLUE, L_BLUE, False), ("Lb[5]", ORANGE, L_ORANGE, False),
            ("Sc[1]", GREEN, L_GREEN, False)]
    arcs = [(0, 7, "A[0,0] 重访：距离 7 = 2K+1（等 j 轮回）", BLUE),
            (1, 8, "B[0,0] 重访：距离 7（i=0 这轮里 B 列每格只用一次）", ORANGE)]
    b += band(96, "i-j-k", "k 最内层：A 沿行连续、B 跳 N、C 不进体（i=0 的一整段）",
              toks, arcs,
              "A 脚印 0→1→2（+1）；B 脚印 0→2→4（+2 = N，跨行）；C 只有 2 次 store（寄存器累加）——B[·,j] 要等 i 轮回才重访（距离 14 = N(2K+1)）")
    # —— i-k-j：清零 + 日志 t4..t15 ——
    toks2 = [("Sc[0]", GREEN, L_GREEN, False), ("Sc[1]", GREEN, L_GREEN, False),
             ("Sc[2]", GREEN, L_GREEN, False), ("Sc[3]", GREEN, L_GREEN, False),
             ("La[0]", BLUE, L_BLUE, True), ("Lb[0]", ORANGE, L_ORANGE, True),
             ("Lc[0]", GREEN, L_GREEN, False), ("Sc[0]", GREEN, L_GREEN, False),
             ("La[0]", BLUE, L_BLUE, True), ("Lb[1]", ORANGE, L_ORANGE, False),
             ("Lc[1]", GREEN, L_GREEN, False), ("Sc[1]", GREEN, L_GREEN, False),
             ("La[1]", BLUE, L_BLUE, False), ("Lb[2]", ORANGE, L_ORANGE, False)]
    arcs2 = [(4, 8, "A[0,0] 重访：距离 4（体不变——马上又读它）", BLUE),
             (6, 7, "RMW：读 C → 加 → 写回同一格", GREEN)]
    b += band(334, "i-k-j", "j 最内层：先清零 4 格，然后 A 不动、B/C 沿行连续（i=0, k=0..1 的开头）",
              toks2, arcs2,
              "A[0,0] 整个 j 扫描都在重读同一格（朴素 IR 不做 LICM，缓存/寄存器来兜底）；B 脚印 0→1→2→3…（+1）；C 每体一读一写——B[0,0] 要等 i 轮回（距离 24 = 4KN）")
    # —— j-k-i：日志 t4..t11 ——
    toks3 = [("Sc[0]", GREEN, L_GREEN, False), ("Sc[1]", GREEN, L_GREEN, False),
             ("Sc[2]", GREEN, L_GREEN, False), ("Sc[3]", GREEN, L_GREEN, False),
             ("La[0]", BLUE, L_BLUE, True), ("Lb[0]", ORANGE, L_ORANGE, True),
             ("Lc[0]", GREEN, L_GREEN, False), ("Sc[0]", GREEN, L_GREEN, False),
             ("La[3]", BLUE, L_BLUE, True), ("Lb[0]", ORANGE, L_ORANGE, True),
             ("Lc[2]", GREEN, L_GREEN, False), ("Sc[2]", GREEN, L_GREEN, False)]
    arcs3 = [(4, 8, "A 脚印 0→3（+K，跨行）", BLUE),
             (5, 9, "B[0,0] 体不变：距离 4", ORANGE),
             (6, 10, "C 脚印 0→2（+N，跨行 RMW）", GREEN)]
    b += band(572, "j-k-i", "i 最内层：A 跳 K、B 不动、C 跳 N 地读-改-写（j=0, k=0 的开头）",
              toks3, arcs3,
              "同一对 (A,B) 下标组合里，三个矩阵全在跨行跳——这就是 512B 缓存下 jki/kji 缺失最多（8636 / 8447）的脚印版解释")

    # —— 底部结论 ——
    b += srect(30, 800, 1120, 58, L_RED, RED, 2.2, rx=6)
    b += text(48, 824, "三段日志算出的 C 逐位相同（OT1：k 处处升序）；但 512B 缓存回放的缺失是 4764 / 2580 / 8636——", 13, INK, bold=True)
    b += text(48, 846, "「语义相同」与「访存命运相同」是两件事，循环顺序买卖的正是后者。", 13, RED, bold=True)
    save("03-trace-compare.svg", w, h, b)


# ============================================================
# 图 4：实测结果——对照表 + 缓存柱图
# ============================================================

def fig4():
    w, h = 1220, 830
    b = title_block(w, "实测结果：循环顺序 × 访存行为对照表（真实运行＋真实轨迹回放）",
                    "左表：小例 2×3@3×2（种子 92）的步长/流量/复用；右图：16×16×16 真实轨迹的直接映射缓存回放（行 16B）")

    # —— 左：对照表 ——
    x0, y0 = 30, 100
    cols = [("顺序", 78), ("最内", 40), ("A 步长", 78), ("B 步长", 78), ("C(体)", 84),
            ("累加", 46), ("清零", 40), ("C 流量", 92), ("复用 A/B", 74),
            ("miss\n@512B", 64), ("miss\n@1KB", 60)]
    hh = 46
    b += srect(x0, y0, sum(cw for _, cw in cols), hh + 6 * 40 + 8, "none", INK, 2.2, rx=6)
    cx = x0
    for name, cw in cols:
        b += srect(cx, y0, cw, hh, GREY, INK, 1.6, amp=0.8)
        lines = name.split("\n")
        b += mtext(cx + cw / 2, y0 + (20 if len(lines) == 1 else 15), lines, 12, INK, "middle", 16)
        cx += cw
    orders = ["i-j-k", "i-k-j", "j-i-k", "j-k-i", "k-i-j", "k-j-i"]
    for ri, nm in enumerate(orders):
        ry = y0 + hh + ri * 40
        pred = op_.PREDICT[nm]
        _, traf, reuse = op_.measured_streams(RUNS[nm], op_.M, op_.K, op_.N)
        cflow = f"{traf['c_loads']}L+{traf['c_stores']}S"
        if traf["init_stores"]:
            cflow += f"+{traf['init_stores']}清"
        vals = [nm, pred["inner"], pred["a"], pred["b"],
                ("—" if pred["c_body"] == "none" else pred["c_body"]),
                ("寄存" if pred["acc"] == "register" else "内存"),
                ("免" if not pred["init"] else "要"), cflow,
                f"{reuse['a']:.0f}/{reuse['b']:.0f}",
                str(SIMS[(nm, 32)]["misses"]), str(SIMS[(nm, 64)]["misses"])]
        cx = x0
        for (name, cw), v in zip(cols, vals):
            if name in ("A 步长", "B 步长", "C(体)"):
                col = GREEN if v == "seq" else (BLUE if v == "fixed" else RED)
                if v == "—":
                    col = GREEN
                b += srect(cx + 2, ry + 4, cw - 4, 32, L_GREEN if v == "seq" else
                           (L_BLUE if v == "fixed" else (L_RED if v != "—" else L_GREEN)),
                           col, 1.4, amp=0.6, rx=3)
            b += text(cx + cw / 2, ry + 25, v, 11.5, INK, "middle",
                      bold=(name == "顺序"))
            cx += cw
        b += sline(x0, ry, x0 + sum(cw for _, cw in cols), ry, GREY, 1.0, amp=0.6)
    b += mtext(x0, y0 + hh + 6 * 40 + 30,
               ["步长图例：绿 seq=连续+1｜蓝 fixed=体不变（最内层下标不含它）｜红 stride:S=每次跳 S 格",
                "C 流量（小例实测）：k 内层 0L+4S；k 外层 12L+12S＋4 清零——访问量 4 → 28（7 倍）",
                "复用 A/B：同一格最近重访的间隔（访问次数，逐地址实测均值）"],
               11.5, SOFT, "start", 17)

    # —— 右上：缓存柱图（横向条） ——
    bx0, by0, bw_ = 790, 108, 400
    b += text(bx0, by0 - 8, "缺失数（16³ 真实轨迹回放，直接映射 16B 行）", 13.5, INK, bold=True)
    for ci, (ln, note, notecol) in enumerate([
            (32, "512B：连续派（i-k-j / k-i-j）赢——缓存装不下跨行步进", RED),
            (64, "1KB：i-j-k 反超——工作集装得下，寄存器累加免掉 C 的 RMW", GREEN)]):
        cy = by0 + ci * 200
        b += text(bx0, cy, f"缓存 {ln * 16}B（{ln} 行）", 13, notecol, bold=True)
        maxv = max(SIMS[(nm, ln)]["misses"] for nm in orders)
        for ri, nm in enumerate(orders):
            v = SIMS[(nm, ln)]["misses"]
            barw = max(8, int(240 * v / maxv))
            yy = cy + 18 + ri * 22
            b += text(bx0, yy + 12, nm, 11.5, INK)
            hot = nm in ("i-k-j", "k-i-j") if ln == 32 else nm == "i-j-k"
            b += srect(bx0 + 56, yy, barw, 16, L_ORANGE if hot else GREY,
                       ORANGE if hot else SOFT, 1.5, amp=0.7, rx=3)
            b += text(bx0 + 62 + barw, yy + 12, str(v), 11.5, INK, bold=hot)
        b += text(bx0, cy + 18 + 6 * 22 + 6, note, 11.5, notecol)

    # —— 右下：数字卡片 ——
    cy = by0 + 2 * 200 + 14
    cards = [("位等价", "6/6", "小例＋16³，与同序参考逐位相同（OT1）", GREEN),
             ("强制缺失", "192", "4KB 全装下：192 = A64+B64+C64 行，顺序无关（OT3b）", BLUE),
             ("C 流量", "7×", "k 外层：4 → 28 次访问（2·MNK+MN vs MN）", RED)]
    for i, (t1, t2, t3, col) in enumerate(cards):
        yy = cy + i * 56
        b += srect(bx0, yy, 400, 48, "white", col, 2.0, rx=6)
        b += text(bx0 + 14, yy + 30, t1, 13, col, bold=True)
        b += text(bx0 + 86, yy + 31, t2, 17, col, "middle", bold=True)
        b += text(bx0 + 140, yy + 30, t3, 11.5, INK)

    # —— 底部口径 ——
    b += srect(30, 760, 1160, 52, GREY, SOFT, 1.6, rx=5)
    b += mtext(46, 780,
               ["口径：缺失数来自对解释执行器真实访存日志的直接映射缓存回放（write-allocate、无预取、无写缓冲），",
                "是模拟测量、不是任何真实硬件的实测；直接映射的冲突缺失会让特定步长模式额外吃亏——数字用于顺序之间的对比。"],
               11.5, SOFT, "start", 19)
    save("04-results-table.svg", w, h, b)


if __name__ == "__main__":
    fig1()
    fig2()
    fig3()
    fig4()
