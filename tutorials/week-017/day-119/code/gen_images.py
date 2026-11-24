#!/usr/bin/env python3
"""生成第 119 天（第 17 周复盘）的 3 张手绘 sketch 风 SVG 技术图。

风格与 D110~D118 一致。所有数字来自本周（D113~D118）outputs/ 的真实
冻结运行（报告日期 2026-11-13/14，跨 aarch64 Linux/LLVM 18 与
macOS arm64/LLVM 23 双环境）。固定随机种子 119，图可复现。
"""

from __future__ import annotations

import math
import os
import random
import xml.sax.saxutils as su

random.seed(119)

BG = "#FDFBF6"
BORDER = "#E7DFCE"
INK = "#3B3B3B"
MUTED = "#6b6257"
ORANGE = "#E8A87C"
BLUE = "#A9C4D4"
GREEN = "#9CBF8E"
RED = "#C97B7B"
PURPLE = "#B8A7CE"
FONT = "'Comic Sans MS','Kaiti SC','KaiTi','STKaiti',cursive"

W, H = 1080, 800
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "images")


def jit(m=1.6):
    return random.uniform(-m, m)


def hand_rect(x, y, w, h, fill=BG, opacity=0.65, stroke=INK, sw=1.4, dash=None):
    pts = [(x + jit(), y + jit()), (x + w + jit(), y + jit()),
           (x + w + jit(), y + h + jit()), (x + jit(), y + h + jit())]
    d = f"M {pts[0][0]:.1f},{pts[0][1]:.1f} "
    for i in range(4):
        a, b = pts[i], pts[(i + 1) % 4]
        mx, my = (a[0] + b[0]) / 2 + jit(2.2), (a[1] + b[1]) / 2 + jit(2.2)
        d += f"Q {mx:.1f},{my:.1f} {b[0]:.1f},{b[1]:.1f} "
    dd = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<path d="{d} Z" stroke="{stroke}" stroke-width="{sw}" '
            f'stroke-linecap="round" stroke-linejoin="round" '
            f'fill="{fill}" fill-opacity="{opacity}"{dd}/>')


def hand_line(x1, y1, x2, y2, stroke=INK, sw=1.4, dash=None):
    dd = f' stroke-dasharray="{dash}"' if dash else ""
    mx, my = (x1 + x2) / 2 + jit(2.5), (y1 + y2) / 2 + jit(2.5)
    d = (f"M {x1 + jit():.1f},{y1 + jit():.1f} Q {mx:.1f},{my:.1f} "
         f"{x2 + jit():.1f},{y2 + jit():.1f}")
    return (f'<path d="{d}" stroke="{stroke}" stroke-width="{sw}" '
            f'stroke-linecap="round" fill="none"{dd}/>')


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
    path = os.path.join(OUT, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(svg_open(w, h) + body + "</svg>\n")
    print("生成", path)


# ════════════════════════════════════════════════════════════
# 图 1：完整 Lowering 图（计划点名的交付物）——七层表示＋信息流向
# ════════════════════════════════════════════════════════════
def fig1():
    b = []
    b.append(text(W/2, 34, "完整 Lowering 图：七层表示，信息只减不增、但每层长新合同", 16, bold=True))

    layers = [
        ("① 图/算子层", "mini.matmul 等", "MatMul+Bias+Relu 语义\nTile/融合/布局决策", GREEN, "D57~D112"),
        ("② 循环层 scf", "scf.for×3＋memref", "21 op｜iter_args 累加链\ni/j/k 循环序", GREEN, "D85~D90/117"),
        ("③ cf 层", "cf.br/cond_br＋块参数", "9 块、3 cond_br\n'循环'变'块＋回跳边'", BLUE, "D117 阶段1"),
        ("④ LLVM Dialect", "llvm.* 纯方言", "94 op（胶水 6→0）\n描述符 5 字段＋malloc", BLUE, "D117 阶段2"),
        ("⑤ LLVM IR .ll", "define/phi/gep", "62 SSA、4 phi\n%名字→编号、常量内联", ORANGE, "D117 阶段3"),
        ("⑥ 优化后 IR", "opt -O2", "step 4块→1块\nfmul 1→18（展开）", ORANGE, "D113/117 对照"),
        ("⑦ 机器码", "aarch64/arm64", "D118 四路线 12/12\nbitwise 全对", RED, "D118"),
    ]
    # 阶梯式布局：每层一张卡片，左→右下降
    cw, chh = 250, 108
    x0, y0, dx, dy = 60, 70, 145, 92
    for i, (name, form, detail, color, day) in enumerate(layers):
        x = x0 + i * dx
        y = y0 + i * dy
        b.append(hand_rect(x, y, cw, chh, fill=color, opacity=0.5))
        b.append(text(x + cw/2, y + 22, name, 13, bold=True))
        b.append(text(x + cw/2, y + 42, form, 10.5, mono=True))
        for j, line in enumerate(detail.split("\n")):
            b.append(text(x + cw/2, y + 62 + j*17, line, 10))
        b.append(text(x + cw/2, y + chh - 6, day, 9.5, MUTED))
        if i < 6:
            b.append(arrow(x + cw - 4, y + chh/2 + 6, x + cw + dx - 12, y + dy + chh/2, sw=1.6))
    # 丢失标注（每条转换边上挂"丢失"标签）
    losses = ["算子语义没了", "'循环'拆散了", "memref→5字段", "名字/常量没了", "结构折叠/展开", "SSA→寄存器"]
    for i, s in enumerate(losses):
        x = x0 + i * dx + cw + 12
        y = y0 + i * dy + chh/2 + 34
        b.append(text(x, y, "✗ " + s, 9.5, RED))
    # 新增标注
    gains = ["领域语义", "显式循环序", "块模型预演", "C ABI 合同", "值域注记", "可运行"]
    for i, s in enumerate(gains):
        x = x0 + i * dx + cw + 12
        y = y0 + i * dy + chh/2 + 50
        b.append(text(x, y, "★ " + s, 9.5, "#4a7c59"))

    # 底部：面试口径
    b.append(hand_rect(60, 712, W - 120, 74, fill="#F5E9C8", opacity=0.75))
    b.append(text(W/2, 734, "面试口径：为什么不能只看最终 LLVM IR 理解整个编译器？", 12.5, bold=True))
    b.append(text(W/2, 754, "① 信息只减不增——Tile/融合/布局的'为什么'在上层被消费；② 新信息有出处——描述符/malloc/sret 是中间层的合同；", 10.5))
    b.append(text(W/2, 772, "③ 优化抹平朴素形态——fmul 1→18 是优化器决定，反向读 IR 分不清作者决策与优化器决策", 10.5))
    save("01-lowering-map.svg", "".join(b), h=800)


# ════════════════════════════════════════════════════════════
# 图 2：信息守恒账本——三个典型案例的逐层追踪
# ════════════════════════════════════════════════════════════
def fig2():
    b = []
    b.append(text(W/2, 34, "信息守恒账本：三个案例，看每层保留什么、丢什么、长什么", 16, bold=True))

    # 三条泳道
    cases = [
        ("案例 A：'这是融合过的 MatMul+Bias'", 
         ["图：bias 融进 MatMul（D78~D81 决策）", "循环：bias 加在 k=0 圈（任务单写死）",
          "LLVM IR：k=0 的 add 看起来与任何 add 无异", "机器码：fmul/fadd 流里找不到'bias'概念"],
         "✗ 最终 IR 只见三层 for＋一个 add；'为什么 bias 在这'永远消失了"),
        ("案例 B：'Tile 32×64 是搜出来的'",
         ["图：D106 候选空间→D111 调优冠军", "循环：边界常量 32/64 内联进 scf.for",
          "LLVM IR：icmp slt i64 %38, 4（数字在、来历没了）", "机器码：subs/cmp 立即数"],
         "✗ 数字活下来了，'搜索'这件事死了——反向读 IR 只能猜'32 是拍的还是算的'"),
        ("案例 C：'malloc 要有人 free'",
         ["图：计划式内存（D105）——没有 alloc 概念", "循环：memref.alloc() 出现",
          "方言：call @malloc＋declare（D117 M3）", "执行：malloc 债务显形（D118 挂账 D131）"],
         "★ 新合同长出来了——运行库符号依赖，这是 Runtime 存在的理由"),
    ]
    lane_h = 190
    for li, (title, steps, verdict) in enumerate(cases):
        y = 64 + li * (lane_h + 18)
        b.append(hand_rect(50, y, W - 100, lane_h, fill=[GREEN, BLUE, ORANGE][li], opacity=0.28))
        b.append(text(70, y + 24, title, 13.5, bold=True, anchor="start"))
        # 四层小卡
        sw_, sh_ = 220, 78
        for si, s in enumerate(steps):
            x = 70 + si * (sw_ + 12)
            b.append(hand_rect(x, y + 38, sw_, sh_, fill=BG, opacity=0.9))
            parts = s.split("：", 1)
            b.append(text(x + sw_/2, y + 58, parts[0], 10.5, bold=True))
            for j, line in enumerate(parts[1].split("（")[0].split("\n")[:2]):
                b.append(text(x + sw_/2, y + 76 + j*15, line[:24], 9.5))
            if si < 3:
                b.append(arrow(x + sw_ + 1, y + 77, x + sw_ + 11, y + 77, sw=1.4))
        b.append(text(W/2, y + lane_h - 12, verdict, 11, fill=RED if verdict.startswith("✗") else "#4a7c59"))
    save("02-information-ledger.svg", "".join(b), h=700)


# ════════════════════════════════════════════════════════════
# 图 3：第 17 周成绩单＋下周路线
# ════════════════════════════════════════════════════════════
def fig3():
    b = []
    b.append(text(W/2, 34, "第 17 周成绩单（D113~D118）与下周路线（D120~D126）", 16, bold=True))

    # 上：六天卡片
    days = [
        ("D113", "LLVM Dialect vs IR", "4块→1块\n11→5 指令", "5步过"),
        ("D114", "设计 Lowering 路径", "10 行清单\n7 条暂不支持", "7/7"),
        ("D115", "函数与类型转换", "56B 契约\n10 组签名", "8/8"),
        ("D116", "elementwise 算子", "21/21·22/22\nGEMM 14/18", "9/9"),
        ("D117", "导出 LLVM IR", "21→18 op\n胶水 6→0", "22/22"),
        ("D118", "JIT/AOT 执行", "四路线×12\n12 PASS", "12/12"),
    ]
    cw, chh, gap = 160, 118, 16
    x0 = (W - (cw*6 + gap*5)) / 2
    for i, (d, title, nums, passed) in enumerate(days):
        x = x0 + i * (cw + gap)
        b.append(hand_rect(x, 58, cw, chh, fill=BLUE, opacity=0.4))
        b.append(text(x + cw/2, 80, d, 14, bold=True))
        b.append(text(x + cw/2, 98, title, 10.5))
        for j, line in enumerate(nums.split("\n")):
            b.append(text(x + cw/2, 116 + j*15, line, 9.5, MUTED))
        b.append(text(x + cw/2, 158, passed + " PASS", 10.5, fill="#4a7c59", bold=True))

    # 中：周账本
    b.append(hand_rect(80, 196, 480, 150, fill="#F5E9C8", opacity=0.7))
    b.append(text(320, 220, "第 17 周总账", 13.5, bold=True))
    lines = [
        "· 六天全部 PASS：8+7+8+9+22+12 = 66 项",
        "· 可执行里程碑：教学仿真（D113~D116）→ 真工具（D117）→ 真执行（D118）",
        "· 双环境验证：aarch64 Linux/LLVM 18 ↔ macOS arm64/LLVM 23",
        "   （跨版本 census：94↔97 op，胶水均 0，undef→poison 改名）",
        "· 跨天账本：残账 C1×4（D115 挂）→ D117 清；胶水 8→6→0 全程可追",
    ]
    for j, s in enumerate(lines):
        b.append(text(100, 244 + j*20, s, 10.5, anchor="start"))

    b.append(hand_rect(580, 196, 420, 150, fill=PURPLE, opacity=0.35))
    b.append(text(790, 220, "仍然讲不清楚的（下周练）", 13.5, bold=True))
    lines2 = [
        "· Conversion 失败时诊断如何保留（D122 的主题）",
        "· 优化开关的组合爆炸怎么管（D121 分开关）",
        "· IR Dump 的粒度：全存 vs 按需（D123）",
        "· 融合算子映射到循环的通用法则（D124）",
    ]
    for j, s in enumerate(lines2):
        b.append(text(600, 244 + j*20, s, 10.5, anchor="start"))

    # 下：下周路线（第 18 周：统一端到端编译入口）
    b.append(text(W/2, 380, "下周（第 18 周）：统一端到端编译入口——把 17 周的零件装进一个 `minic` 命令", 13.5, bold=True))
    week18 = [
        ("D120", "CLI 设计", "输入/输出/开关/\n诊断/退出码"),
        ("D121", "图优化 Pass", "Shape/简化/融合\n分别可开关"),
        ("D122", "循环+LLVM", "接入 MatMul 管道\n失败诊断"),
        ("D123", "IR Dump", "阶段序列文件\n可观测性"),
        ("D124", "端到端", "MatMul+Bias+Relu\nvs numpy"),
        ("D125", "对照实验", "无优化→全开\n四组收益表"),
        ("D126", "复盘", "干净目录重建\n可复现说明"),
    ]
    cw2, ch2, gap2 = 138, 100, 14
    x0 = (W - (cw2*7 + gap2*6)) / 2
    for i, (d, title, desc) in enumerate(week18):
        x = x0 + i * (cw2 + gap2)
        b.append(hand_rect(x, 402, cw2, ch2, fill=ORANGE, opacity=0.45))
        b.append(text(x + cw2/2, 424, d, 12.5, bold=True))
        b.append(text(x + cw2/2, 442, title, 10.5))
        for j, line in enumerate(desc.split("\n")):
            b.append(text(x + cw2/2, 460 + j*15, line, 9.5))
        if i < 6:
            b.append(arrow(x + cw2 + 1, 452, x + cw2 + gap2 - 1, 452, sw=1.4))

    # 底部：下周唯一核心目标
    b.append(hand_rect(80, 530, W - 160, 60, fill=GREEN, opacity=0.4))
    b.append(text(W/2, 552, "下周唯一核心目标：`./minic input.mini -O2 -o out/` 一条命令从图 IR 跑到可执行，", 12, bold=True))
    b.append(text(W/2, 574, "每个阶段有 IR Dump、每个失败有诊断、四个优化开关有对照数据——「统一入口」是第 19~20 周 Runtime 与回归的地基", 10.5, MUTED))
    save("03-week-report.svg", "".join(b), h=620)


if __name__ == "__main__":
    fig1()
    fig2()
    fig3()
