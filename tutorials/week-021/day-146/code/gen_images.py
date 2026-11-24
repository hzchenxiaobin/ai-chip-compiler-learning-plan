#!/usr/bin/env python3
"""第 146 天 3 张 SVG。种子 146。"""
from __future__ import annotations
import math, os, random
import xml.sax.saxutils as su
random.seed(146)
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
        a, b = pts[i], pts[(i+1) % 4]
        mx, my = (a[0]+b[0])/2 + jit(2.2), (a[1]+b[1])/2 + jit(2.2)
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
    b.append(text(W/2, 34, "扩展验收：10/10 全过＋D141 标准 5 条全勾", 16, bold=True))
    cols = [
        ("正向 5/5", "随机数据×5 种 tile\n(2,2,3)/(1,1,1)/(4,6,3)\n(2,3,2)/(3,2,3)\n全部 allclose ✓", GREEN),
        ("负向 3/3", "零分量拒收 ✓\n负分量拒收 ✓\n非整数拒收 ✓\nE202 带理由", RED),
        ("边界 2/2", "(1,1,1) 退化 ✓\n(8,8,8) 钳制 ✓\n极端不许崩", ORANGE),
    ]
    for i, (name, body, color) in enumerate(cols):
        x = 60 + i * 330
        b.append(hand_rect(x, 60, 300, 190, fill=color, opacity=0.35))
        b.append(text(x + 150, 88, name, 14, bold=True))
        for j, line in enumerate(body.split("\n")):
            b.append(text(x + 150, 114 + j*22, line, 10))
    # 标准 5 条
    b.append(text(W/2, 286, "D141 完成标准逐条勾", 13.5, bold=True))
    stds = [
        "① 块循环 IR 生成（gen_block_v2 产出）",
        "② tile 改变 → 产物改变（phi 7 vs 4 可 grep）",
        "③ fuzz 全过（正 5＋边 2 的数值全对）",
        "④ 性能差异可测（产物差异已证；性能对照 D153）",
        "⑤ 接入分发器（(shape,tile) key 三特化）",
    ]
    y = 308
    for std in stds:
        b.append(hand_rect(200, y, 680, 34, fill=GREEN, opacity=0.3))
        b.append(text(230, y + 23, "✓", 12, bold=True, fill="#4a7c59", anchor="start"))
        b.append(text(560, y + 23, std, 10.5))
        y += 40
    b.append(hand_rect(280, y + 10, 520, 56, fill="#F5E9C8", opacity=0.85, sw=2))
    b.append(text(W/2, y + 34, "验收结论：10/10 ＋ 5/5 —— 第 21 周主目标达成", 13, bold=True))
    b.append(text(W/2, y + 54, "「动态 Shape＋自动调度」轻量组合的最后一块（块循环 Tiling）落地", 10.5))
    save("01-accept.svg", "".join(b), h=y + 80)

def fig2():
    b = []
    b.append(text(W/2, 34, "验收方法的设计：为什么是 5/3/2", 16, bold=True))
    rows = [
        ("正向 5 组", "多 tile 覆盖（好几个 tile 形态）＋随机数据（防固定数据巧合）",
         "数量足够发现常规错；每组的 golden 独立", GREEN),
        ("负向 3 组", "三种非法类型（零/负/非整）——拒收路径的覆盖",
         "拒收是行为不是报错——E202 带理由", RED),
        ("边界 2 组", "两个极端（退化/钳制）——合法输入的刁钻角",
         "极端不许崩——兜底的存在证明", ORANGE),
    ]
    y = 60
    for name, what, why, color in rows:
        b.append(hand_rect(60, y, 960, 110, fill=color, opacity=0.25))
        b.append(text(150, y + 28, name, 12.5, bold=True))
        b.append(text(540, y + 28, what, 10.5))
        b.append(text(540, y + 54, why, 10, fill=MUTED))
        y += 120
    b.append(hand_rect(60, y + 6, 960, 70, fill="#F5E9C8", opacity=0.85))
    b.append(text(W/2, y + 32, "5/3/2 的来源：计划条目原文「至少 5 组正向、3 组负向和 2 组边界」——", 11.5, bold=True))
    b.append(text(W/2, y + 56, "三个数字的内在逻辑：正向管功能、负向管防御、边界管鲁棒——缺一面都是偏科验收（D139 四维的测试版）", 10.5))
    save("02-method.svg", "".join(b), h=y + 90)

def fig3():
    b = []
    b.append(text(W/2, 34, "第 21 周收官预览与扩展的完整账", 16, bold=True))
    week = [
        ("D141", "目标", "块循环 Tiling"),
        ("D142", "方案", "蓝图＋三零修改"),
        ("D143", "正向", "生成器＋差异"),
        ("D144", "约束", "5 负＋3 极端"),
        ("D145", "集成", "四点＋bug 修复"),
        ("D146", "验收", "10/10＋5/5 今天"),
        ("D147", "复盘", "明天"),
    ]
    for i, (d, name, note) in enumerate(week):
        x = 60 + i * 140
        color = PURPLE if d == "D147" else GREEN
        b.append(hand_rect(x, 60, 130, 100, fill=color, opacity=0.35))
        b.append(text(x + 65, 86, d, 11.5, bold=True))
        b.append(text(x + 65, 106, name, 10))
        b.append(text(x + 65, 124, note, 9, MUTED))
    # 扩展的账
    b.append(text(W/2, 200, "本周扩展的完整账（feature ledger）", 13.5, bold=True))
    b.append(hand_rect(60, 220, 960, 200, fill=BG, opacity=0.95, sw=1.8))
    rows = [
        ("新增代码", "~300 行（生成器 v1/v2＋校验＋集成适配）"),
        ("新增测试", "5 正＋3 负＋2 边＝10 例正式＋期间的 30 fuzz＋3 极端"),
        ("发现的 bug", "k0 部分和覆盖（集成测试抓住——形态对执行错的经典）"),
        ("未做（防火墙兑现）", "自动搜索/双缓冲/依赖重排/GPU——四条 × 一条没破"),
        ("向后兼容", "tile=None 零变化——v0.5.0 的全部测试不破"),
    ]
    y = 244
    for k, v in rows:
        b.append(text(110, y, k, 11, bold=True, anchor="start"))
        b.append(text(420, y, v, 10.5, anchor="start"))
        y += 28
    # 底部
    b.append(hand_rect(60, 440, 960, 66, fill="#F5E9C8", opacity=0.85))
    b.append(text(W/2, 466, "扩展周的验收标准回头看：D141 的「完成标准 5 条」今天全部可勾——", 11.5, bold=True))
    b.append(text(W/2, 488, "标准先行的价值：验收不是事后找标准，而是周一就写好的清单逐条打勾——「做到了」有据可查", 10.5))
    save("03-ledger.svg", "".join(b), h=520)

if __name__ == "__main__":
    fig1()
    fig2()
    fig3()
