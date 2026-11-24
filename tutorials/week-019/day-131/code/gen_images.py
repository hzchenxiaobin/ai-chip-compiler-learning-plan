#!/usr/bin/env python3
"""第 131 天（内存分配与复用）3 张 SVG。种子 131。"""
from __future__ import annotations
import math, os, random
import xml.sax.saxutils as su

random.seed(131)
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
    b.append(text(W/2, 34, "malloc 债务结清：从裸分配到池化复用", 16, bold=True))
    # 左：裸 malloc 模式
    b.append(hand_rect(60, 60, 440, 300, fill=RED, opacity=0.3))
    b.append(text(280, 86, "裸 malloc 模式（D118 遗留）", 13, bold=True))
    lines = [
        "每次调用：",
        "  kernel 内 malloc(48) → 输出缓冲区",
        "  调用结束：没人 free！",
        "",
        "E1 实测（2000 次调用）：",
        "  理论泄漏 94KB（RSS Δ=160KB 含噪声）",
        "  C 堆只涨不跌——机制性泄漏",
        "",
        "真实服务换算：",
        "  100 万次/秒 × 48B = 48 MB/s",
        "  一小时 = 165 GB —— 服务必死",
    ]
    y = 112
    for line in lines:
        if line:
            b.append(text(90, y, line, 10.5, mono=("malloc" in line or "48" in line),
                          anchor="start", fill=RED if "死" in line or "泄漏" in line else INK))
        y += 22
    # 右：池化模式
    b.append(hand_rect(560, 60, 440, 300, fill=GREEN, opacity=0.35))
    b.append(text(780, 86, "池化模式（今天实现）", 13, bold=True))
    lines2 = [
        "BufferPool（档位＋空闲链表）：",
        "  acquire(shape) → 池里有就复用",
        "  release(buf)  → 放回池（不 free）",
        "",
        "E2 实测（100 次 acquire/release）：",
        "  hit=99 miss=1 —— 只首次分配",
        "  分配量 48B vs 裸模式 4800B（100×）",
        "",
        "生命周期三层：",
        "  分配=Pool｜归还=调用方｜释放=destroy",
        "  （D127 审计「释放=NONE」的空格填上）",
    ]
    y = 112
    for line in lines2:
        if line:
            b.append(text(590, y, line, 10.5, mono=("acquire" in line or "release" in line or "hit" in line),
                          anchor="start", fill="#4a7c59" if "100" in line or "填上" in line else INK))
        y += 22
    # 中间箭头
    b.append(arrow(504, 210, 556, 210, sw=2.4, label="结清"))
    # 底部
    b.append(hand_rect(60, 380, 960, 80, fill="#F5E9C8", opacity=0.8))
    b.append(text(W/2, 404, "债的本质：kernel 的输出语义是「返回新分配的 memref」（D115 的 sret 合同）——", 11.5, bold=True))
    b.append(text(W/2, 426, "教学版从调用方侧结清（池预分配输出缓冲区）；工程版改 kernel 签名（out 参数化——D124 任务单形态）——两条路都通向「分配次数与调用次数解耦」", 10.5))
    save("01-overview.svg", "".join(b), h=480)

def fig2():
    b = []
    b.append(text(W/2, 34, "BufferPool 的机制：档位分桶＋空闲链表＋视图复用", 16, bold=True))
    # 池结构
    b.append(hand_rect(60, 60, 420, 340, fill=BLUE, opacity=0.3))
    b.append(text(270, 86, "池结构（bucket_bytes=(48,192,1024))", 12.5, bold=True))
    buckets = [
        ("48B 档", "[buf48_1, buf48_2, ...]", "(4,3) 输出用"),
        ("192B 档", "[buf192_1]", "(8,8) 输出用"),
        ("1024B 档", "[buf1024_1]", "(16,16) 输出用"),
    ]
    y = 112
    for name, content, note in buckets:
        b.append(hand_rect(80, y, 380, 60, fill=BG, opacity=0.9))
        b.append(text(100, y + 22, name, 11, bold=True, anchor="start"))
        b.append(text(100, y + 42, content, 9.5, mono=True, anchor="start"))
        b.append(text(340, y + 22, note, 9.5, anchor="start", fill=MUTED))
        y += 70
    # 流程
    b.append(text(270, y + 12, "acquire(4,3)：查 48B 档→命中弹出一个", 10.5))
    b.append(text(270, y + 32, "release(buf)：放回对应档（不 free）", 10.5))
    # 右：流程图
    b.append(hand_rect(520, 60, 480, 340, fill=BG, opacity=0.9, sw=1.8))
    b.append(text(760, 86, "acquire/release 时序（100 次实测）", 12.5, bold=True))
    steps = [
        ("#1 acquire(4,3)", "miss → numpy 分配 48B", "alloc_bytes=48", RED),
        ("#2 acquire(4,3)", "hit → 池弹出 buf48_1", "分配 0 B", GREEN),
        ("#3 release(buf)", "放回 48B 档", "池常驻 48B", BLUE),
        ("#4 acquire(4,3)", "hit（又是它）", "分配 0 B", GREEN),
        ("...", "×97 次同样", "总分配 48B", MUTED),
        ("#100 release", "放回池", "destroy 前常驻", BLUE),
    ]
    y = 108
    for step, action, result, color in steps:
        b.append(hand_rect(540, y, 440, 36, fill=color, opacity=0.25))
        b.append(text(560, y + 24, step, 9.5, mono=True, anchor="start"))
        b.append(text(700, y + 24, action, 9.5, anchor="start"))
        b.append(text(900, y + 24, result, 9, anchor="start", fill=MUTED))
        y += 42
    # 底部
    b.append(hand_rect(60, 420, 940, 60, fill="#F5E9C8", opacity=0.8))
    b.append(text(W/2, 444, "复用的关键：档位让「同尺寸的需求」命中同一批缓冲区——", 11.5, bold=True))
    b.append(text(W/2, 466, "100 次调用只碰 1 次 numpy 分配器（malloc 调用次数与推理次数解耦）——D100 片外工作区的运行时版", 10.5))
    save("02-mechanism.svg", "".join(b), h=500)

def fig3():
    b = []
    b.append(text(W/2, 34, "生命周期三层＋真实系统的分配器对照", 16, bold=True))
    # 三层
    layers = [
        ("分配（acquire）", "Pool：miss 时 numpy 分配", "运行时", GREEN),
        ("归还（release）", "调用方：用完放回（不 free）", "调用方", BLUE),
        ("释放（destroy）", "池：清空＋Python GC 兜底", "池", ORANGE),
    ]
    for i, (name, body, who, color) in enumerate(layers):
        x = 60 + i * 330
        b.append(hand_rect(x, 60, 300, 100, fill=color, opacity=0.35))
        b.append(text(x + 150, 86, name, 12.5, bold=True))
        b.append(text(x + 150, 108, body, 10))
        b.append(text(x + 150, 130, f"职责方：{who}", 9.5, fill=MUTED))
    # 真实系统
    b.append(text(W/2, 200, "真实系统的分配器对照", 13.5, bold=True))
    systems = [
        ("TVM", "TVMArray 从调用方来\n（WorkspacePool 已在图编译期规划）", "D100 的片外工作区就是它"),
        ("PyTorch", "CUDACachingAllocator\n块缓存＋按尺寸分桶＋溢出释放", "与今天 BufferPool 同构！"),
        ("CUDA", "cudaMallocAsync\n流序分配（D132 同步的前置）", "pool=stream 语义"),
        ("minic", "BufferPool 教学版\n档位＋空闲链表＋视图复用", "99% hit / 100 倍分配量差"),
    ]
    for i, (name, body, note) in enumerate(systems):
        x = 50 + i * 250
        b.append(hand_rect(x, 220, 230, 150, fill=PURPLE, opacity=0.3))
        b.append(text(x + 115, 246, name, 12.5, bold=True))
        for j, line in enumerate(body.split("\n")):
            b.append(text(x + 115, 270 + j*17, line, 9.5))
        b.append(text(x + 115, 340, note, 8.8, fill=MUTED))
    # 底部
    b.append(hand_rect(50, 392, 980, 70, fill="#F5E9C8", opacity=0.8))
    b.append(text(W/2, 416, "分配器设计的两难（今天的取舍）：池越大复用率越高、但常驻内存越大——", 11.5, bold=True))
    b.append(text(W/2, 438, "档位分桶是折中（按需增长、按桶复用）；真实系统再加 LRU 淘汰与水位线（PyTorch 的 empty_cache）", 10.5))
    save("03-example.svg", "".join(b), h=480)

if __name__ == "__main__":
    fig1()
    fig2()
    fig3()
