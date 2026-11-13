#!/usr/bin/env python3
"""生成第 89 天教程的 4 张手绘风（Excalidraw-like）SVG 技术图。

运行方式：
    python3 make_images.py

输出到 ../images/ 目录：
    01-overview.svg           第 89 天在第四阶段与编译链路中的位置 + 输入与产出
    02-address-mapping.svg    多维索引 → 线性地址：三个 memref 网格、公式与覆盖统计
    03-body-structure.svg     循环体五块肉的位置：嵌套结构＋作用域推导＋累加器环路
    04-results.svg            实测结果：AT1~AT6、关键数字、四个注入探针

风格与 Day 78~88 保持一致：手绘抖动线条、马克笔笔触、米白背景、
蓝/橙/绿/红四种柔和强调色、简单几何形状。
图中文字与数字全部来自 body_pass.py 的真实运行结果（outputs/）。
"""

import math
import random
from pathlib import Path

random.seed(89)

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


def text(x, y, s, size=16, fill=INK, anchor="start", rot=None, bold=False):
    t = (f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-size="{size}" '
         f'fill="{fill}"')
    if bold:
        t += ' font-weight="bold"'
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
# 图 1：全貌——第四阶段第五步收官 + 编译链路位置 + 输入与产出
# ============================================================

def img1() -> str:
    W, H = 1200, 710
    b = title_block(W, "第 89 天全貌：循环体收官——Load/Mul/Add/Store 填进三重循环",
                    "第四阶段（第 13 周）：Day 88 钉死了循环骨架，今天把最后五块肉填进去，输出第一次有真实数值")

    # 上带：阶段地图
    b += srect(40, 100, 480, 96, fill=L_GREEN, stroke=GREEN, sw=2.4)
    b += text(56, 128, "第三阶段 图优化（D57~84）✓ 已收官", 16, INK)
    b += mtext(56, 152, ["五道闸管道：11 → 5 节点的干净 tensor 图", "产出：设计文档＋讲稿＋清单（D84）"], 12.5, SOFT)
    b += arrow(526, 148, 576, 148, SOFT, 2.4)
    b += srect(580, 100, 580, 96, fill=L_ORANGE, stroke=ORANGE, sw=3.0, amp=1.5)
    b += text(596, 126, "第四阶段 Lowering（D85~112）", 16, INK)
    steps = [("D85 设计 ✓", "white"), ("D86 骨架 ✓", "white"), ("D87 初始化 ✓", "white"),
             ("D88 三重循环 ✓", "white"), ("D89 循环体 ←今天", L_RED), ("D90 边界 shape", "white")]
    x = 596
    for label, fill in steps:
        w = 86 if fill == "white" else 118
        b += srect(x, 138, w, 30, fill=fill, stroke=ORANGE if fill == "white" else RED,
                   sw=1.8, amp=0.9)
        b += text(x + w / 2, 158, label, 11.5, INK, anchor="middle")
        x += w + 5

    # 中带：编译链路
    b += text(60, 232, "编译链路：今天在 Lowering 站里完成「声明 → 循环＋访存」的最后一步", 15, INK)
    b += srect(60, 246, 300, 74, fill="white", stroke=INK, sw=2.0)
    b += mtext(76, 272, ["tensor 图 IR（S0）", "mini.matmul：只声明「做什么」", "形状来自 D83 终图 GEMM"], 12.5)
    b += arrow(368, 283, 428, 283, SOFT, 2.6)
    b += srect(432, 246, 340, 74, fill=L_BLUE, stroke=BLUE, sw=2.6)
    b += mtext(448, 268, ["Lowering 站（DialectConversion 仿真）", "D86 骨架 ✓ → D87 初始化 ✓ → D88 循环 ✓",
                          "D89 循环体 ← 今天：load×2/mulf/addf/store"], 12)
    b += arrow(780, 283, 840, 283, SOFT, 2.6)
    b += srect(844, 246, 296, 74, fill=L_GREEN, stroke=GREEN, sw=2.6)
    b += mtext(860, 268, ["循环＋访存 IR（18 op）", "scf ＋ memref ＋ arith", "mini 方言整体消失"], 12.5)
    b += carrow((590, 320), (560, 360), (500, 392), BLUE, 2.0, dash="6 5")
    b += carrow((900, 320), (940, 356), (980, 392), BLUE, 2.0, dash="6 5")

    # 下带：输入与产出
    b += srect(60, 396, 470, 280, fill="white", stroke=INK, sw=2.2)
    b += text(78, 424, "输入（Day 87/88 的成果）", 15, INK)
    b += srect(78, 438, 434, 104, fill=L_ORANGE, stroke=ORANGE, sw=1.8, amp=1.0)
    b += mtext(92, 460, ["Day 88 循环版 IR（13 op）：三重循环立好、", "四要素有出生证明（LoopSpec）——但循环体只有", "yield %zero 占位：执行结果是全零矩阵"], 12)
    b += srect(78, 552, 434, 106, fill=L_ORANGE, stroke=ORANGE, sw=1.8, amp=1.0)
    b += mtext(92, 574, ["Day 85 任务清单②：三条地址公式", "A[i,k]→6·i+k · B[k,j]→3·k+j · C[i,j]→3·i+j", "（strides 与边界来源——今天全部落地）"], 12)
    b += arrow(540, 536, 600, 536, SOFT, 2.8)

    b += srect(604, 396, 536, 280, fill="white", stroke=INK, sw=2.2)
    b += text(622, 424, "产出（body_pass.py 真实运行）", 15, INK)
    outs = [
        ("body-ir.txt", "完整 MatMul Lowering IR：18 op", L_GREEN, GREEN),
        ("access-table.txt", "156 条访存逐条地址核对＋覆盖统计", L_GREEN, GREEN),
        ("test-report.txt", "AT1~AT6 检查测试 6/6 PASS", L_GREEN, GREEN),
        ("debug-log.txt", "调试树：主图＋动态拒绝＋回滚", L_GREEN, GREEN),
    ]
    yy = 438
    for name, desc, fill, stroke in outs:
        b += srect(622, yy, 500, 48, fill=fill, stroke=stroke, sw=1.8, amp=1.0)
        b += text(638, yy + 20, name, 13.5, INK)
        b += text(638, yy + 38, desc, 12, SOFT)
        yy += 58

    b += text(60, 694, "验收口径：与同序参考实现（i/j/k＋float32 逐步舍入）位等价；156 次访存逐条核对；A 每格读 3 次、B 每格读 4 次、C 每格写 1 次。", 12.5, SOFT)
    return svg_doc(W, H, b)


# ============================================================
# 图 2：多维索引 → 线性地址（核心机制）
# ============================================================

def grid(x, y, rows, cols, cw=38, ch=31, highlight=None, hl=L_ORANGE, hl_stroke=ORANGE):
    """rows×cols 格子，每格写行主序线性地址；highlight=(r,c)。"""
    parts = []
    for r in range(rows):
        for c in range(cols):
            addr = r * cols + c
            fill = hl if (highlight and (r, c) == highlight) else "white"
            stroke = hl_stroke if (highlight and (r, c) == highlight) else INK
            sw = 2.4 if (highlight and (r, c) == highlight) else 1.3
            parts.append(srect(x + c * cw, y + r * ch, cw, ch, fill=fill,
                               stroke=stroke, sw=sw, amp=0.6))
            parts.append(text(x + c * cw + cw / 2, y + r * ch + ch / 2 + 5, str(addr),
                              12, INK, anchor="middle"))
    w, h = cols * cw, rows * ch
    parts.append(srect(x, y, w, h, fill="none", stroke=INK, sw=2.4, amp=1.0))
    return "".join(parts), w, h


def img2() -> str:
    W, H = 1240, 780
    b = title_block(W, "多维索引 → 线性地址：addr = Σ stride·idx（strides 声明在 memref 类型里）",
                    "memref.load/store 收的是多维下标；一维内存的格子号由类型里的 strides 算出——IR 里看不到乘加")

    # 公式横幅
    b += srect(60, 100, 1120, 44, fill=L_BLUE, stroke=BLUE, sw=2.2)
    b += text(620, 128, "addr = strides[0]·idx₀ ＋ strides[1]·idx₁（行主序：最后一维 stride=1）", 15.5,
              INK, anchor="middle")

    # 三列：A / B / C
    cols = [
        dict(x=80, name="A · %a", mtype="memref<4x6xf32, strided<[6, 1]>>",
             formula="addr = 6·i + k", rows=4, c6=6, hl=(1, 2), example="A[1,2] → 6·1+2 = 8",
             cov="24 格 · 每格读 3 次（= N）→ 72 loads", src="strides [6,1]：6 = K"),
        dict(x=470, name="B · %b", mtype="memref<6x3xf32, strided<[3, 1]>>",
             formula="addr = 3·k + j", rows=6, c6=3, hl=(4, 1), example="B[4,1] → 3·4+1 = 13",
             cov="18 格 · 每格读 4 次（= M）→ 72 loads", src="strides [3,1]：3 = N"),
        dict(x=860, name="C · %c", mtype="memref<4x3xf32, strided<[3, 1]>>",
             formula="addr = 3·i + j", rows=4, c6=3, hl=(2, 1), example="C[2,1] → 3·2+1 = 7",
             cov="12 格 · 每格写 1 次 → 12 stores", src="strides [3,1]：3 = N"),
    ]
    for c in cols:
        b += text(c["x"], 186, c["name"], 17, INK)
        b += text(c["x"], 208, c["mtype"], 12, BLUE)
        b += srect(c["x"], 218, 300, 30, fill=L_ORANGE, stroke=ORANGE, sw=1.8, amp=0.8)
        b += text(c["x"] + 150, 238, c["formula"] + "（" + c["src"] + "）", 13.5, INK, anchor="middle")
        g, gw, gh = grid(c["x"], 262, c["rows"], c["c6"], highlight=c["hl"])
        b += g
        ex_y = 262 + c["rows"] * 31 + 26
        b += srect(c["x"], ex_y, 300, 30, fill=L_GREEN, stroke=GREEN, sw=1.8, amp=0.8)
        b += text(c["x"] + 150, ex_y + 20, c["example"], 13, INK, anchor="middle")
        b += text(c["x"], ex_y + 56, c["cov"], 12.5, SOFT)
        b += carrow((c["x"] + 300, ex_y + 15), (c["x"] + 340, ex_y - 6),
                    (c["x"] + c["hl"][1] * 38 + 40, 262 + c["hl"][0] * 31 + 14), RED, 2.0, dash="5 4")

    # 底部：映射在类型里 + 真实轨迹
    b += srect(60, 626, 620, 122, fill="white", stroke=INK, sw=2.0)
    b += text(76, 650, "「映射跟类型走」：同一个 load %a[%i, %k] 文本——", 13.5, INK)
    b += mtext(76, 672, ["· 类型是 strided<[6, 1]>：addr = 6·i+k（行主序，今天用的）",
                         "· 类型若是 strided<[1, 6]>：addr = i+6·k（同一块内存变成列主序视图）",
                         "· 换布局不改 op——只改类型：这就是「多维→线性」声明在类型里的含义"], 12)
    b += srect(700, 626, 480, 122, fill=L_GREEN, stroke=GREEN, sw=2.0)
    b += text(716, 650, "真实轨迹（解释执行，(i,j)=(0,0) 的第一趟）：", 13, INK)
    b += mtext(716, 672, ["load %a[0,0] → 6·0+0 = 0   值 -1.693730",
                          "load %b[0,0] → 3·0+0 = 0   值 +0.469517",
                          "…共 12 次加载后 store %c[0,0] → 3·0+0 = 0  值 -0.949548"], 12)
    b += text(60, 766, "数据来源：outputs/access-table.txt（156 条访存全部与 np.ravel_multi_index 独立重算相等）。", 12.5, SOFT)
    return svg_doc(W, H, b)


# ============================================================
# 图 3：循环体五块肉的位置（嵌套结构＋作用域推导＋累加器环路）
# ============================================================

def opbox(x, y, w, txt, fill="white", stroke=INK, sw=1.8, size=12):
    return (srect(x, y, w, 30, fill=fill, stroke=stroke, sw=sw, amp=0.9)
            + text(x + w / 2, y + 20, txt, size, INK, anchor="middle"))


def img3() -> str:
    W, H = 1240, 800
    b = title_block(W, "循环体五块肉的位置：作用域交集的最内层＋「只写最终值」",
                    "位置不是拍脑袋：每个 op 放在「它依赖的值全部可见」的最内层，再由语义约束收窄")

    # 左：嵌套结构
    lx, ly = 60, 108
    b += srect(lx, ly, 700, 648, fill="white", stroke=INK, sw=2.4, amp=1.5)
    b += text(lx + 16, ly + 26, "func @main(%a, %b)", 14, INK)
    b += opbox(lx + 40, ly + 40, 320, "%c = memref.alloc()（不清零，D87）", L_ORANGE, ORANGE)
    b += opbox(lx + 40, ly + 78, 320, "%zero = arith.constant 0.0（初值，D87）", L_ORANGE, ORANGE)

    # i 循环
    iy = ly + 122
    b += srect(lx + 24, iy, 650, 372, fill="#fbf6ec", stroke=BLUE, sw=2.6, amp=1.2)
    b += text(lx + 40, iy + 24, "scf.for %i = 0 to 4（M 行）—— %i 从这里开始可见", 13, BLUE)
    # j 循环
    jy = iy + 34
    b += srect(lx + 16, jy, 610, 326, fill="white", stroke=GREEN, sw=2.4, amp=1.1)
    b += text(lx + 34, jy + 24, "scf.for %j = 0 to 3（N 列）—— %j 从这里开始可见", 13, GREEN)
    # k 循环
    ky = jy + 34
    b += srect(lx + 14, ky, 560, 216, fill="#fcfaf3", stroke=ORANGE, sw=2.4, amp=1.0)
    b += text(lx + 30, ky + 22, "scf.for %k = 0 to 6，iter_args(%acc = %zero) —— %k 只在这里可见", 12.5, "#b06a1e")
    body = [
        ("%xa = memref.load %a[%i, %k]", "读 A：需要 %i、%k"),
        ("%xb = memref.load %b[%k, %j]", "读 B：需要 %k、%j"),
        ("%p = arith.mulf %xa, %xb", "依赖两个 load"),
        ("%s = arith.addf %acc, %p", "读 %acc（区域参数）"),
        ("scf.yield %s  ← 写回通道", "交给下一趟 %acc"),
    ]
    yy = ky + 34
    for txt, note in body:
        fill = L_BLUE if "load" in txt else ("#f6f0dc" if "yield" in txt else "white")
        b += opbox(lx + 44, yy, 400, txt, fill, INK)
        b += text(lx + 460, yy + 20, note, 11.5, SOFT)
        yy += 36
    # store（k 外、j 内）
    sy = jy + 268
    b += opbox(lx + 44, sy, 400, "memref.store %acc, %c[%i, %j]", L_RED, RED, 2.2)
    b += text(lx + 460, sy + 20, "k 外、j 内：只写最终值", 11.5, RED)
    b += arrow(lx + 244, ky + 252, lx + 244, sy - 2, RED, 2.2)
    b += text(lx + 254, ky + 268, "%acc 出了 k 循环才存在（循环结果）", 11.5, RED)
    # 返回
    b += opbox(lx + 40, ly + 508, 320, "return %c", "white", INK)

    # 右：位置法则表
    rx = 800
    b += srect(rx, 108, 400, 250, fill="white", stroke=INK, sw=2.2)
    b += text(rx + 16, 134, "位置法则（依赖 → 位置）", 15, INK)
    rows = [
        ("load %a[%i,%k]", "需要 %i、%k", "k 体内"),
        ("load %b[%k,%j]", "需要 %k、%j", "k 体内"),
        ("mulf / addf", "依赖 load / %acc", "k 体内"),
        ("yield %s", "终止器（必须收尾）", "k 体末尾"),
        ("store", "%acc＋%i＋%j；只写最终值", "k 外、j 内"),
    ]
    yy = 148
    for opname, dep, pos in rows:
        b += text(rx + 18, yy + 16, opname, 12, INK)
        b += text(rx + 168, yy + 16, dep, 11.5, SOFT)
        b += text(rx + 316, yy + 16, pos, 11.5, BLUE if "k 体" in pos else RED)
        yy += 26
        if yy < 340:
            b += sline(rx + 14, yy - 4, rx + 386, yy - 4, "#e5ddd0", 1.2)

    # 右下：累加器环路
    b += srect(rx, 376, 400, 280, fill=L_BLUE, stroke=BLUE, sw=2.2)
    b += text(rx + 16, 402, "累加器的环路（读 → 算 → 写回）", 15, INK)
    steps = ["%zero（初值）", "iter_args 传入 → %acc", "addf：s = acc + p", "yield %s → 下一趟 acc",
             "循环结束 → %acc（结果）", "store 写进 C[i,j]"]
    yy = 418
    for i, s_ in enumerate(steps):
        b += text(rx + 40, yy + 14, s_, 12.5, INK)
        if i < len(steps) - 1:
            b += arrow(rx + 26, yy + 20, rx + 26, yy + 30, BLUE, 1.8)
        yy += 30
    b += sline(rx + 16, 614, rx + 384, 614, BLUE, 1.4, dash="5 4")
    b += text(rx + 16, 636, "D88 的占位 yield %zero = 恒等循环（全零）；", 12, SOFT)
    b += text(rx + 16, 654, "今天换成 yield %s——环路闭合，开始真的累加。", 12, SOFT)

    b += text(60, 780, "结构依据：AT1（k 体 = load×2＋mulf＋addf＋yield；store 在 fj.body=[fk, store]）；打印自 outputs/body-ir.txt。", 12.5, SOFT)
    return svg_doc(W, H, b)


# ============================================================
# 图 4：实测结果（AT1~AT6、关键数字、四个探针）
# ============================================================

def img4() -> str:
    W, H = 1240, 780
    b = title_block(W, "实测结果：AT1~AT6 全 PASS，循环体有了真实数值",
                    "环境：Linux aarch64，Python 3.11.4，numpy 1.26.4；本机未安装 MLIR（DialectConversion 语义仿真）")

    # 左：AT 清单
    b += srect(60, 100, 420, 328, fill="white", stroke=INK, sw=2.2)
    b += text(76, 126, "检查测试（全部真实运行）", 15, INK)
    ats = [
        ("AT1 结构与位置", "18 op；k 体五连、store 在 k 外 j 内；回滚不留痕"),
        ("AT2 地址映射与覆盖", "156 条访存逐条核对；A×3 / B×4 / C×1"),
        ("AT3 数值与访存统计", "同序参考实现位等价；load 144、store 12"),
        ("AT4 边界 shape 端到端", "7 组形状逐位相等（含 K=0 零趟）"),
        ("AT5 静态前提", "动态 '?' 保守拒绝（strides 无法物化）"),
        ("AT6 反面控制组", "四个注入探针全部被拦下（见右下）"),
    ]
    yy = 142
    for name, desc in ats:
        b += scirc(90, yy - 5, 9, L_GREEN, GREEN, 1.8)
        b += text(90, yy, "✓", 12, GREEN, anchor="middle")
        b += text(108, yy, name, 12.5, INK)
        b += text(118, yy + 17, desc, 11.5, SOFT)
        yy += 46

    # 右上：关键数字卡
    cards = [
        ("18 op", "13（D88）＋ 5 块肉", L_BLUE, BLUE),
        ("load 144", "= 2·M·N·K = 2·4·3·6", L_BLUE, BLUE),
        ("store 12", "= M·N = 4·3（每格写 1 次）", L_BLUE, BLUE),
        ("A 每格读 3 次", "N 次：A 的元素被所有 j 复用", L_GREEN, GREEN),
        ("B 每格读 4 次", "M 次：B 的元素被所有 i 复用", L_GREEN, GREEN),
        ("C 每格写 1 次", "只写最终值（k 外、j 内）", L_GREEN, GREEN),
    ]
    x0, y0 = 510, 100
    for i, (big, small, fill, stroke) in enumerate(cards):
        cx = x0 + (i % 3) * 228
        cy = y0 + (i // 3) * 92
        b += srect(cx, cy, 214, 78, fill=fill, stroke=stroke, sw=2.0, amp=1.0)
        b += text(cx + 107, cy + 32, big, 17, INK, anchor="middle")
        b += text(cx + 107, cy + 56, small, 11.5, SOFT, anchor="middle")

    # 中右：位等价卡
    b += srect(510, 288, 684, 64, fill=L_ORANGE, stroke=ORANGE, sw=2.2)
    b += text(526, 312, "位等价（AT3）：C 与同序参考实现（i/j/k＋float32 逐步舍入）逐位相等 = True", 13, INK)
    b += text(526, 334, "np.matmul 对照：逐位相等 = False，max|diff| = 2.384e-07（舍入顺序不同——单独报告，不算失败）", 12, SOFT)
    b += text(526, 352, "首格对账：C[0,0] = -0.949548（12 次加载＋1 次存储的一生）", 12, SOFT)

    # 下：四个探针
    b += text(60, 456, "四个注入探针（AT6 反面控制组）——今天讲的四件事，每件都有真实报错作证：", 14.5, INK)
    probes = [
        ("P1 配对写反", "load %a[%k,%i]：A(4,6) 被当 6×4 用",
         "拦截前读的是 A 的第 0 列（(0,0)(1,0)(2,0)(3,0)）；", "报错：第 0 维下标 4 ∉ [0, 4)——按维越界探针拦下", L_RED, RED),
        ("P2 位置错误", "store 放进 k 体、写 %s（部分和）",
         "数值恰好还对（最后写覆盖）；但 store 72 次 = 6×", "写放大：一旦有别的读者/并发就是正确性 bug", L_ORANGE, ORANGE),
        ("P3 写回断开", "yield %p（丢掉累加，只留最后一项）",
         "C[i,j] = A[i,5]·B[5,j]；访存计数 144/12 全正常", "max|C−ref| = 5.071e+00——只有数值对照抓得住", L_RED, RED),
        ("P4 初值错误", "累加器初值 = load %c[%i,%j]（读输出）",
         "12 次未初始化读（Day 87 探针）；load 156 = 144＋12", "max|C−ref| = 8.540e+02：垃圾值 777＋7·addr 混进结果", L_RED, RED),
    ]
    x0, y0 = 60, 470
    for i, (name, what, ev1, ev2, fill, stroke) in enumerate(probes):
        px = x0 + (i % 2) * 582
        py = y0 + (i // 2) * 118
        b += srect(px, py, 566, 104, fill=fill, stroke=stroke, sw=2.2, amp=1.1)
        b += text(px + 16, py + 24, name, 14.5, INK)
        b += text(px + 150, py + 24, what, 12, SOFT)
        b += mtext(px + 16, py + 46, [ev1, ev2], 11.5)

    # 底部：诚实边界
    b += srect(60, 712, 1120, 46, fill="white", stroke=SOFT, sw=1.6, dash="6 5")
    b += mtext(76, 730, ["诚实边界：访存日志/地址核对/覆盖统计/按维越界是解释执行器的仿真探针；iv/iter_args 用 attrs 里的 Value 模拟（真实 MLIR 是 BlockArgument）；",
                         "AT4 的 7 组 shape 是循环体正确性预飞——Day 90 按计划做 ≥8 组边界 shape 的系统对照与修复。"], 11.5, SOFT)
    return svg_doc(W, H, b)


def main():
    OUT.mkdir(exist_ok=True)
    for name, fn in [("01-overview.svg", img1), ("02-address-mapping.svg", img2),
                     ("03-body-structure.svg", img3), ("04-results.svg", img4)]:
        path = OUT / name
        path.write_text(fn(), encoding="utf-8")
        print(f"已生成 {path}（{path.stat().st_size} 字节）")


if __name__ == "__main__":
    main()
