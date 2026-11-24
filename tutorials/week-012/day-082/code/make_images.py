#!/usr/bin/env python3
"""生成第 82 天教程的 4 张手绘风（Excalidraw-like）SVG 技术图。

运行方式：
    python3 make_images.py

输出到 ../images/ 目录：
    01-overview.svg       今天在数值精度周与编译链路中的位置 + 三类转换节点
    02-mechanism.svg      核心机制：格点幂等（Q 往返零位移）+ Cast 往返方向律
    03-rules.svg          13 条消除规则表的图形版（SAFE/CONDITIONAL/UNSAFE）
    04-before-after.svg   贯穿例子：安全优化与 naive 优化的真实对照数据

风格与 Day 78~81 保持一致：手绘抖动线条、马克笔笔触、米白背景、
蓝/橙/绿/红四种柔和强调色、简单几何形状。
图中数值全部来自 qdq_lab.py 的真实运行结果。
"""

import math
import random
from pathlib import Path

random.seed(82)

INK = "#3b3b3b"
SOFT = "#6b6459"
BLUE = "#5f8fcb"
ORANGE = "#e8973f"
GREEN = "#79b26a"
RED = "#d96c5c"
BG = "#fdf9f0"
L_BLUE = "#dbe7f6"
L_ORANGE = "#fdead3"
L_GREEN = "#e5f1dc"
L_RED = "#f9dfd9"
FONT = "'Comic Sans MS','Segoe Print','Bradley Hand','Kaiti SC','KaiTi','STKaiti',cursive"

OUT = Path(__file__).resolve().parent.parent / "images"


def jseg(x1, y1, x2, y2, amp=1.3):
    dx, dy = (x2 - x1) / 2.0, (y2 - y1) / 2.0
    a = random.uniform(-amp, amp)
    b = random.uniform(-amp, amp)
    c = random.uniform(-amp, amp)
    d = random.uniform(-amp, amp)
    e = random.uniform(-amp, amp)
    f = random.uniform(-amp, amp)
    return (f"M {x1 + a:.1f},{y1 + b:.1f} Q {x1 + dx + c:.1f},{y1 + dy + d:.1f} "
            f"{x2 + e:.1f},{y2 + f:.1f}")


def style(fill="none", stroke=INK, sw=2.2, dash=None):
    s = (f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}" '
         f'stroke-linecap="round" stroke-linejoin="round"')
    if dash:
        s += f' stroke-dasharray="{dash}"'
    return s


def srect(x, y, w, h, fill="none", stroke=INK, sw=2.2, amp=1.3, dash=None, rx=6):
    pts = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
    d = " ".join(jseg(*p, *q, amp) for p, q in zip(pts, pts[1:] + pts[:1]))
    return f'<path d="{d} Z" {style(fill, stroke, sw, dash)} rx="{rx}"/>'


def sline(x1, y1, x2, y2, stroke=INK, sw=2.2, dash=None, amp=1.3):
    return f'<path d="{jseg(x1, y1, x2, y2, amp)}" {style("none", stroke, sw, dash)}/>'


def head(x, y, ang, stroke, sw, l=13, spread=0.46):
    a1 = (x - l * math.cos(ang - spread), y - l * math.sin(ang - spread))
    a2 = (x - l * math.cos(ang + spread), y - l * math.sin(ang + spread))
    return (f'<path d="{jseg(x, y, a1[0], a1[1], 0.7)}" {style("none", stroke, sw)}/>'
            f'<path d="{jseg(x, y, a2[0], a2[1], 0.7)}" {style("none", stroke, sw)}/>')


def arrow(x1, y1, x2, y2, stroke=INK, sw=2.2, dash=None):
    ang = math.atan2(y2 - y1, x2 - x1)
    return (f'<path d="{jseg(x1, y1, x2, y2)}" {style("none", stroke, sw, dash)}/>'
            + head(x2, y2, ang, stroke, sw))


def carrow(p0, ctrl, p1, stroke=INK, sw=2.2, dash=None):
    d = f"M {p0[0]:.1f},{p0[1]:.1f} Q {ctrl[0]:.1f},{ctrl[1]:.1f} {p1[0]:.1f},{p1[1]:.1f}"
    ang = math.atan2(p1[1] - ctrl[1], p1[0] - ctrl[0])
    return f'<path d="{d}" {style("none", stroke, sw, dash)}/>' + head(p1[0], p1[1], ang, stroke, sw)


def text(x, y, s, size=16, fill=INK, anchor="start", rot=None):
    t = (f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-size="{size}" '
         f'fill="{fill}"')
    if rot:
        t += f' transform="rotate({rot} {x} {y})"'
    return t + f">{s}</text>"


def svg_doc(w, h, body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
            f'width="{w}" height="{h}">'
            f'<rect x="3" y="3" width="{w - 6}" height="{h - 6}" rx="7" fill="{BG}"/>'
            f'<g font-family="{FONT}">' + body + "</g></svg>")


def chip(x, y, label, fill, tfill=INK, w=None, h=26, size=15):
    w = w or (len(label) * (size * 0.62) + 18)
    body = srect(x, y, w, h, fill=fill, stroke=fill, sw=1.6, amp=0.9)
    body += text(x + w / 2, y + h * 0.72, label, size, tfill, "middle")
    return body, w


def node(x, y, label, fill="white", stroke=INK, w=58, h=32, size=15, dash=None):
    body = srect(x, y, w, h, fill=fill, stroke=stroke, sw=2.0, amp=0.8, dash=dash)
    body += text(x + w / 2, y + h * 0.66, label, size, INK, "middle")
    return body


def strike(x, y, w, h, color=RED, sw=2.6):
    return (sline(x - 4, y - 4, x + w + 4, y + h + 4, color, sw, amp=0.6) +
            sline(x + w + 4, y - 4, x - 4, y + h + 4, color, sw, amp=0.6))


def check_icon(x, y, color=GREEN, sw=3.0, s=1.0):
    return (sline(x - 8 * s, y + 1 * s, x - 2 * s, y + 7 * s, color, sw, 0.4) +
            sline(x - 2 * s, y + 7 * s, x + 9 * s, y - 7 * s, color, sw, 0.4))


def cross_icon(x, y, color=RED, sw=3.0):
    return (sline(x - 7, y - 7, x + 7, y + 7, color, sw, 0.4) +
            sline(x + 7, y - 7, x - 7, y + 7, color, sw, 0.4))


def title_bar(y, main, sub=None):
    body = text(28, y, main, 24, INK)
    if sub:
        body += text(28, y + 26, sub, 15, SOFT)
    return body


# ---------------------------------------------------------------- 图 1：位置

def draw_overview():
    W, H = 1120, 640
    b = title_bar(46, "Day 82: 量化图里的转换节点 —— 今天在整条链路的哪里？",
                  "昨天造尺（QAT 校准），今天修图：图里成串的 Q/DQ/Cast 哪些能删、哪些删了就错")

    # 上排：本周日程
    days = [("D78 浮点误差", 0.86), ("D79 判据工具", 0.86), ("D80 浮点三税", 0.86),
            ("D81 造刻度尺", 1.06), ("D82 修图", 1.32), ("D83 集成验收", 0.86),
            ("D84 复盘", 0.72)]
    x = 30
    bw, bh, y0 = 128, 34, 86
    centers = []
    for label, scale in days:
        w = bw * scale
        today = "D82" in label
        fill = L_ORANGE if today else ("white" if scale < 1.2 else L_BLUE)
        b += srect(x, y0, w, bh, fill=fill, stroke=ORANGE if today else INK,
                   sw=2.6 if today else 1.8, amp=0.8)
        b += text(x + w / 2, y0 + 23, label, 15, INK if not today else "#8a5a17", "middle")
        centers.append((x, x + w))
        x += w + 18
    for (a1, a2), (c1, c2) in zip(centers, centers[1:]):
        b += arrow(a2 + 2, y0 + bh / 2, c1 - 2, y0 + bh / 2, INK, 1.8)
    b += text(30, y0 - 8, "第 12 周（数值精度与量化）", 14, SOFT)

    # 中排：编译链路
    y1, bh1 = 168, 56
    stages = [("图输入", "算子+成串\nQ/DQ/Cast", 0.9, False),
              ("合法性检查", "Day 12/39", 0.78, False),
              ("图优化", "QDQ/Cast 冗余消除\n（今天）", 1.5, True),
              ("融合/Layout", "Day 50~70", 0.9, False),
              ("Lowering", "Day 85+", 0.78, False),
              ("执行", "CPU/硬件", 0.72, False)]
    x = 34
    centers = []
    for label, sub, scale, today in stages:
        w = 118 * scale
        fill = L_ORANGE if today else "white"
        b += srect(x, y1, w, bh1, fill=fill, stroke=ORANGE if today else INK,
                   sw=2.6 if today else 1.8, amp=0.9)
        b += text(x + w / 2, y1 + 21, label, 16, INK, "middle")
        for i, ln in enumerate(sub.split("\n")):
            b += text(x + w / 2, y1 + 37 + i * 15, ln, 12.5, SOFT, "middle")
        centers.append((x, x + w))
        x += w + 46
    for (a1, a2), (c1, c2) in zip(centers, centers[1:]):
        b += arrow(a2 + 3, y1 + bh1 / 2, c1 - 3, y1 + bh1 / 2, INK, 2.0)
    b += text(W / 2, y1 + bh1 + 62,
              "删掉『删了不变』的转换节点，其余登记进规则表 —— 不急着实现不安全的 Pattern",
              14.5, SOFT, "middle")

    # 下排：三类节点卡片
    y2, ch = 300, 250
    cards = [
        (30, 250, "Quantize / Dequantize：『门票』", BLUE, L_BLUE,
         ["带着刻度尺的转换节点：", "每张门票自带 (scale, zero_point)",
          "码 ≠ 数：0.5 的码是 -92，", "离开 (s, zp) 谁也不知道它是什么",
          "成对出现，标注『这条边量化了』"]),
        (320, 250, "Cast：『搬运工』", GREEN, L_GREEN,
         ["只换表示，不带任何元数据：", "放宽无损：int8→int32 精确",
          "收窄失真：32258→127(饱和)", "          或→2(回绕)",
          "fp 收窄：0.1 只剩一半精度再丢"]),
        (610, 250, "算子：『干活的人』", ORANGE, L_ORANGE,
         ["Relu / Add / MatMul 本体：", "被 QDQ 夹着 → 量化岛",
          "被 Cast 夹着 → 三明治(改口径)", "岛和三明治都不能白拆，",
          "要证明等价才动 —— 这是规则表"]),
        (895, 195, "判定三问", RED, L_RED,
         ["① 参数一致吗？(s, zp)", "② 值已在格上吗？", "③ 放宽在前还是收窄在前？",
          "三问全过 → 可以删；", "差一条 → 登记，不动手"]),
    ]
    for cx, cw, name, accent, laccent, lines in cards:
        b += srect(cx, y2, cw, ch, fill="white", stroke=accent, sw=2.4, amp=1.0)
        b += srect(cx, y2, cw, 40, fill=laccent, stroke=accent, sw=2.2, amp=0.9)
        b += text(cx + cw / 2, y2 + 27, name, 16 if cw > 200 else 15.5, INK, "middle")
        for i, ln in enumerate(lines):
            b += text(cx + 14, y2 + 68 + i * 26, ln, 13.5, INK)
    b += text(30, y2 - 10, "今天要分清的三类角色 + 一套判定问题", 14, SOFT)
    b += sline(28, 620, W - 28, 620, SOFT, 1.2, "2 6")
    b += text(W / 2, 634, "判定口径：bit-exact（删了逐位不变）—— 对应 Day 79 的误差判据思想：不变才叫冗余",
              13.5, SOFT, "middle")
    return svg_doc(W, H, b)


# ---------------------------------------------------------------- 图 2：机制

def draw_mechanism():
    W, H = 1120, 716
    b = title_bar(44, "为什么有的 Q→DQ 能删、有的不能：格点幂等 + 方向决定往返",
                  "左：值在不在格上，决定 Q 往返有没有位移；右：放宽在前才恒等；下：Cast 与 Quantize 的语义边界")

    # ---- 左上：格点幂等（QDQ）----
    b += srect(28, 92, 520, 268, fill="white", stroke=BLUE, sw=2.4, amp=1.1)
    b += text(44, 120, "情况 A：值不在格上 —— 删 = 变值（R06 拒删）", 15.5, INK)
    gx, gy, gw = 60, 150, 440
    for i in range(0, 9):
        xx = gx + i * (gw / 8)
        b += sline(xx, gy, xx, gy + 16, SOFT, 1.6, 0.4)
        if i % 2 == 0:
            b += text(xx, gy + 32, f"{i * 0.5:.1f}", 12.5, SOFT, "middle")
    b += sline(gx, gy + 46, gx + gw, gy + 46, SOFT, 1.4)
    # x = 1.3 落在 1.0~1.5 之间，靠档到 1.5
    fx = gx + 2.6 * (gw / 8)
    b += text(fx, gy - 8, "x = 1.3（格间）", 13, RED, "middle")
    b += f'<circle cx="{fx:.0f}" cy="{gy + 46}" r="6" fill="{RED}"/>'
    hx = gx + 3 * (gw / 8)
    b += f'<circle cx="{hx:.0f}" cy="{gy + 46}" r="6" fill="{GREEN}"/>'
    b += arrow(fx, gy + 62, hx - 4, gy + 62, RED, 2.2)
    b += text((fx + hx) / 2 + 90, gy + 82, "Q→DQ 靠档：x̂ = 1.5（位移 0.2 ≤ 半格）", 13, RED, "middle")
    b += text(44, 250, "删掉这对 → 读数从 1.5 变回 1.3 —— 图变了", 13.5, INK)
    b += text(44, 278, "所以裸 Q→DQ 不是 no-op：它就是『把值放上格点』这个动作本身", 13.5, INK)
    b += text(44, 304, "QAT 语义下删它 = 取消这条边的量化 —— 策略决定，不是优化", 13.5, SOFT)

    b += srect(28, 376, 520, 268, fill="white", stroke=GREEN, sw=2.4, amp=1.1)
    b += text(44, 404, "情况 B：值已在格上 —— 删了逐位不变（R03 可删）", 15.5, INK)
    gx, gy = 60, 434
    for i in range(0, 9):
        xx = gx + i * (gw / 8)
        b += sline(xx, gy, xx, gy + 16, SOFT, 1.6, 0.4)
        if i % 2 == 0:
            b += text(xx, gy + 32, f"{i * 0.5:.1f}", 12.5, SOFT, "middle")
    b += sline(gx, gy + 46, gx + gw, gy + 46, SOFT, 1.4)
    # x2 = 2.0 恰在格点
    hx = gx + 4 * (gw / 8)
    b += f'<circle cx="{hx:.0f}" cy="{gy + 46}" r="6" fill="{GREEN}"/>'
    b += text(hx, gy - 8, "x₂ = 2.0（格点上）", 13, GREEN, "middle")
    b += text(44, 530, "Q(x₂) 精确回码、DQ 原样带回 —— 往返位移 = 0", 13.5, INK)
    b += text(44, 558, "账本：x₂/s = s·(q−z)/s = (q−z)(1+ε)，|m·ε| ≈ 6e-14", 13.5, INK)
    b += text(44, 584, "离 0.5 的靠档边界差 13 个数量级 → round 必中回 m → 幂等", 13.5, INK)
    b += check_icon(52, 626, GREEN)
    b += text(70, 622, "qdq(qdq(x)) == qdq(x)：10 万随机值 ×3 批逐位相等（实验 2 实测）", 13.5, GREEN)

    # ---- 右侧：Cast 往返方向 ----
    rx = 572
    b += srect(rx, 92, 520, 268, fill="white", stroke=RED, sw=2.4, amp=1.1)
    b += text(rx + 16, 120, "收窄在前 —— 往返必失真（R09/R10 禁删）", 15.5, INK)
    b += node(rx + 30, 156, "int32", fill=L_RED, stroke=RED)
    b += node(rx + 130, 156, "int8", fill=L_RED, stroke=RED)
    b += node(rx + 230, 156, "int32", fill=L_RED, stroke=RED)
    b += arrow(rx + 30 + 58, 172, rx + 130, 172, RED, 2.0)
    b += arrow(rx + 130 + 58, 172, rx + 230, 172, RED, 2.0)
    b += text(rx + 88, 194, "截断", 12.5, RED, "middle")
    b += text(rx + 188, 194, "复原≠原值", 12.5, RED, "middle")
    b += text(rx + 30, 226, "32258 → 饱和 127 / 回绕 2（实测）", 14, INK)
    b += text(rx + 30, 252, "fp 同理：fp32→fp16→fp32，max rel err 4.87e-4（实测）", 14, INK)
    b += text(rx + 30, 278, "1e5 → inf：连『有损』都算不上，直接没了", 14, INK)
    b += text(rx + 30, 316, "一句话：信息先丢了，回来就补不齐", 13.5, SOFT)

    b += srect(rx, 376, 520, 268, fill="white", stroke=GREEN, sw=2.4, amp=1.1)
    b += text(rx + 16, 404, "放宽在前 —— 无损往返（R02 可删）", 15.5, INK)
    b += node(rx + 30, 440, "int8", fill=L_GREEN, stroke=GREEN)
    b += node(rx + 130, 440, "int32", fill=L_GREEN, stroke=GREEN)
    b += node(rx + 230, 440, "int8", fill=L_GREEN, stroke=GREEN)
    b += arrow(rx + 88, 456, rx + 130, 456, GREEN, 2.0)
    b += arrow(rx + 188, 456, rx + 230, 456, GREEN, 2.0)
    b += text(rx + 88, 478, "精确", 12.5, GREEN, "middle")
    b += text(rx + 188, 478, "截而不丢", 12.5, GREEN, "middle")
    b += text(rx + 30, 510, "127 → 127 → 127：256 个码 int32 全装得下", 14, INK)
    b += text(rx + 30, 536, "fp16→fp32 同理：fp16 的每个值 fp32 都精确表示", 14, INK)
    b += text(rx + 30, 574, "所以判定只看一件事：第一跳是放宽还是收窄", 13.5, INK)
    b += check_icon(rx + 40, 614, GREEN)
    b += text(rx + 58, 610, "int8→int32→int8：np.array_equal == True（实测）", 13.5, GREEN)

    # ---- 底部横条：Cast vs Quantize ----
    b += srect(28, 652, 1064, 52, fill=L_BLUE, stroke=BLUE, sw=2.2, amp=0.9)
    b += text(44, 674, "语义边界：Cast ≠ Quantize", 15, INK)
    b += text(252, 674, "Cast(0.5→int8) = 0（小数被截断，没有元数据）；Q(0.5) = −92（码，配 (s=0.0137, zp=−128) 才解码回 0.4941）", 14, INK)
    return svg_doc(W, H, b)


# ---------------------------------------------------------------- 图 3：规则表

def draw_rules():
    W, H = 1150, 840
    b = title_bar(44, "转换节点消除规则表（13 条）—— 图形版",
                  "绿色 = bit-exact 可删 · 橙色 = 登记/策略 · 红色 = 禁删；数字与判定均来自 qdq_lab.py 真实运行")

    cells = [
        ("R01", "Cast(T→T)", "同型转型，恒等", "SAFE", GREEN, L_GREEN),
        ("R02", "放宽→收窄回", "int8→int32→int8 无损往返", "SAFE", GREEN, L_GREEN),
        ("R03", "同参 DQ→Q→DQ", "值已在格上，删尾对幂等", "SAFE", GREEN, L_GREEN),
        ("R04", "DQ(Q(const))", "编译期常量折叠", "SAFE", GREEN, L_GREEN),
        ("R05", "Q→Cast(放宽)→DQ", "Cast 值不变，合并重标注", "SAFE", GREEN, L_GREEN),
        ("R06", "裸 Q→DQ 单对", "删 = 取消该边量化：x̂→x，≤1 格", "CONDITIONAL", ORANGE, L_ORANGE),
        ("R07", "Q(s₁,z₁)→DQ(s₂,z₂)", "参数不同 = requant：0.5→−2.54", "UNSAFE", RED, L_RED),
        ("R08", "码张量多使用者", "删除即断链：naive 实测 KeyError", "UNSAFE", RED, L_RED),
        ("R09", "fp32→fp16→fp32", "舍入 4.9e-4 + 溢出 inf，非恒等", "UNSAFE", RED, L_RED),
        ("R10", "int32→int8→int32", "饱和/回绕：32258→127 / 2", "UNSAFE", RED, L_RED),
        ("R11", "Cast 三明治包算子", "算子换口径算：0.1+0.2 变 0.29993", "UNSAFE", RED, L_RED),
        ("R12", "DQ→op→Q 量化岛", "折叠需整数语义证明（Relu 可证）", "CONDITIONAL", ORANGE, L_ORANGE),
    ]
    cw, chh = 356, 118
    x0, y0, gap = 28, 116, 14
    for idx, (rid, pattern, reason, verdict, accent, laccent) in enumerate(cells):
        r, c = divmod(idx, 3)
        x = x0 + c * (cw + gap)
        y = y0 + r * (chh + gap)
        b += srect(x, y, cw, chh, fill="white", stroke=accent, sw=2.2, amp=1.0)
        tag, tw = chip(x + 12, y + 10, rid, accent, "white", size=14)
        b += tag
        vt, vw = chip(x + cw - 12 - len(verdict) * 9.6 - 18, y + 10, verdict, laccent, accent, size=13)
        b += vt
        b += text(x + 14, y + 62, pattern, 16.5, INK)
        b += text(x + 14, y + 90, reason, 13.5, SOFT)
        if rid in ("R01", "R02", "R03", "R04", "R05"):
            b += check_icon(x + cw - 26, y + 78, GREEN)
        elif verdict == "UNSAFE":
            b += cross_icon(x + cw - 26, y + 74, RED)
        else:
            b += text(x + cw - 40, y + 82, "登记", 13.5, ORANGE)

    # R13 横幅
    y = y0 + 4 * (chh + gap) + 6
    b += srect(28, y, W - 56, 84, fill=L_BLUE, stroke=BLUE, sw=2.4, amp=1.0)
    b += text(46, y + 32, "R13 语义边界声明：Cast 顶替不了 Quantize", 17, INK)
    b += text(46, y + 64, "Cast 只换表示、不带 (s, zp) 元数据：Cast(0.5) = 0；Quantize 是带元数据的量程映射：Q(0.5) = −92 码 → DQ 解码 0.4941", 14.5, INK)
    b += text(W / 2, H - 22, "产出口径：本表即当天『优化规则表』—— 不实现 UNSAFE Pattern，CONDITIONAL 只登记不动手", 14, SOFT, "middle")
    return svg_doc(W, H, b)


# ---------------------------------------------------------------- 图 4：前后对照

def draw_before_after():
    W, H = 1150, 760
    b = title_bar(44, "贯穿例子：同一个图，安全优化 vs naive 优化（真实运行数据）",
                  "x = [−1.2, −0.5, 0.5, 1.0, 3.5]，s = 0.0137，zp = −128；每条结论都由 qdq_lab.py 实测复现")

    # 上：优化前 8 节点
    y0 = 100
    b += text(30, y0 - 10, "优化前：8 节点（分类器打标）", 15, SOFT)
    chain = [("x", 34, "input"), ("Q", "q1", "q"), ("DQ", "x1", "dq"), ("Relu", "r", "op"),
             ("Q", "q2", "q"), ("DQ", "x2", "dq"), ("Q", "q3", "q"), ("DQ", "out", "dq")]
    x = 70
    fills = {"input": L_BLUE, "q": "white", "dq": "white", "op": L_ORANGE}
    positions = {}
    for label, name, kind in chain:
        w = 56 if kind != "input" else 40
        b += node(x, y0, label, fill=fills[kind], w=w)
        positions[name] = (x, x + w, y0)
        x += w + 62
        if (label, name) != ("DQ", "out"):
            b += arrow(x - 60, y0 + 16, x - 4, y0 + 16, INK, 1.8)
    # 标签
    tags = [("R06 · 策略", "q1", RED, -46), ("R12 · 登记", "r", ORANGE, -80),
            ("R06 · 策略", "q2", RED, -46), ("R03 · SAFE", "q3", GREEN, -46)]
    for label, name, color, dy in tags:
        px0, px1, py = positions[name]
        mid = (px0 + px1) / 2
        b += carrow((mid, py + 34), (mid, py + 50), (mid, py + 46 - dy), color, 1.8, "3 4")
        wpx = len(label) * 9.4 + 14
        b += srect(mid - wpx / 2, py + 48 - dy, wpx, 24, fill="white", stroke=color,
                   sw=1.6, amp=0.7)
        b += text(mid, py + 65 - dy, label, 12.5, color, "middle")

    # 左下：安全路径
    y1 = 268
    b += srect(28, y1, 528, 208, fill="white", stroke=GREEN, sw=2.6, amp=1.0)
    b += check_icon(50, y1 + 26, GREEN)
    b += text(68, y1 + 30, "安全优化：只删 R03（q3/out 这对）", 16, INK)
    chain2 = ["x", "Q", "DQ", "Relu", "Q", "DQ"]
    x = 60
    prev_end = None
    for label in chain2:
        w = 40 if label == "x" else 56
        b += node(x, y1 + 58, label, fill=L_BLUE if label == "x" else "white", w=w)
        prev_end = x + w
        x += w + 34
        if prev_end < 500:
            b += arrow(prev_end + 4, y1 + 74, x - 4, y1 + 74, INK, 1.8)
    b += text(46, y1 + 128, "8 → 6 节点；R06 两个裸对、R12 量化岛：登记不动", 14, INK)
    b += text(46, y1 + 154, "位等价验证：固定输入 + 3 组 × 10000 随机输入", 14, INK)
    b += text(46, y1 + 180, "np.array_equal 全部 True（|diff|max = 0.0）", 14, GREEN)

    # 右下：naive 路径
    y2 = 268
    b += srect(572, y1, 550, 208, fill="white", stroke=RED, sw=2.6, amp=1.0)
    b += cross_icon(594, y1 + 26, RED)
    b += text(612, y1 + 30, "naive 优化：见到同参 Q→DQ 一律删（3 对全删）", 16, INK)
    b += node(600, y1 + 58, "x", fill=L_RED, stroke=RED, w=40)
    b += node(690, y1 + 58, "Relu", fill=L_RED, stroke=RED)
    b += strike(690, y1 + 58, 58, 32, RED)
    b += strike(600, y1 + 58, 40, 32, RED, 2.0)
    b += arrow(642, y1 + 74, 688, y1 + 74, RED, 2.0)
    b += text(600, y1 + 128, "out: 0.4941 → 0.5（diff 0.0059） · 1.0020 → 1.0（0.0020）", 14, INK)
    b += text(600, y1 + 154, "它删对了双对（幂等），删错了单对（变值）——", 14, INK)
    b += text(600, y1 + 180, "同一个长相的 pattern，上下文决定安全性", 14, RED)

    # 底部：naive 在另外两类图上的真实下场
    y3 = 506
    b += text(30, y3 - 8, "naive 在另外两类图上的真实下场（实验 3/T04/T03 实测）", 15, SOFT)
    b += srect(28, y3, 334, 180, fill="white", stroke=RED, sw=2.2, amp=0.9)
    b += text(44, y3 + 30, "requant 图（R07）", 15, INK)
    b += text(44, y3 + 58, "Q(s,zp=−128) → DQ(s′,zp=0)", 13.5, INK)
    b += text(44, y3 + 86, "0.5 的码 −92 用错尺子解码", 13.5, INK)
    b += text(44, y3 + 114, "→ −2.5354（正确值 0.4941）", 14, RED)
    b += text(44, y3 + 150, "参数检查必须是第一道闸", 13.5, SOFT)

    b += srect(386, y3, 334, 180, fill="white", stroke=RED, sw=2.2, amp=0.9)
    b += text(402, y3 + 30, "多使用者图（R08）", 15, INK)
    b += text(402, y3 + 58, "q1 同时喂 DQ 和 Cast 导出", 13.5, INK)
    b += text(402, y3 + 86, "naive 删掉 Q，Cast 读悬空名字", 13.5, INK)
    b += text(402, y3 + 114, "→ KeyError: 'q1'（图断链）", 14, RED)
    b += text(402, y3 + 150, "删节点前数一遍使用者", 13.5, SOFT)

    b += srect(744, y3, 378, 180, fill=L_GREEN, stroke=GREEN, sw=2.2, amp=0.9)
    b += text(760, y3 + 32, "今天的产出：13 条规则表", 15.5, INK)
    for i, ln in enumerate([
        "SAFE 5 条：已实现进 safe_optimize，",
        "        每条都有位等价测试护着；",
        "UNSAFE 5 条 + 边界 1 条：只写进规则表，",
        "        不实现 —— 拒绝也是优化器的功能。",
        "CONDITIONAL 2 条：登记 + 等整数语义证明。",
    ]):
        b += text(760, y3 + 62 + i * 24, ln, 13.5, INK)
    return svg_doc(W, H, b)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    docs = [
        ("01-overview.svg", draw_overview()),
        ("02-mechanism.svg", draw_mechanism()),
        ("03-rules.svg", draw_rules()),
        ("04-before-after.svg", draw_before_after()),
    ]
    for name, doc in docs:
        (OUT / name).write_text(doc, encoding="utf-8")
        print(f"生成 {name}: {len(doc)} 字符")


if __name__ == "__main__":
    main()
