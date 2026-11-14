#!/usr/bin/env python3
"""第 149 天 3 张 SVG。种子 149。"""
from __future__ import annotations
import math, os, random
import xml.sax.saxutils as su
random.seed(149)
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
    b.append(text(W/2, 34, "时间分解：首次调用 97.7% 在编译、稳态 100% 在执行", 15, bold=True))
    # 两个视角
    b.append(hand_rect(60, 60, 460, 300, fill=BLUE, opacity=0.28))
    b.append(text(290, 86, "首次调用（端到端）", 13, bold=True))
    firsts = [("编译（一次性）", 928.86, 97.7, BLUE), ("kernel 执行", 21.44, 2.3, RED),
              ("描述符+调用+分配", 0.006, 0.0, MUTED)]
    y = 110
    for name, ms, pct, color in firsts:
        b.append(text(130, y, name, 10.5, anchor="start"))
        bar_w = max(2, pct / 100 * 280)
        b.append(hand_rect(300, y - 12, bar_w, 22, fill=color, opacity=0.5))
        b.append(text(620, y, f"{ms:.2f}ms {pct:.1f}%", 10, anchor="start"))
        y += 40
    b.append(text(290, y + 24, "→ 首次调用的体验瓶颈：编译", 11, bold=True, fill=BLUE))
    b.append(text(290, y + 46, "（JIT 场景的冷启动问题——D129 缓存的动机）", 9.5, fill=MUTED))
    b.append(hand_rect(560, 60, 460, 300, fill=RED, opacity=0.25))
    b.append(text(790, 86, "稳态（编译摊销后）", 13, bold=True))
    steadies = [("kernel 执行", 21.444, 100.0, RED), ("描述符", 0.005, 0.02, MUTED),
                ("调用+分配", 0.001, 0.0, MUTED)]
    y = 110
    for name, ms, pct, color in steadies:
        b.append(text(630, y, name, 10.5, anchor="start"))
        bar_w = max(2, pct / 100 * 280)
        b.append(hand_rect(800, y - 12, bar_w, 22, fill=color, opacity=0.5))
        b.append(text(1110 if False else 1020, y, f"{ms:.3f}ms {pct:.1f}%", 10, anchor="start"))
        y += 40
    b.append(text(790, y + 24, "→ 稳态的性能瓶颈：执行本身", 11, bold=True, fill=RED))
    b.append(text(790, y + 46, "（21.4ms 里是计算受限还是访存？——D150 Roofline）", 9.5, fill=MUTED))
    # 底部
    b.append(hand_rect(60, 380, 960, 70, fill="#F5E9C8", opacity=0.85))
    b.append(text(W/2, 406, "两个视角的分工：首次视角管「用户体验」（JIT 延迟）、稳态视角管「吞吐」（推理性能）——", 11.5, bold=True))
    b.append(text(W/2, 428, "归因要看稳态（D148 基线的口径）——编译是一次性成本，可摊销可缓存；执行是每次都付的", 10.5))
    save("01-two-views.svg", "".join(b), h=470)

def fig2():
    b = []
    b.append(text(W/2, 34, "测量方法：小 kernel 对照法分离开销", 16, bold=True))
    steps = [
        ("① 测小 kernel", "2×2×2 同结构 kernel\n执行≈0 → 总时间≈纯开销", GREEN),
        ("② 测大 kernel", "160³ 同结构 kernel\n总时间 = 开销 + 执行", BLUE),
        ("③ 相减", "净执行 = 大总 − 小总\n21.444 − 0.001 ≈ 21.44ms", ORANGE),
    ]
    for i, (name, body, color) in enumerate(steps):
        x = 60 + i * 330
        b.append(hand_rect(x, 60, 300, 130, fill=color, opacity=0.35))
        b.append(text(x + 150, 88, name, 12.5, bold=True))
        for j, line in enumerate(body.split("\n")):
            b.append(text(x + 150, 112 + j*22, line, 10))
    # 方法论
    b.append(hand_rect(60, 220, 960, 110, fill="#F5E9C8", opacity=0.85))
    b.append(text(W/2, 246, "小 kernel 对照法的假设与边界", 12.5, bold=True))
    lines = [
        "假设：同结构的 2³ kernel 执行时间≈0（160³ 的 1/512000）——开销与 shape 无关（描述符/调用/小分配）",
        "边界：kernel 内 malloc 与 shape 相关（输出缓冲 160²×4B=102KB vs 16B）——但相对 21ms 仍可忽略",
        "对照：真实系统用空 kernel 或 nop kernel 做同样的分离（CUDA 的 empty kernel launch ~5µs）",
    ]
    for j, line in enumerate(lines):
        b.append(text(W/2, 272 + j*22, line, 10.5))
    save("02-method.svg", "".join(b), h=350)

def fig3():
    b = []
    b.append(text(W/2, 34, "五段的嫌疑排序与明天的路", 16, bold=True))
    suspects = [
        ("kernel 执行", "21.44ms", "★★★★★ 头号嫌疑——稳态 100%", RED),
        ("编译", "929ms（一次性）", "★★★ 首次体验——可摊销/缓存", ORANGE),
        ("搜索", "0（教学版）", "—— 无（真实系统可能小时级）", MUTED),
        ("描述符+调用", "0.006ms", "☆ 可忽略", GREEN),
        ("分配", "≈0.001ms", "☆ 可忽略（教学规模）", GREEN),
    ]
    y = 60
    for name, val, note, color in suspects:
        b.append(hand_rect(60, y, 960, 60, fill=color, opacity=0.2 if "☆" in note or "无" in note else 0.3))
        b.append(text(200, y + 26, name, 12, bold=True))
        b.append(text(450, y + 26, val, 11, mono=True))
        b.append(text(750, y + 26, note, 10, anchor="start"))
        y += 66
    b.append(hand_rect(60, y + 10, 960, 70, fill="#F5E9C8", opacity=0.85))
    b.append(text(W/2, y + 36, "嫌疑排序完成：头号嫌疑是 kernel 执行（21.4ms、稳态 100%）——", 12, bold=True))
    b.append(text(W/2, y + 60, "明天 D150 的 Roofline 分析把这 21.4ms 拆成「计算受限 vs 访存受限」：算术强度是钥匙", 10.5))
    save("03-suspects.svg", "".join(b), h=y + 90)

if __name__ == "__main__":
    fig1()
    fig2()
    fig3()
