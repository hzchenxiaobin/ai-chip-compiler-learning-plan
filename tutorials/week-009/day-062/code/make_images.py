#!/usr/bin/env python3
"""make_images.py —— 第 62 天教程的四张手绘 sketch 风 SVG 信息图。

风格约定（与第 8/9 周各天一致）：
  - 背景 #fdfaf2（米白），盒子白底 + 深灰 #6b6357 手绘描边
  - 强调色不超过 4 种柔和色：蓝 #4a7fa5 / 橙 #a8772e / 绿 #5a8a5a / 红 #b0605a
  - 线条带轻微抖动（L 段折线），圆头笔触，线宽 2 左右
  - 手写感字体栈：Comic Sans MS / Comic Neue / Kaiti SC / 楷体 / cursive

图中全部数字来自 2026-11-12 的真实运行（outputs/ 目录）：
  specialize：a=2x3,b=3x2 → 4 处替换，mlir-opt exit=0；
  指标对照：memref.dim 1→0；affine+三次 full-unroll 后 affine.for 1→0、
  load 18→36、行数 55→94、字节 2453→4273；
  k_blind：动态 exit=0 放行，特化后 exit=1（operand #1 ... 4, but found 3）；
  产物：12 次调用轨迹 [2,2,4,2,8,2,4,16,2,4,2,32] → 5 个不同 M，
  编译 18.0/18.5/18.8/18.6/18.8 ms（中位数×3），通用版 18.9 ms，
  特化总 92.7 ms；策略 A 1 次 18.9ms / B、C 6 次 111.7ms；
  dispatch：场景 1 hit=1,M=2 → 220/280/490/640；场景 2 hit=0,M=4 →
  220/280/490/640/760/1000/1030/1360；场景 3 hit=1,M=4 → 同八值；
  test_specialize 28/28，products_lab 8/8。

运行: python3 make_images.py   （在 code/ 目录下，输出到 ../images/）
"""

from __future__ import annotations

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

rng = random.Random(62)


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


def sketch_line(x0, y0, x1, y1, stroke=STROKE, sw=2.0, arrow=False):
    out = [f'<path d="M {x0:.1f},{y0:.1f} L {x1:.1f},{y1:.1f}" '
           f'fill="none" stroke="{stroke}" stroke-width="{sw}" '
           f'stroke-linecap="round" stroke-linejoin="round"/>']
    if arrow:
        import math
        ang = math.atan2(y1 - y0, x1 - x0)
        L, A = 11, 0.5
        ax, ay = x1 - L * math.cos(ang), y1 - L * math.sin(ang)
        out.append(f'<path d="M {x1:.1f},{y1:.1f} L {ax:.1f},{ay - 4:.1f}" '
                   f'fill="none" stroke="{stroke}" stroke-width="{sw}" '
                   f'stroke-linecap="round"/>')
        out.append(f'<path d="M {x1:.1f},{y1:.1f} L {ax:.1f},{ay + 4:.1f}" '
                   f'fill="none" stroke="{stroke}" stroke-width="{sw}" '
                   f'stroke-linecap="round"/>')
    return "".join(out)


def header(w, h, title, sub):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" '
            f'height="{h}" viewBox="0 0 {w} {h}">\n'
            f'<rect width="{w}" height="{h}" fill="{BG}"/>\n'
            + txt(40, 38, title, 20, INK, bold=True) + "\n"
            + txt(40, 61, sub, 12, MUTED) + "\n")


# ============================================================
# 图 1：全貌——第 62 天在六阶段、第 9 周与编译链路中的位置
# ============================================================

def img1():
    W, H = 1240, 800
    p = [header(W, H,
                "第 62 天全貌：静态 Shape 特化入口——把 ? 钉成数字的那一站",
                "上：六阶段里程碑与第 9 周日程（今天第 6 天）｜中：编译链路上的特化入口｜下：昨天到今天的衔接")]

    # ---- 上：里程碑 ----
    p.append(txt(40, 92, "168 天六阶段（今天是阶段三·第 9 周的第 6 天，明天周复盘）：",
                 13.5, INK, bold=True))
    miles = [
        ("阶段一\nC++/编译器基础", "Day 1-28", TINT["white"], STROKE, MUTED),
        ("阶段二\nMLIR 核心能力", "Day 29-56", TINT["white"], STROKE, MUTED),
        ("阶段三\n图优化（今天）", "Day 57-84", TINT["blue"], BLUE, BLUE),
        ("阶段四\nLowering/Tiling", "Day 85-112", TINT["white"], STROKE, MUTED),
        ("阶段五\n端到端/Runtime", "Day 113-140", TINT["white"], STROKE, MUTED),
        ("阶段六\n收口/面试", "Day 141-168", TINT["white"], STROKE, MUTED),
    ]
    bw, gap = 176, 14
    for i, (name, rng_, fill, stroke, fg) in enumerate(miles):
        x = 40 + i * (bw + gap)
        p.append(sketch_rect(x, 104, bw, 52, fill, stroke, 2.2))
        lines = name.split("\n")
        p.append(txt(x + bw / 2, 124, lines[0], 12, fg, "middle", bold=True))
        p.append(txt(x + bw / 2, 143, lines[1], 10.5, fg, "middle"))
        p.append(txt(x + bw / 2, 159, rng_, 10, MUTED, "middle"))

    # ---- 第 9 周日程条 ----
    p.append(txt(40, 190, "第 9 周：Tensor、Shape、Stride 与 Layout（今天倒数第二天）：",
                 13.5, INK, bold=True))
    week = [
        ("57", "逻辑 Shape\n物理布局"),
        ("58", "NCHW/NHWC\n编译器 Layout"),
        ("59", "Reshape\n合法性"),
        ("60", "Broadcast\n规则"),
        ("61", "动态 Shape\n三种表示"),
        ("62", "特化入口\n（今天）"),
        ("63", "周复盘"),
    ]
    bw2 = 158
    for i, (day, topic) in enumerate(week):
        x = 40 + i * (bw2 + 8)
        hot = day == "62"
        fill = TINT["orange"] if hot else TINT["white"]
        stroke = ORANGE if hot else STROKE
        p.append(sketch_rect(x, 202, bw2, 56, fill, stroke, 2.6 if hot else 2.0))
        p.append(txt(x + bw2 / 2, 221, f"Day {day}", 11.5,
                     ORANGE if hot else INK, "middle", bold=True))
        for j, ln in enumerate(topic.split("\n")):
            p.append(txt(x + bw2 / 2, 238 + j * 14, ln, 10, INK, "middle"))

    # ---- 中：编译链路 ----
    p.append(txt(40, 292, "今天在编译链路的位置——特化是「动态世界 → 静态世界」的闸口：",
                 13.5, INK, bold=True))
    stages = [
        ("前端动态 IR", "?x3（M 是 ?，\n取值运行期才知）", TINT["red"], RED),
        ("specialize-shape\n（今天的入口）", "替换 ? → 2\n重推 outs + 重验", TINT["orange"], ORANGE),
        ("静态 IR", "2x3（全静态，\n检查网点亮）", TINT["green"], GREEN),
        ("图优化 + Lowering", "展开/常量传播\n有了着力点", TINT["white"], STROKE),
        ("产物库", "5 份特化\n+1 份通用", TINT["blue"], BLUE),
        ("运行时分发", "命中→特化版\n未命中→回退", TINT["blue"], BLUE),
    ]
    bw3, bh3 = 176, 66
    for i, (name, note, fill, stroke) in enumerate(stages):
        x = 40 + i * (bw3 + 14)
        p.append(sketch_rect(x, 306, bw3, bh3, fill, stroke,
                             3.0 if i == 1 else 2.2))
        p.append(txt(x + bw3 / 2, 327, name, 11.5,
                     stroke if i in (1,) else INK, "middle", bold=True))
        for j, ln in enumerate(note.split("\n")):
            p.append(txt(x + bw3 / 2, 344 + j * 13, ln, 9.5, INK, "middle"))
        if i < len(stages) - 1:
            p.append(sketch_line(x + bw3 + 2, 339, x + bw3 + 12, 339,
                                 stroke=STROKE, sw=2.0, arrow=True))

    # ---- 下：昨天到今天的衔接 ----
    p.append(txt(40, 404, "昨天到今天的衔接——bindings 表变成替换清单：", 13.5,
                 INK, bold=True))
    # 昨天的 mini 侧
    p.append(sketch_rect(40, 418, 360, 118, TINT["green"], GREEN, 2.4))
    p.append(txt(58, 440, "第 61 天 · mini 推导器（符号有名字）", 12, GREEN,
                 bold=True))
    p.append(txt(58, 462, "(2, ?k) × (3, 2)", 11, INK))
    p.append(txt(58, 480, "→ 输出 (2, 2)，bindings {k: 3}", 11, INK))
    p.append(txt(58, 498, "对账时顺手记下 ?k==3——", 10.5, MUTED))
    p.append(txt(58, 514, "「特化时可直接替换」的清单", 10.5, MUTED))
    # 箭头
    p.append(sketch_line(408, 477, 468, 477, stroke=ORANGE, sw=2.6, arrow=True))
    p.append(txt(438, 466, "换成 MLIR", 10, ORANGE, "middle", bold=True))
    p.append(txt(438, 492, "? 没有名字", 10, ORANGE, "middle"))
    # 今天的 MLIR 侧
    p.append(sketch_rect(478, 418, 360, 118, TINT["orange"], ORANGE, 2.4))
    p.append(txt(496, 440, "第 62 天 · MLIR 侧（? 按参数对号）", 12, ORANGE,
                 bold=True))
    p.append(txt(496, 462, "memref<?x3xf32>，spec \"a=2x3\"", 11, INK))
    p.append(txt(496, 480, "→ memref<2x3xf32>", 11, INK))
    p.append(txt(496, 498, "值从哪来？运行期观测 / profile——", 10.5, MUTED))
    p.append(txt(496, 514, "这正是第 129 天「静态 Shape 特化」的入口", 10.5, MUTED))

    # 三步
    p.append(txt(40, 570, "入口的三步（第 5 节动手实现）：", 13.5, INK, bold=True))
    steps = [
        ("① 替换", "把 spec 里的具体维\n填进参数类型的 ?", TINT["white"], STROKE),
        ("② 重推", "matmul 规则重推 outs：\nM=%a.dim0，N=%b.dim1，K 对账", TINT["white"], STROKE),
        ("③ 重验", "mlir-opt parse+verify\n再过一遍（mini + 外部两层）", TINT["white"], STROKE),
    ]
    bw4 = 372
    for i, (name, note, fill, stroke) in enumerate(steps):
        x = 40 + i * (bw4 + 16)
        p.append(sketch_rect(x, 584, bw4, 62, fill, stroke, 2.2))
        p.append(txt(x + 16, 606, name, 12, INK, bold=True))
        for j, ln in enumerate(note.split("\n")):
            p.append(txt(x + 16, 624 + j * 13, ln, 10, INK))

    p.append(txt(40, 676, "一句话定位：昨天的 ? 是「编译期还不知道」；今天做的事是「等运行期知道之后，回头把它钉成数字」，", 12, RED, bold=True))
    p.append(txt(40, 698, "换来一整份静态产物——代价是每个不同 Shape 都要重新钉一次。", 12, RED, bold=True))
    p.append(txt(40, 722, "边界说明：特化只对「会重复出现的 Shape」划算（batch=2 反复来）；一次性的 Shape 走通用版更省。", 10.5, MUTED))
    p.append(txt(40, 744, "实测环境：Linux aarch64 · Python 3.11.4 · numpy 1.26.4 · Ubuntu LLVM 18.1.8 · specialize 4 处替换 exit=0 · test 28/28 · lab 8/8", 10.5, MUTED))
    p.append("</svg>")
    (OUT / "01-overview.svg").write_text("\n".join(p), encoding="utf-8")


# ============================================================
# 图 2：核心机制——替换、重推、重验
# ============================================================

def img2():
    W, H = 1240, 880
    p = [header(W, H,
                "核心机制：specialize-shape 的三步——替换、重推、重验",
                "上：类型怎么改（值从描述符搬进类型）｜中：outs 为什么由推导说了算｜下：两层重新验证")]

    # ---- 上：类型改写 + 描述符故事 ----
    p.append(txt(40, 92, "① 替换：值从哪里消失、到哪里出现（第 61 天的描述符，今天的类型）：",
                 13.5, INK, bold=True))
    # 左：动态参数的描述符
    p.append(sketch_rect(40, 106, 420, 128, TINT["red"], RED, 2.2))
    p.append(txt(56, 128, "特化前：%a : memref<?x3xf32>", 12, RED, bold=True))
    p.append(txt(56, 150, "值坐在描述符的 sizes[] 里随参数传入（运行期 Shape 参数）：", 10.5, INK))
    p.append(txt(66, 170, "allocated/aligned ptr + offset", 10, MUTED))
    p.append(txt(66, 186, "sizes[2] = {?, 3}   ← ? 的答案在这", 10.5, RED, bold=True))
    p.append(txt(66, 202, "strides[2] = {3, 1}", 10, MUTED))
    p.append(txt(56, 222, "代码里每次用 M：memref.dim %a, %c0（一次运行期读取）", 10.5, INK))
    # 箭头
    p.append(sketch_line(466, 170, 526, 170, stroke=ORANGE, sw=2.6, arrow=True))
    p.append(txt(496, 158, "spec \"a=2x3\"", 10, ORANGE, "middle", bold=True))
    p.append(txt(496, 184, "钉住 dim0=2", 10, ORANGE, "middle"))
    # 右：静态类型
    p.append(sketch_rect(534, 106, 420, 128, TINT["green"], GREEN, 2.2))
    p.append(txt(550, 128, "特化后：%a : memref<2x3xf32>", 12, GREEN, bold=True))
    p.append(txt(550, 150, "值搬进了类型 → 编译进代码当常数：", 10.5, INK))
    p.append(txt(560, 170, "循环上界 %c2（编译期常数，不再是 %dim）", 10.5, GREEN, bold=True))
    p.append(txt(560, 186, "memref.dim 的折叠/消除有了依据", 10, MUTED))
    p.append(txt(560, 202, "full-unroll 可以整层展开（上界已知）", 10, MUTED))
    p.append(txt(550, 222, "sizes[] 里的 2 还在（运行期不撒谎），只是编译期也知道了", 10.5, INK))
    # 最右：替换清单
    p.append(sketch_rect(972, 106, 236, 128, TINT["white"], STROKE, 2.0))
    p.append(txt(988, 128, "替换清单（= 昨天的 bindings）", 11, INK, bold=True))
    p.append(txt(988, 150, "a.dim0 : ? → 2", 10.5, INK))
    p.append(txt(988, 168, "（b 全静态，未动）", 10, MUTED))
    p.append(txt(988, 186, "o.dim0 : ? → 2", 10.5, INK))
    p.append(txt(988, 204, "（o 由重推得出，", 10, MUTED))
    p.append(txt(988, 220, "  不是 spec 直接给的）", 10, MUTED))

    # ---- 中：outs 重推 + K 对账 ----
    p.append(txt(40, 266, "② 重推：outs 的类型不是声明出来的，是推导出来的（matmul 规则）：",
                 13.5, INK, bold=True))
    # 推导规则
    p.append(sketch_rect(40, 280, 560, 150, TINT["white"], STROKE, 2.2))
    p.append(txt(56, 302, "规则（与第 61 天 matmul_shape 同一条）：", 11.5, INK, bold=True))
    p.append(txt(56, 324, "M = %a.dim0 = 2（跟随 spec 后的 a）", 11, GREEN))
    p.append(txt(56, 342, "N = %b.dim1 = 2（b 本来就静态）", 11, GREEN))
    p.append(txt(56, 360, "K 对账：dim(A,1)=3 vs dim(B,0)=3 → 3==3 通过", 11, GREEN))
    p.append(txt(56, 382, "⇒ %o : memref<?x2xf32> → memref<2x2xf32>", 11, INK, bold=True))
    p.append(txt(56, 404, "为什么 o 不让 spec 直接写死：输出维必须跟着输入走——", 10, MUTED))
    p.append(txt(56, 420, "只钉输出不钉输入 = 类型在撒谎（工具会报「没有根据」）", 10, MUTED))
    # 错误 spec 案例
    p.append(sketch_rect(624, 280, 584, 150, TINT["red"], RED, 2.2))
    p.append(txt(640, 302, "错误 spec 的两种死法（都是真实输出）：", 11.5, RED, bold=True))
    p.append(txt(640, 324, "a) spec \"a=2x3,b=3x4\"：", 10.5, INK))
    p.append(txt(654, 341, "错误：%b 的第 1 维已是静态 2，不能改成 4", 10.5, RED))
    p.append(txt(640, 362, "b) spec \"a=2x4,b=3x2\"（k_blind 现场）：", 10.5, INK))
    p.append(txt(654, 379, "错误：K 对不上账：%a 的 dim1=4，%b 的 dim0=3", 10.5, RED))
    p.append(txt(654, 396, "（mini 层 exit=3 拒绝写出；--force 跳过它试试 → 见下）", 10, MUTED))
    p.append(txt(640, 417, "静态维是承诺：特化只能把 ? 变成数，不能改写已有的数", 10.5, INK, bold=True))

    # ---- 下：两层重新验证 ----
    p.append(txt(40, 462, "③ 重验：两层检查，--force 的对照实验（k_blind.mlir 实测）：",
                 13.5, INK, bold=True))
    # 第一层
    p.append(sketch_rect(40, 476, 380, 128, TINT["white"], STROKE, 2.2))
    p.append(txt(56, 498, "第 1 层 · mini 推导器（specialize.py 内置）", 11.5, INK, bold=True))
    p.append(txt(56, 520, "K 对账 + 输出重推时顺带检查", 10.5, INK))
    p.append(txt(56, 538, "快、诊断信息好（中文、指名参数）", 10.5, MUTED))
    p.append(txt(56, 556, "k_blind + a=2x4 → exit=3", 10.5, RED, bold=True))
    p.append(txt(56, 574, "「K 对不上账……（--force 可跳过）」", 10, RED))
    p.append(txt(56, 592, "不写出文件——错误不落地", 10.5, INK))
    # 第二层
    p.append(sketch_rect(444, 476, 380, 128, TINT["white"], STROKE, 2.2))
    p.append(txt(460, 498, "第 2 层 · 外部 Verifier（mlir-opt）", 11.5, INK, bold=True))
    p.append(txt(460, 520, "写出的产物再跑 parse + verify", 10.5, INK))
    p.append(txt(460, 538, "权威、覆盖工具没内置的约束", 10.5, MUTED))
    p.append(txt(460, 556, "k_blind --force → exit=4", 10.5, RED, bold=True))
    p.append(txt(460, 574, "'linalg.matmul' op ... operand #1", 10, RED))
    p.append(txt(460, 590, "  ... dimension #0 to be 4, but found 3", 10, RED))
    # 右侧结论
    p.append(sketch_rect(848, 476, 360, 128, TINT["green"], GREEN, 2.2))
    p.append(txt(864, 498, "关键现象：静态检查网重新点亮", 11.5, GREEN, bold=True))
    p.append(txt(864, 520, "同一份 k_blind.mlir：", 10.5, INK))
    p.append(txt(864, 538, "  M=? 时 exit=0 放行（? 让推断失明）", 10.5, RED))
    p.append(txt(864, 556, "  M 钉成 2 后 exit=1 拦下", 10.5, GREEN))
    p.append(txt(864, 574, "同一处 K 失配（4 vs 3），特化前看不见、", 10.5, INK))
    p.append(txt(864, 590, "特化后当场拦截——重验不是仪式，是防线", 10.5, INK, bold=True))

    p.append(txt(40, 634, "机制小结：spec 只提供「输入侧」的值；输出侧永远由推导重推；两层验证各拦一类错误（mini 拦推导内冲突，mlir-opt 拦一切）。", 12, RED, bold=True))
    p.append(txt(40, 656, "产物语义不变的证据：特化版与动态版都过 verify，dispatch.mlir 里两版对同一输入输出逐位一致（图 4）。", 10.5, MUTED))
    p.append(txt(40, 678, "边界说明：最小工具按「类型字符串」全局替换——不同参数共用同一类型串时无法区分（会报错而不是猜）；只内置 matmul 一条推导规则。", 10.5, MUTED))
    p.append(txt(40, 700, "真实对照参考：torch.compile 的 dynamic=False、TVM 的静态调度、cuDNN 的 heuristic+cache 都是同一件事的工业版。", 10.5, MUTED))
    p.append("</svg>")
    (OUT / "02-mechanism.svg").write_text("\n".join(p), encoding="utf-8")


# ============================================================
# 图 3：实例对照——特化前后的降级 IR 与 k_blind 的两种命运
# ============================================================

def img3():
    W, H = 1240, 880
    p = [header(W, H,
                "实例对照：同一份 MatMul，特化前后降级 IR 的真实差异",
                "上：降 scf 循环（M 的上界从哪来）｜中：三次 full-unroll 后的结局｜下：k_blind 的两种命运")]

    # ---- 上：scf 循环 ----
    p.append(txt(40, 92, "--convert-linalg-to-loops 之后：唯一的差别是 M 的上界从哪来——", 13.5,
                 INK, bold=True))
    # 左：动态
    p.append(sketch_rect(40, 106, 560, 190, TINT["red"], RED, 2.2))
    p.append(txt(56, 128, "动态版（matmul_dyn.mlir，M=?）", 12, RED, bold=True))
    p.append(txt(56, 152, "%dim = memref.dim %arg0, %c0 : memref<?x3xf32>", 11, INK))
    p.append(txt(310, 152, "← 运行期读", 10, RED, bold=True))
    p.append(txt(56, 170, "scf.for %arg3 = %c0 to %dim step %c1 {", 11, INK))
    p.append(txt(310, 170, "← 上界 %dim", 10, RED, bold=True))
    p.append(txt(56, 188, "  scf.for %arg4 = %c0 to %c2 step %c1 {", 11, INK))
    p.append(txt(310, 188, "N=2 常数", 9.5, MUTED))
    p.append(txt(56, 206, "    scf.for %arg5 = %c0 to %c3 step %c1 {", 11, INK))
    p.append(txt(310, 206, "K=3 常数", 9.5, MUTED))
    p.append(txt(56, 224, "      %0 = memref.load %arg0[%arg3, %arg5]", 11, INK))
    p.append(txt(56, 242, "      ...（按描述符寻址）", 10.5, MUTED))
    p.append(txt(56, 264, "指标：memref.dim=1 · scf.for=3 · 23 行", 10.5, RED, bold=True))
    p.append(txt(56, 284, "（输出 220/280/490/640，与手算一致——语义正确）", 10, MUTED))
    # 右：特化
    p.append(sketch_rect(640, 106, 568, 190, TINT["green"], GREEN, 2.2))
    p.append(txt(656, 128, "特化版（matmul_spec.mlir，M=2）", 12, GREEN, bold=True))
    p.append(txt(656, 152, "scf.for %arg3 = %c0 to %c2 step %c1 {", 11, INK))
    p.append(txt(920, 152, "← 上界常数 2", 10, GREEN, bold=True))
    p.append(txt(656, 170, "  scf.for %arg4 = %c0 to %c2 step %c1 {", 11, INK))
    p.append(txt(920, 170, "N=2 常数", 9.5, MUTED))
    p.append(txt(656, 188, "    scf.for %arg5 = %c0 to %c3 step %c1 {", 11, INK))
    p.append(txt(920, 188, "K=3 常数", 9.5, MUTED))
    p.append(txt(656, 206, "      %0 = memref.load %arg0[%arg3, %arg5]", 11, INK))
    p.append(txt(656, 224, "      ...（寻址相同，但上界全静态）", 10.5, MUTED))
    p.append(txt(656, 246, "没有 memref.dim 这一行——M 的知识进了代码", 10.5, GREEN, bold=True))
    p.append(txt(656, 264, "指标：memref.dim=0 · scf.for=3 · 22 行", 10.5, GREEN, bold=True))
    p.append(txt(656, 284, "（同样输出 220/280/490/640——dispatch.mlir 实测逐位一致）", 10, MUTED))

    # ---- 中：unroll 结局 ----
    p.append(txt(40, 330, "--convert-linalg-to-affine-loops + 三次 full-unroll：静态上界才展得开——", 13.5, INK, bold=True))
    p.append(sketch_rect(40, 344, 560, 150, TINT["red"], RED, 2.2))
    p.append(txt(56, 366, "动态版：M 循环展不开", 12, RED, bold=True))
    p.append(txt(56, 390, "%dim = memref.dim %arg0, %c0 : memref<?x3xf32>", 11, INK))
    p.append(txt(56, 408, "affine.for %arg3 = 0 to %dim {", 11, INK))
    p.append(txt(310, 408, "← 卡在这里", 10, RED, bold=True))
    p.append(txt(56, 426, "  （K、N 循环已展开成直码）", 10.5, MUTED))
    p.append(txt(56, 450, "unroll 后：affine.for=1 · load=18 · 55 行 · 2453 B", 10.5, RED, bold=True))
    p.append(txt(56, 472, "运行期才知道的界，展开器无能为力", 10.5, MUTED))
    p.append(sketch_rect(640, 344, 568, 150, TINT["green"], GREEN, 2.2))
    p.append(txt(656, 366, "特化版：全部直码化", 12, GREEN, bold=True))
    p.append(txt(656, 390, "%0 = affine.load %arg0[%c0, %c0]", 11, INK))
    p.append(txt(656, 408, "%1 = affine.load %arg1[%c0, %c1]", 11, INK))
    p.append(txt(656, 426, "%36 = ... （36 个 load 排成直线，零循环）", 11, INK))
    p.append(txt(656, 450, "unroll 后：affine.for=0 · load=36 · 94 行 · 4273 B", 10.5, GREEN, bold=True))
    p.append(txt(656, 472, "注意代价：直码更长（94 行 vs 55 行）——快是有账单的", 10.5, ORANGE, bold=True))

    # ---- 下：k_blind 两结局 ----
    p.append(txt(40, 528, "k_blind.mlir：同一处 K 失配（4 vs 3 都写在类型里），特化前后的两种命运：", 13.5, INK, bold=True))
    p.append(sketch_rect(40, 542, 560, 130, TINT["red"], RED, 2.2))
    p.append(txt(56, 564, "特化前（M=?）——放行", 12, RED, bold=True))
    p.append(txt(56, 588, "$ mlir-opt k_blind.mlir", 10.5, INK))
    p.append(txt(56, 606, "exit=0（无任何诊断）", 11, RED, bold=True))
    p.append(txt(56, 628, "第 61 天的结论重演：类型里混进一个 ?，", 10.5, INK))
    p.append(txt(56, 646, "整套静态推断退化为「什么都推不出」", 10.5, INK))
    p.append(txt(56, 664, "错误去哪了？运行期：越界或垃圾值", 10, MUTED))
    p.append(sketch_rect(640, 542, 568, 130, TINT["green"], GREEN, 2.2))
    p.append(txt(656, 564, "特化后（M 钉成 2）——拦截", 12, GREEN, bold=True))
    p.append(txt(656, 588, "$ python3 specialize.py k_blind.mlir \\", 10.5, INK))
    p.append(txt(668, 604, "--specialize-shape \"a=2x4,b=3x2\" --force ...", 10.5, INK))
    p.append(txt(656, 626, "exit=4：'linalg.matmul' op ... operand #1 has", 10.5, GREEN, bold=True))
    p.append(txt(668, 642, "  shape's dimension #0 to be 4, but found 3", 10.5, GREEN, bold=True))
    p.append(txt(656, 664, "同一处失配，从不可见变成编译期错误", 10.5, INK, bold=True))

    p.append(txt(40, 700, "对照结论：特化的收益不只是「少一次 memref.dim」——它让展开、常量传播、静态检查这些下游能力全部拿到着力点；", 12, RED, bold=True))
    p.append(txt(40, 722, "而代价（94 行 vs 55 行、每 Shape 一份产物）也在同一组数字里。收益与代价是同一枚硬币的两面，不存在免费特化。", 12, RED, bold=True))
    p.append(txt(40, 746, "说明：23/22 行是降 scf 循环后的 IR 行数；55/94 行是三次 full-unroll 后的行数；均为 mlir-opt 18.1.8 实测输出统计。", 10.5, MUTED))
    p.append(txt(40, 768, "对应文件：outputs/matmul_dyn_scf.mlir · outputs/matmul_spec_scf.mlir · outputs/matmul_dyn_unr3.mlir · outputs/matmul_spec_unr3.mlir", 10.5, MUTED))
    p.append("</svg>")
    (OUT / "03-example.svg").write_text("\n".join(p), encoding="utf-8")


# ============================================================
# 图 4：产物数量、编译时间与通用回退
# ============================================================

def img4():
    W, H = 1240, 880
    p = [header(W, H,
                "产物数量、编译时间与通用回退：12 次调用、5 个不同 batch（全实测）",
                "上：轨迹 → 产物库（编译耗时实测）｜中：三种分发策略｜下：dispatch.mlir 三场景真实输出")]

    # ---- 上：轨迹 + 产物库 ----
    p.append(txt(40, 92, "调用轨迹（M）：12 次调用，5 个不同值——产物数量跟着「不同 Shape 数」走，不是调用次数：", 13.5, INK, bold=True))
    trace = [2, 2, 4, 2, 8, 2, 4, 16, 2, 4, 2, 32]
    seen = {}
    for i, m in enumerate(trace):
        x = 40 + i * 66
        first = m not in seen
        seen[m] = True
        fill = TINT["orange"] if first else TINT["green"]
        stroke = ORANGE if first else GREEN
        p.append(sketch_rect(x, 108, 56, 40, fill, stroke, 2.2))
        p.append(txt(x + 28, 126, f"M={m}", 11, INK, "middle", bold=True))
        p.append(txt(x + 28, 141, "首见" if first else "命中", 9.5,
                     ORANGE if first else GREEN, "middle"))
    p.append(txt(40, 172, "首见（橙）→ 触发一次特化编译；重复（绿）→ 直接用缓存里的产物", 10.5, MUTED))

    # 产物库
    p.append(txt(40, 202, "产物库 = 5 份特化 + 1 份通用回退 = 6 个产物（编译耗时：--convert-linalg-to-loops，中位数×3，实测）：", 13.5, INK, bold=True))
    prods = [
        ("spec_M2", "18.0 ms", "1275 B"),
        ("spec_M4", "18.5 ms", "1275 B"),
        ("spec_M8", "18.8 ms", "1275 B"),
        ("spec_M16", "18.6 ms", "1279 B"),
        ("spec_M32", "18.8 ms", "1279 B"),
        ("generic", "18.9 ms", "1275 B"),
    ]
    bw = 186
    for i, (name, ms, size) in enumerate(prods):
        x = 40 + i * (bw + 8)
        generic = name == "generic"
        fill = TINT["blue"] if generic else TINT["white"]
        stroke = BLUE if generic else STROKE
        p.append(sketch_rect(x, 216, bw, 64, fill, stroke, 2.4))
        p.append(txt(x + bw / 2, 236, name + ("（回退）" if generic else ""),
                     11.5, BLUE if generic else INK, "middle", bold=True))
        p.append(txt(x + bw / 2, 254, f"编译 {ms}", 10.5, INK, "middle"))
        p.append(txt(x + bw / 2, 270, f"{size} · verify exit=0 · dim="
                     + ("1" if generic else "0"), 9.5, MUTED, "middle"))
    p.append(txt(40, 298, "特化编译总耗时 92.7 ms + 通用 18.9 ms ≈ 111.7 ms；全部通过验证；特化产物 memref.dim=0，通用版=1", 10.5, MUTED))

    # ---- 中：三策略 ----
    p.append(txt(40, 330, "三种分发策略（编译耗时为实测值，命中/回退次数由轨迹推演）：", 13.5, INK, bold=True))
    p.append(sketch_rect(40, 344, 1168, 148, TINT["white"], STROKE, 2.2))
    cols = [("策略", 60), ("编译次数", 300), ("编译总耗时", 400), ("服务期行为", 520)]
    p.append(txt(60, 366, "策略", 11.5, INK, bold=True))
    p.append(txt(310, 366, "编译次数", 11.5, INK, bold=True))
    p.append(txt(420, 366, "编译总耗时", 11.5, INK, bold=True))
    p.append(txt(540, 366, "服务期行为", 11.5, INK, bold=True))
    p.append(sketch_line(56, 376, 1192, 376, stroke=TINT["gray"], sw=1.5))
    rows = [
        ("A 全通用（不特化）", "1", "18.9 ms",
         "12 次调用都带 memref.dim + 运行期 K 检查；零编译延迟，每次都付运行期开销", TINT["gray"]),
        ("B miss 时 JIT 特化", "6", "111.7 ms",
         "5 次首见触发编译（约 19 ms 延迟尖峰）+ 7 次命中；用一次编译换后续全部命中", TINT["orange"]),
        ("C 预编译出现过的 Shape", "6", "111.7 ms",
         "编译全在启动前完成，服务期 12 次全命中；但「预编译所有 Shape」不可能——M 无上界", TINT["blue"]),
    ]
    for i, (name, n, ms, note, tint) in enumerate(rows):
        y = 396 + i * 34
        if tint != TINT["white"]:
            p.append(sketch_rect(52, y - 16, 1144, 30, tint, tint, 1.2, nseg=4))
        p.append(txt(60, y + 4, name, 11, INK, bold=True))
        p.append(txt(310, y + 4, n + " 次", 11, INK))
        p.append(txt(420, y + 4, ms, 11, INK))
        p.append(txt(540, y + 4, note, 10, INK))

    # ---- 下：dispatch 三场景 ----
    p.append(txt(40, 520, "dispatch.mlir 真实执行（cpu-runner）：三场景，每场景先打 [hit 标志][M] 再打结果——", 13.5, INK, bold=True))
    scenes = [
        ("场景 1 · A(2,3)×B 经 dispatch_v1", "1  2", "220  280  490  640",
         "命中 spec_2_3_2（缓存里唯一一份）", TINT["green"], GREEN),
        ("场景 2 · A2(4,3)×B 经 dispatch_v1", "0  4",
         "220 280 490 640 760 1000 1030 1360",
         "未命中 → 回退 generic（带运行期 K 检查）", TINT["red"], RED),
        ("场景 3 · 同一份数据经 dispatch_v2", "1  4",
         "220 280 490 640 760 1000 1030 1360",
         "缓存长出 spec_4_3_2 后再命中（JIT 之后）", TINT["green"], GREEN),
    ]
    for i, (title, hm, vals, note, fill, stroke) in enumerate(scenes):
        x = 40 + i * 396
        p.append(sketch_rect(x, 534, 380, 128, fill, stroke, 2.4))
        p.append(txt(x + 16, 556, title, 11, stroke, bold=True))
        p.append(txt(x + 16, 578, "stdout: " + hm, 11.5, INK, bold=True))
        p.append(txt(x + 16, 598, "   " + vals, 10, INK))
        p.append(txt(x + 16, 640, note, 10, MUTED))
    p.append(txt(40, 690, "场景 2 与场景 3 的 8 个值逐位一致：通用版和特化版对同一输入算出同一结果——特化语义保持的直接证据；", 12, RED, bold=True))
    p.append(txt(40, 712, "场景 3 之前的踩坑记录：outs 是累加语义，重放前忘了清零，真实跑出过恰好两倍的 440/560/980/...（已修复，见 6.4）。", 12, ORANGE, bold=True))
    p.append(txt(40, 736, "结论：特化的收益跟着「调用次数 × 每次省的开销」走，代价跟着「不同 Shape 数 × 每份编译时间」走；", 12, RED, bold=True))
    p.append(txt(40, 758, "M 的取值没有上界 ⇒ 不可能预编译所有 Shape ⇒ 通用回退不是优化，是正确性的一部分（删掉它，没见过的 Shape 无路可走）。", 12, RED, bold=True))
    p.append(txt(40, 782, "实测环境：Linux aarch64 · Python 3.11.4 · Ubuntu LLVM 18.1.8 · products_lab 8/8 · test_specialize 28/28（F 段与 numpy 对拍）", 10.5, MUTED))
    p.append("</svg>")
    (OUT / "04-products.svg").write_text("\n".join(p), encoding="utf-8")


if __name__ == "__main__":
    img1()
    img2()
    img3()
    img4()
    for f in sorted(OUT.glob("*.svg")):
        import xml.etree.ElementTree as ET
        ET.parse(f)
        print(f"OK {f.name}  {f.stat().st_size} B")
