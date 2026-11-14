#!/usr/bin/env python3
"""第 138 天 3 张 SVG。种子 138。"""
from __future__ import annotations
import math, os, random
import xml.sax.saxutils as su
random.seed(138)
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
    b.append(text(W/2, 34, "性能回归测试：基准、比较、报警——三件套", 16, bold=True))
    # 三件套
    kits = [
        ("P1 基准采集", "4 个基准 shape\n×7 轮采样\n中位数+P90+波动范围\n→ baseline.json", GREEN),
        ("P2 回归比较", "新测量 vs 基线\n每 shape 算比值\n<1.5× STABLE\n>1.5× REGRESSION", BLUE),
        ("P3 报警演练", "正常波动→不误报\n注入 2× 退化→必报\n阈值 1.5× 的权衡", RED),
    ]
    for i, (name, body, color) in enumerate(kits):
        x = 60 + i * 330
        b.append(hand_rect(x, 60, 300, 170, fill=color, opacity=0.35))
        b.append(text(x + 150, 88, name, 13, bold=True))
        for j, line in enumerate(body.split("\n")):
            b.append(text(x + 150, 114 + j*20, line, 10.5))
    # 实测数据
    b.append(text(W/2, 262, "P1 基准实测（4 shape）", 13.5, bold=True))
    rows = [("4×6×3", "0.0211", "±0%"), ("8×8×8", "0.1344", "±0%"),
            ("16×16×16", "1.1232", "±0%"), ("32×32×32", "8.9414", "±0%")]
    y = 284
    for shape, med, spread in rows:
        b.append(hand_rect(200, y, 680, 32, fill=GREEN, opacity=0.3))
        b.append(text(350, y + 21, shape, 11, mono=True))
        b.append(text(550, y + 21, f"中位 {med} µs", 10.5))
        b.append(text(750, y + 21, spread, 10.5, fill=MUTED))
        y += 38
    # 底部
    b.append(hand_rect(60, y + 10, 960, 90, fill="#F5E9C8", opacity=0.8))
    b.append(text(W/2, y + 34, "三件套的分工：基线是尺子（什么算正常）、比较是判决（新的是否正常）、报警是底线（不正常必须有人知道）", 11.5, bold=True))
    b.append(text(W/2, y + 58, "D107 的测量纪律（3+7/3+21）与 D125 的 kernel 级口径（同进程 2 万次）在今天的 formal 体系里会师", 10.5))
    b.append(text(W/2, y + 78, "性能回归与正确性回归的差别：正确性是二值（对/错）、性能是分布（好/坏/噪声）——所以要有阈值与统计口径", 10.5, MUTED))
    save("01-overview.svg", "".join(b), h=y + 110)

def fig2():
    b = []
    b.append(text(W/2, 34, "阈值 1.5× 的权衡：误报疲劳 vs 漏报风险", 16, bold=True))
    # 阈值数轴
    b.append(hand_rect(120, 60, 840, 70, fill=BG, opacity=0.95, sw=1.8))
    zones = [(120, 300, GREEN, "改善区 <0.67×"), (300, 560, BLUE, "稳定区 0.67~1.5×"),
             (560, 760, ORANGE, "警告区 1.5~2×"), (760, 960, RED, "报警区 >2×")]
    for x1, x2, color, label in zones:
        b.append(hand_rect(x1, 70, x2 - x1, 50, fill=color, opacity=0.4))
        b.append(text((x1 + x2) / 2, 92, label, 9.5, bold=True))
        b.append(text((x1 + x2) / 2, 108, f"{x1/840:.1f}~{x2/840:.1f}×", 8.5, fill=MUTED))
    # 波动 vs 退化
    b.append(text(W/2, 170, "两种「变慢」：波动（噪声）与退化（信号）", 13.5, bold=True))
    b.append(hand_rect(60, 190, 460, 180, fill=BLUE, opacity=0.28))
    b.append(text(290, 216, "波动（±8% 噪声）", 12.5, bold=True))
    lines1 = ["来源：频率迁移/缓存状态/中断", "特征：无方向、有界", "应对：中位数＋阈值容忍", "误报后果：报警疲劳（狼来了）"]
    y = 240
    for line in lines1:
        b.append(text(290, y, line, 10))
        y += 22
    b.append(hand_rect(560, 190, 460, 180, fill=RED, opacity=0.28))
    b.append(text(790, 216, "退化（2× 信号）", 12.5, bold=True))
    lines2 = ["来源：代码变更引入的低效", "特征：持续性、有方向", "应对：超过阈值立即报警", "漏报后果：性能悄悄烂掉"]
    y = 240
    for line in lines2:
        b.append(text(790, y, line, 10))
        y += 22
    # 底部
    b.append(hand_rect(60, 390, 960, 80, fill="#F5E9C8", opacity=0.8))
    b.append(text(W/2, 414, "阈值设计的经验法则", 12, bold=True))
    b.append(text(W/2, 438, "阈值 ≥ 2×观测波动（8%×2 边际 ≈ 1.2×，取整 1.5×）——太紧误报疲劳、太松漏报真退化", 10.5))
    b.append(text(W/2, 458, "生产系统的分层：1.5× 警告（看看）／2× 报警（必须处理）／5× 冻结发布（灾难）——D139 的冻结检查", 10.5, MUTED))
    save("02-mechanism.svg", "".join(b), h=490)

def fig3():
    b = []
    b.append(text(W/2, 34, "性能回归体系的完整形态与本周会师", 16, bold=True))
    # 体系
    b.append(hand_rect(60, 60, 960, 190, fill=PURPLE, opacity=0.25))
    b.append(text(W/2, 86, "性能回归体系（生产形态）", 13, bold=True))
    rows = [
        ("基准集", "固定 shape＋固定数据＋固定环境声明——任何一条变，基线重采"),
        ("采集", "每 shape N 轮×M 次调用→中位数/P90/波动范围——冷启动剔除"),
        ("比较", "新代码 vs 基线→每 shape 比值→分层判定（稳定/警告/报警）"),
        ("报警", "CI 集成——报警的 commit 无法合入；恢复后基线更新"),
        ("复盘", "每季度复审基准集的代表性（新热点 shape 要进、过时要出）"),
    ]
    y = 106
    for k, v in rows:
        b.append(text(180, y, k, 11, bold=True))
        b.append(text(560, y, v, 10, anchor="start", fill=MUTED))
        y += 26
    # 本周会师
    b.append(text(W/2, 286, "第 20 周的四天会师", 13.5, bold=True))
    days = [
        ("D134", "测试整理", "16 例正反集"), ("D135", "随机 fuzz", "200 组全对"),
        ("D136", "二分定位", "注入精确指认"), ("D137", "最小用例", "19→4 节点"),
        ("D138", "性能回归", "阈值 1.5× 双验"), ("D139", "完整回归", "明天：冻结"),
    ]
    for i, (d, name, note) in enumerate(days):
        x = 60 + i * 165
        color = PURPLE if d == "D139" else GREEN
        b.append(hand_rect(x, 306, 150, 90, fill=color, opacity=0.35))
        b.append(text(x + 75, 330, d, 11.5, bold=True))
        b.append(text(x + 75, 350, name, 10))
        b.append(text(x + 75, 370, note, 9, MUTED))
    # 底部
    b.append(hand_rect(60, 416, 960, 66, fill="#F5E9C8", opacity=0.8))
    b.append(text(W/2, 440, "正确性回归（D134/135）答「对不对」；性能回归（今天）答「快不快」；", 11.5, bold=True))
    b.append(text(W/2, 462, "明天的完整回归（D139）把两把尺子＋编译时间＋文档一起量——项目冻结的质量总闸", 10.5))
    save("03-system.svg", "".join(b), h=500)

if __name__ == "__main__":
    fig1()
    fig2()
    fig3()
