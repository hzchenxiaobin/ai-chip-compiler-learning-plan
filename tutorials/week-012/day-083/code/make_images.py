#!/usr/bin/env python3
"""生成第 83 天教程的 4 张手绘风（Excalidraw-like）SVG 技术图。

运行方式：
    python3 make_images.py

输出到 ../images/ 目录：
    01-overview.svg       今天在第三阶段与编译链路中的位置 + 三件集成产物
    02-pipeline.svg       五道闸管道机制：每道闸做什么、依据哪一天、主图上发生了什么
    03-transform.svg      贯穿图三阶段真实变换：11 节点 → 7 节点 → 5 节点
    04-verify.svg         两层验证口径与三个负例（全部真实数据）

风格与 Day 78~82 保持一致：手绘抖动线条、马克笔笔触、米白背景、
蓝/橙/绿/红四种柔和强调色、简单几何形状。
图中数值全部来自 pipeline_lab.py 的真实运行结果（outputs/report.txt）。
"""

import math
import random
from pathlib import Path

random.seed(83)

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


def node(x, y, label, sub=None, fill="white", stroke=INK, w=62, h=34, size=14, dash=None):
    body = srect(x, y, w, h, fill=fill, stroke=stroke, sw=2.0, amp=0.8, dash=dash)
    if sub:
        body += text(x + w / 2, y + h * 0.46, label, size, INK, "middle")
        body += text(x + w / 2, y + h * 0.80, sub, size - 3.5, SOFT, "middle")
    else:
        body += text(x + w / 2, y + h * 0.66, label, size, INK, "middle")
    return body


def chip(x, y, label, fill, w=None, h=26, size=14):
    w = w or (len(label) * (size * 0.62) + 18)
    body = srect(x, y, w, h, fill=fill, stroke=fill, sw=1.6, amp=0.9)
    body += text(x + w / 2, y + h * 0.72, label, size, INK, "middle")
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
    body = text(28, y, main, 23, INK)
    if sub:
        body += text(28, y + 25, sub, 14.5, SOFT)
    return body


# ------------------------------------------------------------------ 图 1：位置

def draw_overview():
    W, H = 1120, 660
    b = title_bar(46, "Day 83: 第三阶段集成验收 —— 28 天的积木今天拼成一台机器",
                  "Shape/Layout、冗余消除、融合收益、数值验证各自单测通过 ≠ 组合起来还能对——集成验收就是回答这件事")

    # 上排：第三阶段四周地图
    weeks = [("W9 D57~63\nShape/Layout 基础", 1.0), ("W10 D64~70\n布局与冗余消除", 1.0),
             ("W11 D71~76\n融合收益与代价", 1.0), ("W12 D78~82\n数值精度与量化", 1.0),
             ("D83\n集成验收", 0.78), ("D84\n复盘", 0.6)]
    x, y0, bw, bh = 30, 96, 178, 56
    centers = []
    for label, scale in weeks:
        w = bw * scale
        today = "D83" in label
        fill = L_ORANGE if today else "white"
        b += srect(x, y0, w, bh, fill=fill, stroke=ORANGE if today else INK,
                   sw=2.6 if today else 1.8, amp=0.9)
        for i, ln in enumerate(label.split("\n")):
            b += text(x + w / 2, y0 + 22 + i * 17, ln, 13.5 if i == 0 else 12.5,
                      "#8a5a17" if today else INK, "middle")
        centers.append((x, x + w))
        x += w + 16
    for (a1, a2), (c1, c2) in zip(centers, centers[1:]):
        b += arrow(a2 + 2, y0 + bh / 2, c1 - 2, y0 + bh / 2, INK, 1.8)
    b += text(30, y0 - 8, "第三阶段（第 57~84 天）：AI 计算图与图优化", 13.5, SOFT)

    # 中排：编译链路
    y1, bh1 = 196, 62
    stages = [("图输入", "转换工具产物：\nQDQ 噪声+布局噪声", 1.06, False),
              ("合法性检查", "Day 12/39/59/60/64", 0.94, False),
              ("图优化管道", "今天：五道闸\n11 节点 → 5 节点", 1.24, True),
              ("Lowering", "Day 85+\n循环/LLVM", 0.8, False),
              ("执行", "CPU/硬件\n验证", 0.72, False)]
    x = 44
    centers = []
    for label, sub, scale, today in stages:
        w = 128 * scale
        fill = L_ORANGE if today else "white"
        b += srect(x, y1, w, bh1, fill=fill, stroke=ORANGE if today else INK,
                   sw=2.6 if today else 1.8, amp=0.9)
        b += text(x + w / 2, y1 + 22, label, 15.5, INK, "middle")
        for i, ln in enumerate(sub.split("\n")):
            b += text(x + w / 2, y1 + 38 + i * 14, ln, 11.5, SOFT, "middle")
        centers.append((x, x + w))
        x += w + 40
    for (a1, a2), (c1, c2) in zip(centers, centers[1:]):
        b += arrow(a2 + 3, y1 + bh1 / 2, c1 - 3, y1 + bh1 / 2, INK, 2.0)
    b += text(W / 2, y1 + bh1 + 24,
              "今天不写新 Pattern —— 把第三阶段的五类能力装进同一根管道，并用两层验证证明『优化没改错』",
              14.5, SOFT, "middle")

    # 下排：三张产物卡片
    y2, ch = 328, 240
    cards = [
        (28, 320, "① 端到端图优化示例", BLUE, L_BLUE,
         ["贯穿图（真实 IR 名字）：",
          "x(2,12)→reshape(24,)→reshape(4,6)",
          "W(3,6)→Q→DQ→transpose(1,0)",
          "→matmul→add(bias)→relu",
          "清理+融合后：11 → 5 个节点",
          "运行时算子 8 → 2（其余进编译期）"]),
        (392, 320, "② IR 对照 + 收益账本", GREEN, L_GREEN,
         ["每个阶段一张 IR（outputs/ 可复查）",
          "每步改写一行审计日志（哪条规则、",
          "为什么安全）",
          "ΔB = 16·M·N = 192 B（消两个中间）",
          "工作集 228 B ≤ 片上 256 KiB",
          "1024³：ΔB=16 MiB 但 spill → 拒绝"]),
        (756, 320, "③ 参考结果 + 全部测试", RED, L_RED,
         ["两层口径分开记账：",
          "位等价（容差=0）：优化不引入变化",
          "  固定输入 / 3×10⁴ 随机 / 50 张随机图",
          "  全部 True",
          "FP64 golden：账本 atol 兜底",
          "  最坏 |diff| 4.61e-07，占用比 0.036"]),
    ]
    for cx, cw, title, accent, light, lines in cards:
        b += srect(cx, y2, cw, ch, fill=light, stroke=accent, sw=2.2, amp=1.0)
        b += text(cx + 16, y2 + 30, title, 15.5, INK)
        b += sline(cx + 14, y2 + 40, cx + cw - 14, y2 + 40, accent, 1.6, amp=0.5)
        for i, ln in enumerate(lines):
            b += text(cx + 16, y2 + 62 + i * 19, ln, 12.5, INK)
    b += text(W / 2, H - 22,
              "学习计划对今天的要求：回顾 Shape/Layout、图优化、Cost Model、数值验证 —— 对一张含 Transpose/Reshape/MatMul/Bias/ReLU 的图执行优化并验证结果",
              13, SOFT, "middle")
    (OUT / "01-overview.svg").write_text(svg_doc(W, H, b), encoding="utf-8")


# ------------------------------------------------------------------ 图 2：管道

def draw_pipeline():
    W, H = 1240, 780
    b = title_bar(46, "Day 83: 五道闸管道 —— 顺序是设计决定，验证是管道的一部分",
                  "先清噪声再匹配模式；清理闸在不动点里循环（上一轮的改写创造下一轮的机会，Day 69）；改写后 Shape 复推")

    # 输入
    b += node(26, 106, "输入图", "11 节点", L_BLUE, BLUE, w=84, h=44, size=15)
    b += arrow(112, 128, 146, 128, INK, 2.2)

    gates = [
        ("闸0 合法性检查", ["内维 / 元素数 / perm / 广播", "（D12/39/59/60/64 的 Verifier）"],
         ["主图：11 节点", "Shape 全部可推导"], BLUE, L_BLUE, 158),
        ("闸1 QDQ 清理", ["R04：DQ(Q(const))→常量折叠", "R03：幂等尾对删除", "R07 报警 / R06 登记（D82）"],
         ["R04 命中：q、dq 折叠", "11 → 9 节点"], GREEN, L_GREEN, 192),
        ("闸2 布局简化", ["transpose(const)→常量折叠", "互逆消除 / 排列合并（D65）"],
         ["转置折叠：t 进编译期", "9 → 8 节点"], GREEN, L_GREEN, 170),
        ("闸3 Reshape 合并", ["reshape(reshape(x))→reshape(x)", "中间多使用者→保留（D66）"],
         ["链合并：r1、r2 → 一个", "8 → 7 节点"], GREEN, L_GREEN, 166),
        ("闸4 融合", ["合法性：单使用者 + bias 形状", "收益：ΔB=16MN + spill 门槛", "（D52/74/76 的两问）"],
         ["mm+add+relu → fused", "7 → 5 节点"], ORANGE, L_ORANGE, 192),
    ]
    x = 150
    y0, gh = 100, 130
    centers = []
    for name, sub, effect, accent, light, gw in gates:
        b += srect(x, y0, gw, gh, fill=light, stroke=accent, sw=2.4, amp=1.0)
        b += text(x + gw / 2, y0 + 23, name, 14.5, INK, "middle")
        b += sline(x + 12, y0 + 32, x + gw - 12, y0 + 32, accent, 1.5, amp=0.5)
        for i, ln in enumerate(sub):
            b += text(x + gw / 2, y0 + 49 + i * 14.5, ln, 11, INK, "middle")
        # 效果小票（虚线）
        b += srect(x + 6, y0 + gh - 44, gw - 12, 38, fill="white", stroke=accent,
                   sw=1.5, amp=0.7, dash="5,4")
        for i, ln in enumerate(effect):
            b += text(x + gw / 2, y0 + gh - 28 + i * 14, ln, 11,
                      "#2c5f2d" if accent == GREEN else ("#8a5a17" if accent == ORANGE else "#2a4d7a"),
                      "middle")
        centers.append((x, x + gw))
        x += gw + 20
    for (a1, a2), (c1, c2) in zip(centers, centers[1:]):
        b += arrow(a2 + 2, y0 + gh / 2 - 10, c1 - 2, y0 + gh / 2 - 10, INK, 2.2)

    # 输出
    b += arrow(x - 16, y0 + gh / 2, x + 12, y0 + gh / 2, INK, 2.2)
    b += node(x + 16, y0 + gh / 2 - 22, "终图", "5 节点", L_ORANGE, ORANGE, w=80, h=44, size=15)

    # 不动点循环（闸1~3）
    fx0 = centers[1][0] + 8
    fx1 = centers[3][1] - 8
    loop_y = y0 + gh + 28
    b += sline(fx0, y0 + gh + 4, fx0, loop_y, BLUE, 2.0, dash="7,5", amp=0.8)
    b += sline(fx0, loop_y, fx1, loop_y, BLUE, 2.0, dash="7,5", amp=0.8)
    b += arrow(fx1, loop_y, fx1, y0 + gh + 4, BLUE, 2.0, dash="7,5")
    b += text((fx0 + fx1) / 2, loop_y - 8,
              "不动点循环（实测 2 轮收敛）：R04 折叠出新常量，下一轮转置折叠才有料（Day 69）",
              12.5, BLUE, "middle")

    # 底部：终验两层
    vy = 336
    b += srect(30, vy, 500, 178, fill=L_RED, stroke=RED, sw=2.4, amp=1.0)
    b += text(48, vy + 28, "终验第一层：位等价（容差 = 0）", 15.5, INK)
    b += sline(46, vy + 38, 514, vy + 38, RED, 1.6, amp=0.5)
    b += text(48, vy + 62, "问题：优化改写有没有引入任何数值变化？", 13, INK)
    b += text(48, vy + 86, "对照：优化图 vs 原图，同一组输入 fp32 逐位相等", 13, INK)
    b += text(48, vy + 110, "结构保证：折叠复用执行器同一套数值内核；", 13, INK)
    b += text(48, vy + 130, "融合算子严格按 fp32 的 matmul→add→relu 复刻", 13, INK)
    b += text(48, vy + 158, "实测：固定输入 True｜3×10⁴ 随机 True｜50 张随机图 50/50", 13, "#8a3a2c")

    b += srect(590, vy, 500, 178, fill=L_BLUE, stroke=BLUE, sw=2.4, amp=1.0)
    b += text(608, vy + 28, "终验第二层：FP64 golden（误差账本）", 15.5, INK)
    b += sline(606, vy + 38, 1074, vy + 38, BLUE, 1.6, amp=0.5)
    b += text(608, vy + 62, "问题：实现本身的误差有没有出账？", 13, INK)
    b += text(608, vy + 86, "口径：|a−g| ≤ atol + rtol·|g|，rtol=1e-5", 13, INK)
    b += text(608, vy + 110, "atol 按图记账（D78）：(2K+2)·eps32·max Σ|a·b|", 13, INK)
    b += text(608, vy + 134, "（MatMul 有消去，不能用 D79 逐元素固定表）", 12, SOFT)
    b += text(608, vy + 158, "实测：固定输入 |diff|=0｜随机最坏 4.54e-07，占用比 0.033", 13, "#2a4d7a")

    # 底部一句话
    b += srect(30, vy + 204, 1060, 44, fill="white", stroke=INK, sw=2.0, amp=0.9)
    b += text(560, vy + 231,
              "口径就是语义：位等价管『优化不引入变化』，golden 管『实现自身误差』—— 两个问题，两本账，不能混",
              14.5, INK, "middle")
    (OUT / "02-pipeline.svg").write_text(svg_doc(W, H, b), encoding="utf-8")


# ------------------------------------------------------------------ 图 3：三阶段变换

def draw_transform():
    W, H = 1120, 760
    b = title_bar(46, "Day 83: 贯穿图的三阶段真实变换（节点名与数值全部来自实跑）",
                  "阶段一清 QDQ/布局/reshape 噪声（11→7），阶段二融合 GEMM 尾巴（7→5）—— 每一步删了什么、为什么安全都标在图上")

    # ---------- 阶段一：原图 11 节点 ----------
    b += text(30, 84, "① 原图（11 节点）：转换工具的典型产物", 15.5, INK)
    b += srect(26, 92, 1068, 196, fill="white", stroke=INK, sw=2.0, amp=1.0, dash="9,6")

    nw, nh = 76, 36
    # 权重路径（上排）
    Wx = [(60, 128, "const W", "(3,6)"), (176, 128, "quantize", "s=1/128"),
          (292, 128, "dequantize", ""), (408, 128, "transpose", "(1,0)→(6,3)")]
    for i, (x, y, lab, sub) in enumerate(Wx):
        b += node(x, y, lab, sub or None, "white", INK, w=nw, h=nh, size=12.5)
    for i in range(3):
        b += arrow(Wx[i][0] + nw, Wx[i][1] + nh / 2, Wx[i + 1][0], Wx[i + 1][1] + nh / 2, INK, 1.8)
    # 划掉三个节点（标签放在节点上方、框线之内）
    b += strike(Wx[1][0], Wx[1][1], nw, nh, RED, 2.4)
    b += strike(Wx[2][0], Wx[2][1], nw, nh, RED, 2.4)
    b += strike(Wx[3][0], Wx[3][1], nw, nh, RED, 2.4)
    b += chip(Wx[1][0] - 4, 98, "R04 折叠进常量", L_RED, h=22, size=12)
    b += chip(Wx[3][0] + 6, 98, "转置常量折叠", L_RED, h=22, size=12)

    # 输入路径（下排）
    Xx = [(60, 196, "arg x", "(2,12)"), (176, 196, "reshape", "(24,)"),
          (292, 196, "reshape", "(4,6)")]
    for x, y, lab, sub in Xx:
        b += node(x, y, lab, sub, L_BLUE, BLUE, w=nw, h=nh, size=12.5)
    for i in range(2):
        b += arrow(Xx[i][0] + nw, Xx[i][1] + nh / 2, Xx[i + 1][0], Xx[i + 1][1] + nh / 2, INK, 1.8)
    b += strike(Xx[1][0], Xx[1][1], nw, nh, RED, 2.4)
    b += chip(Xx[1][0] - 12, 240, "reshape 链合并（D66）", L_RED, h=22, size=12)

    # GEMM 尾巴
    b += node(544, 164, "matmul", "(4,6)@(6,3)", "white", INK, w=92, h=nh, size=12.5)
    b += arrow(Xx[2][0] + nw, Xx[2][1] + nh / 2, 544, 164 + nh / 2, INK, 1.8)
    b += carrow((Wx[3][0] + nw / 2, Wx[3][1] + nh), (496, 224), (544, 180), INK, 1.8)
    b += node(668, 164, "add", "+bias(3,)", "white", INK, w=76, h=nh, size=12.5)
    b += arrow(636, 164 + nh / 2, 668, 164 + nh / 2, INK, 1.8)
    b += node(668, 226, "const b", "(0.125,-0.25,0.5)", L_GREEN, GREEN, w=130, h=nh, size=11.5)
    b += arrow(668 + 40, 226, 700, 200, INK, 1.8)
    b += node(780, 164, "relu", "", "white", INK, w=64, h=nh, size=12.5)
    b += arrow(744, 164 + nh / 2, 780, 164 + nh / 2, INK, 1.8)
    b += arrow(844, 164 + nh / 2, 888, 164 + nh / 2, INK, 2.0)
    b += text(894, 172, "return", 13, SOFT)
    b += text(894, 190, "(4,3)", 12, SOFT)

    # 权重靠档效果（真实数据）
    b += srect(878, 208, 206, 62, fill=L_GREEN, stroke=GREEN, sw=1.8, amp=0.8)
    b += text(888, 228, "QDQ 真的改权重（靠档）：", 11.5, INK)
    b += text(888, 245, "0.3 → 码38 → 0.296875", 11.5, "#2c5f2d")
    b += text(888, 261, "0.7 → 码90 → 0.703125", 11.5, "#2c5f2d")

    # ---------- 箭头：11 → 7 ----------
    b += arrow(300, 292, 300, 326, ORANGE, 2.6)
    b += chip(316, 302, "闸1~3 清理：删 4 个节点，位等价 True", L_ORANGE, h=24, size=12.5)

    # ---------- 阶段二：清理后 7 节点 ----------
    b += text(30, 330, "② 清理后（7 节点）：噪声已清，GEMM 尾巴露出来了", 15.5, INK)
    b += srect(26, 338, 1068, 132, fill="white", stroke=INK, sw=2.0, amp=1.0, dash="9,6")
    y2 = 366
    b += node(60, y2, "arg x", "(2,12)", L_BLUE, BLUE, w=nw, h=nh, size=12.5)
    b += node(176, y2, "reshape", "(4,6)", "white", INK, w=nw, h=nh, size=12.5)
    b += arrow(60 + nw, y2 + nh / 2, 176, y2 + nh / 2, INK, 1.8)
    b += node(330, y2, "const Ŵᵀ", "(6,3) 编译期算好", L_GREEN, GREEN, w=124, h=nh, size=12)
    b += arrow(330 + 124, y2 + nh / 2 - 4, 524, y2 + nh / 2 - 4, INK, 1.8)
    b += arrow(176 + nw, y2 + nh / 2 + 4, 524, y2 + nh / 2 + 4, INK, 1.8)
    b += node(524, y2, "matmul", "(4,3)", "white", INK, w=80, h=nh, size=12.5)
    b += node(640, y2, "add", "+bias", "white", INK, w=68, h=nh, size=12.5)
    b += arrow(604, y2 + nh / 2, 640, y2 + nh / 2, INK, 1.8)
    b += node(640, y2 + 52, "const b", "(3,)", L_GREEN, GREEN, w=68, h=nh, size=12)
    b += arrow(674, y2 + 52, 674, y2 + nh, INK, 1.8)
    b += node(744, y2, "relu", "", "white", INK, w=64, h=nh, size=12.5)
    b += arrow(708, y2 + nh / 2, 744, y2 + nh / 2, INK, 1.8)
    b += arrow(808, y2 + nh / 2, 850, y2 + nh / 2, INK, 2.0)
    b += text(856, y2 + 12, "return (4,3)", 13, SOFT)
    # 融合包围圈
    b += srect(516, y2 - 14, 300, 96, fill="none", stroke=ORANGE, sw=2.4, amp=1.2, dash="10,6")
    b += chip(826, 400, "闸4：三算子一起算，中间不落盘", L_ORANGE, h=22, size=12)

    b += arrow(300, 474, 300, 508, ORANGE, 2.6)
    b += chip(316, 484, "闸4 融合：ΔB = 16·M·N = 192 B，无 spill → 融合", L_ORANGE, h=24, size=12.5)

    # ---------- 阶段三：终图 5 节点 ----------
    b += text(30, 512, "③ 终图（5 节点）：交给 Lowering 的干净输入", 15.5, INK)
    b += srect(26, 520, 1068, 124, fill="white", stroke=INK, sw=2.0, amp=1.0, dash="9,6")
    y3 = 548
    b += node(80, y3, "arg x", "(2,12)", L_BLUE, BLUE, w=nw, h=nh, size=12.5)
    b += node(200, y3, "reshape", "(4,6)", "white", INK, w=nw, h=nh, size=12.5)
    b += arrow(80 + nw, y3 + nh / 2, 200, y3 + nh / 2, INK, 1.8)
    b += node(380, y3 - 14, "const Ŵᵀ", "(6,3)", L_GREEN, GREEN, w=80, h=nh, size=12)
    b += node(380, y3 + 42, "const b", "(3,)", L_GREEN, GREEN, w=80, h=nh, size=12)
    b += node(540, y3, "fused_", "matmul_bias_relu", L_ORANGE, ORANGE, w=150, h=44, size=12.5)
    b += arrow(200 + nw, y3 + nh / 2, 540, y3 + 22, INK, 1.8)
    b += arrow(380 + 80, y3 - 14 + nh / 2, 540, y3 + 14, INK, 1.8)
    b += arrow(380 + 80, y3 + 42 + nh / 2, 556, y3 + 44, INK, 1.8)
    b += arrow(690, y3 + 22, 740, y3 + 22, INK, 2.0)
    b += text(748, y3 + 27, "return (4,3)", 13, SOFT)
    b += text(748, y3 + 60, "位等价 True（vs 原图逐位相等）", 12, "#2c5f2d")

    # 底部：节点数对账
    by = 664
    b += srect(30, by, 1060, 86, fill=L_BLUE, stroke=BLUE, sw=2.2, amp=1.0)
    b += text(48, by + 26, "对账（全部实测）：", 14.5, INK)
    b += text(48, by + 52, "节点数 11 → 7 → 5；运行时要执行的算子 8 → 2（q/dq/转置/一个 reshape 搬进编译期）", 13, INK)
    b += text(48, by + 76, "剩余 reshape 不能删：matmul 只会读连续内存，按 stride 读是 Lowering（第 13 周）的事 —— 优化器不越权",
              13, INK)
    (OUT / "03-transform.svg").write_text(svg_doc(W, H, b), encoding="utf-8")


# ------------------------------------------------------------------ 图 4：验证与负例

def draw_verify():
    W, H = 1120, 760
    b = title_bar(46, "Day 83: 验证结果与三个负例 —— 数字全部来自实跑（seed=83）",
                  "两层验证各管一本账；右下三张卡是管道『拒绝也是决策』的实弹：R06 登记、多使用者拒融、requant 报警")

    # 左上：位等价
    b += srect(28, 96, 470, 250, fill=L_GREEN, stroke=GREEN, sw=2.4, amp=1.0)
    b += text(46, 124, "层1 位等价：优化 vs 原图（容差 = 0）", 15, INK)
    b += sline(44, 134, 482, 134, GREEN, 1.6, amp=0.5)
    rows = [("固定输入（dyadic 数据）", "np.array_equal = True"),
            ("随机输入 3 组 × 10000", "True（逐位）"),
            ("随机图 50 张（M,K,N∈[1,8]）", "50/50"),
            ("节点数", "11 → 5（50 张全部）")]
    for i, (k, v) in enumerate(rows):
        b += text(46, 160 + i * 26, k, 12.5, INK)
        b += text(300, 160 + i * 26, v, 12.5, "#2c5f2d")
    b += text(46, 160 + 4 * 26 + 6, "结论：五道闸的改写没有引入任何一个比特的变化", 12.5, SOFT)

    # 右上：golden
    b += srect(522, 96, 470, 250, fill=L_BLUE, stroke=BLUE, sw=2.4, amp=1.0)
    b += text(540, 124, "层2 FP64 golden：atol 按图记账（D78）", 15, INK)
    b += sline(538, 134, 976, 134, BLUE, 1.6, amp=0.5)
    rows = [("固定输入 max|diff|", "0（dyadic 校准：fp32==fp64）"),
            ("账本 atol（主图）", "(2K+2)·eps32·S = 4.29e-06"),
            ("随机 3×10⁴ 最坏 |diff|", "4.54e-07"),
            ("最坏容差占用比", "0.033（离门槛 30 倍余量）")]
    for i, (k, v) in enumerate(rows):
        b += text(540, 160 + i * 26, k, 12.5, INK)
        b += text(740, 160 + i * 26, v, 12.5, "#2a4d7a")
    b += text(540, 160 + 4 * 26 + 6, "ULP 只作观察：近零输出带消去，39936 格 ≠ 错（刻度问题）", 12.5, SOFT)

    # 左下：变体输出对照（量化效果）
    b += srect(28, 376, 470, 250, fill=L_ORANGE, stroke=ORANGE, sw=2.4, amp=1.0)
    b += text(46, 404, "变体图：尾部多一对激活 QDQ（13 → 7 节点）", 15, INK)
    b += sline(44, 414, 482, 414, ORANGE, 1.6, amp=0.5)
    b += text(46, 438, "R04/折叠/合并/融合照常；尾部裸 QDQ 判 R06 登记不动：", 12.5, INK)
    b += text(46, 458, "『删除 = 悄悄取消量化』是策略决定，管道不越权（D82）", 12.5, INK)
    b += text(46, 488, "激活量化把输出放上 1/8 格点（真实对照）：", 12.5, INK)
    pairs = [("主图 0.0625", "→ 0.0000（0.5 格，banker 舍入到偶）"),
             ("主图 1.2383", "→ 1.2500（9.9 格 → 10 格）"),
             ("主图 3.0703", "→ 3.1250（24.6 格 → 25 格）")]
    for i, (k, v) in enumerate(pairs):
        b += text(60, 512 + i * 24, k, 12.5, INK)
        b += text(190, 512 + i * 24, v, 12.5, "#8a5a17")
    b += text(46, 512 + 3 * 24 + 8, "位等价仍 True：q→dq 原样执行，一个比特没动", 12.5, SOFT)

    # 右下：两个负例卡
    b += srect(522, 376, 228, 250, fill=L_RED, stroke=RED, sw=2.4, amp=1.0)
    b += text(540, 404, "负例：多使用者拒融", 14.5, INK)
    b += sline(538, 414, 734, 414, RED, 1.6, amp=0.5)
    b += text(540, 438, "matmul 输出同时是", 12.5, INK)
    b += text(540, 458, "图输出 → 融合会夺走", 12.5, INK)
    b += text(540, 478, "别的消费者的输入", 12.5, INK)
    b += text(540, 508, "实测：6 → 6 节点", 12.5, "#8a3a2c")
    b += text(540, 532, "审计：『拒绝：输出被", 12.5, INK)
    b += text(540, 552, "2 个节点使用』", 12.5, INK)
    b += text(540, 582, "Day 52 的边界原样上岗", 12.5, SOFT)

    b += srect(764, 376, 228, 250, fill=L_RED, stroke=RED, sw=2.4, amp=1.0)
    b += text(782, 404, "负例：requant 报警", 14.5, INK)
    b += sline(780, 414, 976, 414, RED, 1.6, amp=0.5)
    b += text(782, 438, "Q(s=1/128) → DQ(s=1/64)", 12.5, INK)
    b += text(782, 458, "参数不一致（R07）", 12.5, INK)
    b += text(782, 488, "实测：3 → 3 节点，图没动", 12.5, "#8a3a2c")
    b += text(782, 512, "报警而不是抢救：", 12.5, INK)
    b += text(782, 532, "坏图要在上游修参数", 12.5, INK)
    b += text(782, 562, "（D82 结论：删不删都已错）", 12.5, SOFT)

    # 底部横幅
    b += srect(28, 656, 1030, 52, fill="white", stroke=INK, sw=2.0, amp=0.9)
    b += check_icon(56, 682, GREEN, 3.0, 1.1)
    b += text(84, 688,
              "验收口径：『删了不变』用位等价证明；『算得对不对』用 golden + 账本证明；『不该动的』用负例证明它确实没动",
              13.5, INK)
    (OUT / "04-verify.svg").write_text(svg_doc(W, H, b), encoding="utf-8")


def main() -> None:
    draw_overview()
    draw_pipeline()
    draw_transform()
    draw_verify()
    for f in sorted(OUT.glob("*.svg")):
        print(f"生成 {f.name}（{f.stat().st_size} 字节）")


if __name__ == "__main__":
    main()
