#!/usr/bin/env python3
"""make_images.py —— 第 71 天（计算量与访存量）教程的四张手绘 sketch 风 SVG 信息图。

风格约定（与第 8/9/10 周各天一致，Excalidraw-like）：
  - 背景 #fdfaf2（米白），盒子白底 + 深灰 #6b6357 手绘描边
  - 强调色不超过 4 种柔和色：蓝 #4a7fa5 / 橙 #a8772e / 绿 #5a8a5a / 红 #b0605a
  - 线条带轻微抖动（L 段折线），圆头笔触，线宽 2 左右
  - 手写感字体栈：Comic Sans MS / Comic Neue / Kaiti SC / 楷体 / cursive
  - 只用矩形、格子、箭头、圆角框等简单几何形状

图中全部数字来自 2026-11-12 的真实运行（code/outputs/）：
  flops_bytes_lab 26/26；test_flops_bytes 23/23；
  贯穿示例 A(2,3)@B(3,2)：MatMul 24 FLOPs / 64 B / AI 0.375；
  Add 4 / 48 B / 1/12；Relu 4 / 32 B / 1/8；链 32 FLOPs / 144 B；
  拆账：io 80 B + 中间两遍税 64 B（44.4%）；
  方阵 AI = n/6：2.67 / 10.67 / 42.67 / 170.67 / 682.67（n=16…4096）；
  A100 SXM 40GB FP32 datasheet：19.5 TFLOPS ÷ 1555 GB/s = 12.54 FLOP/B；
  临界 n = 76；dtype：144 B → 72 B → 36 B（fp32/fp16/int8）。

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

rng = random.Random(71)


def esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;")
             .replace(">", "&gt;"))


def tw(s: str, size: float) -> float:
    """粗略的字宽估算：CJK 约 1×size，ASCII 约 0.55×size。"""
    return sum(size if ord(c) > 0x2E80 else size * 0.55 for c in s)


def txt(x, y, s, size=12, fill=INK, anchor="start", bold=False,
        opacity=1.0):
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


def dot(x, y, r=5, fill=INK, stroke=STROKE):
    return (f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="1.8"/>')


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


def badge(x, y, s, color, size=11.5, h=22, fill=None):
    w = tw(s, size) + 16
    return (sketch_rect(x, y, w, h, fill=fill or TINT["white"], stroke=color,
                        sw=1.8, nseg=4)
            + txt(x + w / 2, y + h - 7, s, size, color, anchor="middle",
                  bold=True))


# ============================================================
# 图 1：全貌
# ============================================================

def fig1() -> None:
    w, h = 1180, 840
    b = [header(w, h, "第 71 天全貌：计算量与访存量",
                "第 11 周「融合收益与代价模型」第一天 —— 融合之前，先学会给算子算账"
                " ｜ 图中数字均为 2026-11-12 本机实测")]

    # ---- 顶部：阶段进度条 ----
    b.append(txt(40, 92, "学习计划位置（24 周 / 168 天）", 13, MUTED, bold=True))
    stages = [
        ("W1–4", "C++/IR/基础 Pass", False),
        ("W5–8", "MLIR/融合", False),
        ("W9–10", "Shape/Layout/图优化", False),
        ("W11", "融合收益与代价 ← 今天", True),
        ("W12", "数值精度与量化", False),
        ("W13–16", "Lowering/Tiling/调优", False),
        ("W17–24", "端到端与收口", False),
    ]
    bx, by, bw, bh, gap = 40, 100, 152, 50, 8
    for i, (rng_, theme, cur) in enumerate(stages):
        x = bx + i * (bw + gap)
        fill = TINT["orange"] if cur else TINT["gray"]
        b.append(sketch_rect(x, by, bw, bh, fill=fill,
                             stroke=ORANGE if cur else STROKE,
                             sw=2.6 if cur else 2.0))
        b.append(txt(x + bw / 2, by + 20, rng_, 12,
                     ORANGE if cur else MUTED, anchor="middle", bold=True))
        b.append(txt(x + bw / 2, by + 38, theme, 10.5,
                     INK if cur else MUTED, anchor="middle",
                     bold=cur))

    # ---- 中排：本周七天 ----
    b.append(txt(40, 178, "本周链路（第 11 周：融合收益与代价模型）", 13, MUTED,
                 bold=True))
    days = [("D71", "计算量与访存量"), ("D72", "融合减少的流量"),
             ("D73", "融合的资源代价"), ("D74", "合法/收益分离"),
             ("D75", "构造不融合案例"), ("D76", "简单 Cost Model"),
             ("D77", "复盘")]
    dx, dy, dw, dh = 40, 186, 152, 46
    for i, (d, t) in enumerate(days):
        x = dx + i * (dw + 8)
        cur = i == 0
        b.append(sketch_rect(x, dy, dw, dh,
                             fill=TINT["orange"] if cur else TINT["white"],
                             stroke=ORANGE if cur else STROKE,
                             sw=2.6 if cur else 1.8))
        b.append(txt(x + dw / 2, dy + 19, d, 12,
                     ORANGE if cur else INK, anchor="middle", bold=True))
        b.append(txt(x + dw / 2, dy + 36, t, 10.5, INK, anchor="middle"))
    b.append(sketch_line(40 + 7 * (dw + 8) - 4, dy + dh / 2, 1140,
                         dy + dh / 2, stroke=MUTED, sw=1.6, dashed=True))

    # ---- 下排：四个内容盒（2×2） ----
    boxes = [
        (40, 258, 552, 252, "① 贯穿示例的账单（A(2,3)@B(3,2)，fp32）", BLUE,
         [("算子", "FLOPs", "字节", "AI (FLOP/B)"),
          ("MatMul", "24", "64 B", "0.375"),
          ("Add", "4", "48 B", "1/12 ≈ 0.083"),
          ("Relu", "4", "32 B", "1/8 = 0.125"),
          ("链合计", "32", "144 B", "0.222")]),
        (612, 258, 528, 252, "② Shape 扫描（方阵 AI = n/6）", GREEN,
         [("n", "AI (FLOP/B)", "一阶判断（阈值 12.54）", ""),
          ("16", "2.67", "访存受限", ""),
          ("64", "10.67", "访存受限（临界 n=76）", ""),
          ("256", "42.67", "算力受限", ""),
          ("1024+", "170.67+", "算力受限", "")]),
    ]
    for x, y, bw2, bh2, title, color, rows in boxes:
        b.append(sketch_rect(x, y, bw2, bh2, fill=TINT["white"],
                             stroke=color, sw=2.4))
        b.append(txt(x + 14, y + 24, title, 13, color, bold=True))
        colx = [x + 14, x + 130, x + 220, x + 360]
        ty = y + 52
        b.append(txt(colx[0], ty, rows[0][0], 11, MUTED, bold=True))
        b.append(txt(colx[1], ty, rows[0][1], 11, MUTED, bold=True))
        b.append(txt(colx[2], ty, rows[0][2], 11, MUTED, bold=True))
        b.append(txt(colx[3], ty, rows[0][3], 11, MUTED, bold=True))
        b.append(sketch_line(x + 12, ty + 8, x + bw2 - 12, ty + 8,
                             stroke=MUTED, sw=1.2))
        ry = ty + 24
        for r in rows[1:]:
            emph = r[0] == "链合计" or r[0] == "64"
            b.append(txt(colx[0], ry, r[0], 11.5,
                         ORANGE if emph else INK, bold=emph))
            b.append(txt(colx[1], ry, r[1], 11.5,
                         ORANGE if emph else INK, bold=emph))
            b.append(txt(colx[2], ry, r[2], 11.5,
                         ORANGE if emph else INK, bold=emph))
            b.append(txt(colx[3], ry, r[3], 11.5, INK))
            ry += 22
    b.append(txt(40, 530, "逐元素算子 AI 与 shape 无关：Add 恒 1/12、Relu 恒 1/8"
                " —— 永远访存受限（融合动机的定量来源）", 11, MUTED))
    b.append(txt(612, 530, "阈值 = A100 SXM 40GB FP32 datasheet：19.5 TFLOPS"
                " ÷ 1555 GB/s = 12.54 FLOP/B（峰值口径，非实测）", 11, MUTED))

    # 盒 3：dtype 对照；盒 4：与昨天的衔接
    x, y, bw2, bh2 = 40, 556, 552, 150
    b.append(sketch_rect(x, y, bw2, bh2, fill=TINT["white"], stroke=GREEN,
                         sw=2.4))
    b.append(txt(x + 14, y + 24, "③ dtype 缩放（改一个参数再观察）", 13, GREEN,
                 bold=True))
    for i, (dt, bs, aimm) in enumerate([("fp32", "144 B", "0.375"),
                                        ("fp16", "72 B", "0.75"),
                                        ("int8", "36 B", "1.5")]):
        bx2 = x + 14 + i * 178
        b.append(sketch_rect(bx2, y + 38, 46, 26, fill=TINT["green"],
                             stroke=GREEN, sw=1.6, nseg=3))
        b.append(txt(bx2 + 23, y + 56, dt, 11, INK, anchor="middle"))
        b.append(txt(bx2 + 56, y + 56, f"链 {bs}", 11, INK))
        b.append(txt(bx2 + 118, y + 56, f"AI {aimm}", 11, INK))
    b.append(txt(x + 14, y + 96, "FLOPs 不变（32）；字节 ∝ itemsize；AI 反比；"
                "两遍税占比不变（44.4%）", 11, MUTED))
    b.append(txt(x + 14, y + 118, "→ 低精度让「每字节承载的运算」翻倍"
                "（第 78 天起管数值语义）", 11, MUTED))

    x, y = 612, 556
    b.append(sketch_rect(x, y, 528, 150, fill=TINT["blue"], stroke=BLUE,
                         sw=2.4))
    b.append(txt(x + 14, y + 24, "④ 与昨天/明天的衔接", 13, BLUE, bold=True))
    b.append(txt(x + 14, y + 48, "D70 内存账本：事后日志（4-op 链物理世界 144 B）",
                 11, INK))
    b.append(txt(x + 14, y + 70, "D71 今天：同样口径的事前公式（读一遍+写一遍）",
                 11, INK))
    b.append(txt(x + 14, y + 92, "链拆账：任务流量 80 B ＋ 中间两遍税 64 B"
                "（44.4%）", 11, ORANGE, bold=True))
    b.append(txt(x + 14, y + 116, "D72 明天：融合收益公式 = 消掉那 64 B 的"
                "一部分，减去融合代价", 11, MUTED))

    # ---- 底部徽标 ----
    badges = [("主实验 26/26", GREEN), ("验收测试 23/23", GREEN),
              ("产出：公式＋代入示例＋数据表", ORANGE),
              ("4 张图全部真实数字", BLUE)]
    bx3 = 40
    for s, c in badges:
        b.append(badge(bx3, 748, s, c))
        bx3 += tw(s, 11.5) + 34

    b.append(txt(40, 806, "运行入口：code/run_all.sh（主实验 → 独立测试 →"
                " 重新生成本组图片）", 11, MUTED))
    save("01-overview.svg", "".join(b))


# ============================================================
# 图 2：核心机制
# ============================================================

def fig2() -> None:
    w, h = 1180, 780
    b = [header(w, h, "核心机制：一个算子，两笔账；一条链，一笔两遍税",
                "上：贯穿示例的读写箭头（数字真实）｜ 下左：公式卡片 ｜"
                " 下右：算术强度坐标与平衡点")]

    # ---- 上半：链 + DRAM ----
    # 输入盒子（上方）
    for (x, label, sub) in [(238, "B (3,2)", "读 24 B"),
                            (598, "D (2,2)", "读 16 B")]:
        b.append(sketch_rect(x, 82, 86, 40, fill=TINT["white"], sw=1.8))
        b.append(txt(x + 43, 100, label, 11.5, INK, anchor="middle"))
        b.append(txt(x + 43, 115, sub, 10, MUTED, anchor="middle"))

    # 流程行
    ops = [(200, "MatMul", "24 FLOPs", BLUE),
           (470, "Add", "4 FLOPs", BLUE),
           (740, "Relu", "4 FLOPs", BLUE)]
    for x, name, fl, c in ops:
        b.append(sketch_rect(x, 150, 120, 54, fill=TINT["blue"], stroke=c,
                             sw=2.2))
        b.append(txt(x + 60, 172, name, 13, INK, anchor="middle", bold=True))
        b.append(txt(x + 60, 191, fl, 10.5, MUTED, anchor="middle"))

    tensors = [(60, "A (2,3)", "", STROKE),
               (348, "C (2,2)", "中间", ORANGE),
               (618, "E (2,2)", "中间", ORANGE),
               (888, "F (2,2)", "输出", GREEN)]
    for x, label, role, st in tensors:
        fill = (TINT["orange"] if role == "中间"
                else TINT["green"] if role == "输出" else TINT["white"])
        b.append(sketch_rect(x, 155, 88, 44, fill=fill, stroke=st, sw=2.0))
        b.append(txt(x + 44, 173, label, 11.5, INK, anchor="middle",
                     bold=True))
        if role:
            b.append(txt(x + 44, 191, role, 10, st, anchor="middle"))

    # 流程箭头
    b.append(sketch_line(148, 177, 198, 177, arrow=True))
    b.append(sketch_line(320, 177, 348, 177, arrow=True))
    b.append(sketch_line(436, 177, 470, 177, arrow=True))
    b.append(sketch_line(590, 177, 618, 177, arrow=True))
    b.append(sketch_line(706, 177, 740, 177, arrow=True))
    b.append(sketch_line(860, 177, 888, 177, arrow=True))
    # 输入箭头（B、D 从上方进入算子）
    b.append(sketch_line(281, 122, 281, 148, arrow=True))
    b.append(sketch_line(641, 122, 641, 148, arrow=True))

    # 每个算子下方：DRAM 的上行读箭头 / 下行写箭头
    dram_y = 316
    read_specs = [(260, "读 A 24 B + B 24 B"),
                  (530, "读 C 16 B + D 16 B"),
                  (800, "读 E 16 B")]
    for cx, label in read_specs:
        b.append(sketch_line(cx - 8, dram_y, cx - 8, 206, stroke=GREEN,
                             sw=2.0, arrow=True))
        b.append(txt(cx - 16, 240, label, 10.5, GREEN, anchor="end"))
    write_specs = [(300, "写 C 16 B"), (570, "写 E 16 B"), (840, "写 F 16 B")]
    for cx, label in write_specs:
        b.append(sketch_line(cx, 206, cx, dram_y, stroke=RED, sw=2.0,
                             arrow=True))
        b.append(txt(cx + 8, 300, label, 10.5, RED))
    b.append(txt(60, 264, "↗ 读（上行，绿）", 11, GREEN, bold=True))
    b.append(txt(60, 286, "↘ 写（下行，红）", 11, RED, bold=True))
    # 合计徽标（右侧竖排，避开箭头与标签）
    for s, yy in [("MatMul 64 B", 220), ("Add 48 B", 248), ("Relu 32 B", 276)]:
        b.append(badge(980, yy, s, BLUE, 11))

    # DRAM 带
    b.append(sketch_rect(40, dram_y, 1100, 48, fill=TINT["gray"],
                         stroke=STROKE, sw=2.2))
    b.append(txt(590, 346, "内存 DRAM（口径：缓存完美复用 → compulsory 理想"
                "下界；真实流量只会 ≥ 它）", 12, INK, anchor="middle",
                bold=True))

    # 两遍税注解（DRAM 带下方）
    b.append(txt(40, 390, "中间 Tensor 两遍税：C 写一遍 + 读一遍 = 32 B；"
                "E 同样 32 B；合计 64 B（占总流量 44.4%）", 12, ORANGE,
                bold=True))

    # ---- 下半左：公式卡片 ----
    cards = [
        ("MatMul", ["FLOPs = 2·M·N·K = 24（MAC = 2 FLOPs）",
                    "字节 = 4(MK+KN+MN) = 64 B（读 48 + 写 16）",
                    "AI = 24 / 64 = 0.375 FLOP/B"], BLUE),
        ("Add", ["FLOPs = M·N = 4",
                 "字节 = 12·M·N = 48 B（读 32 + 写 16）",
                 "AI = 1/12 ≈ 0.083 FLOP/B"], GREEN),
        ("Relu", ["FLOPs = M·N = 4（口径：1 比较/元素）",
                  "字节 = 8·M·N = 32 B（读 16 + 写 16）",
                  "AI = 1/8 = 0.125 FLOP/B"], ORANGE),
    ]
    for i, (name, lines, c) in enumerate(cards):
        y = 410 + i * 112
        b.append(sketch_rect(40, y, 350, 100, fill=TINT["white"], stroke=c,
                             sw=2.2))
        b.append(txt(54, y + 22, name, 13, c, bold=True))
        ly = y + 46
        for ln in lines:
            b.append(txt(54, ly, ln, 11, INK))
            ly += 22
    b.append(txt(40, 764, "仪器化对拍：朴素三重循环数出 12 乘 + 12 加 = 24"
                "（= 公式）", 11, MUTED))

    # ---- 下半右：AI 坐标 ----
    ax0, ax1, ay = 460, 1100, 640
    b.append(panel_title(460, 428, "算术强度坐标（FLOP/Byte，线性轴 0–16）"))
    b.append(sketch_line(ax0, ay, ax1, ay, sw=2.2))
    for v in (0, 4, 8, 12, 16):
        x = ax0 + v / 16 * (ax1 - ax0)
        b.append(sketch_line(x, ay, x, ay + 6, sw=1.6))
        b.append(txt(x, ay + 22, str(v), 10.5, MUTED, anchor="middle"))
    # 平衡线
    bx = ax0 + 12.54 / 16 * (ax1 - ax0)
    b.append(sketch_line(bx, 448, bx, ay, stroke=RED, sw=2.0, dashed=True))
    b.append(txt(bx - 8, 466, "A100 FP32 平衡点 12.54", 11, RED,
                 anchor="end", bold=True))
    b.append(txt(bx - 8, 482, "（datasheet 峰值口径）", 10, MUTED,
                 anchor="end"))
    # 数据点（挂在轴上，竖直短线 + 圆点 + 错层标签）
    pts = [("Add 1/12", 1 / 12, GREEN, "start"),
           ("Relu 1/8", 0.125, ORANGE, "start"),
           ("链 0.222", 0.222, MUTED, "start"),
           ("MatMul(本例) 0.375", 0.375, BLUE, "start"),
           ("n=16 → 2.67", 2.67, BLUE, "start"),
           ("n=64 → 10.67", 10.67, BLUE, "end")]
    for i, (label, v, c, anch) in enumerate(pts):
        x_d = ax0 + v / 16 * (ax1 - ax0)
        ylab = 466 + i * 24
        b.append(sketch_line(x_d, ay, x_d, ay - 10, stroke=c, sw=1.8))
        b.append(dot(x_d, ay - 16, 4.5, fill=c, stroke=c))
        if anch == "start":
            b.append(sketch_line(x_d, ay - 22, x_d + 12, ylab, stroke=c,
                                 sw=1.0, opacity=0.7))
            b.append(txt(x_d + 16, ylab + 4, label, 10.5, c, bold=True))
        else:
            b.append(sketch_line(x_d, ay - 22, x_d - 12, ylab, stroke=c,
                                 sw=1.0, opacity=0.7))
            b.append(txt(x_d - 16, ylab + 4, label, 10.5, c, anchor="end",
                         bold=True))
    b.append(txt(620, 700, "方阵 MatMul：AI = n/6 随规模线性增长；"
                "n = 76 处越过平衡线", 11, INK))
    b.append(txt(620, 720, "（n = 256 → 42.67，超出本图 → 算力受限；"
                "见图 3 的完整扫描）", 10.5, MUTED))
    save("02-mechanism.svg", "".join(b))


# ============================================================
# 图 3：Shape 扫描数据图（对数-对数坐标，真实输出）
# ============================================================

def fig3() -> None:
    w, h = 1180, 780
    b = [header(w, h, "Shape 扫描：MatMul 的 AI 随 n 线性爬升，逐元素算子贴地",
                "数据来自 code/outputs/flops_bytes_lab.txt 第 5 节真实运行"
                "（方阵 n×n×n，fp32，理想下界口径）｜ 双对数坐标")]

    # 坐标区
    x0, x1, y0, y1 = 130, 1030, 560, 120   # y0 底，y1 顶
    lo, hi = -2.0, 3.0                     # log10(AI) 范围：0.01 ~ 1000

    def px(n):
        return x0 + (math.log10(n) - math.log10(16)) / (
            math.log10(4096) - math.log10(16)) * (x1 - x0)

    def py(a):
        return y0 - (math.log10(a) - lo) / (hi - lo) * (y0 - y1)

    # 轴
    b.append(sketch_line(x0 - 30, y0, x1 + 20, y0, sw=2.2))
    b.append(sketch_line(x0 - 30, y0, x0 - 30, y1 - 10, sw=2.2))
    for d in range(-2, 4):
        yv = py(10 ** d)
        b.append(sketch_line(x0 - 36, yv, x0 - 24, yv, sw=1.6))
        lab = f"{10 ** d:g}"
        b.append(txt(x0 - 42, yv + 4, lab, 10.5, MUTED, anchor="end"))
    for n in (16, 64, 256, 1024, 4096):
        xv = px(n)
        b.append(sketch_line(xv, y0, xv, y0 + 6, sw=1.6))
        b.append(txt(xv, y0 + 24, str(n), 11, MUTED, anchor="middle"))
    b.append(txt((x0 + x1) / 2, y0 + 48, "方阵规模 n（对数刻度）", 12, MUTED,
                 anchor="middle"))
    # 纵轴标签（旋转 90°，只画一次）
    b.append(f'<text x="{x0 - 100}" y="{(y0 + y1) / 2}" '
             f'font-family="{FONT}" font-size="12" fill="{MUTED}" '
             f'text-anchor="middle" transform="rotate(-90 '
             f'{x0 - 100} {(y0 + y1) / 2})">{esc("算术强度 AI（FLOP/Byte，对数刻度）")}'
             f'</text>')

    # MatMul 折线（真实点）
    sweep = [(16, 2.67, "访存受限"), (64, 10.67, "访存受限"),
             (256, 42.67, "算力受限"), (1024, 170.67, "算力受限"),
             (4096, 682.67, "算力受限")]
    pts_xy = [(px(n), py(a)) for n, a, _ in sweep]
    for (xa, ya), (xb, yb) in zip(pts_xy, pts_xy[1:]):
        b.append(sketch_line(xa, ya, xb, yb, stroke=BLUE, sw=2.6))
    for (n, a, verdict), (xv, yv) in zip(sweep, pts_xy):
        b.append(dot(xv, yv, 5.5, fill=BLUE, stroke=BLUE))
        b.append(txt(xv + 2, yv - 14 if n != 4096 else yv + 24,
                      f"n={n}", 10.5, BLUE, bold=True))
        b.append(txt(xv + 2, yv - 30 if n != 4096 else yv + 40,
                      f"AI={a:g}", 10.5, BLUE))
    b.append(txt(560, 108, "MatMul：AI = 2n³ / 12n² = n/6（对数-对数坐标上"
                "是斜率 1 的直线）", 11, BLUE, bold=True))
    # 图内左上角注解（避开 x 轴标题）
    b.append(txt(150, 152, "逐元素算子永远在访存区：", 11, MUTED, bold=True))
    b.append(txt(150, 170, "不管外层 MatMul 多大，它们按带宽结算", 11,
                 MUTED))

    # 平衡线（A100）
    by = py(12.54)
    b.append(sketch_line(x0 - 24, by, x1 + 20, by, stroke=RED, sw=2.2,
                        dashed=True))
    b.append(txt(x1 - 6, by - 10, "A100 FP32 平衡点 12.54 FLOP/B"
                "（datasheet 峰值，非实测）", 11, RED, anchor="end",
                bold=True))
    # 临界点 n=76
    cx = px(76)
    b.append(dot(cx, by, 6, fill=RED, stroke=RED))
    b.append(txt(cx, by + 45, "临界 n = 76（AI = 12.67 刚过 12.54）", 11,
                 RED, anchor="middle", bold=True))

    # Add / Relu 水平线（标签错层，避免互相覆盖）
    ay_l = py(1 / 12)
    ry_l = py(0.125)
    b.append(sketch_line(x0 - 24, ay_l, x1 + 20, ay_l, stroke=GREEN, sw=2.0,
                         dashed=True))
    b.append(txt(x1 - 6, ay_l + 20, "Add：AI = 1/12 ≈ 0.083（与 n 无关）",
                 11, GREEN, anchor="end", bold=True))
    b.append(sketch_line(x0 - 24, ry_l, x1 + 20, ry_l, stroke=ORANGE, sw=2.0,
                         dashed=True))
    b.append(txt(x1 - 6, ry_l - 10, "Relu：AI = 1/8 = 0.125（与 n 无关）",
                 11, ORANGE, anchor="end", bold=True))

    # 底部：真实输出数据表
    b.append(panel_title(40, 640, "真实运行输出（方阵 n×n×n，fp32，理想下界）",
                         GREEN))
    ty = 662
    cols = [("n", 40), ("FLOPs", 90), ("字节(B)", 250), ("AI(FLOP/B)", 400),
            ("一阶判断（阈值 12.54）", 540)]
    for name, cxx in cols:
        b.append(txt(cxx, ty, name, 10.5, MUTED, bold=True))
    b.append(sketch_line(40, ty + 8, 640, ty + 8, stroke=MUTED, sw=1.2))
    rows = [("16", "8,192", "3,072", "2.67", "访存受限"),
            ("64", "524,288", "49,152", "10.67", "访存受限 ← 临界 76"),
            ("256", "33,554,432", "786,432", "42.67", "算力受限")]
    ry2 = ty + 26
    for r in rows:
        for (val, (name, cxx)) in zip(r, cols):
            emph = r[0] == "64"
            b.append(txt(cxx, ry2, val, 11, ORANGE if emph else INK,
                        bold=emph or name == "n"))
        ry2 += 20
    b.append(txt(40, 748, "n = 1024 → AI 170.67；n = 4096 → AI 682.67"
                "（都在算力受限区，图上五个点全部真实）", 10.5, MUTED))
    save("03-shape-sweep.svg", "".join(b))


# ============================================================
# 图 4：中间 Tensor 流量（两遍税）
# ============================================================

def fig4() -> None:
    w, h = 1180, 760
    b = [header(w, h, "中间 Tensor 流量：独立执行时每个中间结果交两遍税",
                "上：读写箭头 ｜ 下：拆账与缩放")]

    # ---- 上：链 + 每个 Tensor 的趟数 ----
    # 张量行
    tens = [(60, "A (2,3)", "", STROKE),
            (348, "C (2,2)", "中间", ORANGE),
            (618, "E (2,2)", "中间", ORANGE),
            (888, "F (2,2)", "输出", GREEN)]
    for x, label, role, st in tens:
        fill = (TINT["orange"] if role == "中间"
                else TINT["green"] if role == "输出" else TINT["white"])
        b.append(sketch_rect(x, 88, 88, 46, fill=fill, stroke=st, sw=2.2))
        b.append(txt(x + 44, 108, label, 11.5, INK, anchor="middle",
                     bold=True))
        if role:
            b.append(txt(x + 44, 126, role, 10, st, anchor="middle"))
    ops = [(200, "MatMul"), (470, "Add"), (740, "Relu")]
    for x, name in ops:
        b.append(sketch_rect(x, 82, 120, 58, fill=TINT["blue"],
                             stroke=BLUE, sw=2.2))
        b.append(txt(x + 60, 106, name, 13, INK, anchor="middle", bold=True))
        b.append(txt(x + 60, 125, "独立执行", 10, MUTED, anchor="middle"))
    b.append(sketch_line(148, 111, 198, 111, arrow=True))
    b.append(sketch_line(320, 111, 348, 111, arrow=True))
    b.append(sketch_line(436, 111, 470, 111, arrow=True))
    b.append(sketch_line(590, 111, 618, 111, arrow=True))
    b.append(sketch_line(706, 111, 740, 111, arrow=True))
    b.append(sketch_line(860, 111, 888, 111, arrow=True))
    for x, lab in [(238, "B (3,2) 读 24 B"), (598, "D (2,2) 读 16 B")]:
        b.append(sketch_rect(x, 30, 96, 36, fill=TINT["white"], sw=1.8))
        b.append(txt(x + 48, 53, lab, 10.5, INK, anchor="middle"))
        b.append(sketch_line(x + 48, 66, x + 48, 80, arrow=True))

    # DRAM 带与箭头（写 = 张量 → DRAM 向下；读 = DRAM → 张量 向上）
    dy = 210
    b.append(sketch_rect(40, dy, 1100, 46, fill=TINT["gray"], stroke=STROKE,
                         sw=2.2))
    b.append(txt(590, 238, "内存 DRAM（kernel 之间交接必须经过这里）", 12,
                 INK, anchor="middle", bold=True))
    # A：1 趟读（上行）
    b.append(sketch_line(104, dy, 104, 134, stroke=GREEN, sw=2.2, arrow=True))
    b.append(txt(110, 158, "读 24 B", 10.5, GREEN))
    # C：两趟（写下行 + 读上行）
    b.append(sketch_line(382, 134, 382, dy, stroke=RED, sw=2.2, arrow=True))
    b.append(sketch_line(402, dy, 402, 134, stroke=GREEN, sw=2.2, arrow=True))
    b.append(txt(372, 158, "写 16 B ＋ 读 16 B", 10.5, ORANGE,
                 anchor="end", bold=True))
    # E：两趟
    b.append(sketch_line(652, 134, 652, dy, stroke=RED, sw=2.2, arrow=True))
    b.append(sketch_line(672, dy, 672, 134, stroke=GREEN, sw=2.2, arrow=True))
    b.append(txt(642, 158, "写 16 B ＋ 读 16 B", 10.5, ORANGE,
                 anchor="end", bold=True))
    # F：1 趟写（下行）
    b.append(sketch_line(932, 134, 932, dy, stroke=RED, sw=2.2, arrow=True))
    b.append(txt(938, 158, "写 16 B", 10.5, RED))

    b.append(txt(40, 286, "两遍税（C、E）：16+16 + 16+16 = 64 B，占总流量"
                " 144 B 的 44.4% —— 只要三个算子独立执行（各自 kernel），"
                "这笔税就是结构性的", 12, ORANGE, bold=True))

    # ---- 下左：拆账条 ----
    b.append(panel_title(40, 330, "链总流量的拆账（144 B，fp32）", GREEN))
    bar_x, bar_y, bar_w = 60, 352, 600
    io_w = bar_w * 80 / 144
    b.append(sketch_rect(bar_x, bar_y, io_w, 40, fill=TINT["green"],
                         stroke=GREEN, sw=2.2))
    b.append(txt(bar_x + io_w / 2, bar_y + 18, "外部输入 + 最终输出", 11, INK,
                 anchor="middle"))
    b.append(txt(bar_x + io_w / 2, bar_y + 34, "80 B（55.6%）", 11, GREEN,
                 anchor="middle", bold=True))
    b.append(sketch_rect(bar_x + io_w, bar_y, bar_w - io_w, 40,
                         fill=TINT["orange"], stroke=ORANGE, sw=2.2))
    b.append(txt(bar_x + io_w + (bar_w - io_w) / 2, bar_y + 18,
                 "中间两遍税", 11, INK, anchor="middle"))
    b.append(txt(bar_x + io_w + (bar_w - io_w) / 2, bar_y + 34,
                 "64 B（44.4%）", 11, ORANGE, anchor="middle", bold=True))
    b.append(txt(60, 424, "任务流量：A 24 + B 24 + D 16 + F 16 = 80 B"
                "（这个任务理论上不可省的搬运）", 10.5, MUTED))
    b.append(txt(60, 444, "两遍税：C、E 各写一遍 + 读一遍 = 64 B"
                "（当前执行方式额外付出的）", 10.5, ORANGE))
    b.append(txt(60, 470, "拆账闭合检查：80 + 64 == 144（主实验 4f）", 11,
                 GREEN, bold=True))
    b.append(badge(60, 490, "144 B = 各算子 read+write 之和", BLUE, 11))

    # ---- 下右：dtype 缩放条 ----
    b.append(panel_title(660, 330, "dtype 缩放（FLOPs 不变，字节 ∝ itemsize）",
                         GREEN))
    dts = [("fp32  4 B/元素", 144, "链 144 B｜MatMul AI 0.375"),
           ("fp16  2 B/元素", 72, "链 72 B｜MatMul AI 0.75"),
           ("int8  1 B/元素", 36, "链 36 B｜MatMul AI 1.5")]
    for i, (lab, val, note) in enumerate(dts):
        y = 356 + i * 62
        b.append(txt(660, y + 8, lab, 11, INK, bold=True))
        bw2 = 300 * val / 144
        b.append(sketch_rect(660, y + 16, bw2, 22, fill=TINT["blue"],
                             stroke=BLUE, sw=2.0))
        b.append(txt(660 + bw2 + 10, y + 32, note, 10.5, BLUE))
    b.append(txt(660, 552, "两遍税占比不变（64/144 = 32/72 = 8/36"
                " = 44.4%）：所有项同比缩放", 10.5, MUTED))
    b.append(txt(660, 574, "低精度让每字节承载的运算翻倍 → 量化收益的账面"
                "来源（数值语义第 78 天起管）", 10.5, MUTED))

    # ---- 右下：明天入口 ----
    b.append(sketch_rect(660, 596, 480, 96, fill=TINT["blue"], stroke=BLUE,
                         sw=2.2))
    b.append(txt(676, 620, "Day 72 预告：融合减少的流量", 13, BLUE, bold=True))
    b.append(txt(676, 642, "融合 = 把中间 Tensor 的「写回 + 读出」搬进"
                "寄存器 / 片上", 11, INK))
    b.append(txt(676, 662, "收益公式（明天算）：省下的流量 = 今天的 64 B"
                " 两遍税", 11, ORANGE, bold=True))
    b.append(txt(676, 682, "减去融合付出的代价（寄存器 / 片上 / 并行度，"
                "Day 73）", 10.5, MUTED))

    save("04-chain-ledger.svg", "".join(b))


if __name__ == "__main__":
    fig1()
    fig2()
    fig3()
    fig4()
