#!/usr/bin/env python3
"""make_images.py —— 第 61 天教程的四张手绘 sketch 风 SVG 信息图。

风格约定（与第 8/9 周各天一致）：
  - 背景 #fdfaf2（米白），盒子白底 + 深灰 #6b6357 手绘描边
  - 强调色不超过 4 种柔和色：蓝 #4a7fa5 / 橙 #a8772e / 绿 #5a8a5a / 红 #b0605a
  - 线条带轻微抖动（L 段折线），圆头笔触，线宽 2 左右
  - 手写感字体栈：Comic Sans MS / Comic Neue / Kaiti SC / 楷体 / cursive

图中全部数字来自 2026-11-12 的真实运行：
  dynamic_lab.py 16/16、test_dynamic.py 41/41（判定表 12/12、随机 500 组
  ok=129 error=371 零崩溃、numpy 对拍逐位一致）、
  mlir-opt 放行 8 房间 generated_dynamic_tests（M/N/K 静态-动态全组合）、
  --convert-linalg-to-loops 降出 memref.dim（M/K/N 运行期读，K 只读 A）、
  cpu-runner 真实执行 220/280/490/640、
  k_hazard 越界现场 1.44752e+28 / 100 / 2.89504e+28 / 280（exit=0）、
  k_check 有检查现场 stdout=220+matmul: K dims must match（abort exit=134）、
  canonicalize 把静态约束链整体折没、动态约束链保留、
  --convert-shape-constraints 物化出 cf.assert、
  bad_dynamic 三房间：秩拦截 / 静态拦截（inferred 4 but found 3）/ ? 失明放行。

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

rng = random.Random(61)


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
    d = f"M {x0:.1f},{y0:.1f} L {x1:.1f},{y1:.1f}"
    out = [f'<path d="{d}" fill="none" stroke="{stroke}" '
           f'stroke-width="{sw}" stroke-linecap="round" '
           f'stroke-linejoin="round"/>']
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
# 图 1：全貌——第 61 天在六阶段与第 9 周中的位置
# ============================================================

def img1():
    W, H = 1240, 790
    p = [header(W, H,
                "第 61 天全貌：动态 Shape 表示——? 是「还不知道」，不是「怎么都行」",
                "上：六阶段里程碑与第 9 周日程（今天第 5 天）｜中：昨天到今天的衔接｜下：动态维度在编译链路各站的待遇")]

    # ---- 上：里程碑 ----
    p.append(txt(40, 92, "168 天六阶段（今天是阶段三·第 9 周的第 5 天）：", 13.5,
                 INK, bold=True))
    miles = [
        ("阶段一\nC++/编译器基础", "Day 1-28", TINT["white"], STROKE, MUTED),
        ("阶段二\nMLIR 核心能力", "Day 29-56", TINT["white"], STROKE, MUTED),
        ("阶段三\n计算图与图优化\n(进行中)", "Day 57-84", TINT["orange"], ORANGE, ORANGE),
        ("阶段四\nLowering/性能", "Day 85-112", TINT["white"], STROKE, MUTED),
        ("阶段五\n端到端/Runtime", "Day 113-140", TINT["white"], STROKE, MUTED),
        ("阶段六\n综合项目", "Day 141-168", TINT["white"], STROKE, MUTED),
    ]
    mw, mh, gap = 180, 74, 12
    for i, (t, d, fill, sc, tc) in enumerate(miles):
        x = 40 + i * (mw + gap)
        p.append(sketch_rect(x, 104, mw, mh, fill, sc,
                             2.6 if i == 2 else 1.8, 5))
        lines = t.split("\n")
        for k, line in enumerate(lines):
            p.append(txt(x + mw / 2, 122 + k * 16, line, 11.5, tc,
                         "middle", bold=(i == 2)))
        p.append(txt(x + mw / 2, 122 + len(lines) * 16 + 8, d, 10.5, MUTED,
                     "middle"))

    # 第 9 周日程
    p.append(txt(40, 214, "第 9 周（Shape/Layout 语义周）的日程：", 13.5, INK,
                 bold=True))
    week = [
        ("Day 57", "Shape / Stride /\nOffset / Contiguous\n四件套词汇表",
         TINT["white"], STROKE, MUTED),
        ("Day 58", "NCHW vs NHWC：\n两套 Strides 各成全\n哪类访问模式",
         TINT["white"], STROKE, MUTED),
        ("Day 59", "Reshape 合法性：\n零拷贝 vs 搬家",
         TINT["white"], STROKE, MUTED),
        ("Day 60", "Broadcast 规则：\n右对齐 · 扩展 ·\n未知维度 None",
         TINT["white"], STROKE, MUTED),
        ("Day 61", "动态 Shape 表示：\n静态 / 符号 Sym / 未知 ?\n＋运行期 Shape 参数\n（今天）",
         TINT["orange"], ORANGE, ORANGE),
        ("Day 62+", "静态 Shape 特化 /\n复盘……",
         TINT["white"], STROKE, MUTED),
    ]
    cw2, ch2 = 180, 96
    for i, (d, body, fill, sc, tc) in enumerate(week):
        x = 40 + i * (cw2 + 12)
        p.append(sketch_rect(x, 228, cw2, ch2, fill, sc, 2.6 if i == 4 else 1.8, 5))
        p.append(txt(x + 12, 250, d, 12.5, tc, bold=True))
        for k, line in enumerate(body.split("\n")):
            p.append(txt(x + 12, 270 + k * 16, line, 10.5, INK))
        if i < 5:
            p.append(sketch_line(x + cw2 + 1, 228 + ch2 / 2, x + cw2 + 11,
                                 228 + ch2 / 2, MUTED, 1.8, arrow=True))

    # ---- 中：衔接卡片 ----
    p.append(txt(40, 362, "昨天到今天：把 None 从「推导规则里的一个记号」升级成「带约束的表示」",
                 14, INK, bold=True))
    cards = [
        ("第 57-60 天打好的地基", "偏移公式 Σ idx×stride、\nreshape 的零拷贝判定、\nbroadcast 的 meet 规则：\n「运行期必须是 d 或 1」只是句口头约束",
         TINT["white"], STROKE, MUTED),
        ("第 61 天要回答的", "None 升级成 Sym（有名字的未知）\n和 None（无身份的未知）；\n「两个 K 运行期必须相等」怎么变成\nIR 里可检查的约束？",
         TINT["blue"], BLUE, BLUE),
        ("后续谁要用它", "Day 62 形状特化：bindings 表\n就是特化的替换清单；\nDay 128+ 运行期 Shape 参数、\n特化产物与通用回退",
         TINT["white"], STROKE, MUTED),
    ]
    cx, cy, cw3, ch3 = 40, 380, 373, 124
    for i, (t, body, fill, sc, tc) in enumerate(cards):
        x = cx + i * (cw3 + 17)
        p.append(sketch_rect(x, cy, cw3, ch3, fill, sc, 2.4, 5))
        p.append(txt(x + 14, cy + 24, t, 12.5, tc, bold=True))
        for k, line in enumerate(body.split("\n")):
            p.append(txt(x + 14, cy + 48 + k * 19, line, 10.5, INK))
        if i < 2:
            p.append(sketch_line(x + cw3 + 1, cy + ch3 / 2,
                                 x + cw3 + 16, cy + ch3 / 2, MUTED, 1.8,
                                 arrow=True))

    # ---- 下：编译链路 ----
    p.append(txt(40, 548, "动态维度在编译链路各站的待遇（今天用真实 mlir-opt / mlir-cpu-runner 逐站验证）：",
                 13.5, INK, bold=True))
    lx, ly, lw2, lh2 = 40, 564, 360, 118
    p.append(sketch_rect(lx, ly, lw2, lh2, "#ffffff", STROKE, 2.0, 5))
    p.append(txt(lx + 14, ly + 22, "类型层：? 写在 IR 类型里", 12, BLUE, bold=True))
    p.append(txt(lx + 14, ly + 45, "memref<?x3xf32> / tensor<?x?xf32>", 11, INK))
    p.append(txt(lx + 14, ly + 63, "Verifier 静态对账：静态维直接比，", 11, INK))
    p.append(txt(lx + 14, ly + 80, "  ? 躲开比较——一个 ? 让整张检查网失明", 11, RED))
    p.append(txt(lx + 14, ly + 103, "→ 房间 2 拦 / 房间 3 放行（实测）", 10.5, MUTED))
    x2 = lx + lw2 + 30
    p.append(sketch_line(x2 - 26, ly + lh2 / 2, x2 - 4, ly + lh2 / 2,
                         ORANGE, 2.4, arrow=True))
    p.append(sketch_rect(x2, ly, lw2, lh2, TINT["orange"], ORANGE, 2.4, 5))
    p.append(txt(x2 + 14, ly + 22, "推导层：三种表示三档约束", 12, ORANGE, bold=True))
    p.append(txt(x2 + 14, ly + 45, "静态 int → 直接对账", 11, INK))
    p.append(txt(x2 + 14, ly + 63, "Sym ?s → bindings / renames 表", 11, INK))
    p.append(txt(x2 + 14, ly + 80, "None ? → 运行期约束（cf.assert 原料）", 11, INK))
    p.append(txt(x2 + 14, ly + 103, "→ mini.matmul：12 判定 + 500 组压力零崩溃", 10.5, MUTED))
    x3 = x2 + lw2 + 30
    p.append(sketch_line(x3 - 26, ly + lh2 / 2, x3 - 4, ly + lh2 / 2,
                         GREEN, 2.4, arrow=True))
    p.append(sketch_rect(x3, ly, 1240 - 40 - x3, lh2, "#ffffff", GREEN, 2.0, 5))
    p.append(txt(x3 + 14, ly + 22, "运行层：Shape 是参数", 12, GREEN, bold=True))
    p.append(txt(x3 + 14, ly + 45, "循环上界 = memref.dim（运行期读）", 11, INK))
    p.append(txt(x3 + 14, ly + 63, "有检查：assert 触发 abort=134", 11, INK))
    p.append(txt(x3 + 14, ly + 80, "没检查：静默读越界吐垃圾值 exit=0", 11, RED))
    p.append(txt(x3 + 14, ly + 103, "→ cpu-runner 实测 220/280/490/640", 10.5, MUTED))

    p.append(txt(40, 716, "实测环境（全部真实运行）：Linux aarch64 · Python 3.11.4 · "
                          "numpy 1.26.4 · Ubuntu LLVM 18.1.8（mlir-opt + mlir-cpu-runner）",
                 11, MUTED))
    p.append(txt(40, 738, "今日战绩：dynamic_lab 16/16 · test_dynamic 41/41（判定表 12/12 · "
                          "随机 500 组 ok=129 error=371 零崩溃 · numpy 对拍逐位一致）", 11, MUTED))
    p.append(txt(40, 760, "MLIR 六连：8 房间放行 · memref.dimm 降级 · 220/280/490/640 真实执行 · "
                          "静态约束折叠 / 动态约束保留 · cf.assert 物化 · 事故现场两组", 11, MUTED))
    p.append("</svg>")
    (OUT / "01-overview.svg").write_text("\n".join(p), encoding="utf-8")


# ============================================================
# 图 2：核心机制——三种表示 + K 对账 + 运行期描述符
# ============================================================

def img2():
    W, H = 1240, 900
    p = [header(W, H,
                "核心机制：三种表示各允诺什么 → K 对账走哪一档 → 运行期 Shape 从哪读",
                "上：静态 int / Sym / None 三档允诺对照｜中：K 对账的四条分支（判定表背后）｜下：memref<?x3xf32> 的运行期真身")]

    # ---- 上：三种表示 ----
    p.append(txt(40, 92, "维度的三种表示——允诺从强到弱（mini 的约定，MLIR 里前两种都写成 ?）：",
                 13.5, INK, bold=True))
    reps = [
        ("静态 int（如 3）", BLUE,
         "允诺：编译期就知道值是 3，\nVerifier 直接对账。\n失配当场报错（房间 2 实测：\ninferred 4, but found 3）。", TINT["blue"]),
        ("符号 Sym（如 ?k）", ORANGE,
         "允诺：不知道值，但有名字。\n同名 = 运行期必须同值；\n碰上静态值 → 绑定（?k==3）；\n两个名字 → 改名统一。", TINT["orange"]),
        ("未知 None（如 ?）", RED,
         "允诺最弱：不知道值、没有身份，\n值由运行期实际输入决定。\nM/N 透传=任意合法值都行；\nK 对上 K → 仍隐含相等约束！", TINT["red"]),
    ]
    rw, rh = 373, 116
    for i, (t, c, body, fill) in enumerate(reps):
        x = 40 + i * (rw + 17)
        p.append(sketch_rect(x, 106, rw, rh, fill, c, 2.2, 5))
        p.append(txt(x + 14, 128, t, 12.5, c, bold=True))
        for k, line in enumerate(body.split("\n")):
            p.append(txt(x + 14, 150 + k * 17, line, 10.5, INK))

    p.append(txt(40, 244, "关键区分：M 的 ?（batch 维）是「任意」——函数对它通用；K 的 ? 是「未知但受约束」——两个 ? 必须相等。",
                 12, RED, bold=True))

    # ---- 中：K 对账四分支 ----
    p.append(txt(40, 282, "matmul_shape 的 K 对账（A 的 dim1 对 B 的 dim0），四条分支：",
                 13.5, INK, bold=True))
    steps = [
        ("① 静态 vs 静态", GREEN, "3 vs 3 → 对上，过\n3 vs 4 → ShapeError：\n「K 对不上——\ndim(A,1)=3，dim(B,0)=4」\n（mini 比实测的 MLIR 更严）", TINT["green"]),
        ("② 符号 vs 静态", ORANGE, "?k vs 3 → bindings[k]=3\n编译期成立、特化可替换\n（Day 62 的入口）；\n图里再遇 4 → 绑定冲突报错", TINT["orange"]),
        ("③ 符号 vs 符号", BLUE, "?k1 vs ?k2 → renames:\nk2→k1，两个名字一个未知；\n同名 → 什么都不记\n（相等性由「同一个名字」承载）", TINT["blue"]),
        ("④ 涉及 None → 运行期", RED, "runtime 记下等式：\ndim(A,1) == dim(B,0)\n编译期对不了账——\n它要么变成 cf.assert，\n要么被无视（事故现场）", TINT["red"]),
    ]
    sw_, sh_ = 278, 128
    for i, (t, c, body, fill) in enumerate(steps):
        x = 40 + i * (sw_ + 22)
        p.append(sketch_rect(x, 296, sw_, sh_, fill, c, 2.4, 5))
        p.append(txt(x + 14, 318, t, 12.5, c, bold=True))
        for k, line in enumerate(body.split("\n")):
            p.append(txt(x + 14, 340 + k * 17, line, 10.5, INK))

    # ---- 下：运行期描述符 ----
    p.append(txt(40, 462, "「运行期 Shape 参数」的真身：memref<?x3xf32> 在机器层面是一个描述符（descriptor）：",
                 13.5, INK, bold=True))
    p.append(sketch_rect(40, 478, 520, 128, "#ffffff", STROKE, 2.2, 5))
    p.append(txt(56, 500, "函数参数 %a : memref<?x3xf32>，运行期实际收到：", 11.5, INK))
    cells = [("allocated ptr", "指向数据首地址", BLUE, TINT["blue"]),
             ("aligned ptr", "对齐后的地址（第 57 天）", BLUE, TINT["blue"]),
             ("offset", "0", MUTED, TINT["gray"]),
             ("sizes[2]", "? 的值放这里！比如 5", RED, TINT["red"]),
             ("strides[2]", "3, 1（其余维静态可推）", GREEN, TINT["green"])]
    for i, (name, note, c, fill) in enumerate(cells):
        y = 516 + 0
        x = 56 + (i % 2) * 250
        yy = 522 + (i // 2) * 32
        p.append(sketch_rect(x, yy - 16, 118, 24, fill, c, 1.5, 3))
        p.append(txt(x + 59, yy, name, 10.5, c, "middle", bold=True))
        p.append(txt(x + 126, yy, note, 10, MUTED))
    p.append(txt(56, 598, "静态维（3、1）在类型里，编译进代码；动态维（?）坐在描述符的 sizes[] 里，",
                 10.5, MUTED))
    p.append(txt(56, 616, "memref.dim 就是往这里伸手——这就是「运行期 Shape 参数」四个字在机器上的样子。",
                 10.5, MUTED))

    # 右下：降级后的循环
    p.append(sketch_rect(596, 478, 604, 128, "#ffffff", GREEN, 2.2, 5))
    p.append(txt(612, 500, "--convert-linalg-to-loops 之后（真实 IR，matmul_dynamic.mlir）：", 11.5,
                 GREEN, bold=True))
    code = [
        ("%dim = memref.dim %arg0, %c0 : memref<?x3xf32>", "M 运行期读"),
        ("scf.for %arg3 = %c0 to %dim step %c1 {", "上界是 %dim"),
        ("  scf.for %arg4 = %c0 to %c2 step %c1 {", "N=2 编译期常数"),
        ("    scf.for %arg5 = %c0 to %c3 step %c1 {", "K=3 编译期常数"),
        ("      %0 = memref.load %arg0[%arg3, %arg5]", "按描述符寻址"),
        ("      ... 三重循环算一个乘加", ""),
    ]
    for i, (line, note) in enumerate(code):
        p.append(txt(612, 524 + i * 18, line, 10.5, INK))
        if note:
            p.append(txt(960, 524 + i * 18, note, 10, RED if i < 2 else MUTED))
    p.append(txt(612, 636, "全动态时 K 上界只从 A 读（%dim_0 = dim %arg0, %c1）——B 的 K 没人查：缺口的源头。",
                 10.5, RED))

    p.append(txt(40, 646, "", 11))
    p.append(txt(40, 668, "对账结论（判定表 12/12 + 500 组压力实测）：编译期能结清的只有 ①②③ 三档；",
                 12, RED, bold=True))
    p.append(txt(40, 690, "第 ④ 档的等式没有消失——它要么被物化成运行期检查（cf.assert），要么变成没人管的隐患。",
                 12, RED, bold=True))
    p.append(txt(40, 714, "mini 的三档约束（bindings / renames / runtime）正好对应「特化清单 / 同一未知 / 检查原料」三种后续用途。",
                 11, MUTED))
    p.append(txt(40, 738, "边界说明：MLIR 的 ? 写不出「符号」与「未知」的区别（都是 ?），所以才有 shape dialect 的 witness——图 4。",
                 11, MUTED))
    p.append(txt(40, 762, "实测环境：Linux aarch64 · Python 3.11.4 · numpy 1.26.4 · Ubuntu LLVM 18.1.8 · "
                          "dynamic_lab 16/16 · test_dynamic 41/41", 11, MUTED))
    p.append("</svg>")
    (OUT / "02-mechanism.svg").write_text("\n".join(p), encoding="utf-8")


# ============================================================
# 图 3：实例对照——判定表、两种事故现场与三种待遇
# ============================================================

def img3():
    W, H = 1240, 980
    p = [header(W, H,
                "实例对照：同一处 K 失配，三种待遇；有检查与无检查，两种命运",
                "上：mini 判定表（真实输出节选）｜中：bad_dynamic 三房间实测｜下：k_hazard 与 k_check 的运行期现场")]

    # ---- 上：判定表 ----
    p.append(txt(40, 92, "mini.matmul 判定表（12/12，节选；真实输出见 outputs/dynamic_lab.txt）：",
                 13.5, INK, bold=True))
    cols = [(40, "用例"), (215, "A"), (365, "B"), (515, "输出"), (680, "约束去向")]
    p.append(sketch_rect(40, 100, 1160, 26, TINT["gray"], STROKE, 1.6, 4))
    for x, t in cols:
        p.append(txt(x + 6, 118, t, 11.5, MUTED, bold=True))
    rows = [
        ("J1 全静态", "(2, 3)", "(3, 2)", "(2, 2)", "无——编译期对完账", GREEN),
        ("J2 M 未知", "(None, 3)", "(3, 2)", "(None, 2)", "无——M 任意", GREEN),
        ("J4 K 一边未知", "(2, None)", "(3, 2)", "(2, 2)", "runtime: dim(A,1)==dim(B,0)", ORANGE),
        ("J5 K 双未知", "(None, None)", "(None, 2)", "(None, 2)", "runtime: 同上（输出照样带 ?）", ORANGE),
        ("J8 K 符号对静态", "(2, ?k)", "(3, 2)", "(2, 2)", "bindings: k=3（可特化）", BLUE),
        ("J10 K 双符号异名", "(2, ?k1)", "(?k2, 2)", "(2, 2)", "renames: k2→k1", BLUE),
        ("J11 K 未知对符号", "(2, None)", "(?k, 2)", "(2, 2)", "runtime: dim(A,1)==dim(B,0)", ORANGE),
        ("J12 静态失配", "(2, 3)", "(4, 2)", "ShapeError", "「K 对不上——dim(A,1)=3, dim(B,0)=4」", RED),
    ]
    for i, (a, b, c, d, e, col) in enumerate(rows):
        y = 130 + i * 30
        p.append(sketch_rect(40, y, 1160, 26, "#ffffff", STROKE, 1.2, 3))
        p.append(txt(46, y + 19, a, 11, INK))
        p.append(txt(221, y + 19, b, 11, INK))
        p.append(txt(371, y + 19, c, 11, INK))
        p.append(txt(521, y + 19, d, 11, RED if d == "ShapeError" else BLUE))
        p.append(txt(686, y + 19, e, 10.5, col))

    # ---- 中：bad_dynamic 三房间 ----
    p.append(txt(40, 400, "同一处静态 K 失配（4 vs 3），三种待遇（bad_dynamic.mlir 逐房间实测）：",
                 13.5, INK, bold=True))
    rooms = [
        ("房间 1：秩错误", GREEN, "memref<?xf32> 喂 matmul\nexit=1，Verifier 拦截：\n「expected operand rank (1) to\nmatch the result rank of\nindexing_map #0 (2)」", TINT["green"]),
        ("房间 2：K 失配 + M 静态", GREEN, "memref<2x4xf32> × memref<3x2xf32>\nexit=1，Verifier 拦截：\n「operand #1 has shape's\ndimension #0 to be 4,\nbut found 3」", TINT["green"]),
        ("房间 3：K 失配 + M 动态", RED, "memref<?x4xf32> × memref<3x2xf32>\nexit=0，Verifier 放行！\n4 和 3 都明明白白写在类型里，\n但一个 ? 让整张静态检查网失明。\ntensor 版同样 exit=0。", TINT["red"]),
    ]
    rw, rh = 373, 130
    for i, (t, c, body, fill) in enumerate(rooms):
        x = 40 + i * (rw + 17)
        p.append(sketch_rect(x, 414, rw, rh, fill, c, 2.2, 5))
        p.append(txt(x + 14, 436, t, 12.5, c, bold=True))
        for k, line in enumerate(body.split("\n")):
            p.append(txt(x + 14, 458 + k * 17, line, 10.5, INK))

    # ---- 下：两个运行期现场 ----
    p.append(txt(40, 580, "房间 3 放走的错误，运行期是什么下场（cpu-runner 真实执行，数据 A(2,3) 配错行数的 B）：",
                 13.5, INK, bold=True))
    p.append(sketch_rect(40, 596, 566, 150, "#ffffff", RED, 2.4, 5))
    p.append(txt(56, 618, "k_hazard.mlir：没有检查（exit=0，静默事故）", 12, RED, bold=True))
    p.append(txt(56, 642, "A(2,3) × B(2,2)：K 上界从 A 读出 3，", 11, INK))
    p.append(txt(56, 660, "第 3 步读 B[2,j] —— B 只有两行，越界。", 11, INK))
    p.append(txt(56, 684, "真实输出：1.44752e+28 / 100 / 2.89504e+28 / 280", 11, RED, bold=True))
    p.append(txt(56, 706, "合法答案本该是 220 / 280 / 490 / 640 —— 垃圾值混进来，退出码 0。", 10.5, MUTED))
    p.append(txt(56, 728, "「未知 ≠ 任意」的学费：没人检查的约束不会自动成立。", 11, RED))

    p.append(sketch_rect(634, 596, 566, 150, "#ffffff", GREEN, 2.4, 5))
    p.append(txt(650, 618, "k_check.mlir：装上 cf.assert（exit=134，响亮失败）", 12, GREEN, bold=True))
    p.append(txt(650, 642, "同一份数据：%ka = memref.dim %a, 1；%kb = memref.dim %b, 0", 10.5, INK))
    p.append(txt(650, 660, "cf.assert %eq, \"matmul: K dims must match\"", 11, GREEN))
    p.append(txt(650, 684, "真实输出：220（第一次调用合法，检查放行）", 11, INK))
    p.append(txt(650, 702, "          matmul: K dims must match（第二次调用，abort）", 11, GREEN, bold=True))
    p.append(txt(650, 728, "降级 IR 里消息文本是 puts(@assert_msg)+abort()——检查确定触发。", 10.5, MUTED))

    p.append(txt(40, 776, "结论：同一个错误，三种命运——静态拦住（房间 2）/ 运行期拦住（k_check）/ 无声滑过（k_hazard）。",
                 12.5, RED, bold=True))
    p.append(txt(40, 798, "选哪种不是编译器「能不能」的问题，而是「约束有没有被写下来」的问题：推导层记的 runtime 等式，就是检查的唯一原料。",
                 11, INK))
    p.append(txt(40, 822, "对照：mini 的 simulate(checked=True/False) 复现了同样的两种命运（RuntimeShapeError vs 静默算完）。",
                 11, MUTED))
    p.append(txt(40, 846, "实测环境：Linux aarch64 · Python 3.11.4 · Ubuntu LLVM 18.1.8 · "
                          "cpu-runner 两次真实执行 · 判定表 12/12 · 压力 500 组零崩溃", 11, MUTED))
    p.append("</svg>")
    (OUT / "03-example.svg").write_text("\n".join(p), encoding="utf-8")


# ============================================================
# 图 4：witness 约束链——折叠 / 保留 / 物化
# ============================================================

def img4():
    W, H = 1240, 880
    p = [header(W, H,
                "把口头约束写进 IR：witness 链的折叠（静态）、保留（动态）与物化（cf.assert）",
                "上：约束链六个环节｜中：canonicalize 的两种结局｜下：三房间实测证据串")]

    # ---- 上：约束链 ----
    p.append(txt(40, 92, "shape dialect 怎么表达「两个 K 运行期必须相等」（k_constraint.mlir 房间 2）：",
                 13.5, INK, bold=True))
    chain = [
        ("① shape.shape_of\n%a → !shape.shape", "把形状取出来"),
        ("② shape.get_extent\n%sa, 1 → !shape.size", "取 A 的 K（第 1 维）"),
        ("③ size_to_index\n→ index", "转成 index 参与比较"),
        ("④ arith.cmpi eq\n%ia, %ib", "两维相等吗？"),
        ("⑤ shape.cstr_require\n%eq, \"K dims...\"", "约束：必须成立！"),
        ("⑥ shape.assuming\n%w { matmul }", "成立才执行的区域"),
    ]
    cwid = 178
    for i, (t, note) in enumerate(chain):
        x = 40 + i * (cwid + 12)
        c = [BLUE, BLUE, BLUE, GREEN, RED, ORANGE][i]
        fill = [TINT["blue"], TINT["blue"], TINT["blue"], TINT["green"],
                TINT["red"], TINT["orange"]][i]
        p.append(sketch_rect(x, 108, cwid, 74, fill, c, 2.0, 4))
        p.append(txt(x + 8, 128, t, 10.5, c, bold=True))
        p.append(txt(x + 8, 158, note, 10, INK))
        if i < 5:
            p.append(sketch_line(x + cwid + 1, 145, x + cwid + 10, 145,
                                 MUTED, 1.6, arrow=True))

    # ---- 中：两种结局 ----
    p.append(txt(40, 214, "--canonicalize 的两种结局（真实输出，outputs/k_constraint_canon.mlir）：",
                 13.5, INK, bold=True))
    p.append(sketch_rect(40, 228, 566, 168, TINT["green"], GREEN, 2.4, 5))
    p.append(txt(56, 252, "静态房间 @static_ok（A<2x3>、B<3x2>）：整条链消失", 12, GREEN, bold=True))
    p.append(txt(56, 276, "shape_of → const_shape [2,3] / [3,2]", 11, INK))
    p.append(txt(56, 294, "get_extent → 常数 3 / 3；cmpi → true", 11, INK))
    p.append(txt(56, 312, "cstr_require → const_witness true", 11, INK))
    p.append(txt(56, 330, "assuming(true) → 区域原地展开", 11, INK))
    p.append(txt(56, 356, "函数体只剩 linalg.matmul——约束编译期结清，运行期零开销", 11, GREEN, bold=True))

    p.append(sketch_rect(634, 228, 566, 168, TINT["orange"], ORANGE, 2.4, 5))
    p.append(txt(650, 252, "动态房间 @dynamic_checked（A<?x?>、B<?x?>）：整条链保留", 12, ORANGE, bold=True))
    p.append(txt(650, 276, "%0 = shape.shape_of %arg0 : tensor<?x?xf32> → tensor<2xindex>", 10.5, INK))
    p.append(txt(650, 294, "%6 = arith.cmpi eq, %4, %5 : index", 11, INK))
    p.append(txt(650, 312, "%7 = shape.cstr_require %6, \"matmul: K dims must match\"", 10.5, RED))
    p.append(txt(650, 330, "%8 = shape.assuming %7 { ... matmul ... }", 11, INK))
    p.append(txt(650, 356, "形状来自参数——等式编译期结不清，留到运行期当检查", 11, ORANGE, bold=True))

    # ---- 下：证据串 ----
    p.append(txt(40, 430, "约束的三种存在形态（全部真实运行）：", 13.5, INK, bold=True))
    ev = [
        ("① canonicalize：静态折叠", GREEN,
         "@static_ok 全部约束链 + assuming 整体消失\n函数体只剩一行 linalg.matmul\n——第 60 天那句口头约束\n「运行期必须是 d 或 1」今天长成了\nIR 里可折叠、可检查的 witness"),
        ("② canonicalize：动态保留", ORANGE,
         "@dynamic_checked 的 cstr_require 原样保留\n错误消息 \"matmul: K dims must match\"\n就写在 IR 里\n——检查的时点从编译期挪到运行期，\n但检查本身没有丢"),
        ("③ convert-shape-constraints", RED,
         "cstr_require 物化成：\n  cf.assert %7, \"matmul: K dims must match\"\nassuming 换成 const_witness true\n——mini 的 runtime 等式表到这里\n走完了最后一公里"),
        ("④ k_check 真实执行", BLUE,
         "手写物化结果（cf.assert + memref.dim）\n合法输入：打印 220，放行\n事故输入：打印约束消息后 abort\n（退出码 134，崩溃栈已存 outputs）\n——检查确定触发，语义一字不差"),
    ]
    ew, eh = 574, 158
    for i, (t, c, body) in enumerate(ev):
        x = 40 + (i % 2) * (ew + 12)
        y = 446 + (i // 2) * (eh + 14)
        p.append(sketch_rect(x, y, ew, eh, "#ffffff", c, 2.2, 5))
        p.append(txt(x + 14, y + 24, t, 12.5, c, bold=True))
        for k, line in enumerate(body.split("\n")):
            p.append(txt(x + 14, y + 46 + k * 18, line, 10.5, INK))

    p.append(txt(40, 794, "一句话贯通：未知维度的约束不会自己消失——它要么在编译期被折掉（静态），要么在运行期被查（cf.assert），",
                 12.5, RED, bold=True))
    p.append(txt(40, 816, "要么被无视（k_hazard 的垃圾值）。动态 Shape 编译器的本事，就是把这三条路摆到桌面上选。",
                 12.5, RED, bold=True))
    p.append(txt(40, 840, "边界说明：shape dialect 在 LLVM 18.1.8 上对 memref 的 shape_of 降不到 LLVM（实测 failed to", 11, MUTED))
    p.append(txt(40, 858, "materialize），所以 ④ 用手写的物化结果执行——目标形态一致，语义一字不差。", 11, MUTED))
    p.append("</svg>")
    (OUT / "04-witness.svg").write_text("\n".join(p), encoding="utf-8")


if __name__ == "__main__":
    img1()
    img2()
    img3()
    img4()
    for f in sorted(OUT.glob("*.svg")):
        print(f"{f.name}: {f.stat().st_size} bytes")
