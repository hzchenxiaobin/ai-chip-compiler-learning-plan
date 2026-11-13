#!/usr/bin/env python3
"""make_images.py —— 第 70 天（第 10 周复盘）教程的四张手绘 sketch 风 SVG 信息图。

风格约定（与第 8/9/10 周各天一致，Excalidraw-like）：
  - 背景 #fdfaf2（米白），盒子白底 + 深灰 #6b6357 手绘描边
  - 强调色不超过 4 种柔和色：蓝 #4a7fa5 / 橙 #a8772e / 绿 #5a8a5a / 红 #b0605a
  - 线条带轻微抖动（L 段折线），圆头笔触，线宽 2 左右
  - 手写感字体栈：Comic Sans MS / Comic Neue / Kaiti SC / 楷体 / cursive
  - 只用矩形、格子、箭头、圆角框等简单几何形状

图中全部数字来自 2026-11-12 的真实运行（code/outputs/）：
  counterexample_lab 39/39；test_counterexamples 33/33；
  两本账本：同图 view 48B/1 alloc vs physical 144B/3 alloc（值逐位相等）；
  三明治 2×2：view 48/48、physical 144/48（省 96B），
  view 输出 strides (1,2)→(3,1)；
  R1 f16 roundtrip 6/6 变值；R2 V1 拦截 + shape (2,3)→(6,)；
  R3 写集合 buf1→buf0；R4 naive DCE 后 G 空；
  R5 双消费者 48B→96B；R6 op 2→3、元素 6→12；R7 shape (3,1)→(1,2)；
  MLIR：truncf+extf 不折叠、reshape 链不合并、copy 不删、
  死 addf 删 / store 留、恒等排列 linalg.transpose 不删；
  本周测试 7 套 286/286（63/33/30/39/37/51/33）。

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

rng = random.Random(70)


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


def badge(x, y, s, color, w=None, h=22):
    w = w or (len(s) * 7.2 + 14)
    return (sketch_rect(x, y, w, h, fill=TINT["white"], stroke=color,
                        sw=1.8, nseg=4)
            + txt(x + w / 2, y + h - 7, s, 11.5, color, anchor="middle",
                  bold=True))


# ============================================================
# 图 1：全貌
# ============================================================

def fig1() -> None:
    w, h = 1180, 830
    b = [header(w, h, "第 70 天全貌：第 10 周复盘",
                "第 10 周「Layout 与冗余算子消除」收官 —— 命题：图结构相同 ≠ 内存语义相同"
                " ｜ 全部数字为 2026-11-12 本机实测")]

    # ---- 顶部：本周时间线 ----
    b.append(txt(40, 92, "本周链路（第 10 周）", 13, MUTED, bold=True))
    days = [("D64", "转置语义"), ("D65", "转置消除"), ("D66", "Reshape 合并"),
            ("D67", "Cast 消除"), ("D68", "Layout 传播"),
            ("D69", "组合测试"), ("D70", "复盘")]
    bx, by, bw, bh, gap = 40, 102, 150, 46, 10
    for i, (d, t) in enumerate(days):
        x = bx + i * (bw + gap)
        today = d == "D70"
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
                 "前六天：零件与守卫（每条 Pattern 的语义门）", 11.5, MUTED))
    b.append(txt(bx + 6 * (bw + gap) + 2, by - 8,
                 "今天：收拢成一个命题 + 七条反例", 11.5, ORANGE, bold=True))

    # ---- 中排：两本账本 ----
    y0 = 196
    b.append(sketch_rect(40, y0, 330, 240, fill=TINT["white"]))
    b.append(panel_title(56, y0 + 24, "结构账本（值世界）", BLUE))
    b.append(txt(56, y0 + 48, "state_hash：算子 + 连接 + 属性", 11.5, INK))
    b.append(txt(56, y0 + 70, "回答「值怎么算」", 11.5, MUTED))
    b.append(txt(56, y0 + 102, "同一张 4-op 链：", 11.5, INK, bold=True))
    for i, line in enumerate(["arg (2,3)", "transpose (1,0) → (3,2)",
                              "relu → (3,2)", "reshape → (6,)"]):
        b.append(txt(70, y0 + 124 + i * 20, line, 11, INK))
    b.append(badge(56, y0 + 206, "hash a05676ce（两个世界共用）", BLUE))

    b.append(sketch_rect(400, y0, 330, 240, fill=TINT["white"]))
    b.append(panel_title(416, y0 + 24, "内存账本（字节世界）", RED))
    b.append(txt(416, y0 + 48, "buffer / strides / offset / traffic",
                 11.5, INK))
    b.append(txt(416, y0 + 70, "写集合 / 副作用 / 布局契约", 11.5, INK))
    b.append(txt(416, y0 + 102, "同一张图的两种物理执行：", 11.5, INK,
                 bold=True))
    b.append(sketch_rect(416, y0 + 116, 298, 44, fill=TINT["blue"]))
    b.append(txt(565, y0 + 134, "视图世界（框架前端）", 11.5, BLUE,
                 anchor="middle", bold=True))
    b.append(txt(565, y0 + 152, "traffic 48B ｜ 中间分配 1", 11.5, INK,
                 anchor="middle"))
    b.append(sketch_rect(416, y0 + 168, 298, 44, fill=TINT["red"]))
    b.append(txt(565, y0 + 186, "物理世界（降级后端）", 11.5, RED,
                 anchor="middle", bold=True))
    b.append(txt(565, y0 + 204, "traffic 144B ｜ 中间分配 3", 11.5, INK,
                 anchor="middle"))
    b.append(txt(565, y0 + 228, "输出值逐位相等 —— 差别只在内存", 11,
                 GREEN, anchor="middle", bold=True))

    # 中间的等号/不等号
    b.append(txt(385, y0 + 120, "≠", 26, RED, anchor="middle", bold=True))
    b.append(txt(385, y0 + 165, "同一张图", 10.5, MUTED, anchor="middle"))

    # ---- 右中：本周测试 + 明天 ----
    b.append(sketch_rect(760, y0, 380, 240, fill=TINT["white"]))
    b.append(panel_title(776, y0 + 24, "今天的验收（全部真实复跑）", GREEN))
    rows = [("counterexample_lab", "39/39"),
            ("test_counterexamples", "33/33"),
            ("MLIR 探针 ×5", "5/5"),
            ("本周 7 套测试", "286/286")]
    for i, (k, v) in enumerate(rows):
        yy = y0 + 52 + i * 28
        b.append(txt(776, yy, k, 11.5, INK))
        b.append(txt(1100, yy, v, 11.5, GREEN, anchor="end", bold=True))
    b.append(sketch_line(776, y0 + 168, 1124, y0 + 168, sw=1.2,
                         opacity=0.5))
    b.append(txt(776, y0 + 192, "产出：反例集（7 条）+ 一页复盘 +",
                 11.5, INK, bold=True))
    b.append(txt(776, y0 + 212, "守卫清单（每条 Pattern 的语义门）",
                 11.5, INK, bold=True))
    b.append(txt(776, y0 + 234, "明天 D71：计算量与访存量（FLOPs / 字节）",
                 11, MUTED))

    # ---- 底部：反例集 ----
    y1 = 470
    b.append(panel_title(40, y1 + 4, "反例集：7 条「看似能消除但实际不能消除」"
                         "（计划要求 ≥5）", ORANGE))
    cards = [
        ("R1", "Cast f32→f16→f32", "精度", "类型对消", "6/6 元素变值",
         "src==dst 才透传"),
        ("R2", "双层同目标 Reshape", "形状", "外层看似透明",
         "V1 拦截；(2,3)→(6,)", "只并一层"),
        ("R3", "copy(x) 消除", "别名", "值上恒等", "写集合 buf1→buf0",
         "别名分析"),
        ("R4", "无使用者的 store", "副作用", "DCE 猎物", "删后 G 变空",
         "活跃∪副作用"),
        ("R5", "恒等排列物理转置", "布局", "值上照抄", "双消费者 48→96B",
         "布局契约"),
        ("R6", "多使用者传播", "复制", "和 T(relu) 同构", "op 2→3；元素 6→12",
         "C2 唯一使用者"),
        ("R7", "reduce 传播", "轴语义", "T 挂在算子上", "shape (3,1)→(1,2)",
         "C1 白名单"),
    ]
    cx, cy, cw, ch = 40, y1 + 22, 272, 92
    for i, (rid, name, dim, lure, evid, guard) in enumerate(cards):
        col = i % 4
        row = i // 4
        x = cx + col * (cw + 10)
        y = cy + row * (ch + 10)
        b.append(sketch_rect(x, y, cw, ch, fill=TINT["white"]))
        b.append(badge(x + 8, y + 8, rid, RED, w=34, h=19))
        b.append(txt(x + 50, y + 22, name, 11.5, INK, bold=True))
        b.append(badge(x + cw - 66, y + 8, dim, ORANGE, w=58, h=19))
        b.append(txt(x + 8, y + 46, "图上：" + lure, 10.5, BLUE))
        b.append(txt(x + 8, y + 64, "实测：" + evid, 10.5, GREEN))
        b.append(txt(x + 8, y + 82, "守卫：" + guard, 10.5, MUTED))
    # 第 8 格：MLIR 裁决卡
    x = cx + 3 * (cw + 10)
    y = cy + (ch + 10)
    b.append(sketch_rect(x, y, cw, ch, fill=TINT["gray"]))
    b.append(txt(x + 8, y + 22, "MLIR stock 同款裁决", 11.5, INK, bold=True))
    b.append(txt(x + 8, y + 44, "copy / store / 恒等转置：都不删", 10.5,
                 MUTED))
    b.append(txt(x + 8, y + 62, "死 addf 删、store 留（一删一留）", 10.5,
                 MUTED))
    b.append(txt(x + 8, y + 80, "truncf+extf / reshape 链：不折叠", 10.5,
                 MUTED))

    b.append(txt(40, h - 22, "命题的机器可检形式：state_hash 相同 + 输出值"
                 "逐位相等 + 内存轨迹不同 →「图结构相同不代表内存语义相同」",
                 12, RED, bold=True))
    save("01-overview.svg", "".join(b))


# ============================================================
# 图 2：核心机制——两本账本怎么记账
# ============================================================

def fig2() -> None:
    w, h = 1180, 760
    b = [header(w, h, "核心机制：同一个图节点，两本账",
                "上：4-op 链在两个世界的记账流水（真实事件日志）｜ "
                "下：三明治改写的 2×2 账单（值等价 ≠ 账单等价）")]

    # ---- 顶部：4-op 链 + 两个世界的事件日志 ----
    b.append(panel_title(40, 96, "同一条链", BLUE))
    chain = ["arg\n(2,3)", "transpose\n(1,0)", "relu", "reshape\n(6,)"]
    x0, y0, bw, bh = 40, 110, 96, 52
    for i, name in enumerate(chain):
        x = x0 + i * (bw + 26)
        b.append(sketch_rect(x, y0, bw, bh, fill=TINT["blue"]))
        for j, line in enumerate(name.split("\n")):
            b.append(txt(x + bw / 2, y0 + 22 + j * 16, line, 11, INK,
                         anchor="middle", bold=(j == 0)))
        if i < len(chain) - 1:
            b.append(sketch_line(x + bw + 2, y0 + bh / 2,
                                 x + bw + 24, y0 + bh / 2, arrow=True))
    b.append(txt(x0 + 4 * (bw + 26) + 4, y0 + 22, "state_hash", 11, BLUE,
                 bold=True))
    b.append(txt(x0 + 4 * (bw + 26) + 4, y0 + 40, "a05676ce", 11, BLUE))
    b.append(txt(x0 + 4 * (bw + 26) + 4, y0 + 58, "（同一张图）", 10.5,
                 MUTED))

    # 视图世界日志
    lx, ly = 40, 200
    b.append(sketch_rect(lx, ly, 530, 150, fill=TINT["white"]))
    b.append(panel_title(lx + 16, ly + 24, "视图世界的内存账本", BLUE))
    view_log = [
        ("%2 transpose", "视图 buf-1  strides(3,1)→(1,3)", "0B"),
        ("%3 relu", "alloc buf0 + 读+写", "48B"),
        ("%4 reshape", "视图 buf0  (3,2)→(6,)", "0B"),
    ]
    for i, (op, act, by) in enumerate(view_log):
        yy = ly + 50 + i * 24
        b.append(txt(lx + 16, yy, op, 11, INK, bold=True))
        b.append(txt(lx + 130, yy, act, 11, INK))
        b.append(txt(lx + 400, yy, by, 11.5, BLUE if by == "0B" else INK,
                     bold=True))
    b.append(txt(lx + 16, ly + 132,
                 "traffic 48B ｜ 中间分配 1（只剩 relu 真搬字节）", 12,
                 BLUE, bold=True))

    # 物理世界日志
    lx2 = 610
    b.append(sketch_rect(lx2, ly, 530, 150, fill=TINT["white"]))
    b.append(panel_title(lx2 + 16, ly + 24, "物理世界的内存账本", RED))
    phys_log = [
        ("%2 transpose", "物化 alloc buf0 + 搬运", "48B"),
        ("%3 relu", "alloc buf1 + 读+写", "48B"),
        ("%4 reshape", "物化 alloc buf2 + 搬运", "48B"),
    ]
    for i, (op, act, by) in enumerate(phys_log):
        yy = ly + 50 + i * 24
        b.append(txt(lx2 + 16, yy, op, 11, INK, bold=True))
        b.append(txt(lx2 + 130, yy, act, 11, INK))
        b.append(txt(lx2 + 400, yy, by, 11.5, RED, bold=True))
    b.append(txt(lx2 + 16, ly + 132,
                 "traffic 144B ｜ 中间分配 3（每个 op 都真搬字节）", 12,
                 RED, bold=True))

    b.append(txt(590, ly + 75, "值：逐位相等", 12, GREEN, anchor="middle",
                 bold=True))
    b.append(txt(590, ly + 95, "3× 差距", 12, ORANGE, anchor="middle",
                 bold=True))

    # ---- 底部：三明治 2×2 ----
    y2 = 400
    b.append(panel_title(40, y2 + 4,
                         "三明治 T(relu(T(x))) → relu(x)：同一个「值等价」"
                         "改写，两世界账单不同", ORANGE))
    # 表格
    tx, ty, cw, ch = 60, y2 + 22, 260, 74
    heads = ["", "保留三明治", "相消（传播+合并）"]
    cells = [
        ["视图世界", "48B ｜ 输出 strides (1,2)", "48B ｜ 输出 strides (3,1)"],
        ["物理世界", "144B（3 次搬运）", "48B（省 96B = 2×转置）"],
    ]
    for j, hd in enumerate(heads):
        b.append(txt(tx + j * (cw + 12) + cw / 2, ty + 16, hd, 12, INK,
                     anchor="middle", bold=True))
    for i, row in enumerate(cells):
        y = ty + 28 + i * (ch + 12)
        b.append(sketch_rect(tx, y, cw, ch, fill=TINT["gray"]))
        b.append(txt(tx + cw / 2, y + ch / 2 + 4, row[0], 12.5, INK,
                     anchor="middle", bold=True))
        for j in range(2):
            x = tx + (j + 1) * (cw + 12)
            fill = TINT["blue"] if i == 0 else TINT["red"]
            b.append(sketch_rect(x, y, cw, ch, fill=fill))
            lines = row[j + 1].split("｜")
            for k, ln in enumerate(lines):
                b.append(txt(x + cw / 2, y + 28 + k * 18, ln.strip(), 11.5,
                             INK, anchor="middle", bold=(k == 0)))
    b.append(txt(60, ty + 28 + 2 * (ch + 12) + 4,
                 "值全部逐位相等；视图世界相消还把输出从非连续 (1,2) 变连续"
                 " (3,1) —— 下游零拷贝权利改变（第 9 周命题一回归）",
                 11.5, GREEN, bold=True))

    # 右下：账本字段
    b.append(sketch_rect(920, y2 + 22, 220, 190, fill=TINT["white"]))
    b.append(panel_title(936, y2 + 46, "内存账本记什么", RED))
    for i, (k, v) in enumerate([
            ("buffer", "字节住在哪块"),
            ("strides/offset", "下标怎么映射"),
            ("traffic", "读+写多少字节"),
            ("写集合", "谁写了谁的缓冲"),
            ("副作用", "外部世界看到啥"),
            ("布局契约", "连续 / 别名要求")]):
        b.append(txt(936, y2 + 72 + i * 24, k, 11.5, RED, bold=True))
        b.append(txt(1030, y2 + 72 + i * 24, v, 11.5, INK))

    b.append(txt(40, h - 18, "结构账本一个字段都不记这些 —— 这正是「图结构相同"
                 "不代表内存语义相同」的机制根源", 12, RED, bold=True))
    save("02-mechanism.svg", "".join(b))


# ============================================================
# 图 3：反例集对照
# ============================================================

def fig3() -> None:
    w, h = 1180, 980
    b = [header(w, h, "反例集：图结构说能删，内存语义说不许动",
                "7 条反例 ×「图结构视角 → 内存/数值语义 → 实测证据」"
                " ｜ 全部证据为 2026-11-12 本机真实运行")]

    cards = [
        ("R1", "Cast f32→f16→f32 往返", "精度",
         "类型一进一出「对消」，shape 不变",
         "f16 只有 10 位尾数（f32 有 23 位），往返丢位；"
         "单层 cast 还把 buffer 从 24B 缩到 12B",
         "6/6 元素变值；守卫版只放行 src==dst",
         "MLIR：truncf+extf 不折叠"),
        ("R2", "Reshape(Reshape(x,t),t)", "形状",
         "外层目标 == 当前 shape，看似透明",
         "Reshape(Reshape(x,t),t) = Reshape(x,t) ≠ x"
         "（除非 t == shape(x)）",
         "透传错版：return (2,3)→(6,)；下游 rank-1 转置被 [V1] 拦截",
         "MLIR：reshape 链 stock 不合并"),
        ("R3", "copy(x) 消除", "别名",
         "copy 是值上的恒等映射",
         "copy 划定缓冲边界；消除后 in-place 后端直接写源缓冲",
         "写集合 buf1→buf0；return 的 x 变成 relu(x)；纯函数 eval 看不见",
         "MLIR：memref.copy 不删（canonicalize/cse）"),
        ("R4", "无使用者的 store", "副作用",
         "没有任何使用者 —— DCE 的标准猎物",
         "副作用对外部世界可观察（外部全局 G）",
         "naive DCE 删掉后 G 变空；guarded DCE 保留",
         "MLIR：store 留 / 死 addf 删（一删一留）"),
        ("R5", "恒等排列的物理转置", "布局",
         "perm=(0,1) 值上什么都不做",
         "它是 strided→连续 的物化点，把布局转换摊销到所有消费者",
         "双消费者下消除：traffic 48B→96B 翻倍",
         "MLIR：linalg.transpose 恒等排列不删"),
        ("R6", "多使用者传播", "复制",
         "T(relu(x))，和 Day 68 传播模式同构",
         "relu 另有使用者时，传播复制逐元素工作、转置一个没少",
         "op 2→3；元素计算 6→12；值仍等价（错在收益）",
         "守卫：C2 唯一使用者门"),
        ("R7", "T(reduce_sum(x)) 传播", "轴语义",
         "还是「transpose 挂在算子上面」",
         "reduce 带轴语义，axis 必须跟着换：新 axis = inv_perm[旧 axis]",
         "照抄传播 shape (3,1)→(1,2)；axis 换对才逐位相等",
         "守卫：C1 白名单只放逐位置不变算子"),
    ]

    y = 96
    ch = 112
    for rid, name, dim, lure, why, evid, mlir in cards:
        b.append(sketch_rect(40, y, 1100, ch - 10, fill=TINT["white"]))
        b.append(badge(52, y + 10, rid, RED, w=36, h=20))
        b.append(txt(98, y + 25, name, 13, INK, bold=True))
        b.append(badge(300, y + 10, dim, ORANGE, w=62, h=20))
        # 三栏
        b.append(txt(390, y + 24, "图结构视角（诱人处）", 10, BLUE, bold=True))
        for k, ln in enumerate(wrap_cn(lure, 22)):
            b.append(txt(390, y + 44 + k * 16, ln, 10.5, BLUE))
        b.append(txt(640, y + 24, "内存/数值语义（拒绝理由）", 10, RED,
                     bold=True))
        for k, ln in enumerate(wrap_cn(why, 24)):
            b.append(txt(640, y + 44 + k * 16, ln, 10.5, RED))
        b.append(txt(940, y + 24, "实测证据", 10, GREEN, bold=True))
        for k, ln in enumerate(wrap_cn(evid, 22)):
            b.append(txt(940, y + 44 + k * 16, ln, 10.5, GREEN))
        b.append(txt(940, y + 44 + len(wrap_cn(evid, 22)) * 16 + 4, mlir,
                     9.5, MUTED))
        y += ch

    b.append(txt(40, h - 20, "每条反例的完整复现命令与输出："
                 "code/counterexample_lab.py（39 项检查）｜"
                 "code/counterexamples.md（反例集全文）", 11.5, MUTED))
    save("03-counterexamples.svg", "".join(b))


def wrap_cn(s: str, width: int) -> list[str]:
    """按显示宽度近似折行（中文按 2 个半角计）。"""
    out, cur, cw = [], "", 0
    for chx in s:
        wch = 2 if ord(chx) > 127 else 1
        if cw + wch > width:
            out.append(cur)
            cur, cw = chx, wch
        else:
            cur += chx
            cw += wch
    if cur:
        out.append(cur)
    return out


# ============================================================
# 图 4：本周测试汇总
# ============================================================

def fig4() -> None:
    w, h = 1180, 700
    b = [header(w, h, "本周全部测试：7 套 286 个测试点一键复跑",
                "Day 64–69 六套 + 今天复盘一套 ｜ bash run_week_tests.sh"
                " ｜ 2026-11-12 本机真实执行")]

    # ---- 左：结果表 ----
    b.append(panel_title(40, 96, "逐日结果（退出码全 0）", BLUE))
    rows = [("064", "test_transpose.py", 63), ("065", "test_transpose_elim.py", 33),
            ("066", "test_reshape_merge.py", 30), ("067", "test_cast_elim.py", 39),
            ("068", "test_layout_prop.py", 37), ("069", "test_combo_lab.py", 51),
            ("070", "test_counterexamples.py", 33)]
    ty = 112
    b.append(txt(40, ty, "Day", 11, MUTED, bold=True))
    b.append(txt(90, ty, "测试文件", 11, MUTED, bold=True))
    b.append(txt(330, ty, "结果", 11, MUTED, bold=True))
    b.append(sketch_line(40, ty + 8, 420, ty + 8, sw=1.2, opacity=0.5))
    for i, (d, f, n) in enumerate(rows):
        yy = ty + 30 + i * 26
        today = d == "070"
        if today:
            b.append(sketch_rect(36, yy - 15, 390, 22, fill=TINT["orange"],
                                 sw=1.5, nseg=4))
        b.append(txt(40, yy, d, 11.5, ORANGE if today else INK, bold=True))
        b.append(txt(90, yy, f, 11.5, INK))
        b.append(txt(330, yy, f"{n} PASS", 11.5, GREEN, bold=True))
    b.append(sketch_line(40, ty + 30 + 7 * 26 - 8, 420,
                         ty + 30 + 7 * 26 - 8, sw=1.2, opacity=0.5))
    b.append(txt(90, ty + 30 + 7 * 26 + 10, "合计", 12, INK, bold=True))
    b.append(txt(330, ty + 30 + 7 * 26 + 10, "286 PASS / 0 FAIL", 12, GREEN,
                 bold=True))
    b.append(txt(40, ty + 30 + 7 * 26 + 34,
                 "第 10 周测试状态：全部通过 ✓（日志：outputs/week_tests/）",
                 11.5, GREEN, bold=True))

    # ---- 右：条形图 ----
    b.append(panel_title(480, 96, "各套测试点数量", GREEN))
    gx, gy, gw, gh = 480, 120, 340, 220
    maxv = 70
    for i, (d, f, n) in enumerate(rows):
        yy = gy + i * 28
        bwv = gw * n / maxv
        col = ORANGE if d == "070" else GREEN
        b.append(sketch_rect(gx + 44, yy, bwv, 18, fill=TINT["green"],
                             stroke=col, sw=1.6, nseg=4))
        b.append(txt(gx + 38, yy + 14, d, 10.5, MUTED, anchor="end"))
        b.append(txt(gx + 48 + bwv, yy + 14, str(n), 10.5, col, bold=True))
    b.append(txt(gx + 44, gy + 7 * 28 + 6,
                 "今天的 33 个测试点 = A 内存账本模型 + B 反例回归 + "
                 "C 守卫 + D DCE", 10.5, MUTED))

    # ---- 右下：今天测试的四段 ----
    b.append(sketch_rect(480, 380, 340, 130, fill=TINT["white"]))
    b.append(panel_title(496, 404, "test_counterexamples.py 七段", GREEN))
    segs = [("A", "内存账本模型（6）"), ("B", "反例回归 R1–R7（7）"),
            ("C", "守卫双门测试（8）"), ("D", "DCE 副作用（2）"),
            ("E", "结构哈希规范化（3）"), ("F", "随机性质 40+20 组（2）"),
            ("G", "MLIR 探针（5）")]
    for i, (s, d) in enumerate(segs):
        yy = 424 + i * 18 if i < 4 else 424 + (i - 4) * 18
        xx = 496 if i < 4 else 660
        b.append(txt(xx, yy + 14, s, 10.5, GREEN, bold=True))
        b.append(txt(xx + 16, yy + 14, d, 10.5, INK))

    # ---- 底部：带走的三句话 ----
    b.append(sketch_rect(40, 530, 1100, 140, fill=TINT["orange"]))
    b.append(txt(60, 556, "带走的三句话", 13, ORANGE, bold=True))
    lines = [
        ("1", "结构账本（state_hash）只回答「值怎么算」；内存账本"
              "（buffer/strides/traffic）回答「字节怎么搬」",
         "—— 同一张图在视图世界和物理世界是两种程序（48B vs 144B）。"),
        ("2", "每条消除/传播规则的守卫，都是某个反例的墓碑",
         "—— 守卫不是官僚作风，是语义边界。"),
        ("3", "值等价是改写的必要条件，不是充分条件：",
         "别名、布局、副作用、精度、轴语义都住在值世界看不见的地方。"),
    ]
    yy = 578
    for num, l1, l2 in lines:
        b.append(txt(60, yy, num, 11, ORANGE, bold=True))
        b.append(txt(74, yy, l1, 11, INK))
        b.append(txt(74, yy + 18, l2, 11, INK))
        yy += 40

    b.append(txt(40, h - 18, "一页复盘：code/review-onepage.md ｜ "
                 "反例集全文：code/counterexamples.md", 11.5, MUTED))
    save("04-week-tests.svg", "".join(b))


def main() -> int:
    fig1()
    fig2()
    fig3()
    fig4()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
