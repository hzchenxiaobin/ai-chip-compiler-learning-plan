#!/usr/bin/env python3
"""生成第 118 天的 3 张手绘 sketch 风 SVG 技术图（Excalidraw-like）。

风格与 D110~D117 一致：白板涂鸦感——带抖动的贝塞尔手绘路径、马克笔笔触、
3～4 种柔和强调色（蓝/橙/绿/红）＋米白背景、简单几何形状、手写感字体。
所有数字来自 outputs/ 的真实冻结运行（report.txt，2026-11-14，
macOS arm64，Homebrew LLVM/clang 23.1.5，Python 3.9.6 / numpy 1.26.4）。
固定随机种子 118，图可复现。
"""

from __future__ import annotations

import math
import os
import random
import xml.sax.saxutils as su

random.seed(118)

BG = "#FDFBF6"
BORDER = "#E7DFCE"
INK = "#3B3B3B"
MUTED = "#6b6257"
ORANGE = "#E8A87C"
BLUE = "#A9C4D4"
GREEN = "#9CBF8E"
RED = "#C97B7B"
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


# ════════════════════════════════════════════════════════════════
# 图 1：overview——今天在编译链路中的位置 + 四条执行路线全景
# ════════════════════════════════════════════════════════════════
def fig1():
    b = []
    # 上排：编译链路（D113~D117 已走完的栈 + 今天的出口）
    chain = [("图 IR\nD57~D105", BLUE), ("循环+内存 IR\nD85~D105", BLUE),
             ("函数+类型\nD115 ✓", GREEN), ("算子+内存\nD116 ✓", GREEN),
             ("LLVM Dialect\nD117 ✓", GREEN), ("LLVM IR .ll\nD117 ✓", GREEN)]
    x0, y0, cw, chh, gap = 70, 60, 148, 66, 24
    for i, (label, color) in enumerate(chain):
        x = x0 + i * (cw + gap)
        b.append(hand_rect(x, y0, cw, chh, fill=color, opacity=0.55))
        b.append(text(x + cw/2, y0 + 26, label.split("\n")[0], 12.5, bold=True))
        b.append(text(x + cw/2, y0 + 46, label.split("\n")[1], 10.5, MUTED))
        if i < len(chain) - 1:
            b.append(arrow(x + cw + 2, y0 + chh/2, x + cw + gap - 3, y0 + chh/2))
    # 今天的框（橙色）
    tx = x0 + 6 * (cw + gap)
    b.append(hand_rect(tx, y0, cw, chh, fill=ORANGE, opacity=0.75, sw=2.2))
    b.append(text(tx + cw/2, y0 + 26, "执行！", 14, bold=True))
    b.append(text(tx + cw/2, y0 + 46, "今天 D118", 10.5, MUTED))
    b.append(arrow(x0 + 5*(cw+gap) + cw + 2, y0 + chh/2, tx - 3, y0 + chh/2, sw=2.2))
    b.append(text(W/2, 36, "从「能导出」到「能运行」——今天接最后一棒", 16, bold=True))

    # 中排：四条执行路线
    b.append(text(W/2, 175, "四条执行路线（同一份 gemm-3.ll，12/12 全对）", 14, bold=True))
    routes = [
        ("路线 1  AOT-静态", "clang 编 .ll+driver.c\n→ 可执行文件\n进程外、一次编译反复跑", GREEN),
        ("路线 2  AOT-共享库", "llc→.o→libgemm.dylib\npython3+ctypes 调用\n编译期/运行期进程边界", BLUE),
        ("路线 3  JIT-lli", ".ll + jit_main.ll\nlli 解释执行\n零产物文件、逐次编译", ORANGE),
        ("路线 4  JIT-MCJIT", "C++ 驱动内嵌 LLVM API\nparse→MCJIT→getFunctionAddress\n真实 JIT 引擎路径", RED),
    ]
    rw, rh, rgap = 236, 150, 22
    rx0 = (W - (rw*4 + rgap*3)) / 2
    for i, (title, body, color) in enumerate(routes):
        x = rx0 + i * (rw + rgap)
        b.append(hand_rect(x, 200, rw, rh, fill=color, opacity=0.5))
        b.append(text(x + rw/2, 226, title, 13, bold=True))
        for j, line in enumerate(body.split("\n")):
            b.append(text(x + rw/2, 250 + j*19, line, 10.5))
    b.append(arrow(rx0 + rw/2, 355, rx0 + rw/2 + rgap, 355))  # 装饰箭头不必
    # 中下：金色对照带
    b.append(hand_rect(rx0, 378, rw*4 + rgap*3, 54, fill="#F5E9C8", opacity=0.7))
    b.append(text(W/2, 400, "golden = numpy A@B（float32，C[0][1]=0.5×2−1×5+2×8+0+1.5×14−0.5×17 = 24.5 手算锚点）", 11))
    b.append(text(W/2, 420, "四条路线 × 12 点全部 bitwise 一致——执行层的唯一裁判是数值", 11, MUTED))

    # 下排：C 合同（ABI 约定）
    b.append(text(W/2, 468, "三条路线共用同一份 C 合同（D115 定契约 → D116 手写 → D117 真工具生成）", 13.5, bold=True))
    b.append(hand_rect(110, 486, 860, 96, fill=BLUE, opacity=0.35))
    b.append(text(140, 510, "void _mlir_ciface_gemm(desc_t* out, desc_t* a, desc_t* b)", 12.5, mono=True, anchor="start"))
    b.append(text(140, 532, "desc_t = { float* alloc; float* aligned; i64 off; i64 sh[2]; i64 st[2]; }  // 56B", 11.5, mono=True, anchor="start"))
    b.append(text(140, 556, "关键语义：@gemm 内部 memref.alloc() 自己 malloc——结果在返回的 desc 里，不在调用方缓冲区", 11, anchor="start", fill=RED))
    b.append(text(140, 574, "（malloc 债务：kernel 不 free；教学规模无所谓，真实 Runtime 要管生命周期——D131 内存分配与复用）", 10, anchor="start", fill=MUTED))

    # 底部：今日战绩数字
    b.append(text(W/2, 615, "真机证据（macOS arm64 · Homebrew clang 23.1.5 · 2026-11-14）", 13.5, bold=True))
    stats = [("12/12", "四路线×12点\nbitwise 全对"), ("50248 B", "AOT 可执行文件\n（含启动代码）"),
             ("2.8 ms", "进程级端到端中位\n（fork+exec ~1ms）"), ("12 PASS", "TP0~TP6\n0 FAIL")]
    sw_, sh_, sgap = 200, 84, 24
    sx0 = (W - (sw_*4 + sgap*3)) / 2
    for i, (num, label) in enumerate(stats):
        x = sx0 + i * (sw_ + sgap)
        b.append(hand_rect(x, 634, sw_, sh_, fill=ORANGE, opacity=0.55))
        b.append(text(x + sw_/2, 660, num, 17, bold=True))
        for j, line in enumerate(label.split("\n")):
            b.append(text(x + sw_/2, 678 + j*16, line, 10, MUTED))
    save("01-overview.svg", "".join(b))


# ════════════════════════════════════════════════════════════════
# 图 2：mechanism——JIT 与 AOT 的分岔点：编译时机
# ════════════════════════════════════════════════════════════════
def fig2():
    b = []
    b.append(text(W/2, 36, "JIT 与 AOT：同一份 .ll，两种「编译时机」", 16, bold=True))

    # 顶部公共输入
    b.append(hand_rect(W/2 - 130, 58, 260, 52, fill=GREEN, opacity=0.55))
    b.append(text(W/2, 80, "gemm-3.ll（D117 冻结）", 13.5, bold=True))
    b.append(text(W/2, 100, "LLVM IR 文本 · 2 define · sret 三指针包装", 10.5, MUTED))

    # 左右分岔
    b.append(arrow(W/2 - 100, 112, 260, 170, sw=2.0, label="编译期（离线）"))
    b.append(arrow(W/2 + 100, 112, W - 260, 170, sw=2.0, label="运行期（在线）"))

    # 左：AOT
    b.append(hand_rect(70, 178, 400, 250, fill=BLUE, opacity=0.35))
    b.append(text(270, 204, "AOT：Ahead-Of-Time", 14, bold=True))
    b.append(text(270, 226, "clang gemm-3.ll driver.c -o gemm_aot", 10.5, mono=True))
    steps_l = [
        "① llc/clang 后端编译 → 目标文件 .o",
        "② 链接（启动代码 + libc + driver）→ 可执行文件",
        "③ 磁盘落盘 50248 B，之后每次运行零编译",
        "④ 启动代价：fork+exec ~1ms（教学规模实测中位 2.8ms）",
        "⑤ 符号在链接期解析完——运行期没有「编译」这个动作",
    ]
    for j, s in enumerate(steps_l):
        b.append(text(95, 254 + j*22, s, 11, anchor="start"))
    b.append(text(270, 376 + 24, "适合：形态固定、反复部署（D124 端到端、D125 对照实验都用它）", 10.5, MUTED))

    # 右：JIT
    b.append(hand_rect(W - 470, 178, 400, 250, fill=ORANGE, opacity=0.4))
    b.append(text(W - 270, 204, "JIT：Just-In-Time", 14, bold=True))
    b.append(text(W - 270, 226, "lli jit_combined.ll  /  MCJIT driver", 10.5, mono=True))
    steps_r = [
        "① 运行期 parse .ll（或收 IR 字节码）",
        "② 内存中生成目标代码（不落盘）",
        "③ getFunctionAddress 按名取函数指针",
        "④ 首次调用含编译开销，之后直接执行机器码",
        "⑤ 可按运行期信息特化（真实系统：按 shape 生成 kernel）",
    ]
    for j, s in enumerate(steps_r):
        b.append(text(W - 445, 254 + j*22, s, 11, anchor="start"))
    b.append(text(W - 270, 376 + 24, "适合：形态不定、按需生成（D129 静态 Shape 特化的思想源）", 10.5, MUTED))

    # 中下：殊途同归带
    b.append(arrow(270, 432, 400, 490, dash="6 4"))
    b.append(arrow(W - 270, 432, W - 400, 490, dash="6 4"))
    b.append(hand_rect(W/2 - 320, 500, 640, 64, fill="#F5E9C8", opacity=0.75))
    b.append(text(W/2, 524, "殊途同归：两条路线的 @gemm 机器码语义等价（TP3 逐行对照一致）", 12.5, bold=True))
    b.append(text(W/2, 548, "分歧只在「编译发生在什么时刻」——这是 Compiler/Runtime 边界的第一课（D127 展开）", 11, MUTED))

    # 底部：MCJIT 内部解剖
    b.append(text(W/2, 600, "MCJIT 驱动内部（路线 4 把 lli 黑盒拆开）", 13.5, bold=True))
    mc = ["parseIRFile", "verifyModule", "create MCJIT", "finalizeObject", "getFunctionAddress", "按 C 合同调用"]
    mw, mgap = 150, 14
    mx0 = (W - (mw*6 + mgap*5)) / 2
    for i, s in enumerate(mc):
        x = mx0 + i * (mw + mgap)
        b.append(hand_rect(x, 620, mw, 46, fill=RED, opacity=0.45))
        b.append(text(x + mw/2, 640, s, 11.5, mono=True))
        b.append(text(x + mw/2, 656, ["读 .ll", "验 IR", "创建引擎", "编译到内存", "查符号拿地址", "ctypes 同款 ABI"][i], 9.5, MUTED))
        if i < 5:
            b.append(arrow(x + mw + 1, 643, x + mw + mgap - 1, 643))
    b.append(text(W/2, 700, "—— 这 6 步正是 MLIR ExecutionEngine（mlir-runner 的心脏）每天在做的事", 11, MUTED))
    save("02-mechanism.svg", "".join(b), h=720)


# ════════════════════════════════════════════════════════════════
# 图 3：example——driver.c 的调用现场 + malloc 债务数据流
# ════════════════════════════════════════════════════════════════
def fig3():
    b = []
    b.append(text(W/2, 36, "调用现场解剖：一次 _mlir_ciface_gemm 调用的数据流", 16, bold=True))

    # 左：调用方
    b.append(hand_rect(60, 70, 330, 300, fill=GREEN, opacity=0.4))
    b.append(text(225, 96, "调用方（driver.c / ctypes / jit_main.ll）", 13, bold=True))
    caller = [
        "float A[24] = {0.5,-1,2,...};   // 栈/全局数据",
        "desc_t da = {A, A, 0, {4,6}, {6,1}};",
        "desc_t db = {B, B, 0, {6,3}, {3,1}};",
        "desc_t dc = {0,0,0, {4,3},{3,1}};  // alloc 留空",
        "",
        "  ↓ 按 C 合同传三个指针 ↓",
        "_mlir_ciface_gemm(&dc, &da, &db);",
        "",
        "  ↑ 包装把返回描述符 store 回 dc ↑",
        "printf(\"%f\", dc.alloc[1]);  // 24.50 ✓",
    ]
    for j, s in enumerate(caller):
        b.append(text(225, 124 + j*24, s, 10.5, mono=True))

    # 右：被调方（LLVM 侧）
    b.append(hand_rect(W - 500, 70, 440, 300, fill=BLUE, opacity=0.4))
    b.append(text(W - 280, 96, "被调方（gemm-3.ll，D117 冻结）", 13, bold=True))
    callee = [
        "define @gemm(...) -> {ptr,ptr,i64,[2xi64],[2xi64]} {",
        "  %29 = call ptr @malloc(48)      ← 债务①",
        "  ... 4×6×3 三重循环 fmul/fadd ...",
        "  store 到 %29（kernel 自己的缓冲区）",
        "  ret 描述符（含 %29）",
        "}",
        "define @_mlir_ciface_gemm(ptr %0, ptr %1, ptr %2) {",
        "  从 %1/%2 load 两个描述符 → 拆 7 字段",
        "  call @gemm(...) → 拿到新描述符",
        "  store 新描述符到 %0（sret 语义）  ← 结果出口",
        "}",
    ]
    for j, s in enumerate(callee):
        b.append(text(W - 280, 124 + j*24, s, 10.5, mono=True))

    # 中间的箭头
    b.append(arrow(395, 210, W - 505, 210, sw=2.0, label="三个 desc 指针（56B×3）"))
    b.append(arrow(W - 505, 280, 395, 280, sw=2.0, label="sret：把结果 desc 写回 *out"))

    # 下：malloc 债务与误区
    b.append(hand_rect(60, 400, 460, 130, fill=RED, opacity=0.35))
    b.append(text(290, 426, "常见误区（TP5 实测复现）", 13, bold=True))
    b.append(text(80, 450, "× 以为 kernel 会写调用方给的 C 数组", 11.5, anchor="start"))
    b.append(text(80, 472, "  实测：C[0..11] 全 0（kernel 从未写过）", 11, anchor="start", fill=MUTED))
    b.append(text(80, 494, "  正确：结果在 dc.alloc 指向的 malloc 缓冲区", 11.5, anchor="start"))
    b.append(text(80, 516, "  （driver_wrong.c 存档：wrong-result.txt）", 10, anchor="start", fill=MUTED))

    b.append(hand_rect(W - 520, 400, 460, 130, fill="#F5E9C8", opacity=0.75))
    b.append(text(W - 290, 426, "malloc 债务（今天挂账，D131 结清）", 13, bold=True))
    b.append(text(W - 500, 450, "· @gemm 每次 malloc 48B，从不 free", 11.5, anchor="start"))
    b.append(text(W - 500, 472, "· 教学规模（12 点）无所谓；真实推理服务", 11.5, anchor="start"))
    b.append(text(W - 500, 494, "  每秒百万次调用＝48MB/s 泄漏——必须上分配器/池", 11.5, anchor="start"))
    b.append(text(W - 500, 516, "· Runtime 的第一项职责由此产生（D131 内存分配与复用）", 11, anchor="start", fill=MUTED))

    # 底部：验证口径
    b.append(hand_rect(60, 560, W - 120, 100, fill=GREEN, opacity=0.3))
    b.append(text(W/2, 586, "验证口径（三层都在场）", 13.5, bold=True))
    b.append(text(W/2, 610, "契约层：desc 56B 布局与 D115 教学口径逐字段一致（alloc/aligned/off/sh/st）", 11))
    b.append(text(W/2, 632, "数值层：12/12 点与 numpy golden bitwise 一致（四条路线都过）", 11))
    b.append(text(W/2, 654, "交叉层：JIT 输出与 AOT 输出逐行 diff 一致（TP3）；同进程两轮调用一致（TP2）", 11))
    save("03-example.svg", "".join(b), h=690)


if __name__ == "__main__":
    fig1()
    fig2()
    fig3()
