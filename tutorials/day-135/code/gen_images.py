#!/usr/bin/env python3
"""第 135 天 3 张 SVG。种子 135。"""
from __future__ import annotations
import math, os, random
import xml.sax.saxutils as su
random.seed(135)
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
    b.append(text(W/2, 34, "随机 Shape 测试：200 组全对、种子可复现、注入全检出", 16, bold=True))
    cards = [
        ("F1 随机正确性", "200 组随机 (M,K,N)\nM/K/N ∈ [1,32]\n含 1 维退化/方阵/长扁\n动态 kernel vs numpy\n结果：全部 PASS", GREEN),
        ("F2 种子可复现", "同种子两遍\nshape 序列完全一致\n失败时报告\n「种子 + trial 号」\n→ 精确复现", BLUE),
        ("F3 失败注入", "故意注入 bug golden\n（k 少一圈）\n20/20 全检出\n失败用例自动保存\ninjected-failures.json", RED),
    ]
    for i, (name, body, color) in enumerate(cards):
        x = 60 + i * 330
        b.append(hand_rect(x, 60, 300, 220, fill=color, opacity=0.35))
        b.append(text(x + 150, 88, name, 13.5, bold=True))
        for j, line in enumerate(body.split("\n")):
            b.append(text(x + 150, 116 + j*20, line, 10.5,
                          bold=("PASS" in line or "一致" in line or "20/20" in line)))
    # 随机的分布
    b.append(text(W/2, 310, "随机的价值：覆盖手工想不到的组合", 14, bold=True))
    b.append(hand_rect(60, 330, 960, 130, fill="#F5E9C8", opacity=0.8))
    lines = [
        "手工正反例（D134 的 16 例）覆盖「想得到的坑」；随机测试探索「想不到的组合」——",
        "M=1×K=1×N=1 的全退化、31×1×31 的极扁、16×16×16 的方阵——边界形态由分布自然给出",
        "配比纪律（计划条目）：先验证正确性再记录性能——今天只跑正确性（性能归 D138 的基准）",
    ]
    for j, line in enumerate(lines):
        b.append(text(W/2, 356 + j*24, line, 11 if j == 0 else 10.5, bold=(j == 0)))
    # 底部数字
    b.append(text(W/2, 496, "一天的数字", 13.5, bold=True))
    stats = [("200 组", "随机全对"), ("1 个种子", "完全可复现"), ("20/20", "注入检出"), ("0 个", "孤儿失败")]
    for i, (num, label) in enumerate(stats):
        x = 120 + i * 220
        b.append(hand_rect(x, 516, 200, 66, fill=GREEN, opacity=0.4))
        b.append(text(x + 100, 542, num, 14, bold=True))
        b.append(text(x + 100, 562, label, 10, MUTED))
    save("01-overview.svg", "".join(b), h=600)

def fig2():
    b = []
    b.append(text(W/2, 34, "Fuzz 测试的工作流：生成→执行→对照→（失败）保存→复现", 16, bold=True))
    steps = [
        ("① 生成", "rng(M,K,N)\n固定种子", GREEN),
        ("② 执行", "动态 kernel\n（一份 .ll）", BLUE),
        ("③ 对照", "k 序 golden\nallclose", ORANGE),
        ("④ 失败？", "保存 shape+种子\n+trial 号", RED),
        ("⑤ 复现", "同种子重跑\n→ 精确重现", PURPLE),
    ]
    for i, (name, body, color) in enumerate(steps):
        x = 50 + i * 205
        b.append(hand_rect(x, 60, 185, 110, fill=color, opacity=0.35))
        b.append(text(x + 92, 88, name, 12.5, bold=True))
        for j, line in enumerate(body.split("\n")):
            b.append(text(x + 92, 112 + j*18, line, 9.5))
        if i < 4:
            b.append(hand_rect(x + 187, 100, 16, 30, fill=INK, opacity=0.5))
    # 失败用例文件
    b.append(text(W/2, 210, "失败复现文件（injected-failures.json 摘录）", 13.5, bold=True))
    b.append(hand_rect(200, 230, 680, 160, fill=BG, opacity=0.95, sw=1.8))
    code = [
        '{',
        '  "seed": 20261116,',
        '  "failures": [',
        '    {"trial": 0, "M": 5, "K": 9, "N": 12,',
        '     "note": "k 少一圈的 golden vs 正确 kernel"},',
        '    {"trial": 1, "M": 13, "K": 4, "N": 2, ...}',
        '  ]',
        '}',
    ]
    y = 252
    for line in code:
        b.append(text(240, y, line, 10.5, mono=True, anchor="start"))
        y += 18
    # 底部纪律
    b.append(hand_rect(60, 420, 960, 90, fill="#F5E9C8", opacity=0.8))
    b.append(text(W/2, 446, "两条纪律（计划条目的原文展开）", 12.5, bold=True))
    b.append(text(W/2, 470, "① 固定随机种子——没有种子的 fuzz 报告无法复现，等于没有报告", 11))
    b.append(text(W/2, 492, "② 失败用例保存——随机发现的坑要『固化』成 D134 的手工正反例（随机→手工的回流）", 11))
    save("02-workflow.svg", "".join(b), h=530)

def fig3():
    b = []
    b.append(text(W/2, 34, "随机测试的边界与下一步", 16, bold=True))
    # 边界
    b.append(hand_rect(60, 60, 460, 240, fill=RED, opacity=0.2))
    b.append(text(290, 86, "随机测不到的（诚实清单）", 13, bold=True))
    limits = [
        "· 数值精度边界（atol=1e-4 的灰区）：",
        "  随机数据在大 K 下的舍入累积——阈值设紧会误报",
        "· 并发竞争（D132 场景 C）：",
        "  单线程 fuzz 触不到时序竞争",
        "· 极端规模（内存上限）：",
        "  [1,32] 的 shape 不触碰 OOM 路径",
        "· Tile 参数（计划条目提到）：",
        "  教学版 tile 不消费（D125 空变量）——待块循环",
    ]
    y = 112
    for line in limits:
        b.append(text(90, y, line, 10, anchor="start"))
        y += 22
    # 下一步
    b.append(hand_rect(560, 60, 460, 240, fill=GREEN, opacity=0.3))
    b.append(text(790, 86, "随机测试的进化路线", 13, bold=True))
    nexts = [
        "① 覆盖引导（coverage-guided）：",
        "  记录已覆盖的代码路径，倾向生成新路径的输入",
        "② 失败最小化（D137 预告）：",
        "  随机发现的失败 shape 自动 shrink 到最小",
        "③ 性能 fuzz（D138 预告）：",
        "  正确性全过后的性能分布记录",
        "④ 回归固化：",
        "  每个随机发现的坑→手工正反例（免疫回流）",
    ]
    y = 112
    for line in nexts:
        b.append(text(590, y, line, 10, anchor="start"))
        y += 22
    # 底部
    b.append(hand_rect(60, 320, 960, 60, fill="#F5E9C8", opacity=0.8))
    b.append(text(W/2, 344, "随机与手工的关系：手工是精锐（每例都有出处与意图），随机是军团（量级压倒）——", 11.5, bold=True))
    b.append(text(W/2, 366, "D134 的 16 例手工正反例 + 今天的 200 组随机 = 教学项目的完整 L1 层", 10.5))
    save("03-limits.svg", "".join(b), h=400)

if __name__ == "__main__":
    fig1()
    fig2()
    fig3()
