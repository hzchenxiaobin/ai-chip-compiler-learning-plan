#!/usr/bin/env python3
"""生成第 115 天的 3 张手绘 sketch 风 SVG 技术图（Excalidraw-like）。

风格与 D110~D114 一致：白板涂鸦感——带抖动的贝塞尔手绘路径、马克笔笔触、
3～4 种柔和强调色（蓝/橙/绿/红）＋米白背景、简单几何形状、手写感字体。
所有数字来自 outputs/ 的真实冻结运行（func-report.txt /
func-report-s232.txt，2026-11-13，Python 3.11.4 aarch64，numpy 1.26.4，
llvmlite 0.50.0 内嵌 LLVM 22.1.0，gcc 9.4.0）。固定随机种子，图可复现。
"""

from __future__ import annotations

import math
import os
import random
import xml.sax.saxutils as su

random.seed(115)

BG = "#FDFBF6"
BORDER = "#E7DFCE"
INK = "#3B3B3B"
MUTED = "#6b6257"
ORANGE = "#E8A87C"
BLUE = "#A9C4D4"
GREEN = "#9CBF8E"
RED = "#C97B7B"
FONT = "'Comic Sans MS','Kaiti SC','KaiTi','STKaiti',cursive"


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


def frame(w, h, title):
    body = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
            f'font-family="{FONT}">',
            hand_rect(4, 4, w - 8, h - 8, BG, 1.0, BORDER, 2),
            text(w / 2, 34, title, 17.5, INK, "middle", True)]
    return body


def save(name, body):
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "..", "images", name)
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(body) + "\n</svg>\n")
    print(f"  已生成 images/{name}")


def card(b, x, y, w, h, title, lines, fill, tsize=11.5, lsize=10,
         opacity=0.42, anchor_left=False, mono_lines=None):
    b.append(hand_rect(x, y, w, h, fill, opacity, INK, 1.6))
    ax = x + 12 if anchor_left else x + w / 2
    aanchor = "start" if anchor_left else "middle"
    if title:
        b.append(text(ax, y + 19, title, tsize, INK, aanchor, True))
    for i, ln in enumerate(lines):
        b.append(text(ax, y + 36 + i * 16, ln, lsize, INK, aanchor))
    for i, ln in enumerate(mono_lines or []):
        b.append(text(ax, y + 36 + len(lines) * 16 + i * 14.5, ln, 9.3,
                      MUTED, aanchor, mono=True))


# ======================= 图 1：全局定位图 =======================

def fig1():
    W, H = 1020, 730
    b = frame(W, H, "第 115 天定位：第 17 周动工第一天——把 D114 清单的第一段（F1/R1/A1）落成真代码")
    b.append(hand_line(300, 44, 720, 45, ORANGE, 3))

    # 上排：编译链路
    b.append(text(48, 68, "编译链路：今天走到哪一站？", 12.5, INK, "start", True))
    chain = [
        (60, 150, "图 IR", "mini 方言", BG, "已完成"),
        (165, 275, "循环＋内存 IR", "scf·memref", BG, "D85~D105"),
        (290, 450, "今天：函数与类型", "F1/R1/A1", GREEN, "D115 ★"),
        (465, 625, "算子与内存", "M1~M3/A2~A3", BG, "D116"),
        (640, 780, "循环＋导出", "C1→LLVM IR", BG, "D117"),
        (795, 965, "执行", "JIT / AOT", BG, "D118"),
    ]
    y0 = 86
    for x1, x2, name, sub, fill, sched in chain:
        b.append(hand_rect(x1, y0, x2 - x1, 52, fill, 0.55, INK, 1.6))
        b.append(text((x1 + x2) / 2, y0 + 22, name, 12.5, INK, "middle", True))
        b.append(text((x1 + x2) / 2, y0 + 40, sub, 9.5, MUTED, "middle"))
        b.append(text((x1 + x2) / 2, y0 + 62, sched, 9.5,
                      GREEN if fill == GREEN else MUTED, "middle"))
    for i in range(5):
        x1, x2 = chain[i][1], chain[i + 1][0]
        b.append(arrow(x1 + 3, y0 + 26, x2 - 3, y0 + 26, INK, 1.8))
    b.append(text(510, y0 + 82, "最终 Lowering 段：D113 读样本 → D114 写清单 → D115~D118 按清单施工",
                  10.5, MUTED, "middle"))

    # 中排：本周排期条
    b.append(text(48, 208, "第 17 周排期：今天只做函数与类型，别把 D116 的活提前干了", 12.5, INK, "start", True))
    days = [("D113", "读目标语言样本", True), ("D114", "类型表＋合法性清单", True),
            ("D115", "函数转换＋类型测试", False), ("D116", "Elementwise＋访存", False),
            ("D117", "循环＋导出 LLVM IR", False), ("D118", "执行与校验", False)]
    bw = 148
    for i, (d, desc, done) in enumerate(days):
        x1 = 60 + i * (bw + 4)
        fill = BG if done else (ORANGE if d == "D115" else BG)
        b.append(hand_rect(x1, 224, bw, 64, fill, 0.65 if d == "D115" else 0.45,
                           INK, 1.8 if d == "D115" else 1.4))
        b.append(text(x1 + bw / 2, 244, d, 12, INK, "middle", True))
        b.append(text(x1 + bw / 2, 262, desc, 9.5, MUTED, "middle"))
        if done:
            b.append(text(x1 + bw / 2, 280, "✓ 已完成", 9, GREEN, "middle"))
        elif d == "D115":
            b.append(text(x1 + bw / 2, 280, "★ 今天", 9, INK, "middle", True))

    # 下排：今天三个概念
    b.append(text(48, 330, "今天的三件事（一根链条：换类型 → 算字节 → 定怎么传）", 12.5, INK, "start", True))
    card(b, 55, 346, 288, 150, "① 函数签名转换（F1）",
         ["memref 参数 → 5 字段描述符结构体", "index → i64，f32 原样",
          "0/1/≥2 结果 → void/直返/打包 struct", "残账里 scf·memref·arith 留给 D116/D117"],
         BLUE, 11.5, 10, 0.45, True)
    card(b, 367, 346, 288, 150, "② DataLayout：类型→字节的规则书",
         ["大小：f32=4B，ptr=8B，i64=8B", "对齐：结构体逐成员补齐到边界",
          "index 位宽＝目标指针宽（64 位）", "rank1/2/3 描述符＝40/56/72B，align 8"],
         GREEN, 11.5, 10, 0.45, True)
    card(b, 679, 346, 288, 150, "③ ABI 基础：字节怎么上寄存器/栈",
         [">16B 聚合＝调用方复制＋传地址（indirect）", "大返回＝x8 隐式结果指针（sret）",
          "JIT 入口按 C ABI 用 ptr 签名", "证据链：gcc 汇编＋ctypes 实测"],
         ORANGE, 11.5, 10, 0.45, True)
    for x1, x2 in [(343, 367), (655, 679)]:
        b.append(arrow(x1 + 2, 420, x2 - 2, 420, INK, 1.8))

    # 底部：今日真实数字预告
    b.append(text(48, 540, "今天结束时的真实证据（全部来自本机冻结运行）", 12.5, INK, "start", True))
    facts = [
        (160, "8/18", "op 今天能转，残账 10 条带排期"),
        (390, "56B/8", "rank2 描述符，偏移 0,8,16,24,40"),
        (620, "112→56", "GEMM 参数/返回的 ABI 字节账"),
        (852, "36/36", "真机 peek 全点 bitwise 对"),
    ]
    for x, big, small in facts:
        b.append(text(x, 578, big, 20, INK, "middle", True))
        b.append(text(x, 600, small, 9.5, MUTED, "middle"))
    b.append(hand_line(55, 620, 965, 621, BORDER, 2))
    b.append(text(510, 648, "验收标准沿用 D114 立下的两条：对照实验 B 的两道闸（tensor 拒收、mini 非法）今天变成可执行的检查",
                  10.5, MUTED, "middle"))
    b.append(text(510, 668, "诚实声明：本机无 mlir-opt，四角色为教学仿真；但布局数字对账真 LLVM、ABI 证据来自真 gcc 汇编与真机 JIT 调用",
                  10.5, MUTED, "middle"))
    save("01-overview.svg", b)


# ======================= 图 2：机制图 =======================

def fig2():
    W, H = 1020, 780
    b = frame(W, H, "机制：一条函数签名怎么过海关——类型兑换、字节布局、胶水与 ABI")
    b.append(hand_line(310, 44, 700, 45, ORANGE, 3))

    # 左上：源签名
    card(b, 50, 66, 380, 96, "源：func @gemm（循环 IR 的函数头）",
         [], BLUE, 11.5, 10, 0.45, True,
         mono_lines=["%a: memref<4x6xf32, strided<[6,1]>>",
                     "%b: memref<6x3xf32, strided<[3,1]>>",
                     "-> memref<4x3xf32, strided<[3,1]>>"])
    # 中上：兑换关卡
    card(b, 480, 66, 210, 96, "TypeConverter", ["逐参数查兑换表", "查 DataLayout 记字节账",
                                                "结果 0/1/≥2 →", "void / 直返 / 打包 struct"],
         GREEN, 11.5, 10, 0.45, False)
    # 右上：目标签名
    card(b, 740, 66, 240, 96, "目标：llvm.func @gemm",
         [], ORANGE, 11.5, 10, 0.45, True,
         mono_lines=["%a: !llvm.struct<(ptr,ptr,i64,",
                     "  array<2xi64>,array<2xi64>)>",
                     "%b: 同上",
                     "-> !llvm.struct<...>（56B）"])
    b.append(arrow(432, 114, 478, 114, INK, 1.8, label="F1"))
    b.append(arrow(692, 114, 738, 114, INK, 1.8))
    b.append(text(510, 190, "拒收清单（两道闸之一）：tensor（必须先 bufferize）｜动态 shape memref｜未知类型——签名当场失败，函数进不了海关",
                  10, MUTED, "middle"))

    # 中部：描述符解剖
    b.append(text(50, 224, "描述符解剖：5 个字段按顺序排好，56 字节（与真机 LLVM TargetData 逐项对账）",
                  12.5, INK, "start", True))
    fields = [("allocated", 8, 0, "分配指针（malloc 返回）"),
              ("aligned", 8, 8, "对齐后的起始指针"),
              ("offset", 8, 16, "元素偏移"),
              ("sizes[2]", 16, 24, "每维长度"),
              ("strides[2]", 16, 40, "每维步长（元素单位）")]
    x = 150
    scale = 9.0
    for i, (name, size, off, note) in enumerate(fields):
        w = size * scale
        fill = [BLUE, BLUE, GREEN, ORANGE, ORANGE][i]
        b.append(hand_rect(x, 240, w, 54, fill, 0.5, INK, 1.6))
        b.append(text(x + w / 2, 260, name, 10.5, INK, "middle", True))
        b.append(text(x + w / 2, 276, f"{size}B", 9.5, MUTED, "middle"))
        b.append(text(x + w / 2, 288, f"@{off}", 9, MUTED, "middle"))
        x += w
    b.append(text(50, 314, "总大小 56B，ABI 对齐 8；rank1=40B、rank3=72B——数组字段的对齐是元素对齐（8B），不是整块大小",
                  10, MUTED, "start"))

    # 左下：胶水（三类）
    card(b, 50, 340, 430, 190, "半转换产物里的 8 条胶水（unrealized_conversion_cast）",
         ["入口参数已换新类型，残留 op 还要旧值 → 源物化：",
          "  %a_m = cast %a : !llvm.struct<...> -> memref<...>   ×2",
          "  %c0_i = cast %c0 : i64 -> index   ×5（scf.for 还要 index）",
          "返回值要新类型，旧值要换新 → 目标物化：",
          "  %c_d = cast %c : memref<...> -> !llvm.struct<...>   ×1",
          "账本：D116 的 M1~M3/A2~A3 逐条消费这些旧值；",
          "D117 导出前由 reconcile-unrealized-casts 清零"],
         GREEN, 11.5, 10.2, 0.42, True)

    # 右下：ABI 三形态
    card(b, 510, 340, 465, 190, "ABI 三形态：同一个 offset=42 的真机实测（aarch64）",
         ["✓ define @f(ptr %d)＋ctypes 传 &desc → 读到 42",
          "  C ABI 上 >16B 聚合本来就'间接传'：gcc 实测 getoff_c(按值)",
          "  与 getoff_p(指针) 汇编一字不差：ldr x0,[x0,16]",
          "✗ define @f(ptr byval(%desc) %d) → 错位（LLVM 从参数栈区读）",
          "✗ define @f({ptr,ptr,i64,...} %d) → 错位（LLVM 自行拆传）",
          "结论：JIT 边界签名必须与调用方约定同一份 ABI"],
         ORANGE, 11.5, 10.2, 0.42, True)

    # 底部：账单
    b.append(text(50, 560, "GEMM 的 ABI 账单（来自签名转换表的字节账）", 12.5, INK, "start", True))
    bill = [("参数 %a", "56B 描述符", "调用方复制，x0 传副本地址"),
            ("参数 %b", "56B 描述符", "x1 传副本地址"),
            ("参数合计", "112B", "D114'56 字节按值传参'伏笔的兑现"),
            ("返回 %c", "56B 描述符", "大聚合返回：x8 隐式结果指针（sret）")]
    bx = 50
    for i, (what, size, how) in enumerate(bill):
        w = 222
        b.append(hand_rect(bx, 576, w, 86, BG, 0.4, INK, 1.4))
        b.append(text(bx + w / 2, 596, what, 11, INK, "middle", True))
        b.append(text(bx + w / 2, 614, size, 13, INK, "middle", True))
        b.append(text(bx + w / 2, 634, how, 8.8, MUTED, "middle"))
        bx += w + 4
        if i == 1:
            b.append(text(bx - 2, 614, "＋", 13, MUTED, "middle"))
    b.append(hand_line(55, 684, 965, 685, BORDER, 2))
    b.append(text(510, 708, "多结果函数：≥2 个结果在 MLIR 层打包成 !llvm.struct<(...)>（S9 例：struct<(desc,desc)>＝112B，align 8）",
                  10.5, MUTED, "middle"))
    b.append(text(510, 728, "真机验证：peek 用 ptr 签名读连续/转置布局全点 bitwise 对；mul2_out 演示 sret 式双出口",
                  10.5, MUTED, "middle"))
    save("02-mechanism.svg", b)


# ======================= 图 3：实例结果图 =======================

def fig3():
    W, H = 1020, 730
    b = frame(W, H, "真实运行结果：残账、两道闸、真机 ABI 证据与探针（全部本机冻结数字）")
    b.append(hand_line(300, 44, 720, 45, ORANGE, 3))

    # 面板①：partial 账本
    card(b, 45, 62, 300, 250, "① partial 账本：8/18，SUCCESS",
         ["今天转换 8：F1×1＋A1×6＋R1×1",
          "残账 10（各带排期）：",
          "  scf.for ×3 ＋ yield ×1 → C1（D117）",
          "  memref.load ×2 → M1（D116）",
          "  memref.store ×1 → M2（D116）",
          "  memref.alloc ×1 → M3（D116）",
          "  arith.mulf/addf ×2 → A3（D116）",
          "full 模式：同账本 → 整体 FAIL",
          "（D117 导出前的门，非今天的失败）",
          "胶水 8 条：desc→memref×2，",
          "i64→index×5，memref→desc×1"],
         BLUE, 11.5, 10.3, 0.42, True)

    # 面板②：两道闸
    card(b, 370, 62, 300, 250, "② 两道闸：D114 实验 B 的执行版",
         ["类型闸（TypeConverter，当场失败）：",
          "  tensor<4x6xf32> → 拒收（先 bufferize）",
          "  memref<?x?xf32> → 拒收（动态 shape）",
          "  bf16 → 拒收（未知类型）",
          "方言闸（ConversionTarget，op 级）：",
          "  mini.relu ×1 → 非法方言（无排期）",
          "  '必须在第一段 Lowering 处理'",
          "换形状对照（2×3×2）：计数不变",
          "8/18＋10；类型文本随形状变",
          "（A strides [3,1]）——转换按 op",
          "生效，与形状无关"],
         GREEN, 11.5, 10.3, 0.42, True)

    # 面板③：真机 ABI 证据
    card(b, 695, 62, 295, 250, "③ 真机证据链（LLVM 22＋gcc）",
         ["JIT peek（ptr 签名，bitwise 全对）：",
          "  连续 4×6：24/24 点",
          "  转置 4×3（strides (1,4)）：12/12 点",
          "  mul2_out：ret=23，out=46 双出口对",
          "gcc -O2 -S（C ABI ground truth）：",
          "  getoff_c ≡ getoff_p：ldr x0,[x0,16]",
          "  → >16B 聚合'间接传'，按值＝指针",
          "  make_desc 写 [x8] → sret 返回",
          "  sizeof(struct desc)＝退出码 56",
          "TargetData 对账：56B/align8/",
          "偏移 0,8,16,24,40；rank1/3＝40/72B"],
         ORANGE, 11.5, 10.3, 0.42, True)

    # 面板④：探针
    b.append(text(50, 348, "探针与误用对照：故意犯的错，真机咬得住", 12.5, INK, "start", True))
    card(b, 45, 364, 460, 190, "④ 描述符填错（ABI 版探针，确定性错值）",
         ["P1 strides 填反（[6,1] 写成 [1,6]）：20/24 点错，max|diff|=25",
          "  ——对角线 3 点碰巧读对：巧合不等于正确（i=j 时地址恰好相同）",
          "P2 offset 错填 8：24/24 点错，max|diff|=8",
          "  ——整体错位 8 个元素，全局读偏",
          "两例都真机可复现；对照 D114 P1（仿真层面 2 个 NaN＋120.13）：",
          "描述符错误在任何一层都会暴露——填表、翻译、调用一回事"],
         RED, 11.5, 10.3, 0.42, True)
    card(b, 530, 364, 460, 190, "⑤ ABI 形态误用（错位，值随环境变化）",
         ["byval 形态读到 281474053336576（一次运行的实测值，非确定）",
          "直接聚合形态读到 281474053336512（同上）",
          "正确形态（ptr）读到 42 —— 三种形态读同一个字段",
          "错位值是栈上残留内容，随调用环境变化；",
          "但'错'本身是确定的：签名形态＝ABI 合同，双方必须一致",
          "这也是 MLIR 在 C 边界提供 _mlir_ciface 包装的原因之一"],
         RED, 11.5, 10.3, 0.42, True)

    # 底部：验收带
    b.append(hand_rect(45, 578, 945, 130, BG, 0.5, INK, 1.6))
    b.append(text(510, 604, "今日验收对照：8/8 PASS（主运行）＋9/9 PASS（换形状对照）", 14, INK, "middle", True))
    checks = ["TP1 布局对账", "TP2 签名表", "TP3 两道闸", "TP4 partial/full", "TP5 胶水账",
              "TP6 真机 ABI", "TP7 gcc 证据链", "TP8 探针", "TP9 形状对照"]
    for i, c in enumerate(checks):
        col = i % 3
        row = i // 3
        b.append(text(190 + col * 320, 632 + row * 22, f"✓ {c}", 11, GREEN, "middle"))
    b.append(text(510, 696, "环境：Python 3.11.4 / numpy 1.26.4 / llvmlite 0.50.0（LLVM 22.1.0）/ gcc 9.4.0 / aarch64 Linux · 2026-11-13 冻结运行",
                  10, MUTED, "middle"))
    save("03-example.svg", b)


if __name__ == "__main__":
    print("生成第 115 天的 3 张手绘图（seed=115）：")
    fig1()
    fig2()
    fig3()
    print("完成。")
