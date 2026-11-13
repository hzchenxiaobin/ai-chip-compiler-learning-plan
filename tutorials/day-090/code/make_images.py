#!/usr/bin/env python3
"""生成第 90 天教程的 4 张手绘风（Excalidraw-like）SVG 技术图。

运行方式：
    python3 make_images.py

输出到 ../images/ 目录：
    01-overview.svg          第 90 天在第四阶段与编译链路中的位置 + 输入与产出
    02-shape-matrix.svg      15 组形状矩阵：类别、trips、流量、覆盖、目的（ST1 真实数据）
    03-blindness.svg         方阵盲区机制：三个旋钮重合 → 四类变异隐身/静默算错（ST2/ST4）
    04-results.svg           实测结果：ST1~ST7、猎杀矩阵实色网格、关键数字（真实运行）

风格与 Day 78~89 保持一致：手绘抖动线条、马克笔笔触、米白背景、
蓝/橙/绿/红四种柔和强调色、简单几何形状。
图中文字与数字全部来自 shape_pass.py 的真实运行结果（ST1/ST3 直接 import 复跑）。
"""

import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import shape_pass as sp

random.seed(90)

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
GREY = "#e9e4d8"
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
# 实数据：跑一遍 ST1/ST3（与 outputs/ 一致）
# ============================================================

_, _, ST1_ROWS = sp.st1_matrix()
_, _, GRID = sp.st3_kill_matrix()
KILL = {}
for (mname, shp), (status, ev) in GRID.items():
    KILL.setdefault(shp, {})[mname] = status


def kill_color(status):
    return {"OOB": (L_RED, RED), "NUM": (L_ORANGE, ORANGE), "SAME": (GREY, SOFT)}[status]


# ============================================================
# 图 1：全貌——第四阶段第六步 + 编译链路位置 + 输入与产出
# ============================================================

def img1() -> str:
    W, H = 1200, 710
    b = title_block(W, "第 90 天全貌：支持非方形与边界 Shape——让 Lowering 对任意 (M,K,N) 有牙齿",
                    "第四阶段（第 13 周）：Day 89 循环体收官后，今天的题目是「怎么证明它真的支持各种形状」")

    # 上带：阶段地图
    b += srect(40, 100, 440, 96, fill=L_GREEN, stroke=GREEN, sw=2.4)
    b += text(56, 128, "第三阶段 图优化（D57~84）✓", 15, INK)
    b += mtext(56, 150, ["五道闸管道：11 → 5 节点", "产出：设计文档＋讲稿（D84）"], 11.5, SOFT)
    b += arrow(486, 148, 530, 148, SOFT, 2.4)
    b += srect(534, 100, 646, 96, fill=L_ORANGE, stroke=ORANGE, sw=3.0, amp=1.5)
    b += text(550, 122, "第四阶段 Lowering（D85~112）", 14.5, INK)
    steps = [("D85✓", "white"), ("D86✓", "white"), ("D87✓", "white"),
             ("D88✓", "white"), ("D89✓", "white"), ("D90 边界 shape ←今天", L_RED),
             ("D91 复盘", "white")]
    x = 550
    for label, fill in steps:
        w = 52 if fill == "white" and len(label) <= 4 else (
            150 if fill != "white" else 64)
        b += srect(x, 134, w, 28, fill=fill, stroke=ORANGE if fill == "white" else RED,
                   sw=1.8, amp=0.9)
        b += text(x + w / 2, 152, label, 11, INK, anchor="middle")
        x += w + 4
    b += text(550, 182, "设计 → 骨架 → 初始化 → 三重循环 → 循环体 → 边界 shape（今天） → 复盘", 11, SOFT)

    # 中带：编译链路
    b += text(60, 232, "编译链路：今天仍在 Lowering 站——同一条 Pattern，换形状只换常量与类型", 15, INK)
    b += srect(60, 246, 300, 74, fill="white", stroke=INK, sw=2.0)
    b += mtext(76, 272, ["tensor 图 IR（S0）", "mini.matmul：只声明「做什么」", "形状 (M,K,N) 是输入的一部分"], 12.5)
    b += arrow(368, 283, 428, 283, SOFT, 2.6)
    b += srect(432, 246, 340, 74, fill=L_BLUE, stroke=BLUE, sw=2.6)
    b += mtext(448, 268, ["Lowering 站（DialectConversion 仿真）", "D89 已产 18 op 循环体（贯穿例 4,6,3）",
                          "D90 ← 今天：M/N/K 独立取值＋边界形状矩阵"], 12)
    b += arrow(780, 283, 840, 283, SOFT, 2.6)
    b += srect(844, 246, 296, 74, fill=L_GREEN, stroke=GREEN, sw=2.6)
    b += mtext(860, 268, ["循环＋访存 IR（18 op 恒定）", "形状＝数据：常量 {0,1,M,N,K}＋类型",
                          "15 组形状逐位等价（ST1）"], 12.5)
    b += carrow((590, 320), (560, 360), (500, 392), BLUE, 2.0, dash="6 5")
    b += carrow((900, 320), (940, 356), (980, 392), BLUE, 2.0, dash="6 5")

    # 下带：输入与产出
    b += srect(60, 396, 470, 280, fill="white", stroke=INK, sw=2.2)
    b += text(78, 424, "输入（Day 88/89 的成果）", 15, INK)
    b += srect(78, 438, 434, 104, fill=L_ORANGE, stroke=ORANGE, sw=1.8, amp=1.0)
    b += mtext(92, 460, ["Day 89 循环体完整版 IR（18 op）：", "load/mulf/addf/store 全部就位，", "贯穿例 A(4,6)@B(6,3) 位等价"], 12)
    b += srect(78, 552, 434, 106, fill=L_ORANGE, stroke=ORANGE, sw=1.8, amp=1.0)
    b += mtext(92, 574, ["Day 89 AT4 预飞：7 组形状全绿", "但只是「预飞」——方阵/标量测不出", "配对与边界错误（今天 ST2/ST4 实证）"], 12)
    b += arrow(540, 536, 600, 536, SOFT, 2.8)

    b += srect(604, 396, 536, 280, fill="white", stroke=INK, sw=2.2)
    b += text(622, 424, "产出（shape_pass.py 真实运行）", 15, INK)
    outs = [
        ("shape-matrix.txt", "15 组形状：trips/流量/覆盖/位等价（ST1）", L_GREEN, GREEN),
        ("kill-matrix.txt", "4 变异 × 15 形状的 OOB/NUM/SAME 猎杀矩阵", L_GREEN, GREEN),
        ("fix-loop.txt", "红→定位→修复→绿 四个修复闭环（ST7）", L_GREEN, GREEN),
        ("test-report.txt", "ST1~ST7 检查测试 7/7 PASS", L_GREEN, GREEN),
        ("debug-log.txt", "调试树：动态拒绝×2＋回滚＋正常转换", L_GREEN, GREEN),
    ]
    yy = 438
    for name, desc, fill, stroke in outs:
        b += srect(622, yy, 500, 40, fill=fill, stroke=stroke, sw=1.8, amp=1.0)
        b += text(638, yy + 17, name, 13, INK)
        b += text(638, yy + 33, desc, 11.5, SOFT)
        yy += 48

    b += text(60, 694, "验收口径：15 组形状与同序参考实现逐位相等；流量 load=2MNK/store=MN；覆盖 A×N/B×M/C×1；4 个注入变异各被 ≥10 组形状杀死。", 12.5, SOFT)
    return svg_doc(W, H, b)


# ============================================================
# 图 2：形状矩阵（核心交付物：15 组 Shape 测试与参考结果对照）
# ============================================================

def minigrid(x, y, r, c, cw=9.5, ch=8.5, fill="white", stroke=INK):
    """极简行列格：M×K / K×N / M×N 的比例示意。"""
    out = []
    for rr in range(min(r, 6)):
        for cc in range(min(c, 8)):
            out.append(srect(x + cc * cw, y + rr * ch, cw, ch, fill=fill,
                             stroke=stroke, sw=0.8, amp=0.4))
    w, h = min(c, 8) * cw, min(r, 6) * ch
    out.append(srect(x, y, w, h, fill="none", stroke=stroke, sw=1.6, amp=0.7))
    return "".join(out), w, h


# 图片专用短目的（SHAPE_MATRIX 的 purpose 太长，这里改写成两行短句）
IMG_PURPOSE = {
    (3, 3, 3): ("盲区基线：M=N=K", "全绿 ≠ 正确"),
    (1, 7, 4): ("M=1：i 单趟", "杀 a_swap / i_ub_n"),
    (6, 1, 4): ("K=1 外积：k 单趟", "杀 k_ub_n / a_swap"),
    (4, 3, 1): ("N=1：j 单趟", "杀 b_swap"),
    (1, 1, 1): ("只测管道", "4 个变异全免疫"),
    (2, 3, 5): ("M≠K≠N", "单挑杀全部 4 个"),
    (5, 2, 3): ("K<M,K<N 小 K", "部分和现形"),
    (2, 8, 3): ("K>M,K>N 宽 K", "归约比输出长"),
    (4, 6, 3): ("贯穿例 D85~89", "连续对账"),
    (3, 3, 5): ("M==K≠N", "a_swap 静默算错"),
    (5, 2, 2): ("K==N≠M", "b_swap 算错/ k 隐身"),
    (4, 6, 4): ("M==N≠K", "i_ub_n 隐身"),
    (4, 0, 3): ("空归约：C 全零", "杀 k_ub_n"),
    (0, 6, 3): ("空输出：i 零趟", "杀 i_ub_n"),
    (3, 2, 0): ("空输出：j 零趟", "i/k 类盲区"),
}


def img2() -> str:
    W, H = 1240, 840
    b = title_block(W, "形状矩阵：15 组 Shape 测试与参考结果对照（ST1 真实运行）",
                    "每组的「目的」回答「它能杀什么 bug」——测试不是凑数，形状是按杀伤力选的")

    # 顶部横幅：结构不变式
    b += srect(60, 96, 1120, 40, fill=L_BLUE, stroke=BLUE, sw=2.2)
    b += text(620, 121, "结构不变式：IR 恒为 18 op——形状是数据（常量 {0,1,M,N,K} ＋ 3 个 memref 类型），不是代码结构", 14.5,
              INK, anchor="middle")

    # 15 张卡片：5 列 × 3 行
    col_w, row_h = 236, 196
    x0, y0 = 54, 152
    for i, r in enumerate(ST1_ROWS):
        cx = x0 + (i % 5) * (col_w + 6)
        cy = y0 + (i // 5) * (row_h + 8)
        M, K, N = r["M"], r["K"], r["N"]
        b += srect(cx, cy, col_w, row_h, fill="white", stroke=INK, sw=2.0, amp=1.1)
        b += text(cx + 12, cy + 24, r["cat"], 13.5, INK)
        b += text(cx + 12, cy + 42, f"A({M},{K})@B({K},{N})→C({M},{N})", 12, BLUE)
        # 三个迷你格
        gy = cy + 52
        ga, wa, ha = minigrid(cx + 14, gy, M, K, fill=L_ORANGE, stroke=ORANGE)
        b += ga
        b += text(cx + 14, gy + M * 8.5 + 14 if M else gy + 10, f"M×K", 9.5, SOFT)
        gb, wb, hb = minigrid(cx + 14 + (K and min(K, 8) * 9.5 + 12) + 0, gy, K, N,
                              fill=L_GREEN, stroke=GREEN)
        b += gb
        b += text(cx + 14 + min(K, 8) * 9.5 + 12, gy + min(K, 6) * 8.5 + 14, f"K×N", 9.5, SOFT)
        gc, wc, hc = minigrid(cx + 14 + min(K, 8) * 9.5 + 12 + min(N, 8) * 9.5 + 12, gy, M, N,
                              fill=L_RED, stroke=RED)
        b += gc
        b += text(cx + 14 + min(K, 8) * 9.5 + 12 + min(N, 8) * 9.5 + 12,
                  gy + min(M, 6) * 8.5 + 14, f"M×N", 9.5, SOFT)
        # trips / 流量
        ty = cy + 128
        b += text(cx + 12, ty, f"trip {r['trips'][0]}/{r['trips'][1]}/{r['trips'][2]}", 11.5, INK)
        b += text(cx + 90, ty, f"load {r['loads']}", 11.5, BLUE)
        b += text(cx + 158, ty, f"store {r['stores']}", 11.5, BLUE)
        # 覆盖注（短版）
        cov_short = ("A×%d B×%d C×1" % (N, M)) if r["loads"] else ("零访存" if r["stores"] == 0 else "C×1")
        b += text(cx + 12, ty + 17, cov_short, 11, SOFT)
        p1, p2 = IMG_PURPOSE[(M, K, N)]
        b += text(cx + 12, ty + 35, p1, 10.5, SOFT)
        b += text(cx + 12, ty + 51, p2, 10.5, SOFT)
        # 位等价章
        b += scirc(cx + col_w - 22, cy + 22, 10, L_GREEN, GREEN, 1.8)
        b += text(cx + col_w - 22, cy + 26, "✓", 12, GREEN, anchor="middle")

    # 底部：流量与覆盖公式带
    b += srect(60, 766, 1120, 54, fill=L_GREEN, stroke=GREEN, sw=2.0)
    b += mtext(76, 786, [
        "参数化定律（15 组全部对账）：load = 2·M·N·K · store = M·N · A 每格读 N 次 · B 每格读 M 次 · C 每格写 1 次",
        "维度 0：K=0 → 空归约＝单位元 0（C 全零，store 仍 M·N 次）；M=0/N=0 → 空输出（零趟循环、无任何访存）"], 12)

    b += text(60, 834, "数据来源：outputs/shape-matrix.txt（ST1 真实运行：15/15 组 11 项检查全过；种子 SEED=90）。", 12.5, SOFT)
    return svg_doc(W, H, b)


# ============================================================
# 图 3：方阵盲区机制（核心概念图）
# ============================================================

def img3() -> str:
    W, H = 1240, 800
    b = title_block(W, "方阵盲区：M、N、K 是三个旋钮——旋钮重合时，错误绑定的读数也一样",
                    "测试只能「区分」错误与正确；形状让错误与正确产生不同行为，才谈得上被发现")

    # 左上：三个旋钮
    b += srect(60, 100, 560, 300, fill="white", stroke=INK, sw=2.2)
    b += text(76, 126, "形状 = 三个独立的旋钮", 15, INK)
    knobs = [("M（行数）", 120), ("N（列数）", 200), ("K（归约长）", 280)]
    for label, ky in knobs:
        b += sline(110, ky, 300, ky, INK, 2.4)
        b += scirc(120 + 180, ky, 13, L_ORANGE, ORANGE, 2.2)
        b += text(96, ky - 22, label, 13, INK)
    b += mtext(96, 336, ["每个旋钮各管一段：i < M（行）· j < N（列）· k < K（归约）",
                         "strides 也是三个数：A=[K,1] · B=[N,1] · C=[N,1]"], 12)
    b += arrow(632, 250, 680, 250, SOFT, 2.6)

    # 右上：方阵 = 旋钮重合
    b += srect(688, 100, 492, 300, fill=L_RED, stroke=RED, sw=2.6)
    b += text(704, 128, "方阵 (3,3,3)：三个旋钮指着同一个数", 15, RED)
    b += sline(740, 170, 860, 170, RED, 2.4)
    for kx in (760, 800, 840):
        b += scirc(kx, 170, 13, L_ORANGE, RED, 2.2)
    b += mtext(704, 210, [
        "M=N=K=3 → 交换/错绑后的「错误读数」与正确读数数值相同：",
        "  · i 上界绑成 N：3 == 3 → 位相同（完全隐身）",
        "  · k 上界绑成 N：3 == 3 → 位相同（完全隐身）",
        "  · A[%k,%i] 配对写反：仍合法（读 Aᵀ）→ 静默算错，",
        "    不崩、不越界——没有参考对照就溜了（ST2 实测：",
        "    max|C−ref| = 2.199 / 1.701，两个 NUM 也是「无声」的）",
        "  · (1,1,1) 更进一步：四个变异全部位相同（ST4）",
    ], 12)

    # 中左：非方形 = 旋钮散开 → 错误暴露
    b += srect(60, 424, 560, 250, fill=L_GREEN, stroke=GREEN, sw=2.6)
    b += text(76, 450, "非方形 (2,3,5)：三个旋钮各指各的数", 15, GREEN)
    b += sline(110, 500, 300, 500, GREEN, 2.4)
    for kx, col in ((120, BLUE), (200, ORANGE), (280, RED)):
        b += scirc(kx, 500 - (kx - 120) * 0.12, 13, L_ORANGE, col, 2.2)
    b += mtext(76, 546, [
        "M=2、N=5、K=3 → 任何错绑都改变「读数」：",
        "  · i 上界绑成 N=5 > M=2 → 越界：load %a(1,0) 第 0 维 1 ∉ [0,2)",
        "  · k 上界绑成 N=5 > K=3 → 越界：load %a 走出归约维",
        "  · 配对写反 A[%k,%i] → 第 0 维越界（k 当行用）",
        "真实报错（ST3 实测，(2,3,5) 杀全部 4 个变异）：",
        "  memref.load %a(2,0)：第 0 维下标 2 ∉ [0, 2)（shape (2, 3)）",
    ], 12)

    # 右下：猎杀矩阵的「盲区也要记录」
    b += srect(688, 424, 492, 250, fill="white", stroke=INK, sw=2.2)
    b += text(704, 450, "盲区地图（SAME = 该形状杀不了这个变异）", 15, INK)
    b += mtext(704, 480, [
        "· 标量 (1,1,1)：四个变异全部 SAME——只测管道",
        "· N=0 (3,2,0)：四个变异全部 SAME——零趟循环无访存",
        "· K=0 / M=0：对配对类变异 SAME（无访存），",
        "  但对边界类变异亮红（OOB）——退化维各有分工",
        "· 巧合对各护一个盲区：M==N 护 i_ub_n · K==N 护 k_ub_n",
        "结论：单个形状必有盲区；矩阵整体没有——这便是",
        "「至少 8 组」背后的道理：形状组合起来才覆盖错误空间",
    ], 12)

    b += text(60, 780, "数据来源：outputs/kill-matrix.txt（ST2/ST3/ST4 真实运行；OOB=越界探针拦截，NUM=参考对照抓到的静默算错，SAME=位相同）。", 12.5, SOFT)
    return svg_doc(W, H, b)


# ============================================================
# 图 4：实测结果（ST 清单＋猎杀矩阵实色网格＋关键数字）
# ============================================================

def img4() -> str:
    W, H = 1240, 790
    b = title_block(W, "实测结果：ST1~ST7 全 PASS，形状矩阵 15/15，四个变异各被 ≥10 组杀死",
                    "环境：Linux aarch64，Python 3.11.4，numpy 1.26.4；本机未安装 MLIR（DialectConversion 语义仿真）")

    # 左：ST 清单
    b += srect(60, 100, 400, 330, fill="white", stroke=INK, sw=2.2)
    b += text(76, 126, "检查测试（全部真实运行）", 15, INK)
    sts = [
        ("ST1 形状矩阵端到端", "15 组 × 11 项：位等价/流量/覆盖/IV 轨迹"),
        ("ST2 方阵盲区", "(3,3,3)：2 个 NUM ＋ 2 个 SAME——全都不崩"),
        ("ST3 猎杀矩阵", "4 变异 × 15 形状：各杀 ≥10（OOB ≥5）"),
        ("ST4 维度 1 退化", "(1,1,1) 全 SAME；1×N/K=1/M×1 各有杀伤"),
        ("ST5 退化维 0", "K=0 → C 全零；M=0/N=0 → 空输出零访存"),
        ("ST6 静态与契约", "动态 '?' 宁拒不猜；回滚不留痕（边界形状版）"),
        ("ST7 修复闭环", "红→定位→修复→绿：四个变异各走一遍"),
    ]
    yy = 142
    for name, desc in sts:
        b += scirc(90, yy - 5, 9, L_GREEN, GREEN, 1.8)
        b += text(90, yy, "✓", 12, GREEN, anchor="middle")
        b += text(108, yy, name, 12.5, INK)
        b += text(118, yy + 17, desc, 11, SOFT)
        yy += 40

    # 右：猎杀矩阵实色网格
    b += srect(480, 100, 700, 330, fill="white", stroke=INK, sw=2.2)
    b += text(496, 126, "猎杀矩阵（真实运行）：行=形状，列=变异", 14.5, INK)
    gx, gy = 560, 148
    cw, ch = 148, 18
    cols = ["a_swap", "b_swap", "i_ub_n", "k_ub_n"]
    b += text(gx - 8, gy + 14, "形状", 11, SOFT, anchor="end")
    for j, c in enumerate(cols):
        b += text(gx + 12 + j * cw + 8, gy + 14, c, 12, INK)
    yy = gy + 24
    for cat, shp, _ in sp.SHAPE_MATRIX:
        label = f"{cat} {shp}"
        b += text(gx - 8, yy + 13, label, 10.5, SOFT, anchor="end")
        for j, mname in enumerate([m[0] for m in sp.MUTANTS]):
            status = KILL[shp][mname]
            fill, stroke = kill_color(status)
            b += srect(gx + 8 + j * cw, yy, cw - 6, 15, fill=fill, stroke=stroke,
                       sw=1.4, amp=0.7)
            b += text(gx + 8 + j * cw + (cw - 6) / 2, yy + 11.5, status, 10, INK,
                      anchor="middle")
        yy += 19.5
    # 图例
    lx, ly = 560, yy + 6
    b += text(lx, ly + 12, "图例：", 11.5, INK)
    for k, (status, meaning) in enumerate([
            ("OOB", "越界拦截（带报错）"),
            ("NUM", "静默算错（靠参考对照）"),
            ("SAME", "位相同（盲区）")]):
        fill, stroke = kill_color(status)
        b += srect(lx + 44 + k * 204, ly, 40, 15, fill=fill, stroke=stroke, sw=1.4, amp=0.7)
        b += text(lx + 64 + k * 204, ly + 11.5, status, 10, INK, anchor="middle")
        b += text(lx + 92 + k * 204, ly + 12, meaning, 10.5, SOFT)

    # 底部：关键数字卡
    cards = [
        ("15 组形状", "≥ 计划要求的 8 组；每组成员都有杀伤目标", L_BLUE, BLUE),
        ("7/7 PASS", "ST1~ST7 全部真实运行通过", L_GREEN, GREEN),
        ("11/15 杀伤", "每个变异被 ≥10 组形状杀死（OOB ≥5）", L_RED, RED),
        ("(2,3,5) 全杀", "M≠K≠N：四个变异全在越界处爆", L_ORANGE, ORANGE),
    ]
    x0, y0 = 60, 448
    for i, (big, small, fill, stroke) in enumerate(cards):
        cx = x0 + i * 286
        b += srect(cx, y0, 270, 84, fill=fill, stroke=stroke, sw=2.2, amp=1.1)
        b += text(cx + 135, y0 + 34, big, 17.5, INK, anchor="middle")
        b += text(cx + 135, y0 + 58, small, 11.5, SOFT, anchor="middle")

    # 底部：修复闭环样例（真实文本）
    b += srect(60, 552, 1120, 180, fill="white", stroke=INK, sw=2.2)
    b += text(76, 578, "修复闭环样例（ST7，真实运行；四个变异各有一条，此处展示 M4）", 14, INK)
    b += mtext(76, 604, [
        "红（OOB 路径）：A(6,1)@B(1,4)，k 上界绑成 %cN=4 → memref.load %a(0,1)：第 1 维下标 1 ∉ [0, 1)（shape (6, 1)）",
        "红（NUM 路径）：A(4,6)@B(6,3)，k 只累加 3/6 项 → max|C − ref| = 4.081e+00（部分和，静默算错）",
        "定位：LoopSpec 出生证明写着「K ← 内维契约」，而 IR 里 for %k 绑的是 %c3（= N）——应然 vs 实然一对照即见错位",
        "修复：k 循环上界绑回 %cK（K = 内维契约 A.shape[1]==B.shape[0]）→ 绿：killer 形状位等价 ✓ ＋ 全矩阵 15/15 回归",
    ], 12.5)

    b += srect(60, 744, 1120, 34, fill="white", stroke=SOFT, sw=1.6, dash="6 5")
    b += text(76, 766, "诚实边界：四个变异是故意注入的探针（D89 的 Pattern 在预飞 7 组已全绿）；猎杀矩阵证明的是「形状矩阵有牙齿」，并演练修复闭环。", 11.5, SOFT)
    return svg_doc(W, H, b)


def main():
    OUT.mkdir(exist_ok=True)
    for name, fn in [("01-overview.svg", img1), ("02-shape-matrix.svg", img2),
                     ("03-blindness.svg", img3), ("04-results.svg", img4)]:
        path = OUT / name
        path.write_text(fn(), encoding="utf-8")
        print(f"已生成 {path}（{path.stat().st_size} 字节）")


if __name__ == "__main__":
    main()
