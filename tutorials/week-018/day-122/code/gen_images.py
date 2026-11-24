#!/usr/bin/env python3
"""生成第 122 天（minic S2~S5）的 3 张手绘 sketch 风 SVG 图。

数字来自 outputs/report.txt 真实运行（2026-11-14，macOS arm64，
Python 3.9.6，Homebrew LLVM 23.1.5）。固定随机种子 122。
"""
from __future__ import annotations

import math
import os
import random
import xml.sax.saxutils as su

random.seed(122)

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


# ── 图 1：minic 0.3.0 全景——S1~S5 全真实 ──
def fig1():
    b = []
    b.append(text(W/2, 34, "minic 0.3.0：一条命令从图 IR 到汇编——S1~S5 全部真实", 16, bold=True))

    # 顶行：minic 命令
    b.append(hand_rect(180, 56, 720, 46, fill=ORANGE, opacity=0.7, sw=2))
    b.append(text(W/2, 84, "minic main.graph -o out/ --tile 2,3,6 --dump-ir", 13.5, bold=True, mono=True))

    # 六阶段流
    stages = [
        ("S0", "读入", "38 行计数\n+扩展名校验", GREEN),
        ("S1", "图优化", "11→5 节点\n（D121 五闸）", GREEN),
        ("S2", "循环生成", "fused→scf.for\nM/NK 推断自图", BLUE),
        ("S3", "Tiling", "tile 进步长\nmin 钳制", BLUE),
        ("S4", "LLVM Lower", "七 pass 管道\n（D117 同款）", ORANGE),
        ("S5", "代码生成", "translate→.ll\nllc→.s", RED),
    ]
    sw_, sh_, sgap = 158, 100, 14
    sx0 = (W - (sw_*6 + sgap*5)) / 2
    for i, (sid, name, desc, color) in enumerate(stages):
        x = sx0 + i * (sw_ + sgap)
        b.append(hand_rect(x, 122, sw_, sh_, fill=color, opacity=0.45))
        b.append(text(x + sw_/2, 144, sid + " ✓", 12.5, bold=True))
        b.append(text(x + sw_/2, 162, name, 11))
        for j, line in enumerate(desc.split("\n")):
            b.append(text(x + sw_/2, 180 + j*15, line, 9.5))
        if i < 5:
            b.append(arrow(x + sw_ + 1, 172, x + sw_ + sgap - 1, 172, sw=1.4))
    b.append(hand_rect(sx0, 238, sw_*6 + sgap*5, 40, fill="#F5E9C8", opacity=0.8))
    b.append(text(W/2, 262, "S6 验证：骨架（D124 接入 golden bitwise）——今天管道停在「可编译证明」", 11, fill=MUTED))

    # 中：产物目录树（stage 序号）
    b.append(text(W/2, 310, "out/ 目录：阶段序列文件（文件名含序号——D123 可观测性的地基）", 14, bold=True))
    b.append(hand_rect(200, 328, 680, 200, fill=BG, opacity=0.95, sw=1.8))
    tree = [
        ("manifest.json", "机器合同（exit_code/stages/diags）", GREEN),
        ("stage-1-graph-opt.graph", "S1 终图（5 节点）", GREEN),
        ("stage-2-loop.mlir", "S2 循环 IR（scf.for×3）", BLUE),
        ("stage-4-03-canonicalize+csi.mlir", "S4 pass 1：优化", ORANGE),
        ("stage-4-04-convert-scf-to-cf.mlir", "S4 pass 2：C1 落地", ORANGE),
        ("stage-4-05..09-*.mlir", "S4 pass 3~7：五连转换", ORANGE),
        ("stage-4-10-reconcile-*.mlir", "S4 pass 8：胶水清零", ORANGE),
        ("stage-5.ll / stage-5.s", "S5：LLVM IR＋汇编", RED),
    ]
    y = 350
    for fname, desc, color in tree:
        b.append(hand_rect(220, y, 640, 20, fill=color, opacity=0.3))
        b.append(text(240, y + 15, fname, 9.5, mono=True, anchor="start"))
        b.append(text(700, y + 15, desc, 9.5, anchor="start", fill=MUTED))
        y += 22

    # 底部：数字
    b.append(text(W/2, 560, "真机证据（25 PASS / 0 FAIL）", 14, bold=True))
    stats = [("11 个", "stage 文件按序\n落盘（TP2）"), ("0 条", "胶水残留\n（reconcile 干净）"),
             ("退出码 1", "E202/E204 失败\n如实分级"), ("stderr 全文", "pipeline-error.txt\n落盘（TP5）")]
    cw, chh, cgap = 210, 76, 20
    cx0 = (W - (cw*4 + cgap*3)) / 2
    for i, (num, label) in enumerate(stats):
        x = cx0 + i * (cw + cgap)
        b.append(hand_rect(x, 580, cw, chh, fill=ORANGE, opacity=0.5))
        b.append(text(x + cw/2, 604, num, 14.5, bold=True))
        for j, line in enumerate(label.split("\n")):
            b.append(text(x + cw/2, 622 + j*14, line, 9.5, MUTED))
    save("01-overview.svg", "".join(b), h=680)


# ── 图 2：失败诊断的分层保留 ──
def fig2():
    b = []
    b.append(text(W/2, 34, "失败诊断：保留现场、指认责任、停止后续——三条失败路径对照", 16, bold=True))

    # 主流程（成功路径）
    b.append(hand_rect(60, 60, 960, 60, fill=GREEN, opacity=0.35))
    b.append(text(W/2, 84, "成功路径：S0→S1→S2→S3→S4（pass 1~8）→S5（translate+llc）→ manifest(exit 0)", 11.5, bold=True))
    b.append(text(W/2, 106, "每个阶段一个 stage 文件——成功时它们是产物，失败时它们是现场", 10.5, MUTED))

    # 三条失败路径
    fails = [
        ("失败 A：E202（S2 循环生成）", 
         "触发：图中出现不支持的算子\n（conv2d / vector.* / ...）",
         "诊断：E202 带节点 id＋算子名＋支持集\n现场：stage-1 终图落盘（可复查）\n退出码 1",
         "「进海关前就拦下」——还没花\nS4/S5 的编译成本", BLUE),
        ("失败 B：E204（S4 某条 pass）",
         "触发：vector.reduce 残账（D114\n暂不支持清单第 4 条）",
         "诊断：E204 带失败 pass 名＋首行报错\n现场：pipeline-error.txt（stderr 全文）\n＋失败前的 stage 文件全保留",
         "「指认到条」——八条 pass 哪条\n失败一清二楚", ORANGE),
        ("失败 C：E205（S5 代码生成）",
         "触发：mlir-translate / llc 失败\n（如胶水残留、目标不支持）",
         "诊断：E205 带工具名\n现场：.ll 若已生成则保留\n退出码 1",
         "「最后一公里」——D117 四个\n错误存档的工程化", RED),
    ]
    fw, fh, fgap = 300, 300, 22
    fx0 = (W - (fw*3 + fgap*2)) / 2
    for i, (title, trigger, diag, meaning, color) in enumerate(fails):
        x = fx0 + i * (fw + fgap)
        b.append(hand_rect(x, 140, fw, fh, fill=color, opacity=0.35))
        b.append(text(x + fw/2, 164, title, 12, bold=True))
        b.append(text(x + fw/2, 186, "怎么触发", 10, fill=MUTED))
        for j, line in enumerate(trigger.split("\n")):
            b.append(text(x + fw/2, 202 + j*14, line, 9))
        b.append(text(x + fw/2, 244, "诊断与现场", 10, fill=MUTED))
        for j, line in enumerate(diag.split("\n")):
            b.append(text(x + fw/2, 260 + j*14, line, 9))
        b.append(text(x + fw/2, 316, "意义", 10, fill=MUTED))
        for j, line in enumerate(meaning.split("\n")):
            b.append(text(x + fw/2, 332 + j*14, line, 9))

    # 下：诊断设计三原则
    b.append(text(W/2, 478, "诊断设计三原则（今天的三条实现决策）", 14, bold=True))
    principles = [
        ("① 保留现场", "失败前的 stage 文件不删；\npipeline-error.txt 存 stderr 全文。\n调试不从头再来。", GREEN),
        ("② 指认到条", "E204 报哪条 pass、E202 报哪个节点；\n每条 pass 单独跑（不用一串 flag\n一次性跑完——失败时无法定位）。", BLUE),
        ("③ 陈旧清理", "二次运行前清掉旧 stage 文件——\n现场只属于本次。\n（今天踩的真坑：新旧产物混淆）", RED),
    ]
    pw, ph, pgap = 300, 130, 22
    px0 = (W - (pw*3 + pgap*2)) / 2
    for i, (title, body, color) in enumerate(principles):
        x = px0 + i * (pw + pgap)
        b.append(hand_rect(x, 498, pw, ph, fill=color, opacity=0.4))
        b.append(text(x + pw/2, 522, title, 12.5, bold=True))
        for j, line in enumerate(body.split("\n")):
            b.append(text(x + pw/2, 544 + j*16, line, 9.5))

    b.append(hand_rect(80, 648, W - 160, 42, fill="#F5E9C8", opacity=0.8))
    b.append(text(W/2, 670, "与 D117 的关系：那天的四个错误是「复现存档」（errors-1~4.txt）；今天把它们工程化成 minic 的运行时行为——错误不再需要手动复现", 11))
    save("02-mechanism.svg", "".join(b), h=710)


# ── 图 3：跨天对账与 stage-5.ll 解剖 ──
def fig3():
    b = []
    b.append(text(W/2, 34, "跨天对账：minic S4 产物与 D117 冻结管道同构", 16, bold=True))

    # 左：D117 gemm.mlir 双路对照
    b.append(hand_rect(50, 60, 480, 300, fill=BLUE, opacity=0.3))
    b.append(text(290, 84, "D117 的 gemm.mlir 走两条路（TP8 实测）", 13, bold=True))
    b.append(text(290, 110, "路径 A（D117 冻结）：lower.sh 七 pass + translate", 10.5, anchor="start"))
    b.append(text(290, 128, "  → gemm-3.ll（62 SSA / 4 phi / 21 iv）", 10, anchor="start", mono=True, fill=MUTED))
    b.append(text(290, 152, "路径 B（今天）：minic S4 管道（同一命令序列）", 10.5, anchor="start"))
    b.append(text(290, 170, "  → stage-5.ll", 10, anchor="start", mono=True, fill=MUTED))
    b.append(arrow(290, 186, 290, 208, sw=1.6))
    b.append(hand_rect(80, 210, 420, 120, fill="#F5E9C8", opacity=0.85))
    checks = [
        "✓ _mlir_ciface_gemm 包装在位（emit_c_interface）",
        "✓ malloc 调用在位（M3 模式：alloc→call）",
        "✓ 七 pass 全过、胶水 0（reconcile 干净）",
        "✓ LLVM 18（D117）与 23（本机）语义同构",
        "  （文本差异：undef→poison、gep 加 inbounds nuw",
        "   ——D118 实验 A 与 D119 跨版本对账的结论）",
    ]
    for j, line in enumerate(checks):
        b.append(text(100, 232 + j*17, line, 9.5, anchor="start"))

    # 右：stage-5.ll 的解剖
    b.append(hand_rect(550, 60, 480, 300, fill=ORANGE, opacity=0.3))
    b.append(text(790, 84, "main.graph 的 stage-5.ll 解剖（今天的主线产物）", 13, bold=True))
    parts = [
        ("define @main_kernel(...)", "签名：3 个 strided memref（a/b/bias）", GREEN),
        ("  14 个裸参数", "3 memref × 7 字段拆包（D115 ABI）", GREEN),
        ("  call @malloc(48)", "输出缓冲区（M3：alloc→malloc）", BLUE),
        ("  三重循环体", "tile 壳＋点循环（scf→cf→llvm 落地）", BLUE),
        ("define @_mlir_ciface_main_kernel", "sret 三指针包装（D116/117 合同）", ORANGE),
        ("  (ptr, ptr, ptr)", "C 合同：out, a, b(+bias)", ORANGE),
    ]
    y = 108
    for code, desc, color in parts:
        b.append(hand_rect(570, y, 440, 34, fill=color, opacity=0.3))
        b.append(text(585, y + 14, code, 9.5, mono=True, anchor="start"))
        b.append(text(585, y + 27, desc, 8.5, anchor="start", fill=MUTED))
        y += 40

    # 下：S2 生成的关键决策
    b.append(text(W/2, 396, "S2 循环生成的三个关键决策", 14, bold=True))
    decisions = [
        ("① shape 从图推断", "const 的 shape 属性 / arg 的 tensor 类型 / reshape 的 new_shape\n——不猜：三个来源各管一段，推断不出就 E202", GREEN),
        ("② tile 直接进步长", "scf.for %i0 = 0 to M step TM——min(TM,M) 钳制接边界\n（教学简化：点循环展开留注释，数值由 S6 把关）", BLUE),
        ("③ bias 融在 k=0 圈", "fused_matmul_bias_relu 的 bias 语义 = D85~90 任务单的「k=0 加 bias」\n——图优化（D121 融合）与循环生成（今天）的合同对齐", ORANGE),
    ]
    y = 416
    for title, body, color in decisions:
        b.append(hand_rect(70, y, 940, 62, fill=color, opacity=0.35))
        b.append(text(100, y + 22, title, 11.5, bold=True, anchor="start"))
        for j, line in enumerate(body.split("\n")):
            b.append(text(100, y + 40 + j*14, line, 9.5, anchor="start"))
        y += 72

    b.append(hand_rect(70, y + 4, 940, 48, fill="#F5E9C8", opacity=0.8))
    b.append(text(W/2, y + 24, "明天 D123 IR Dump 与可观测性：今天的 stage 序号文件是地基——要补的是「每条 pass 的改写记录」与 dump 粒度控制", 11))
    b.append(text(W/2, y + 42, "（审计日志结构化、--dump-ir 按需分阶段、时间线可视化）", 10, MUTED))
    save("03-example.svg", "".join(b), h=700)


if __name__ == "__main__":
    fig1()
    fig2()
    fig3()
