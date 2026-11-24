#!/usr/bin/env python3
"""生成第 126 天（第 18 周复盘）的 3 张手绘 sketch 风 SVG 图。

数字来自 outputs/rebuild-log.txt 与本周六天的 outputs/ 冻结产物
（2026-11-14，macOS arm64）。固定随机种子 126。
"""
from __future__ import annotations

import math
import os
import random
import xml.sax.saxutils as su

random.seed(126)

BG = "#FDFBF6"
BORDER = "#E7DFCE"
INK = "#3B3B3B"
MUTED = "#6b6257"
ORANGE = "#E8A87C"
BLUE = "#A9C4D4"
GREEN = "#9CBF8E"
RED = "#C97B7B"
PURPLE = "#B8A7CE"
FONT = "'Comic Sans MS','Kaiti SC','KaiTi','STKaiti',cursive"

W, H = 1080, 760
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "images")


def jit(m=1.6):
    return random.uniform(-m, m)


def hand_rect(x, y, w, h, fill=BG, opacity=0.65, stroke=INK, sw=1.4, dash=None):
    pts = [(x + jit(), y + jit()), (x + w + jit(), y + jit()),
           (x + w + jit(), y + h + jit()), (x + jit(), y + h + jit())]
    d = f"M {pts[0][0]:.1f},{pts[0][1]:.1f} "
    for i in range(4):
        a, b = pts[i], pts[(i + 1) % 4]
        mx, my = (a[0] + b[0]) / 2 + jit(2.2), (a[1] + b[1]) / 2 + jit(2.2)
        d += f"Q {mx:.1f},{my:.1f} {b[0]:.1f},{b[1]:.1f} "
    dd = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<path d="{d} Z" stroke="{stroke}" stroke-width="{sw}" '
            f'stroke-linecap="round" stroke-linejoin="round" '
            f'fill="{fill}" fill-opacity="{opacity}"{dd}/>')


def arrow(x1, y1, x2, y2, stroke=INK, sw=1.8, dash=None, label=None):
    dd = f' stroke-dasharray="{dash}"' if dash else ""
    mx, my = (x1 + x2) / 2 + jit(2.0), (y1 + y2) / 2 + jit(2.0)
    ang = math.atan2(y2 - y1, x2 - x1)
    hx, hy = x2 - 9 * math.cos(ang), y2 - 9 * math.sin(ang)
    a1 = (hx + 5 * math.cos(ang + 2.7), hy + 5 * math.sin(ang + 2.7))
    a2 = (hx + 5 * math.cos(ang - 2.7), hy + 5 * math.sin(ang - 2.7))
    d = (f"M {x1 + jit():.1f},{y1 + jit():.1f} Q {mx:.1f},{my:.1f} "
         f"{x2:.1f},{y2:.1f} M {a1[0]:.1f},{a1[1]:.1f} L {x2:.1f},{y2:.1f} "
         f"L {a2[0]:.1f},{a2[1]:.1f}")
    out = (f'<path d="{d}" stroke="{stroke}" stroke-width="{sw}" '
           f'stroke-linecap="round" fill="none"{dd}/>')
    if label:
        out += text((x1 + x2) / 2, (y1 + y2) / 2 - 8, label, 10.5, MUTED)
    return out


def text(x, y, s, size=13, fill=INK, anchor="middle", bold=False, mono=False):
    s = su.escape(s)
    wt = ' font-weight="bold"' if bold else ""
    fam = "'Courier New',monospace" if mono else FONT
    return (f'<text x="{x}" y="{y}" font-family="{fam}" font-size="{size}" '
            f'fill="{fill}" text-anchor="{anchor}"{wt}>{s}</text>')


def svg_open(w=W, h=H):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
            f'viewBox="0 0 {w} {h}">'
            f'<rect x="4" y="4" width="{w-8}" height="{h-8}" rx="14" '
            f'fill="{BG}" stroke="{BORDER}" stroke-width="2"/>')


def save(name, body, w=W, h=H):
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
        f.write(svg_open(w, h) + body + "</svg>\n")
    print("生成", name)


# ── 图 1：第 18 周总览——minic 的成长曲线 ──
def fig1():
    b = []
    b.append(text(W/2, 34, "第 18 周总览：minic 从 0.1.0 骨架到 0.3.0 完整编译器", 16, bold=True))

    # 六天成长阶梯
    days = [
        ("D120", "CLI 骨架 0.1.0", "四份合同\n25 项测试", GREEN),
        ("D121", "S1 接入 0.2.0", "五闸＋五开关\n11→5 节点", GREEN),
        ("D122", "S2~S5 接入 0.3.0", "七 pass＋失败诊断\n11 个 stage 文件", BLUE),
        ("D123", "可观测层", "四级粒度＋改写记录\n＋时间线", BLUE),
        ("D124", "端到端！", "S2 点循环＋S6 验证\n12/12 bitwise", ORANGE),
        ("D125", "对照实验", "四组×五指标\nkernel 级计时", RED),
    ]
    dw, dh, dgap = 160, 130, 16
    dx0 = (W - (dw*6 + dgap*5)) / 2
    for i, (d, name, desc, color) in enumerate(days):
        x = dx0 + i * (dw + dgap)
        y = 60 + (5 - i) * 18   # 上升阶梯
        b.append(hand_rect(x, y, dw, dh, fill=color, opacity=0.45))
        b.append(text(x + dw/2, y + 24, d, 13, bold=True))
        b.append(text(x + dw/2, y + 44, name, 10.5))
        for j, line in enumerate(desc.split("\n")):
            b.append(text(x + dw/2, y + 66 + j*16, line, 9.5))
        if i < 5:
            b.append(arrow(x + dw + 1, y + dh/2, x + dw + dgap - 1, y + dh/2 - 10, sw=1.5))

    # 中：版本能力对照
    b.append(text(W/2, 280, "0.1.0 → 0.3.0：能力清单的变化", 14, bold=True))
    caps = [
        ("周一有的", ["--help/--version", "退出码 0/1/2", "16 条诊断", "manifest 9 字段", "六阶段骨架日志"], GREEN),
        ("周五有的", ["以上全部（合同零退化）", "＋五开关＋四级 dump", "＋真实管道到汇编", "＋12/12 bitwise 验证", "＋四组对照＋收益表"], ORANGE),
    ]
    for i, (title, items, color) in enumerate(caps):
        x = 120 + i * 460
        b.append(hand_rect(x, 300, 420, 160, fill=color, opacity=0.35))
        b.append(text(x + 210, 324, title, 12.5, bold=True))
        for j, item in enumerate(items):
            b.append(text(x + 210, 348 + j*22, item, 10))

    # 底：108 项判定
    b.append(hand_rect(80, 480, 900, 90, fill="#F5E9C8", opacity=0.8))
    b.append(text(W/2, 504, "本周新增测试：108 项 PASS 判定（25+25+25+12+11+10）", 13, bold=True))
    b.append(text(W/2, 528, "D120 合同 25｜D121 开关矩阵 25｜D122 失败诊断 25｜D123 可观测 12｜D124 端到端 11｜D125 对照 10", 10.5))
    b.append(text(W/2, 550, "＋今天干净重建 5/5（从空 outputs/ 重跑核心链全绿）——可复现性不是文档口号", 10.5, fill="#4a7c59"))
    save("01-overview.svg", "".join(b), h=600)


# ── 图 2：干净重建的方法论 ──
def fig2():
    b = []
    b.append(text(W/2, 34, "干净重建：可复现性的最终验收——删掉一切输出，从零再跑一遍", 16, bold=True))

    # 流程
    steps = [
        ("① 删", "outputs/ 清空\n重建目录移除", RED),
        ("② 跑", "S1→S2→S4/S5→S6\n四组对照，5 步", ORANGE),
        ("③ 验", "每步断言结构结论\n（节点数/胶水/bitwise）", BLUE),
        ("④ 绿", "5/5 PASS＋产物在位", GREEN),
    ]
    sw_, sh_ = 210, 110
    sx0 = 80
    for i, (name, desc, color) in enumerate(steps):
        x = sx0 + i * (sw_ + 24)
        b.append(hand_rect(x, 60, sw_, sh_, fill=color, opacity=0.45))
        b.append(text(x + sw_/2, 88, name, 16, bold=True))
        for j, line in enumerate(desc.split("\n")):
            b.append(text(x + sw_/2, 112 + j*16, line, 10))
        if i < 3:
            b.append(arrow(x + sw_ + 2, 115, x + sw_ + 22, 115, sw=1.6))

    # 重建五步实录
    b.append(text(W/2, 210, "重建五步实录（rebuild-log.txt，总耗时 ~9 秒）", 14, bold=True))
    rows = [
        ("S1 图优化", "0.0s", "11 → 5 节点（fused 在位）", GREEN),
        ("S2 循环生成", "0.0s", "34 行（bias 融 k=0 + relu 在位）", GREEN),
        ("S4/S5 管道", "0.8s", "七 pass 全过，胶水 0", GREEN),
        ("S6 端到端验证", "3.8s", "12/12 bitwise 一致", GREEN),
        ("四组对照", "4.3s", "A/B/C/D 正确性全过", GREEN),
    ]
    y = 232
    for name, t, detail, color in rows:
        b.append(hand_rect(120, y, 840, 36, fill=color, opacity=0.3))
        b.append(text(250, y + 24, name, 11, bold=True))
        b.append(text(400, y + 24, t, 10.5, mono=True))
        b.append(text(700, y + 24, detail, 10))
        y += 42

    # 方法论
    b.append(text(W/2, y + 16, "为什么干净重建是最终验收？", 14, bold=True))
    b.append(hand_rect(80, y + 36, 900, 100, fill=PURPLE, opacity=0.3))
    reasons = [
        "① 文档说「一键复现」——删掉输出重跑是唯一证法（写出来的和跑通的之间隔着环境依赖）；",
        "② 冻结产物可能掩盖「依赖残留」——上次运行留下的文件让本次「看起来能跑」；",
        "③ 复盘的信用建立在证据上——干净重建 5/5 让「本周可运行产出」这句话有实测背书。",
    ]
    for j, r in enumerate(reasons):
        b.append(text(120, y + 62 + j*24, r, 10.5, anchor="start"))
    save("02-mechanism.svg", "".join(b), h=y + 160)


# ── 图 3：第 18 周账本与下周路线 ──
def fig3():
    b = []
    b.append(text(W/2, 34, "第 18 周账本（每周模板）与第 19 周路线", 16, bold=True))

    # 左：账本摘要
    b.append(hand_rect(50, 60, 520, 400, fill="#F5E9C8", opacity=0.7))
    b.append(text(310, 84, "本周账本（week-ledger.txt 摘要）", 13.5, bold=True))
    items = [
        ("目标", "统一端到端编译入口 minic"),
        ("产出", "0.1.0→0.3.0：七阶段全真实\n一条命令图 IR→汇编→12/12"),
        ("测试", "108 项判定＋干净重建 5/5"),
        ("核心问题", "六天零件怎么「装」成编译器？\n答案：合同先行＋逐日接入＋每天回归"),
        ("优化对照", "-O2 展开反例：慢 60%\n（fmul 1→6 但体积代价>收益）"),
        ("讲不清的", "块循环 Tiling 的 minic 化\nJIT 路线接入、多算子支持集"),
    ]
    y = 106
    for name, val in items:
        b.append(text(80, y + 12, name, 10.5, bold=True, anchor="start"))
        for j, line in enumerate(val.split("\n")):
            b.append(text(200, y + 12 + j*16, line, 9.5, anchor="start"))
        y += 16 * len(val.split("\n")) + 18

    # 右：下周路线
    b.append(hand_rect(600, 60, 430, 400, fill=PURPLE, opacity=0.3))
    b.append(text(815, 84, "第 19 周：Runtime 与动态 Shape", 13.5, bold=True))
    week19 = [
        ("D127", "Compiler/Runtime 职责划分"),
        ("D128", "运行期参数与 Shape"),
        ("D129", "静态 Shape 特化"),
        ("D130", "通用实现回退"),
        ("D131", "内存分配与复用（malloc 债务结清！）"),
        ("D132", "异步与同步模型"),
        ("D133", "第 19 周复盘"),
    ]
    y = 110
    for d, name in week19:
        highlight = "（malloc 债务结清！）" in name
        b.append(hand_rect(620, y, 390, 40, fill=ORANGE if highlight else BG, opacity=0.5 if highlight else 0.9))
        b.append(text(650, y + 25, d, 11, bold=True))
        b.append(text(820, y + 25, name, 10, bold=highlight))
        y += 48
    b.append(text(815, y + 12, "minic 的 manifest/stage 产物是", 10, MUTED))
    b.append(text(815, y + 28, "Runtime 的输入接口——本周地基直接可用", 10, MUTED))

    # 底
    b.append(hand_rect(50, 480, 980, 70, fill=GREEN, opacity=0.35))
    b.append(text(W/2, 506, "第 18 周收官判断：统一编译入口完成——「能用」与「可交付」之间的工程化层全部就位", 12.5, bold=True))
    b.append(text(W/2, 530, "判据：一条命令端到端 ✓｜108 项测试全绿 ✓｜干净重建 5/5 ✓｜四组对照有收益表与反例 ✓｜失败有诊断有现场 ✓", 10.5))
    save("03-week-report.svg", "".join(b), h=580)


if __name__ == "__main__":
    fig1()
    fig2()
    fig3()
