#!/usr/bin/env python3
"""生成第 87 天教程的 4 张手绘风（Excalidraw-like）SVG 技术图。

运行方式：
    python3 make_images.py

输出到 ../images/ 目录：
    01-overview.svg           第 87 天在第四阶段与编译链路中的位置 + 输入与三件产出
    02-memory-semantics.svg   内存语义：tensor 值世界 vs memref 位置世界 + 三策略内存轨迹
    03-iterargs.svg           iter_args 数据流解剖 + 动态维度保守路径
    04-results.svg            实测结果：IT1~IT5、三策略真实数据、待填分工

风格与 Day 78~86 保持一致：手绘抖动线条、马克笔笔触、米白背景、
蓝/橙/绿/红四种柔和强调色、简单几何形状。
图中文字与数字全部来自 init_pass.py 的真实运行结果（outputs/）。
"""

import math
import random
from pathlib import Path

random.seed(87)

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


def sline(x1, y1, x2, y2, stroke=INK, sw=2.2, dash=None, amp=1.3):
    return f'<path d="{jseg(x1, y1, x2, y2, amp)}" {style("none", stroke, sw, dash)}/>'


def head(x, y, ang, stroke, sw, l=13, spread=0.46):
    a1 = (x - l * math.cos(ang - spread), y - l * math.sin(ang - spread))
    a2 = (x - l * math.cos(ang + spread), y - l * math.sin(ang + spread))
    return (f'<path d="{jseg(x, y, a1[0], a1[1], 0.7)}" {style("none", stroke, sw)}/>'
            f'<path d="{jseg(x, y, a2[0], a2[1], 0.7)}" {style("none", stroke, sw)}/>')


def arrow(x1, y1, x2, y2, stroke=INK, sw=2.2, dash=None):
    ang = math.atan2(y2 - y1, x2 - y1)
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
# 图 1：全貌——第四阶段第三步 + 编译链路位置 + 输入与产出
# ============================================================

def img1() -> str:
    W, H = 1200, 710
    b = title_block(W, "第 87 天全貌：填第一块肉——输出初始化",
                    "第四阶段（第 13 周）：在 Day 86 骨架上把「零起点」显式化，alloc 不清零是要点")

    # 上带：阶段地图
    b += srect(40, 100, 480, 96, fill=L_GREEN, stroke=GREEN, sw=2.4)
    b += text(56, 128, "第三阶段 图优化（D57~84）✓ 已收官", 16, INK)
    b += mtext(56, 152, ["五道闸管道：11 → 5 节点的干净 tensor 图", "产出：设计文档＋讲稿＋清单（D84）"], 12.5, SOFT)
    b += arrow(526, 148, 576, 148, SOFT, 2.4)
    b += srect(580, 100, 580, 96, fill=L_ORANGE, stroke=ORANGE, sw=3.0, amp=1.5)
    b += text(596, 126, "第四阶段 Lowering（D85~）", 16, INK)
    steps = [("D85 设计 ✓", "white"), ("D86 骨架 ✓", "white"), ("D87 初始化 ←今天", L_RED), ("D88+ 完整计算", "white")]
    x = 596
    for label, fill in steps:
        w = 132 if fill == "white" else 138
        b += srect(x, 138, w, 30, fill=fill, stroke=ORANGE if fill == "white" else RED,
                   sw=1.8, amp=0.9)
        b += text(x + w / 2, 158, label, 12.5, INK, "middle")
        x += w + 8
    b += text(596, 188, "口号：零起点显式化——%zero ＋ iter_args，正确性从初始化开始", 12.5, SOFT)

    # 中带：编译链路
    b += text(40, 232, "编译链路：今天走到哪一步？", 15, SOFT)
    stages = [
        ("前端\n(mini 图)", "white", SOFT, False),
        ("图优化\nD57~84 ✓", L_GREEN, GREEN, False),
        ("Lowering\nD87 今天", L_ORANGE, ORANGE, True),
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
            b += text(x + bw / 2, y0 - 12, "▼ 今天在这里填初始化 ▼", 13, ORANGE, "middle")
        if i < 4:
            b += arrow(x + bw + 2, y0 + bh / 2, x + bw + gap - 2, y0 + bh / 2, SOFT, 2.0)
    b += mtext(40, 356, ["今天的 Pass 产出「初始化就位、访存留白」的循环 IR：alloc ＋ %zero ＋ iter_args；",
                         "零起点是否显式、动态维度如何保守处理——今天验收；load/store/累加留给 D88。"], 13, SOFT)

    # 下带：输入与产出
    b += text(40, 420, "今天的输入与产出（全部真实运行）", 15, SOFT)
    b += srect(40, 434, 250, 130, fill="white", stroke=SOFT, sw=2.0, dash="6 5")
    b += text(54, 460, "输入：Day 86 骨架＋清单③", 14.5, INK)
    b += mtext(54, 484, ["骨架 12 op（预留注释点名", "  D87 填 %zero＋iter_args）", "＋ Day 85 任务清单③：", "  输出初始化三方案对照"], 11.8, INK, lh=18)
    outs = [
        ("产出 1：初始化 IR", "init-ir.txt", "3 op → 13 op，预留标注 D88", L_BLUE, BLUE),
        ("产出 2：检查测试", "test-report.txt", "IT1~IT5 全部真实执行：5/5 PASS", L_GREEN, GREEN),
        ("产出 3：调试树", "debug-log.txt", "3 案例：主图/动态拒绝/回滚", L_ORANGE, ORANGE),
    ]
    x0, bw, gap = 312, 268, 22
    for i, (t, f, m, lf, lc) in enumerate(outs):
        x = x0 + i * (bw + gap)
        b += srect(x, 434, bw, 130, fill=lf, stroke=lc, sw=2.4)
        b += text(x + 14, 462, t, 15, INK)
        b += text(x + 14, 488, f, 13, lc)
        b += mtext(x + 14, 512, [m], 12, INK)
        b += text(x + 14, 552, "outputs/ 里可查", 11.5, SOFT)
    b += arrow(292, 499, 310, 499, SOFT, 2.2)

    # 底部：为什么初始化值得单独一天
    b += srect(40, 592, 1120, 86, fill="white", stroke=RED, sw=2.2, dash="8 6")
    b += text(58, 620, "为什么初始化值得单独一天？", 14.5, RED)
    b += mtext(58, 644, ["memref.alloc 是 malloc 不是 calloc——分配的 48 B 里是什么，IR 层没有任何保证；", "不初始化就做读改写＝未定义行为（今天实测 12 次未初始化读、误差 8.5e+02）——正确性从零起点开始。"], 12.5, INK, lh=20)
    return svg_doc(W, H, b)


# ============================================================
# 图 2：内存语义——两个世界 + alloc 不清零 + 三策略内存轨迹
# ============================================================

def img2() -> str:
    W, H = 1240, 830
    b = title_block(W, "内存语义：alloc 不清零，零起点必须显式——三种初始化策略的内存轨迹",
                    "tensor 世界里每个值都有定义；memref 世界里 alloc 只给地址不给值（malloc ≠ calloc）")

    # 左上：两个世界
    b += srect(40, 104, 560, 210, fill="white", stroke=SOFT, sw=2.4)
    b += text(56, 130, "两个世界：值有定义 vs 位置有垃圾", 15, INK)
    b += srect(56, 146, 262, 88, fill=L_GREEN, stroke=GREEN, sw=2.0)
    b += text(68, 168, "tensor 世界（Day 83 前）", 13, GREEN)
    b += mtext(68, 190, ["%mm = mini.matmul(%x, %w)", "——每个值都有定义：", "函数式，读了一定有语义"], 11.5, INK, lh=17)
    b += srect(334, 146, 252, 88, fill=L_RED, stroke=RED, sw=2.0)
    b += text(346, 168, "memref 世界（Day 85 起）", 13, RED)
    b += mtext(346, 190, ["%c = memref.alloc() : 4x3", "——只给地址不给值：", "48 B 里是「？」（垃圾）"], 11.5, INK, lh=17)
    b += mtext(56, 258, ["类比：tensor 像「带出生证明的人」——名字背后必有来历；memref.alloc 像「毛坯房」——",
                         "钥匙给你了，屋里有什么没人知道。对应到技术上是：SSA 值由 op 定义；", "内存位置由 alloc 分配，内容未定义（除非被 fill/store 写过）。"], 11.8, SOFT, lh=17)

    # 右上：C 的 12 格
    b += srect(630, 104, 570, 210, fill=L_ORANGE, stroke=ORANGE, sw=2.6)
    b += text(646, 130, "%c 的 48 B（alloc 之后、初始化之前）", 15, INK)
    gx, gy, cw, ch = 646, 148, 52, 40
    for i in range(12):
        r, c = divmod(i, 4)
        x, y = gx + c * (cw + 6), gy + r * (ch + 6)
        b += srect(x, y, cw, ch, fill="white", stroke=RED, sw=1.8, amp=0.8)
        b += text(x + cw / 2, y + 26, "?", 17, RED, "middle")
        b += text(x + 4, y + 13, f"{777 + 7 * i}", 8.5, SOFT)
    b += mtext(905, 168, ["垃圾值（仿真，确定性）：", "garbage(addr)", "  = 777 + 7·addr", "真实语义＝未定义行为", "",
                          "alloc ＝ malloc ≠ calloc", "想清零？必须显式 ↓"], 11.8, INK, lh=19)

    # 下：三策略内存轨迹（泳道）
    b += text(40, 344, "三种初始化策略的内存轨迹（IT3 实测，A(4,6)@B(6,3)）", 15, SOFT)
    lanes = [
        ("方案 B（选定）", GREEN, L_GREEN,
         ["%zero = 0.0（SSA 常量）", "iter_args(%acc = %zero)", "C：零读 · 零 fill · 每元素只写 1 次"],
         "未初始化读 0 次 · 位等价 · ＋0 B"),
        ("方案 A（fill）", BLUE, L_BLUE,
         ["memref.fill %zero, %c（12 格写 0）", "初值 = load C[i,j]（读 fill 过的 0）", "C：1 fill · 1 读 · 1 写"],
         "未初始化读 0 次 · 位等价 · ＋96 B"),
        ("什么都不做", RED, L_RED,
         ["没有 fill，也没有 %zero", "初值 = load C[i,j]（读垃圾 777…）", "C：未初始化读 ×12 · 结果被污染"],
         "未初始化读 12 次 · max|diff| = 8.5e+02"),
    ]
    y = 362
    for name, lc, lf, cells, verdict in lanes:
        b += srect(40, y, 700, 118, fill=lf, stroke=lc, sw=2.4)
        b += text(56, y + 26, name, 14.5, lc)
        b += mtext(56, y + 50, cells, 12, INK, lh=19)
        b += text(56, y + 106, f"实测：{verdict}", 12, lc)
        y += 130
    # 右侧：iter_args 初值分叉示意
    b += srect(770, 362, 430, 368, fill="white", stroke=ORANGE, sw=2.4)
    b += text(786, 388, "三策略的差别只有一个：iter_args 初值来自哪里", 13.5, INK)
    b += mtext(786, 416, ["scf.for %k ... iter_args(%acc = ???)", "",
                          "B   ：%zero        ← SSA 常量（零起点在「值」里）",
                          "A   ：load C[i,j]  ← 内存（fill 保证了 0.0）",
                          "none：load C[i,j]  ← 内存（没 fill——垃圾）"], 12, INK, lh=21)
    b += mtext(786, 530, ["零起点放在哪里？", "  · 放内存里 → 必须先写后读（fill 付 12 格写流量）",
                          "  · 放 SSA 值里 → C 只写不读，零起点白拿（方案 B 赢）",
                          "", "Day 85 清单③的结论，今天在 IR 层逐位复现（IT3）。"], 11.8, SOFT, lh=18)
    return svg_doc(W, H, b)


# ============================================================
# 图 3：iter_args 数据流解剖 + 动态维度保守路径
# ============================================================

def img3() -> str:
    W, H = 1240, 810
    b = title_block(W, "iter_args：循环携带值的解剖——零起点怎么进循环、部分和怎么出来",
                    "scf.for 的 iter_args(%acc = %zero) -> (f32) ＋ scf.yield 的回传；体内 %acc ≠ 体外 %acc")

    # 左：iter_args 数据流
    b += srect(40, 104, 700, 400, fill="white", stroke=BLUE, sw=2.6)
    b += text(56, 130, "数据流：%zero → 循环 → %acc（今天的占位 vs Day 88 的完整）", 14.5, INK)
    # 初值
    b += srect(70, 152, 150, 46, fill=L_GREEN, stroke=GREEN, sw=2.0)
    b += text(145, 180, "%zero = 0.0", 13, INK, "middle")
    b += arrow(222, 175, 292, 175, GREEN, 2.2)
    b += text(257, 163, "初值", 11.5, GREEN, "middle")
    # 循环框
    b += srect(296, 146, 240, 320, fill=L_BLUE, stroke=BLUE, sw=2.4)
    b += text(416, 170, "scf.for %k = %c0 to %c6", 12.5, INK, "middle")
    b += text(416, 190, "iter_args(%acc = %zero)", 12.5, INK, "middle")
    b += text(416, 210, "-> (f32)", 12.5, INK, "middle")
    # 体内展开（两次迭代示意）
    b += srect(312, 226, 208, 66, fill="white", stroke=SOFT, sw=1.8)
    b += mtext(322, 248, ["k=0：体内 %acc ← 0.0", "  今天：yield %zero（占位）", "  D88：yield %s=addf(%acc,%p)"], 10.8, INK, lh=15)
    b += arrow(416, 292, 416, 312, SOFT, 1.8)
    b += srect(312, 316, 208, 66, fill="white", stroke=SOFT, sw=1.8)
    b += mtext(322, 338, ["k=1：体内 %acc ← 上次 yield", "  今天：还是 %zero（恒等）", "  D88：新的部分和"], 10.8, INK, lh=15)
    b += text(416, 400, "…k=5 后循环结束…", 11, SOFT, "middle")
    b += text(416, 434, "零次迭代（ub==lb）→ 结果 = 初值", 11, BLUE, "middle")
    # 结果
    b += arrow(538, 175, 608, 175, BLUE, 2.2)
    b += text(573, 163, "结果", 11.5, BLUE, "middle")
    b += srect(612, 152, 110, 46, fill=L_BLUE, stroke=BLUE, sw=2.0)
    b += text(667, 180, "%acc", 13, INK, "middle")
    # 两个 %acc 辨析
    b += srect(70, 240, 200, 130, fill=L_ORANGE, stroke=ORANGE, sw=2.0)
    b += text(82, 262, "两个 %acc，同名不同值！", 12, ORANGE)
    b += mtext(82, 284, ["体内 %acc：iter_args 的", "区域参数——每次迭代", "重新绑定（上次 yield）",
                         "", "体外 %acc：循环结果——", "最后一次 yield 的值"], 10.8, INK, lh=15)
    b += carrow((270, 370), (330, 400), (416, 380), ORANGE, 1.8)
    b += mtext(70, 396, ["SSA 不许「循环里改一个变量」，iter_args/yield 就是它给",
                         "「循环携带状态」开的显式通道：初值进门、新值回传、", "终值出门——全程没有内存，全在值的世界里。"], 11.8, INK, lh=17)

    # 右：动态维度保守路径
    b += srect(770, 104, 430, 400, fill="white", stroke=RED, sw=2.4)
    b += text(786, 130, "动态维度的保守路径（IT4 实测）", 14.5, RED)
    b += srect(786, 148, 190, 100, fill=L_GREEN, stroke=GREEN, sw=2.0)
    b += text(798, 170, "静态 shape（今天）", 12.5, GREEN)
    b += mtext(798, 192, ["A(4,6) @ B(6,3)", "边界/类型编译期全知：", "%c4/%c3/%c6 常量＋", "alloc 4x3 定型"], 11, INK, lh=15)
    b += srect(994, 148, 190, 100, fill=L_RED, stroke=RED, sw=2.0)
    b += text(1006, 170, "动态 '?'（保守拒绝）", 12.5, RED)
    b += mtext(1006, 192, ["A(?x6) @ B(6,3)", "M 编译期未知：alloc 类型", "写不出、%cM 无从产生", "→ 宁拒不猜"], 11, INK, lh=15)
    b += mtext(786, 276, ["签名转换不拦：tensor<?x6> → memref<?x6, strided<[6,1]>>", "（strides 仍可知）；拦截发生在 Pattern 的 match：", "",
                          "  } -> FAILURE : 动态维度（A('?', 6) @ B(6, 3)）：",
                          "    alloc 类型与循环边界无法编译期确定，本 Pattern",
                          "    只接静态 shape——保守路径，宁拒不猜"], 11, INK, lh=17)
    b += srect(786, 388, 398, 96, fill=L_BLUE, stroke=BLUE, sw=2.0)
    b += mtext(798, 410, ["full：整体失败（点名 mini.matmul）；partial：显式残留，", "交给后续 Pass。", "真实编译器的分工：动态版 Pattern 用 memref.dim ＋",
                          "动态 alloc；静态版专走常量快路径——拒绝也是调度手段。"], 11, INK, lh=16)

    # 底部：今天的 IR 关键段
    b += srect(40, 530, 1160, 106, fill=L_GREEN, stroke=GREEN, sw=2.4)
    b += text(58, 558, "今天 Pattern 产出的关键段（init-ir.txt）", 14.5, GREEN)
    b += mtext(58, 582, ["%zero = arith.constant 0.0 : f32                        ← 任务③ 1/2：零起点是 SSA 值",
                         "%acc = scf.for %k = %c0 to %c6 step %c1",
                         "        iter_args(%acc = %zero) -> (f32) {              ← 任务③ 2/2：累加器初值挂上循环",
                         "  scf.yield %zero : f32                                  ← 占位：恒等循环；D88 换成 yield %s"], 12, INK, lh=19)
    return svg_doc(W, H, b)


# ============================================================
# 图 4：实测结果——IT1~IT5、三策略数据、待填分工
# ============================================================

def img4() -> str:
    W, H = 1240, 790
    b = title_block(W, "实测结果：IT1~IT5 全 PASS——零起点显式化，垃圾读数为零",
                    "环境：Linux aarch64 · Python 3.11.4 · numpy 1.26.4 · 无 MLIR（仿真＋解释执行）——全部真实运行，无估算")

    # 左：今天的 IR 与待填分工
    b += text(40, 112, "今天的 IR（init-ir.txt，A(4,6)@B(6,3)→C(4,3)）：3 op → 13 op", 15, SOFT)
    b += srect(40, 126, 560, 300, fill="white", stroke=SOFT, sw=2.2)
    b += mtext(54, 150, ["func @main(%a: memref<4x6…>, %b: memref<6x3…>)",
                         "  %c    = memref.alloc() : memref<4x3…>   ← 骨架（D86）",
                         "  %zero = arith.constant 0.0 : f32        ← 今天新填 ✓",
                         "  %c0/%c1/%c4/%c3/%c6 = arith.constant    ← 骨架（D86）",
                         "  scf.for %i = %c0 to %c4 step %c1 {",
                         "    scf.for %j = %c0 to %c3 step %c1 {",
                         "      %acc = scf.for %k = %c0 to %c6 step %c1",
                         "              iter_args(%acc = %zero) -> (f32) {",
                         "        scf.yield %zero : f32              ← 占位回传",
                         "      }",
                         "    }",
                         "  }",
                         "  return %c"], 12, INK, "start", 19)
    b += srect(54, 436, 260, 62, fill=L_GREEN, stroke=GREEN, sw=2.0)
    b += text(66, 456, "今天已填：初始化（2 op）", 12.5, GREEN)
    b += mtext(66, 474, ["%zero ＋ iter_args 升级", "骨架 10 ＋ 2 = 11 目标 op"], 11, INK, lh=15)
    b += srect(326, 436, 260, 62, fill=L_ORANGE, stroke=ORANGE, sw=2.0)
    b += text(338, 456, "Day 88 待填：访存＋累加（5 op）", 12.5, ORANGE)
    b += mtext(338, 474, ["load×2 ＋ mulf ＋ addf ＋ store", "11 ＋ 5 = 16 目标 op 收官"], 11, INK, lh=15)
    b += mtext(54, 528, ["IT2 实测：恒等循环 %acc ≡ 0.0；C 零访问（load/store/fill = 0）——中间态安全。"], 11.8, SOFT)

    # 右上：IT1~IT5
    b += text(640, 112, "检查测试 IT1~IT5（真实执行，全部 PASS）", 15, SOFT)
    dts = [
        ("IT1 初始化结构", "13 op；%zero 就位；iter_args(%acc=%zero)->(f32)；yield %zero"),
        ("IT2 占位语义", "解释执行：%acc 终值 0.0；C 零访问；未初始化读 0 次"),
        ("IT3 三策略内存语义", "B/A 位等价＋0 次垃圾读；none 12 次垃圾读＋误差 8.5e+02"),
        ("IT4 动态保守路径", "A(?x6)：full 失败、原因进调试树；partial 显式残留"),
        ("IT5 事务性回归", "回滚后终图与只用 Init 逐字相同；失败后 IR 与转换前一致"),
    ]
    y = 132
    for t, m in dts:
        b += srect(640, y, 560, 44, fill="white", stroke=SOFT, sw=1.8)
        b += text(654, y + 18, "PASS", 12.5, GREEN)
        b += text(706, y + 18, t, 13, INK)
        b += text(706, y + 35, m, 11.3, SOFT)
        y += 52

    # 右下：三策略对照数据
    b += text(640, y + 8, "三策略对照（IT3 真实数据，种子 87）", 15, SOFT)
    b += srect(640, y + 22, 560, 118, fill="white", stroke=ORANGE, sw=2.2)
    rows = [
        ("方案 B（选定）", "0 次", "0.0e+00", "＋0 B", GREEN),
        ("方案 A（fill）", "0 次", "0.0e+00", "＋96 B", BLUE),
        ("什么都不做", "12 次", "8.540e+02", "—（UB）", RED),
    ]
    yy = y + 46
    b += text(654, yy - 16, "策略", 11.5, SOFT)
    b += text(790, yy - 16, "未初始化读", 11.5, SOFT, "middle")
    b += text(910, yy - 16, "max|C-ref|", 11.5, SOFT, "middle")
    b += text(1050, yy - 16, "额外流量", 11.5, SOFT, "middle")
    for name, reads, diff, traffic, lc in rows:
        b += sline(654, yy - 8, 1186, yy - 8, SOFT, 1.0, dash="3 4")
        b += text(654, yy + 8, name, 12, lc)
        b += text(790, yy + 8, reads, 12, INK, "middle")
        b += text(910, yy + 8, diff, 12, INK, "middle")
        b += text(1050, yy + 8, traffic, 12, INK, "middle")
        yy += 30
    b += text(654, yy + 6, "口径：参考实现与循环 IR 严格同序（i/j/k ＋ float32 舍入）→ 位等价可判", 11, SOFT)

    # 底部：口径附注
    b += srect(40, 636, 1160, 88, fill="white", stroke=GREEN, sw=2.4)
    b += text(58, 664, "验收口径（诚实声明）", 14.5, GREEN)
    b += mtext(58, 688, ["今天的验收 = 结构（IT1）＋中间态语义（IT2）＋初始化内存语义（IT3，用手工预演的完整 IR）＋保守路径（IT4）＋事务回归（IT5）。",
                         "数值执行的完整验收（Pattern 自动产出 load/store 后的位等价）在 Day 88 收官；垃圾值是确定性公式，真实语义为未定义行为。"], 12.3, INK, lh=20)
    return svg_doc(W, H, b)


def main():
    OUT.mkdir(exist_ok=True)
    for name, fn in [("01-overview.svg", img1),
                     ("02-memory-semantics.svg", img2),
                     ("03-iterargs.svg", img3),
                     ("04-results.svg", img4)]:
        (OUT / name).write_text(fn(), encoding="utf-8")
        print(f"wrote {OUT / name}")


if __name__ == "__main__":
    main()
