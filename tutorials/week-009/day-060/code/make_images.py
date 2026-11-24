#!/usr/bin/env python3
"""make_images.py —— 第 60 天教程的四张手绘 sketch 风 SVG 信息图。

风格约定（与第 8/9 周各天一致）：
  - 背景 #fdfaf2（米白），盒子白底 + 深灰 #6b6357 手绘描边
  - 强调色不超过 4 种柔和色：蓝 #4a7fa5 / 橙 #a8772e / 绿 #5a8a5a / 红 #b0605a
  - 线条带轻微抖动（L 段折线），圆头笔触，线宽 2 左右
  - 手写感字体栈：Comic Sans MS / Comic Neue / Kaiti SC / 楷体 / cursive

图中全部数字来自 2026-11-12 的真实运行：
  broadcast_lab.py 9/9、test_broadcast.py 48/48（判定表 16/16、随机 300 组
  ok=178 error=122、broadcast_to strides 71 组）、
  mlir-opt --canonicalize 把 shape.broadcast 折成 [2,3] 与 [8,1000,256]、
  失配的 (2,3)+(4,) 原样保留、--convert-linalg-to-loops 降出
  memref.load %1[%arg1] 与 [%arg0, %c0]、mlir-cpu-runner 输出 33/25/101/206、
  bad_broadcast.mlir 被拒（inferred 3 but found 4 / inferred 2 but found 3）。

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

rng = random.Random(60)


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


def sketch_poly(points, stroke=STROKE, sw=2.0, arrow=False):
    d = ("M " + " L ".join(f"{px:.1f},{py:.1f}" for px, py in points))
    out = [f'<path d="{d}" fill="none" stroke="{stroke}" '
           f'stroke-width="{sw}" stroke-linecap="round" '
           f'stroke-linejoin="round"/>']
    if arrow:
        (x0, y0), (x1, y1) = points[-2], points[-1]
        out.append(sketch_line(x0, y0, x1, y1, stroke, sw, arrow=True))
    return "".join(out)


def header(w, h, title, sub):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" '
            f'height="{h}" viewBox="0 0 {w} {h}">\n'
            f'<rect width="{w}" height="{h}" fill="{BG}"/>\n'
            + txt(40, 38, title, 20, INK, bold=True) + "\n"
            + txt(40, 61, sub, 12, MUTED) + "\n")


# ============================================================
# 图 1：全貌——第 60 天在六阶段与第 9 周中的位置
# ============================================================

def img1():
    W, H = 1240, 790
    p = [header(W, H,
                "第 60 天全貌：Broadcast 规则——两边形状不同，怎么凑到同一张输出表上？",
                "上：六阶段里程碑与第 9 周日程（今天第 4 天）｜中：昨天到今天的衔接｜下：Broadcast 推导发生在编译链路的哪一站")]

    # ---- 上：里程碑 ----
    p.append(txt(40, 92, "168 天六阶段（今天是阶段三·第 9 周的第 4 天）：", 13.5,
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
        ("Day 59", "Reshape 合法性：\n什么时候零拷贝？\n什么时候必须搬家？",
         TINT["white"], STROKE, MUTED),
        ("Day 60", "Broadcast 规则：\n右对齐 · 维度为 1\n的扩展 · 未知维度\n（今天）",
         TINT["orange"], ORANGE, ORANGE),
        ("Day 61+", "动态 Shape /\n静态特化 / 复盘……",
         TINT["white"], STROKE, MUTED),
    ]
    cw2, ch2 = 226, 96
    for i, (d, body, fill, sc, tc) in enumerate(week):
        x = 40 + i * (cw2 + 12)
        p.append(sketch_rect(x, 228, cw2, ch2, fill, sc, 2.6 if i == 3 else 1.8, 5))
        p.append(txt(x + 12, 250, d, 12.5, tc, bold=True))
        for k, line in enumerate(body.split("\n")):
            p.append(txt(x + 12, 270 + k * 17, line, 11, INK))
        if i < 4:
            p.append(sketch_line(x + cw2 + 1, 228 + ch2 / 2, x + cw2 + 11,
                                 228 + ch2 / 2, MUTED, 1.8, arrow=True))

    # ---- 中：衔接卡片 ----
    p.append(txt(40, 362, "昨天到今天：从「一个张量怎么变形」到「两个张量怎么凑对」", 14,
                 INK, bold=True))
    cards = [
        ("第 57-59 天打好的地基", "偏移公式 Σ idx×stride、\n视图 vs 搬家两档代价、\ninfer_shape 的校验思路",
         TINT["white"], STROKE, MUTED),
        ("第 60 天要回答的", "bias(256,) 加到 logits(8,1000,256) 上：\n输出形状是什么？什么时候非法？\n「扩展」到底扩没扩内存？",
         TINT["blue"], BLUE, BLUE),
        ("后续谁要用它", "Day 61 动态维度的 meet 约定、\nDay 62 形状特化的入口、\n融合前的一致性检查",
         TINT["white"], STROKE, MUTED),
    ]
    cx, cy, cw3, ch3 = 40, 380, 373, 118
    for i, (t, body, fill, sc, tc) in enumerate(cards):
        x = cx + i * (cw3 + 17)
        p.append(sketch_rect(x, cy, cw3, ch3, fill, sc, 2.4, 5))
        p.append(txt(x + 14, cy + 24, t, 12.5, tc, bold=True))
        for k, line in enumerate(body.split("\n")):
            p.append(txt(x + 14, cy + 50 + k * 20, line, 11, INK))
        if i < 2:
            p.append(sketch_line(x + cw3 + 1, cy + ch3 / 2,
                                 x + cw3 + 16, cy + ch3 / 2, MUTED, 1.8,
                                 arrow=True))

    # ---- 下：编译链路 ----
    p.append(txt(40, 542, "Broadcast 推导发生在编译链路的哪一站（今天用真实 mlir-opt / "
                          "mlir-cpu-runner 验证形状推导与执行这一环）：",
                 13.5, INK, bold=True))
    lx, ly, lw2, lh2 = 40, 558, 360, 120
    p.append(sketch_rect(lx, ly, lw2, lh2, "#ffffff", STROKE, 2.0, 5))
    p.append(txt(lx + 14, ly + 22, "框架图：广播只写形状", 12, BLUE, bold=True))
    p.append(txt(lx + 14, ly + 45, "logits + bias  /  x + y", 11.5, INK))
    p.append(txt(lx + 14, ly + 62, "  两个形状不同的张量同台", 11.5, INK))
    p.append(txt(lx + 14, ly + 84, "  输出形状是推导出来的，不是声明的", 11, MUTED))
    p.append(txt(lx + 14, ly + 106, "→ 用户视角：不写输出形状", 11, MUTED))
    x2 = lx + lw2 + 30
    p.append(sketch_line(x2 - 26, ly + lh2 / 2, x2 - 4, ly + lh2 / 2,
                         ORANGE, 2.4, arrow=True))
    p.append(sketch_rect(x2, ly, lw2, lh2, TINT["orange"], ORANGE, 2.4, 5))
    p.append(txt(x2 + 14, ly + 22, "mini 编译器：Broadcast 推导（今天的位置）", 12,
                 ORANGE, bold=True))
    p.append(txt(x2 + 14, ly + 45, "右对齐比较维度（缺的维按 1）", 11.5, INK))
    p.append(txt(x2 + 14, ly + 62, "维度为 1 → 扩展；否则必须相等", 11.5, INK))
    p.append(txt(x2 + 14, ly + 84, "未知维度 None：meet 规则（Day 61 展开）", 11,
                 MUTED))
    p.append(txt(x2 + 14, ly + 106, "  / 输出 strides：广播维记 0", 11, MUTED))
    x3 = x2 + lw2 + 30
    p.append(sketch_line(x3 - 26, ly + lh2 / 2, x3 - 4, ly + lh2 / 2,
                         GREEN, 2.4, arrow=True))
    p.append(sketch_rect(x3, ly, 1240 - 40 - x3, lh2, "#ffffff", GREEN, 2.0, 5))
    p.append(txt(x3 + 14, ly + 22, "后端：广播 = 少一个下标", 12, GREEN, bold=True))
    p.append(txt(x3 + 14, ly + 45, "linalg：indexing map 丢掉 d0", 11.5, INK))
    p.append(txt(x3 + 14, ly + 62, "降成循环：memref.load %b[%arg1]", 11.5, INK))
    p.append(txt(x3 + 14, ly + 84, "MLIR 对照：shape.broadcast 折叠成", 11, MUTED))
    p.append(txt(x3 + 14, ly + 106, "  常数形状 [2,3]（编译期完成）", 11, MUTED))

    p.append(txt(40, 716, "实测环境（全部真实运行）：Linux aarch64 · Python 3.11.4 · "
                          "numpy 1.26.4 · Ubuntu LLVM 18.1.8（mlir-opt + mlir-cpu-runner）",
                 11, MUTED))
    p.append(txt(40, 738, "今日战绩：broadcast_lab 9/9 · test_broadcast 48/48（判定表 16/16 · "
                          "随机 300 组 ok=178 error=122 · strides 71 组）· "
                          "canonicalize 折出 [2,3] 与 [8,1000,256]", 11, MUTED))
    p.append(txt(40, 760, "cpu-runner 真实执行 33 / 25 / 101 / 206 · bad_broadcast 两间房均被 "
                          "Verifier 拒绝 · shape.broadcast 对失配形状静态不报错（缺口）",
                 11, MUTED))
    p.append("</svg>")
    (OUT / "01-overview.svg").write_text("\n".join(p), encoding="utf-8")


# ============================================================
# 图 2：核心机制——右对齐 + 三态判定 + stride-0 地址映射
# ============================================================

def img2():
    W, H = 1240, 900
    p = [header(W, H,
                "核心机制：右对齐比较 → 三态判定 → stride-0 地址映射（不搬数据）",
                "上：推导算法四步走（bias 例子）｜中：逐维三态规则与翻车现场｜下：广播维的物理真相——0 步长")]

    # ---- 上：算法流程 ----
    p.append(txt(40, 92, "mini.broadcast 的推导算法（例子：logits (8,1000,256) + bias (256,)）：",
                 13.5, INK, bold=True))
    steps = [
        ("① 输入：两个形状", BLUE, "(8, 1000, 256)  与  (256,)\nrank 不同没关系\n比较从不看左边开始",
         TINT["blue"]),
        ("② 右对齐，短侧补 1", ORANGE, "(8, 1000, 256)\n( 1,    1, 256)\n缺的维度按 1 参与\n——不是把 256 对到 8 上！",
         TINT["orange"]),
        ("③ 逐维三态判定", GREEN, "8  vs 1   → 8（1 让位）\n1000 vs 1 → 1000（1 让位）\n256 vs 256 → 256（相等保留）",
         TINT["green"]),
        ("④ 输出形状", BLUE, "(8, 1000, 256)\n→ 这就是加法结果的 shape\n全程 O(rank)，纯静态推导",
         TINT["blue"]),
    ]
    sw_, sh_ = 268, 118
    for i, (t, c, body, fill) in enumerate(steps):
        x = 40 + i * (sw_ + 22)
        p.append(sketch_rect(x, 106, sw_, sh_, fill, c, 2.4, 5))
        p.append(txt(x + 14, 128, t, 12.5, c, bold=True))
        for k, line in enumerate(body.split("\n")):
            p.append(txt(x + 14, 152 + k * 19, line, 11, INK))
        if i < 3:
            p.append(sketch_line(x + sw_ + 2, 106 + sh_ / 2, x + sw_ + 20,
                                 106 + sh_ / 2, MUTED, 2.0, arrow=True))

    # ---- 中：三态规则 + 翻车现场 ----
    p.append(txt(40, 262, "第 ③ 步的逐维三态（对每一对同位维度问三个问题）：", 13.5,
                 INK, bold=True))
    rules = [
        ("相等 → 保留", GREEN, "256 vs 256 → 256\n0 vs 0 → 0（0 尺寸维也一样）\n最常见也最无聊的一态", TINT["green"]),
        ("一方为 1 → 取另一方", BLUE, "8 vs 1 → 8 · 1 vs 1000 → 1000\n1 vs 0 → 0（不是取 max！）\n「扩展」就发生在这条上", TINT["blue"]),
        ("都不是 → 失配报错", RED, "3 vs 4 → error\n1000 vs 256 → error\n有 1 也救不了别的维", TINT["red"]),
    ]
    rw, rh = 373, 96
    for i, (t, c, body, fill) in enumerate(rules):
        x = 40 + i * (rw + 17)
        p.append(sketch_rect(x, 278, rw, rh, fill, c, 2.2, 5))
        p.append(txt(x + 14, 300, t, 12.5, c, bold=True))
        for k, line in enumerate(body.split("\n")):
            p.append(txt(x + 14, 322 + k * 19, line, 11, INK))

    p.append(txt(40, 404, "翻车现场：(256,1) 一样有 256，却非法——右对齐后对不上（真实报错）：",
                 13.5, INK, bold=True))
    p.append(sketch_rect(40, 418, 1160, 78, "#ffffff", RED, 2.0, 5))
    p.append(txt(56, 442, "logits (8,1000,256) + bias (256,1)：", 12, INK))
    p.append(txt(56, 464, "  右对齐 → (8,1000,256) vs (1,256,1)：第 1 维 1000 vs 256，既不相等也没有 1 → 失配", 11.5, RED, bold=True))
    p.append(txt(56, 486, "  ValueError: shape mismatch: objects cannot be broadcast to a single shape.  Mismatch is between arg 0 with shape (8, 1000, 256) and arg 1 with shape (256, 1).", 10, MUTED))

    # ---- 下：stride-0 ----
    p.append(txt(40, 532, "「扩展」的物理真相：广播维 stride = 0，一格数据反复读，从不拷贝：",
                 13.5, INK, bold=True))

    # 左：b(3,) → (2,3)
    p.append(txt(40, 560, "行向量 b (3,) 当 (2,3) 用：新 strides = (0, 1)", 12, BLUE,
                 bold=True))
    cw_, ch_ = 64, 42
    vals = ["10", "20", "30"]
    for j in range(3):
        x = 40 + j * (cw_ + 6)
        p.append(sketch_rect(x, 574, cw_, ch_, TINT["blue"], BLUE, 1.6, 3))
        p.append(txt(x + cw_ / 2, 574 + ch_ / 2 + 5, vals[j], 13, INK, "middle"))
    p.append(txt(40, 644, "逻辑第 0 行 [i=0] ──读──▶  10  20  30", 11, INK))
    p.append(txt(40, 664, "逻辑第 1 行 [i=1] ──读──▶  10  20  30（同一排格子）", 11, INK))
    p.append(txt(40, 690, "行 +1 → 走 0 步（stride 0）", 11.5, RED, bold=True))
    p.append(txt(40, 708, "列 +1 → 走 1 步（stride 1）", 11.5, INK))
    p.append(txt(40, 732, "偏移 = i×0 + j×1：np.broadcast_to(b,(2,3))", 11, MUTED))
    p.append(txt(40, 750, "实测 strides = (0, 8) bytes，与源共享内存", 11, MUTED))

    # 中：c(2,1) → (2,3)
    tx = 430
    p.append(txt(tx, 560, "列向量 c (2,1) 当 (2,3) 用：新 strides = (1, 0)", 12,
                 GREEN, bold=True))
    cvals = ["100", "200"]
    for i in range(2):
        p.append(sketch_rect(tx, 574 + i * (ch_ + 6), cw_, ch_, TINT["green"],
                             GREEN, 1.6, 3))
        p.append(txt(tx + cw_ / 2, 574 + i * (ch_ + 6) + ch_ / 2 + 5, cvals[i],
                     13, INK, "middle"))
    p.append(txt(tx + 84, 596, "第 0 行 = 100 100 100", 11, INK))
    p.append(txt(tx + 84, 620, "第 1 行 = 200 200 200", 11, INK))
    p.append(txt(tx + 84, 644, "（同一格读三遍）", 11, MUTED))
    p.append(txt(tx, 690, "行 +1 → 走 1 步（换到 200 那格）", 11.5, INK))
    p.append(txt(tx, 708, "列 +1 → 走 0 步（原地不动）", 11.5, RED, bold=True))
    p.append(txt(tx, 732, "偏移 = i×1 + j×0：MLIR 里就是", 11, MUTED))
    p.append(txt(tx, 750, "affine_map<(d0,d1) -> (d0, 0)>：d1 钉死 0", 11, MUTED))

    # 右：标量
    tx2 = 820
    p.append(txt(tx2, 560, "标量 () 当 (2,3) 用：新 strides = (0, 0)", 12, ORANGE,
                 bold=True))
    p.append(sketch_rect(tx2, 574, cw_, ch_, TINT["orange"], ORANGE, 1.6, 3))
    p.append(txt(tx2 + cw_ / 2, 574 + ch_ / 2 + 5, "s", 13, INK, "middle"))
    p.append(txt(tx2, 644, "所有下标都读同一格 s", 11, INK))
    p.append(txt(tx2, 664, "两个方向都走 0 步", 11, INK))
    p.append(txt(tx2, 690, "所以标量是「万能形状」", 11.5, INK))
    p.append(txt(tx2, 708, "() 与任何形状广播都得原形状", 11.5, INK))
    p.append(txt(tx2, 732, "实测 broadcast_to((), (2,3))", 11, MUTED))
    p.append(txt(tx2, 750, "strides = (0, 0)", 11, MUTED))

    # 底部结论
    p.append(txt(40, 792, "关键结论：广播的「扩展」是地址映射不是数据复制——b 的 12 MiB 版本 (100000,3) 与 3 个元素共享存储（实测）；",
                 12.5, RED, bold=True))
    p.append(txt(40, 814, "stride 0 也解释了为什么广播视图只读：两个逻辑位置指着同一格，写哪个都说不清（numpy: assignment destination is read-only）。",
                 11, INK))
    p.append(txt(40, 838, "MLIR 同口径：linalg.generic 的 indexing map (d0,d1) -> (d1) 丢掉 d0，降成循环后 %b 只用一个下标寻址——广播在后端就是「少一个下标」。",
                 11, MUTED))
    p.append(txt(40, 862, "边界说明：numpy 对 in==out==1 的维也记 stride 0（size-1 维下标恒 0，0 与继承值等价）；0 尺寸维按普通维参与三态判定。",
                 11, MUTED))
    p.append("</svg>")
    (OUT / "02-mechanism.svg").write_text("\n".join(p), encoding="utf-8")


# ============================================================
# 图 3：实例对照——判定表、数值与对拍统计
# ============================================================

def img3():
    W, H = 1240, 980
    p = [header(W, H,
                "实例对照：判定表 16/16 全对拍，数值、strides 与错误消息逐字一致",
                "上：判定表浓缩版（真实输出，完整表见 code/outputs/broadcast_lab.txt）｜中：a+b 的值与 cpu-runner 真实执行｜下：对拍统计")]

    # ---- 上：判定表 ----
    p.append(txt(40, 92, "判定表（浓缩 10 行，C1–C16 全表 16/16 ok）：", 13.5, INK, bold=True))
    cols = [(40, "用例"), (200, "输入形状"), (460, "mini 预测"), (660, "numpy 实测"), (880, "对拍结论")]
    p.append(sketch_rect(40, 100, 1160, 26, TINT["gray"], STROKE, 1.6, 4))
    for x, t in cols:
        p.append(txt(x + 6, 118, t, 11.5, MUTED, bold=True))
    rows = [
        ("C2  标量 vs 矩阵", "(2,3) + ()", "(2, 3)", "(2, 3)", "ok", GREEN),
        ("C3  行向量（贯穿例子）", "(2,3) + (3,)", "(2, 3)", "(2, 3)", "ok", GREEN),
        ("C4  列向量右对齐", "(2,3) + (2,1)", "(2, 3)", "(2, 3)", "ok", GREEN),
        ("C5  bias 相加", "(8,1000,256) + (256,)", "(8,1000,256)", "(8,1000,256)", "ok", GREEN),
        ("C6  经典翻车", "(8,1000,256) + (256,1)", "error", "error", "ok", RED),
        ("C9  0 尺寸维", "(0,) + (1,)", "(0,)", "(0,)", "ok", GREEN),
        ("C11 三形状连播", "(8,1000,256)+(256,)+(1,1)", "(8,1000,256)", "(8,1000,256)", "ok", GREEN),
        ("C12 -1 不是未知维度", "(2,3) + (-1,)", "error", "error", "ok", RED),
        ("C13 维度 1 不豁免他维", "(3,1) + (2,3)", "error", "error", "ok", RED),
        ("C16 1×n 对 n×1", "(1,3) + (3,1)", "(3, 3)", "(3, 3)", "ok", GREEN),
    ]
    for i, (a, b, c, d, e, col) in enumerate(rows):
        y = 130 + i * 30
        p.append(sketch_rect(40, y, 1160, 26, "#ffffff", STROKE, 1.2, 3))
        p.append(txt(46, y + 19, a, 11, INK))
        p.append(txt(206, y + 19, b, 11, INK))
        p.append(txt(466, y + 19, c, 11, BLUE if c != "error" else RED))
        p.append(txt(666, y + 19, d, 11, GREEN if d != "error" else RED))
        p.append(txt(886, y + 19, e, 11, col, bold=True))
    p.append(txt(40, 436, "注：4 组 error 用例的错误消息与 numpy 逐字相同（含 (256,1) 那句 "
                          "Mismatch is between arg 0 ... and arg 1 ...）。", 11, MUTED))

    # ---- 中：数值与 cpu-runner ----
    p.append(txt(40, 470, "a + b 的值（b 沿行广播：每行加的是同一个 b）与 MLIR 真实执行：",
                 13.5, INK, bold=True))
    # 2x3 result grid
    res = [["11", "22", "33"], ["14", "25", "36"]]
    bx = 40
    for i in range(2):
        for j in range(3):
            x = bx + j * (74 + 5)
            y = 486 + i * (44 + 5)
            fill = TINT["blue"] if i == 0 else "#ffffff"
            p.append(sketch_rect(x, y, 74, 44, fill, BLUE, 1.5, 3))
            p.append(txt(x + 37, y + 28, res[i][j], 14, INK, "middle", bold=True))
    p.append(txt(bx, 596, "a(2,3) + b(3,) = [[11,22,33],[14,25,36]]", 11.5, INK))
    p.append(txt(bx, 616, "第 0 行 [1,2,3]+[10,20,30]，第 1 行 [4,5,6]+[10,20,30]", 11, MUTED))
    p.append(txt(bx, 636, "a + c(2,1) = [[101,102,103],[204,205,206]]（c 沿列广播）", 11.5, INK))

    # cpu-runner box
    p.append(sketch_rect(430, 486, 330, 156, "#ffffff", GREEN, 2.2, 5))
    p.append(txt(444, 510, "mlir-cpu-runner 真实执行（broadcast_add.mlir）", 12,
                 GREEN, bold=True))
    p.append(txt(444, 536, "o1[0,2] = 3 + 30   → 打印 33", 12, INK))
    p.append(txt(444, 558, "o1[1,1] = 5 + 20   → 打印 25", 12, INK))
    p.append(txt(444, 580, "o2[0,0] = 1 + 100  → 打印 101", 12, INK))
    p.append(txt(444, 602, "o2[1,2] = 6 + 200  → 打印 206", 12, INK))
    p.append(txt(444, 628, "手算 = 实测，四个值全部对上", 11, RED, bold=True))

    # stride-0 evidence box
    p.append(sketch_rect(790, 486, 410, 156, TINT["white"], STROKE, 2.0, 5))
    p.append(txt(804, 510, "stride-0 视图对拍（np.broadcast_to 实测）", 12, BLUE,
                 bold=True))
    p.append(txt(804, 536, "(3,)   → (2,3)：mini (0,1)   numpy (0,1)", 11, INK))
    p.append(txt(804, 558, "(2,1)  → (2,3)：mini (1,0)   numpy (1,0)", 11, INK))
    p.append(txt(804, 580, "(256,) → (8,1000,256)：(0,0,1) 两边一致", 11, INK))
    p.append(txt(804, 602, "(2,3)  → (4,1,2,3)：(0,0,3,1) 两边一致", 11, INK))
    p.append(txt(804, 628, "10 组逐位一致；广播维一律 0 步长", 11, RED, bold=True))

    # ---- 下：统计 ----
    p.append(txt(40, 674, "对拍统计（种子 60，全部真实运行）：", 13.5, INK, bold=True))
    stats = [
        ("判定表", "16/16 一致\n（含 4 组错误消息逐字相同）", BLUE, TINT["blue"]),
        ("随机形状对拍", "300 组零失配\nok=178 · error=122", GREEN, TINT["green"]),
        ("随机 strides 对拍", "71 组逐位一致\nbroadcast_to 同口径", ORANGE, TINT["orange"]),
        ("验收测试", "test_broadcast 48/48\nA–E 五段全过", RED, TINT["red"]),
    ]
    stw, sth = 278, 96
    for i, (t, body, c, fill) in enumerate(stats):
        x = 40 + i * (stw + 16)
        p.append(sketch_rect(x, 690, stw, sth, fill, c, 2.2, 5))
        p.append(txt(x + 14, 712, t, 12.5, c, bold=True))
        for k, line in enumerate(body.split("\n")):
            p.append(txt(x + 14, 736 + k * 20, line, 11, INK))

    p.append(txt(40, 812, "numpy 的两条真实报错（判定表与实验 1 逐字记录）：", 13.5, INK,
                 bold=True))
    p.append(sketch_rect(40, 826, 1160, 64, "#ffffff", RED, 1.8, 5))
    p.append(txt(56, 848, "推导口径：ValueError: shape mismatch: objects cannot be broadcast to a single shape.  Mismatch is between arg 0 with shape (2, 3) and arg 1 with shape (4,).",
                 10.5, INK))
    p.append(txt(56, 872, "执行口径：ValueError: operands could not be broadcast together with shapes (2,3) (4,) ——同一场失配，推导和执行各自报各自的。",
                 10.5, MUTED))

    p.append(txt(40, 918, "要点：mini 与 numpy 的判定完全等价——右对齐补 1 后逐维三态；"
                          "「(256,) 行而 (256,1) 不行」不是玄学，是第 1 维 1000 vs 256 失配。", 12, RED, bold=True))
    p.append(txt(40, 940, "实测环境：Linux aarch64 · Python 3.11.4 · numpy 1.26.4 · "
                          "Ubuntu LLVM 18.1.8 · broadcast_lab 9/9 · test_broadcast 48/48", 11, MUTED))
    p.append("</svg>")
    (OUT / "03-example.svg").write_text("\n".join(p), encoding="utf-8")


# ============================================================
# 图 4：未知维度 meet 规则与 MLIR 双视角
# ============================================================

def img4():
    W, H = 1240, 880
    p = [header(W, H,
                "未知维度与 MLIR 对照：None 的 meet 规则；shape 折叠 / linalg 映射 / Verifier 现场",
                "左上：meet 真值表（mini 约定）｜右上：未知维度用例与 -1 的边界｜下：MLIR 四项实测证据")]

    # ---- 左上：meet 真值表 ----
    p.append(txt(40, 92, "未知维度的 meet 规则（右对齐补 1 之后，逐维查这张表；mini 约定）：",
                 13.5, INK, bold=True))
    tx, ty, cw_, ch_ = 40, 108, 128, 44
    head = ["meet ↓ →", "已知 e>1", "已知 1", "未知 None"]
    for j, h in enumerate(head):
        p.append(sketch_rect(tx + j * cw_, ty, cw_, ch_, TINT["gray"], STROKE, 1.6, 3))
        p.append(txt(tx + j * cw_ + cw_ / 2, ty + 28, h, 11.5, MUTED, "middle", bold=True))
    table = [
        ("已知 d>1", ["d==e → d；否则失配", "e（1 让位）", "d（None 让位）"], BLUE),
        ("已知 1", ["e（1 让位）", "1", "None！"], GREEN),
        ("未知 None", ["d（None 让位）", "None！", "None"], ORANGE),
    ]
    for i, (row, cells, c) in enumerate(table):
        y = ty + ch_ + i * ch_
        p.append(sketch_rect(tx, y, cw_, ch_, TINT["white"], c, 1.8, 3))
        p.append(txt(tx + cw_ / 2, y + 28, row, 11.5, c, "middle", bold=True))
        for j, cell in enumerate(cells):
            warn = "None" in cell and cell.endswith("None！")
            p.append(sketch_rect(tx + (j + 1) * cw_, y, cw_, ch_,
                                 TINT["red"] if warn else "#ffffff",
                                 RED if warn else STROKE, 1.4, 3))
            p.append(txt(tx + (j + 1) * cw_ + cw_ / 2, y + 28, cell, 10.5,
                         RED if warn else INK, "middle", bold=warn))
    p.append(txt(40, 312, "两条容易看反的（标红的 None）：", 12, RED, bold=True))
    p.append(txt(40, 334, "· None 对 1 → None：结果维跟随未知方（若它最后是 7，1 vs 7 结果是 7）", 11, INK))
    p.append(txt(40, 354, "· None 对 d>1 → d：输出静态可定，但运行期该维必须是 d 或 1 才合法", 11, INK))
    p.append(txt(40, 376, "「None 是还没定的维度」不是「任意维度」——区分这两者是 Day 61 的主题", 11, MUTED))

    # ---- 右上：未知维度用例 + -1 边界 ----
    p.append(txt(560, 92, "未知维度用例（broadcast_shapes_unknown，期望手算）：", 13.5,
                 INK, bold=True))
    ucases = [
        ("U1  (None,3) + (3,)", "(None, 3)", GREEN),
        ("U2  (None,3) + (5,3)", "(5, 3)", GREEN),
        ("U3  (None,3) + (1,)", "(None, 3)", GREEN),
        ("U5  (None,) + (3,)", "(3,)", GREEN),
        ("U7  (None,None)+(None,4)", "(None, 4)", GREEN),
        ("U8  (None,4) + (3,)", "error（4 vs 3）", RED),
    ]
    for i, (a, b, col) in enumerate(ucases):
        y = 108 + i * 30
        p.append(sketch_rect(560, y, 400, 26, "#ffffff", STROKE, 1.2, 3))
        p.append(txt(572, y + 19, a, 11, INK))
        p.append(txt(800, y + 19, b, 11, col, bold=True))
    p.append(txt(560, 296, "边界：-1 不是广播的未知维度（真实报错）：", 12, RED, bold=True))
    p.append(txt(560, 318, "np.broadcast_shapes((2,3), (-1,)) → ValueError:", 11, INK))
    p.append(txt(560, 340, "  negative dimensions are not allowed", 11, RED, bold=True))
    p.append(txt(560, 362, "reshape 的 -1 是「帮我算」；广播里 -1 就是负数维度。", 11, MUTED))
    p.append(txt(560, 384, "mini 用 None 表未知，把两套约定彻底分开（测试 E3）。", 11, MUTED))

    # ---- 下：MLIR 四项证据 ----
    p.append(txt(40, 428, "MLIR 四项实测证据（run_all.sh 真实输出，已存 code/outputs/）：",
                 13.5, INK, bold=True))
    ev = [
        ("① shape.broadcast 折叠成常数", BLUE,
         "shape.const_shape [2,3] 与 [3] 做 shape.broadcast\n--canonicalize 直接折成 const_shape [2, 3]\nbias 例 (8,1000,256)+(256,) 折成 [8, 1000, 256]\n——编译期就完成输出形状推导"),
        ("② 失配形状静态不报错（缺口）", RED,
         "(2,3) 与 (4,) 的 shape.broadcast\n--canonicalize 原样保留、exit=0 不报错\n错误要等运行期才暴露\nnumpy / mini.broadcast 都是静态拦——该补"),
        ("③ 广播降成「少一个下标」", GREEN,
         "linalg：b 的 indexing_map (d0,d1) -> (d1)\n--convert-linalg-to-loops 之后：\n  %8 = memref.load %1[%arg1] : memref<3xf32>\n列向量则是 [%arg0, %c0]：d1 被钉死 0\n= mini 的 stride 0，同一件事两种说法"),
        ("④ Verifier 拒绝非法广播", ORANGE,
         "bad_broadcast 房间 1：(2,3)+(4,)\n  error: inferred ... dimension #0 to be 3,\n  but found 4（exit=1）\n房间 2：(3,1)+(2,3)：inferred 2, but found 3\n——维度 1 豁免不了别的维的失配"),
    ]
    ew, eh = 574, 150
    for i, (t, c, body) in enumerate(ev):
        x = 40 + (i % 2) * (ew + 12)
        y = 444 + (i // 2) * (eh + 14)
        p.append(sketch_rect(x, y, ew, eh, "#ffffff", c, 2.2, 5))
        p.append(txt(x + 14, y + 24, t, 12.5, c, bold=True))
        for k, line in enumerate(body.split("\n")):
            p.append(txt(x + 14, y + 46 + k * 19, line, 10.5, INK))

    p.append(txt(40, 770, "一句话贯通：右对齐补 1 是「排位」，三态判定是「合法性」，stride 0 / 少一个下标是「执行方式」，",
                 12.5, RED, bold=True))
    p.append(txt(40, 792, "None 的 meet 是「静态能推多少推多少」——四件事一起构成 mini.broadcast 的完整形状推导。",
                 12.5, RED, bold=True))
    p.append(txt(40, 816, "实测环境：Linux aarch64 · Python 3.11.4 · numpy 1.26.4 · Ubuntu LLVM 18.1.8 · "
                          "broadcast_lab 9/9（未知维度 10/10）· test_broadcast 48/48", 11, MUTED))
    p.append(txt(40, 838, "边界说明：meet 的 None 约定是 mini 的设计选择（部分框架更保守，遇到未知直接返回未知）；"
                          "本文所有折叠/报错行为均在 LLVM 18.1.8 实测。", 11, MUTED))
    p.append("</svg>")
    (OUT / "04-unknown-and-mlir.svg").write_text("\n".join(p), encoding="utf-8")


if __name__ == "__main__":
    img1()
    img2()
    img3()
    img4()
    for f in sorted(OUT.glob("*.svg")):
        print(f"{f.name}: {f.stat().st_size} bytes")
