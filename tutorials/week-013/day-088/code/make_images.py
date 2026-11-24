#!/usr/bin/env python3
"""生成第 88 天教程的 4 张手绘风（Excalidraw-like）SVG 技术图。

运行方式：
    python3 make_images.py

输出到 ../images/ 目录：
    01-overview.svg           第 88 天在第四阶段与编译链路中的位置 + 输入与产出
    02-loop-semantics.svg     scf.for 四要素：语法解剖、半开区间数轴、配对表、iv 身份
    03-boundary-tests.svg     边界测试：7 组 shape 实测表 + 三个注入探针
    04-results.svg            实测结果：BT1~BT7、关键数字、待填分工

风格与 Day 78~87 保持一致：手绘抖动线条、马克笔笔触、米白背景、
蓝/橙/绿/红四种柔和强调色、简单几何形状。
图中文字与数字全部来自 loop_pass.py 的真实运行结果（outputs/）。
"""

import math
import random
from pathlib import Path

random.seed(88)

INK = "#3b3b3b"
SOFT = "#6b6459"
BLUE = "#5f8fcb"
ORANGE = "#e8973f"
GREEN = "#79b26a"
RED = "#d96c5c"
BG = "#fdf9f0"
L_BLUE = "#dbe7f6"
L_ORANGE = "#fdead3"
L_GREEN = "#e5f1dc"
L_RED = "#f9dfd9"
FONT = "'Comic Sans MS','Segoe Print','Bradley Hand','Kaiti SC','KaiTi','STKaiti',cursive"

OUT = Path(__file__).resolve().parent.parent / "images"


def jseg(x1, y1, x2, y2, amp=1.3):
    dx, dy = (x2 - x1) / 2.0, (y2 - y1) / 2.0
    a = random.uniform(-amp, amp)
    b = random.uniform(-amp, amp)
    c = random.uniform(-amp, amp)
    d = random.uniform(-amp, amp)
    e = random.uniform(-amp, amp)
    f = random.uniform(-amp, amp)
    return (f"M {x1 + a:.1f},{y1 + b:.1f} Q {x1 + dx + c:.1f},{y1 + dy + d:.1f} "
            f"{x2 + e:.1f},{y2 + f:.1f}")


def style(fill="none", stroke=INK, sw=2.2, dash=None):
    s = (f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}" '
         f'stroke-linecap="round" stroke-linejoin="round"')
    if dash:
        s += f' stroke-dasharray="{dash}"'
    return s


def srect(x, y, w, h, fill="none", stroke=INK, sw=2.2, amp=1.3, dash=None):
    pts = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
    d = " ".join(jseg(*p, *q, amp) for p, q in zip(pts, pts[1:] + pts[:1]))
    return f'<path d="{d} Z" {style(fill, stroke, sw, dash)}/>'


def scirc(x, y, r, fill="white", stroke=INK, sw=2.0):
    wob = random.uniform(-0.8, 0.8)
    return (f'<path d="M {x - r},{y + wob} C {x - r},{y - r} {x + r},{y - r} '
            f'{x + r},{y} C {x + r},{y + r} {x - r},{y + r} {x - r},{y + wob}" '
            f'{style(fill, stroke, sw)}/>')


def sline(x1, y1, x2, y2, stroke=INK, sw=2.2, dash=None, amp=1.3):
    return f'<path d="{jseg(x1, y1, x2, y2, amp)}" {style("none", stroke, sw, dash)}/>'


def head(x, y, ang, stroke, sw, l=13, spread=0.46):
    a1 = (x - l * math.cos(ang - spread), y - l * math.sin(ang - spread))
    a2 = (x - l * math.cos(ang + spread), y - l * math.sin(ang + spread))
    return (f'<path d="{jseg(x, y, a1[0], a1[1], 0.7)}" {style("none", stroke, sw)}/>'
            f'<path d="{jseg(x, y, a2[0], a2[1], 0.7)}" {style("none", stroke, sw)}/>')


def arrow(x1, y1, x2, y2, stroke=INK, sw=2.2, dash=None):
    ang = math.atan2(y2 - y1, x2 - x1)
    return (f'<path d="{jseg(x1, y1, x2, y2)}" {style("none", stroke, sw, dash)}/>'
            + head(x2, y2, ang, stroke, sw))


def carrow(p0, ctrl, p1, stroke=INK, sw=2.2, dash=None):
    d = f"M {p0[0]:.1f},{p0[1]:.1f} Q {ctrl[0]:.1f},{ctrl[1]:.1f} {p1[0]:.1f},{p1[1]:.1f}"
    ang = math.atan2(p1[1] - ctrl[1], p1[0] - ctrl[0])
    return f'<path d="{d}" {style("none", stroke, sw, dash)}/>' + head(p1[0], p1[1], ang, stroke, sw)


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def text(x, y, s, size=16, fill=INK, anchor="start", rot=None):
    t = (f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-size="{size}" '
         f'fill="{fill}"')
    if rot:
        t += f' transform="rotate({rot} {x} {y})"'
    return t + f">{esc(s)}</text>"


def mtext(x, y, lines, size=12.5, fill=INK, anchor="start", lh=None):
    lh = lh or size + 4.5
    return "".join(text(x, y + i * lh, ln, size, fill, anchor) for i, ln in enumerate(lines))


def svg_doc(w, h, body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
            f'width="{w}" height="{h}">'
            f'<rect x="3" y="3" width="{w - 6}" height="{h - 6}" rx="7" fill="{BG}"/>'
            f'<g font-family="{FONT}">' + body + "</g></svg>")


def title_block(w, title, sub=None):
    body = text(30, 44, title, 25, INK)
    if sub:
        body += text(30, 70, sub, 14.5, SOFT)
    body += sline(30, 82, w - 30, 82, SOFT, 1.6, dash="7 6")
    return body


# ============================================================
# 图 1：全貌——第四阶段第四步 + 编译链路位置 + 输入与产出
# ============================================================

def img1() -> str:
    W, H = 1200, 710
    b = title_block(W, "第 88 天全貌：钉死三重循环——上界、下界、步长与归纳变量",
                    "第四阶段（第 13 周）：Day 87 保证了零起点，今天验收循环自身的四要素")

    # 上带：阶段地图
    b += srect(40, 100, 480, 96, fill=L_GREEN, stroke=GREEN, sw=2.4)
    b += text(56, 128, "第三阶段 图优化（D57~84）✓ 已收官", 16, INK)
    b += mtext(56, 152, ["五道闸管道：11 → 5 节点的干净 tensor 图", "产出：设计文档＋讲稿＋清单（D84）"], 12.5, SOFT)
    b += arrow(526, 148, 576, 148, SOFT, 2.4)
    b += srect(580, 100, 580, 96, fill=L_ORANGE, stroke=ORANGE, sw=3.0, amp=1.5)
    b += text(596, 126, "第四阶段 Lowering（D85~）", 16, INK)
    steps = [("D85 设计 ✓", "white"), ("D86 骨架 ✓", "white"), ("D87 初始化 ✓", "white"),
             ("D88 三重循环 ←今天", L_RED), ("D89 循环体", "white")]
    x = 596
    for label, fill in steps:
        w = 100 if fill == "white" else 130
        b += srect(x, 138, w, 30, fill=fill, stroke=ORANGE if fill == "white" else RED,
                   sw=1.8, amp=0.9)
        b += text(x + w / 2, 158, label, 12.5 if fill == "white" else 11.5, INK, "middle")
        x += w + 8
    b += text(596, 188, "口号：循环不是抄来的数字——四要素要有出生证明、有边界测试", 12.5, SOFT)

    # 中带：编译链路
    b += text(40, 232, "编译链路：今天走到哪一步？", 15, SOFT)
    stages = [
        ("前端\n(mini 图)", "white", SOFT, False),
        ("图优化\nD57~84 ✓", L_GREEN, GREEN, False),
        ("Lowering\nD88 今天", L_ORANGE, ORANGE, True),
        ("循环 IR 上的\nTiling/调度", "white", SOFT, False),
        ("CodeGen\n(第 14 周+)", "white", SOFT, False),
    ]
    x0, y0, bw, bh, gap = 40, 248, 200, 76, 28
    for i, (label, lf, lc, hot) in enumerate(stages):
        x = x0 + i * (bw + gap)
        b += srect(x, y0, bw, bh, fill=lf, stroke=lc, sw=3.0 if hot else 2.0, amp=1.2)
        ls = label.split("\n")
        b += text(x + bw / 2, y0 + 32, ls[0], 15.5, INK, "middle")
        b += text(x + bw / 2, y0 + 58, ls[1], 13.5, ORANGE if hot else SOFT, "middle")
        if hot:
            b += text(x + bw / 2, y0 - 12, "▼ 今天在这里钉循环四要素 ▼", 13, ORANGE, "middle")
        if i < 4:
            b += arrow(x + bw + 2, y0 + bh / 2, x + bw + gap - 2, y0 + bh / 2, SOFT, 2.0)
    b += mtext(40, 356, ["今天的 Pass 产出「四要素钉死、访存留白」的循环 IR：LoopSpec 规格＋边界/步长/iv；",
                          "半开区间与配对经过 BT1~BT7 验收；load/store/累加是 Day 89 的填空。"], 13, SOFT)

    # 下带：输入与产出
    b += text(40, 420, "今天的输入与产出（全部真实运行）", 15, SOFT)
    b += srect(40, 434, 250, 130, fill="white", stroke=SOFT, sw=2.0, dash="6 5")
    b += text(54, 460, "输入：D87 的 IR＋D85 清单②", 14.5, INK)
    b += mtext(54, 484, ["Day 87 初始化版 IR：13 op，", "  yield %zero 占位、访存留白", "＋ Day 85 任务清单②的索引栏：", "  三条循环边界与地址公式"], 11.8, INK, lh=18)
    outs = [
        ("产出 1：循环 IR", "loop-ir.txt", "带 LoopSpec 规格表；13 op", L_BLUE, BLUE),
        ("产出 2：边界表", "boundary-table.txt", "7 组 shape 的 trip/IV 实测", L_GREEN, GREEN),
        ("产出 3：测试报告", "test-report.txt", "BT1~BT7 真实执行：7/7 PASS", L_ORANGE, ORANGE),
    ]
    x0, bw, gap = 312, 268, 22
    for i, (t, f, m, lf, lc) in enumerate(outs):
        x = x0 + i * (bw + gap)
        b += srect(x, 434, bw, 130, fill=lf, stroke=lc, sw=2.4)
        b += text(x + 14, 462, t, 15, INK)
        b += text(x + 14, 488, f, 13, lc)
        b += mtext(x + 14, 512, [m], 12, INK)
        b += text(x + 14, 552, "outputs/ 里可查（＋debug-log.txt）", 11.5, SOFT)
    b += arrow(292, 499, 310, 499, SOFT, 2.2)

    # 底部：为什么循环值得单独一天
    b += srect(40, 592, 1120, 86, fill="white", stroke=RED, sw=2.2, dash="8 6")
    b += text(58, 620, "为什么循环值得单独一天？", 14.5, RED)
    b += mtext(58, 644, ["off-by-one 是循环 bug 之王；边界配对错在方阵测试里不响、到非方形才爆；step 不是精度参数；",
                          "iv 出了循环就不存在——Day 89 要往循环体里填访存与累加，地基必须先钉死。"], 12.5, INK, lh=20)
    return svg_doc(W, H, b)


# ============================================================
# 图 2：scf.for 四要素——语法解剖、官方语义、数轴、配对表、iv 身份
# ============================================================

def img2() -> str:
    W, H = 1240, 830
    b = title_block(W, "scf.for 的四要素：半开区间、步长为正、归纳变量是区域参数",
                    "语义依据官方文档（mlir.llvm.org，SCF dialect，2026-11 核对）——图中数字全部来自 BT1/BT2 实测")

    # 上左：语法解剖
    b += srect(40, 104, 570, 226, fill="white", stroke=BLUE, sw=2.6)
    b += text(56, 130, "语法解剖：一行 scf.for 的四个位置", 14.5, INK)
    b += text(66, 166, "scf.for %i = %c0 to %c4 step %c1 {", 17, INK)
    for cx, cy, label, col in [(120, 178, "归纳变量\n（区域参数）", ORANGE),
                               (215, 178, "下界\n（含端点）", GREEN),
                               (330, 178, "上界\n（不含！）", RED),
                               (452, 178, "步长\n（必须 > 0）", BLUE)]:
        b += arrow(cx, 182, cx, 214, col, 1.8)
        b += mtext(cx - 34, 234, label.split("\n"), 10.5, col, lh=14)
    b += mtext(56, 288, ["体：单个 block，以 scf.yield 结尾（无结果时可隐式插入终止器）",
                          "——今天 k 循环带 iter_args → 显式 yield %zero；i/j 循环无结果 → 隐式"], 11.3, SOFT, lh=17)

    # 上右：官方语义
    b += srect(630, 104, 570, 226, fill=L_BLUE, stroke=BLUE, sw=2.4)
    b += text(646, 130, "官方语义（scf.for，逐条核对）", 14.5, BLUE)
    b += mtext(646, 156, ["· 半开区间 [lb, ub)：含下界、不含上界",
                          "· trip = max(0, ceil((ub − lb) / step))",
                          "· iv 取 lb + j·step，j = 0 … trip−1（升序）",
                          "· step 必须严格为正（st ≤ 0 直接拒绝）",
                          "· iv 是区域第一个参数；iter_args 跟随其后",
                          "· lb/ub/step：index 或整数类型的 SSA 值"], 12.3, INK, lh=25)
    b += text(646, 312, "→ BT2 实测：trip 4/3/6，iv 最大值 = ub−step", 11.5, BLUE)

    # 中：半开区间数轴
    b += srect(40, 350, 1160, 168, fill="white", stroke=ORANGE, sw=2.4)
    b += text(58, 378, "半开区间数轴：i 的取值（M = 4，trip = 4）", 14.5, ORANGE)
    ax_y = 436
    b += sline(120, ax_y, 1050, ax_y, INK, 2.6)
    for t in range(5):
        x = 180 + t * 170
        b += sline(x, ax_y - 8, x, ax_y + 8, INK, 2.0)
        if t < 4:
            b += scirc(x, ax_y, 11, fill=L_GREEN, stroke=GREEN, sw=2.4)
            b += text(x, ax_y + 34, str(t), 14, INK, "middle")
        else:
            b += scirc(x, ax_y, 11, fill="white", stroke=RED, sw=2.4)
            b += text(x, ax_y + 34, "4 = ub", 13, RED, "middle")
    b += text(180, ax_y - 26, "取值 {0,1,2,3}", 12.5, GREEN, "middle")
    b += text(860, ax_y - 26, "不含！（空心）", 12.5, RED, "middle")
    b += mtext(58, 498, ["长度 4 的轴 ⇔ 合法下标恰是 [0,4)：半开区间与 0-based 下标天作之合（下界取 0 的理由）。",
                          "off-by-one 一格之差：把 to %c4 写成 to %c5 → trip=5，i=4 时 A[4,k] 越界（探针 P1 实测拦截）。"], 11.8, INK, lh=17)

    # 下左：配对表
    b += srect(40, 540, 570, 250, fill="white", stroke=GREEN, sw=2.4)
    b += text(56, 566, "三条循环的配对表（LoopSpec 规格）", 14.5, GREEN)
    cols = [(70, "iv"), (128, "lb"), (188, "ub"), (268, "step"), (360, "trip"), (452, "ub 来源")]
    for x, h in cols:
        b += text(x, 592, h, 11.8, SOFT)
    b += sline(56, 600, 596, 600, SOFT, 1.2, dash="4 4")
    rows = [("%i", "0", "M=4", "1", "4", "A.shape[0]（行数）", GREEN),
            ("%j", "0", "N=3", "1", "3", "B.shape[1]（列数）", BLUE),
            ("%k", "0", "K=6", "1", "6", "内维契约 A.shape[1]==B.shape[0]", ORANGE)]
    y = 622
    for iv, lb, ub, st, tr, src, lc in rows:
        b += text(70, y, iv, 12.5, lc)
        b += text(128, y, lb, 12.5, INK)
        b += text(188, y, ub, 12.5, INK)
        b += text(268, y, st, 12.5, INK)
        b += text(360, y, tr, 12.5, INK)
        b += text(452, y, src, 10.8, INK)
        y += 34
    b += mtext(56, 736, ["配错行的后果 → 图 3 探针 P3：迭代总数不变（3×4×6=72），",
                          "地址空间全错——方阵测试抓不住，非方形才爆。"], 11.3, SOFT, lh=16)

    # 下右：iv 的身份
    b += srect(630, 540, 570, 250, fill="white", stroke=ORANGE, sw=2.4)
    b += text(646, 566, "iv 的身份：区域参数，不是常量", 14.5, ORANGE)
    b += srect(646, 582, 262, 76, fill=L_BLUE, stroke=BLUE, sw=1.8)
    b += mtext(658, 604, ["%c4 = arith.constant 4 : index", "SSA 常量：全程一个值，", "哪里都能用（只要支配）"], 10.8, INK, lh=15)
    b += srect(922, 582, 262, 76, fill=L_ORANGE, stroke=ORANGE, sw=1.8)
    b += mtext(934, 604, ["%i：循环的区域参数", "i=0 → 1 → 2 → 3", "每次迭代重新绑定"], 10.8, INK, lh=15)
    b += mtext(646, 692, ["· 体外不可见：出了循环 region，%i 就不存在（支配性；", "   真实 MLIR 由 verifier 强制，BT3 用结构断言）",
                          "· index 类型：Day 89 地址公式 6·i＋k、3·k＋j 乘的就是它",
                          "· 与 Day 87 的 %acc 同机制：iv 是第一个区域参数，", "   iter_args(%acc=…) 跟在后面——同一个通道"], 11.3, INK, lh=19)
    return svg_doc(W, H, b)


# ============================================================
# 图 3：边界测试——7 组 shape 实测 + 三个注入探针
# ============================================================

def img3() -> str:
    W, H = 1240, 830
    b = title_block(W, "边界测试：7 组 shape 的实测 ＋ 三个注入探针，全部按预期变红",
                    "数据来自 boundary-table.txt 与 BT7（真实运行）——探针是故意注入的 bug，用来验证测试咬得住人")

    # 左：7 组 shape 表
    b += srect(40, 104, 640, 500, fill="white", stroke=GREEN, sw=2.6)
    b += text(56, 130, "7 组 shape 的 trip / IV 轨迹（BT5 实测）", 14.5, GREEN)
    b += text(64, 156, "shape", 11.3, SOFT)
    b += text(214, 156, "trips(i,j,k)", 11.3, SOFT)
    b += text(360, 156, "总迭代", 11.3, SOFT, "middle")
    b += text(452, 156, "IV 值域（i / j / k）", 11.3, SOFT)
    b += sline(56, 164, 664, 164, SOFT, 1.2, dash="4 4")
    rows = [
        ("A(1,1)@B(1,1)", "(1, 1, 1)", "1", "{0} / {0} / {0}", False),
        ("A(1,5)@B(5,3)", "(1, 3, 5)", "15", "{0} / {0,1,2} / {0..4}", False),
        ("A(5,1)@B(1,3)", "(5, 3, 1)", "15", "{0..4} / {0,1,2} / {0}", False),
        ("A(2,3)@B(3,2)", "(2, 2, 3)", "12", "{0,1} / {0,1} / {0,1,2}", False),
        ("A(3,2)@B(2,7)", "(3, 7, 2)", "42", "{0,1,2} / {0..6} / {0,1}", False),
        ("A(4,6)@B(6,3)", "(4, 3, 6)", "72", "{0..3} / {0,1,2} / {0..5}", False),
        ("A(4,0)@B(0,3)", "(4, 3, 0)", "0", "{0..3} / {0,1,2} / ∅", True),
    ]
    y = 186
    for shp, tr, tot, vals, zero in rows:
        col = RED if zero else INK
        b += text(64, y, shp, 12, col)
        b += text(214, y, tr, 12, col)
        b += text(360, y, tot + "  ← 零趟" if zero else tot, 12, col, "middle" if not zero else "start")
        b += text(452, y, vals, 11.5, col)
        y += 30
    b += text(64, y - 4, "全部 PASS：trips = (M,N,K)；k 体总执行 = M×N×K；值域不含 ub", 11.3, GREEN)
    # 零趟特写
    b += srect(56, y + 8, 608, 108, fill=L_RED, stroke=RED, sw=2.0)
    b += text(70, y + 32, "零趟特写 K=0（A(4,0) @ B(0,3)）", 13, RED)
    b += mtext(70, y + 54, ["k 循环 trip = max(0, ceil(0/1)) = 0 → 体一次不执行；%acc 终值 = 初值 0.0",
                            "预演完整 IR：store 12 次（每个 (i,j) 写 0.0）· load 0 次 · 未初始化读 0 次",
                            "数学佐证：空和 = 0（np.matmul((4,0),(0,3)) = 4×3 零矩阵，逐位相同）",
                            "—— Day 87 的「零次迭代 = 初值」今天拿到数学身份：%zero 正是归约的单位元"], 10.8, INK, lh=16)

    # 右：三个探针
    b += srect(700, 104, 500, 500, fill="white", stroke=RED, sw=2.6)
    b += text(716, 130, "反面控制组：三个注入探针（BT7）", 14.5, RED)
    probes = [
        ("P1 off-by-one：i 上界 = M+1 = 5", L_RED, RED,
         ["结构探针红：trip = 5 ≠ M = 4",
          "执行探针红：i=4 时 load %a[4,k]",
          "真实报错：第 0 维下标 4 ∉ [0, 4)",
          "（shape (4,6)）——线性地址 24 也越界"]),
        ("P2 step=2：k 步长 = 2", L_ORANGE, ORANGE,
         ["k 取值 {0,2,4}，每趟 3 次（ceil(6/2)）",
          "load A/B 共 72 次 = 正确 144 的一半",
          "不越界、安静地错：max|C−ref| = 1.939e+00",
          "—— step 不是「精度」参数，漏加全部奇数 k"]),
        ("P3 配对错误：i 界=N、j 界=M", L_RED, RED,
         ["迭代总数不变：3×4×6 = 72 = M×N×K",
          "j 跑到 3（B 的列界外）被按维检查拦下",
          "真实报错：第 1 维下标 3 ∉ [0, 3)",
          "线性地址 3 仍在 18 格缓冲区内——只查线性抓不住！"]),
    ]
    yy = 148
    for title_, lf, lc, lines in probes:
        b += srect(716, yy, 468, 138, fill=lf, stroke=lc, sw=2.0)
        b += text(730, yy + 24, title_, 12.5, lc)
        b += mtext(730, yy + 48, lines, 11, INK, lh=19)
        yy += 152
    b += text(716, yy + 2, "三个探针全红：边界测试咬得住人，才配当 Day 89 填空时的护栏", 11.8, RED)

    # 底部：IV 轨迹证据
    b += srect(40, 624, 1160, 120, fill=L_BLUE, stroke=BLUE, sw=2.4)
    b += text(58, 652, "IV 轨迹证据（BT2，主图 A(4,6)@B(6,3) 解释执行）", 14, BLUE)
    b += mtext(58, 678, ["%i：进入 1 次 · 每趟 4 次迭代 · 取值 {0,1,2,3}        %j：进入 4 次（=M）· 每趟 3 次 · 取值 {0,1,2}",
                          "%k：进入 12 次（=M×N）· 每趟 6 次 · 取值 {0..5}        max(iv) = ub − step：3=4−1 · 2=3−1 · 5=6−1"], 12, INK, lh=21)
    b += text(58, 730, "每趟迭代数 = trip 公式；k 体总执行 72 = M×N×K——半开区间的执行级证据", 11.3, SOFT)
    return svg_doc(W, H, b)


# ============================================================
# 图 4：实测结果——BT1~BT7、关键数字、待填分工
# ============================================================

def img4() -> str:
    W, H = 1240, 790
    b = title_block(W, "实测结果：BT1~BT7 全 PASS——循环四要素钉死，Day 89 可以放心填肉",
                    "环境：Linux aarch64 · Python 3.11.4 · numpy 1.26.4 · 无 MLIR（仿真＋解释执行）——全部真实运行，无估算")

    # 左：今天的 IR 与待填分工
    b += text(40, 112, "今天的 IR（loop-ir.txt，A(4,6)@B(6,3)→C(4,3)）：13 op，头部带规格表", 14.5, SOFT)
    b += srect(40, 126, 560, 300, fill="white", stroke=SOFT, sw=2.2)
    b += mtext(54, 150, ["// 循环规格表（LoopSpec）：",
                          "//   iv   lb  ub  step  trip   ub 来源",
                          "//   %i    0   4    1    4     M = A.shape[0]",
                          "//   %j    0   3    1    3     N = B.shape[1]",
                          "//   %k    0   6    1    6     K = 内维契约",
                          "func @main(%a: memref<4x6…>, %b: memref<6x3…>)",
                          "  %c    = memref.alloc() : 4x3        ← D86",
                          "  %zero = arith.constant 0.0 : f32    ← D87",
                          "  %c0/%c1/%c4/%c3/%c6 = arith.constant ← 四要素素材",
                          "  scf.for %i = %c0 to %c4 step %c1 {  ← lb 含·ub 不含",
                          "    scf.for %j = %c0 to %c3 step %c1 {",
                          "      %acc = scf.for %k = %c0 to %c6 step %c1",
                          "              iter_args(%acc = %zero) -> (f32) {",
                          "        scf.yield %zero : f32          ← 占位回传",
                          "  …                                     ← 每条循环带四要素注释"], 11.6, INK, "start", 18.5)
    b += srect(54, 436, 260, 62, fill=L_GREEN, stroke=GREEN, sw=2.0)
    b += text(66, 456, "今天钉死：四要素＋规格表", 12.5, GREEN)
    b += mtext(66, 474, ["13 op 不变（骨架 10＋D87 初始化 2 = 11 目标 op）", "LoopSpec 单一事实来源＋BT1~BT7 验收"], 10.3, INK, lh=14)
    b += srect(326, 436, 260, 62, fill=L_ORANGE, stroke=ORANGE, sw=2.0)
    b += text(338, 456, "Day 89 待填：访存＋累加（5 op）", 12.5, ORANGE)
    b += mtext(338, 474, ["load×2 ＋ mulf ＋ addf ＋ store", "11 ＋ 5 = 16 目标 op 收官"], 10.3, INK, lh=14)
    b += mtext(54, 528, ["BT2 实测：%acc 终值 0.0；C 零访问——中间态安全，填空接口已就位。"], 11.8, SOFT)

    # 右上：BT1~BT7
    b += text(640, 112, "检查测试 BT1~BT7（真实执行，全部 PASS）", 14.5, SOFT)
    bts = [
        ("BT1 四要素与配对", "13 op；(lb,ub,step)=(0,M/N/K,1)；LoopSpec 出生证明；回滚回归"),
        ("BT2 半开区间与 IV 轨迹", "trip 4/3/6；总迭代 72；max(iv)=ub−step；%acc 终值 0.0"),
        ("BT3 iv 身份与作用域", "index 类型；不是常量；体外无引用；终止器显隐规则"),
        ("BT4 嵌套结构", "深度 3、i→j→k；归约最内（%acc 挂 k）；iv 互不重用"),
        ("BT5 边界 shape 全家福", "7 组 shape 全 PASS；K=0 零趟：%acc=0.0=空和（numpy 佐证）"),
        ("BT6 静态前提", "A(?x6)：四要素无法物化 → 宁拒不猜；partial 显式残留"),
        ("BT7 反面控制组", "P1/P3 按维越界被拦；P2 静默错被数值探针拦——3/3 全红"),
    ]
    y = 132
    for t, m in bts:
        b += srect(640, y, 560, 44, fill="white", stroke=SOFT, sw=1.8)
        b += text(654, y + 18, "PASS", 12.5, GREEN)
        b += text(706, y + 18, t, 13, INK)
        b += text(706, y + 35, m, 10.8, SOFT)
        y += 52

    # 右下：关键数字卡
    b += srect(640, y + 6, 560, 92, fill=L_GREEN, stroke=GREEN, sw=2.2)
    b += text(654, y + 30, "关键数字（全部实测）", 13, GREEN)
    b += mtext(654, y + 52, ["trip = 4/3/6 · 总迭代 72 = 4×3×6 · IV 值域不含 ub（max = ub−step）",
                              "K=0 零趟：12 次 store 写 0.0、0 次 load · 探针拦截 3/3 · P2 静默误差 1.939e+00"], 11.3, INK, lh=19)

    # 底部：口径附注
    b += srect(40, 636, 1160, 100, fill="white", stroke=GREEN, sw=2.4)
    b += text(58, 664, "验收口径（诚实声明）", 14.5, GREEN)
    b += mtext(58, 688, ["今天的验收 = 结构（BT1/BT4）＋执行轨迹（BT2/BT3）＋边界 shape（BT5，循环体仍为空）＋静态前提（BT6）＋反面控制（BT7）。",
                          "scf.for 语义依据官方文档（2026-11 核对）；仿真差异：env 平铺不做运行期支配检查（BT3 用结构断言）；按维越界检测是今天新增的仿真探针。",
                          "端到端数值对照（≥8 组 shape）是 Day 90 的验收；垃圾值是确定性公式，真实语义为未定义行为。"], 12, INK, lh=19)
    return svg_doc(W, H, b)


def main():
    OUT.mkdir(exist_ok=True)
    for name, fn in [("01-overview.svg", img1),
                     ("02-loop-semantics.svg", img2),
                     ("03-boundary-tests.svg", img3),
                     ("04-results.svg", img4)]:
        (OUT / name).write_text(fn(), encoding="utf-8")
        print(f"wrote {OUT / name}")


if __name__ == "__main__":
    main()
