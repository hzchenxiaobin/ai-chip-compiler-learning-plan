#!/usr/bin/env python3
"""第 140 天 3 张 SVG。种子 140。"""
from __future__ import annotations
import math, os, random
import xml.sax.saxutils as su
random.seed(140)
BG = "#FDFBF6"; BORDER = "#E7DFCE"; INK = "#3B3B3B"; MUTED = "#6b6257"
ORANGE = "#E8A87C"; BLUE = "#A9C4D4"; GREEN = "#9CBF8E"; RED = "#C97B7B"
PURPLE = "#B8A7CE"
FONT = "'Comic Sans MS','Kaiti SC','KaiTi','STKaiti',cursive"
W, H = 1080, 760
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "images")

def jit(m=1.6): return random.uniform(-m, m)

def hand_rect(x, y, w, h, fill=BG, opacity=0.65, stroke=INK, sw=1.4):
    pts = [(x + jit(), y + jit()), (x + w + jit(), y + jit()),
           (x + w + jit(), y + h + jit()), (x + jit(), y + h + jit())]
    d = f"M {pts[0][0]:.1f},{pts[0][1]:.1f} "
    for i in range(4):
        a, b = pts[i], pts[(i + 1) % 4]
        mx, my = (a[0] + b[0]) / 2 + jit(2.2), (a[1] + b[1]) / 2 + jit(2.2)
        d += f"Q {mx:.1f},{my:.1f} {b[0]:.1f},{b[1]:.1f} "
    return (f'<path d="{d} Z" stroke="{stroke}" stroke-width="{sw}" '
            f'stroke-linecap="round" stroke-linejoin="round" '
            f'fill="{fill}" fill-opacity="{opacity}"/>')

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

def fig1():
    b = []
    b.append(text(W/2, 34, "调试流水线：五站串珠（计划点名的脱稿演示）", 16, bold=True))
    stations = [
        ("① 失败发现", "D134 正反集 16 例\n＋D135 随机 200 组\n种子＋trial 可复现", GREEN),
        ("② Dump IR", "D123 --dump-ir=full\n阶段序列＋改写记录\n「哪步改了什么」", BLUE),
        ("③ 关闭 Pass", "D136 前缀二分\n✓✓✓✗✗ 首次变坏\n＝最早破坏点", ORANGE),
        ("④ 最小复现", "D137 Reduce 三板斧\n19→4 节点（79%）\n删无可删的核", RED),
        ("⑤ 修复回归", "固化正反例（免疫）\n性能复核（阈值内）\n过四维闸合入", PURPLE),
    ]
    for i, (name, body, color) in enumerate(stations):
        x = 50 + i * 200
        b.append(hand_rect(x, 60, 180, 160, fill=color, opacity=0.35))
        b.append(text(x + 90, 88, name, 12.5, bold=True))
        for j, line in enumerate(body.split("\n")):
            b.append(text(x + 90, 114 + j*20, line, 9.5))
        if i < 4:
            b.append(arrow(x + 182, 140, x + 198, 140, sw=1.5))
    # 口诀
    b.append(hand_rect(160, 250, 760, 56, fill="#F5E9C8", opacity=0.85, sw=2))
    b.append(text(W/2, 274, "口诀：发现 → 看清 → 锁定 → 缩小 → 修死", 15, bold=True))
    b.append(text(W/2, 296, "（每站一句、五站脱稿可讲——计划 D140 条目的验收标准）", 10.5, MUTED))
    # 演示路径
    b.append(text(W/2, 340, "一次真实走位（注入版演练）", 13.5, bold=True))
    demo = [
        "fuzz 第 137 号 trial 失败（seed 20261115）→ 重放确认",
        "→ dump stage-4-04 的 IR：fadd 不见了",
        "→ 前缀判定：前 3 条好、前 4 条坏——凶手 convert-func-to-llvm",
        "→ Reduce：19 节点缩到 4 节点核（matmul 内维 3≠4）",
        "→ 修 const shape＋固化反例＋四维闸 7/7 合入",
    ]
    y = 362
    for line in demo:
        b.append(text(W/2, y, line, 10.5, mono=True))
        y += 22
    save("01-pipeline.svg", "".join(b), h=y + 20)

def fig2():
    b = []
    b.append(text(W/2, 34, "第 20 周战报与第 5 阶段收官", 16, bold=True))
    # 六天卡
    days = [
        ("D134", "测试金字塔", "16 例正反集", GREEN),
        ("D135", "随机 fuzz", "200 组全对", GREEN),
        ("D136", "二分定位", "注入精确指认", ORANGE),
        ("D137", "最小用例", "19→4 节点", ORANGE),
        ("D138", "性能回归", "阈值 1.5× 双验", BLUE),
        ("D139", "冻结发布", "四维 7/7＋v0.5.0", RED),
    ]
    for i, (d, name, note, color) in enumerate(days):
        x = 60 + i * 165
        b.append(hand_rect(x, 60, 150, 100, fill=color, opacity=0.35))
        b.append(text(x + 75, 86, d, 12, bold=True))
        b.append(text(x + 75, 106, name, 10))
        b.append(text(x + 75, 126, note, 9, MUTED))
    # 第 5 阶段总账
    b.append(text(W/2, 196, "第 5 阶段（D113~D140）总账", 13.5, bold=True))
    b.append(hand_rect(60, 216, 960, 150, fill="#F5E9C8", opacity=0.8))
    rows = [
        "· 17 周：Lowering 到 LLVM 并执行（七层对账、四路线执行 12/12）",
        "· 18 周：统一编译入口 minic（S0~S6 全真实、108 项判定、干净重建 5/5）",
        "· 19 周：Runtime 与动态 Shape（职责迁移五格、三件套齐、40 项判定）",
        "· 20 周：测试调试回归（金字塔/随机/定位/最小用例/性能/冻结）",
        "· 产出汇总：148＋40＋25≈213 项判定｜版本 v0.5.0-stage5 已冻结",
        "· future 清单 8 项→第 21 周起逐项消化",
    ]
    y = 240
    for line in rows:
        b.append(text(100, y, line, 10.5, anchor="start"))
        y += 22
    # 底部
    b.append(hand_rect(60, 386, 960, 60, fill=PURPLE, opacity=0.25))
    b.append(text(W/2, 410, "第 5 阶段的答卷：从「能导出」到「能运行」到「能交付」——", 12, bold=True))
    b.append(text(W/2, 432, "编译（17 周）→集成（18 周）→运行时（19 周）→质量（20 周）＝完整可交付的编译器项目", 10.5))
    save("02-stage5.svg", "".join(b), h=460)

def fig3():
    b = []
    b.append(text(W/2, 34, "第 21 周预告：扩展方向——冻结之上的第一个迭代", 16, bold=True))
    # 选择
    b.append(hand_rect(60, 60, 460, 250, fill=ORANGE, opacity=0.3))
    b.append(text(290, 86, "默认选择（计划建议）", 13, bold=True))
    lines = [
        "「动态 Shape＋自动调度」轻量组合",
        "",
        "为什么是它：",
        "· 承接 D128 的动态签名（已实现）",
        "· 承接 D129 的特化分发（已实现）",
        "· future F-01 块循环 Tiling 是缺的",
        "  最后一块——第 21 周的主目标",
        "· 岗位相关性高（TVM/Triton 核心）",
    ]
    y = 112
    for line in lines:
        if line:
            b.append(text(290, y, line, 10.5))
        y += 22
    b.append(hand_rect(560, 60, 460, 250, fill=BLUE, opacity=0.3))
    b.append(text(790, 86, "七天的节奏（同每周结构）", 13, bold=True))
    week21 = [
        "D141 确定唯一扩展目标（不做清单）",
        "D142 设计实现方案（接口/文件/测试）",
        "D143 实现最小正向路径",
        "D144 补充约束与失败路径",
        "D145 与现有优化集成",
        "D146 扩展功能验收（5正/3负/2边界）",
        "D147 复盘＋删除实验分支",
    ]
    y = 112
    for d in week21:
        b.append(text(790, y, d, 10.5, anchor="start"))
        y += 22
    # 底部
    b.append(hand_rect(60, 330, 960, 66, fill="#F5E9C8", opacity=0.8))
    b.append(text(W/2, 354, "扩展周的纪律（计划第 21 周的开头提醒）：", 11.5, bold=True))
    b.append(text(W/2, 376, "「只选择一个主目标，写清输入、输出、完成标准和明确不做的内容」——范围失控是扩展周的第一死因", 10.5))
    save("03-week21.svg", "".join(b), h=410)

if __name__ == "__main__":
    fig1()
    fig2()
    fig3()
