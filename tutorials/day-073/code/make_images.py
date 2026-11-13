#!/usr/bin/env python3
"""make_images.py —— 第 73 天（融合的资源代价）教程的四张手绘 sketch 风 SVG 信息图。

风格约定（与第 71、72 天一致，Excalidraw-like）：
  - 背景 #fdfaf2（米白），盒子白底 + 深灰 #6b6357 手绘描边
  - 强调色不超过 4 种柔和色：蓝 #4a7fa5 / 橙 #a8772e / 绿 #5a8a5a / 红 #b0605a
  - 线条带轻微抖动（L 段折线），圆头笔触，线宽 2 左右
  - 手写感字体栈：Comic Sans MS / Comic Neue / Kaiti SC / 楷体 / cursive
  - 只用矩形、格子、箭头、圆角框等简单几何形状

图中全部数字来自 2026-11-12 的真实运行（code/outputs/）：
  fusion_resource_lab 22/22；test_fusion_resource 25/25；
  机器假设卡：寄存器堆 64 KiB / SRAM 192 KiB / 64 通道 / fp32；
  贯穿示例 P3 活集 272 B = 累加器 16 B + bias 在飞 256 B，四种计划零 spill，
  净收益 0/32/32/64 B；
  tile 扫描（M=N=2048, K=64）：32→2048 活集 4,352→16,777,472 B，
  tile-AI 5.33/8.00/10.67/12.80/15.52，并发 12/3/1/1/1，
  128×128 累加器恰满 64 KiB（epilogue 256 B 顶过线），256×256 溢 256 B，
  2048 不分块溢 16,515,328 B、兑现 50.8%；
  MM→MM：K1=64/256/1024/4096 兑现 100/100/37.5/9.4%，
  净收益封顶 6 MiB = 2×16 行块×192 KiB；
  指令增量 2/K：K=3 → 66.7%，K=64 → 3.1%。

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

rng = random.Random(73)


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
    b = [header(w, h, "第 73 天全貌：融合的资源代价",
                 "第 11 周「融合收益与代价模型」第三天 —— 把昨天的隐藏假设"
                 "「寄存器够用」展开成一张资源账 ｜ 图中数字均为 2026-11-12 本机实测")]

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
             ("D73", "融合的资源代价 ←"), ("D74", "合法/收益分离"),
             ("D75", "构造不融合案例"), ("D76", "简单 Cost Model"),
             ("D77", "复盘")]
    dx, dy, dw, dh = 40, 186, 152, 46
    for i, (d, t) in enumerate(days):
        x = dx + i * (dw + 8)
        cur = i == 2
        b.append(sketch_rect(x, dy, dw, dh,
                             fill=TINT["orange"] if cur else TINT["white"],
                             stroke=ORANGE if cur else STROKE,
                             sw=2.6 if cur else 1.8))
        b.append(txt(x + dw / 2, dy + 19, d, 12,
                     ORANGE if cur else INK, anchor="middle", bold=True))
        b.append(txt(x + dw / 2, dy + 36, t, 10.5, INK, anchor="middle"))
    b.append(sketch_line(40 + 7 * (dw + 8) - 4, dy + dh / 2, 1140,
                         dy + dh / 2, stroke=MUTED, sw=1.6, dashed=True))

    # ---- 盒 1：昨天的脚注 → 今天的一句话 ----
    x, y, bw2, bh2 = 40, 258, 552, 240
    b.append(sketch_rect(x, y, bw2, bh2, fill=TINT["white"], stroke=BLUE,
                         sw=2.4))
    b.append(txt(x + 14, y + 24, "① 昨天公式有一个脚注，今天把它展开", 13, BLUE,
                 bold=True))
    b.append(txt(x + 14, y + 50, "D72 收益公式：ΔB = Σ 2 · numel · itemsize"
                 "（每个被消除的中间省两趟）", 11.5, INK))
    b.append(txt(x + 14, y + 72, "隐藏假设：中间值驻留片上（寄存器够用）"
                 "——今天验这句话", 11.5, ORANGE, bold=True))
    b.append(sketch_rect(x + 14, y + 88, 524, 74, fill=TINT["blue"],
                         stroke=BLUE, sw=2.0, nseg=8))
    b.append(txt(x + 276, y + 112, "融合 = 把中间值从 DRAM 搬进片上活集", 13,
                 INK, anchor="middle", bold=True))
    b.append(txt(x + 276, y + 136, "代价 = 活集变大（+256 B/通道）"
                 "｜收益 = 两遍税消失（64 B 全额）", 11, INK, anchor="middle"))
    b.append(txt(x + 276, y + 154, "净收益 = ΔB − spill 流量（A9 口径）", 10.5,
                 MUTED, anchor="middle"))
    b.append(txt(x + 14, y + 186, "P3 活集 272 B = 累加器 16 B + bias 在飞"
                 " 256 B：epilogue 复用累加器槽", 11.5, GREEN, bold=True))
    b.append(txt(x + 14, y + 208, "四种计划零 spill → 贯穿示例上 64 B 收益"
                 "全额兑现；资源不设限", 11.5, INK))

    # ---- 盒 2：四个代价轴 + 机器假设卡 ----
    x, y = 612, 258
    b.append(sketch_rect(x, y, 528, 240, fill=TINT["white"], stroke=GREEN,
                         sw=2.4))
    b.append(txt(x + 14, y + 24, "② 四个代价轴（机器假设卡：64 KiB 寄存器堆"
                 " / 192 KiB SRAM）", 13, GREEN, bold=True))
    axes = [
        ("寄存器", "累加器块 tm·tn·4 跨 K 循环；epilogue 只 +256 B",
         BLUE),
        ("片上存储", "降级活集与 A/B 分块共享 192 KiB；D 无复用流式不驻留",
         GREEN),
        ("并行度", "并发 tile = min(reg/acc, sram/分块)：32→2048 时 12→1",
         ORANGE),
        ("指令复杂度", "增量 2/K：K=64 → 3.1%；K=3（贯穿示例）→ 66.7%",
         RED),
    ]
    for i, (name, desc, color) in enumerate(axes):
        yy = y + 48 + i * 44
        b.append(badge(x + 14, yy - 16, name, color, size=11, h=20))
        b.append(txt(x + 110, yy, desc, 11, INK))

    # ---- 盒 3：三个真实结论 ----
    x, y, bw2, bh2 = 40, 522, 552, 184
    b.append(sketch_rect(x, y, bw2, bh2, fill=TINT["white"], stroke=ORANGE,
                         sw=2.4))
    b.append(txt(x + 14, y + 24, "③ 三个边界结论（全部真实运行）", 13, ORANGE,
                 bold=True))
    b.append(txt(x + 14, y + 50, "tile 128×128：累加器恰满 64 KiB，epilogue"
                 " 的 256 B 把它顶过线", 11.5, INK))
    b.append(txt(x + 14, y + 70, "  → tile 不能按理论最优取，要给 epilogue/"
                 "寻址留寄存器余量", 11, RED, bold=True))
    b.append(txt(x + 14, y + 96, "不分块（2048²）活集 16 MiB 顶爆片上 256 KiB："
                 "spill 15.75 MiB", 11.5, INK))
    b.append(txt(x + 14, y + 116, "  → ΔB 64 MiB 只兑现 50.8%；活集必须按 tile"
                 " 计，不随总量走", 11, RED, bold=True))
    b.append(txt(x + 14, y + 142, "MM→MM 融合：K1=1024 兑现 37.5%，净收益封顶"
                 " 6 MiB = 2×16 行块×192 KiB", 11.5, INK))
    b.append(txt(x + 14, y + 162, "  → 装不下的部分两遍税照交：收益打折而不是"
                 "亏光", 11, RED, bold=True))

    # ---- 盒 4：输出去向 ----
    x, y = 612, 522
    b.append(sketch_rect(x, y, 528, 184, fill=TINT["white"], stroke=BLUE,
                         sw=2.4))
    b.append(txt(x + 14, y + 24, "④ 这张账交给谁（本周后半程）", 13, BLUE,
                 bold=True))
    b.append(txt(x + 14, y + 50, "D74 合法性与收益性分离：收益列的输入 = "
                 "（ΔB, 资源账）", 11.5, INK))
    b.append(txt(x + 14, y + 70, "  能融合（合法性 Pattern，D50/D52）≠ "
                 "值得融合（收益判断）", 11, MUTED))
    b.append(txt(x + 14, y + 96, "D75 构造不融合案例：资源超限是四类负收益"
                 "之一", 11.5, INK))
    b.append(txt(x + 14, y + 116, "D76 Cost Model v0.1：今天的三级容量阶梯"
                 "是代价项的雏形", 11.5, INK))
    b.append(txt(x + 14, y + 148, "今天的产出：Machine 假设卡 ＋ "
                 "KernelResource 估算结构 ＋ 假设清单 A1–A10", 11.5, GREEN,
                 bold=True))

    # ---- 底部徽标 ----
    badges = [("主实验 22/22", GREEN), ("验收测试 25/25", GREEN),
              ("产出：资源估算模型＋假设清单 A1–A10", ORANGE),
              ("4 张图全部真实数字", BLUE)]
    bx3 = 40
    for s, c in badges:
        b.append(badge(bx3, 748, s, c))
        bx3 += tw(s, 11.5) + 34

    b.append(txt(40, 806, "运行入口：code/run_all.sh（主实验 → 独立测试 → "
                "重新生成本组图片）", 11, MUTED))
    save("01-overview.svg", "".join(b))


# ============================================================
# 图 2：核心机制（容量阶梯 + P3 kernel 解剖）
# ============================================================

def fig2() -> None:
    w, h = 1180, 830
    b = [header(w, h, "核心机制：活集掉进哪一级容量阶梯，决定收益还剩多少",
                 "左：三级容量阶梯（寄存器堆 → SRAM → DRAM spill）｜"
                 "右：融合 kernel 的活集解剖 ｜ 图中数字均为真实运行")]

    # ================= 左：容量阶梯 =================
    b.append(panel_title(40, 100, "三级容量阶梯（活集优先保，溢出记两趟流量）",
                         BLUE))
    # 阶梯三层（自上而下容量增大、速度变慢）；每层内嵌一个真实落位样例
    lv = [
        (110, 150, 440, 110, "第 1 级：寄存器堆 64 KiB", "累加器块 + 在飞向量"
         " ｜ 活集 ≤ 64 KiB → 落 reg",
         "样例：P3 贯穿示例 272 B（累加器 16 + bias 在飞 256）", "blue", BLUE),
        (140, 284, 440, 110, "第 2 级：片上 SRAM 192 KiB", "降级活集 + A/B 输入"
         "分块共享 ｜ 64 KiB < 活集 ≤ 256 KiB",
         "样例：tile 128×128 活集 65,792 B → 降级 256 B（epilogue 顶过线）",
         "green", GREEN),
        (170, 418, 440, 110, "第 3 级：DRAM（spill）", "超出 256 KiB 的部分回 "
         "DRAM：一写一读两趟，直接吃 ΔB",
         "样例：不分块 2048² 活集 16,777,472 B → spill 15.75 MiB",
         "red", RED),
    ]
    for x0, y0, wdt, hgt, title, desc, sample, tint, color in lv:
        b.append(sketch_rect(x0, y0, wdt, hgt, fill=TINT[tint], stroke=color,
                             sw=2.4))
        b.append(txt(x0 + wdt / 2, y0 + 28, title, 13, color, anchor="middle",
                     bold=True))
        b.append(txt(x0 + wdt / 2, y0 + 54, desc, 10.5, INK, anchor="middle"))
        b.append(txt(x0 + wdt / 2, y0 + 84, sample, 10, color, anchor="middle"))
    # 层间向下箭头
    b.append(sketch_line(330, 262, 330, 280, stroke=MUTED, sw=2.0, arrow=True))
    b.append(sketch_line(360, 396, 360, 414, stroke=MUTED, sw=2.0, arrow=True))
    b.append(txt(330, 556, "越往下越慢：reg 免费 → SRAM 无 DRAM 流量但 RMW 变慢"
                 " → spill 记两趟流量（A4 下界，真实更贵）", 10.5, MUTED,
                 anchor="middle"))
    b.append(txt(40, 584, "落位规则（假设清单精神）：活集优先占降级空间；输入分块"
                "放不下记 staging short（再细分即可，不产生流量）", 10.5, MUTED))
    b.append(txt(40, 606, "边界含等号：活集 == 容量线不溢出（自检 2a/2b：恰等 "
                "regfile 仍落 reg，恰等 onchip 仍零 spill）", 10.5, MUTED))

    # ================= 右：P3 kernel 解剖 =================
    b.append(panel_title(620, 100, "P3 FusedMatMulBiasReLU 的活集解剖"
                         "（epilogue 融合 ≈ 寄存器免费）", GREEN))

    # kernel 大盒
    b.append(sketch_rect(640, 130, 480, 480, fill=TINT["white"], stroke=BLUE,
                         sw=2.6))
    b.append(txt(880, 152, "单个融合 kernel", 13, BLUE, anchor="middle",
                 bold=True))

    # SRAM 盒（输入分块）
    b.append(sketch_rect(660, 168, 200, 108, fill=TINT["green"], stroke=GREEN,
                         sw=2.0))
    b.append(txt(760, 188, "SRAM：A/B 分块驻留", 11, GREEN, anchor="middle",
                 bold=True))
    b.append(txt(760, 208, "(tm·K + K·tn)·4 B", 10.5, INK, anchor="middle"))
    b.append(txt(760, 226, "有复用才驻留（A3）", 10, MUTED, anchor="middle"))
    b.append(txt(760, 246, "D 无复用 → 不进来", 10, RED, anchor="middle",
                 bold=True))

    # 寄存器堆盒（累加器 + epilogue 槽）
    b.append(sketch_rect(900, 168, 200, 108, fill=TINT["blue"], stroke=BLUE,
                         sw=2.0))
    b.append(txt(1000, 188, "寄存器堆：累加器块", 11, BLUE, anchor="middle",
                 bold=True))
    b.append(txt(1000, 208, "tm·tn·4 B 跨 K 循环", 10.5, INK, anchor="middle"))
    b.append(txt(1000, 226, "+ bias 在飞 1 槽/通道", 10, ORANGE, anchor="middle",
                 bold=True))
    b.append(txt(1000, 246, "= 全部寄存器增量 256 B", 10, ORANGE, anchor="middle",
                 bold=True))

    # K 循环 + epilogue 流程
    b.append(txt(880, 300, "K 循环：累加器 += A 分块 · B 分块", 11.5, INK,
                 anchor="middle"))
    b.append(sketch_line(780, 262, 860, 292, stroke=GREEN, sw=2.0, arrow=True))
    b.append(sketch_line(990, 292, 970, 262, stroke=BLUE, sw=2.0, arrow=True,
                         dashed=True))
    b.append(txt(880, 330, "epilogue：累加器 + bias → max(·,0) → 写出 F", 11.5,
                 ORANGE, anchor="middle", bold=True))
    b.append(txt(880, 350, "（add/max 复用累加器自己的槽，不新增中间）", 10.5,
                 MUTED, anchor="middle"))
    b.append(txt(880, 382, "C、E 只存在一瞬间：累加器 → +D → max → 写出", 11,
                 GREEN, anchor="middle", bold=True))
    b.append(txt(880, 400, "两遍税消失，因为它们从没离开过片上", 10.5, GREEN,
                 anchor="middle"))

    # 溢出警告卡
    b.append(sketch_rect(660, 430, 440, 84, fill=TINT["red"], stroke=RED,
                         sw=2.2))
    b.append(txt(880, 452, "若活集 > 片上容量（累加器装不下）", 12, RED,
                 anchor="middle", bold=True))
    b.append(txt(880, 472, "超出部分 spill 回 DRAM：一写一读两趟", 11, INK,
                 anchor="middle"))
    b.append(txt(880, 492, "昨天的 ΔB 被砍：净收益 = ΔB − spill 流量", 11, RED,
                 anchor="middle", bold=True))

    # DRAM 带
    dram_y = 680
    b.append(sketch_rect(620, dram_y, 520, 46, fill=TINT["gray"],
                        stroke=STROKE, sw=2.2))
    b.append(txt(880, dram_y + 29, "内存 DRAM：A、B、D 流入，F 写出；C、E 不在这里",
                 11.5, INK, anchor="middle", bold=True))

    # 流箭头：kernel 底边 ↔ DRAM 带（短箭头，不穿内容）
    b.append(sketch_line(760, dram_y - 6, 760, 616, stroke=GREEN, sw=2.0,
                         arrow=True))
    b.append(txt(770, 640, "A、B 分块流入", 10, GREEN, bold=True))
    b.append(sketch_line(880, dram_y - 6, 880, 616, stroke=ORANGE, sw=2.0,
                         arrow=True, dashed=True))
    b.append(txt(890, 640, "D 流式直进 epilogue", 10, ORANGE, bold=True))
    b.append(sketch_line(1040, 616, 1040, dram_y - 6, stroke=RED, sw=2.2,
                         arrow=True))
    b.append(txt(1050, 640, "F 写出", 10, RED, bold=True))
    b.append(txt(620, 756, "右图对应活集公式：P3 = 累加器 tm·tn·4 + 256 B；"
                "tile 是活集的调节阀（见正文 5.4）", 10.5, MUTED))
    save("02-mechanism.svg", "".join(b))


# ============================================================
# 图 3：实例对照（贯穿示例资源账，真实运行）
# ============================================================

def fig3() -> None:
    w, h = 1180, 790
    b = [header(w, h, "实例对照：小链上的资源账——融合用 256 B 换 64 B",
                 "数据来自 code/outputs/fusion_resource_lab.txt 第 3 节真实运行"
                 "（A(2,3)@B(3,2)+D(2,2)→relu，fp32，64 通道）")]

    # ---- 上：四种计划资源账表 ----
    b.append(panel_title(40, 100, "四种计划的资源账（今天的核心表之一）", BLUE))
    cols = [("计划", 60), ("kernel", 130), ("峰值片上活集", 190),
            ("放置", 320), ("spill", 385), ("省下(D72口径)", 445),
            ("净收益", 560)]
    ty = 130
    for name, cxx in cols:
        b.append(txt(cxx, ty, name, 11, MUTED, bold=True))
    b.append(sketch_line(50, ty + 8, 640, ty + 8, stroke=MUTED, sw=1.2))
    rows = [
        ("P0 不融合", "3", "768 B（Add 在飞）", "reg", "0 B", "0 B", "0 B",
         False),
        ("P1 MatMul|FusedAddReLU", "2", "768 B", "reg", "0 B", "32 B", "32 B",
         False),
        ("P2 FusedMatMulBias|ReLU", "2", "512 B（Relu 在飞）", "reg", "0 B",
         "32 B", "32 B", False),
        ("P3 全融合", "1", "320 B（272+48staging）", "reg", "0 B", "64 B",
         "64 B", True),
    ]
    ry = ty + 28
    for name, nk, live, place, spill, saved, net, emph in rows:
        color = ORANGE if emph else INK
        b.append(txt(60, ry, name, 11.5, color, bold=emph))
        b.append(txt(130, ry, nk, 11.5, color, bold=emph))
        b.append(txt(190, ry, live, 11, color, bold=emph))
        b.append(txt(320, ry, place, 11.5, color, bold=emph))
        b.append(txt(385, ry, spill, 11.5, color, bold=emph))
        b.append(txt(445, ry, saved, 11.5, color, bold=emph))
        b.append(txt(560, ry, net, 11.5, color, bold=emph))
        ry += 26
    b.append(txt(60, ry + 6, "峰值片上活集 < 1 KiB ≪ 寄存器堆 64 KiB：小链上"
                "资源不设限，四计划全部落 reg", 11, MUTED))

    # ---- 中：交换卡（DRAM 驻留 → 片上活集）----
    y0 = 280
    b.append(panel_title(40, y0, "融合的交换：中间值从 DRAM 搬进片上活集", GREEN))
    # P0 半边
    b.append(sketch_rect(60, y0 + 24, 240, 130, fill=TINT["orange"],
                         stroke=ORANGE, sw=2.2))
    b.append(txt(180, y0 + 48, "P0 不融合", 12, ORANGE, anchor="middle",
                 bold=True))
    b.append(txt(180, y0 + 74, "中间值 C、E 驻 DRAM：32 B", 11.5, INK,
                 anchor="middle"))
    b.append(txt(180, y0 + 96, "两遍税 64 B（D72 的账）", 11, ORANGE,
                 anchor="middle", bold=True))
    b.append(txt(180, y0 + 128, "片上活集小但 DRAM 流量大", 10.5, MUTED,
                 anchor="middle"))
    # 交换箭头
    b.append(sketch_line(310, y0 + 88, 420, y0 + 88, stroke=GREEN, sw=2.6,
                         arrow=True))
    b.append(txt(365, y0 + 74, "融合", 11, GREEN, anchor="middle", bold=True))
    b.append(txt(365, y0 + 108, "交换", 10.5, GREEN, anchor="middle"))
    # P3 半边
    b.append(sketch_rect(430, y0 + 24, 240, 130, fill=TINT["green"],
                         stroke=GREEN, sw=2.2))
    b.append(txt(550, y0 + 48, "P3 全融合", 12, GREEN, anchor="middle",
                 bold=True))
    b.append(txt(550, y0 + 74, "中间值驻片上活集：272 B", 11.5, INK,
                 anchor="middle"))
    b.append(txt(550, y0 + 96, "两遍税 0 B", 11, GREEN, anchor="middle",
                 bold=True))
    b.append(txt(550, y0 + 128, "DRAM 中间 0 B：收益全额到手", 10.5, MUTED,
                 anchor="middle"))
    b.append(txt(360, y0 + 180, "代价 = 活集增量 256 B/通道（bias 在飞），"
                "收益 = 64 B 两遍税消失——贯穿示例上稳赚", 11.5, INK,
                 anchor="middle", bold=True))

    # ---- 右：epilogue 增量拆解卡 ----
    x, y = 740, y0 + 6
    b.append(sketch_rect(x, y + 16, 400, 200, fill=TINT["white"], stroke=BLUE,
                         sw=2.2))
    b.append(txt(x + 14, y + 40, "为什么 P3 ≈ P0 的 MatMul ＋ 256 B", 12.5,
                 BLUE, bold=True))
    b.append(txt(x + 14, y + 66, "P0 MatMul 活集：累加器 16 B", 11.5, INK))
    b.append(txt(x + 14, y + 86, "P3 活集：累加器 16 B + bias 在飞 256 B", 11.5,
                 ORANGE, bold=True))
    b.append(txt(x + 14, y + 112, "逐元素 epilogue 复用累加器槽做完 add/max：", 11,
                 INK))
    b.append(txt(x + 14, y + 130, "寄存器上近乎免费（检查 3b）", 11, GREEN,
                 bold=True))
    b.append(txt(x + 14, y + 158, "指令增量 2/K：K=3 → 66.7%（相对大绝对小）", 11,
                 INK))
    b.append(txt(x + 14, y + 178, "『小实验上融合永远免费』是陷阱：", 10.5, RED,
                 bold=True))
    b.append(txt(x + 14, y + 196, "放大 shape 才见容量边界（正文 5.4）", 10.5,
                 RED, bold=True))

    # ---- 下：P0 各 kernel 的活集条形对比 ----
    y1 = 520
    b.append(panel_title(40, y1, "各 kernel 的活集（真实值；条形对数示意，"
                         "非等比例）", ORANGE))
    bars = [
        ("P0 MatMul", 16, "累加器 2×2 fp32", BLUE),
        ("P0 Add", 768, "3 个在飞向量（2 入 1 出）", BLUE),
        ("P0 Relu", 512, "2 个在飞向量", BLUE),
        ("P3 全融合", 272, "累加器 16 B + bias 256 B", GREEN),
    ]
    bx0 = 190
    for i, (name, val, sub, color) in enumerate(bars):
        yy = y1 + 22 + i * 52
        b.append(txt(60, yy + 16, name, 11.5, color, bold=True))
        width = 60 + 340 * (math.log10(val) - 1) / 4   # 10 B → 100 KiB 对数条
        b.append(sketch_rect(bx0, yy, width, 32, fill=TINT["white"], stroke=color,
                             sw=2.0, nseg=5))
        b.append(txt(bx0 + width + 12, yy + 21, f"{val} B", 11.5, color,
                     bold=True))
        b.append(txt(bx0 + width + 78, yy + 21, sub, 10, MUTED))
    b.append(txt(60, y1 + 240, "逐元素 kernel 的活集 = 每通道在飞向量（A5 流式），"
                "与数据总量无关；小链上 MatMul 累加器只有 16 B——", 10.5, MUTED))
    b.append(txt(60, y1 + 258, "真实大 shape 下累加器才是主角（下一张图的 "
                "tile 扫描）", 10.5, MUTED))
    save("03-comparison.svg", "".join(b))


# ============================================================
# 图 4：扫描实验（tile 折中 + K1 兑现率，真实数据点）
# ============================================================

def fig4() -> None:
    w, h = 1180, 800
    b = [header(w, h, "扫描实验：tile 是复用与并行度的折中；装不下就打折",
                 "数据来自 code/outputs/fusion_resource_lab.txt 第 4、5 节真实运行"
                 "（fp32，toy-core：64 KiB reg / 192 KiB SRAM）")]

    # ================= 左：tile 扫描 =================
    x0, x1, y0, y1 = 130, 520, 400, 130
    b.append(panel_title(40, 104, "扫 tile（M=N=2048, K=64）：AI 升、并发降、"
                         "容量顶爆", BLUE))

    def px_t(t):
        return x0 + (math.log10(t) - math.log10(32)) / (
            math.log10(2048) - math.log10(32)) * (x1 - x0)

    # AI 轴（左）
    for ai_v in (4, 8, 12, 16):
        yy = y0 - (ai_v - 4) / 12 * (y0 - y1)
        b.append(sketch_line(x0 - 26, yy, x0 - 14, yy, sw=1.5))
        b.append(txt(x0 - 32, yy + 4, f"{ai_v}", 10, MUTED, anchor="end"))
    b.append(f'<text x="{x0 - 66}" y="{(y0 + y1) / 2}" '
             f'font-family="{FONT}" font-size="11" fill="{MUTED}" '
             f'text-anchor="middle" transform="rotate(-90 '
             f'{x0 - 66} {(y0 + y1) / 2})">'
             f'{esc("tile-AI（FLOP/B）")}</text>')
    # 并发轴（右）
    for cc_v in (1, 4, 8, 12):
        yy = y0 - (cc_v - 1) / 11 * (y0 - y1)
        b.append(sketch_line(x1 + 14, yy, x1 + 26, yy, sw=1.5))
        b.append(txt(x1 + 34, yy + 4, f"{cc_v}", 10, MUTED))
    b.append(f'<text x="{x1 + 70}" y="{(y0 + y1) / 2}" '
             f'font-family="{FONT}" font-size="11" fill="{MUTED}" '
             f'text-anchor="middle" transform="rotate(90 '
             f'{x1 + 70} {(y0 + y1) / 2})">'
             f'{esc("并发 tile 数")}</text>')
    # x 轴
    b.append(sketch_line(x0 - 20, y0, x1 + 16, y0, sw=2.2))
    for t in (32, 64, 128, 256, 2048):
        xx = px_t(t)
        b.append(sketch_line(xx, y0, xx, y0 + 6, sw=1.5))
        b.append(txt(xx, y0 + 22, str(t), 10.5, MUTED, anchor="middle"))
    b.append(txt((x0 + x1) / 2, y0 + 46, "tile 边长（对数刻度）", 11.5, MUTED,
                 anchor="middle"))
    # 平衡线 12.54
    bal_y = y0 - (12.54 - 4) / 12 * (y0 - y1)
    b.append(sketch_line(x0 - 20, bal_y, x1 + 16, bal_y, stroke=RED, sw=2.0,
                         dashed=True))
    b.append(txt(x1 - 4, bal_y - 10, "机器平衡点 12.54（D71）", 10.5, RED,
                 anchor="end", bold=True))
    # AI 折线（真实点）
    ai_pts = [(32, 5.33), (64, 8.00), (128, 10.67), (256, 12.80),
              (2048, 15.52)]
    pts = [(px_t(t), y0 - (a - 4) / 12 * (y0 - y1)) for t, a in ai_pts]
    for (xa, ya), (xb, yb) in zip(pts, pts[1:]):
        b.append(sketch_line(xa, ya, xb, yb, stroke=BLUE, sw=2.6))
    for (t, a), (xx, yy) in zip(ai_pts, pts):
        b.append(dot(xx, yy, 5.5, fill=BLUE, stroke=BLUE))
        b.append(txt(xx, yy - 13, f"{a:.2f}", 10, BLUE, anchor="middle",
                     bold=True))
    # 并发折线（真实点）
    cc_pts = [(32, 12), (64, 3), (128, 1), (256, 1), (2048, 1)]
    cpts = [(px_t(t), y0 - (c - 1) / 11 * (y0 - y1)) for t, c in cc_pts]
    for (xa, ya), (xb, yb) in zip(cpts, cpts[1:]):
        b.append(sketch_line(xa, ya, xb, yb, stroke=GREEN, sw=2.6,
                             dashed=True))
    for (t, c), (xx, yy) in zip(cc_pts, cpts):
        b.append(dot(xx, yy, 5.5, fill=GREEN, stroke=GREEN))
        b.append(txt(xx, yy - 13, f"{c}", 10, GREEN, anchor="middle",
                     bold=True))
    # 标注
    b.append(txt(238, 158, "tile 256：AI 12.80 翻过平衡点，", 10, RED))
    b.append(txt(238, 172, "但 SRAM 先顶爆（spill 256 B）", 10, RED))
    b.append(txt(240, 330, "tile 128×128：累加器恰满 64 KiB", 10, ORANGE,
                 bold=True))
    b.append(txt(240, 344, "epilogue 256 B 顶过线 → 并发只剩 1", 10, ORANGE))
    b.append(txt(330, 362, "tile 2048 不分块：活集 16 MiB", 10, RED, bold=True))
    b.append(txt(330, 376, "spill 15.75 MiB，兑现 50.8%", 10, RED, bold=True))

    # ================= 右：K1 扫描（MM→MM）=================
    rx0, rx1 = 700, 1100
    b.append(panel_title(620, 104, "扫 K1（MatMul→MatMul 融合）：兑现率跌、"
                         "净收益封顶", GREEN))

    def px_k(Kv):
        return rx0 + (math.log10(Kv) - math.log10(64)) / (
            math.log10(4096) - math.log10(64)) * (rx1 - rx0)

    # 兑现率轴（左）
    for pct in (0, 25, 50, 75, 100):
        yy = y0 - pct / 100 * (y0 - y1)
        b.append(sketch_line(rx0 - 26, yy, rx0 - 14, yy, sw=1.5))
        b.append(txt(rx0 - 32, yy + 4, f"{pct}%", 10, MUTED, anchor="end"))
    b.append(f'<text x="{rx0 - 68}" y="{(y0 + y1) / 2}" '
             f'font-family="{FONT}" font-size="11" fill="{MUTED}" '
             f'text-anchor="middle" transform="rotate(-90 '
             f'{rx0 - 68} {(y0 + y1) / 2})">'
             f'{esc("ΔB 兑现率")}</text>')
    # x 轴
    b.append(sketch_line(rx0 - 20, y0, rx1 + 16, y0, sw=2.2))
    for Kv in (64, 256, 1024, 4096):
        xx = px_k(Kv)
        b.append(sketch_line(xx, y0, xx, y0 + 6, sw=1.5))
        b.append(txt(xx, y0 + 22, str(Kv), 10.5, MUTED, anchor="middle"))
    b.append(txt((rx0 + rx1) / 2, y0 + 46, "中间维度 K1（对数刻度，行块 128 行）",
                 11.5, MUTED, anchor="middle"))
    # 兑现率折线（真实点）
    rate_pts = [(64, 1.0), (256, 1.0), (1024, 0.375), (4096, 0.09375)]
    rpts = [(px_k(Kv), y0 - r * (y0 - y1)) for Kv, r in rate_pts]
    for (xa, ya), (xb, yb) in zip(rpts, rpts[1:]):
        b.append(sketch_line(xa, ya, xb, yb, stroke=GREEN, sw=2.6))
    for (Kv, r), (xx, yy) in zip(rate_pts, rpts):
        b.append(dot(xx, yy, 5.5, fill=GREEN, stroke=GREEN))
        b.append(txt(xx, yy - 13, f"{r:.1%}", 10, GREEN, anchor="middle",
                     bold=True))
    # 驻留分界 K1=384
    bd_x = px_k(384)
    b.append(sketch_line(bd_x, y1 - 20, bd_x, y0, stroke=RED, sw=2.0,
                         dashed=True))
    b.append(txt(bd_x - 8, 128, "192 KiB 分界（K1=384）", 10, RED,
                 anchor="end", bold=True))
    b.append(txt(rx1 - 10, y0 - 60, "装不下 → 两遍税照交", 10.5, MUTED,
                 anchor="end"))
    # 净收益封顶注释卡
    b.append(sketch_rect(710, y1 - 10, 360, 58, fill=TINT["white"],
                         stroke=ORANGE, sw=2.0))
    b.append(txt(890, y1 + 12, "净收益封顶 = 2×16 行块×192 KiB = 6 MiB", 11,
                 ORANGE, anchor="middle", bold=True))
    b.append(txt(890, y1 + 32, "K1=1024 与 4096 都只净赚 6 MiB（检查 5c）",
                 10.5, INK, anchor="middle"))

    # ---- 底部：三条要点 ----
    boxes = [
        (40, 480, 352, 140, BLUE,
         [("活集随 tile 走，不随总量走", True),
          ("tile 2048→32：活集 16 MiB→4 KiB", False),
          ("ΔB 恒 64 MiB：容量与收益解耦", False),
          ("（tile 是资源侧的调节阀）", False)]),
        (414, 480, 352, 140, GREEN,
         [("净收益 ≤ 2×片上驻留×行块数", True),
          ("K1→∞ 时封顶 6 MiB、兑现率→0", False),
          ("spill 的部分两遍税原样交回", False),
          ("（收益打折，不是亏光）", False)]),
        (788, 480, 352, 140, ORANGE,
         [("tile 选择 = 折中，不是最优", True),
          ("AI↑ 复用好 ↔ 并发↑ 延迟隐藏", False),
          ("128×128 恰满载：还要留余量", False),
          ("（D76 Cost Model 的第二个输入）", False)]),
    ]
    for x, y, bw2, bh2, color, lines in boxes:
        b.append(sketch_rect(x, y, bw2, bh2, fill=TINT["white"], stroke=color,
                             sw=2.2))
        for i, (s, bold) in enumerate(lines):
            b.append(txt(x + 14, y + 26 + i * 28, s,
                         11.5 if bold else 10.5, color if bold else INK,
                         bold=bold))
    b.append(txt(40, 680, "全部数据点均为主实验真实输出（fp32；ΔB 沿用 D72 的"
                "无缓存复用口径）；AI 轴参照 D71 平衡点 12.54", 10.5, MUTED))
    b.append(txt(40, 700, "扫 tile 一览：32→64→128→256→2048 的活集 4,352 →"
                " 16,640 → 65,792 → 262,400 → 16,777,472 B（真实值）", 10.5,
                MUTED))
    save("04-sweep.svg", "".join(b))


if __name__ == "__main__":
    fig1()
    fig2()
    fig3()
    fig4()
