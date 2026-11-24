#!/usr/bin/env python3
"""make_images.py —— 第 67 天（Cast 消除）教程的四张手绘 sketch 风 SVG 信息图。

风格约定（与第 8/9/10 周各天一致，Excalidraw-like）：
  - 背景 #fdfaf2（米白），盒子白底 + 深灰 #6b6357 手绘描边
  - 强调色不超过 4 种柔和色：蓝 #4a7fa5 / 橙 #a8772e / 绿 #5a8a5a / 红 #b0605a
  - 线条带轻微抖动（L 段折线），圆头笔触，线宽 2 左右
  - 手写感字体栈：Comic Sans MS / Comic Neue / Kaiti SC / 楷体 / cursive
  - 只用矩形、格子条、括号线、箭头等简单几何形状

图中全部数字来自 2026-11-12 的真实运行（code/outputs/）：
  cast_elim_lab 24/24；test_cast_elim 39/39；
  MLIR 八连测：extf f32→f32 Verifier 拒（cast incompatible）、
  bitcast f32→f32 消除、truncf∘extf 保留 2 op（无浮点回环折叠）、
  extf∘truncf 保留（正确拒绝）、trunci∘extsi 消除、extsi∘trunci 保留、
  bitcast 链消除、ui8 类型不存在（MLIR 整数 signless）；
  判定表 17/17；随机链 300/300（894 op → 730，消除 164 个 identity）；
  数值现场：0.1 三重人格（0.10000000149011612 / 0.0999755859375 /
  0.099609375）、0.5 假阴性、300→44、0xFF=-1/255、
  f32→f16→f32 有 1001/1003 个值变化。

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

rng = random.Random(67)


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
    print(f"写出 {path}（{path.stat().st_size} B）")


# ===========================================================================
# 图 1：全貌——第 10 周第 4 天 + Pattern 在优化管道中的位置
# ===========================================================================

def fig1() -> None:
    W, H = 1020, 730
    b = [header(W, H, "第 67 天全貌：Cast 消除",
                 "阶段三「AI 计算图与图优化」· 第 10 周第 4 天 · 判据从「元素数量」换成「类型全等」")]

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
                 "本周主线：转置（65）→ reshape（66）→ Cast（今天）→ Layout 传播（68）——同一副 Pattern 骨架第四天复用，判据从形状世界换到类型世界",
                 11.5, MUTED))

    # 中部：问题框 + Pattern 框 + 反例框
    qy = 182
    b.append(sketch_rect(40, qy, 280, 130, fill=TINT["blue"], sw=2.4))
    b.append(txt(180, qy + 24, "图里的无操作 Cast", 14, BLUE, "middle",
                 bold=True))
    b.append(txt(180, qy + 48, "%c = mini.cast %in", 11, INK, "middle"))
    b.append(txt(180, qy + 65, "     from=f32 to=f32", 11, INK, "middle"))
    b.append(txt(180, qy + 90, "AMP 边界、前端规范化、优化器", 10, MUTED,
                 "middle"))
    b.append(txt(180, qy + 107, "插的转换没人回收 → 残留 no-op", 10, MUTED,
                 "middle"))

    b.append(sketch_rect(370, qy, 300, 130, fill=TINT["green"], sw=2.4))
    b.append(txt(520, qy + 24, "Pattern：无操作 Cast 消除", 13.5, GREEN,
                 "middle", bold=True))
    b.append(txt(520, qy + 52, "Cast(x, T) 且 type(x) == T → x",
                 11, INK, "middle", bold=True))
    b.append(txt(520, qy + 76, "判据是 dtype 全等（位宽×类别×符号/格式）", 10,
                 MUTED, "middle"))
    b.append(txt(520, qy + 98, "无需唯一使用者检查——Day 66 P1 原型直接复用：", 10,
                 MUTED, "middle"))
    b.append(txt(520, qy + 115, "删 op 自身、replaceAllUses 全量改道", 10,
                 MUTED, "middle"))
    b.append(sketch_path([(320, qy + 65), (370, qy + 65)],
                         stroke=STROKE, sw=2.0, arrow=True, curved=True))

    b.append(sketch_rect(700, qy, 280, 130, fill=TINT["red"], sw=2.4))
    b.append(txt(840, qy + 24, "四类反例：今天全部保留", 13.5, RED, "middle",
                 bold=True))
    for k, s in enumerate([
            "精度扩展 f16→f32 · 精度缩减 f32→f16",
            "符号语义 i8↔ui8（0xFF = -1 还是 255？）",
            "域翻转 f32↔i32（0.5 → 0）· 同宽异格式 f16↔bf16",
            "回环合并「先缩后扩」改数值 → 留给以后"]):
        b.append(txt(840, qy + 52 + k * 19, s, 9.8, INK, "middle"))
    b.append(sketch_path([(670, qy + 65), (700, qy + 65)],
                         stroke=STROKE, sw=2.0, arrow=True, curved=True))

    # 中下：PassManager 迭代
    my = 340
    b.append(sketch_rect(40, my, 940, 78, fill="#ffffff", sw=2.2))
    b.append(txt(60, my + 24, "PassManager：迭代到不动点（实测）", 13, INK,
                 bold=True))
    b.append(txt(60, my + 46,
                 "连续两个 identity：f32→f32→f32 → 3 轮 2 次应用 → func.return %in（每轮消一个，最后一轮确认不动点）",
                 11.5, INK))
    b.append(txt(60, my + 66,
                 "多使用者照样消（场景 A：3 op → 2）；被 return 也照样消（场景 B：1 → 0）——删除的只是 op 自身",
                 10.5, MUTED))

    # 底部：MLIR 实测对照
    by = 442
    b.append(txt(40, by, "MLIR 侧真实事实（本机 LLVM 18.1.8，--canonicalize 实测）：",
                 12, INK, bold=True))
    facts = [
        ("① 同型 cast 大多表达不出", "arith.extf f32→f32 被拒绝（\"cast incompatible\"）",
         "方向化家族表达不出 no-op——源头就进不了 IR", "red"),
        ("② bitcast 同型/双射回环消除", "bitcast f32→f32、f32→i32→f32 都消除为 return %arg0",
         "类型全等/双射才动手（与 mini 一致）", "green"),
        ("③ stock 是拼图不是原则", "整数回环 trunci∘extsi 折叠，浮点回环 truncf∘extf 保留——恒等也要自己写",
         "有损回环一律被正确保留", "orange"),
    ]
    fy = by + 14
    for t1, l1, l2, col in facts:
        b.append(sketch_rect(40, fy, 460, 46, fill=TINT[col], sw=2.0))
        b.append(txt(56, fy + 19, t1, 11.5,
                     {"red": RED, "green": GREEN, "orange": ORANGE}[col],
                     bold=True))
        b.append(txt(56, fy + 37, l1, 9.6, INK, bold=True))
        b.append(txt(360, fy + 37, l2, 9.6, INK))
        fy += 54

    # 右下：验收汇总
    ay = by + 14
    b.append(sketch_rect(530, ay, 450, 142, fill=TINT["green"], sw=2.4))
    b.append(txt(546, ay + 24, "今日验收（全部真实运行）：", 12.5, GREEN,
                 bold=True))
    lines = [
        "主实验 24/24 · 验收测试 39/39（A–G 七段）",
        "判定表 17/17：identity → 0 op，其余 → 1 op",
        "随机链 300/300（894 op → 730，消除 164 个 identity）",
        "位宽陷阱现场：i8→ui8 消除后 255 → -1（数值对拍揭穿）",
        "方向终审：f32→f16→f32 有 1001/1003 个值变化（0.1 现场）",
    ]
    for k, ln in enumerate(lines):
        b.append(txt(546, ay + 46 + k * 18, "· " + ln, 10.3, INK))

    # 明日预告条
    ny = 634
    b.append(sketch_rect(40, ny, 940, 40, fill="#ffffff", sw=2.0))
    b.append(txt(60, ny + 25, "明天（Day 68）：", 11.5, GREEN, bold=True))
    b.append(txt(178, ny + 25,
                 "Layout 转换传播——转换向生产者或消费者移动；今天「类型不同就全保留」的保守纪律正是它的预习",
                 11.5, INK))
    save("01-overview.svg", "".join(b))


# ===========================================================================
# 图 2：核心机制——类型三要素 + 0xFF 两副面孔 + 0.1 三重人格与单向门
# ===========================================================================

def fig2() -> None:
    W, H = 1060, 830
    b = [header(W, H, "核心机制：类型 = 位宽 × 类别 × 符号/格式",
                 "「无操作」当且仅当三个要素全部一致 · 信息只往窄的方向丢 · 数字全部来自真实运行")]

    # 顶部：判据框
    b.append(sketch_rect(40, 76, 980, 92, fill=TINT["blue"], sw=2.4))
    b.append(txt(60, 102, "判据（对比昨天：不看形状看类型）", 12.5, BLUE,
                 bold=True))
    b.append(txt(60, 126, "identity ⟺ in_dtype == out_dtype：f32 =「32 位·浮点」、i8 =「8 位·整数·有符号」、ui8 =「8 位·整数·无符号」——一项不同就不是同一个类型",
                 11.3, INK))
    b.append(txt(60, 150, "位宽陷阱（今天的头号反面教材）：只比位宽会把 i8→ui8、f32→i32、f16→bf16 全错判成 no-op——实测 i8(-1) 消除后 255 变 -1",
                 11.3, INK, bold=True))

    # 中部：类型地图（位宽台阶）
    fy = 186
    b.append(sketch_rect(40, fy, 500, 300, fill="#ffffff", sw=2.2))
    b.append(txt(60, fy + 24, "类型地图：同宽不同型，窄宽分上下", 13, INK,
                 bold=True))

    def dtype_box(x, y, name, desc, tint="white", stroke=STROKE):
        b.append(sketch_rect(x, y, 108, 46, fill=TINT[tint], sw=2.0))
        b.append(txt(x + 54, y + 20, name, 13, INK, "middle", bold=True))
        b.append(txt(x + 54, y + 37, desc, 8.8, MUTED, "middle"))

    # 浮点列（左）与整数列（右）
    dtype_box(80, fy + 60, "f32", "32 位 · 24 位尾数")
    dtype_box(80, fy + 210, "f16", "16 位 · 10 位尾数")
    dtype_box(210, fy + 210, "bf16", "16 位 · 7 位尾数")
    dtype_box(360, fy + 60, "i32", "32 位 · 有符号")
    dtype_box(360, fy + 210, "i8", "8 位 · 有符号")
    dtype_box(360, fy + 270, "ui8", "8 位 · 无符号")

    b.append(txt(80, fy + 52, "浮点（float）", 10, MUTED, bold=True))
    b.append(txt(360, fy + 52, "整数（int）", 10, MUTED, bold=True))

    # 箭头：widen（绿，向上）、narrow（橙，向下）
    b.append(sketch_path([(134, fy + 210), (134, fy + 108)],
                         stroke=GREEN, sw=2.4, arrow=True))
    b.append(txt(70, fy + 166, "widen 扩展", 9.5, GREEN, bold=True))
    b.append(sketch_path([(108, fy + 108), (108, fy + 210)],
                         stroke=ORANGE, sw=2.4, arrow=True))
    b.append(txt(104, fy + 190, "narrow 缩减", 9.5, ORANGE, "end", bold=True))
    b.append(sketch_path([(414, fy + 210), (414, fy + 108)],
                         stroke=GREEN, sw=2.4, arrow=True))
    b.append(txt(422, fy + 150, "widen", 8.8, GREEN, bold=True))
    b.append(sketch_path([(388, fy + 108), (388, fy + 210)],
                         stroke=ORANGE, sw=2.4, arrow=True))
    b.append(txt(380, fy + 196, "narrow", 8.8, ORANGE, "end", bold=True))
    # signflip（红，i8 与 ui8 上下相邻——垂直双向短箭头）
    b.append(sketch_path([(408, fy + 258), (408, fy + 268)],
                         stroke=RED, sw=2.4, arrow=True))
    b.append(sketch_path([(424, fy + 268), (424, fy + 258)],
                         stroke=RED, sw=2.4, arrow=True))
    b.append(txt(476, fy + 262, "signflip", 9.2, RED, bold=True))
    b.append(txt(476, fy + 276, "符号语义", 9.2, RED, bold=True))
    # reformat（红，f16 与 bf16 水平相邻——双向短箭头）
    b.append(sketch_path([(188, fy + 226), (210, fy + 226)],
                         stroke=RED, sw=2.4, arrow=True))
    b.append(sketch_path([(210, fy + 244), (188, fy + 244)],
                         stroke=RED, sw=2.4, arrow=True))
    b.append(txt(264, fy + 274, "reformat 同宽异格式", 9.2, RED, "middle",
                 bold=True))
    # domainflip（灰虚，f32<->i32）
    b.append(sketch_path([(188, fy + 83), (360, fy + 83)],
                         stroke=MUTED, sw=2.0, arrow=True, opacity=0.85))
    b.append(sketch_path([(360, fy + 96), (188, fy + 96)],
                         stroke=MUTED, sw=2.0, arrow=True, opacity=0.85))
    b.append(txt(274, fy + 76, "domainflip 域翻转", 9.5, MUTED, "middle",
                 bold=True))

    # identity 注记（放在浮点列与整数列之间的空地，避开箭头）
    b.append(txt(274, fy + 130, "identity = 同型自环", 10.2, BLUE, "middle",
                 bold=True))
    b.append(txt(274, fy + 146, "f32→f32、i8→i8、f16→f16、ui8→ui8", 9.6,
                 INK, "middle"))
    b.append(txt(274, fy + 162, "只有它今天被消除", 9.6, BLUE, "middle",
                 bold=True))

    # 0xFF 两副面孔（右中）
    hx, hy = 570, fy
    b.append(sketch_rect(hx, hy, 450, 138, fill=TINT["red"], sw=2.4))
    b.append(txt(hx + 16, hy + 24, "0xFF 的两副面孔（符号语义）", 13, RED,
                 bold=True))
    b.append(txt(hx + 16, hy + 48, "同一串位 11111111：按 i8 读是 -1，按 ui8 读是 255",
                 10.5, INK))
    b.append(txt(hx + 16, hy + 70, "下游 extsi 得 -1 · extui 得 255 → 消除 i8→ui8 会改程序行为",
                 10.5, INK, bold=True))
    b.append(txt(hx + 16, hy + 94, "MLIR 的答案：整数是 signless 的，ui8 类型不存在——",
                 9.8, MUTED))
    b.append(txt(hx + 16, hy + 112, "符号在操作里（extsi/extui）不在类型里；mini/PyTorch 的 dtype 带符号，更不能只比位宽",
                 9.8, MUTED))

    # 0.1 三重人格 + 单向门（右中下）
    gx, gy = 570, fy + 152
    b.append(sketch_rect(hx, gy, 450, 148, fill="#ffffff", sw=2.2))
    b.append(txt(hx + 16, gy + 24, "0.1 的三重人格（精度缩减的现场）", 13, INK,
                 bold=True))
    b.append(txt(hx + 16, gy + 48, "f32 : 0.10000000149011612（0x3DCCCCCD）",
                 10.5, INK))
    b.append(txt(hx + 16, gy + 68, "f16 : 0.0999755859375（0x2E66）· bf16 : 0.099609375（0x3DCC0000）",
                 10.5, INK))
    b.append(txt(hx + 16, gy + 92, "回环 f32→f16→f32：0.1 ≠ 0.0999755859375——信息只往窄的方向丢",
                 10.5, ORANGE, bold=True))
    b.append(txt(hx + 16, gy + 114, "假阴性：0.5 回环恰好相等（2 的幂）——测试值不能只挑好值",
                 9.8, MUTED))
    b.append(txt(hx + 16, gy + 134, "安全方向存在：f16→f32→f16 的 1003 个值（含 ±inf/NaN）全部原样",
                 9.8, GREEN, bold=True))

    # 底部左：今日裁决三条
    ly = 512
    b.append(sketch_rect(40, ly, 500, 200, fill="#ffffff", sw=2.2))
    b.append(txt(60, ly + 26, "今日裁决（保守边界一刀切）：", 13, INK,
                 bold=True))
    rules = [
        ("消除", "in_dtype == out_dtype（类型全等）", "Cast(x, T) → x，无条件，多使用者无妨",
         "green"),
        ("保留", "widen / narrow / signflip / reformat / domainflip",
         "单个 op 都合法，但今天一个都不动", "orange"),
        ("缓办", "回环链合并（先缩后扩 ≠ 恒等）",
         "安全方向（先宽后窄回子集）要逐对证明——今天的边界挡住它", "red"),
    ]
    ryy = ly + 46
    for t1, t2, t3, col in rules:
        b.append(sketch_rect(60, ryy, 460, 44, fill=TINT[col], sw=2.0))
        b.append(txt(76, ryy + 18, t1, 11.5,
                     {"green": GREEN, "orange": ORANGE, "red": RED}[col],
                     bold=True))
        b.append(txt(116, ryy + 18, t2, 10.2, INK, bold=True))
        b.append(txt(76, ryy + 35, t3, 9.6, MUTED))
        ryy += 52

    # 底部右：回环方向终审表
    ry2 = 512
    b.append(sketch_rect(570, ry2, 450, 200, fill="#ffffff", sw=2.2))
    b.append(txt(586, ry2 + 26, "回环终审（数值实测）：方向决定安全", 13, INK,
                 bold=True))
    rows = [
        ("f16→f32→f16", "1003 个值（含 ±inf/NaN）原样", "安全", GREEN),
        ("f32→f16→f32", "1001/1003 变了（0.1 现场）", "有损", RED),
        ("i8→i32→i8", "[-128..127] 原样（符号扩展保低位）", "安全", GREEN),
        ("i32→i8→i32", "255→-1、300→44（截断丢高位）", "有损", RED),
        ("f32→bf16→f32", "0.1 → 0.099609375（尾数 24→7 位）", "有损", RED),
        ("i8→ui8→i8", "双射回原（mod 256）——但今天也不合并", "安全*", GREEN),
    ]
    ryy = ry2 + 46
    for name, scene, verdict, col in rows:
        b.append(txt(586, ryy, name, 10.2, INK, bold=True))
        b.append(txt(700, ryy, scene, 9.6, INK))
        b.append(txt(1000, ryy, verdict, 10, col, "end", bold=True))
        ryy += 24
    b.append(txt(586, ryy + 8, "* 安全 ≠ 今天做：mini 的边界只放行 identity，其余逐对证明后再说",
                 9.3, MUTED))

    save("02-mechanism.svg", "".join(b))


# ===========================================================================
# 图 3：优化前后 IR 对照（真实输出）
# ===========================================================================

def fig3() -> None:
    W, H = 1060, 950
    b = [header(W, H, "优化前后 IR 对照：消除与保留的五种命运",
                 "全部 IR 来自 outputs/cast_elim_lab.txt 的真实打印（mini IR 文本格式）")]

    cases = [
        ("场景 A：identity 多使用者（%r 被 2 处使用）→ 照样消除", GREEN, "green",
         ["%r = mini.cast %in from=f32 to=f32 : (2x3xf32) -> (2x3xf32)",
          "%a = mini.cast %r from=f32 to=f16 : (2x3xf32) -> (2x3xf16)",
          "%b = mini.cast %r from=f32 to=i32 : (2x3xf32) -> (2x3xi32)",
          "func.return %a, %b"],
         ["%a = mini.cast %in from=f32 to=f16 : (2x3xf32) -> (2x3xf16)",
          "%b = mini.cast %in from=f32 to=i32 : (2x3xf32) -> (2x3xi32)",
          "func.return %a, %b"],
         "P 不看使用者数：删的是 op 自身（3 op → 2），%a/%b 全部改道读 %in"),
        ("场景 B：identity 单跳直返 → return %in", GREEN, "green",
         ["%c = mini.cast %in from=f32 to=f32 : (2x3xf32) -> (2x3xf32)",
          "func.return %c"],
         ["func.return %in"],
         "整体消除（1 op → 0）——被 return 也不挡：返回值改道读 %in"),
        ("场景 C：混合图（identity + 扩展 + 缩减）→ 只消 identity", BLUE, "blue",
         ["%a = mini.cast %in from=f32 to=f32 : (2x3xf32) -> (2x3xf32)",
          "%b = mini.cast %a from=f32 to=f16 : (2x3xf32) -> (2x3xf16)",
          "%c = mini.cast %b from=f16 to=f32 : (2x3xf16) -> (2x3xf32)",
          "func.return %c"],
         ["%b = mini.cast %in from=f32 to=f16 : (2x3xf32) -> (2x3xf16)",
          "%c = mini.cast %b from=f16 to=f32 : (2x3xf16) -> (2x3xf32)",
          "func.return %c"],
         "3 op → 2：%b/%c 是「先缩后扩」回环——合并会改数值（0.1 现场），保留"),
        ("场景 E：四类反例单跳 → 全保留（4 op → 4，零应用）", ORANGE, "orange",
         ["%w = mini.cast %in from=f32 to=f16 : (2x3xf32) -> (2x3xf16)",
          "%n = mini.cast %in from=f32 to=bf16 : (2x3xf32) -> (2x3xbf16)",
          "%d = mini.cast %in from=f32 to=i32 : (2x3xf32) -> (2x3xi32)",
          "%s = mini.cast %inp from=i8 to=ui8 : (2x3xi8) -> (2x3xui8)",
          "func.return %w, %n, %d, %s"],
         ["（图原样保留：扩展/缩减/域翻转/符号语义一个不动）"],
         "四个 op 没有一个是 identity——位宽相同也不行（%s 是 0xFF 的两副面孔）"),
        ("场景 F：位宽判据的反面教材——i8→ui8 上当场翻车", RED, "red",
         ["%u = mini.cast %in from=i8 to=ui8 : (2x3xi8) -> (2x3xui8)",
          "func.return %u     （正确版：1 op 保留，返回 uint8 值 255）"],
         ["func.return %in     （buggy 版：op 消失，返回 int8 值 -1！）"],
         "数值对拍 False：-1 应该变成 255——「只比位宽」把符号语义当成了 no-op"),
    ]

    y0 = 92
    chs = [148, 118, 158, 172, 138]
    y = y0
    for (title, color, tint, before, after, note), chh in zip(cases, chs):
        b.append(txt(40, y + 4, title, 13, color, bold=True))
        b.append(sketch_rect(40, y + 10, 500, chh - 26, fill="#ffffff", sw=2.0))
        b.append(txt(56, y + 32, "优化前", 10.5, MUTED, bold=True))
        for j, ln in enumerate(before):
            b.append(txt(56, y + 52 + j * 17, ln, 9.2, INK))
        b.append(sketch_line(548, y + (chh - 26) / 2 + 10, 596,
                             y + (chh - 26) / 2 + 10, stroke=color, sw=2.6,
                             arrow=True))
        b.append(txt(572, y + (chh - 26) / 2 - 6, "P", 9.5, color,
                     "middle", bold=True))
        b.append(sketch_rect(600, y + 10, 420, chh - 26,
                             fill=TINT[tint], sw=2.2))
        b.append(txt(616, y + 32, "优化后", 10.5, MUTED, bold=True))
        for j, ln in enumerate(after):
            b.append(txt(616, y + 52 + j * 17, ln, 9.2, INK, bold=True))
        b.append(txt(616, y + chh - 34, note, 9.2, color))
        y += chh + 8

    save("03-before-after.svg", "".join(b))


# ===========================================================================
# 图 4：MLIR 实测裁决 + 判定表汇总
# ===========================================================================

def fig4() -> None:
    W, H = 1060, 830
    b = [header(W, H, "MLIR 实测裁决 × 判定表汇总",
                 "cast 家族八连测（本机 LLVM 18.1.8）· 17 个 dtype 对判定表 · 随机压力对拍")]

    # 左上：MLIR 八连测
    lx, ly = 40, 90
    b.append(txt(lx, ly + 4, "现场一：cast 家族交给 --canonicalize，八项裁决", 13,
                 INK, bold=True))
    verdicts = [
        ("① extf f32→f32", "Verifier 拒绝", "cast incompatible", RED),
        ("② bitcast f32→f32", "消除", "return %arg0", GREEN),
        ("③ truncf∘extf 浮点回环", "保留 2 op", "数学恒等也无此规则", ORANGE),
        ("④ extf∘truncf 有损回环", "保留 2 op", "正确拒绝", ORANGE),
        ("⑤ trunci∘extsi 整数回环", "消除", "return %arg0", GREEN),
        ("⑥ extsi∘trunci 有损回环", "保留 2 op", "正确拒绝", ORANGE),
        ("⑦ bitcast 链 f32→i32→f32", "消除", "双射重解释", GREEN),
        ("⑧ bitcast i8→ui8", "Verifier 拒绝", "ui8 不存在（signless）", RED),
    ]
    vy = ly + 16
    for name, v, note, col in verdicts:
        b.append(sketch_rect(lx, vy, 470, 30, fill="#ffffff", sw=1.6))
        b.append(txt(lx + 12, vy + 20, name, 10.2, INK, bold=True))
        b.append(txt(lx + 218, vy + 20, v, 10.2, col, bold=True))
        b.append(txt(lx + 458, vy + 20, note, 8.8, MUTED, "end"))
        vy += 36
    b.append(txt(lx, vy + 10,
                 "结论：stock 是「拼图」——整数回环有折叠、浮点回环没有；",
                 10, MUTED))
    b.append(txt(lx, vy + 28,
                 "有损方向一律保留（正确）。mini 的判据一刀切：type(x) == T 才消除。",
                 10, MUTED))

    # 左下：随机压力 + 数值现场
    sy = vy + 44
    b.append(sketch_rect(lx, sy, 470, 128, fill=TINT["green"], sw=2.2))
    b.append(txt(lx + 16, sy + 24, "随机压力对拍 300/300：", 11.5, GREEN,
                 bold=True))
    b.append(txt(lx + 16, sy + 46,
                 "随机 dtype 链（六型全组合、链长 1..5）：数值不变、", 10, INK))
    b.append(txt(lx + 16, sy + 64,
                 "Verifier 通过、op 数 = 非 identity 跳数", 10, INK))
    b.append(txt(lx + 16, sy + 90,
                 "894 个初始 cast op → 730 个（消除 164 个 identity）", 10,
                 INK, bold=True))
    b.append(txt(lx + 16, sy + 110,
                 "值域非负有界：回绕/负值翻车现场由判定表与场景 F 承担", 9.3,
                 MUTED))

    # 右：判定表
    rx, ry = 550, 90
    b.append(txt(rx, ry + 4, "判定表（17 个 dtype 对，优化后 op 数 + 数值对拍全 ok）：",
                 12.5, INK, bold=True))
    rows = [
        ("f32→f32 · f16→f16 · bf16→bf16 · i8→i8", "无操作", 0),
        ("f16→f32 · bf16→f32 · i8→i32 · ui8→i32", "精度扩展", 1),
        ("f32→f16 · f32→bf16 · i32→i8", "精度缩减", 1),
        ("f16→bf16 · bf16→f16", "同宽异格式", 1),
        ("i8→ui8 · ui8→i8", "符号语义", 1),
        ("f32→i32 · i32→f32", "域翻转", 1),
    ]
    ty = ry + 22
    b.append(txt(rx + 8, ty, "dtype 对", 10.5, MUTED, bold=True))
    b.append(txt(rx + 316, ty, "分类", 10.5, MUTED, bold=True))
    b.append(txt(rx + 420, ty, "剩 op", 10.5, MUTED, bold=True))
    b.append(sketch_line(rx + 4, ty + 6, rx + 440, ty + 6, opacity=0.4))
    b.append(sketch_line(rx + 4, ty + 10, rx + 440, ty + 10, opacity=0.4))
    yy = ty + 24
    for name, cls, ops in rows:
        b.append(txt(rx + 8, yy, name, 9.6, INK))
        b.append(txt(rx + 316, yy, cls, 9.6, INK))
        b.append(txt(rx + 438, yy, str(ops), 10.5,
                     GREEN if ops == 0 else INK, "end", bold=True))
        yy += 26
    b.append(txt(rx + 8, yy + 4,
                 "0 = 整体消除为 return %in；1 = 原样保留——位宽相同也保留（i8→ui8）",
                 9.3, MUTED))

    # 右中：位宽陷阱
    wy = yy + 18
    b.append(sketch_rect(rx, wy, 460, 118, fill=TINT["red"], sw=2.4,
                         stroke=RED))
    b.append(txt(rx + 14, wy + 22, "位宽陷阱实测（只比位宽的 buggy 判据）：",
                 11.5, RED, bold=True))
    b.append(txt(rx + 14, wy + 44, "i8→ui8：消除后返回值 255 → -1（值翻车）",
                 10, INK))
    b.append(txt(rx + 14, wy + 62, "f32→i32：0.1/0.5 原样放行（应截成 0）",
                 10, INK))
    b.append(txt(rx + 14, wy + 80, "f16→bf16：值没有重新编码（应 0.099609375）",
                 10, INK))
    b.append(txt(rx + 14, wy + 102,
                 "三个同宽反例全翻车——「位宽相同」不是「类型一致」，mini 的 returns 没有签名类型，",
                 9.3, MUTED))
    b.append(txt(rx + 14, wy + 116,
                 "数值对拍抓住了它；真实 MLIR 里 replaceAllUses 后类型不匹配也会被 Verifier 拒", 9.3,
                 MUTED))

    # 右下：方向终审
    dy = wy + 130
    b.append(sketch_rect(rx, dy, 460, 128, fill="#ffffff", sw=2.2))
    b.append(txt(rx + 14, dy + 22, "回环方向终审（信息只往窄的方向丢）：", 11.5,
                 INK, bold=True))
    pairs2 = [
        ("f16→f32→f16", "安全（1003 值原样）", GREEN),
        ("f32→f16→f32", "有损（1001/1003 变，0.1 现场）", RED),
        ("i8→i32→i8", "安全（符号扩展保低位）", GREEN),
        ("i32→i8→i32", "有损（255→-1、300→44）", RED),
    ]
    yy = dy + 44
    for name, verdict, col in pairs2:
        b.append(txt(rx + 14, yy, name, 9.8, INK, bold=True))
        b.append(txt(rx + 130, yy, verdict, 9.8, col))
        yy += 20
    b.append(txt(rx + 14, yy + 6,
                 "安全方向今天也不合并：回环合并要逐对证明，留到以后（明天的 Layout 传播也要同样的纪律）",
                 9.3, MUTED))

    # 底部：验收汇总
    by = 764
    b.append(sketch_rect(40, by, 980, 44, fill=TINT["gray"], sw=2.2))
    b.append(txt(60, by + 18, "今日验收（全部真实运行）：", 12, GREEN, bold=True))
    b.append(txt(248, by + 18,
                 "主实验 24/24 · 验收测试 39/39 · 判定表 17/17 · 随机 300/300 · MLIR 八连测全部复现",
                 11, INK))
    b.append(txt(60, by + 36,
                 "产出：Cast 消除 Pattern + 位宽判据反面教材（cast_elim_lab.py）· 判定表 + 类型反例 · outputs/ 全部留档",
                 10, MUTED))
    save("04-verdicts.svg", "".join(b))


if __name__ == "__main__":
    fig1()
    fig2()
    fig3()
    fig4()
