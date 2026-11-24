#!/usr/bin/env python3
"""第 133 天（第 19 周复盘）3 张 SVG。种子 133。"""
from __future__ import annotations
import math, os, random
import xml.sax.saxutils as su

random.seed(133)
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
    b.append(text(W/2, 34, "职责迁移表：一周翻了五格（D127 审计 → D133）", 16, bold=True))
    rows = [
        ("Shape 确定", "COMPILE", "RUNTIME", "D128", "一份 .ll 三 shape", GREEN),
        ("Kernel 选择", "COMPILE", "SPLIT", "D129", "两层分发 fmul 2→18", GREEN),
        ("内存释放", "NONE", "RUNTIME", "D131", "BufferPool.destroy", GREEN),
        ("Kernel 缓存", "NONE", "雏形", "D129", "幂等 register", ORANGE),
        ("错误恢复", "COMPILE", "＋RUNTIME", "D130", "四级降级链", GREEN),
        ("同步", "IMPLICIT", "显式化路径", "D132", "Stream/Event 仿真", ORANGE),
        ("Stride", "COMPILE", "COMPILE", "—", "教学取舍保持", MUTED),
        ("Tile", "COMPILE", "COMPILE", "—", "第三周空变量", MUTED),
        ("搬运", "CALLER", "CALLER", "—", "未动", MUTED),
    ]
    y = 60
    b.append(text(150, y, "决策点", 10.5, bold=True)); b.append(text(330, y, "周一", 10.5, bold=True))
    b.append(text(500, y, "周五", 10.5, bold=True)); b.append(text(620, y, "翻转日", 10.5, bold=True))
    b.append(text(850, y, "证据", 10.5, bold=True))
    y += 14
    for name, before, after, day, ev, color in rows:
        flipped = color == GREEN
        b.append(hand_rect(80, y, 920, 40, fill=color if color != MUTED else BLUE, opacity=0.3 if flipped else 0.15))
        b.append(text(150, y + 26, name, 10.5, bold=True))
        b.append(text(330, y + 26, before, 10, mono=True, fill=MUTED))
        b.append(text(500, y + 26, after, 10.5, mono=True, bold=flipped, fill="#4a7c59" if flipped else INK))
        b.append(text(620, y + 26, day, 10, bold=flipped))
        b.append(text(850, y + 26, ev, 9.5, fill=MUTED))
        if flipped:
            b.append(arrow(415, y + 20, 455, y + 20, sw=1.4))
        y += 46
    b.append(hand_rect(80, y + 8, 920, 56, fill="#F5E9C8", opacity=0.8))
    b.append(text(W/2, y + 30, "翻转统计：5 格实质翻转＋1 格补全＋1 格路径清晰＋3 格保持（教学取舍的诚实记录）", 11.5, bold=True))
    b.append(text(W/2, y + 52, "保持的三格不是遗漏——是教学刻度的显式选择（Stride/Tile/搬运：下周起的候选）", 10.5))
    save("01-migration.svg", "".join(b), h=y + 80)

def fig2():
    b = []
    b.append(text(W/2, 34, "动态化的完整成本：一格翻转＝一串涟漪＋三件配套", 16, bold=True))
    # 涟漪
    b.append(hand_rect(60, 60, 460, 260, fill=BLUE, opacity=0.3))
    b.append(text(290, 86, "一串涟漪（D128 六件事）", 13, bold=True))
    ripples = ["① 签名 memref<4x6>→<?x?x>", "② 读回 dim+extractvalue",
               "③ 分配 alloc(%M,%N)", "④ 边界 icmp 常量→SSA",
               "⑤ 验证参数化", "⑥ 性能语义收缩（fmul 18→2）"]
    y = 112
    for r in ripples:
        b.append(text(100, y, r, 10.5, anchor="start", mono=True))
        y += 22
    b.append(text(290, y + 12, "→ 改一个类型标注，六处跟着动", 10.5, bold=True, fill=BLUE))
    # 三件配套
    b.append(hand_rect(560, 60, 460, 260, fill=ORANGE, opacity=0.3))
    b.append(text(790, 86, "三件配套（动态的安全网）", 13, bold=True))
    kits = [("特化 D129", "拿性能：fmul 2→18"), ("回退 D130", "兜正确：四级降级链"),
            ("池化 D131", "管内存：99% 复用")]
    y = 112
    for k, v in kits:
        b.append(hand_rect(590, y, 400, 50, fill=BG, opacity=0.9))
        b.append(text(620, y + 20, k, 11, bold=True, anchor="start"))
        b.append(text(620, y + 38, v, 10, anchor="start", fill=MUTED))
        y += 60
    b.append(text(790, y + 8, "缺一件：性能/正确性/内存三缺一", 10.5, bold=True, fill=ORANGE))
    # 底部标准回答
    b.append(hand_rect(60, 340, 960, 120, fill="#F5E9C8", opacity=0.8))
    b.append(text(W/2, 366, "「为什么动态 Shape 不只是把常量改成变量」——第 19 周的标准回答", 12.5, bold=True))
    b.append(text(W/2, 392, "不是一格翻转——是一串涟漪（签名/读回/分配/边界/验证/性能语义六处联动），", 11))
    b.append(text(W/2, 414, "且每格翻转要配平三件事（特化拿性能＋回退兜正确＋池管内存）——", 11))
    b.append(text(W/2, 436, "动态化的完整成本是「整个 Runtime 层」，不是改个类型标注。", 11.5, bold=True, fill="#4a7c59"))
    # 数字带
    b.append(text(W/2, 496, "一周的数字战报", 14, bold=True))
    stats = [("40 项", "判定全绿"), ("fmul 2→18", "特化收益 9 倍"),
             ("99%", "池化复用率"), ("0.01ms", "launch 开销"), ("1.4×", "双 stream 并行")]
    for i, (num, label) in enumerate(stats):
        x = 100 + i * 180
        b.append(hand_rect(x, 516, 160, 70, fill=GREEN, opacity=0.4))
        b.append(text(x + 80, 542, num, 15, bold=True))
        b.append(text(x + 80, 564, label, 10, MUTED))
    save("02-ledger.svg", "".join(b), h=610)

def fig3():
    b = []
    b.append(text(W/2, 34, "第 20 周预告：测试、调试与回归体系", 16, bold=True))
    week20 = [
        ("D134", "IR/Pass 测试整理", "单元/IR 文本/端到端三层职责；\nVerifier/Shape/融合/Layout/Lowering 正反例"),
        ("D135", "随机 Shape 正确性", "随机 M/N/K/Tile；先正确再性能；\n固定种子＋失败用例保存"),
        ("D136", "Pass 二分定位", "逐个关 Pass 的调试流；\n对注入错误定位（D123 改写记录的地基）"),
        ("D137", "最小失败用例", "Reduce：删无关节点/缩 shape/简化类型；\n复杂失败→最小复现"),
        ("D138", "性能回归测试", "固定基准 shape＋中位数/波动范围；\n合理报警阈值"),
        ("D139", "完整回归＋冻结", "正确性/编译时间/性能/文档联合验收；\n第五阶段版本冻结"),
        ("D140", "第 20 周复盘", "调试核心＝定位最早语义破坏点；\n脱稿演示失败→Dump→关 Pass→复现→修复"),
    ]
    for i, (d, name, desc) in enumerate(week20):
        y = 60 + i * 88
        color = PURPLE if d == "D140" else GREEN
        b.append(hand_rect(60, y, 960, 76, fill=color, opacity=0.3))
        b.append(text(110, y + 26, d, 13, bold=True))
        b.append(text(110, y + 50, name, 10.5))
        for j, line in enumerate(desc.split("\n")):
            b.append(text(350, y + 24 + j*20, line, 10, anchor="start"))
    b.append(hand_rect(60, 60 + 7*88 + 4, 960, 44, fill="#F5E9C8", opacity=0.8))
    b.append(text(W/2, 60 + 7*88 + 30, "第 19~20 周的关系：本周建了「能力」（Runtime 三件套），下周建「信心」（质量地基）——", 11.5, bold=True))
    save("03-week20.svg", "".join(b), h=60 + 7*88 + 60)

if __name__ == "__main__":
    fig1()
    fig2()
    fig3()
