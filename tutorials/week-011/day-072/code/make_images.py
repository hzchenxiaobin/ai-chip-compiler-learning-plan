#!/usr/bin/env python3
"""make_images.py —— 第 72 天（融合减少的流量）教程的四张手绘 sketch 风 SVG 信息图。

风格约定（与第 71 天及之前各天一致，Excalidraw-like）：
  - 背景 #fdfaf2（米白），盒子白底 + 深灰 #6b6357 手绘描边
  - 强调色不超过 4 种柔和色：蓝 #4a7fa5 / 橙 #a8772e / 绿 #5a8a5a / 红 #b0605a
  - 线条带轻微抖动（L 段折线），圆头笔触，线宽 2 左右
  - 手写感字体栈：Comic Sans MS / Comic Neue / Kaiti SC / 楷体 / cursive
  - 只用矩形、格子、箭头、圆角框等简单几何形状

图中全部数字来自 2026-11-12 的真实运行（code/outputs/）：
  fusion_traffic_lab 25/25；test_fusion_traffic 16/16；
  贯穿示例 A(2,3)@B(3,2)+D(2,2)→relu，fp32：
  P0 不融合 144 B（任务 80 + 中间落盘 64）；P1/P2 两算子融合 112 B（ΔB 32）；
  P3 全融合 80 B（ΔB 64，省 44.4%）；链 AI 0.222 → 0.400；
  多使用者 keep 策略 ΔB 48 B；bias 广播省比 65.3% → 78.0%；
  K 扫描（M=N=256）：66.6/65.3/61.5/50.0/28.6/10.5%，ΔB 恒 1 MiB；
  n 扫描（K=64）：28.6/50.0/61.5/65.3%，天花板 2/3。

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

rng = random.Random(72)


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
    b = [header(w, h, "第 72 天全貌：融合减少的流量",
                 "第 11 周「融合收益与代价模型」第二天 —— 把昨天的 64 B 两遍税"
                 "变成收益公式 ｜ 图中数字均为 2026-11-12 本机实测")]

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
                     INK if cur else MUTED, anchor="middle", bold=cur))

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
        cur = i == 1
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
    # 盒 1：从昨天的账到今天的公式
    x, y, bw2, bh2 = 40, 258, 552, 252
    b.append(sketch_rect(x, y, bw2, bh2, fill=TINT["white"], stroke=BLUE,
                         sw=2.4))
    b.append(txt(x + 14, y + 24, "① 从昨天的账到今天的公式", 13, BLUE,
                 bold=True))
    b.append(txt(x + 14, y + 52, "D71 账本：144 B = 任务流量 80 B"
                 " ＋ 中间两遍税 64 B", 11.5, INK))
    b.append(txt(x + 14, y + 76, "今天收益公式：ΔB = Σ 2 · numel · itemsize",
                 12, ORANGE, bold=True))
    b.append(txt(x + 14, y + 96, "（每消除一个单使用者中间，省它一写一读两趟）",
                 10.5, MUTED))
    # 小等式条
    eq = [("P0", "144 B", "3 kernel"), ("P1/P2", "112 B", "2 kernel"),
          ("P3", "80 B", "1 kernel")]
    for i, (p, v, k) in enumerate(eq):
        ex = x + 14 + i * 178
        b.append(sketch_rect(ex, y + 112, 168, 56, fill=TINT["blue"],
                             stroke=BLUE, sw=1.8, nseg=4))
        b.append(txt(ex + 84, y + 132, f"{p}：{v}", 12, INK,
                     anchor="middle", bold=True))
        b.append(txt(ex + 84, y + 152, k, 10.5, MUTED, anchor="middle"))
        if i < 2:
            b.append(txt(ex + 172, y + 138, "−32", 11, ORANGE, bold=True))
    b.append(txt(x + 14, y + 196, "全融合：ΔB = 2 个中间 × 2 趟 × 16 B"
                 " = 64 B，省 44.4%", 11.5, GREEN, bold=True))
    b.append(txt(x + 14, y + 220, "融合后总流量 = 任务流量 80 B：中间落盘"
                 " 64 B → 0 B", 11.5, INK))

    # 盒 2：融合流量对照表
    x, y = 612, 258
    b.append(sketch_rect(x, y, 528, 252, fill=TINT["white"], stroke=GREEN,
                         sw=2.4))
    b.append(txt(x + 14, y + 24, "② 融合流量对照表（真实运行，今天的核心产出）",
                 13, GREEN, bold=True))
    cols = [("计划", 14), ("kernel", 130), ("总流量", 200), ("ΔB", 280),
            ("省比", 340), ("链AI", 420)]
    ty = y + 52
    for name, cxx in cols:
        b.append(txt(x + cxx, ty, name, 11, MUTED, bold=True))
    b.append(sketch_line(x + 12, ty + 8, x + bw2 - 12, ty + 8, stroke=MUTED,
                         sw=1.2))
    rows = [("P0 不融合", "3", "144 B", "—", "—", "0.222"),
            ("P1 MatMul|AddReLU", "2", "112 B", "32 B", "22.2%", "0.286"),
            ("P2 MMBias|ReLU", "2", "112 B", "32 B", "22.2%", "0.286"),
            ("P3 全融合", "1", "80 B", "64 B", "44.4%", "0.400")]
    ry = ty + 26
    for r in rows:
        emph = r[0].startswith("P3")
        for (val, (name, cxx)) in zip(r, cols):
            b.append(txt(x + cxx, ry, val, 11.5,
                         ORANGE if emph else INK, bold=emph or name == "计划"))
        ry += 24
    b.append(txt(x + 14, y + 180, "任务流量 80 B 四种计划都一样：P3 恰好"
                 "只付任务流量", 11, MUTED))
    b.append(txt(x + 14, y + 202, "FLOPs 恒 32：链 AI 0.222 → 0.400"
                 "（融合提高强度，但仍远低于 12.54）", 11, MUTED))

    # 盒 3：收益的三个边界
    x, y, bw2, bh2 = 40, 556, 552, 150
    b.append(sketch_rect(x, y, bw2, bh2, fill=TINT["white"], stroke=ORANGE,
                         sw=2.4))
    b.append(txt(x + 14, y + 24, "③ 收益的三个边界（什么时候退不了税）", 13,
                 ORANGE, bold=True))
    b.append(txt(x + 14, y + 50, "单使用者：E 还被外部 kernel 用时，它的写和"
                 "外部读省不掉", 11, INK))
    b.append(txt(x + 14, y + 70, "  → keep 策略只省 48 B = C 2 趟 + E 1 趟"
                 "（不是 64 B）", 11, RED, bold=True))
    b.append(txt(x + 14, y + 94, "寄存器驻留：中间值装不进寄存器会溢出，"
                 "收益被吃掉（D73 算代价）", 11, INK))
    b.append(txt(x + 14, y + 118, "无缓存复用口径：小 Tensor 可能被 L2 兜住"
                 " → 公式是理想上界", 11, INK))

    # 盒 4：Shape 扫描
    x, y = 612, 556
    b.append(sketch_rect(x, y, 528, 150, fill=TINT["white"], stroke=GREEN,
                         sw=2.4))
    b.append(txt(x + 14, y + 24, "④ Shape 扫描：省比 = 4MN/(MK+KN+6MN) < 2/3",
                 13, GREEN, bold=True))
    b.append(txt(x + 14, y + 50, "K↑（M=N=256）：66.6% → 10.5%；"
                 "ΔB 恒 16·MN = 1 MiB", 11, INK))
    b.append(txt(x + 14, y + 74, "n↑（K=64）：28.6% → 65.3%，"
                 "爬向 2/3 ≈ 66.7% 天花板", 11, INK))
    b.append(txt(x + 14, y + 98, "bias (M,N) → (N,) 广播：ΔB 不变，"
                 "省比 65.3% → 78.0%", 11, INK))
    b.append(txt(x + 14, y + 122, "绝对收益只看输出规模 MN；相对收益看"
                 "中间占流量的比重", 11, MUTED))

    # ---- 底部徽标 ----
    badges = [("主实验 25/25", GREEN), ("验收测试 16/16", GREEN),
              ("产出：对照表＋收益公式＋扫描数据", ORANGE),
              ("4 张图全部真实数字", BLUE)]
    bx3 = 40
    for s, c in badges:
        b.append(badge(bx3, 748, s, c))
        bx3 += tw(s, 11.5) + 34

    b.append(txt(40, 806, "运行入口：code/run_all.sh（主实验 → 独立测试 →"
                " 重新生成本组图片）", 11, MUTED))
    save("01-overview.svg", "".join(b))


# ============================================================
# 图 2：核心机制（P0 绕道 DRAM vs P3 寄存器手递手）
# ============================================================

def fig2() -> None:
    w, h = 1180, 820
    b = [header(w, h, "核心机制：不融合 = 中间结果绕道 DRAM；融合 = 寄存器里手递手",
                 "上：P0 三个 kernel，C、E 落在 DRAM 里来回 ｜ 下：P3 单 kernel，"
                 "C、E 只活在寄存器 ｜ 右：收益公式")]

    # ================= P0 面板 =================
    b.append(panel_title(40, 96, "P0 不融合：3 个 kernel，中间结果必须绕道 DRAM"
                         "（总流量 144 B）", BLUE))
    # kernel 盒
    for kx, name in [(100, "MatMul"), (420, "Add"), (720, "Relu")]:
        b.append(sketch_rect(kx, 112, 120, 52, fill=TINT["blue"],
                             stroke=BLUE, sw=2.2))
        b.append(txt(kx + 60, 133, name, 13, INK, anchor="middle", bold=True))
        b.append(txt(kx + 60, 152, "kernel", 10, MUTED, anchor="middle"))
    # B、D 从上方进入
    for x0, label, arrow_x in [(240, "B (3,2) 读 24 B", 240),
                               (560, "D (2,2) 读 16 B", 560)]:
        b.append(sketch_rect(x0 - 48, 66, 96, 32, fill=TINT["white"],
                             sw=1.8))
        b.append(txt(x0, 87, label, 10.5, INK, anchor="middle"))
        b.append(sketch_line(arrow_x, 98, arrow_x, 110, arrow=True, sw=1.8))

    # DRAM 带 + 六个 Tensor 盒
    dram_y = 306
    b.append(sketch_rect(40, dram_y, 840, 46, fill=TINT["gray"],
                         stroke=STROKE, sw=2.2))
    b.append(txt(460, 335, "内存 DRAM（kernel 之间交接必须经过这里）", 12,
                 INK, anchor="middle", bold=True))
    tens = [(60, "A (2,3)", "读 24 B", "white", STROKE),
            (150, "B (3,2)", "读 24 B", "white", STROKE),
            (300, "C (2,2)", "写16+读16", "orange", ORANGE),
            (450, "D (2,2)", "读 16 B", "white", STROKE),
            (600, "E (2,2)", "写16+读16", "orange", ORANGE),
            (750, "F (2,2)", "写 16 B", "green", GREEN)]
    for x0, label, sub, tint, st in tens:
        b.append(sketch_rect(x0, dram_y - 38, 82, 34,
                             fill=TINT[tint], stroke=st, sw=2.0))
        b.append(txt(x0 + 41, dram_y - 24, label, 10.5, INK,
                     anchor="middle", bold=True))
        b.append(txt(x0 + 41, dram_y - 10, sub, 9.5, st, anchor="middle"))
    # 读写箭头：kernel <-> DRAM
    # A、B -> MatMul（读，上行）
    b.append(sketch_line(100, dram_y - 38, 130, 166, stroke=GREEN, sw=2.0,
                         arrow=True))
    b.append(sketch_line(190, dram_y - 38, 170, 166, stroke=GREEN, sw=2.0,
                         arrow=True))
    # MatMul -> C（写，下行）
    b.append(sketch_line(215, 166, 325, dram_y - 38, stroke=RED, sw=2.2,
                         arrow=True))
    b.append(txt(232, 240, "写 16 B", 10.5, RED, bold=True))
    # C -> Add（读，上行）
    b.append(sketch_line(355, dram_y - 38, 440, 166, stroke=GREEN, sw=2.2,
                         arrow=True))
    b.append(txt(368, 240, "读 16 B", 10.5, GREEN, bold=True))
    # D -> Add（读）
    b.append(sketch_line(490, dram_y - 38, 475, 166, stroke=GREEN, sw=2.0,
                         arrow=True))
    # Add -> E（写）
    b.append(sketch_line(510, 166, 625, dram_y - 38, stroke=RED, sw=2.2,
                         arrow=True))
    b.append(txt(527, 240, "写 16 B", 10.5, RED, bold=True))
    # E -> Relu（读）
    b.append(sketch_line(655, dram_y - 38, 740, 166, stroke=GREEN, sw=2.2,
                         arrow=True))
    b.append(txt(668, 240, "读 16 B", 10.5, GREEN, bold=True))
    # Relu -> F（写）
    b.append(sketch_line(780, 166, 785, dram_y - 38, stroke=RED, sw=2.0,
                         arrow=True))
    # 两遍税标注
    b.append(txt(40, 388, "两遍税：C（写16+读16）+ E（写16+读16）= 64 B 落盘"
                 " —— 只要三个算子独立执行，这笔税就是结构性的", 12, ORANGE,
                 bold=True))
    b.append(badge(920, 120, "总流量 144 B", BLUE, 12))
    b.append(badge(920, 152, "读 96 + 写 48", MUTED, 11))
    b.append(badge(920, 184, "中间落盘 64 B（44.4%）", ORANGE, 11))

    # 右侧公式卡
    cx, cy, cw2, ch2 = 900, 236, 240, 168
    b.append(sketch_rect(cx, cy, cw2, ch2, fill=TINT["white"], stroke=BLUE,
                         sw=2.4))
    b.append(txt(cx + 14, cy + 24, "收益公式（今天）", 13, BLUE, bold=True))
    b.append(txt(cx + 14, cy + 50, "ΔB = Σ 2 · numel · itemsize", 12, INK,
                 bold=True))
    b.append(txt(cx + 14, cy + 72, "被消除的中间 × 一写一读两趟", 10.5, MUTED))
    b.append(txt(cx + 14, cy + 98, "本例：2 个 × 2 趟 × 16 B = 64 B", 11.5,
                 ORANGE, bold=True))
    b.append(txt(cx + 14, cy + 122, "前提：单使用者（D52）＋ 寄存器装得下"
                 "（D73）", 10, MUTED))
    b.append(txt(cx + 14, cy + 142, "＋ 无跨 kernel 缓存复用（口径）", 10,
                 MUTED))

    # ================= P3 面板 =================
    py0 = 440
    b.append(panel_title(40, py0 + 16, "P3 全融合：1 个 kernel，中间结果在寄存器里"
                         "手递手（总流量 80 B）", GREEN))
    # 大 kernel 盒 + 寄存器子盒
    b.append(sketch_rect(150, py0 + 40, 430, 128, fill=TINT["blue"],
                         stroke=BLUE, sw=2.6))
    b.append(txt(365, py0 + 64, "FusedMatMulBiasReLU（1 kernel）", 13, INK,
                 anchor="middle", bold=True))
    b.append(sketch_rect(170, py0 + 78, 390, 66, fill=TINT["green"],
                         stroke=GREEN, sw=1.8, nseg=8))
    b.append(txt(360, py0 + 96, "寄存器：C 和 E 只在这里活着，不落盘", 11,
                 GREEN, anchor="middle", bold=True))
    # 手递手示意：C 圈 → +D → E 圈
    b.append(dot(280, py0 + 122, 13, fill=TINT["white"], stroke=ORANGE))
    b.append(txt(280, py0 + 126, "C", 11, ORANGE, anchor="middle", bold=True))
    b.append(sketch_line(296, py0 + 122, 396, py0 + 122, stroke=ORANGE,
                         sw=2.0, arrow=True))
    b.append(txt(346, py0 + 116, "+D, relu", 9.5, MUTED, anchor="middle"))
    b.append(dot(412, py0 + 122, 13, fill=TINT["white"], stroke=ORANGE))
    b.append(txt(412, py0 + 126, "E", 11, ORANGE, anchor="middle", bold=True))
    b.append(txt(500, py0 + 126, "手递手，不经过 DRAM", 10, MUTED))

    # DRAM 带 + 四个 Tensor 盒（没有 C、E！）
    dram_y2 = 680
    b.append(sketch_rect(40, dram_y2, 840, 46, fill=TINT["gray"],
                         stroke=STROKE, sw=2.2))
    b.append(txt(460, 709, "内存 DRAM（只剩外部输入 A、B、D 和最终输出 F）",
                 12, INK, anchor="middle", bold=True))
    tens2 = [(90, "A (2,3)", "读 24 B"), (250, "B (3,2)", "读 24 B"),
             (410, "D (2,2)", "读 16 B"), (610, "F (2,2)", "写 16 B")]
    for x0, label, sub in tens2:
        b.append(sketch_rect(x0, dram_y2 - 38, 82, 34,
                             fill=TINT["white"], stroke=STROKE, sw=2.0))
        b.append(txt(x0 + 41, dram_y2 - 24, label, 10.5, INK,
                     anchor="middle", bold=True))
        b.append(txt(x0 + 41, dram_y2 - 10, sub, 9.5, MUTED,
                     anchor="middle"))
    b.append(txt(735, dram_y2 - 18, "C、E 不在这里", 10.5, ORANGE, bold=True))
    # 读写箭头
    b.append(sketch_line(130, dram_y2 - 38, 230, py0 + 168, stroke=GREEN,
                         sw=2.2, arrow=True))
    b.append(txt(120, 610, "读 24 B", 10.5, GREEN, bold=True))
    b.append(sketch_line(290, dram_y2 - 38, 300, py0 + 168, stroke=GREEN,
                         sw=2.2, arrow=True))
    b.append(txt(296, 610, "读 24 B", 10.5, GREEN, bold=True))
    b.append(sketch_line(450, dram_y2 - 38, 380, py0 + 168, stroke=GREEN,
                         sw=2.2, arrow=True))
    b.append(txt(448, 610, "读 16 B", 10.5, GREEN, bold=True))
    b.append(sketch_line(500, py0 + 168, 645, dram_y2 - 38, stroke=RED,
                         sw=2.2, arrow=True))
    b.append(txt(546, 610, "写 16 B", 10.5, RED, bold=True))
    # 汇总
    b.append(txt(40, 762, "C、E 的生命周期缩短到一个 kernel 内 → 落盘 0 B；"
                 "总流量 80 B = 任务流量（读 64 + 写 16）", 12, GREEN,
                 bold=True))
    # 右侧：ΔB 拆解卡
    cx, cy = 900, 470
    b.append(sketch_rect(cx, cy, 240, 150, fill=TINT["white"], stroke=GREEN,
                         sw=2.4))
    b.append(txt(cx + 14, cy + 24, "省下的 64 B 从哪来", 13, GREEN, bold=True))
    b.append(txt(cx + 14, cy + 50, "C：写 16 + 读 16 = 32 B", 11.5, INK))
    b.append(txt(cx + 14, cy + 72, "E：写 16 + 读 16 = 32 B", 11.5, INK))
    b.append(txt(cx + 14, cy + 100, "P0 144 − 64 = P3 80 B", 12, GREEN,
                 bold=True))
    b.append(txt(cx + 14, cy + 124, "多使用者（keep）只省 48 B，见正文 5.4",
                 10, MUTED))
    save("02-mechanism.svg", "".join(b))


# ============================================================
# 图 3：融合流量对照（真实运行数据）
# ============================================================

def fig3() -> None:
    w, h = 1180, 780
    b = [header(w, h, "融合流量对照：任务流量纹丝不动，落盘的中间流量逐级消失",
                 "数据来自 code/outputs/fusion_traffic_lab.txt 第 3 节真实运行"
                 "（贯穿示例，fp32）｜ 条形按流量等比例绘制")]

    # ---- 上：四条堆叠条形图 ----
    b.append(panel_title(40, 96, "四种执行计划的 DRAM 流量（144 B 满量程）",
                         BLUE))
    bar_x, bar_w_full = 210, 880
    plans = [
        ("P0 不融合", "3 kernel", 144, 64, "—", "—"),
        ("P1 MatMul|FusedAddReLU", "2 kernel", 112, 32, "32 B", "22.2%"),
        ("P2 FusedMatMulBias|ReLU", "2 kernel", 112, 32, "32 B", "22.2%"),
        ("P3 全融合", "1 kernel", 80, 0, "64 B", "44.4%"),
    ]
    for i, (name, k, total, inter, delta, frac) in enumerate(plans):
        y = 118 + i * 74
        task = total - inter
        # 左侧标签
        b.append(txt(40, y + 22, name, 11.5, INK, bold=True))
        b.append(txt(40, y + 40, k, 10.5, MUTED))
        # 任务流量段（绿）
        tw_px = bar_w_full * task / 144
        b.append(sketch_rect(bar_x, y, tw_px, 48, fill=TINT["green"],
                             stroke=GREEN, sw=2.2))
        b.append(txt(bar_x + tw_px / 2, y + 21, "任务流量", 11, INK,
                     anchor="middle"))
        b.append(txt(bar_x + tw_px / 2, y + 38, f"{task} B", 11, GREEN,
                     anchor="middle", bold=True))
        # 中间落盘段（橙）
        if inter > 0:
            iw = bar_w_full * inter / 144
            b.append(sketch_rect(bar_x + tw_px, y, iw, 48,
                                 fill=TINT["orange"], stroke=ORANGE, sw=2.2))
            b.append(txt(bar_x + tw_px + iw / 2, y + 21, "中间落盘", 11, INK,
                         anchor="middle"))
            b.append(txt(bar_x + tw_px + iw / 2, y + 38, f"{inter} B", 11,
                         ORANGE, anchor="middle", bold=True))
        else:
            b.append(txt(bar_x + tw_px + 14, y + 29, "0 B（C、E 都在寄存器）",
                         11, GREEN, bold=True))
        # 右侧合计
        b.append(txt(bar_x + bar_w_full + 16, y + 22, f"{total} B", 12, INK,
                     bold=True))
        b.append(txt(bar_x + bar_w_full + 16, y + 40,
                     f"ΔB {delta}｜省 {frac}" if delta != "—" else "基准",
                     10.5, ORANGE if delta != "—" else MUTED))

    # ---- 下左：真实输出表 ----
    b.append(panel_title(40, 448, "真实运行输出（与上方条形逐格对应）", GREEN))
    cols = [("计划", 40), ("kernel", 172), ("读(B)", 240), ("写(B)", 310),
            ("总流量(B)", 380), ("中间落盘", 480), ("ΔB", 580), ("省比", 640)]
    ty = 472
    for name, cxx in cols:
        b.append(txt(cxx, ty, name, 10.5, MUTED, bold=True))
    b.append(sketch_line(40, ty + 8, 700, ty + 8, stroke=MUTED, sw=1.2))
    rows = [("P0 不融合", "3", "96", "48", "144", "64 B", "—", "—"),
            ("P1 MatMul|AddReLU", "2", "80", "32", "112", "32 B", "32 B",
             "22.2%"),
            ("P2 MMBias|ReLU", "2", "80", "32", "112", "32 B", "32 B",
             "22.2%"),
            ("P3 全融合", "1", "64", "16", "80", "0 B", "64 B", "44.4%")]
    ry = ty + 26
    for r in rows:
        emph = r[0].startswith("P3")
        for val, (name, cxx) in zip(r, cols):
            b.append(txt(cxx, ry, val, 11, ORANGE if emph else INK,
                         bold=emph or name == "计划"))
        ry += 22
    b.append(txt(40, ry + 8, "拆账闭合：任务 80 ＋ 中间落盘 == 总流量"
                 "（主实验检查 3d）", 10.5, MUTED))

    # ---- 下右：两条结论卡 ----
    x, y = 760, 448
    b.append(sketch_rect(x, y, 380, 132, fill=TINT["blue"], stroke=BLUE,
                         sw=2.2))
    b.append(txt(x + 14, y + 24, "FLOPs 恒 32，AI 0.222 → 0.400", 12, BLUE,
                 bold=True))
    b.append(txt(x + 14, y + 48, "融合把逐元素尾部的带宽账折进 MatMul 的"
                 "写回环节", 10.5, INK))
    b.append(txt(x + 14, y + 68, "链 AI 仍远低于平衡点 12.54：融合提强度，"
                 "不改变受限类型", 10.5, INK))
    b.append(txt(x + 14, y + 92, "（省下的 64 B 里没有 1 B 来自少算运算）",
                 10.5, MUTED))
    b.append(sketch_rect(x, y + 148, 380, 108, fill=TINT["orange"],
                         stroke=ORANGE, sw=2.2))
    b.append(txt(x + 14, y + 172, "P1 与 P2 都是 112 B", 12, ORANGE, bold=True))
    b.append(txt(x + 14, y + 196, "本链 C、E 同尺寸：消哪个都省 32 B"
                 "——流量打平", 10.5, INK))
    b.append(txt(x + 14, y + 216, "选哪个不看流量：看 D73 的资源代价与"
                 "D74 的收益判断", 10.5, INK))
    b.append(txt(x + 14, y + 240, "（kernel 数也一样从 3 → 2，launch 开销"
                 "今天不计）", 10, MUTED))
    save("03-comparison.svg", "".join(b))


# ============================================================
# 图 4：Shape 扫描（真实数据点）
# ============================================================

def fig4() -> None:
    w, h = 1180, 780
    b = [header(w, h, "Shape 扫描：绝对收益只看输出规模，相对收益被输入稀释",
                 "数据来自 code/outputs/fusion_traffic_lab.txt 第 4 节真实运行"
                 "（fp32，理想下界口径）｜ 横轴对数刻度，纵轴线性")]

    # ---- 左图：K 扫描 ----
    x0, x1, y0, y1 = 120, 540, 430, 150
    b.append(panel_title(40, 104, "固定 M=N=256，扫 K：省比被输入稀释", BLUE))

    def px_k(K):
        return x0 + math.log10(K) / math.log10(4096) * (x1 - x0)

    def py_f(f):
        return y0 - f / 0.70 * (y0 - y1)

    # 轴
    b.append(sketch_line(x0 - 20, y0, x1 + 16, y0, sw=2.2))
    b.append(sketch_line(x0 - 20, y0, x0 - 20, y1 - 8, sw=2.2))
    for pct in (0, 20, 40, 60):
        yy = py_f(pct / 100)
        b.append(sketch_line(x0 - 26, yy, x0 - 14, yy, sw=1.5))
        b.append(txt(x0 - 32, yy + 4, f"{pct}%", 10, MUTED, anchor="end"))
    for K in (1, 16, 64, 256, 1024, 4096):
        xx = px_k(K)
        b.append(sketch_line(xx, y0, xx, y0 + 6, sw=1.5))
        b.append(txt(xx, y0 + 22, str(K), 10.5, MUTED, anchor="middle"))
    b.append(txt((x0 + x1) / 2, y0 + 46, "归约维度 K（对数刻度，M=N=256）",
                 11.5, MUTED, anchor="middle"))
    b.append(f'<text x="{x0 - 92}" y="{(y0 + y1) / 2}" '
             f'font-family="{FONT}" font-size="11.5" fill="{MUTED}" '
             f'text-anchor="middle" transform="rotate(-90 '
             f'{x0 - 92} {(y0 + y1) / 2})">'
             f'{esc("全融合省比 ΔB / B₀")}</text>')
    # 数据点（真实）
    sweep_k = [(1, 0.666), (16, 0.653), (64, 0.615), (256, 0.500),
               (1024, 0.286), (4096, 0.105)]
    pts = [(px_k(K), py_f(f)) for K, f in sweep_k]
    for (xa, ya), (xb, yb) in zip(pts, pts[1:]):
        b.append(sketch_line(xa, ya, xb, yb, stroke=BLUE, sw=2.6))
    for (K, f), (xx, yy) in zip(sweep_k, pts):
        b.append(dot(xx, yy, 5.5, fill=BLUE, stroke=BLUE))
        b.append(txt(xx, yy - 14, f"{f:.1%}", 10.5, BLUE, anchor="middle",
                     bold=True))
    b.append(txt(348, 168, "输入 A、B 变大 → 分母被稀释", 10.5, MUTED))
    # ΔB 恒定注解
    b.append(sketch_rect(300, 190, 232, 58, fill=TINT["white"], stroke=GREEN,
                         sw=2.0))
    b.append(txt(416, 212, "绝对收益 ΔB 恒 = 16·MN", 11, GREEN,
                 anchor="middle", bold=True))
    b.append(txt(416, 232, "= 1,048,576 B（1 MiB）", 10.5, GREEN,
                 anchor="middle"))
    b.append(sketch_line(300, 234, 250, py_f(0.60), stroke=GREEN, sw=1.4,
                         dashed=True))

    # ---- 右图：n 扫描 ----
    rx0, rx1 = 680, 1100
    b.append(panel_title(620, 104, "固定 K=64，扫 M=N=n：省比爬向 2/3 天花板",
                         GREEN))

    def px_n(n):
        return rx0 + (math.log10(n) - math.log10(16)) / (
            math.log10(1024) - math.log10(16)) * (rx1 - rx0)

    b.append(sketch_line(rx0 - 20, y0, rx1 + 16, y0, sw=2.2))
    b.append(sketch_line(rx0 - 20, y0, rx0 - 20, y1 - 8, sw=2.2))
    for pct in (0, 20, 40, 60):
        yy = py_f(pct / 100)
        b.append(sketch_line(rx0 - 26, yy, rx0 - 14, yy, sw=1.5))
        b.append(txt(rx0 - 32, yy + 4, f"{pct}%", 10, MUTED, anchor="end"))
    for n in (16, 64, 256, 1024):
        xx = px_n(n)
        b.append(sketch_line(xx, y0, xx, y0 + 6, sw=1.5))
        b.append(txt(xx, y0 + 22, str(n), 10.5, MUTED, anchor="middle"))
    b.append(txt((rx0 + rx1) / 2, y0 + 46, "方阵规模 n（对数刻度，K=64）",
                 11.5, MUTED, anchor="middle"))
    # 天花板
    ceil_y = py_f(2 / 3)
    b.append(sketch_line(rx0 - 20, ceil_y, rx1 + 16, ceil_y, stroke=RED,
                         sw=2.2, dashed=True))
    b.append(txt(rx1 + 6, ceil_y - 10, "上界 2/3 ≈ 66.7%", 11, RED,
                 anchor="end", bold=True))
    # 数据点（真实）
    sweep_n = [(16, 0.286), (64, 0.500), (256, 0.615), (1024, 0.653)]
    pts_n = [(px_n(n), py_f(f)) for n, f in sweep_n]
    for (xa, ya), (xb, yb) in zip(pts_n, pts_n[1:]):
        b.append(sketch_line(xa, ya, xb, yb, stroke=GREEN, sw=2.6))
    for (n, f), (xx, yy) in zip(sweep_n, pts_n):
        b.append(dot(xx, yy, 5.5, fill=GREEN, stroke=GREEN))
        b.append(txt(xx, yy - 14, f"{f:.1%}", 10.5, GREEN, anchor="middle",
                     bold=True))
    b.append(txt(950, 470, "输出 MN 变大 → 中间占流量比重升高", 10.5, MUTED,
                 anchor="end"))
    b.append(txt(950, 490, "两图共享点 (n=256, K=64) = 61.5%（检查 4e）",
                 10.5, MUTED, anchor="end"))

    # ---- 底部：三条要点 ----
    boxes = [
        (40, 546, 352, 130, BLUE,
         [("绝对收益 ΔB = 16·MN B", True),
          ("只看被消除的中间 Tensor", False),
          ("与 K、bias 形状、dtype 之外的一切无关", False),
          ("（dtype 只做线性缩放）", False)]),
        (414, 546, 352, 130, GREEN,
         [("相对收益 = 4MN/(MK+KN+6MN)", True),
          ("正方形：2n/(K+3n) → 上界 2/3", False),
          ("K↑ 被输入稀释；MN↑ 爬向天花板", False),
          ("（D76 Cost Model 的收益项输入）", False)]),
        (788, 546, 352, 130, ORANGE,
         [("同一件事的两面", True),
          ("省比 = 中间落盘 ÷ 总流量", False),
          ("输出大、输入小的链融合最赚", False),
          ("（逐元素链可到 2/3，广播 bias 78%）", False)]),
    ]
    for x, y, bw2, bh2, color, lines in boxes:
        b.append(sketch_rect(x, y, bw2, bh2, fill=TINT["white"], stroke=color,
                             sw=2.2))
        for i, (s, bold) in enumerate(lines):
            b.append(txt(x + 14, y + 26 + i * 26, s,
                         11.5 if bold else 10.5, color if bold else INK,
                         bold=bold))
    b.append(txt(40, 726, "全部数据点均为主实验真实输出；广播 bias 实验"
                "（M=N=1024, K=64）：ΔB 16 MiB 不变，省比 65.3% → 78.0%",
                 10.5, MUTED))
    save("04-sweep.svg", "".join(b))


if __name__ == "__main__":
    fig1()
    fig2()
    fig3()
    fig4()
