#!/usr/bin/env python3
"""生成第 86 天教程的 4 张手绘风（Excalidraw-like）SVG 技术图。

运行方式：
    python3 make_images.py

输出到 ../images/ 目录：
    01-overview.svg           第 86 天在第四阶段与编译链路中的位置 + 输入与三件产出
    02-pattern-rewriter.svg   ConversionPattern + ConversionPatternRewriter 事务机制
    03-failure-handling.svg   两级失败处理（Pattern 级 / 驱动器级）+ 原子回滚
    04-results.svg            实测结果：骨架 IR、DT1~DT6、回滚与换形状对照

风格与 Day 78~85 保持一致：手绘抖动线条、马克笔笔触、米白背景、
蓝/橙/绿/红四种柔和强调色、简单几何形状。
图中文字与数字全部来自 lowering_pass.py 的真实运行结果（outputs/）。
"""

import math
import random
from pathlib import Path

random.seed(86)

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


def chip(x, y, label, fill, w=None, h=25, size=13.5, stroke=None):
    stroke = stroke or fill
    w = w or (len(label) * (size * 0.62) + 16)
    body = srect(x, y, w, h, fill=fill, stroke=stroke, sw=1.6, amp=0.9)
    body += text(x + w / 2, y + h * 0.72, label, size, INK, "middle")
    return body


def title_block(w, title, sub=None):
    body = text(30, 44, title, 25, INK)
    if sub:
        body += text(30, 70, sub, 14.5, SOFT)
    body += sline(30, 82, w - 30, 82, SOFT, 1.6, dash="7 6")
    return body


# ============================================================
# 图 1：全貌——第四阶段动工 + 编译链路位置 + 输入与产出
# ============================================================

def img1() -> str:
    W, H = 1200, 710
    b = title_block(W, "第 86 天全貌：动工第一天——先搭骨架的空 Lowering Pass",
                    "第四阶段（第 13 周）：把 Day 85 的施工图变成能跑、能诊断的 ConversionPattern 骨架")

    # 上带：阶段地图
    b += srect(40, 100, 480, 96, fill=L_GREEN, stroke=GREEN, sw=2.4)
    b += text(56, 128, "第三阶段 图优化（D57~84）✓ 已收官", 16, INK)
    b += mtext(56, 152, ["五道闸管道：11 → 5 节点的干净 tensor 图", "产出：设计文档＋讲稿＋清单（D84）"], 12.5, SOFT)
    b += arrow(526, 148, 576, 148, SOFT, 2.4)
    b += srect(580, 100, 580, 96, fill=L_ORANGE, stroke=ORANGE, sw=3.0, amp=1.5)
    b += text(596, 126, "第四阶段 Lowering（D85~）", 16, INK)
    steps = [("D85 设计 ✓", "white"), ("D86 骨架 ←今天", L_RED), ("D87 初始化", "white"), ("D88+ 完整计算", "white")]
    x = 596
    for label, fill in steps:
        w = 132 if fill == "white" else 138
        b += srect(x, 138, w, 30, fill=fill, stroke=ORANGE if fill == "white" else RED,
                   sw=1.8, amp=0.9)
        b += text(x + w / 2, 158, label, 12.5, INK, "middle")
        x += w + 8
    b += text(596, 188, "口号：骨架先行——匹配、结构、缝合、诊断先验收，计算再填", 12.5, SOFT)

    # 中带：编译链路
    b += text(40, 232, "编译链路：今天走到哪一步？", 15, SOFT)
    stages = [
        ("前端\n(mini 图)", "white", SOFT, False),
        ("图优化\nD57~84 ✓", L_GREEN, GREEN, False),
        ("Lowering\nD86 今天", L_ORANGE, ORANGE, True),
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
            b += text(x + bw / 2, y0 - 12, "▼ 今天在这里搭骨架 ▼", 13, ORANGE, "middle")
        if i < 4:
            b += arrow(x + bw + 2, y0 + bh / 2, x + bw + gap - 2, y0 + bh / 2, SOFT, 2.0)
    b += mtext(40, 356, ["今天的 Pass 产出「结构就位、计算留白」的循环 IR：alloc＋常量＋三重空循环；",
                         "匹配是否成功、失败是否有诊断——今天验收；load/store/累加留给 D87、D88。"], 13, SOFT)

    # 下带：输入与产出
    b += text(40, 420, "今天的输入与产出（全部真实运行）", 15, SOFT)
    b += srect(40, 434, 250, 130, fill="white", stroke=SOFT, sw=2.0, dash="6 5")
    b += text(54, 460, "输入：Day 85 的施工图", 14.5, INK)
    b += mtext(54, 484, ["三张任务清单（类型/索引/", "  初始化）＋ S0→S4 路线", "＋ TP1~TP6 测试计划", "＋ ir-loop.txt 目标样例"], 11.8, INK, lh=18)
    outs = [
        ("产出 1：骨架 IR", "skeleton-ir.txt", "3 op → 12 op，TODO 标注 D87/D88", L_BLUE, BLUE),
        ("产出 2：诊断测试", "pass-report.txt", "DT1~DT6 全部真实执行：6/6 PASS", L_GREEN, GREEN),
        ("产出 3：调试树", "debug-log.txt", "4 个案例，dialect-conversion 风格", L_ORANGE, ORANGE),
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

    # 底部：为什么骨架先行
    b += srect(40, 592, 1120, 86, fill="white", stroke=BLUE, sw=2.2, dash="8 6")
    b += text(58, 620, "为什么不一次写完整个翻译？", 14.5, BLUE)
    b += mtext(58, 644, ["一次写完 alloc＋循环＋load/store＋索引公式，错了分不清是匹配、类型、地址还是初始化的锅；", "今天先把「匹配得到、结构对、缝得上、失败有话说」验收掉（DT1~DT6），之后每填一块肉都有干净的基线。"], 12.5, INK, lh=20)
    return svg_doc(W, H, b)


# ============================================================
# 图 2：ConversionPattern + Rewriter 事务机制
# ============================================================

def img2() -> str:
    W, H = 1240, 800
    b = title_block(W, "ConversionPattern ＋ ConversionPatternRewriter：一次事务性翻译的解剖",
                    "所有修改先暂存，Pattern 成功才提交；失败回滚，IR 永远不停在「改了一半」的状态")

    # 左：matchAndRewrite 三件套
    b += srect(40, 104, 350, 330, fill="white", stroke=SOFT, sw=2.4)
    b += text(56, 130, "matchAndRewrite 的三件套", 15.5, INK)
    rows = [
        ("① op（原文）", "%mm = mini.matmul(%x, %w)", "职责：交代完整语义——", "操作数类型/shape、内维契约、结果类型", L_RED, RED),
        ("② adaptor（已换币的钱）", "operands = [%a, %b]（memref）", "最近一次替换后的值；类型已是", "TypeConverter 合法化后的类型", L_ORANGE, ORANGE),
        ("③ rewriter（唯一通道）", "create / replaceOp / eraseOp", "改 IR 只许走它；直接 op.erase()", "在真实 MLIR 里是违规操作", L_BLUE, BLUE),
    ]
    y = 148
    for t, code, m1, m2, lf, lc in rows:
        b += srect(56, y, 318, 88, fill=lf, stroke=lc, sw=2.0, amp=1.0)
        b += text(68, y + 24, t, 13.5, INK)
        b += text(68, y + 44, code, 11.8, lc)
        b += text(68, y + 62, m1, 11.2, SOFT)
        b += text(68, y + 78, m2, 11.2, SOFT)
        y += 96
    b += mtext(56, y + 8, ["对应 MLIR：ConversionPattern 比 RewritePattern", "多一个 operands/adaptor 参数；配了 TypeConverter", "时类型即合法化类型，操作数无法合法化则", "pattern 在调用前就失败。"], 11.5, SOFT)

    # 中：事务暂存区
    b += srect(430, 104, 390, 330, fill=L_BLUE, stroke=BLUE, sw=2.6)
    b += text(446, 130, "事务暂存区（staging）", 15.5, INK)
    b += mtext(446, 156, ["MatMulSkeletonPattern 里发生的事（真实顺序）：",
                          "  create  memref.alloc        → %c",
                          "  create  arith.constant ×5   → %c0..%c6",
                          "  create  scf.yield           → 占位",
                          "  create  scf.for %k / %j / %i → 从内向外",
                          "  replaceOp(matmul, [%c])     → 处置 root"], 12, INK, lh=19)
    b += srect(446, 288, 170, 50, fill="white", stroke=GREEN, sw=2.2)
    b += text(456, 308, "返回 success", 12.5, GREEN)
    b += text(456, 328, "commit：插入＋记账", 11.5, INK)
    b += srect(634, 288, 170, 50, fill="white", stroke=RED, sw=2.2)
    b += text(644, 308, "返回 failure", 12.5, RED)
    b += text(644, 328, "rollback：全部丢弃", 11.5, INK)
    b += mtext(446, 360, ["commit 做两件事：新建 op 顶替 root 的位置；", "%mm → %c 记入替换映射（uses 延迟替换）。"], 11.8, INK, lh=18)
    b += mtext(446, 402, ["真实 MLIR 的 rollback 模式更彻底：replaceOp/", "eraseOp 延迟到整个转换结束才生效，还能回滚", "已应用的 Pattern（allowPatternRollback）。"], 11.2, SOFT, lh=17)

    # 右：延迟替换映射 + finalize
    b += srect(860, 104, 340, 330, fill=L_ORANGE, stroke=ORANGE, sw=2.6)
    b += text(876, 130, "替换映射＋finalize（延迟替换）", 15, INK)
    maps = [
        ("%x : tensor<4x6>", "%a : memref<4x6, strided<[6,1]>>", "S1 签名转换"),
        ("%w : tensor<6x3>", "%b : memref<6x3, strided<[3,1]>>", "S1 签名转换"),
        ("%mm : tensor<4x3>", "%c : memref<4x3, strided<[3,1]>>", "Pattern 提交（今天）"),
    ]
    y = 150
    for old, new, note in maps:
        b += text(876, y, old, 11.5, SOFT)
        b += arrow(1000, y - 4, 1030, y - 4, ORANGE, 1.8)
        b += text(1038, y, new, 11.5, INK)
        b += text(876, y + 16, note, 11, SOFT)
        y += 44
    b += srect(876, 296, 308, 56, fill="white", stroke=ORANGE, sw=2.0)
    b += text(888, 318, "finalize：转换结束后统一改 uses", 12.5, INK)
    b += mtext(888, 338, ["return 的操作数 %mm → %c；中途的「半 tensor", "半 memref」由映射缝上（DT3 实测无悬空引用）"], 11, SOFT)
    b += mtext(876, 378, ["adaptor 的底座就是这张映射：", "getRemappedValue(%x) → %a。"], 11.8, INK, lh=18)

    # 连接箭头
    b += arrow(392, 250, 428, 250, SOFT, 2.4)
    b += text(410, 236, "调用", 12, SOFT, "middle")
    b += arrow(822, 250, 856, 250, SOFT, 2.4)
    b += text(839, 236, "记账", 12, SOFT, "middle")

    # 底部：三条契约
    b += srect(40, 470, 1160, 130, fill="white", stroke=RED, sw=2.4)
    b += text(58, 498, "Pattern 的三条契约（真实 MLIR 文档《Pattern Rewriting》Restrictions）", 14.5, RED)
    b += mtext(58, 524, ["① 一切 IR 修改（包括创建）必须经过 PatternRewriter——不许 op.erase() 绕过；",
                         "② root op 必须 in-place 更新、replace 或 erase——「匹配了却没处置」是违约；",
                         "③ matchAndRewrite 返回 success 当且仅当 IR 被修改——返回 failure 就不许留下任何改动。"], 12.5, INK, lh=21)
    b += text(58, 586, "运行时检查：-DMLIR_ENABLE_EXPENSIVE_PATTERN_API_CHECKS=ON（默认构建不查；今天的仿真一律硬失败，DT6-C 实测）", 11.8, SOFT)

    # 最底：驱动器一句话
    b += srect(40, 626, 1160, 76, fill=L_GREEN, stroke=GREEN, sw=2.2)
    b += text(58, 654, "驱动器视角的一句话", 14.5, GREEN)
    b += mtext(58, 678, ["先序遍历（op 先于其 region）；非法 op 按 benefit 从高到低逐条试 Pattern；全都不行才轮到", "驱动器级失败（full 整体失败 / partial 显式残留）——失败的两级结构见下一张图。"], 12.5, INK, lh=19)
    return svg_doc(W, H, b)


# ============================================================
# 图 3：两级失败处理 + 原子回滚
# ============================================================

def img3() -> str:
    W, H = 1240, 820
    b = title_block(W, "转换失败的两级处理：Pattern 拒绝是悄悄的，驱动器失败是大声的",
                    "「失败要大声」没错——但大声的位置有讲究：Pattern 级默认安静（试下一条），驱动器级必须震耳")

    # 左上：Pattern 级
    b += srect(40, 104, 570, 240, fill=L_ORANGE, stroke=ORANGE, sw=2.6)
    b += text(56, 130, "Pattern 级：notifyMatchFailure（这条规则不翻）", 15, INK)
    b += mtext(56, 156, ["match 条件不满足（维度≠2、内维不匹配……）→ rewriter.notifyMatchFailure(op, reason)",
                         "→ 返回 failure，驱动器换下一条 Pattern 再试（benefit 从高到低）",
                         "→ 展示方式由驱动器决定：dialect conversion 把 reason 放进调试树，",
                         "   普通运行默认不打印——不是丢消息，是设计（很多 Pattern 本来就不该匹配）"], 12.2, INK, lh=20)
    b += srect(56, 248, 538, 82, fill="white", stroke=SOFT, sw=1.8)
    b += mtext(66, 268, ["A(4,6) @ B(3,2) 的真实调试树（--debug，案例 2）：",
                         "  * Pattern : 'MatMulSkeletonPattern' {",
                         "  } -> FAILURE : 内维不匹配：A.shape[1]=6 ≠ B.shape[0]=3，",
                         "                k 循环边界无从确定"], 11.3, INK, lh=16)

    # 右上：驱动器级
    b += srect(640, 104, 560, 240, fill=L_RED, stroke=RED, sw=2.6)
    b += text(656, 130, "驱动器级：所有 Pattern 都不行（这个 op 没救）", 15, INK)
    b += srect(656, 148, 258, 88, fill="white", stroke=RED, sw=2.0)
    b += text(668, 170, "full 模式（今天选它）", 13, RED)
    b += mtext(668, 192, ["整体失败、指名道姓：", "无法合法化 'mini.conv'：没有注册", "对应的 ConversionPattern"], 11.3, INK, lh=17)
    b += srect(928, 148, 258, 88, fill="white", stroke=BLUE, sw=2.0)
    b += text(940, 170, "partial 模式", 13, BLUE)
    b += mtext(940, 192, ["成功但显式残留：", "['mini.conv']（交给后续 Pass，", "下游得有人接手）"], 11.3, INK, lh=17)
    b += mtext(656, 262, ["同一个「无法合法化」有两种病因，诊断文本不同（今天实测）：",
                          "  · 没有注册 Pattern（mini.conv）→ 补规则或改目标",
                          "  · Pattern 都拒绝了（内维不匹配的 matmul）→ 看 --debug 调试树里的拒绝原因"], 12, INK, lh=19)

    # 下：回滚实验
    b += text(40, 386, "原子回滚（DT6-A/B 实测）：失败的 Pattern 不留痕", 15, SOFT)
    b += srect(40, 402, 1160, 200, fill="white", stroke=GREEN, sw=2.4)
    flow = [
        ("HalfDoneMatMulPattern\n(benefit=2，先试)", "先 create 了 memref.alloc\n再 notifyMatchFailure", L_RED, RED),
        ("rollback\n(丢弃暂存)", "暂存的 create/replace\n全部丢弃", "white", SOFT),
        ("MatMulSkeletonPattern\n(benefit=1，接手)", "重新 match＋rewrite\n正常提交 10 个目标 op", L_GREEN, GREEN),
        ("终图（12 op）\n", "与只用 Skeleton 的结果\n逐字相同：True（实测）", L_BLUE, BLUE),
    ]
    x, y0, bw, bh, gap = 60, 424, 250, 92, 34
    for i, (t, m, lf, lc) in enumerate(flow):
        b += srect(x, y0, bw, bh, fill=lf, stroke=lc, sw=2.2)
        ls = t.split("\n")
        b += text(x + 14, y0 + 26, ls[0], 13, INK)
        if len(ls) > 1 and ls[1]:
            b += text(x + 14, y0 + 44, ls[1], 11.5, SOFT)
        ms = m.split("\n")
        b += text(x + 14, y0 + 66, ms[0], 11.5, INK)
        b += text(x + 14, y0 + 82, ms[1], 11.5, INK)
        if i < 3:
            b += arrow(x + bw + 2, y0 + bh / 2, x + bw + gap - 2, y0 + bh / 2, SOFT, 2.2)
        x += bw + gap
    b += mtext(60, 556, ["反例 B：只注册 HalfDone → full 失败，且失败后 IR 的 op 序列 = [func.func, mini.matmul, func.return]（与转换前相同），",
                         "骨架半成品残留 = 无——「先建了 alloc 再放弃」没有留下任何东西。",], 12, INK, lh=19)
    b += mtext(60, 594, ["契约反例 C：Forgetful 返回成功却忘了 replaceOp → 仿真硬失败：「root op 既未被 replaceOp 也未被 eraseOp」；",
                         "真实 MLIR 默认构建不查这条，需 -DMLIR_ENABLE_EXPENSIVE_PATTERN_API_CHECKS=ON。"], 12, SOFT, lh=19)

    # 底部：排障路线
    b += srect(40, 626, 1160, 76, fill="white", stroke=BLUE, sw=2.2, dash="8 6")
    b += text(58, 654, "排障路线（今天练成的肌肉记忆）", 14.5, BLUE)
    b += mtext(58, 678, ["full 失败 → 看诊断点名谁 → 有注册 Pattern 吗？有 → 开 --debug 看拒绝原因（notifyMatchFailure）；",
                         "没有 → 补 Pattern / 调整 ConversionTarget / 换 partial 并确认下游接手。"], 12.5, INK, lh=19)
    return svg_doc(W, H, b)


# ============================================================
# 图 4：实测结果——骨架 IR、DT1~DT6、两个对照实验
# ============================================================

def img4() -> str:
    W, H = 1240, 780
    b = title_block(W, "实测结果：DT1~DT6 全 PASS——骨架 10 op 就位，待填 6 op 有主",
                    "环境：Linux aarch64 · Python 3.11.4 · 无 MLIR（DialectConversion 语义仿真）——全部真实运行，无估算")

    # 左：骨架 IR 与待填
    b += text(40, 112, "骨架 IR（skeleton-ir.txt，A(4,6)@B(6,3)→C(4,3)）：3 op → 12 op", 15, SOFT)
    b += srect(40, 126, 560, 330, fill="white", stroke=SOFT, sw=2.2)
    b += mtext(54, 150, ["func @main(%a: memref<4x6…>, %b: memref<6x3…>)",
                         "  %c   = memref.alloc() : memref<4x3…>      ← 骨架①",
                         "  %c0/%c1/%c4/%c3/%c6 = arith.constant     ← 骨架② 0/1/M/N/K",
                         "  scf.for %i = %c0 to %c4 step %c1 {",
                         "    scf.for %j = %c0 to %c3 step %c1 {",
                         "      scf.for %k = %c0 to %c6 step %c1 {",
                         "        scf.yield                        ← 占位：留白",
                         "      }",
                         "    }",
                         "  }",
                         "  return %c"], 12, INK, "start", 21)
    b += srect(54, 336, 240, 62, fill=L_GREEN, stroke=GREEN, sw=2.0)
    b += text(66, 356, "Day 87 填：初始化", 12.5, GREEN)
    b += mtext(66, 374, ["%zero = arith.constant 0.0", "＋ iter_args(%acc = %zero) 升级"], 11, INK, lh=15)
    b += srect(310, 336, 276, 62, fill=L_ORANGE, stroke=ORANGE, sw=2.0)
    b += text(322, 356, "Day 88 填：访存与累加", 12.5, ORANGE)
    b += mtext(322, 374, ["load×2 ＋ mulf ＋ addf ＋ store", "（yield 原位升级为回传 %s）"], 11, INK, lh=15)
    b += mtext(54, 424, ["骨架 10 op ＋ 待填 6 op = 完整目标 16 op（Day 85 的 op 名级", "仿真记 14 op：5 个常量算 1 条）；yield 是占位，不重复计数。"], 11.8, SOFT, lh=17)

    # 右上：DT1~DT6
    b += text(640, 112, "诊断测试 DT1~DT6（真实执行，全部 PASS）", 15, SOFT)
    dts = [
        ("DT1 匹配与替换", "3 op → 12 op，op 序列与预期骨架完全一致，mini 残留 = 无"),
        ("DT2 骨架结构", "alloc 类型/strides、常量 {0,1,3,4,6}、边界 4/3/6、嵌套深度 3"),
        ("DT3 类型缝合", "adaptor 拿到 %a/%b（memref）；终图无 tensor、无悬空引用"),
        ("DT4 驱动器级失败", "mini.conv：full 指名失败 / partial 残留 ['mini.conv']"),
        ("DT5 Pattern 级失败", "内维 6≠3：拒绝原因只在 --debug 调试树，普通运行静默"),
        ("DT6 原子性与契约", "回滚后终图逐字相同；忘 replaceOp → 契约硬失败"),
    ]
    y = 132
    for t, m in dts:
        b += srect(640, y, 560, 44, fill="white", stroke=SOFT, sw=1.8)
        b += text(654, y + 18, "PASS", 12.5, GREEN)
        b += text(706, y + 18, t, 13, INK)
        b += text(706, y + 35, m, 11.3, SOFT)
        y += 52

    # 右下：两个对照
    b += text(640, y + 8, "两个对照实验（真实数据）", 15, SOFT)
    b += srect(640, y + 22, 274, 118, fill=L_RED, stroke=RED, sw=2.2)
    b += text(654, y + 44, "对照 1：只注册半途而废的 Pattern", 12.5, INK)
    b += mtext(654, y + 66, ["full 模式失败；失败后 op 序列", "= [func.func, mini.matmul,",
                             "  func.return]（与转换前相同）", "骨架半成品残留 = 无 → 失败不留痕"], 11.2, INK, lh=16)
    b += srect(926, y + 22, 274, 118, fill=L_BLUE, stroke=BLUE, sw=2.2)
    b += text(940, y + 44, "对照 2：换形状 --shape 2 3 2", 12.5, INK)
    b += mtext(940, y + 66, ["骨架 12 op 不变；常量变 {0,1,2,2,3}，", "M=N=2 出现两个「2」→ 命名去重",
                             "%c2 与 %c2'；边界 i/j/k = 2/2/3；", "alloc 变 memref<2x2, strided<[2,1]>>"], 11.2, INK, lh=16)

    # 底部：口径附注
    b += srect(40, 626, 1160, 88, fill="white", stroke=GREEN, sw=2.4)
    b += text(58, 654, "验收口径（诚实声明）", 14.5, GREEN)
    b += mtext(58, 678, ["今天的验收是结构性的：匹配、骨架、类型缝合、失败诊断（DT1~DT6）；骨架不做数值计算，执行等价（同序 fp32 位等价）从 Day 87 起逐块补上。",
                         "与真实 MLIR 的差异见脚本头部：rollback 深度（Pattern 级 vs 整条路径）、签名转换前置、契约检查策略。"], 12.3, INK, lh=20)
    return svg_doc(W, H, b)


def main():
    OUT.mkdir(exist_ok=True)
    for name, fn in [("01-overview.svg", img1),
                     ("02-pattern-rewriter.svg", img2),
                     ("03-failure-handling.svg", img3),
                     ("04-results.svg", img4)]:
        (OUT / name).write_text(fn(), encoding="utf-8")
        print(f"wrote {OUT / name}")


if __name__ == "__main__":
    main()
