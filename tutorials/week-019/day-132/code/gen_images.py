#!/usr/bin/env python3
"""第 132 天（异步与同步模型）3 张 SVG。种子 132。"""
from __future__ import annotations
import math, os, random
import xml.sax.saxutils as su

random.seed(132)
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
    b.append(text(W/2, 34, "从同步到异步：调用方的时间线变化", 16, bold=True))
    # 三种模式的时间线
    modes = [
        ("同步（CPU 现状）", [("k1 执行 30ms", 0, 30, GREEN), ("k2 执行 30ms", 30, 60, GREEN)],
         "调用方阻塞 60ms", RED),
        ("异步单 stream", [("launch 0.01ms", 0, 1, ORANGE), ("k1 排队+执行", 1, 31, BLUE), ("k2 排队+执行", 31, 61, BLUE)],
         "launch 0.02ms＋自由 60ms（stream 内串行）", ORANGE),
        ("异步双 stream", [("launch×2 0.02ms", 0, 1, ORANGE), ("k1 @s0", 1, 31, BLUE), ("k2 @s1 并行", 1, 31, GREEN)],
         "总 42ms（1.4×——真并行）", GREEN),
    ]
    for mi, (name, bars, verdict, color) in enumerate(modes):
        y0 = 60 + mi * 170
        b.append(hand_rect(60, y0, 960, 150, fill=color, opacity=0.15))
        b.append(text(110, y0 + 24, name, 12.5, bold=True, anchor="start"))
        # 时间轴
        tx, tw = 200, 700
        b.append(arrow(tx, y0 + 40, tx + tw, y0 + 40, sw=1.2))
        for label, start, end, c in bars:
            x = tx + start / 65 * tw
            w = max((end - start) / 65 * tw, 8)
            b.append(hand_rect(x, y0 + 50, w, 34, fill=c, opacity=0.55))
            b.append(text(x + w/2, y0 + 71, label, 8.5))
        b.append(text(540, y0 + 118, verdict, 11.5, bold=True, fill=color))
    # 底部
    b.append(hand_rect(60, 580, 960, 60, fill="#F5E9C8", opacity=0.8))
    b.append(text(W/2, 604, "异步的全部收益：调用方从「等 60ms」变「等 0.02ms＋自由时间」——", 11.5, bold=True))
    b.append(text(W/2, 626, "自由时间可以准备下一批输入、launch 更多 kernel、或干脆省电；同步点从「每次调用」减到「真正需要结果时」", 10.5))
    save("01-overview.svg", "".join(b), h=660)

def fig2():
    b = []
    b.append(text(W/2, 34, "Stream/Event 的语义：队列、顺序执行、完成通知", 16, bold=True))
    # Stream 结构
    b.append(hand_rect(60, 60, 460, 300, fill=BLUE, opacity=0.3))
    b.append(text(290, 86, "Stream（命令队列）", 13, bold=True))
    items = [
        "launch(kernel, args, event)",
        "  → 入队（0.01ms）立即返回",
        "  → 调用方继续跑",
        "",
        "工作线程（GPU 的执行单元）：",
        "  按提交顺序逐个执行",
        "  （同 stream 保序——顺序语义）",
        "",
        "kernel 完成 → event.set()",
        "  → 等这个 event 的各方被唤醒",
    ]
    y = 112
    for line in items:
        if line:
            b.append(text(90, y, line, 10.5, mono=("launch" in line or "event" in line),
                          anchor="start"))
        y += 22
    # Event 状态机
    b.append(hand_rect(560, 60, 460, 300, fill=ORANGE, opacity=0.3))
    b.append(text(790, 86, "Event（完成通知）", 13, bold=True))
    b.append(hand_rect(600, 106, 180, 44, fill=BG, opacity=0.9))
    b.append(text(690, 132, "未置位", 11, bold=True))
    b.append(arrow(784, 128, 836, 128, sw=2, label="set()"))
    b.append(hand_rect(840, 106, 160, 44, fill=GREEN, opacity=0.5))
    b.append(text(920, 132, "已置位", 11, bold=True))
    b.append(text(790, 180, "wait()：阻塞到置位（同步点）", 10.5))
    b.append(text(790, 200, "is_set：轮询（非阻塞查询）", 10.5))
    b.append(text(790, 232, "谁 set：kernel 完成时（工作线程）", 10))
    b.append(text(790, 252, "谁 wait：需要结果的调用方/下游 kernel", 10))
    b.append(hand_rect(600, 280, 380, 60, fill="#F5E9C8", opacity=0.8))
    b.append(text(790, 302, "CUDA 对照：cuEventRecord/cuEventSynchronize", 10))
    b.append(text(790, 322, "cuStreamSynchronize＝等整条队列清空", 10))
    # 底部：映射表
    b.append(text(W/2, 396, "CPU 语义 → 异步设备 的概念映射", 13.5, bold=True))
    maps = [
        ("函数调用", "Launch（提交到队列，不执行）"),
        ("返回值", "Event（完成通知——要主动等）"),
        ("调用返回＝结果就绪", "分离：launch 返回≠结果就绪"),
        ("内存池归还（D131）", "必须挂 event（等读方完成再 release）"),
        ("隐式同步（D127）", "显式化：每个需要结果的点都是同步点"),
    ]
    y = 418
    for k, v in maps:
        b.append(hand_rect(80, y, 920, 36, fill=PURPLE, opacity=0.22))
        b.append(text(300, y + 24, k, 11, bold=True))
        b.append(text(700, y + 24, v, 10.5, fill=MUTED))
        y += 42
    save("02-mechanism.svg", "".join(b), h=y + 20)

def fig3():
    b = []
    b.append(text(W/2, 34, "三个场景的依赖与同步点标注（E3 分析）", 16, bold=True))
    # 场景 A
    b.append(hand_rect(60, 60, 960, 120, fill=GREEN, opacity=0.3))
    b.append(text(110, 86, "场景 A：minic 现状（融合后）", 12.5, bold=True, anchor="start"))
    b.append(text(540, 112, "fused_kernel [launch] → event → 调用方读结果", 11, mono=True))
    b.append(text(540, 136, "同步点：1 个——融合把三个算子打进一个 kernel，无中间依赖（D121 的收益在异步世界重现）", 10, fill="#4a7c59"))
    # 场景 B
    b.append(hand_rect(60, 196, 960, 140, fill=BLUE, opacity=0.25))
    b.append(text(110, 222, "场景 B：假想未融合链", 12.5, bold=True, anchor="start"))
    b.append(text(540, 248, "matmul [launch] → bias [launch] → relu [launch] → event", 11, mono=True))
    b.append(text(540, 272, "同 stream：自动按序（顺序执行语义）——无需中间 event", 10.5))
    b.append(text(540, 294, "跨 stream：必须 event——bias_stream 先 wait matmul_event", 10.5, fill=RED))
    b.append(text(540, 318, "依赖是静态的（编译期已知）→ Compiler 排拓扑序；同步是动态的 → Runtime 建 event", 10, fill=MUTED))
    # 场景 C
    b.append(hand_rect(60, 352, 960, 130, fill=RED, opacity=0.25))
    b.append(text(110, 378, "场景 C：池化内存×异步（D131 的伏笔）", 12.5, bold=True, anchor="start"))
    b.append(text(540, 404, "release(buf) 必须等读 buf 的最后一个 kernel 完成！", 11, bold=True, fill=RED))
    b.append(text(540, 428, "同步世界：调用方读完后 release——顺序天然保证", 10.5))
    b.append(text(540, 450, "异步世界：kernel 还在跑、调用方已 release——下一个 acquire 拿到正在被写的 buf！数据竞争", 10.5))
    b.append(text(540, 472, "解法：release 挂 event（最后一次使用完成才归还）——PyTorch CUDACachingAllocator 的 record_stream 同思路", 10, fill="#4a7c59"))
    # 底部分工
    b.append(hand_rect(60, 498, 960, 110, fill="#F5E9C8", opacity=0.8))
    b.append(text(W/2, 522, "Compiler/Runtime 分工（异步版·计划条目产出）", 12.5, bold=True))
    b.append(text(W/2, 548, "Compiler：算子依赖图（静态）→ launch 拓扑序＋内存规划（谁的生命周期跨几个 kernel）", 10.5))
    b.append(text(W/2, 570, "Runtime：stream 分配策略、event 创建/等待、内存生命周期管理（event 触发 release）", 10.5))
    b.append(text(W/2, 592, "调用方：最终同步（wait 最后的 event）＋读结果——三层各管一段，同步点显式化", 10.5))
    save("03-example.svg", "".join(b), h=620)

if __name__ == "__main__":
    fig1()
    fig2()
    fig3()
