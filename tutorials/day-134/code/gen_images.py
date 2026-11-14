#!/usr/bin/env python3
"""第 134 天 3 张 SVG。种子 134。"""
from __future__ import annotations
import math, os, random
import xml.sax.saxutils as su

random.seed(134)
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
    b.append(text(W/2, 34, "测试金字塔：三层职责与数量配比", 16, bold=True))
    # 金字塔
    layers = [
        ("L3 端到端", "输入图→执行→golden", "1 例（D124 12/12）", "慢（秒）·总闸", RED, 300),
        ("L2 IR 文本", "输入 IR→期望 IR（file-check）", "雏形（D123 改写记录）", "中速·锁 Pass 行为", ORANGE, 500),
        ("L1 单元", "一个 Pattern 一个 case", "16 例（今天整理）", "快（µs）·定位准", GREEN, 700),
    ]
    for i, (name, what, count, prop, color, width) in enumerate(layers):
        y = 60 + i * 130
        x = (W - width) / 2
        b.append(hand_rect(x, y, width, 110, fill=color, opacity=0.4))
        b.append(text(W/2, y + 28, name, 14, bold=True))
        b.append(text(W/2, y + 52, what, 10.5))
        b.append(text(W/2, y + 74, count, 11, bold=True, fill="#4a7c59" if "例" in count else ORANGE))
        b.append(text(W/2, y + 94, prop, 9.5, fill=MUTED))
    # 配比
    b.append(hand_rect(60, 460, 960, 60, fill="#F5E9C8", opacity=0.8))
    b.append(text(W/2, 484, "健康配比 L1:L2:L3 ≈ 10:3:1——大量快测试打底、少量慢总闸封顶", 11.5, bold=True))
    b.append(text(W/2, 506, "当前项目：L1 16 例（今天）｜L2 雏形｜L3 1 例——底部厚顶部薄，符合教学阶段", 10.5))
    save("01-pyramid.svg", "".join(b), h=540)

def fig2():
    b = []
    b.append(text(W/2, 34, "五类组件 × 正反例：16 例测试集的组织", 16, bold=True))
    cats = [
        ("Verifier", 3, 1, "合法性闸的守门测试", GREEN),
        ("Shape", 5, 1, "三来源推断＋两个拒收", BLUE),
        ("融合", 1, 2, "结构+收益双门的边界", ORANGE),
        ("Layout", 1, 1, "常量折叠的能与不能", PURPLE),
        ("Lowering", 1, 2, "管道通过＋两类拒收", RED),
    ]
    for i, (name, pos, neg, note, color) in enumerate(cats):
        x = 50 + i * 200
        b.append(hand_rect(x, 60, 180, 150, fill=color, opacity=0.35))
        b.append(text(x + 90, 88, name, 12.5, bold=True))
        b.append(text(x + 90, 112, f"正例 {pos}", 11, fill="#4a7c59", bold=True))
        b.append(text(x + 90, 132, f"反例 {neg}", 11, fill=RED, bold=True))
        b.append(text(x + 90, 160, note, 9))
    b.append(hand_rect(60, 230, 960, 80, fill="#F5E9C8", opacity=0.8))
    b.append(text(W/2, 254, "反例的价值：它们是免疫系统的记忆——每个 ✗ 都对应一次真实的踩坑", 12, bold=True))
    b.append(text(W/2, 276, "（V-neg-内维不匹配←D83 T01 的真实报错；L-neg-vector 残账←D122 TP5 的注入实验；出处列就是坑史）", 10.5))
    # 反例详情
    b.append(text(W/2, 340, "六个反例的「拒收理由」清单", 13.5, bold=True))
    negs = [
        ("内维不匹配", "matmul(4x6, 2x3)", "闸0：K=6≠2"),
        ("非法排列", "perm=[0,0,1]", "闸0：不是排列"),
        ("不可推断", "未知算子输出", "E202：无 shape 来源"),
        ("元素数不符", "(2,3)→(7,)", "闸0：6≠7"),
        ("多使用者", "matmul 双下游", "融合边界：破坏语义"),
        ("vector 残账", "vector.reduce", "E204：pass 拒收"),
    ]
    y = 360
    for i, (name, inp, why) in enumerate(negs):
        x = 60 + (i % 3) * 320
        yy = y + (i // 3) * 80
        b.append(hand_rect(x, yy, 300, 70, fill=RED, opacity=0.2))
        b.append(text(x + 150, yy + 20, name, 10.5, bold=True))
        b.append(text(x + 150, yy + 38, inp, 9.5, mono=True))
        b.append(text(x + 150, yy + 56, why, 9, fill=RED))
    save("02-cases.svg", "".join(b), h=530)

def fig3():
    b = []
    b.append(text(W/2, 34, "正反例的写作纪律：每例四要素", 16, bold=True))
    elems = [
        ("① 输入", "构造最小触发条件", "「matmul(4x6, 2x3)」——不是「错误的图」"),
        ("② 期望行为", "通过什么/拒绝什么——精确到诊断码", "「闸0 拒绝：内维不匹配」不是「失败」"),
        ("③ 出处", "这个 case 从哪次真实踩坑来", "「D83 T01」——坑史可追溯"),
        ("④ 反例的边界", "拒收的理由要写成断言", "「K=6≠2」可 grep——不是「感觉不对」"),
    ]
    y = 60
    for title, body, example in elems:
        b.append(hand_rect(60, y, 960, 90, fill=BLUE, opacity=0.25))
        b.append(text(100, y + 26, title, 12.5, bold=True, anchor="start"))
        b.append(text(400, y + 26, body, 10.5, anchor="start"))
        b.append(text(100, y + 56, f"例：{example}", 10, anchor="start", fill=MUTED))
        y += 100
    b.append(hand_rect(60, y + 10, 960, 70, fill="#F5E9C8", opacity=0.8))
    b.append(text(W/2, y + 36, "四要素齐全的测试才能「失败时告诉你答案」——缺出处的测试是孤儿（改语义时没人敢动它）", 11.5, bold=True))
    b.append(text(W/2, y + 58, "明天的随机 Shape 测试（D135）会把这层基座扩大一个数量级——随机是手工正反例的放大器", 10.5))
    save("03-discipline.svg", "".join(b), h=y + 90)

if __name__ == "__main__":
    fig1()
    fig2()
    fig3()
