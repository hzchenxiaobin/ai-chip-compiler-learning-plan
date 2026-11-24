#!/usr/bin/env python3
"""第 129 天（静态 Shape 特化）3 张 SVG。种子 129。"""
from __future__ import annotations
import math, os, random
import xml.sax.saxutils as su

random.seed(129)
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
    b.append(text(W/2, 34, "静态 Shape 特化：两层分发——特化拿性能、动态兜正确", 16, bold=True))
    # 顶层：调用
    b.append(hand_rect(340, 56, 400, 48, fill=ORANGE, opacity=0.7, sw=2))
    b.append(text(W/2, 78, "disp.run(A, B)  →  shape=(M,K,N) 查表", 13, bold=True, mono=True))
    b.append(arrow(W/2, 106, W/2, 140, sw=2))
    # 分发器
    b.append(hand_rect(340, 144, 400, 52, fill=PURPLE, opacity=0.5))
    b.append(text(W/2, 166, "Dispatcher（分发器）", 13, bold=True))
    b.append(text(W/2, 186, "特化表 {(4,6,3): lib_s4x6x3, (8,8,8): lib_s8x8x8}", 9.5, mono=True))
    # 两层
    b.append(arrow(400, 198, 250, 250, sw=2, label="命中 hit"))
    b.append(arrow(680, 198, 830, 250, sw=2, label="未命中 miss", dash="6 4"))
    b.append(hand_rect(60, 254, 380, 200, fill=GREEN, opacity=0.42))
    b.append(text(250, 280, "特化层（静态 kernel＋O2）", 13, bold=True))
    b.append(text(250, 302, "shape 常量编进指令", 10.5))
    b.append(text(250, 322, "O2 敢展开：fmul 2 → 18（9 倍）", 11, bold=True, fill="#4a7c59"))
    b.append(text(250, 344, "phi 10 → 1（循环控制消掉）", 10.5))
    b.append(text(250, 366, "150 行 .ll（膨胀但快）", 10, MUTED))
    b.append(text(250, 388, "产物：spec-4x6x3/libkernel.dylib", 9.5, mono=True, fill=MUTED))
    b.append(text(250, 410, "50000 B/份（代码大小记录）", 9.5, fill=MUTED))
    b.append(hand_rect(640, 254, 380, 200, fill=BLUE, opacity=0.42))
    b.append(text(830, 280, "动态层（memref<?x?x> 兜底）", 13, bold=True))
    b.append(text(830, 302, "shape 从描述符读回", 10.5))
    b.append(text(830, 322, "任何 shape 都能跑", 11, bold=True, fill=BLUE))
    b.append(text(830, 344, "O2 保守：fmul=2、phi=10", 10.5))
    b.append(text(830, 366, "141 行 .ll（紧凑但慢）", 10, MUTED))
    b.append(text(830, 388, "产物：e2-dynamic/libdyn.dylib", 9.5, mono=True, fill=MUTED))
    b.append(text(830, 410, "一份 .ll 吃任意 shape（D128）", 9.5, fill=MUTED))
    # 底部
    b.append(hand_rect(60, 480, 960, 100, fill="#F5E9C8", opacity=0.8))
    b.append(text(W/2, 506, "两层分发的本质：把「优化空间」与「灵活性」解耦——", 12.5, bold=True))
    b.append(text(W/2, 530, "热点 shape 走特化（O2 展开的收益全额兑现）、长尾 shape 走动态（正确性兜底不拒收）", 10.5))
    b.append(text(W/2, 552, "真实世界对应：PyTorch 2.x 的 shape 特化缓存、TVM 的 shape-generic fallback——三件套的第一件", 10.5, MUTED))
    b.append(text(W/2, 590, "（第二件缓存＝今天的 E3 幂等；第三件回退＝明天 D130）", 10, MUTED))
    save("01-overview.svg", "".join(b), h=610)


def fig2():
    b = []
    b.append(text(W/2, 34, "特化收益的机器码证据：O2 为什么敢展开静态版？", 16, bold=True))
    # 左右对照
    b.append(hand_rect(50, 60, 480, 280, fill=GREEN, opacity=0.3))
    b.append(text(290, 86, "静态特化版（4×6×3）", 13, bold=True))
    lines_s = [
        "%cK = arith.constant 6 : index      ← K 是常量",
        "...Lowering...",
        "%48 = icmp slt i64 %46, 6            ← 常量比较",
        "...opt -O2 展开...",
        "fmul × 18（K 循环展开＋部分展开）",
        "phi × 1（循环变量消掉）",
        "",
        "为什么敢展开：优化器能证明",
        "「循环恰好跑 6 次」——unroll 安全",
    ]
    y = 112
    for line in lines_s:
        if line:
            b.append(text(90, y, line, 10, mono=True, anchor="start",
                          fill="#4a7c59" if "敢" in line or "fmul" in line else INK))
        y += 22
    b.append(hand_rect(550, 60, 480, 280, fill=BLUE, opacity=0.3))
    b.append(text(790, 86, "动态版（memref<?x?x>）", 13, bold=True))
    lines_d = [
        "%K = memref.dim %a, %c1              ← 运行期读",
        "...Lowering...",
        "%54 = icmp slt i64 %52, %30          ← SSA 比较",
        "...opt -O2 保守...",
        "fmul × 2（只敢部分展开）",
        "phi × 10（控制流反而变多）",
        "",
        "为什么不敢：优化器无法证明",
        "循环次数——unroll 不安全",
    ]
    y = 112
    for line in lines_d:
        if line:
            b.append(text(590, y, line, 10, mono=True, anchor="start",
                          fill=RED if "不敢" in line else INK))
        y += 22
    # 底部：unroll 安全性
    b.append(hand_rect(50, 360, 980, 120, fill="#F5E9C8", opacity=0.8))
    b.append(text(W/2, 386, "展开的安全性证明——优化器的视角", 13, bold=True))
    b.append(text(W/2, 410, "静态：迭代次数 = ⌈(6−0)/1⌉ = 6（编译期可算）→ 展开成 6 份乘加，正确性可证", 11))
    b.append(text(W/2, 434, "动态：迭代次数 = ⌈(%30−0)/1⌉，%30 运行期才知道 → 展开需要「次数≥N」的前提，无法证明", 11))
    b.append(text(W/2, 458, "→ 特化的本质：把「运行期才知道的事实」提前到编译期告诉优化器——确定性是优化器的燃料", 11, fill="#4a7c59", bold=True))
    save("02-mechanism.svg", "".join(b), h=500)


def fig3():
    b = []
    b.append(text(W/2, 34, "三件套进度与特化的成本账", 16, bold=True))
    # 三件套
    kits = [
        ("特化（今天）", "按 shape 编译专用 kernel\n静态签名→O2 展开\n收益：fmul 2→18", GREEN),
        ("缓存（E3 雏形）", "特化产物按 shape 复用\n幂等 register\n磁盘=libkernel.dylib", ORANGE),
        ("回退（明天 D130）", "miss 时走动态兜底\n错误时的降级路径\n真实系统：OOM→CPU", RED),
    ]
    for i, (name, body, color) in enumerate(kits):
        x = 60 + i * 330
        b.append(hand_rect(x, 60, 300, 140, fill=color, opacity=0.4))
        b.append(text(x + 150, 88, name, 13, bold=True))
        for j, line in enumerate(body.split("\n")):
            b.append(text(x + 150, 112 + j*20, line, 10))
    # 成本账
    b.append(text(W/2, 240, "特化的成本账（不是免费的午餐）", 14, bold=True))
    costs = [
        ("编译时间", "每个 shape 全管道一次（~1s 教学版）", "首次调用慢——JIT 编译延迟"),
        ("代码体积", "每份特化 50000 B（.dylib 含元数据）", "shape 种类多→体积膨胀"),
        ("维护复杂度", "分发器＋两层产物＋统计", "调试要区分走的是哪层"),
        ("覆盖盲区", "只特化注册过的 shape", "长尾 shape 永远走慢路"),
    ]
    y = 262
    for k, v, note in costs:
        b.append(hand_rect(80, y, 920, 52, fill=RED, opacity=0.2))
        b.append(text(110, y + 22, k, 11.5, bold=True, anchor="start"))
        b.append(text(280, y + 22, v, 10.5, anchor="start"))
        b.append(text(280, y + 42, note, 9.5, anchor="start", fill=MUTED))
        y += 58
    # 底部
    b.append(hand_rect(80, y + 6, 920, 56, fill="#F5E9C8", opacity=0.8))
    b.append(text(W/2, y + 30, "特化决策的判据：shape 的分布（热点集中→特化赚；shape 均匀→特化亏）", 12, bold=True))
    b.append(text(W/2, y + 50, "真实系统的做法：按调用频率阈值触发特化（PyTorch 2.x：同 shape 出现 N 次后 compile）——D136 的观测数据是输入", 10.5))
    save("03-example.svg", "".join(b), h=y + 80)


if __name__ == "__main__":
    fig1()
    fig2()
    fig3()
