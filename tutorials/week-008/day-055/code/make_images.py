#!/usr/bin/env python3
"""make_images.py —— 第 55 天教程的四张手绘 sketch 风 SVG 信息图。

风格约定（与第 8 周前几天一致）：
  - 背景 #fdfaf2（米白），盒子白底 + 深灰 #6b6357 手绘描边
  - 强调色不超过 4 种柔和色：蓝 #4a7fa5 / 橙 #a8772e / 绿 #5a8a5a / 红 #b0605a
  - 线条带轻微抖动（Q/L 混合路径），圆头笔触，线宽 2 左右
  - 手写感字体栈：Comic Sans MS / Comic Neue / Kaiti SC / 楷体 / cursive

运行: python3 make_images.py   （在 code/ 目录下，输出到 ../images/）
"""

from __future__ import annotations

import math
import random
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "images"
OUT.mkdir(parents=True, exist_ok=True)

FONT = ("Comic Sans MS, Comic Neue, Segoe Print, Kaiti SC, KaiTi, 楷体, "
        "cursive")
INK = "#3b352d"          # 主文字色
MUTED = "#84796a"        # 次要文字色
STROKE = "#6b6357"       # 手绘描边
BG = "#fdfaf2"           # 米白背景
BLUE, ORANGE, GREEN, RED = "#4a7fa5", "#a8772e", "#5a8a5a", "#b0605a"
TINT = {"blue": "#eef3f7", "orange": "#f8f0e2", "green": "#edf4ee",
        "red": "#f7ecea"}

rng = random.Random(55)


def esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;")
             .replace(">", "&gt;"))


def txt(x, y, s, size=12, fill=INK, anchor="start", bold=False,
        opacity=1.0):
    w = 'font-weight="bold"' if bold else 'font-weight="normal"'
    return (f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" '
            f'fill="{fill}" text-anchor="{anchor}" opacity="{opacity}" '
            f'{w}>{esc(s)}</text>')


def sketch_rect(x, y, w, h, fill="#ffffff", stroke=STROKE, sw=2.2,
                nseg=6):
    """带抖动的手绘矩形：每条边拆成 nseg 段，节点随机偏移 1~2px，圆角收尾。"""
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
                bow=0.0):
    """手绘直线（可带弧度与箭头）。bow>0 时用二次贝塞尔做轻微弯曲。"""
    if bow:
        mx, my = (x0 + x1) / 2, (y0 + y1) / 2
        dx, dy = x1 - x0, y1 - y0
        mx, my = mx - dy * bow, my + dx * bow
        d = (f"M {x0:.1f},{y0:.1f} Q {mx:.1f},{my:.1f} "
             f"{x1:.1f},{y1:.1f}")
    else:
        d = f"M {x0:.1f},{y0:.1f} L {x1:.1f},{y1:.1f}"
    out = [f'<path d="{d}" fill="none" stroke="{stroke}" '
           f'stroke-width="{sw}" stroke-linecap="round" '
           f'stroke-linejoin="round"/>']
    if arrow:
        ang = math.atan2(y1 - y0, x1 - x0) if not bow else \
            math.atan2(y1 - my, x1 - mx)
        L = 9.0
        for da in (math.radians(152), math.radians(-152)):
            ax = x1 + L * math.cos(ang + da)
            ay = y1 + L * math.sin(ang + da)
            out.append(f'<path d="M {x1:.1f},{y1:.1f} L {ax:.1f},{ay:.1f}" '
                       f'fill="none" stroke="{stroke}" stroke-width="{sw}" '
                       f'stroke-linecap="round"/>')
    return "".join(out)


def sketch_dash(x0, y0, x1, y1, stroke=MUTED, sw=1.6):
    d = f"M {x0:.1f},{y0:.1f} L {x1:.1f},{y1:.1f}"
    return (f'<path d="{d}" fill="none" stroke="{stroke}" '
            f'stroke-width="{sw}" stroke-linecap="round" '
            f'stroke-dasharray="7 6"/>')


def header(w, h, title, sub):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" '
            f'height="{h}" viewBox="0 0 {w} {h}">\n'
            f'<rect width="{w}" height="{h}" fill="{BG}"/>\n'
            + txt(40, 38, title, 20, INK, bold=True) + "\n"
            + txt(40, 61, sub, 12, MUTED) + "\n")


# ===================== 图 1：全局定位（管道 + 三道闸门 + 周路线） =====================

def img_overview() -> str:
    W, H = 1180, 880
    p = [header(W, H,
                "第 55 天：融合正确性与负例总验收——「能融」的边界由三道闸门说了算",
                "上：mini-opt 管道与今天的验收器｜中：三道闸门各拦哪类负例｜下：第 8 周路线（今天是第 6 格）")]
    # ---- 上：管道 ----
    p.append(txt(60, 104, "① mini-opt 管道：验收器站在融合 Pass 的下游，裁决它的一整轮行为", 13, INK, bold=True))
    boxes = [("parse 解析", 96), ("verify 闸门一", 268),
             ("融合 Pass 闸门二", 440), ("验收器（今天）", 612),
             ("（后续）lowering", 784)]
    bw, bh, by = 150, 46, 120
    for i, (name, x) in enumerate(boxes):
        hi = i in (2, 3)
        p.append(sketch_rect(x, by, bw, bh,
                             fill=TINT["blue"] if hi else "#ffffff",
                             stroke=BLUE if hi else STROKE))
        p.append(txt(x + bw / 2, by + 28, name, 12.5,
                     INK, "middle", bold=hi))
        if i < len(boxes) - 1:
            p.append(sketch_line(x + bw + 4, by + bh / 2,
                                 boxes[i + 1][1] - 6, by + bh / 2,
                                 arrow=True))
    p.append(txt(531, 188, "R1 双遍历同形态 + R2 恒等断言 +（Python 层）R3 数值对账 / R4 二次防线",
                 10.5, BLUE, "middle", bold=True))

    # ---- 中：三道闸门 ----
    p.append(txt(60, 236, "② 三道闸门与四类负例：每道闸门各管一层，谁拦下谁写得明明白白", 13, INK, bold=True))
    gates = [
        ("闸门一：Verifier", "parse + verify 就地报错", BLUE, TINT["blue"],
         ["Shape 不兼容：C12 Mismatch / C13 需广播", "f64 matmul：C14（元素类型必须 f32）",
          "MLIR 层 M08 / M09 / M10 同在此层"]),
        ("闸门二：Pattern 规则", "match 里的收手条件", ORANGE, TINT["orange"],
         ["多使用者：C07/M03（use 表非空不删）", "歧义：C10/M05（两侧都是 matmul）",
          "类型闸门：C09/C11、M06/M07（fused* 只对 f32）"]),
        ("闸门三：数值对账", "evaluate 前后 allclose（R3）", GREEN, TINT["green"],
         ["全部可求值用例：融合前后输出一致", "没有负例被它「拦下」——它证明",
          "闸门一/二没拦错、语义确实没变"]),
    ]
    gw, gh, gy = 336, 180, 252
    for i, (name, cap, color, tint, items) in enumerate(gates):
        gx = 60 + i * (gw + 32)
        p.append(sketch_rect(gx, gy, gw, gh, fill=tint, stroke=color))
        p.append(txt(gx + gw / 2, gy + 30, name, 14, color, "middle", bold=True))
        p.append(txt(gx + gw / 2, gy + 50, cap, 10.5, MUTED, "middle"))
        for j, it in enumerate(items):
            p.append(txt(gx + 18, gy + 82 + j * 26, "· " + it, 11, INK))
    p.append(sketch_line(228, gy + gh + 6, 228, gy + gh + 26, arrow=True))
    p.append(sketch_line(596, gy + gh + 6, 596, gy + gh + 26, arrow=True))
    p.append(sketch_line(964, gy + gh + 6, 964, gy + gh + 26, arrow=True))
    p.append(sketch_rect(60, gy + gh + 28, 1016, 58, fill="#ffffff"))
    p.append(txt(70, gy + gh + 52, "性能收益账本（第 74 天才建）：今天只画线、不判账——正例「融了」≠「融了更快」，",
                 11, MUTED))
    p.append(txt(70, gy + gh + 72, "收益判断属于未来两阶段的 CostModel；验收器今天回答的只有「敢不敢融」。",
                 11, MUTED))

    # ---- 下：第 8 周路线 ----
    p.append(txt(60, 556, "③ 第 8 周路线（融合周）：今天是收官验收——51～54 的全部规则在这里当试金石", 13, INK, bold=True))
    days = [("50", "定义融合算子", False), ("51", "Add+Relu 融合", False),
            ("52", "多使用者限制", False), ("53", "MatMul+Bias", False),
            ("54", "三算子/优先级", False), ("55", "负例总验收", True),
            ("56", "第 8 周复盘", False)]
    cw, ch, cy = 128, 74, 572
    for i, (d, name, hi) in enumerate(days):
        cx = 60 + i * (cw + 14)
        p.append(sketch_rect(cx, cy, cw, ch,
                             fill=TINT["orange"] if hi else "#ffffff",
                             stroke=ORANGE if hi else STROKE,
                             sw=2.6 if hi else 2.0))
        p.append(txt(cx + cw / 2, cy + 30, "第 " + d + " 天", 12,
                     ORANGE if hi else MUTED, "middle", bold=hi))
        p.append(txt(cx + cw / 2, cy + 54, name, 11.5, INK, "middle", bold=hi))
        if i < len(days) - 1:
            p.append(sketch_line(cx + cw + 1, cy + ch / 2,
                                 cx + cw + 13, cy + ch / 2))
    p.append(txt(60, cy + ch + 34, "验收语料 24 例 = Python 层 14 例（C01～C14）＋ MLIR 层 10 例（M01～M10）：",
                 11.5, INK))
    p.append(txt(60, cy + ch + 54, "正例必须两种遍历收敛到同一形态；负例必须恒等拒绝；Verifier 负例必须 parse/verify 当场拦下。",
                 11.5, INK))
    p.append(txt(60, cy + ch + 78, "已核对第 8 周相邻各天：今天不引入新算子、不做收益判断（第 74 天）、不碰广播（第 60 天）。",
                 10.5, MUTED))
    p.append("</svg>")
    return "\n".join(p)


# ===================== 图 2：四类负例 × 闸门分流 =====================

def img_gates() -> str:
    W, H = 1180, 880
    p = [header(W, H,
                "四类融合负例分别被哪道闸门拦下（Python 层 14 用例的真实判决）",
                "左：负例类型与代表用例｜中：两道前置闸门（外加一个半融合不动点）｜右：三种判决结果")]

    p.append(txt(60, 104, "负例类型（今天整理的完整清单）", 13, INK, bold=True))
    p.append(txt(470, 104, "被谁拦下", 13, INK, bold=True))
    p.append(txt(880, 104, "判决（真实运行）", 13, INK, bold=True))

    cases = [
        ("① 多使用者", "C07 multi_user_product：", "乘积 %0 被 add＋第二个 relu 共用",
         "闸门二：use 表非空不许删生产者", "identity 恒等拒绝", ORANGE),
        ("② Shape 不兼容", "C12 Mismatch / C13 需广播：", "bias 2x3、[2] 对乘积 2x2",
         "闸门一：add 的 Verifier 报错", "verifier_reject", BLUE),
        ("③ 类型不支持", "C09 全 f64 add / C11 混 dtype / C14 f64 matmul：",
         "fused* 语义只对 f32 验证过",
         "C14 走闸门一（matmul Verifier）；C09/C11 走闸门二（类型闸门）",
         "verifier_reject 或 identity", BLUE),
        ("④ 歧义与额外使用", "C10 两侧都是 matmul / C08 加法结果被 return 共用：",
         "分不清谁是 bias；Relu 吸收不掉",
         "C10 走闸门二（判定规则）；C08 不算被拦——收敛到半融合不动点",
         "identity 恒等拒绝 / fused(半融合)", GREEN),
    ]
    by = 124
    rh = 118
    for i, (kind, rep, detail, gate, verdict, color) in enumerate(cases):
        y = by + i * (rh + 18)
        p.append(sketch_rect(60, y, 350, rh, fill="#ffffff"))
        p.append(txt(74, y + 26, kind, 12.5, color, bold=True))
        p.append(txt(74, y + 48, rep, 10.5, INK))
        p.append(txt(74, y + 68, detail, 10.5, MUTED))
        # 中间：闸门说明
        p.append(sketch_rect(470, y + 8, 330, rh - 16,
                             fill=TINT["blue"] if i in (1, 2) else
                             (TINT["orange"] if i in (0, 3) else "#ffffff")))
        p.append(txt(486, y + 34, gate.split("；")[0] if "；" in gate else gate,
                     11, INK, bold=True))
        rest = gate.split("；", 1)
        if len(rest) > 1:
            p.append(txt(486, y + 58, rest[1], 10.5, MUTED))
            p.append(txt(486, y + 78, "（同一类负例可能拆给两道闸门）", 10, MUTED))
        else:
            p.append(txt(486, y + 58, "＝ Pattern 的 match 里 return failure()", 10.5, MUTED))
        p.append(sketch_line(414, y + rh / 2, 464, y + rh / 2, arrow=True))
        # 右：判决
        p.append(sketch_rect(880, y + 8, 240, rh - 16, fill="#ffffff"))
        p.append(txt(1000, y + 40, verdict.split(" 或 ")[0], 12,
                     RED if "reject" in verdict.split(" 或 ")[0] else GREEN,
                     "middle", bold=True))
        if " 或 " in verdict:
            p.append(txt(1000, y + 62, "或", 10, MUTED, "middle"))
            p.append(txt(1000, y + 84, verdict.split(" 或 ")[1], 12,
                         GREEN, "middle", bold=True))
        p.append(sketch_line(804, y + rh / 2, 874, y + rh / 2, arrow=True))

    p.append(txt(60, 700, "判决的英文原名（今天新词，都用一句普通话解释过）：", 12, INK, bold=True))
    p.append(txt(76, 724, "identity 恒等拒绝 ＝ 拒绝也是一种动作：IR 逐字不变、代价账本不变、use 计数原样（失败无副作用，第 52 天的规矩）", 10.5, INK))
    p.append(txt(76, 746, "verifier_reject ＝ 图本身就是非法的：parse + verify 当场报错，Pattern 根本没机会看到它（错误信息见 outputs/*.err）", 10.5, INK))
    p.append(txt(76, 768, "半融合不动点 ＝ C08/M04 的结局：MatMul+Bias 照融，Relu 吸不走——fused_matmul_bias + relu 是所有路线的共同终点", 10.5, INK))
    p.append(sketch_rect(60, 786, 1060, 62, fill=TINT["red"], stroke=RED))
    p.append(txt(76, 810, "对照实验（真实运行）：拆掉类型闸门（--no-type-guard）后 C09/C11 变成 fused、C14 的第二道防线失效——", 11, RED, bold=True))
    p.append(txt(76, 832, "验收器立刻报警（11/14 ✘）。闸门必须双向验收：装着要拦得住，拆了要报得出。", 11, RED))
    p.append("</svg>")
    return "\n".join(p)


# ===================== 图 3：mini-accept 验收流程 =====================

def img_flow() -> str:
    W, H = 1180, 880
    p = [header(W, H,
                "mini-accept 的验收流程：同一份输入走两条遍历路，只能有一个判决",
                "左：三道检查的主流程（R1/R2）｜右上：两条遍历路的差异｜右下：Python 层补的 R3/R4")]

    p.append(sketch_rect(60, 118, 140, 44, fill="#ffffff"))
    p.append(txt(130, 145, "输入 .mlir", 12, INK, "middle", bold=True))

    p.append(sketch_line(130, 164, 130, 186, arrow=True))
    p.append(sketch_rect(48, 190, 164, 58, fill=TINT["blue"], stroke=BLUE))
    p.append(txt(130, 214, "闸门一：parse + verify", 11.5, BLUE, "middle", bold=True))
    p.append(txt(130, 234, "M08 / M09 / M10 在此拦下", 10, MUTED, "middle"))

    # 失败分支
    p.append(sketch_line(212, 219, 300, 219, arrow=True))
    p.append(sketch_rect(304, 194, 190, 50, fill=TINT["red"], stroke=RED))
    p.append(txt(399, 216, "verdict = verifier_reject", 11.5, RED, "middle", bold=True))
    p.append(txt(399, 236, "rc=0（期望吻合即通过）", 10, MUTED, "middle"))

    # 通过分支
    p.append(sketch_line(130, 250, 130, 286, arrow=True))
    p.append(txt(140, 272, "通过", 10.5, MUTED))

    # 两条遍历路
    p.append(sketch_line(130, 286, 96, 306, arrow=True))
    p.append(sketch_line(130, 286, 236, 306, arrow=True))
    p.append(sketch_rect(30, 310, 200, 92, fill="#ffffff"))
    p.append(txt(130, 334, "A 路：bottom-up", 12, ORANGE, "middle", bold=True))
    p.append(txt(130, 354, "自底向上访问（消费者先）", 10, MUTED, "middle"))
    p.append(txt(130, 374, "GreedyRewriteConfig 默认", 10, MUTED, "middle"))
    p.append(txt(130, 392, "P1+P2+P51g+P3＋类型闸门", 10, MUTED, "middle"))
    p.append(sketch_rect(206, 310, 200, 92, fill="#ffffff"))
    p.append(txt(306, 334, "B 路：top-down", 12, ORANGE, "middle", bold=True))
    p.append(txt(306, 354, "自顶向下访问（生产者先）", 10, MUTED, "middle"))
    p.append(txt(306, 374, "useTopDownTraversal = true", 10, MUTED, "middle"))
    p.append(txt(306, 392, "同一套 Pattern，只换顺序", 10, MUTED, "middle"))

    p.append(sketch_line(130, 402, 130, 428, arrow=True))
    p.append(sketch_line(306, 402, 306, 428, arrow=True))
    p.append(sketch_rect(48, 432, 340, 54, fill=TINT["orange"], stroke=ORANGE))
    p.append(txt(218, 454, "R1：两路最终算子名单必须相同", 11.5, ORANGE, "middle", bold=True))
    p.append(txt(218, 474, "Day 54 的教训写成断言：遍历顺序不能决定最终形态", 10, MUTED, "middle"))

    p.append(sketch_line(218, 486, 218, 512, arrow=True))
    p.append(sketch_rect(48, 516, 340, 54, fill=TINT["green"], stroke=GREEN))
    p.append(txt(218, 538, "R2：负例必须是恒等拒绝", 11.5, GREEN, "middle", bold=True))
    p.append(txt(218, 558, "融合后 IR 与输入逐字一致（expect=identity 时才检查）", 10, MUTED, "middle"))

    p.append(sketch_line(218, 570, 218, 596, arrow=True))
    p.append(sketch_rect(48, 600, 340, 50, fill="#ffffff"))
    p.append(txt(218, 622, "融合后 verify 复查 ＋ 判决", 11.5, INK, "middle", bold=True))
    p.append(txt(218, 641, "有 mini.fused* → fused，否则 identity", 10, MUTED, "middle"))

    p.append(sketch_line(218, 650, 218, 676, arrow=True))
    p.append(sketch_rect(88, 680, 260, 46, fill=TINT["green"], stroke=GREEN))
    p.append(txt(218, 702, "accept = PASS（rc=0）", 12, GREEN, "middle", bold=True))
    p.append(txt(218, 720, "否则 accept = FAIL（rc=1）", 10, MUTED, "middle"))

    # 右上：为什么两条路
    p.append(sketch_rect(470, 118, 650, 120, fill="#ffffff"))
    p.append(txt(486, 144, "为什么同一输入要走两条路？", 12.5, INK, bold=True))
    p.append(txt(486, 168, "第 54 天的抢跑事故：Pattern 集 [P51, P3] 只换访问顺序，最终形态一个 fused_add_relu+matmul、", 10.5, INK))
    p.append(txt(486, 188, "一个 fused_matmul_bias_relu——都合法、都收敛、verify 都通过。所以「verify 通过 ≠ 融对了」；", 10.5, INK))
    p.append(txt(486, 208, "今天把「两种遍历殊途同归」写进验收器，成了对 Pattern 集本身的要求（R1）。", 10.5, INK))
    p.append(txt(486, 228, "今天的验收管道（让位版 P51g ＋ 类型闸门）在全部 24 例上 R1 均 PASS。", 10.5, GREEN, bold=True))

    # 右中：决策日志样例
    p.append(sketch_rect(470, 254, 650, 128, fill="#ffffff"))
    p.append(txt(486, 280, "看得见的拒绝：每次 match 向 stderr 打一行决策日志（M06 f64_add_relu 真实记录）", 12, INK, bold=True))
    log = ["[P2] 访问 Relu：操作数由 mini.add 定义 -> 不匹配",
           "[P51g] 类型边界：元素类型非 f32 -> 拒绝",
           "（fused_add_relu 的语义只对 f32 验证过）",
           "verdict=identity  accept=PASS"]
    for i, line in enumerate(log):
        color = INK if i < 3 else GREEN
        p.append(txt(502, 304 + i * 20, line, 10.5, color,
                     bold=(i == 3)))

    # 右下：Python 层
    p.append(sketch_rect(470, 398, 650, 148, fill=TINT["blue"], stroke=BLUE))
    p.append(txt(486, 424, "MLIR 壳做不了的两件事，由 Python 层补上（mini_fuse_accept.py）", 12, BLUE, bold=True))
    p.append(txt(486, 450, "R3 数值对账：evaluate() 按程序序求值，融合前后所有输出 numpy allclose——", 10.5, INK))
    p.append(txt(502, 470, "结构检查（verify/IR）证明「图没坏」，数值对账证明「语义没变」，缺一不可。", 10.5, INK))
    p.append(txt(486, 496, "R4 二次防线：对 Verifier 负例关掉 verify 复跑，Pattern 的第二道防线必须仍然拦下", 10.5, INK))
    p.append(txt(502, 516, "（C12/C13/C14 全部 IR 恒等）。拆掉类型闸门的对照实验见 outputs/python-accept-no-type-guard.txt。", 10.5, INK))
    p.append(txt(486, 540, "MLIR 壳没有解释器，不伪造运行数据——R3/R4 如实标注「在 Python 层完成」。", 10, MUTED))

    # 底部：结果
    p.append(sketch_rect(470, 566, 650, 100, fill="#ffffff"))
    p.append(txt(486, 592, "真实运行结果（2026-11-12，g++ 9.4.0 / LLVM 18.1.8 / aarch64 Linux）：", 11.5, INK, bold=True))
    p.append(txt(486, 616, "Python 层 14/14 通过（outputs/python-accept-full.txt）；单元测试 16/16 OK（test_negative_acceptance.py）；", 11, GREEN))
    p.append(txt(486, 638, "MLIR 层 10/10 通过（mlir-mini/outputs/accept-summary.txt）；对照实验 11/14 失守（设计如此，验收器报警）。", 11, GREEN))
    p.append(txt(486, 658, "主线图优化前后：matmul+add+relu 3 算子 → fused_matmul_bias_relu 1 算子（代价账本 8 → 4）。", 11, ORANGE))

    p.append(txt(60, 756, "一句话：验收器不是「再写一个 Pass」，而是把 51～54 的规则变成可执行的断言语料——", 11.5, INK))
    p.append(txt(60, 778, "正例答「融到什么形态」，负例答「以什么姿态不融」，两层各跑一遍，答案必须一致。", 11.5, INK))
    p.append("</svg>")
    return "\n".join(p)


# ===================== 图 4：结果矩阵与对照实验 =====================

def img_results() -> str:
    W, H = 1180, 900
    p = [header(W, H,
                "验收结果矩阵：24 例判决一览 ＋ 拆闸门对照实验",
                "左：Python 层 14 例与 MLIR 层 10 例的判决表｜右：--no-type-guard 对照实验的三处失守")]

    # 左：判决表
    p.append(txt(60, 104, "验收语料判决表（真实运行，全部通过）", 13, INK, bold=True))
    rows = [
        ("C01～C04 正例", "bias_relu / bias_only / add_relu / 左 bias", "fused", GREEN),
        ("C05～C06 假负例", "relu 结果多用 / bias 两链共用", "fused", GREEN),
        ("C08 额外使用", "加法结果被 return 共用", "fused（半融合）", GREEN),
        ("C07 多使用者", "乘积被 add＋relu 共用", "identity", ORANGE),
        ("C09 / C11 类型", "全 f64 add / 混 dtype bias", "identity", ORANGE),
        ("C10 歧义", "add 两侧都是 matmul", "identity", ORANGE),
        ("C12～C13 Shape", "Mismatch / 需广播", "verifier_reject", BLUE),
        ("C14 类型(Verifier)", "f64 matmul 链", "verifier_reject", BLUE),
    ]
    ty, rh = 118, 42
    p.append(sketch_rect(60, ty, 560, 30, fill=TINT["blue"]))
    p.append(txt(74, ty + 20, "用例", 11, INK, bold=True))
    p.append(txt(250, ty + 20, "特征", 11, INK, bold=True))
    p.append(txt(540, ty + 20, "判决", 11, INK, "middle", bold=True))
    for i, (name, feat, verdict, color) in enumerate(rows):
        y = ty + 32 + i * rh
        p.append(sketch_rect(60, y, 560, rh - 6, fill="#ffffff"))
        p.append(txt(74, y + 25, name, 10.5, INK, bold=True))
        p.append(txt(250, y + 25, feat, 10, MUTED))
        p.append(txt(540, y + 25, verdict, 10.5, color, "middle", bold=True))
    y_end = ty + 32 + len(rows) * rh
    p.append(txt(60, y_end + 22, "Python 层 14/14 ✔（C01～C14） · MLIR 层 10/10 ✔（M01～M10 对应上述八类，两层判决一一吻合）",
                 11, GREEN, bold=True))

    # 右：对照实验
    p.append(txt(700, 104, "拆闸门对照实验：--no-type-guard（真实运行）", 13, RED, bold=True))
    p.append(sketch_rect(700, 118, 420, 240, fill=TINT["red"], stroke=RED))
    p.append(txt(716, 144, "类型闸门拆除后，验收器必须报警——这正是它的职责：", 11, RED, bold=True))
    fails = [
        ("C09 f64_add_relu", "identity → fused ✘", "fused_add_relu 融掉了 f64 图"),
        ("C11 mixed_dtype_bias", "identity → fused ✘", "f32 乘积 ＋ f64 bias 被融成一坨"),
        ("C14 f64_matmul_chain", "第二道防线失效 ✘", "绕过 verify 复跑时 6→4，IR 被改写"),
    ]
    for i, (name, change, why) in enumerate(fails):
        y = 168 + i * 62
        p.append(txt(716, y, name, 11, INK, bold=True))
        p.append(txt(716, y + 20, change, 11, RED, bold=True))
        p.append(txt(900, y, why, 10, MUTED))
    p.append(txt(716, 340, "汇总 11/14 ✘——三处失守全部被验收器抓到，一处都没有静默漏过。", 11, RED, bold=True))

    # 右下：C08 半融合 + 主线优化前后
    p.append(txt(700, 392, "两个值得盯住的正例细节", 13, INK, bold=True))
    p.append(sketch_rect(700, 406, 420, 150, fill="#ffffff"))
    p.append(txt(716, 432, "① C08/M04 半融合不动点：", 11, INK, bold=True))
    p.append(txt(716, 452, "fused_matmul_bias ＋ relu（Relu 吸不走——%s 的第二个使用者", 10, INK))
    p.append(txt(716, 470, "是 return，删不得）。两种遍历、两条路线全停在同一形态。", 10, INK))
    p.append(txt(716, 498, "② 主线图 C01 优化前后：", 11, INK, bold=True))
    p.append(txt(716, 518, "matmul＋add＋relu（3 算子，代价 8） → fused_matmul_bias_relu", 10, INK))
    p.append(txt(716, 536, "（1 算子，代价 4）——注意这只是「第 53 天口径的记账」，不是实测耗时。", 10, MUTED))

    # 底部：怎么复跑
    p.append(txt(60, 545, "复跑方式（第 8 周工程惯例）：", 12, INK, bold=True))
    cmds = [
        "cd code && python3 mini_fuse_accept.py                # 14/14",
        "cd code && python3 mini_fuse_accept.py --no-type-guard  # 11/14 ✘（对照）",
        "cd code && python3 test_negative_acceptance.py         # 16 tests OK",
        "cd code/mlir-mini && ninja -C build mini-accept && bash run_all.sh  # 10/10",
    ]
    for i, c in enumerate(cmds):
        p.append(txt(76, 571 + i * 26, c, 11, INK))

    p.append(txt(60, 700, "验收清单背后的三条硬标准：", 12, INK, bold=True))
    p.append(txt(76, 726, "R1 正例两种遍历同形态（顺序不能决定结果） · R2 负例恒等拒绝（无副作用） · R3 数值对账（语义没变）", 11, INK))
    p.append(txt(76, 748, "加上 R4 二次防线（Verifier 拦过的，Pattern 也拦得住）——四条都过，才叫「边界画完了」。",
                 11, INK))
    p.append(txt(60, 790, "下一步（不抢跑）：第 56 天做第 8 周复盘；收益账本（CostModel）在第 74 天才建，广播放行在第 60 天。",
                 10.5, MUTED))
    p.append("</svg>")
    return "\n".join(p)


def main():
    for name, fn in [("01-overview", img_overview),
                     ("02-gates", img_gates),
                     ("03-acceptance-flow", img_flow),
                     ("04-results-matrix", img_results)]:
        path = OUT / f"{name}.svg"
        path.write_text(fn(), encoding="utf-8")
        print(f"wrote {path} ({path.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
