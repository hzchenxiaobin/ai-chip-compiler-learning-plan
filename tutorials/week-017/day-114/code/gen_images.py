#!/usr/bin/env python3
"""生成第 114 天的 3 张手绘 sketch 风 SVG 技术图（Excalidraw-like）。

风格与 D110~D113 一致：白板涂鸦感——带抖动的贝塞尔手绘路径、
马克笔笔触、3～4 种柔和强调色（蓝/橙/绿/红）＋米白背景、简单几何
形状、手写感字体。所有数字来自 outputs/ 的真实冻结运行
（conversion-report.txt / conversion-report-s233.txt，
2026-11-13，Python 3.11.4 aarch64，numpy 1.26.4，
llvmlite 0.50.0 内嵌 LLVM 22.1.0）。固定随机种子，图可复现。
"""

from __future__ import annotations

import math
import os
import random
import xml.sax.saxutils as su

random.seed(114)

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


def arrow(x1, y1, x2, y2, stroke=INK, sw=1.8, dash=None):
    dd = f' stroke-dasharray="{dash}"' if dash else ""
    mx, my = (x1 + x2) / 2 + jit(2.0), (y1 + y2) / 2 + jit(2.0)
    ang = math.atan2(y2 - y1, x2 - x1)
    hx, hy = x2 - 9 * math.cos(ang), y2 - 9 * math.sin(ang)
    a1 = (hx + 5 * math.cos(ang + 2.5), hy + 5 * math.sin(ang + 2.5))
    a2 = (hx + 5 * math.cos(ang - 2.5), hy + 5 * math.sin(ang - 2.5))
    d = (f"M {x1 + jit():.1f},{y1 + jit():.1f} Q {mx:.1f},{my:.1f} "
         f"{x2:.1f},{y2:.1f} M {a1[0]:.1f},{a1[1]:.1f} L {x2:.1f},{y2:.1f} "
         f"L {a2[0]:.1f},{a2[1]:.1f}")
    return (f'<path d="{d}" stroke="{stroke}" stroke-width="{sw}" '
            f'stroke-linecap="round" fill="none"{dd}/>')


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
         opacity=0.42, anchor_left=False, mono_lines=None, tsize2=None):
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
    W, H = 1020, 720
    b = frame(W, H, "第 114 天定位：第 17 周的施工图日——读完目标语言之后、动工翻译之前")
    b.append(hand_line(320, 44, 700, 45, ORANGE, 3))

    # 上排：编译链路
    b.append(text(48, 68, "编译链路：mini 编译器已经走到哪一站？", 12.5, INK, "start", True))
    chain = [
        ("图 IR", "mini 方言", GREEN, "D12~D84 建成＋优化 ✓"),
        ("循环＋内存 IR", "scf / memref / arith", BLUE, "D85~D105 第一次 Lowering ✓"),
        ("最终 Lowering", "设计日（今天）", ORANGE, "D114 ↓ 画施工图"),
        ("LLVM 方言", "llvm.* 一族", GREEN, "D113 读过样本 ✓"),
        ("LLVM IR → 执行", "真机器码", GREEN, "D117 导出 / D118 执行"),
    ]
    x = 44
    for i, (t1, t2, col, t3) in enumerate(chain):
        w = 176
        card(b, x, 80, w, 74, t1, [t2, t3], col, 11.5, 9.6, 0.5)
        if i < len(chain) - 1:
            arrow(x + w + 2, 117, x + w + 22, 117, INK, 1.8)
        x += w + 24
    b.append(text(510, 180, "今天的输入：A(4×6)@B(6×3) 的循环 IR（loop_ir.mlir，18 个 op，横跨 func/memref/arith/scf 四个方言）",
                  11.5, MUTED, "middle"))

    # 中排：第 17 周排期
    b.append(text(48, 218, "第 17 周六天怎么分工？", 12.5, INK, "start", True))
    week = [
        ("D113 ✓", "读目标语言样本", "llvm.func@step\n9 个 llvm.* op", GREEN),
        ("D114 今天", "设计最终 Lowering", "类型表＋合法性清单\n两种驱动＋真机验证", ORANGE),
        ("D115", "转换函数与类型", "F1/R1/A1 落地", BG),
        ("D116", "转换简单算子", "M1/M2/M3 落地", BG),
        ("D117", "导出 LLVM IR", "C1 落地＋全管道", BG),
        ("D118", "JIT/AOT 执行", "真机跑起来", BG),
    ]
    x = 44
    for t1, t2, t3, col in week:
        w = 150
        lines = t3.split("\n")
        card(b, x, 230, w, 92, t1, [t2] + lines, col, 11, 9.4,
             0.72 if col is ORANGE else 0.42)
        x += w + 13.6
    b.append(text(510, 344, "D113 是“看”，D115~D118 是“做”——中间的今天决定“做的顺序和验收标准”",
                  11.5, MUTED, "middle"))

    # 下排左：D85 与 D114 的镜像
    b.append(text(48, 382, "和 D85 是镜像：两次 Lowering，同一套四角色，不同的清单内容", 12.5, INK, "start", True))
    card(b, 48, 394, 300, 138, "D85 第一次 Lowering（施工图）",
         ["源：mini.matmul（tensor 图）", "终态：允许 scf / memref / arith",
          "类型表：tensor → memref",
          "角色：Target / Converter / Pattern / 驱动器",
          "产出：任务清单＋测试计划＋循环 IR"],
         GREEN, 11, 9.4, 0.42, anchor_left=True)
    card(b, 672, 394, 300, 138, "D114 最终 Lowering（今天）",
         ["源：循环＋内存 IR（scf/memref）", "终态：只允许 llvm.*",
          "类型表：memref → 5 字段描述符",
          "角色：同一套四角色，再走一遍",
          "产出：合法性清单＋目标形态＋验证"],
         ORANGE, 11, 9.4, 0.42, anchor_left=True)
    b.append(hand_rect(366, 412, 288, 100, BG, 1.0, INK, 1.6))
    b.append(text(510, 434, "两次翻译都过同一座“海关”", 11.5, INK, "middle", True))
    b.append(text(510, 456, "ConversionTarget 管合法", 10.3, INK, "middle"))
    b.append(text(510, 473, "TypeConverter 管类型（兑换表＋拒收）", 10.3, INK, "middle"))
    b.append(text(510, 490, "Pattern 管逐 op 翻译", 10.3, INK, "middle"))
    b.append(text(510, 507, "驱动器管验收：残留即退回 / 记账", 10.3, INK, "middle"))
    arrow(348, 463, 364, 463, INK, 1.8)
    arrow(656, 463, 670, 463, INK, 1.8)

    # 下排右：今日产出（真实文件）
    b.append(text(48, 558, "今天的产出（全部真实运行、outputs/ 里可查）", 12.5, INK, "start", True))
    card(b, 48, 570, 294, 122, "产出 1：合法性清单（主产出）",
         ["legality-checklist.md（机器生成）",
          "10 条模式 F1/R1/A1~A3/C1/M1~M3",
          "每行：终态判定＋目标序列＋排期",
          "＋暂不支持清单 7 条＋类型表 6 行"],
         BLUE, 11, 9.4, 0.45, anchor_left=True)
    card(b, 364, 570, 294, 122, "产出 2：目标形态样板",
         ["llvm-dialect-target.mlir",
          "18 op → 69 op（10 个基本块）",
          "一条 load 展开 10 条目标 op",
          "描述符 7 次 insertvalue 填满"],
         GREEN, 11, 9.4, 0.45, anchor_left=True)
    card(b, 680, 570, 292, 122, "产出 3：真机验证",
         ["gemm.ll（真 LLVM IR）",
          "llvmlite 22.1.0：parse+verify+MCJIT",
          "执行结果与逐项参考 bitwise 一致",
          "解释器 211 步同样逐位一致"],
         ORANGE, 11, 9.4, 0.45, anchor_left=True)
    save("01-overview.svg", b)


# ======================= 图 2：翻译手册机制图 =======================

def fig2():
    W, H = 1060, 900
    b = frame(W, H, "最终 Lowering 的翻译手册：左边进海关、右边出 llvm.*，类型表管名词、驱动器管验收")
    b.append(hand_line(340, 44, 720, 45, ORANGE, 3))

    # 顶部：类型兑换表
    b.append(text(530, 70, "TypeConverter 类型兑换表（管“名词”）", 12.5, INK, "middle", True))
    card(b, 44, 82, 306, 96, "index → i64",
         ["位宽随目标指针宽度（64 位目标）",
          "LLVM 方言兼容类型清单里没有 index"],
         BLUE, 11, 9.4, 0.45, anchor_left=True)
    card(b, 366, 82, 306, 96, "f32 → f32 ／ i32 → i32",
         ["浮点与整型原样通过",
          "D113 的 step 函数用的就是它们"],
         GREEN, 11, 9.4, 0.45, anchor_left=True)
    card(b, 688, 82, 330, 96, "memref<...> → 描述符结构体",
         ["!llvm.struct<(ptr, ptr, i64,",
          "  array<2xi64>, array<2xi64>)>  56 B",
          "字段与顺序＝真实 MLIR MemRefDescriptor"],
         ORANGE, 11, 9.4, 0.45, anchor_left=True)

    # 拒收条
    b.append(hand_rect(44, 188, 974, 40, RED, 0.4, RED, 1.6, dash="7 5"))
    b.append(text(531, 213, "拒收清单：tensor<...>（必须先 bufferize）｜memref<?x?xf32>（动态 shape 暂不支持）——带着它们进海关的 op 一律残留＋原因入账",
                  11, INK, "middle", True))

    # 中部三栏：源 op → 模式 → 目标序列
    b.append(text(150, 258, "① 源方言（今天输入里出现）", 12, INK, "middle", True))
    b.append(text(530, 258, "② 模式（翻译手册）", 12, INK, "middle", True))
    b.append(text(886, 258, "③ 目标 op 序列（样板里实际出现）", 12, INK, "middle", True))

    rows = [
        ("func.func / func.return", "func",
         "F1 / R1（D115）", "llvm.func ＋ llvm.return（签名先过兑换表）"),
        ("arith.constant ×6", "arith",
         "A1（D115）", "llvm.mlir.constant（index 常量→i64）"),
        ("arith.mulf / addf ×2", "arith",
         "A3（D116）", "llvm.fmul / llvm.fadd"),
        ("scf.for ×3 ＋ scf.yield ×1", "scf",
         "C1（D117）", "llvm.br＋块参数＋llvm.icmp＋llvm.cond_br＋回边传值（导出后是 phi）"),
        ("memref.load ×2 / store ×1", "memref",
         "M1 / M2（D116）", "extractvalue×4＋mul×2＋add×2＋getelementptr＋load/store"),
        ("memref.alloc ×1", "memref",
         "M3（D116）", "llvm.call @malloc＋undef＋insertvalue×7"),
    ]
    y = 272
    for src, dialect, pat, dst in rows:
        fillc = BLUE if dialect == "func" else GREEN if dialect == "arith" \
            else ORANGE if dialect == "scf" else BLUE
        card(b, 44, y, 258, 60, src, [f"方言：{dialect}"], fillc, 10.3, 9.2, 0.4)
        card(b, 372, y, 176, 60, pat, [], BG, 10.3, 9.2, 0.55)
        card(b, 640, y, 378, 60, "", [dst], BG, 10.3, 9.4, 0.3, anchor_left=True)
        arrow(304, y + 30, 370, y + 30, INK, 1.7)
        arrow(550, y + 30, 638, y + 30, INK, 1.7)
        y += 66

    # 残留行（红色）
    card(b, 44, y, 258, 60, "mini.* ／ vector.* ／ tensor 残留", ["对照输入 B 才会出现"], RED, 10.3, 9.2, 0.42)
    b.append(hand_rect(372, y, 176, 60, RED, 0.4, RED, 1.6, dash="7 5"))
    b.append(text(460, y + 26, "无模式", 10.3, INK, "middle", True))
    b.append(text(460, y + 44, "终态非法", 9.2, INK, "middle"))
    card(b, 640, y, 378, 60, "", ["残留报告：'非法方言 mini.*'或'类型转换失败：tensor'"], RED, 10.3, 9.4, 0.35, anchor_left=True)
    arrow(304, y + 30, 370, y + 30, INK, 1.7, dash="6 5")
    arrow(550, y + 30, 638, y + 30, INK, 1.7, dash="6 5")

    # 底部左：描述符解剖
    b.append(text(190, 766, "描述符解剖（P1 探针盯防的位置）", 12, INK, "middle", True))
    b.append(hand_rect(44, 776, 560, 74, BG, 1.0, INK, 1.6))
    fields = ["[0] allocated ptr\n(malloc 返回)", "[1] aligned ptr\n(真正起点)", "[2] offset\n(i64)",
              "[3] sizes\n[2 × i64]", "[4] strides\n[2 × i64]"]
    fx = 56
    for f in fields:
        t, sub = f.split("\n")
        b.append(hand_rect(fx, 784, 102, 56, GREEN, 0.45, INK, 1.4))
        b.append(text(fx + 51, 802, t, 9.6, INK, "middle", True))
        b.append(text(fx + 51, 820, sub, 8.6, MUTED, "middle"))
        fx += 110
    b.append(text(324, 866, "64 位目标上 2×8＋8＋16＋16 = 56 字节；load 的地址 = aligned + (offset + Σ idx_d × stride_d) × 4B",
                  9.6, MUTED, "middle"))

    # 底部右：两种驱动
    b.append(text(836, 766, "④ 驱动器：同一份清单、两种执法", 12, INK, "middle", True))
    card(b, 618, 776, 210, 74, "full（全量）",
         ["残留 1 个 → 整体 FAIL", "D117 导出前的最后一道门"],
         GREEN, 10.3, 9.0, 0.42)
    card(b, 844, 776, 174, 74, "partial（部分）",
         ["残留记账 → SUCCESS", "D115~D116 渐进施工的账本"],
         ORANGE, 10.3, 9.0, 0.42)
    save("02-mechanism.svg", b)


# ======================= 图 3：实验结果对照图 =======================

def fig3():
    W, H = 1060, 760
    b = frame(W, H, "第 114 天真实运行结果：7/7 项 PASS——膨胀 3.8 倍，三种设计错误全部被清单咬住")
    b.append(hand_line(330, 44, 730, 45, ORANGE, 3))
    b.append(text(530, 66, "环境：Python 3.11.4（aarch64）· numpy 1.26.4 · llvmlite 0.50.0（LLVM 22.1.0）· 2026-11-13，全部出自一次冻结运行（outputs/）",
                  10.3, MUTED, "middle"))

    # 面板 a：全量转换 + 真机验证
    card(b, 44, 88, 310, 240, "① 全量转换：18 op 全部过海关",
         ["源 IR：18 op（4 个方言）",
          "目标形态：69 op、10 个基本块",
          "膨胀 3.8 倍（信息显式化的代价）",
          "full 驱动：18/18 转换，残留 0",
          "每条 load 展开 10 条目标 op",
          "描述符 7 次 insertvalue 填满"],
         GREEN, 11.5, 10.2, 0.4, anchor_left=True)
    b.append(hand_rect(360, 88, 310, 240, BG, 1.0, INK, 1.6))
    b.append(text(515, 108, "② 两条执行路径都逐位一致", 11.5, INK, "middle", True))
    b.append(text(515, 132, "解释器（numpy 逐 op 仿真）", 10.2, INK, "middle"))
    b.append(text(515, 150, "执行 211 步 → 与逐项参考 bitwise 相等：True", 10, INK, "middle"))
    b.append(text(515, 172, "真机（llvmlite MCJIT）", 10.2, INK, "middle"))
    b.append(text(515, 190, "LLVM IR parse + verify 通过", 10, INK, "middle"))
    b.append(text(515, 208, "编译 → ctypes 调用 malloc/访存", 10, INK, "middle"))
    b.append(text(515, 226, "C_jit 与逐项参考 bitwise 相等：True", 10, INK, "middle"))
    b.append(text(515, 250, "设计＝可执行的，不是纸面结论", 10.2, ORANGE, "middle", True))
    b.append(text(515, 272, "（对照 numpy f32 matmul 差 3.05e-05：", 9.3, MUTED, "middle"))
    b.append(text(515, 288, "  BLAS 累加序不同，只作参考）", 9.3, MUTED, "middle"))
    card(b, 676, 88, 342, 240, "③ 对照实验 C：换形状 2×3×2",
         ["全部 7 项检查照样 PASS",
          "解释器 51 步，bitwise 相等",
          "真机 JIT bitwise 相等",
          "描述符 strides [6,1]→[3,1]，",
          "  malloc 48 B→16 B 随 shape 重算",
          "探针照样被咬住（见下）"],
         BLUE, 11.5, 10.2, 0.4, anchor_left=True)

    # 面板 b：两种驱动对照（EXP A/B）
    b.append(text(230, 358, "④ partial vs full：同一份残留清单，语义相反（对照实验 A）", 12, INK, "middle", True))
    card(b, 44, 370, 484, 176, "扣掉 C1（scf 一族）后重跑驱动器",
         ["partial：14/18 转换、残留 4（SUCCESS）",
          "  残留 = 3×scf.for ＋ 1×scf.yield",
          "  每条原因：'模式未注册（排期见清单）'",
          "full：同配置 FAIL，列出同样 4 条",
          "  循环体内的 load/store 照样被转换——",
          "  partial 是逐 op 执法，不是逐函数放弃"],
         ORANGE, 11, 9.8, 0.42, anchor_left=True)
    card(b, 534, 370, 484, 176, "对照实验 B：把 tensor 图直接喂最终 Lowering",
         ["输入 residual.mlir：3 op（func＋mini.matmul＋return）",
          "partial：0/3 转换，残留 3（SUCCESS，入账）",
          "  func ＋ return → 类型转换失败：tensor",
          "  mini.matmul → 非法方言且无模式",
          "full：FAIL——两道闸把管道顺序错误",
          "  拦在门外：先 bufferize，再最终 Lowering"],
         RED, 11, 9.8, 0.42, anchor_left=True)

    # 面板 c：探针
    b.append(text(230, 578, "⑤ 三个故意埋的设计错误：一个都跑不掉", 12, INK, "middle", True))
    card(b, 44, 590, 310, 122, "P1 描述符 strides 填反",
         ["（镜像 D85 的 P1'strides 算反'）",
          "有限部分 max|diff| = 120.0132",
          "2 个元素永远没写到（NaN 暴露",
          "malloc 的未初始化内存）",
          "→ 被 TP5 逐位比对咬住"],
         ORANGE, 10.8, 9.6, 0.42, anchor_left=True)
    card(b, 376, 590, 310, 122, "P3 iter_args 接线断开",
         ["（镜像 D85 的 P3'忘初始化'）",
          "body 里用的还是初值 %zero",
          "每个 (i,j) 只剩最后一项乘积",
          "max|diff| = 191.1975",
          "→ 被 TP5 咬住"],
         ORANGE, 10.8, 9.6, 0.42, anchor_left=True)
    card(b, 708, 590, 310, 122, "P2 index 忘了兑换",
         ["（镜像 D85 的 P2'忘类型转换'）",
          "目标形态出现 index 类型 23 处",
          "LLVM 方言没有 index——",
          "类型检查 fail-closed 拦截",
          "→ 被 TP4 咬住（静态检查）"],
         ORANGE, 10.8, 9.6, 0.42, anchor_left=True)
    b.append(text(530, 736, "结论：清单不只是文档——它是驱动器的执法依据、解释器的验收表、真机验证的合同。D115~D118 每天从这张清单领任务。",
                  11, GREEN, "middle", True))
    save("03-example.svg", b)


if __name__ == "__main__":
    print("生成第 114 天的 3 张手绘图：")
    fig1()
    fig2()
    fig3()
