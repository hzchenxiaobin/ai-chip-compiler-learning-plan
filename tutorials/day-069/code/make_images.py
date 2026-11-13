#!/usr/bin/env python3
"""make_images.py —— 第 69 天（图优化组合测试）教程的四张手绘 sketch 风 SVG 信息图。

风格约定（与第 8/9/10 周各天一致，Excalidraw-like）：
  - 背景 #fdfaf2（米白），盒子白底 + 深灰 #6b6357 手绘描边
  - 强调色不超过 4 种柔和色：蓝 #4a7fa5 / 橙 #a8772e / 绿 #5a8a5a / 红 #b0605a
  - 线条带轻微抖动（L 段折线），圆头笔触，线宽 2 左右
  - 手写感字体栈：Comic Sans MS / Comic Neue / Kaiti SC / 楷体 / cursive
  - 只用矩形、格子、箭头、圆角框等简单几何形状

图中全部数字来自 2026-11-12 的真实运行（code/outputs/）：
  combo_lab 60/60；test_combo_lab 51/51；
  混合链 10 op → 4 op（5 轮 fixpoint，稳定三条件全过）；
  竞争对：先传播 5 op / 先融合 4 op（各剩 1 个转置，哈希不同，数值都对）；
  顺序表：推荐/融合优先 hash c784b0c7（2 计算 op）、传播优先/倒序
  c404512b（3 计算 op），全部 5 轮；合流对 cast×融合 2 vs 2 轮同终点；
  规则环：6 排列起点全部 oscillation（检出 2~3 轮，轨迹为 2-环）；
  undo 对 2 轮检出；哈希陷阱 40 轮 max_rounds；
  驯服：逆序轨迹 [3,2,1,0]，步数=初始逆序，6 起点 → 1 规范形；
  压力 200/200：轮次 0/2/14，计算 op 1357→973（-28.3%），
  转置 188→126，cast 172→0，reshape 380→240，fused 生成 10；
  MLIR：canonicalize/cse 幂等；canon→cse 1 addf / cse→canon 2 addf /
  补趟 1；tensor.cast 删 0；canon→cse 1 generic / cse→canon 2 generic。

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

rng = random.Random(69)


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


# ============================================================
# 图 1：全貌
# ============================================================

def fig1() -> None:
    w, h = 1150, 800
    b = [header(w, h, "第 69 天全貌：图优化组合测试",
                "第 10 周「Layout 与冗余算子消除」Day 6/6 —— 零件全部到齐，今天只研究它们住进同一根管道之后"
                " ｜ 数字均为 2026-11-12 本机实测")]

    # ---- 顶部：本周时间线 ----
    b.append(txt(40, 92, "本周链路（第 10 周）", 13, MUTED, bold=True))
    days = [("D64", "转置语义"), ("D65", "转置消除"), ("D66", "Reshape 合并"),
            ("D67", "Cast 消除"), ("D68", "Layout 传播"),
            ("D69", "组合测试"), ("D70", "复盘")]
    bx, by, bw, bh, gap = 40, 102, 140, 46, 10
    for i, (d, t) in enumerate(days):
        x = bx + i * (bw + gap)
        today = d == "D69"
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
                 "前五天：每条 Pattern 自己的单测里都收敛", 11.5, MUTED))
    b.append(txt(bx + 5 * (bw + gap) + 2, by - 8,
                 "今天：组合之后的三类新行为", 11.5, ORANGE, bold=True))

    # ---- 中排：零件库 / 组合管道 / 三个研究对象 ----
    y0 = 196
    b.append(sketch_rect(40, y0, 350, 250, fill=TINT["white"]))
    b.append(panel_title(56, y0 + 24, "零件库（今天一字不改，只取用）", BLUE))
    parts = [
        ("merge_transposes", "D65", "消除类"),
        ("merge_reshapes", "D66", "消除类"),
        ("transparent_reshape", "D66", "消除类"),
        ("eliminate_noop_cast", "D67", "消除类"),
        ("fold_transpose_const", "D68", "消除类"),
        ("fuse_add_relu", "D51", "融合"),
        ("push_transpose", "D68", "传播"),
    ]
    for i, (p, d, tier) in enumerate(parts):
        yy = y0 + 44 + i * 27
        col = {"消除类": GREEN, "融合": ORANGE,
               "传播": BLUE}[tier]
        b.append(badge(56, yy - 14, d, col, w=44))
        b.append(txt(112, yy, p, 11.5, INK))
        b.append(txt(300, yy, tier, 11.5, col))
    b.append(txt(56, y0 + 238, "7 条全部通过「装进来没坏」最小用例 + 数值抽查",
                 10.5, MUTED))

    b.append(sketch_rect(420, y0, 300, 250, fill=TINT["white"]))
    b.append(panel_title(436, y0 + 24, "今天的组合管道", ORANGE))
    # PassManager 循环
    b.append(sketch_rect(446, y0 + 44, 248, 118, fill=TINT["orange"]))
    b.append(txt(570, y0 + 62, "run_passes：循环到不动点", 12, ORANGE,
                 anchor="middle", bold=True))
    b.append(txt(570, y0 + 82, "每轮把整个 Pattern 集试一遍", 10.5, INK,
                 anchor="middle"))
    b.append(txt(570, y0 + 100, "（被挡住的下一轮还有机会 → 合流对自动追平）",
                 10, INK, anchor="middle"))
    b.append(txt(570, y0 + 122, "每轮触发后算一次规范化状态哈希", 10.5, INK,
                 anchor="middle"))
    b.append(txt(570, y0 + 140, "重复 = 环 → oscillation", 10.5, RED,
                 anchor="middle", bold=True))
    b.append(txt(570, y0 + 154, "没人能触发 → fixpoint", 10.5, GREEN,
                 anchor="middle", bold=True))
    b.append(sketch_line(430, y0 + 175, 430, y0 + 44, stroke=ORANGE,
                         sw=1.8, arrow=True, dashed=True))
    b.append(txt(436, y0 + 192, "next round", 10, MUTED))
    b.append(txt(436, y0 + 218,
                 "max_rounds=40 只是兜底：真实差距是 2 轮 vs 40 轮（实测）",
                 10.5, RED))

    b.append(sketch_rect(750, y0, 360, 250, fill=TINT["white"]))
    b.append(panel_title(766, y0 + 24, "三个研究对象（今天的产出对应）", RED))
    rows = [
        ("① 不动点", "10-op 混合链 5 轮到稳定 IR",
         "稳定三条件：幂等 + 哈希不变 + 数值相等"),
        ("② 意外无限变换", "规则环 / undo 对 / 哈希陷阱",
         "驯服：规范序 + 总逆序每步恰降 1（6 起点 1 规范形）"),
        ("③ 优化顺序", "合流对（cast×融合）vs 竞争对（传播×融合）",
         "先传播 5 op / 先融合 4 op，两个不动点数值都对"),
    ]
    for i, (t, d, e) in enumerate(rows):
        yy = y0 + 48 + i * 66
        b.append(badge(766, yy - 14, t, RED, w=110))
        b.append(txt(766, yy + 26, "· " + d, 11, INK))
        b.append(txt(766, yy + 44, "· " + e, 10.5, MUTED))

    # ---- 下排：MLIR 实测 / mini 验收 ----
    y1 = 478
    b.append(sketch_rect(40, y1, 530, 216, fill=TINT["white"]))
    b.append(panel_title(56, y1 + 24, "MLIR 实测（Ubuntu LLVM 18.1.8）", BLUE))
    facts = [
        ("canonicalize / cse 跑两遍", "各自幂等（x2 == x1）"),
        ("canon → cse", "1 个 arith.addf"),
        ("cse → canon", "2 个 addf（顺序敏感！）"),
        ("cse → canon → cse", "1 个（补一趟追平：差的是调度）"),
        ("canon 删恒等 tensor.cast", "canon→cse 1 个 generic / 反序 2 个"),
    ]
    for i, (c, d) in enumerate(facts):
        yy = y1 + 50 + i * 30
        b.append(txt(60, yy, "· " + c, 11, BLUE))
        b.append(txt(300, yy, "→ " + d, 11, INK))
    b.append(txt(56, y1 + 202,
                 "mlir-opt 的 pass 一次性按序执行、不回头——顺序是真实决策",
                 11, ORANGE, bold=True))

    b.append(sketch_rect(600, y1, 510, 216, fill=TINT["white"]))
    b.append(panel_title(616, y1 + 24, "mini 侧验收汇总", GREEN))
    acc = [
        ("combo_lab.py", "60 / 60 通过"),
        ("test_combo_lab.py", "51 / 51 通过"),
        ("混合链", "10 op → 4 op，5 轮，稳定三条件全过"),
        ("压力对拍 200 组", "数值/fixpoint/幂等/op 不增 200/200"),
        ("计算 op 总数", "1357 → 973（消掉 28.3%）"),
    ]
    for i, (t, d) in enumerate(acc):
        yy = y1 + 52 + i * 30
        b.append(txt(620, yy, "· " + t, 11.5, INK))
        b.append(txt(800, yy, d, 11.5, GREEN, bold=True))

    # ---- 底部：明天 ----
    y2 = 716
    b.append(sketch_rect(40, y2, 1070, 52, fill=TINT["gray"]))
    b.append(txt(60, y2 + 32, "明天（D70）第 10 周复盘：", 13, INK, bold=True))
    b.append(txt(290, y2 + 32,
                 "「图结构相同不代表内存语义相同」——整理至少 5 个"
                 "「看似能消除但实际不能消除」的反例；"
                 "今天的守卫、竞争对和两个真实 bug 都是复盘素材",
                 12, MUTED))
    save("01-overview.svg", "".join(b))


# ============================================================
# 图 2：机制（状态机 + 三类现场 + 驯服）
# ============================================================

def fig2() -> None:
    w, h = 1150, 820
    b = [header(w, h, "组合管道机制：IR 状态机、环检测与单调配度",
                "左：混合链的 5 步转移与稳定三条件 ｜ 右上：三类无限变换现场"
                " ｜ 右下：驯服机制（规范序 + 总逆序恰降 1）")]

    # ---- 左：状态机 ----
    b.append(sketch_rect(40, 88, 540, 700, fill=TINT["white"]))
    b.append(panel_title(56, 112, "① 组合优化 = IR 状态机", BLUE))

    states = [
        ("初始态：10 op", "T∘T / cast / add+relu / T / R∘R", None),
        ("① merge_t", "r=恒等 → 透传，2 个 T 消失", GREEN),
        ("② merge_r", "两层 reshape → 1 层", GREEN),
        ("③ transparent_r", "目标=输入 shape → 透传", GREEN),
        ("④ cast", "f32→f32 无操作 → 透传", GREEN),
        ("⑤ fuse", "add+relu → fused_add_relu", ORANGE),
        ("不动点：4 op", "transpose(fused(x,y))", None),
    ]
    sx, sy, sw_, sh_ = 70, 136, 200, 52
    for i, (t, d, col) in enumerate(states):
        x = sx + (i % 2) * 260
        y = sy + i * 62
        fix = i == len(states) - 1
        fillc = TINT["green"] if fix else TINT["gray"]
        b.append(sketch_rect(x, y, sw_, sh_, fill=fillc,
                             stroke=GREEN if fix else STROKE,
                             sw=2.6 if fix else 2.0))
        b.append(txt(x + sw_ / 2, y + 21, t, 12,
                     GREEN if fix else INK, anchor="middle", bold=True))
        b.append(txt(x + sw_ / 2, y + 40, d, 9.5, MUTED, anchor="middle"))
        if i < len(states) - 1:
            nx = sx + ((i + 1) % 2) * 260
            ny = sy + (i + 1) * 62
            if i % 2 == 0:
                b.append(sketch_path([(x + sw_ + 2, y + sh_ / 2),
                                      (nx - 2, ny + sh_ / 2)],
                                     arrow=True, sw=1.8))
            else:
                b.append(sketch_path([(x + sw_ / 2, y + sh_ + 2),
                                      (nx + sw_ / 2, ny - 2)],
                                     arrow=True, sw=1.8))
    b.append(txt(70, sy + 7 * 62 - 6, "每轮恰好触发一条 Pattern；5 轮后无规则可触发",
                 10.5, MUTED))
    b.append(txt(70, sy + 7 * 62 + 12,
                 "（另一条路：传播先拿窗口 → 5 op 的不动点，见图 3 左）", 10.5,
                 RED))

    # 稳定三条件
    b.append(sketch_rect(70, sy + 7 * 62 + 24, 470, 96, fill=TINT["blue"]))
    b.append(txt(86, sy + 7 * 62 + 46, "稳定三条件（实测全过）", 12, BLUE,
                 bold=True))
    conds = [
        ("S1 幂等", "二次运行 0 轮"),
        ("S2 结构稳定", "规范化状态哈希不变"),
        ("S3 数值稳定", "3 组随机输入逐位相等"),
    ]
    for i, (t, d) in enumerate(conds):
        yy = sy + 7 * 62 + 64 + i * 22
        b.append(txt(86, yy, "☑", 12, GREEN, bold=True))
        b.append(txt(108, yy, t, 11, INK, bold=True))
        b.append(txt(206, yy, d, 10.5, INK))
    b.append(txt(70, sy + 7 * 62 + 136,
                 "「跑完了」≠「跑对了」：三条缺一不可", 11, RED, bold=True))

    # ---- 右上：三类现场 ----
    b.append(sketch_rect(610, 88, 500, 320, fill=TINT["white"]))
    b.append(panel_title(626, 112, "② 三类意外无限变换（全部实测）", RED))

    # 现场一：规则环
    b.append(sketch_rect(626, 130, 468, 86, fill=TINT["red"]))
    b.append(txt(640, 150, "现场一 规则环：6 条双向交换规则", 11.5, RED,
                 bold=True))
    b.append(txt(640, 168, "{T, relu, floor} 两两可交换；每对配双向交换 →",
                 10.5, INK))
    b.append(txt(640, 184, "6 个排列起点全部 oscillation（检出 2~3 轮）",
                 10.5, INK))
    b.append(txt(640, 204, "每条规则单独存在都能停——错在集合，不在单条", 10.5,
                 RED, bold=True))

    # 现场二：undo 对
    b.append(sketch_rect(626, 226, 468, 74, fill=TINT["red"]))
    b.append(txt(640, 246, "现场二 undo 对：fuse × unfuse 同场", 11.5, RED,
                 bold=True))
    b.append(txt(640, 264, "add→relu → fused → add→relu 回到起点：", 10.5,
                 INK))
    b.append(txt(640, 282, "2 轮检出（规范化哈希看见「回去了」）", 10.5, INK))

    # 现场三：哈希陷阱
    b.append(sketch_rect(626, 310, 468, 86, fill=TINT["orange"]))
    b.append(txt(640, 330, "现场三 哈希陷阱：原始 SSA 名字哈希", 11.5,
                 ORANGE, bold=True))
    b.append(txt(640, 348, "同一振荡，名字每轮递增 → 环永远测不出：", 10.5,
                 INK))
    b.append(txt(640, 366, "40 轮 max_rounds 兜底（真实差距：2 vs 40）",
                 10.5, INK))
    b.append(txt(640, 386, "修复：op 按 topo 位置重命名 #k 再散列", 10.5,
                 GREEN, bold=True))

    # ---- 右下：驯服 ----
    b.append(sketch_rect(610, 428, 500, 360, fill=TINT["white"]))
    b.append(panel_title(626, 452, "③ 驯服：单调配度（良基测度）", GREEN))

    b.append(txt(640, 478, "规范序：transpose(0) < relu(1) < floor(2)",
                 11.5, GREEN, bold=True))
    b.append(txt(640, 496, "交换规则只在「逆序」时触发 → 冒泡排序", 11, INK))

    # 逆序数阶梯（起点 F→R→T，总逆序 3）
    ladder = [
        ("3", "起点 floor→relu→transpose", 520),
        ("2", "换 (F,R) → (R,F)：总逆序 3→2", 556),
        ("1", "换 (F,T) → (T,F)：总逆序 2→1", 592),
        ("0", "规范形 transpose→relu→floor", 628),
    ]
    lx = 644
    prev_y = None
    for lab, note, y in ladder:
        b.append(sketch_rect(lx, y - 16, 36, 26, fill=TINT["green"], sw=1.8,
                             nseg=3))
        b.append(txt(lx + 18, y + 2, lab, 12, GREEN, anchor="middle",
                     bold=True))
        if prev_y is not None:
            b.append(sketch_line(lx + 18, prev_y + 12, lx + 18, y - 18,
                                 arrow=True, stroke=GREEN, sw=2.0))
        prev_y = y
        b.append(txt(696, y + 2, note, 10.5, INK))
    b.append(txt(640, 664, "总逆序数每步恰降 1（实测轨迹 [3,2,1,0]）；步数 = 初始逆序",
                 10.5, GREEN, bold=True))
    b.append(txt(640, 686, "注意：测度必须数「总逆序」（i<j 且 rank(i)>rank(j)）——", 10.5,
                 RED))
    b.append(txt(640, 704, "「相邻逆序对数」在交换后可能不降（开发时实测踩坑）", 10.5,
                 RED))
    b.append(txt(640, 726, "交换一对逆序的相邻元素，恰使总逆序减 1 —— 冒泡排序经典结论",
                 10.5, MUTED))
    b.append(txt(640, 756, "6 个起点 → 同一规范形（哈希去重后只剩 1 个，实测）",
                 11, GREEN, bold=True))
    save("02-mechanism.svg", "".join(b))


# ============================================================
# 图 3：竞争对 + 规则环 + 驯服（实例对照）
# ============================================================

def fig3() -> None:
    w, h = 1150, 770
    b = [header(w, h, "顺序与振荡实测：两个不动点、规则环轨迹与驯服",
                "左：竞争对（传播×融合争 relu 窗口）｜ 中：规则环的实测轨迹"
                " ｜ 右：驯服后的单调轨迹（数字全部来自 outputs/）")]

    # ---- 左：竞争对 ----
    b.append(sketch_rect(40, 88, 500, 640, fill=TINT["white"]))
    b.append(panel_title(56, 112, "① 竞争对：z = T(relu(add(x,y)))", RED))
    b.append(txt(56, 134, "窗口是那个 relu——谁先用掉它，谁关掉另一条路：",
                 11, INK))

    b.append(badge(56, 148, "顺序A：传播在前 → 1 轮 fixpoint", BLUE, w=232))
    b.append(sketch_rect(56, 178, 220, 118, fill=TINT["gray"], sw=2.0))
    ir_a = ["%1 = arg        ; (2,3)", "%2 = arg        ; (2,3)",
            "%3 = add  %1, %2", "%6 = transpose %3", "%7 = relu  %6",
            "return %7"]
    for i, ln in enumerate(ir_a):
        b.append(txt(70, 200 + i * 17, ln, 10.5, INK))
    b.append(txt(292, 200, "总 op 5（含 2 arg）", 12, BLUE, bold=True))
    b.append(txt(292, 220, "relu(T(add(x,y)))", 10.5, MUTED))
    b.append(txt(292, 240, "转置卡在 add 上（二元，", 10.5, RED))
    b.append(txt(292, 256, "白名单过不去）", 10.5, RED))

    b.append(badge(56, 312, "顺序B：融合在前 → 1 轮 fixpoint", ORANGE, w=232))
    b.append(sketch_rect(56, 342, 220, 102, fill=TINT["gray"], sw=2.0))
    ir_b = ["%1 = arg        ; (2,3)", "%2 = arg        ; (2,3)",
            "%6 = fused_add_relu %1, %2", "%5 = transpose %6",
            "return %5"]
    for i, ln in enumerate(ir_b):
        b.append(txt(70, 364 + i * 17, ln, 10.5, INK))
    b.append(txt(292, 364, "总 op 4（含 2 arg）", 12, ORANGE, bold=True))
    b.append(txt(292, 384, "T(fused(x,y))", 10.5, MUTED))
    b.append(txt(292, 404, "转置卡在 fused 上（白名单", 10.5, RED))
    b.append(txt(292, 420, "不认融合算子）", 10.5, RED))

    b.append(sketch_rect(56, 458, 470, 78, fill=TINT["red"]))
    b.append(txt(70, 480, "两个不动点：哈希不同、数值都对、各剩 1 个转置", 11.5,
                 RED, bold=True))
    b.append(txt(70, 500, "· 传播用掉窗口：T 穿过 relu，融合的匹配（relu 的输入", 10.5,
                 INK))
    b.append(txt(70, 516, "  是 add）从此断了", 10.5, INK))
    b.append(txt(70, 532, "· 融合用掉窗口：relu 变成 fused，传播白名单认不出", 10.5,
                 INK))

    b.append(txt(56, 568, "混合链顺序表（同一条 10-op 链，4 种顺序，全部 5 轮）：",
                 11, INK))
    tbl = [("推荐(消除→融合→传播)", "2 计算 op", "hash c784b0c7"),
           ("传播优先", "3 计算 op", "hash c404512b"),
           ("融合优先", "2 计算 op", "hash c784b0c7"),
           ("倒序", "3 计算 op", "hash c404512b")]
    for i, (o, ops, hh) in enumerate(tbl):
        yy = 584 + i * 24
        b.append(txt(66, yy, o, 10.5, INK))
        b.append(txt(300, yy, ops, 10.5, ORANGE, bold=True))
        b.append(txt(400, yy, hh, 10.5, MUTED))
    b.append(txt(56, 690,
                 "推荐把融合放传播前：4 op < 5 op；但三明治相消（D68）只有传统能做——",
                 10, MUTED))
    b.append(txt(56, 706, "竞争对无全局最优，量化留给第 11 周 Cost Model",
                 10, MUTED))

    # ---- 中：规则环 ----
    b.append(sketch_rect(570, 88, 280, 640, fill=TINT["white"]))
    b.append(panel_title(586, 112, "② 规则环实测", RED))
    b.append(txt(586, 134, "6 条双向交换规则（优先级=列表序，", 10.5, INK))
    b.append(txt(586, 150, "first-match-wins）", 10.5, INK))

    # 2-cycle: T,R,F <-> R,T,F
    b.append(sketch_rect(636, 170, 150, 40, fill=TINT["red"], sw=2.2))
    b.append(txt(711, 190, "T → R → F", 12, RED, anchor="middle", bold=True))
    b.append(txt(711, 204, "轮 0", 9.5, MUTED, anchor="middle"))
    b.append(sketch_rect(636, 250, 150, 40, fill=TINT["red"], sw=2.2))
    b.append(txt(711, 270, "R → T → F", 12, RED, anchor="middle", bold=True))
    b.append(txt(711, 284, "轮 1", 9.5, MUTED, anchor="middle"))
    b.append(sketch_path([(700, 212), (700, 248)], arrow=True, stroke=RED,
                         sw=2.0))
    b.append(sketch_path([(722, 248), (722, 212)], arrow=True, stroke=RED,
                         sw=2.0))
    b.append(txt(586, 316, "轮 2 = 轮 0：状态哈希重复 → oscillation", 10.5,
                 RED, bold=True))

    b.append(txt(586, 348, "6 个起点全部 oscillation：", 10.5, INK, bold=True))
    starts = [("T→R→F", "2"), ("T→F→R", "3"), ("R→T→F", "2"),
              ("R→F→T", "3"), ("F→T→R", "2"), ("F→R→T", "2")]
    for i, (s, r) in enumerate(starts):
        yy = 366 + i * 22
        b.append(txt(600, yy, s, 10.5, INK))
        b.append(txt(680, yy, f"检出 {r} 轮", 10.5, RED))
    b.append(txt(586, 502,
                 "状态空间只有 6 个排列；每步必有规则可触发", 10, MUTED))
    b.append(txt(586, 518, "（相邻对总能换向）→ 抽屉原理保证必环", 10, MUTED))
    b.append(txt(586, 546, "每条规则语义都对：振荡中数值", 10.5, GREEN,
                 bold=True))
    b.append(txt(586, 562, "始终逐位相等（改写没错，错在不停）", 10.5, GREEN))

    b.append(sketch_rect(586, 586, 250, 128, fill=TINT["orange"]))
    b.append(txt(600, 608, "undo 对 & 哈希陷阱（实测）", 11, ORANGE,
                 bold=True))
    b.append(txt(600, 630, "fuse/unfuse：2 轮检出环", 10.5, INK))
    b.append(txt(600, 650, "原始名哈希：40 轮 max_rounds", 10.5, INK))
    b.append(txt(600, 672, "规范化哈希：2 轮即检出", 10.5, GREEN, bold=True))
    b.append(txt(600, 694, "差距 2 vs 40 = 生产里的超时与死循环", 10, RED))

    # ---- 右：驯服 ----
    b.append(sketch_rect(880, 88, 230, 640, fill=TINT["white"]))
    b.append(panel_title(896, 112, "③ 驯服实测", GREEN))
    b.append(txt(896, 134, "规范序 T < R < F，", 10.5, GREEN, bold=True))
    b.append(txt(896, 150, "只在逆序时交换", 10.5, GREEN, bold=True))

    lad = [("起点 F→R→T", "总逆序 3", TINT["red"], RED),
           ("换 (F,R) → (R,F)", "逆序 3 → 2", TINT["gray"], INK),
           ("换 (F,T) → (T,F)", "逆序 2 → 1", TINT["gray"], INK),
           ("换 (R,T) → (T,R)", "逆序 1 → 0", TINT["gray"], INK),
           ("规范形 T→R→F", "逆序 0（终点）", TINT["green"], GREEN)]
    for i, (t, d, f, c) in enumerate(lad):
        yy = 172 + i * 76
        x = 896 + i * 8
        b.append(sketch_rect(x, yy, 180, 56, fill=f, sw=2.0,
                             stroke=GREEN if i == 4 else STROKE))
        b.append(txt(x + 90, yy + 23, t, 10.5, c, anchor="middle", bold=True))
        b.append(txt(x + 90, yy + 42, d, 10, c, anchor="middle"))
        if i < 4:
            b.append(sketch_line(x + 90, yy + 58, x + 98, yy + 74,
                                 arrow=True, stroke=GREEN, sw=1.8))
    b.append(txt(896, 580, "6 个起点全部到达同一规范形：", 10.5, INK))
    b.append(txt(896, 598, "哈希去重后只剩 1 个（实测）", 10.5, INK))
    b.append(txt(896, 628, "步数 = 初始总逆序（0/1/1/2/2/3）", 10.5, GREEN,
                 bold=True))
    b.append(txt(896, 658, "「无限交换」→「冒泡排序」：", 10, MUTED))
    b.append(txt(896, 674, "给每条规则一个必须下降的量", 10, MUTED))
    save("03-order-oscillation.svg", "".join(b))


# ============================================================
# 图 4：结果汇总（压力对拍 + MLIR 探针 + Pass 顺序说明）
# ============================================================

def fig4() -> None:
    w, h = 1150, 800
    b = [header(w, h, "组合测试结果：压力对拍、MLIR 探针与 Pass 顺序说明",
                "上：200 组随机混合图的真实统计 ｜ 左下：4 个 MLIR 探针"
                " ｜ 右下：今日产出的 Pass 顺序说明（推荐顺序 + 两条边界）")]

    # ---- 上：压力对拍 ----
    b.append(sketch_rect(40, 82, 1070, 220, fill=TINT["white"]))
    b.append(panel_title(56, 108, "① 压力对拍：200 组随机混合图（rank 2~3，链长 4~9）",
                         GREEN))
    stats = [
        ("通过率", "200 / 200", GREEN),
        ("轮次 min/中位/max", "0 / 2 / 14", INK),
        ("计算 op 总数", "1357 → 973（-28.3%）", ORANGE),
        ("转置总数", "188 → 126", INK),
        ("cast 总数", "172 → 0", INK),
        ("reshape 总数", "380 → 240", INK),
        ("生成 fused", "10 个", INK),
    ]
    for i, (t, d, c) in enumerate(stats):
        x = 56 + (i % 4) * 262
        y = 128 + (i // 4) * 62
        b.append(sketch_rect(x, y, 240, 48, fill=TINT["gray"], sw=1.8,
                             nseg=4))
        b.append(txt(x + 12, y + 20, t, 10.5, MUTED))
        b.append(txt(x + 12, y + 38, d, 11.5, c, bold=True))
    b.append(txt(56, 264,
                 "每张图断言五条：数值逐位相等 / fixpoint / 二次运行零轮（幂等）/ op 数不增 / 无振荡",
                 11, INK))
    b.append(txt(56, 284,
                 "30% 的图以 add(x,y) 起头（融合机会）、15% const 起头（折叠机会）；cast 全部 f32→f32",
                 10.5, MUTED))

    # ---- 左下：MLIR 探针 ----
    b.append(sketch_rect(40, 326, 520, 400, fill=TINT["white"]))
    b.append(panel_title(56, 350, "② MLIR 探针（Ubuntu LLVM 18.1.8）", BLUE))
    probes = [
        ("探针1-2  幂等", None, None),
        ("canonicalize x2 == x1", "恒等 tensor.cast 删到 0", GREEN),
        ("cse x2 == x1", "2 个相同 generic 合并成 1 个", GREEN),
        ("探针3  顺序敏感（arith）", None, None),
        ("--canonicalize --cse", "1 个 arith.addf", GREEN),
        ("--cse --canonicalize", "2 个 arith.addf（顺序敏感）", RED),
        ("--cse --canonicalize --cse", "1 个（补趟追平）", GREEN),
        ("探针4  Cast 消除解锁 CSE", None, None),
        ("--canonicalize --cse", "1 个 linalg.generic", GREEN),
        ("--cse --canonicalize", "2 个 linalg.generic", RED),
    ]
    yy = 372
    for t, d, c in probes:
        if d is None:
            b.append(txt(56, yy, t, 11.5, BLUE, bold=True))
            yy += 22
        else:
            b.append(txt(70, yy, t, 10.5, INK))
            b.append(txt(300, yy, "→ " + d, 10.5, c, bold=True))
            yy += 20
    b.append(txt(56, 596,
                 "结论：stock 的 pass 一次性按序执行、不回头——", 10.5,
                 ORANGE, bold=True))
    b.append(txt(56, 614, "「先造机会的在前，用机会的在后」；", 10.5, INK))
    b.append(txt(56, 632, "自建管道用 run_passes 循环到不动点即可追平", 10.5,
                 INK))
    b.append(txt(56, 660, "探针文件：idem_canon / idem_cse /", 10, MUTED))
    b.append(txt(56, 676, "order_arith / order_cast（.mlir，可复跑）", 10,
                 MUTED))

    # ---- 右下：Pass 顺序说明 ----
    b.append(sketch_rect(590, 326, 520, 400, fill=TINT["white"]))
    b.append(panel_title(606, 350, "③ Pass 顺序说明（今日产出）", ORANGE))

    b.append(txt(606, 380, "推荐顺序（RECOMMENDED_PATTERNS）：", 11.5, INK,
                 bold=True))
    tiers = [
        ("1-5  消除类", "merge_t / merge_r / transparent_r / cast / fold",
         "只减不加，先跑把图变小；互相独立，内部顺序不敏感", GREEN),
        ("6  融合", "fuse_add_relu",
         "改变算子形态（relu 消失）；抢在传播前拿窗口（4 < 5 op）", ORANGE),
        ("7  传播", "push_transpose",
         "收尾让转置会合（三明治 2→0 是它的独门收益）；白名单不认 fused", BLUE),
    ]
    yy = 402
    for t, p, why, c in tiers:
        b.append(sketch_rect(606, yy, 488, 52, fill=TINT["gray"], sw=1.8,
                             nseg=4))
        b.append(txt(618, yy + 19, t, 11, c, bold=True))
        b.append(txt(720, yy + 19, p, 9.5, INK))
        b.append(txt(618, yy + 41, why, 9.5, MUTED))
        yy += 62

    b.append(txt(606, 596, "两条已知边界（写进文档，不当惊喜）：", 11, RED,
                 bold=True))
    b.append(txt(606, 616, "· 竞争对无全局最优：融合在前更少 op，但三明治", 10.5,
                 INK))
    b.append(txt(606, 634, "  只有传播能消——量化留给第 11 周 Cost Model", 10.5,
                 INK))
    b.append(txt(606, 654, "· 一次性管道（mlir-opt 命令行顺序）没有「下一轮」：", 10.5,
                 INK))
    b.append(txt(606, 672, "  消除类必须排在使用机会的 pass 之前（1 vs 2）", 10.5,
                 INK))
    b.append(txt(606, 700, "稳定 IR（混合链终点，10 op → 4 op，5 轮）：", 10.5,
                 GREEN, bold=True))
    b.append(txt(606, 718, "%12 = fused_add_relu %1, %2   %8 = transpose %12",
                 10, INK))
    save("04-results.svg", "".join(b))


if __name__ == "__main__":
    fig1()
    fig2()
    fig3()
    fig4()
    print("全部 4 张 SVG 生成完毕")
