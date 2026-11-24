#!/usr/bin/env python3
"""第 130 天（通用实现回退）3 张 SVG。种子 130。"""
from __future__ import annotations
import math, os, random
import xml.sax.saxutils as su

random.seed(130)
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
    b.append(text(W/2, 34, "回退的完整故事：从「查表分发」到「四级降级链」", 16, bold=True))
    # 主链
    b.append(hand_rect(60, 60, 220, 60, fill=GREEN, opacity=0.5))
    b.append(text(170, 86, "① shape 校验", 12, bold=True))
    b.append(text(170, 106, "E301 fail-fast", 10, fill=RED))
    b.append(arrow(284, 90, 340, 90, sw=1.8))
    b.append(hand_rect(342, 60, 220, 60, fill=GREEN, opacity=0.5))
    b.append(text(452, 86, "② 特化命中？", 12, bold=True))
    b.append(text(452, 106, "hit → 特化 kernel", 10))
    b.append(arrow(566, 90, 622, 90, sw=1.8, label="miss"))
    b.append(arrow(452, 122, 452, 168, stroke=RED, sw=1.6, label="异常"))
    b.append(hand_rect(624, 60, 220, 60, fill=BLUE, opacity=0.5))
    b.append(text(734, 86, "③ 动态兜底", 12, bold=True))
    b.append(text(734, 106, "E302 回退/W301 警告", 10))
    b.append(arrow(734, 122, 734, 168, stroke=RED, sw=1.6, label="失败"))
    b.append(hand_rect(870, 60, 150, 60, fill=RED, opacity=0.6))
    b.append(text(945, 86, "④ 上抛", 12, bold=True))
    b.append(text(945, 106, "E303", 10))
    # 各级详细
    details = [
        ("E301 校验拒收", "内维不匹配 5≠6\ndtype float64≠f32\n3D 输入 (2,4,6)\n零维 (0,6)@(6,3)", "四种非法输入\n全部 fail-fast\n（E2 实测×4）", GREEN),
        ("特化执行", "命中（4,6,3）\n正常 → 返回结果", "特化层正常路径\n（D129 行为保持）", GREEN),
        ("E302/W301 回退", "特化 kernel 崩溃\n→ 动态版重试\n→ 结果正确＋警告", "E3 实测：\n注入坏 kernel\n回退成功 PASS", ORANGE),
        ("E303 上抛", "动态版也失败\n→ RtError(E303)\n→ 调用方处理", "E4 实测：\n两层全崩\n结构化上抛 ✓", RED),
    ]
    for i, (title, body, note, color) in enumerate(details):
        x = 60 + i * 245
        b.append(hand_rect(x, 190, 225, 150, fill=color, opacity=0.35))
        b.append(text(x + 112, 214, title, 11.5, bold=True))
        for j, line in enumerate(body.split("\n")):
            b.append(text(x + 112, 236 + j*17, line, 9.5))
        b.append(text(x + 112, 316, note.split("\n")[0], 9, fill=MUTED))
        b.append(text(x + 112, 330, note.split("\n")[1] if len(note.split("\n"))>1 else "", 9, fill=MUTED))
    # 底部
    b.append(hand_rect(60, 366, 960, 76, fill="#F5E9C8", opacity=0.8))
    b.append(text(W/2, 390, "四级降级链的语义：每一级失败降一级——校验拦得住的不进 kernel、特化崩了有动态、", 11.5, bold=True))
    b.append(text(W/2, 412, "动态也崩才上抛（且带 E3xx 结构化诊断）——「永远能给出答案或给出结构化错误」，这就是回退的全部合同", 10.5))
    b.append(text(W/2, 452, "三件套齐了：特化（D129）＋缓存（D129 E3）＋回退（今天）＝ PyTorch 2.x 的动态派工程答案", 12, bold=True, fill="#4a7c59"))
    save("01-overview.svg", "".join(b), h=470)

def fig2():
    b = []
    b.append(text(W/2, 34, "E3xx：运行期诊断——D120 诊断体系的第三层", 16, bold=True))
    # 三层诊断
    layers = [
        ("E1xx 用法层", "D120", "参数拼错、文件不存在\n退出码 2：先读 --help", GREEN),
        ("E2xx 编译层", "D122", "Pass 失败、S2 拒收\n退出码 1：改输入或修管道\n＋现场保留（pipeline-error.txt）", BLUE),
        ("E3xx 运行层", "今天", "校验失败（E301）\n回退发生（E302/W301）\n不可恢复（E303）——运行期事件", ORANGE),
    ]
    for i, (name, day, body, color) in enumerate(layers):
        x = 60 + i * 330
        b.append(hand_rect(x, 60, 300, 190, fill=color, opacity=0.35))
        b.append(text(x + 150, 88, name, 13, bold=True))
        b.append(text(x + 150, 108, f"（{day}）", 10, fill=MUTED))
        for j, line in enumerate(body.split("\n")):
            b.append(text(x + 150, 134 + j*18, line, 9.5))
        if i < 2:
            b.append(arrow(x + 302, 150, x + 328, 150, sw=1.6))
    # 对照：运行期 vs 编译期诊断的差异
    b.append(text(W/2, 286, "运行期诊断与编译期诊断的三个差异", 13.5, bold=True))
    diffs = [
        ("触发时机", "编译期：编译时一次性发现｜运行期：每次调用都可能触发"),
        ("处理策略", "编译期：失败退出（E2xx 现场保留）｜运行期：能降级就降级（E302）、不能才上抛（E303）"),
        ("观测方式", "编译期：pipeline-error.txt 落盘｜运行期：events 列表＋stats 计数（可查询的运行轨迹）"),
    ]
    y = 308
    for k, v in diffs:
        b.append(hand_rect(80, y, 920, 44, fill=PURPLE, opacity=0.25))
        b.append(text(110, y + 27, k, 11.5, bold=True, anchor="start"))
        b.append(text(300, y + 27, v, 10, anchor="start"))
        y += 52
    # 底部
    b.append(hand_rect(80, y + 6, 920, 44, fill="#F5E9C8", opacity=0.8))
    b.append(text(W/2, y + 28, "回退的可观测性：events 记录「谁回退了、为什么」；stats 的 fallback 计数是健康指标——", 11, bold=True))
    b.append(text(W/2, y + 46, "fallback 比例升高＝特化层在退化（产物损坏/环境变化）——监控的 hook 从这里接", 10.5))
    save("02-mechanism.svg", "".join(b), h=y + 70)

def fig3():
    b = []
    b.append(text(W/2, 34, "真实系统的回退对照与今天的边界", 16, bold=True))
    # 真实系统
    systems = [
        ("PyTorch 2.x", "torch.compile 失败 →\n回退 eager 解释器\n（graph break 也回退）\nFallbackDetector 计数", GREEN),
        ("TVM", "编译 OOM →\n自动降 tile 重试\n（Ansor 的约束收缩）\n或回退 fallbackschedule", BLUE),
        ("cuDNN", "kernel 不支持该 shape →\n内部算法枚举换一个\n（heuristics 的备选链）\n全不支持才报错", ORANGE),
        ("minic（今天）", "特化崩→动态重试\n动态崩→E303 上抛\n校验拦→E301 拒收\n四级降级链", RED),
    ]
    for i, (name, body, color) in enumerate(systems):
        x = 50 + i * 250
        b.append(hand_rect(x, 60, 230, 170, fill=color, opacity=0.35))
        b.append(text(x + 115, 86, name, 12.5, bold=True))
        for j, line in enumerate(body.split("\n")):
            b.append(text(x + 115, 112 + j*18, line, 9.5))
    # 共性提炼
    b.append(text(W/2, 262, "回退的三个共性（不管哪个系统）", 13.5, bold=True))
    commons = [
        ("① 永远有底", "最底层一定是一个「什么都能跑」的实现（eager/朴素循环/通用算法）——今天的动态版"),
        ("② 降级可见", "回退不是静默的——计数/日志/警告（今天的 W301+stats.fallback）——否则退化无感"),
        ("③ 底也会破", "底失败时要有结构化出口（今天的 E303）——「无声崩溃」是系统的耻辱"),
    ]
    y = 284
    for k, v in commons:
        b.append(hand_rect(80, y, 920, 50, fill="#F5E9C8", opacity=0.7))
        b.append(text(110, y + 20, k, 11.5, bold=True, anchor="start"))
        b.append(text(110, y + 40, v, 10, anchor="start"))
        y += 58
    # 底部：边界
    b.append(hand_rect(80, y + 6, 920, 60, fill=PURPLE, opacity=0.25))
    b.append(text(W/2, y + 30, "今天的边界（诚实声明）：E3 的「坏 kernel」是 Python 层模拟的异常——真实段错误的回退", 11, bold=True))
    b.append(text(W/2, y + 50, "需要信号处理（SIGSEGV catch）或进程隔离（子进程执行）——教学版演示「回退的语义」，工程版差机制", 10.5))
    save("03-example.svg", "".join(b), h=y + 80)

if __name__ == "__main__":
    fig1()
    fig2()
    fig3()
