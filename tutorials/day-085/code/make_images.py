#!/usr/bin/env python3
"""生成第 85 天教程的 4 张手绘风（Excalidraw-like）SVG 技术图。

运行方式：
    python3 make_images.py

输出到 ../images/ 目录：
    01-overview.svg           第 85 天在第四阶段与编译链路中的位置 + 三件产出
    02-dialect-conversion.svg DialectConversion 四角色协作（源/目标 op 职责）
    03-lowering-steps.svg     S0→S4 转换步骤 + 三张任务清单（当天实践主图）
    04-results.svg            实测结果：初始化三策略对照 + 探针矩阵

风格与 Day 78~84 保持一致：手绘抖动线条、马克笔笔触、米白背景、
蓝/橙/绿/红四种柔和强调色、简单几何形状。
图中数值全部来自 lowering_design.py 的真实运行结果（outputs/test-report.txt）。
"""

import math
import random
from pathlib import Path

random.seed(85)

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


def chip(x, y, label, fill, w=None, h=25, size=13.5):
    w = w or (len(label) * (size * 0.62) + 16)
    body = srect(x, y, w, h, fill=fill, stroke=fill, sw=1.6, amp=0.9)
    body += text(x + w / 2, y + h * 0.72, label, size, INK, "middle")
    return body


def title_block(w, title, sub=None):
    body = text(30, 44, title, 25, INK)
    if sub:
        body += text(30, 70, sub, 14.5, SOFT)
    body += sline(30, 82, w - 30, 82, SOFT, 1.6, dash="7 6")
    return body


# ============================================================
# 图 1：全貌——第四阶段开工 + 编译链路位置 + 三件产出
# ============================================================

def img1() -> str:
    W, H = 1200, 700
    b = title_block(W, "第 85 天全貌：Lowering 开工第一天——不写代码，先画施工图",
                    "第四阶段（第 13 周）：把图优化器交付的 tensor 图翻译成硬件认识的循环＋内存")

    # 上带：阶段地图
    b += srect(40, 100, 500, 92, fill=L_GREEN, stroke=GREEN, sw=2.4)
    b += text(56, 128, "第三阶段 图优化（D57~84）✓ 已收官", 16, INK)
    b += text(56, 154, "Shape/Layout · 融合收益 · 数值验证 · 五道闸管道", 13, SOFT)
    b += text(56, 178, "产出：11→5 节点的干净 tensor 图", 13, SOFT)
    b += arrow(546, 146, 596, 146, SOFT, 2.4)
    b += srect(600, 100, 560, 92, fill=L_ORANGE, stroke=ORANGE, sw=3.0, amp=1.5)
    b += text(616, 128, "第四阶段 Lowering（D85~）← 今天", 16, INK)
    b += text(616, 154, "D85 设计路线（今天）→ D86 骨架 → D87+ 填肉", 13, INK)
    b += text(616, 178, "口号：先画施工图，再动工——返工比设计贵", 13, SOFT)

    # 中带：编译链路
    b += text(40, 232, "编译链路：今天走到哪一步？", 15, SOFT)
    stages = [
        ("前端\n(mini 图)", "white", SOFT, False),
        ("图优化\nD57~84 ✓", L_GREEN, GREEN, False),
        ("Lowering\nD85 今天", L_ORANGE, ORANGE, True),
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
            b += text(x + bw / 2, y0 - 12, "▼ 今天在这里画路线 ▼", 13, ORANGE, "middle")
        if i < 4:
            b += arrow(x + bw + 2, y0 + bh / 2, x + bw + gap - 2, y0 + bh / 2, SOFT, 2.0)
    b += mtext(40, 358, [
        "图优化（第二站）产出的是 tensor：值语义、无地址、无循环——机器不认识；",
        "Lowering（第三站）产出 memref＋scf.for：一块内存的读法＋命令式循环——机器的母语。"], 13, SOFT)

    # 下带：今天三件产出
    b += text(40, 428, "今天的输入与产出（全部真实运行）", 15, SOFT)
    b += srect(40, 442, 250, 118, fill="white", stroke=SOFT, sw=2.0, dash="6 5")
    b += text(54, 468, "输入：S0 源图", 14.5, INK)
    b += mtext(54, 492, ["@main(%x: tensor<4x6xf32>,",
                         "      %w: tensor<6x3xf32>)",
                         "  %c = mini.matmul(%x, %w)",
                         "  return %c"], 11.5, INK)
    outs = [
        ("产出 1：设计文档", "三张任务清单（类型/索引/初始化）", "＋ S0→S4 路线 ＋ 角色职责表", L_BLUE, BLUE),
        ("产出 2：测试计划", "TP1~TP6 全部真实执行：6/6 PASS", "＋ 3 个探针证明计划咬得住人", L_GREEN, GREEN),
        ("产出 3：循环 IR", "ir-loop.txt：alloc + 三重循环", "＋ load/store，地址显式可查", L_ORANGE, ORANGE),
    ]
    x0, bw, gap = 310, 268, 22
    for i, (t, m1, m2, lf, lc) in enumerate(outs):
        x = x0 + i * (bw + gap)
        b += srect(x, 442, bw, 118, fill=lf, stroke=lc, sw=2.4)
        b += text(x + 14, 470, t, 15, INK)
        b += text(x + 14, 496, m1, 12.5, INK)
        b += text(x + 14, 520, m2, 12.5, INK)
        b += text(x + 14, 545, "outputs/ 里可查", 11.5, SOFT)

    b += srect(40, 590, 1120, 76, fill="white", stroke=BLUE, sw=2.2, dash="8 6")
    b += text(58, 620, "为什么先设计再动手？", 14.5, BLUE)
    b += mtext(58, 644, [
        "MLIR 的 DialectConversion 有四个互相咬合的角色（目标/类型/规则/驱动器），漏画一个，",
        "第 86 天写骨架时就会在中途状态、失败模式上返工——今天的施工图就是明天的填空题。"], 12.5, INK)
    return svg_doc(W, H, b)


# ============================================================
# 图 2：DialectConversion 四角色协作机制
# ============================================================

def img2() -> str:
    W, H = 1200, 780
    b = title_block(W, "DialectConversion：一次有目标的翻译，由四个角色咬合完成",
                    "驱动器反复改写非法 op，直到 ConversionTarget 清单全绿——或 full 模式整体失败")

    # 左：源图（tensor 世界）
    b += srect(40, 104, 300, 300, fill="white", stroke=SOFT, sw=2.4)
    b += text(56, 132, "源图 S0：tensor 世界", 15.5, INK)
    b += mtext(56, 158, ["@main(%x: tensor<4x6xf32>,", "      %w: tensor<6x3xf32>)"], 11.5, INK)
    b += srect(66, 186, 200, 42, fill=L_RED, stroke=RED, sw=2.2)
    b += text(76, 212, "%c = mini.matmul", 13.5, INK)
    b += mtext(76, 250, ["return %c : tensor<4x3xf32>"], 11.5, INK)
    b += srect(56, 270, 268, 56, fill="white", stroke=RED, sw=1.8, dash="5 4")
    b += text(70, 292, "源 op 的职责：提供语义", 13, RED)
    b += mtext(70, 312, ["操作数类型/shape、内维契约", "(4,6)×(6,3)、结果类型"], 11.5, SOFT)
    b += text(56, 352, "mini 方言 = 非法（必须消失）", 12.5, RED)
    b += text(56, 374, "转换完成后被替换、擦除", 12, SOFT)

    # 中：驱动器 + 合法性清单
    b += srect(380, 104, 400, 168, fill=L_BLUE, stroke=BLUE, sw=2.6)
    b += text(396, 132, "驱动器（applyFull / applyPartial）", 15, INK)
    b += mtext(396, 158, ["工作列表：发现非法 op → 查 Pattern → 改写 →", "再扫一遍，直到没有非法 op（或失败）"], 12.5, INK)
    b += srect(396, 184, 180, 44, fill="white", stroke=BLUE, sw=2.0)
    b += text(406, 202, "full 模式", 13, BLUE)
    b += text(406, 220, "剩 1 个非法 → 整体失败", 11.5, INK)
    b += srect(590, 184, 176, 44, fill="white", stroke=BLUE, sw=2.0)
    b += text(600, 202, "partial 模式", 13, BLUE)
    b += text(600, 220, "允许残留给后续 Pass", 11.5, INK)
    b += mtext(396, 252, ["实测：主图 3 op → 14 op，全绿；", "mini.conv（无 Pattern）full 失败 / partial 残留"], 12, GREEN)

    # ConversionTarget 清单
    b += srect(380, 300, 400, 150, fill="white", stroke=GREEN, sw=2.6)
    b += text(396, 326, "ConversionTarget：合法性清单", 15, INK)
    b += mtext(396, 352, ["合法（终图允许出现）：", "  func · memref.alloc/fill/load/store", "  scf.for/yield · arith.constant/mulf/addf", "  bufferization.to_tensor/to_memref"], 12, INK)
    b += text(396, 436, "清单 = 「降级完成」的定义，验收就看它", 12.5, GREEN)

    # TypeConverter
    b += srect(380, 476, 400, 132, fill=L_ORANGE, stroke=ORANGE, sw=2.6)
    b += text(396, 502, "TypeConverter：类型也要降级", 15, INK)
    b += mtext(396, 528, ["convertType: tensor<4x6xf32>", "   → memref<4x6xf32, strided<[6,1]>>"], 12, INK)
    b += srect(396, 552, 176, 42, fill="white", stroke=ORANGE, sw=1.8)
    b += text(404, 568, "物化钩子①", 12, ORANGE)
    b += text(404, 586, "to_memref: tensor→memref", 11, INK)
    b += srect(586, 552, 180, 42, fill="white", stroke=ORANGE, sw=1.8)
    b += text(594, 568, "物化钩子②", 12, ORANGE)
    b += text(594, 586, "to_tensor: memref→tensor", 11, INK)
    b += text(396, 604, "缝合「半 tensor 半 memref」的中途状态（TP5 实测）", 11.5, SOFT)

    # 右：目标 op
    b += srect(820, 104, 340, 300, fill=L_GREEN, stroke=GREEN, sw=2.4)
    b += text(836, 132, "目标 op：循环＋内存世界", 15.5, INK)
    b += mtext(836, 158, ["%c = memref.alloc()  (48 B)", "%zero = arith.constant 0.0", "scf.for %i = 0 to 4 {", "  scf.for %j = 0 to 3 {", "    %acc = scf.for %k = 0 to 6", "      iter_args(%acc = %zero)", "      load %a[%i,%k] · load %b[%k,%j]", "      mulf → addf → yield", "    store %c[%i,%j]"], 11.5, INK)
    b += srect(836, 318, 308, 70, fill="white", stroke=GREEN, sw=1.8, dash="5 4")
    b += text(850, 340, "目标 op 的职责（三条都要满足）", 12.5, GREEN)
    b += mtext(850, 360, ["① 在 ConversionTarget 里合法", "② 类型经过 TypeConverter 认可", "③ 组合后与源 op 数值等价（TP 验收）"], 11.5, INK)
    b += text(836, 408, "Pattern = 读源 op，写目标 op", 12.5, SOFT)
    b += text(836, 428, "（matchAndRewrite：adaptor 给出", 11.5, SOFT)
    b += text(836, 446, "  已转换类型的操作数）", 11.5, SOFT)

    # 连接箭头
    b += arrow(344, 254, 376, 254, SOFT, 2.4)
    b += text(360, 240, "改写", 12, SOFT, "middle")
    b += arrow(784, 254, 816, 254, SOFT, 2.4)
    b += carrow((580, 476), (560, 430), (580, 454), ORANGE, 2.0, dash="6 4")
    b += carrow((380, 540), (330, 470), (300, 408), ORANGE, 2.0, dash="6 4")
    b += text(316, 470, "签名降级", 11.5, ORANGE)

    # 底部：失败模式真实输出
    b += srect(40, 640, 1120, 104, fill="white", stroke=RED, sw=2.2)
    b += text(58, 668, "失败模式也是设计（真实输出）：", 14.5, RED)
    b += mtext(58, 692, ["含 mini.conv 的变体（还没写规则）：full 模式 → 整体失败：", "  无法合法化 'mini.conv'：没有注册对应的 ConversionPattern（模式=full，整体失败）", "partial 模式 → 成功但显式残留 ['mini.conv']，交给后续 Pass——失败要大声，不能悄悄吞掉。"], 12.5, INK)
    return svg_doc(W, H, b)


# ============================================================
# 图 3：S0→S4 转换步骤 + 三张任务清单（实践主图）
# ============================================================

def img3() -> str:
    W, H = 1240, 810
    b = title_block(W, "mini.matmul → 循环表示：S0→S4 五步路线＋三张任务清单",
                    "贯穿例子：A(4,6) @ B(6,3) → C(4,3)，种子 85——所有数字来自真实运行")

    cols = [
        ("S0 原图", "tensor 世界", ["@main(%x: tensor<4x6>,", "      %w: tensor<6x3>)", "%c = mini.matmul(%x,%w)", "return %c"], "white", SOFT, "声明式：只说做什么"),
        ("S1 签名降级", "TypeConverter", ["入参 tensor → memref", "%a: memref<4x6,", "   strided<[6,1]>", "%b: memref<6x3,", "   strided<[3,1]>", "体内还没动"], L_BLUE, BLUE, "convertType"),
        ("S2 核心改写", "ConversionPattern", ["%c = memref.alloc()", "scf.for %i 0..4", " scf.for %j 0..3", "  %acc = for %k 0..6", "   load · mulf · addf", "  store %c[%i,%j]", "mini.matmul 消失"], L_ORANGE, ORANGE, "matchAndRewrite"),
        ("S3 边界缝合", "物化钩子", ["return 要 tensor，", "手里只有 memref", "→ bufferization", "   .to_tensor %c", "缝上中途状态"], L_GREEN, GREEN, "to_tensor"),
        ("S4 合法性验收", "ConversionTarget", ["终图 ∩ 非法集", "     = ∅  ✓", "3 op → 14 op", "mini 方言清零", "（full 模式）"], L_GREEN, GREEN, "全绿才算完成"),
    ]
    x0, y0, bw, bh, gap = 40, 104, 210, 250, 22
    for i, (t, who, lines, lf, lc, note) in enumerate(cols):
        x = x0 + i * (bw + gap)
        b += srect(x, y0, bw, bh, fill=lf, stroke=lc, sw=2.6 if i == 2 else 2.2)
        b += text(x + 14, y0 + 28, t, 15, INK)
        b += chip(x + 14, y0 + 40, who, "white" if i else BG, size=11.5)
        b += mtext(x + 14, y0 + 96, lines, 11.2, INK, lh=16.5)
        b += text(x + 14, y0 + bh - 14, note, 11.5, SOFT)
        if i < 4:
            b += arrow(x + bw + 1, y0 + bh / 2, x + bw + gap - 1, y0 + bh / 2, SOFT, 2.2)

    # 三张任务清单便签
    b += text(40, 402, "S2 动手前必须填好的三张任务清单（实践的核心交付）：", 15, SOFT)

    # 便签 1：类型任务
    b += srect(40, 418, 360, 178, fill=L_BLUE, stroke=BLUE, sw=2.4)
    b += text(56, 446, "① 类型任务（TypeConverter）", 14.5, INK)
    b += mtext(56, 472, ["%x  tensor<4x6xf32> → memref<4x6,", "                        strided<[6,1]>  96 B", "%w  tensor<6x3xf32> → memref<6x3,", "                        strided<[3,1]>  72 B", "%c  tensor<4x3xf32> → alloc 48 B", "shape/元素类型不变，只换「读法」"], 11.8, INK, lh=17.5)

    # 便签 2：索引任务
    b += srect(424, 418, 380, 178, fill=L_ORANGE, stroke=ORANGE, sw=2.4)
    b += text(440, 446, "② 索引任务（地址＋边界）", 14.5, INK)
    b += mtext(440, 472, ["A[i,k]: addr = 6·i + 1·k   i∈[0,4) ← A.shape[0]", "B[k,j]: addr = 3·k + 1·j   j∈[0,3) ← B.shape[1]", "C[i,j]: addr = 3·i + 1·j   k∈[0,6) ← 内维契约", "探针 (i=3,j=2,k=5): addr = 23 / 17 / 11", "vs numpy ravel_multi_index 全部 ✓"], 11.8, INK, lh=17.5)

    # 便签 3：初始化任务
    b += srect(828, 418, 372, 178, fill=L_GREEN, stroke=GREEN, sw=2.4)
    b += text(844, 446, "③ 输出初始化任务（alloc 不清零）", 14.5, INK)
    b += mtext(844, 472, ["A fill 0＋读改写：位等价，＋96 B 流量", "B iter_args(%acc=0.0)：位等价，＋0 B", "  ✓ 选定（寄存器累加，只写一次）", "什么都不做：垃圾值起步 = 未定义行为", "  （探针 P2 实测 max|diff| = 777.0001）"], 11.8, INK, lh=17.5)

    # 底部：设计备注
    b += srect(40, 626, 1160, 150, fill="white", stroke=SOFT, sw=2.0, dash="7 5")
    b += text(58, 654, "两条设计备注（衔接前后的天）", 14.5, SOFT)
    b += mtext(58, 680, ["1. Day 83 终图剩下的 reshape((24,)→(4,6)) 在 Lowering 里免费：24 元素连续存储，重排只是", "   strides=[6,1] 的元信息改写，零搬运（Day 84 补讲 1 的 shares_memory=True 已证明）→ 选做挑战。", "2. Day 86 把 S2 从「规则表」变成真正的 ConversionPattern 骨架（ConversionPatternRewriter 的", "   原子提交、失败处理）——上面三张清单就是那天的填空题：类型/索引/初始化各就各位。"], 12.5, INK, lh=22)
    return svg_doc(W, H, b)


# ============================================================
# 图 4：实测结果——初始化三策略 + 探针矩阵
# ============================================================

def img4() -> str:
    W, H = 1200, 760
    b = title_block(W, "实测结果：测试计划咬得住人（6/6 PASS ＋ 3 探针全红）",
                    "环境：Linux aarch64 · Python 3.11.4 · numpy 1.26.4 · 种子 85——全部真实运行，无估算")

    # 左：初始化三策略
    b += text(40, 112, "对照实验：输出初始化三策略（同一 A(4,6)@B(6,3)，同一参考）", 15, SOFT)
    cards = [
        ("方案 B：iter_args（选定）", ["%acc 从常量 0.0 起步", "C 每元素只写一次"], "max|diff| = 0（位等价）", "额外流量 +0 B", GREEN, L_GREEN, "✓"),
        ("方案 A：fill 0 ＋ 读改写", ["先 fill 再 load-accumulate"], "max|diff| = 0（位等价）", "额外流量 +96 B（2×M×N×4）", BLUE, L_BLUE, "✓"),
        ("A′：什么都不做", ["读改写从垃圾 777.0 起步"], "max|diff| = 777.0001", "＝未定义行为", RED, L_RED, "✗"),
    ]
    y = 132
    for t, m1, d1, d2, lc, lf, mark in cards:
        b += srect(40, y, 560, 96, fill=lf, stroke=lc, sw=2.4)
        b += text(58, y + 28, t, 14.5, INK)
        for ln in m1:
            b += text(58, y + 50, ln, 11.8, SOFT)
        b += text(58, y + 76, d1, 13, lc)
        b += text(300, y + 76, d2, 12, SOFT)
        b += text(566, y + 44, mark, 30, lc, "middle")
        y += 110
    b += mtext(40, y + 6, ["结论：初始化是 Lowering 的显式任务——alloc 不清零，", "「忘了」不是性能问题，是正确性问题。"], 12.5, INK)

    # 右：探针矩阵
    b += text(640, 112, "探针矩阵：故意埋 3 个 bug，看哪些检查变红", 15, SOFT)
    x0, y0, cw, rh = 640, 132, 118, 40
    heads = ["探针", "TP1", "TP2", "TP3", "TP6"]
    b += srect(x0, y0, 520, rh, fill="white", stroke=SOFT, sw=2.0)
    b += text(x0 + 14, y0 + 26, heads[0], 13, SOFT)
    for j, h in enumerate(heads[1:]):
        b += text(x0 + 168 + j * 88, y0 + 26, h, 13, SOFT, "middle")
    rows = [
        ("P1 strides 算反 [1,3]", ["红", "红", "红", "红"]),
        ("P2 忘了初始化", ["绿", "绿", "红", "红"]),
        ("P3 K 上界误用 N", ["绿", "绿", "红", "红"]),
    ]
    for i, (name, cells) in enumerate(rows):
        ry = y0 + rh + i * rh
        b += srect(x0, ry, 520, rh, fill="white", stroke=SOFT, sw=1.8)
        b += text(x0 + 14, ry + 26, name, 12.5, INK)
        for j, c in enumerate(cells):
            cx = x0 + 168 + j * 88
            col, lf = (RED, L_RED) if c == "红" else (GREEN, L_GREEN)
            b += srect(cx - 26, ry + 7, 52, 26, fill=lf, stroke=col, sw=1.8, amp=0.9)
            b += text(cx, ry + 26, c, 13, col, "middle")
    b += mtext(640, y0 + rh * 4 + 18, ["读法：TP6 是端到端大网（三个 bug 全拦）；", "TP1/TP2 定位地址类，TP3 定位初值类——", "红了先查哪张清单，矩阵已经告诉你。"], 12.5, INK)

    # 底部：TP 总览
    b += srect(40, 560, 1120, 168, fill="white", stroke=GREEN, sw=2.6)
    b += text(58, 590, "测试计划总览（真实执行，全部 PASS）", 15, GREEN)
    tps = [
        ("TP1 类型完整性", "strides vs 行主序计算值"),
        ("TP2 索引探针", "addr vs ravel_multi_index"),
        ("TP3 输出初始化", "三策略 vs 同序参考"),
        ("TP4 合法性收敛", "full/partial 两种模式"),
        ("TP5 边界缝合", "to_tensor 物化钩子"),
        ("TP6 执行等价", "循环 IR vs 同序参考"),
    ]
    for i, (t, m) in enumerate(tps):
        cx = 58 + (i % 3) * 370
        cy = 614 + (i // 3) * 52
        b += text(cx, cy, "PASS", 13, GREEN)
        b += text(cx + 52, cy, t, 13, INK)
        b += text(cx, cy + 20, m, 11.5, SOFT)
    b += text(58, 716, "附注：循环 IR vs np.matmul 的 max|diff| = 2.384e-07（累加顺序不同，只记录不判红绿）；位等价的对照对象是同序 fp32 参考。", 11.8, SOFT)
    return svg_doc(W, H, b)


def main():
    OUT.mkdir(exist_ok=True)
    for name, fn in [("01-overview.svg", img1),
                     ("02-dialect-conversion.svg", img2),
                     ("03-lowering-steps.svg", img3),
                     ("04-results.svg", img4)]:
        (OUT / name).write_text(fn(), encoding="utf-8")
        print(f"wrote {OUT / name}")


if __name__ == "__main__":
    main()
