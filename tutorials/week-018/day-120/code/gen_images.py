#!/usr/bin/env python3
"""生成第 120 天（minic CLI 设计）的 3 张手绘 sketch 风 SVG 图。

风格与 D110~D119 一致。数字来自 outputs/report.txt 真实合同测试
（2026-11-14，macOS arm64，Python 3.9.6）。固定随机种子 120。
"""
from __future__ import annotations

import math
import os
import random
import xml.sax.saxutils as su

random.seed(120)

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

W, H = 1080, 760
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


# ── 图 1：overview——minic 在第 18 周的位置与六阶段管道 ──
def fig1():
    b = []
    b.append(text(W/2, 34, "minic：统一端到端编译入口——把第 17 周的七层零件装进一条命令", 16, bold=True))

    # 上：从第 17 周零件到 minic
    parts = [("图优化 Pass\nD57~D84", GREEN), ("循环生成\nD85~D90", GREEN),
             ("Tiling\nD91~D97", GREEN), ("Lowering 管道\nD114~D117", BLUE),
             ("执行验证\nD118", BLUE)]
    pw, ph, pgap = 178, 72, 22
    px0 = (W - (pw*5 + pgap*4)) / 2
    for i, (label, color) in enumerate(parts):
        x = px0 + i * (pw + pgap)
        b.append(hand_rect(x, 58, pw, ph, fill=color, opacity=0.5))
        b.append(text(x + pw/2, 84, label.split("\n")[0], 12, bold=True))
        b.append(text(x + pw/2, 104, label.split("\n")[1], 10, MUTED))
    b.append(hand_rect(px0, 150, pw*5 + pgap*4, 56, fill=ORANGE, opacity=0.7, sw=2))
    b.append(text(W/2, 174, "minic input.mlir -O2 --tile 32,32,32 -o out/   ← 第 18 周逐日长成", 13, bold=True))
    b.append(text(W/2, 194, "D120 CLI 骨架（今天）→ D121 图优化 → D122 循环+LLVM → D123 dump → D124 端到端 → D125 对照实验", 10.5, MUTED))

    # 中：六阶段管道
    b.append(text(W/2, 240, "六阶段管道（S0 读入＋S1~S6；今天是骨架，排期已定）", 14, bold=True))
    stages = [
        ("S0", "读入", "38 行 30 op\n预检+计数", GREEN),
        ("S1", "图优化", "shape/简化/融合\n-O0 跳过", BLUE),
        ("S2", "循环生成", "mini.matmul\n→scf.for", BLUE),
        ("S3", "Tiling", "tile→边界常量\nmin 钳制", BLUE),
        ("S4", "LLVM Lower", "七 pass 管道\nD117 同款", ORANGE),
        ("S5", "代码生成", "translate→.ll\n→llc/clang", ORANGE),
        ("S6", "验证", "golden 逐点\nbitwise", RED),
    ]
    sw_, sh_, sgap = 136, 96, 14
    sx0 = (W - (sw_*7 + sgap*6)) / 2
    for i, (sid, name, desc, color) in enumerate(stages):
        x = sx0 + i * (sw_ + sgap)
        b.append(hand_rect(x, 260, sw_, sh_, fill=color, opacity=0.45))
        b.append(text(x + sw_/2, 282, sid, 12.5, bold=True))
        b.append(text(x + sw_/2, 300, name, 11))
        for j, line in enumerate(desc.split("\n")):
            b.append(text(x + sw_/2, 318 + j*15, line, 9.5))
        if i < 6:
            b.append(arrow(x + sw_ + 1, 308, x + sw_ + sgap - 1, 308, sw=1.4))

    # 下：今日合同四件套
    b.append(text(W/2, 392, "今天的四份合同（25/25 合同测试全过）", 14, bold=True))
    contracts = [
        ("帮助文本", "--help：10 个选项\n+示例+版本号\n用户的第一份文档", GREEN),
        ("退出码", "0 成功 / 1 编译失败\n2 用法错误\n（clang/gcc 同族）", BLUE),
        ("诊断体系", "E1xx 用法×7\nE2xx 管道×6 / W1xx×3\n每条带修复建议", ORANGE),
        ("manifest", "JSON 机器合同\nversion/tile/stages\nexit_code 全记录", RED),
    ]
    cw, chh, cgap = 232, 130, 20
    cx0 = (W - (cw*4 + cgap*3)) / 2
    for i, (title, body, color) in enumerate(contracts):
        x = cx0 + i * (cw + cgap)
        b.append(hand_rect(x, 412, cw, chh, fill=color, opacity=0.45))
        b.append(text(x + cw/2, 436, title, 13, bold=True))
        for j, line in enumerate(body.split("\n")):
            b.append(text(x + cw/2, 458 + j*18, line, 10))

    # 底部：本周路线
    b.append(text(W/2, 576, "第 18 周排期：D120 骨架 → D121 S1 → D122 S2~S5 → D123 dump → D124 S6+端到端 → D125 对照 → D126 复盘", 11.5, MUTED))
    b.append(hand_rect(80, 596, W - 160, 56, fill="#F5E9C8", opacity=0.75))
    b.append(text(W/2, 618, "设计原则：CLI 先于集成——合同定了，零件才好接；", 12, bold=True))
    b.append(text(W/2, 638, "「参数解析/诊断/退出码」今天全部测试固化，D121 起每个零件的接入都有现成的合同测试可挂", 10.5, MUTED))
    save("01-overview.svg", "".join(b), h=670)


# ── 图 2：mechanism——诊断流转：从 argv 到退出码 ──
def fig2():
    b = []
    b.append(text(W/2, 34, "一次 minic 调用的生命周期：argv → 解析 → 校验 → 管道 → 退出码", 16, bold=True))

    # 主流程
    steps = [
        ("argv", ["minic gemm.mlir", "-O2 --tile 32,32,32", "-o out/"], GREEN),
        ("parse", ["argparse 解析", "--help/--version", "在此拦截"], GREEN),
        ("校验", ["E101 文件存在?", "E104 tile 格式?", "E103 目录可写?"], BLUE),
        ("Options", ["单一配置对象", "管道各阶段只读", "不碰 argv"], BLUE),
        ("管道 S0~S6", ["S0 读入计数", "S1~S6 骨架日志", "排期 D121~D125"], ORANGE),
        ("manifest", ["JSON 落盘", "机器合同", "CI 可消费"], ORANGE),
    ]
    sw_, sh_ = 156, 110
    sx0 = 40
    for i, (name, body, color) in enumerate(steps):
        x = sx0 + i * (sw_ + 14)
        b.append(hand_rect(x, 60, sw_, sh_, fill=color, opacity=0.45))
        b.append(text(x + sw_/2, 84, name, 12.5, bold=True))
        for j, line in enumerate(body):
            b.append(text(x + sw_/2, 106 + j*18, line, 9.5))
        if i < 5:
            b.append(arrow(x + sw_ + 1, 115, x + sw_ + 13, 115, sw=1.4))

    # 分岔：错误路径
    b.append(arrow(sx0 + 2*sw_ + 28, 172, sx0 + 2*sw_ + 28, 230, stroke=RED, sw=1.8, label="校验失败"))
    b.append(arrow(sx0 + 4*sw_ + 56, 172, sx0 + 4*sw_ + 56, 230, stroke=RED, sw=1.8, label="管道失败"))

    # 错误两条路
    b.append(hand_rect(240, 236, 280, 120, fill=RED, opacity=0.4))
    b.append(text(380, 260, "用法错误路径（E1xx）", 12.5, bold=True))
    b.append(text(380, 282, "E101~E107 结构化诊断", 10.5))
    b.append(text(380, 300, "stderr：代码+位置+原因+修复建议", 10))
    b.append(text(380, 322, "退出码 2（重试无意义，先读 --help）", 10.5, fill=RED, bold=True))

    b.append(hand_rect(560, 236, 280, 120, fill=RED, opacity=0.4))
    b.append(text(700, 260, "编译错误路径（E2xx）", 12.5, bold=True))
    b.append(text(700, 282, "E201~E206 阶段化诊断", 10.5))
    b.append(text(700, 300, "已完成的阶段产物保留在 out/", 10))
    b.append(text(700, 322, "退出码 1（改输入或修管道后再来）", 10.5, fill=RED, bold=True))

    # 诊断解剖
    b.append(text(W/2, 396, "一条诊断的解剖（E104 实例）", 14, bold=True))
    b.append(hand_rect(140, 414, 800, 108, fill=BG, opacity=0.95, sw=1.8))
    b.append(text(160, 438, "E104 [minic] tile 参数格式错误：32,32（应为 M,N,K 三个正整数，逗号分隔）", 11, mono=True, anchor="start"))
    b.append(text(160, 460, "       修复建议：示例：--tile 32,32,32；每维必须 ≥1", 11, mono=True, anchor="start", fill="#4a7c59"))
    b.append(text(160, 486, "├─ 代码：E 系列开头的三位数字（E1=用法层，E2=管道层）  ├─ 位置：哪个阶段/哪层报的", 10, anchor="start", fill=MUTED))
    b.append(text(160, 506, "├─ 原因：具体什么不合法  └─ 修复建议：用户下一步动作——四件套缺一不可", 10, anchor="start", fill=MUTED))

    # 退出码合同
    b.append(text(W/2, 556, "退出码合同（与 clang/gcc 同族——脚本可编程消费）", 14, bold=True))
    codes = [("0", "成功（若 --verify 则含验证通过）", GREEN),
             ("1", "编译/验证失败（E2xx）", ORANGE),
             ("2", "用法错误（E1xx）", RED)]
    for i, (code, desc, color) in enumerate(codes):
        x = 120 + i * 300
        b.append(hand_rect(x, 574, 280, 60, fill=color, opacity=0.4))
        b.append(text(x + 34, 602, code, 20, bold=True))
        b.append(text(x + 160, 600, desc, 10))
        b.append(text(x + 160, 616, "exit $?" if i == 0 else ("make 会停" if i == 1 else "CI 立即红"), 9, MUTED))
    save("02-mechanism.svg", "".join(b), h=660)


# ── 图 3：example——合同测试矩阵与固化的 help 快照 ──
def fig3():
    b = []
    b.append(text(W/2, 34, "合同测试矩阵：25 项测试怎么覆盖四份合同", 16, bold=True))

    # 左：测试矩阵
    b.append(hand_rect(50, 60, 560, 480, fill=BLUE, opacity=0.3))
    b.append(text(330, 86, "run_all.sh 的六个 TP（25 项断言）", 13.5, bold=True))
    tps = [
        ("TP1 帮助文本", "8 项：--help 含 usage/-O/--tile/--emit/", "--dump-ir/--verify/--llvm-bin/示例；", "--version 输出版本号", GREEN),
        ("TP2 退出码", "3 项：合法输入→0；E101→2；E104→2", "（三态合同的每个出口都有测试）", "", BLUE),
        ("TP3 诊断体系", "7 项：E101（含修复建议）/E102/", "E104 非数字/E104 四维/E105/", "E107 逐条触发", ORANGE),
        ("TP4 manifest", "2 项：生成＋字段齐全", "（version/input/tile/stages/", "exit_code 逐个断言）", RED),
        ("TP5 开关与警告", "3 项：W102 触发；-O0 退出 0；", "manifest 记录跳过原因", "", PURPLE),
        ("TP6 合同快照", "2 项：help.txt 入档；选项 ≥10", "（明天起 --help 的任何变化", "都该反映在 diff 里）", GREEN),
    ]
    y = 108
    for name, l1, l2, l3, color in tps:
        b.append(hand_rect(70, y, 520, 66, fill=color, opacity=0.4))
        b.append(text(88, y + 22, name, 11.5, bold=True, anchor="start"))
        for j, line in enumerate([l1, l2, l3]):
            if line:
                b.append(text(88, y + 38 + j*14, line, 9.5, anchor="start"))
        y += 72

    # 右：合同演化
    b.append(hand_rect(640, 60, 400, 480, fill="#F5E9C8", opacity=0.7))
    b.append(text(840, 86, "合同怎么长（第 18 周排期）", 13.5, bold=True))
    grows = [
        ("D120 今天", "CLI 骨架：四份合同全部固化", "25/25 测试绿", GREEN),
        ("D121 明天", "S1 接入：--no-graph-opt 开关", "新增 E2xx：图优化失败诊断", BLUE),
        ("D122", "S2~S5 接入：真实管道", "--emit ir/obj/exec 生效", BLUE),
        ("D123", "--dump-ir 全量：stage-N-*.mlir", "E2xx 带上 IR 定位", ORANGE),
        ("D124", "S6 验证：--verify 生效", "退出码 1 的最大来源", RED),
        ("D125", "对照实验：-O0/O1/O2/O3 四组", "manifest 记录全程开关", PURPLE),
    ]
    y = 108
    for day, what, note, _color in grows:
        b.append(hand_rect(660, y, 360, 62, fill=BG, opacity=0.9))
        b.append(text(680, y + 22, day, 11.5, bold=True, anchor="start"))
        b.append(text(680, y + 40, what, 10, anchor="start"))
        b.append(text(680, y + 54, note, 9.5, anchor="start", fill=MUTED))
        y += 72

    # 底部
    b.append(hand_rect(50, 566, W - 100, 66, fill=GREEN, opacity=0.35))
    b.append(text(W/2, 590, "为什么 CLI 先于集成？——合同是零件的插座。", 12.5, bold=True))
    b.append(text(W/2, 612, "D121 接图优化时不用重新设计参数怎么传、失败怎么报、manifest 怎么记——今天全部定好并测试固化；", 10.5))
    b.append(text(W/2, 628, "反之，先集成后设计 CLI 的项目，最后往往会得到五个互不一致的入口脚本", 10.5, MUTED))
    save("03-example.svg", "".join(b), h=660)


if __name__ == "__main__":
    fig1()
    fig2()
    fig3()
