#!/usr/bin/env python3
"""生成第 91 天教程的 4 张手绘风（Excalidraw-like）SVG 技术图。

运行方式：
    python3 make_images.py

输出到 ../images/ 目录：
    01-overview.svg          第 91 天在第 13 周与编译链路中的位置 + 输入与产出
    02-sketch-vs-ir.svg      手画 2×3 乘 3×2 的循环与索引示例 × 生成 IR 对照
    03-preservation-map.svg  语义保持映射：六条款 → 循环 IR 实现点 → 真实探针
    04-results.svg           实测结果：19 项检查、变异结局网格、数字面板（真实运行）

风格与 Day 78~90 保持一致：手绘抖动线条、马克笔笔触、米白背景、
蓝/橙/绿/红四种柔和强调色、简单几何形状。
图中文字与数字全部来自 review_pass.py 的真实运行结果（RT1~RT4）。
"""

import math
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent.parent / "day-090" / "code"))

import shape_pass as sp  # noqa: E402  （真实数据来源：复跑 Day 90 ST1）

random.seed(91)

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

OUT = HERE.parent / "images"
OUT.mkdir(exist_ok=True)


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


def srect(x, y, w, h, fill="none", stroke=INK, sw=2.2, amp=1.3, dash=None, rx=0):
    pts = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
    d = " ".join(jseg(*p, *q, amp) for p, q in zip(pts, pts[1:] + pts[:1]))
    r = f' rx="{rx}"' if rx else ""
    return f'<path d="{d} Z" {style(fill, stroke, sw, dash)}{r}/>'


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


def save(name, w, h, body):
    (OUT / name).write_text(svg_doc(w, h, body), encoding="utf-8")
    print(f"{name} 已生成（{w}×{h}）")


# ============================================================
# 真实数据：复跑 Day 90 ST1（与 review_pass.py RT4c 同源）
# ============================================================

_, _, ST1_ROWS = sp.st1_matrix()
N_PASS = sum(1 for r in ST1_ROWS if r["good"])

# review_pass.py 真实运行结果（2026-11-13，本机 aarch64 Linux）
CELL11 = [   # C[1,1] 的 K 项展开（--cell 1 1 的真实输出，种子 91）
    ("k=0", "A[1,0]@3 · B[0,1]@1", "-0.275686 · +2.178656", "-0.600625"),
    ("k=1", "A[1,1]@4 · B[1,1]@3", "+1.222254 · +0.517257", "+0.031594"),
    ("k=2", "A[1,2]@5 · B[2,1]@5", "-0.905859 · -1.054888", "+0.987173"),
]
MUT_GRID = [("a_swap", "OOB"), ("b_swap", "OOB"), ("i_ub_n", "SAME"), ("k_ub_n", "NUM")]


# ============================================================
# 图 1：全局位置图
# ============================================================

def fig1():
    w, h = 1120, 690
    b = title_block(w, "第 91 天 · 第 13 周复盘：语义保持站在哪？",
                    "输入是六天的局部检查，产出是一个整体论证——Lowering 前后 IR ＋ 正确性报告 ＋ 一页复盘")

    # ---- 上排：第 13 周七天链路 ----
    b += text(30, 114, "① 第 13 周七天（D85~D91）：每天往「语义保持论证」里添一块砖", 15.5, BLUE, bold=True)
    days = [("D85", "设计"), ("D86", "骨架"), ("D87", "初始化"), ("D88", "三重循环"),
            ("D89", "循环体"), ("D90", "边界形状"), ("D91", "复盘")]
    x0, y0, bw, bh, gap = 34, 128, 134, 64, 20
    for i, (d, t) in enumerate(days):
        x = x0 + i * (bw + gap)
        today = (d == "D91")
        fill, stroke = (L_ORANGE, ORANGE) if today else (L_BLUE, BLUE)
        b += srect(x, y0, bw, bh, fill, stroke, 2.6, rx=8)
        b += text(x + bw / 2, y0 + 27, d, 17, stroke, "middle", bold=True)
        b += text(x + bw / 2, y0 + 48, t, 13, INK, "middle")
        if i < len(days) - 1:
            b += arrow(x + bw + 1, y0 + bh / 2, x + bw + gap - 3, y0 + bh / 2, SOFT, 2.0)
    b += text(34, y0 + bh + 24,
              "D85 列「应然」清单 → D86 保证失败不留痕 → D87~D89 逐块兑现 → D90 证明测试有牙齿 → D91 组装成论证",
              12.5, SOFT)

    # ---- 中排：编译链路与今日焦点 ----
    b += text(30, 252, "② 今天的问题：mini.matmul → 循环实现，凭什么说「语义没变」？", 15.5, BLUE, bold=True)
    boxes = [
        (34, 268, 250, 118, "图算子层（Lowering 前）", L_GREEN, GREEN,
         ["mini.matmul(%x, %w)", "tensor<2x3xf32> 值语义", "一个 op 概括全部语义", "（outputs/pre-ir.txt）"]),
        (435, 268, 250, 118, "Lowering（Pattern＋Rewriter）", L_ORANGE, ORANGE,
         ["MatMulBodyPattern（D89 形态）", "事务性：失败回滚不留痕", "match 检查 → rewrite 生成", "18 op 全部经 rewriter"]),
        (836, 268, 250, 118, "循环/内存层（Lowering 后）", L_GREEN, GREEN,
         ["scf.for ×3 ＋ load/store", "memref strided<[3,1]>…", "（outputs/post-ir.txt）", "结构恒 18 op"]),
    ]
    for x, y, bw2, bh2, t, fill, stroke, sub in boxes:
        b += srect(x, y, bw2, bh2, fill, stroke, 2.6, rx=8)
        b += text(x + bw2 / 2, y + 25, t, 14.5, stroke, "middle", bold=True)
        b += mtext(x + bw2 / 2, y + 48, sub, 11.8, INK, "middle", 17)
    b += arrow(288, 327, 431, 327, INK, 3.0)
    b += arrow(689, 327, 832, 327, INK, 3.0)
    b += text(359, 315, "Lowering", 12.5, SOFT, "middle")
    b += text(760, 315, "同上", 12.5, SOFT, "middle")
    # 红色横括线：整排变化 = 语义保持的对象
    b += sline(34, 412, 1086, 412, RED, 2.0, dash="8 6")
    b += text(560, 434, "这一整排的变化＝Lowering；今天验证的正是：前后语义保持（semantic preservation）",
              13, RED, "middle", bold=True)

    # ---- 下排：输入与产出 ----
    b += text(30, 472, "③ 今日输入与产出", 15.5, BLUE, bold=True)
    b += srect(34, 488, 470, 148, L_BLUE, BLUE, 2.6, rx=8)
    b += text(50, 512, "输入：Day 85~90 的局部检查（各自全绿）", 14, BLUE, bold=True)
    b += mtext(50, 534, [
        "· Day 87~89：18 op 循环体（alloc/%zero/LoopSpec/访存）",
        "· Day 90：15 组形状矩阵（15/15）＋ 4 变异猎杀矩阵",
        "· 六天各自的「绿」——但还没人把它们拼成一个论证",
    ], 12.5, INK, "start", 19)
    b += arrow(510, 562, 600, 562, INK, 3.0)
    b += srect(606, 488, 480, 148, L_ORANGE, ORANGE, 2.6, rx=8)
    b += text(622, 512, "产出：计划点名的三件（outputs/ 五个文件）", 14, ORANGE, bold=True)
    b += mtext(622, 534, [
        "· pre-ir.txt / post-ir.txt —— 前后 IR（RT1）",
        "· correctness-report.txt —— 正确性报告（RT3/RT4）",
        "· review.txt —— 一页复盘（RT5）",
        "· sketch-check.txt —— 手画对账（RT2）",
    ], 12.5, INK, "start", 18)
    b += text(30, h - 16,
              "复盘例 A(2,3)@B(3,2)→C(2,2) 恰是 M==N 巧合对——正确性报告必须引用形状矩阵整体（Day 90 猎杀：i_ub_n 被 11/15 组杀死）",
              12.5, SOFT)
    save("01-overview.svg", w, h, b)


# ============================================================
# 图 2：手画 2×3 乘 3×2 × 生成 IR 对照（核心机制图）
# ============================================================

def draw_grid(x, y, rows, cols, cell, name, note, hl=None):
    """画一个 rows×cols 手绘网格：格内标线性地址，可选高亮若干格。"""
    b = ""
    for r in range(rows):
        for c in range(cols):
            gx, gy = x + c * cell, y + r * cell
            on = hl and (r, c) in hl
            fill = L_ORANGE if on else "white"
            stroke = ORANGE if on else INK
            b += srect(gx, gy, cell, cell, fill, stroke, 1.6, amp=0.9)
            b += text(gx + cell / 2, gy + cell / 2 + 5, str(r * cols + c), 13.5,
                      ORANGE if on else SOFT, "middle")
    b += text(x, y - 10, name, 15, INK, "start", bold=True)
    b += text(x, y + rows * cell + 18, note, 12, SOFT)
    return b


def fig2():
    w, h = 1150, 830
    b = title_block(w, "手画 2×3 乘 3×2 的循环与索引 × 生成 IR（RT2 逐行对账）",
                    "左边是纸上手画（预期），右边是真实转换出的 IR——中间每一行都能对上（✓ 来自 19/19 PASS 的真实运行）")

    # ---- 左：手画区 ----
    b += srect(30, 100, 530, 650, "white", SOFT, 1.8, dash="9 6", rx=10)
    b += text(48, 128, "手画（先不看 IR，在纸上写下预期）", 15.5, BLUE, bold=True)

    # 三个网格：A(2×3)、B(3×2)、C(2×2)
    b += draw_grid(56, 148, 2, 3, 40, "A (2×3)", "addr = 3i+k", hl={(1, 0), (1, 1), (1, 2)})
    b += draw_grid(240, 148, 3, 2, 40, "B (3×2)", "addr = 2k+j", hl={(0, 1), (1, 1), (2, 1)})
    b += draw_grid(410, 148, 2, 2, 40, "C (2×2)", "addr = 2i+j", hl={(1, 1)})
    b += text(56, 308, "橙色格＝C[1,1] 这一趟要碰的格子（下文展开）", 12, ORANGE)

    # 循环嵌套
    b += text(48, 336, "三重循环（半开区间，手画四要素）", 14, INK, bold=True)
    nest = [("for %i = 0 to 2 step 1   (i<M, M=2)", 42), ("for %j = 0 to 2 step 1   (j<N, N=2)", 30),
            ("for %k = 0 to 3 step 1   (k<K, K=3)", 18)]
    yy = 352
    for label, ind in nest:
        b += srect(52 + ind, yy, 460 - ind * 2, 50, "none", BLUE, 2.0, rx=8)
        b += text(66 + ind, yy + 31, label, 13.5, INK)
        yy += 58
    b += text(70, yy + 4, "acc = 0.0；每趟 acc += A[i,k]·B[k,j]", 13, SOFT)
    b += text(70, yy + 24, "k 循环结束 → store C[i,j]（每格恰写 1 次终值）", 13, SOFT)

    # C[1,1] 展开（真实值）
    ty = yy + 52
    b += text(48, ty, "C[1,1] 的 K=3 项展开（真实值，种子 91）", 14, INK, bold=True)
    b += srect(52, ty + 10, 486, 112, L_GREEN, GREEN, 2.0, rx=8)
    for i, (kk, pair, vals, acc) in enumerate(CELL11):
        b += text(66, ty + 34 + i * 27, f"{kk}: {pair}", 12.5, INK)
        b += text(248, ty + 34 + i * 27, vals, 12.5, SOFT)
        b += text(436, ty + 34 + i * 27, f"→ {acc}", 12.5, GREEN)
    b += text(66, ty + 124, "终值 +0.987173 ＝ 执行器实测 C[1,1]（逐位相等 True）→ store @3", 12.5, GREEN)

    # ---- 右：生成 IR ----
    b += srect(580, 100, 540, 650, "white", SOFT, 1.8, dash="9 6", rx=10)
    b += text(598, 128, "生成 IR（真实转换输出，outputs/post-ir.txt 摘录）", 15.5, BLUE, bold=True)
    ir = [
        ("func @main(%a: memref<2x3xf32, strided<[3,1]>>,", None),
        ("             %b: memref<3x2xf32, strided<[2,1]>>)", None),
        ("  -> memref<2x2xf32, strided<[2,1]>> {", "类型＝手画 strides ✓"),
        ("  %c = memref.alloc() : memref<2x2xf32,...>", "输出缓冲（S5）✓"),
        ("  %zero = arith.constant 0.0 : f32", "单位元（S4）✓"),
        ("  %c0/%c1/%c2/%c2'/%c3 = ...  // {0,1,M,N,K}", "={0,1,2,2,3} ✓"),
        ("  scf.for %i = %c0 to %c2 step %c1 {", "i∈[0,2) ← M ✓"),
        ("    scf.for %j = %c0 to %c2' step %c1 {", "j∈[0,2) ← N ✓"),
        ("      %acc = scf.for %k = %c0 to %c3 step %c1", "k∈[0,3) ← K ✓"),
        ("        iter_args(%acc = %zero) -> (f32) {", "初值＝零 ✓"),
        ("        %xa = memref.load %a[%i, %k]", "A[i,k] ✓"),
        ("        %xb = memref.load %b[%k, %j]", "B[k,j] ✓"),
        ("        %p  = arith.mulf %xa, %xb : f32", "乘积项 ✓"),
        ("        %s  = arith.addf %acc, %p : f32", "累加链 ✓"),
        ("        scf.yield %s : f32", "写回通道 ✓"),
        ("      }", None),
        ("      memref.store %acc, %c[%i, %j]", "C[i,j] ✓"),
        ("    }  }  }", None),
        ("  return %c : memref<2x2xf32,...>", None),
        ("}", None),
    ]
    iy = 156
    for line, note in ir:
        b += text(598, iy, line, 11.6, INK)
        if note:
            b += text(892, iy, note, 11.5, GREEN)
        iy += 24.4
    # 对账箭头（左内容 → 右 IR）
    b += carrow((516, 380), (566, 380), (596, 392), RED, 2.4)
    b += carrow((540, ty + 60), (568, ty + 60), (596, ty + 48), RED, 2.4)

    # ---- 底部对账横幅 ----
    b += srect(30, 768, 1090, 46, L_RED, RED, 2.4, rx=8)
    b += text(575, 796,
              "对账结论：手画的每一行（循环/配对/地址/项数/流量/覆盖）都被 IR 与访存日志证实——28/28 条地址逐条 ＝ 3i+k / 2k+j / 2i+j（RT2 真实运行）",
              12.5, INK, "middle", bold=True)
    save("02-sketch-vs-ir.svg", w, h, b)


# ============================================================
# 图 3：语义保持映射（六条款 → 实现点 → 探针）
# ============================================================

def fig3():
    w, h = 1160, 700
    b = title_block(w, "语义保持映射：六条款 → 循环 IR 实现点 → 真实探针（RT3 审计）",
                    "「Lowering 没改变语义」不是一句口号——每条承诺都能指到 18 op 里的实现点，且每条都有今天真跑出的证据")
    col1, col2, col3 = 34, 424, 814
    cw = 340
    b += text(col1 + cw / 2, 112, "mini.matmul 的语义条款", 15, BLUE, "middle", bold=True)
    b += text(col2 + cw / 2, 112, "循环 IR（18 op）里的实现点", 15, ORANGE, "middle", bold=True)
    b += text(col3 + cw / 2, 112, "探针与真实结果（本机实测）", 15, GREEN, "middle", bold=True)
    rows = [
        ("S1 数学定义", "C[i,j] = Σ_{k<K} A[i,k]·B[k,j]",
         ["三重循环 ＋ load/mulf/addf", "iter_args 累加链"],
         ["位等价（同序参考）= True", "每格恰 3 项（日志逐格计数）"]),
        ("S2 形状契约", "输出 (M,N)=(2,2)；内维 K=3 匹配",
         ["LoopSpec ub ← M/N/K", "strided<[3,1]>/<[2,1]>/<[2,1]>"],
         ["18 op ✓ 常量 {0,1,2,2,3} ✓", "LoopSpec (i<M, j<N, k<K) ✓"]),
        ("S3 数值语义", "f32；k 升序逐步舍入",
         ["iter_args(%acc=%zero)", "每趟 addf 舍入一次，k 升序"],
         ["位等价 = True", "np.matmul 差 1.19e-07（顺序）"]),
        ("S4 边界语义", "任意非负 M/N/K；K=0 → C 全零",
         ["trip = max(0, ceil((ub-lb)/step))", "%zero 初值：零趟出门"],
         ["K=0 回归：C 全零 True", "load 0 · store 12（D87 兑现）"]),
        ("S5 内存语义", "独立缓冲；每格终值恰写 1 次",
         ["memref.alloc %c", "store 在 k 外 j 内"],
         ["覆盖 C×1 ✓ 未初始化读 0", "store 4 次全落 %c"]),
        ("S6 保守边界", "静态 Pattern 遇 '?' 宁拒不猜",
         ["match 检测 '?' → 拒绝", "事务 Rewriter 回滚"],
         ["动态 M=? 输入：转换拒绝", "回滚不留痕（ST6 回归）"]),
    ]
    y, rh, gap = 128, 74, 9
    for (s_name, s_promise, impl, probes) in rows:
        b += srect(col1, y, cw, rh, L_BLUE, BLUE, 2.2, rx=8)
        b += text(col1 + 14, y + 27, s_name, 14, BLUE, bold=True)
        b += mtext(col1 + 14, y + 50, [s_promise], 12, INK)
        b += arrow(col1 + cw + 4, y + rh / 2, col2 - 6, y + rh / 2, SOFT, 2.0)
        b += srect(col2, y, cw, rh, L_ORANGE, ORANGE, 2.2, rx=8)
        b += mtext(col2 + 14, y + 28, impl, 11.8, INK, "start", 17.5)
        b += arrow(col2 + cw + 4, y + rh / 2, col3 - 6, y + rh / 2, SOFT, 2.0)
        b += srect(col3, y, cw, rh, L_GREEN, GREEN, 2.2, rx=8)
        b += mtext(col3 + 14, y + 28, probes, 11.8, INK, "start", 17.5)
        y += rh + gap
    # 底部横幅：分辨力
    by = y + 6
    b += srect(col1, by, col3 + cw - col1, 66, L_RED, RED, 2.4, rx=8)
    b += text(col1 + 16, by + 27, "但是：全绿 ≠ 正确——论证还差「分辨力」这一块", 14.5, RED, bold=True)
    b += text(col1 + 16, by + 49,
              "复盘例 (2,3,2) 上 i_ub_n 变异 SAME（M==N=2 盲区，位相同完全隐身）→ 引用 Day 90 形状矩阵整体：i_ub_n 被 11/15 组杀死、全矩阵 15/15 回归",
              12, INK)
    save("03-preservation-map.svg", w, h, b)


# ============================================================
# 图 4：实测结果
# ============================================================

def fig4():
    w, h = 1150, 640
    b = title_block(w, "实测结果：19 项检查全 PASS（真实运行）",
                    "环境：Linux aarch64 · Python 3.11.4 · numpy 1.26.4 · 本机未装 MLIR（Day 57~90 口径：DialectConversion 语义仿真）")

    # 左：检查清单
    b += srect(34, 106, 360, 400, L_GREEN, GREEN, 2.4, rx=8)
    b += text(50, 134, "RT1~RT4 检查清单（19/19 PASS）", 14.5, GREEN, bold=True)
    items = [
        "RT1a 源图结构：func+mini.matmul+return",
        "RT1b 终图 18 op 序列（结构恒定）",
        "RT1c LoopSpec：(i:0..2, j:0..2, k:0..3)",
        "RT1d 常量多重集 {0,1,2,2,3}",
        "RT2a 三重循环四要素＝手画",
        "RT2b 配对 A[i,k]/B[k,j]/C[i,j]",
        "RT2c 28/28 条访存地址＝手画公式",
        "RT2d 每格乘积项数 = K = 3",
        "RT2e load 24 / store 4",
        "RT2f 覆盖 A×2 / B×2 / C×1",
        "S1..S6 六条款审计（各 1 项）",
        "RT4a 变异结局＝预测（对账）",
        "RT4b 复盘例盲区：i_ub_n SAME",
        "RT4c 全矩阵回归 15/15",
    ]
    for i, it in enumerate(items):
        yy = 158 + i * 24
        b += scirc(62, yy - 5, 8.5, L_GREEN, GREEN, 1.8)
        b += text(62, yy - 1, "✓", 11, GREEN, "middle")
        b += text(80, yy, it, 12.2, INK)

    # 中：变异结局网格
    b += srect(414, 106, 350, 400, "white", SOFT, 2.0, rx=8)
    b += text(430, 134, "4 个注入变异 × 复盘例 (2,3,2)", 14.5, ORANGE, bold=True)
    colors = {"OOB": (L_RED, RED), "NUM": (L_ORANGE, ORANGE), "SAME": (GREY, SOFT)}
    notes = {"OOB": "越界拦截（带诊断）", "NUM": "静默算错（只有参考对照抓得住）",
             "SAME": "位相同（该形状免疫＝盲区）"}
    for i, (m, st) in enumerate(MUT_GRID):
        yy = 156 + i * 82
        fill, stroke = colors[st]
        b += srect(430, yy, 318, 68, fill, stroke, 2.2, rx=8)
        b += text(446, yy + 27, m, 14.5, INK, bold=True)
        b += text(446, yy + 50, f"{st}：{notes[st]}", 12, SOFT)
        b += text(734, yy + 30, st, 17, stroke, "middle", bold=True)
    b += text(430, 498, "预测在前、实测对账：OOB/OOB/SAME/NUM 全中（RT4a）", 12, SOFT)

    # 右：数字卡片
    b += srect(784, 106, 332, 400, "white", SOFT, 2.0, rx=8)
    b += text(800, 134, "数字面板（全部真实运行）", 14.5, BLUE, bold=True)
    cards = [
        ("18 op", "IR 结构恒定（形状是数据）"),
        ("28/28", "访存地址逐条＝手画公式"),
        ("24 / 4", "load = 2MNK / store = MN"),
        ("15/15", "Day 90 形状矩阵原样复跑"),
        ("1.19e-07", "np.matmul 差值（顺序不同）"),
    ]
    for i, (num, note) in enumerate(cards):
        yy = 156 + i * 68
        b += srect(800, yy, 300, 56, L_BLUE, BLUE, 2.0, rx=8)
        b += text(818, yy + 34, num, 19, BLUE, bold=True)
        b += text(930, yy + 33, note, 11.8, INK)

    # 底部：产出文件条
    b += srect(34, 526, 1082, 74, L_ORANGE, ORANGE, 2.4, rx=8)
    b += text(50, 552, "五个产出文件（outputs/，随 review_pass.py 生成）", 14, ORANGE, bold=True)
    b += text(50, 574,
              "pre-ir.txt（前 IR）· post-ir.txt（后 IR）· sketch-check.txt（手画对账）· correctness-report.txt（正确性报告）· review.txt（一页复盘）",
              12.2, INK)
    b += text(50, 592, "复跑：python3 review_pass.py　｜　单格展开：--cell 1 1　｜　变异体验：--mutant i_ub_n", 12.2, SOFT)
    save("04-results.svg", w, h, b)


if __name__ == "__main__":
    fig1()
    fig2()
    fig3()
    fig4()
    print("全部 4 张 SVG 已生成到", OUT)
