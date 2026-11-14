#!/usr/bin/env python3
"""第 155 天 3 张 SVG。种子 155。"""
from __future__ import annotations
import math, os, random
import xml.sax.saxutils as su
random.seed(155)
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
def arrow(x1, y1, x2, y2, stroke=INK, sw=1.8, label=None):
    import math as m
    mx, my = (x1+x2)/2 + jit(2), (y1+y2)/2 + jit(2)
    ang = m.atan2(y2-y1, x2-x1)
    hx, hy = x2-9*m.cos(ang), y2-9*m.sin(ang)
    a1 = (hx+5*m.cos(ang+2.7), hy+5*m.sin(ang+2.7))
    a2 = (hx+5*m.cos(ang-2.7), hy+5*m.sin(ang-2.7))
    d = (f"M {x1+jit():.1f},{y1+jit():.1f} Q {mx:.1f},{my:.1f} "
         f"{x2:.1f},{y2:.1f} M {a1[0]:.1f},{a1[1]:.1f} L {x2:.1f},{y2:.1f} L {a2[0]:.1f},{a2[1]:.1f}")
    out = (f'<path d="{d}" stroke="{stroke}" stroke-width="{sw}" '
           f'stroke-linecap="round" fill="none"/>')
    if label:
        out += text((x1+x2)/2, (y1+y2)/2-8, label, 10.5, MUTED)
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
    b.append(text(W/2, 34, "minic 总架构：六层数据流（一条主链）", 16, bold=True))
    layers = [
        ("mini 图 IR", ".graph 文本\n11 节点", GREEN),
        ("S1 图优化", "五道闸→5 节点\n（fused）", GREEN),
        ("S2 循环生成", "scf.for＋memref\n朴素/块循环", BLUE),
        ("S4 LLVM Lower", "七 pass\n胶水 0", ORANGE),
        ("S5 代码生成", "translate→.ll\nllc→.s→.so", RED),
        ("S6 验证", "AOT 执行\n12/12 bitwise", PURPLE),
    ]
    for i, (name, body, color) in enumerate(layers):
        x = 40 + i * 170
        b.append(hand_rect(x, 70, 155, 110, fill=color, opacity=0.4))
        b.append(text(x + 77, 96, name, 11.5, bold=True))
        for j, line in enumerate(body.split("\n")):
            b.append(text(x + 77, 120 + j*18, line, 9.5))
        if i < 5:
            b.append(arrow(x + 157, 125, x + 168, 125, sw=1.5))
    # 运行时
    b.append(hand_rect(140, 210, 800, 80, fill=BLUE, opacity=0.25))
    b.append(text(W/2, 240, "运行时层（S6 之后）", 12.5, bold=True))
    b.append(text(W/2, 264, "调用方 → BufferPool.acquire → Dispatcher.run →（命中）特化 kernel｜（miss/异常）动态兜底 → 结果", 10.5))
    # 底部
    b.append(hand_rect(60, 310, 960, 70, fill="#F5E9C8", opacity=0.85))
    b.append(text(W/2, 336, "架构图的表达原则：职责与数据流——不是文件名堆叠", 12, bold=True))
    b.append(text(W/2, 358, "每层一格写「这层做什么＋产出什么」；箭头是数据不是调用——读者顺着箭头能讲出数据的完整旅程", 10.5))
    save("01-arch.svg", "".join(b), h=400)

def fig2():
    b = []
    b.append(text(W/2, 34, "模块职责表（10 个模块×关键决策）", 16, bold=True))
    mods = [
        ("graph_passes", "S1 五闸", "顺序合同＋不动点", "D121"),
        ("gen_loop_ir_full", "S2 朴素", "bias 融 k=0＋k 序", "D124"),
        ("gen_block_v2", "S2 块循环", "tile 参数化＋校验", "D143~46"),
        ("run_s45", "S4/S5 管道", "逐条 pass（指认到条）", "D122"),
        ("observability", "可观测层", "四级 dump＋改写记录", "D123"),
        ("minic.py", "CLI 入口", "四份合同", "D120"),
        ("specialize", "特化分发", "(shape,tile) key 两层", "D129"),
        ("fallback", "回退链", "E301/302/303 降级", "D130"),
        ("allocator", "缓冲池", "档位＋99% 复用", "D131"),
        ("async_model", "异步仿真", "Stream/Event 映射", "D132"),
    ]
    for i, (mod, role, decision, day) in enumerate(mods):
        x = 60 + (i % 2) * 480
        y = 60 + (i // 2) * 72
        b.append(hand_rect(x, y, 450, 62, fill=BLUE, opacity=0.25))
        b.append(text(x + 225, y + 20, f"{mod}（{role}）", 10.5, bold=True, mono=True))
        b.append(text(x + 225, y + 40, f"关键决策：{decision}｜{day}", 9.5))
    b.append(hand_rect(60, 440, 960, 56, fill="#F5E9C8", opacity=0.85))
    b.append(text(W/2, 464, "职责表的读法：每个模块一行「它做什么＋它最重要的一个决策＋出处」", 11.5, bold=True))
    b.append(text(W/2, 484, "「关键决策」是模块存在的理由——删掉它系统少了什么，一行说清", 10.5))
    save("02-modules.svg", "".join(b), h=510)

def fig3():
    b = []
    b.append(text(W/2, 34, "三份合同：架构的接口层", 16, bold=True))
    contracts = [
        ("C 合同", "_mlir_ciface(out, a, b, bias)\n56B 描述符×N＋sret 语义\n（D115 定→D116 手写→D117 真工具）", GREEN),
        ("manifest 合同", "version/input/tile/stages/exit_code\n机器可读的编译回执\n（D120 定→D125 消费）", BLUE),
        ("诊断合同", "E1xx 用法/E2xx 编译/E3xx 运行时\n＋W1xx 警告——四层全覆盖\n（D120→D122→D130）", ORANGE),
    ]
    for i, (name, body, color) in enumerate(contracts):
        x = 60 + i * 330
        b.append(hand_rect(x, 60, 300, 180, fill=color, opacity=0.32))
        b.append(text(x + 150, 88, name, 13, bold=True))
        for j, line in enumerate(body.split("\n")):
            b.append(text(x + 150, 114 + j*22, line, 10))
    # 底部
    b.append(hand_rect(60, 260, 960, 80, fill="#F5E9C8", opacity=0.85))
    b.append(text(W/2, 286, "合同是架构的「宪法」——模块可以重写、合同不能轻易动", 12, bold=True))
    b.append(text(W/2, 310, "22 周里模块改了无数次（朴素→块循环/单层→分发/裸 malloc→池），三份合同从未破坏——", 10.5))
    b.append(text(W/2, 332, "这是「合同先行」（D120 第一课）的回报：接口稳定让内部演化无牵连", 10.5))
    save("03-contracts.svg", "".join(b), h=360)

if __name__ == "__main__":
    fig1()
    fig2()
    fig3()
