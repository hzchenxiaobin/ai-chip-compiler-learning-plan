#!/usr/bin/env python3
"""生成第 116 天的 3 张手绘 sketch 风 SVG 技术图（Excalidraw-like）。

风格与 D110~D115 一致：白板涂鸦感——带抖动的贝塞尔手绘路径、马克笔笔触、
3～4 种柔和强调色（蓝/橙/绿/红）＋米白背景、简单几何形状、手写感字体。
所有数字来自 outputs/ 的真实冻结运行（op-report.txt / op-report-s23.txt，
2026-11-13，Python 3.11.4 aarch64，numpy 1.26.4，llvmlite 0.50.0 内嵌
LLVM 22.1.0）。固定随机种子 116，图可复现。
"""

from __future__ import annotations

import math
import os
import random
import xml.sax.saxutils as su

random.seed(116)

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
    W, H = 1020, 740
    b = frame(W, H, "第 116 天定位：最终 Lowering 的算子层施工——消费 D115 工单，用最简单的算子点亮整条链路")
    b.append(hand_line(300, 44, 720, 45, ORANGE, 3))

    # 上排：编译链路
    b.append(text(48, 68, "编译链路：今天走到哪一站？", 12.5, INK, "start", True))
    chain = [
        (60, 150, "图 IR", "mini 方言", BG, "已完成"),
        (165, 275, "循环＋内存 IR", "scf·memref", BG, "D85~D105"),
        (290, 450, "函数与类型", "F1/R1/A1", BG, "D115 ✓"),
        (465, 625, "今天：算子与内存", "M1~M3/A2~A4", GREEN, "D116 ★"),
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
    b.append(text(510, y0 + 82, "今天不碰 C1（循环）——三个可执行主角全部没有 scf.for；GEMM 只做账本回归",
                  10.5, MUTED, "middle"))

    # 中排：模式清单施工进度
    b.append(text(48, 208, "模式清单施工进度：D114 写下 10 行，今天再点亮 5 行并新增 A4", 12.5, INK, "start", True))
    rows = [("F1 函数", "D115", True), ("R1 返回", "D115", True), ("A1 常量", "D115", True),
            ("M1 load", "D116 ★", False), ("M2 store", "D116 ★", False),
            ("M3 alloc", "D116 ★", False), ("A2 整数乘加", "D116 ★", False),
            ("A3 浮点乘加", "D116 ★", False), ("A4 cmpf/select", "D116 新增", False),
            ("C1 循环", "D117", None)]
    bw = 90
    for i, (name, plan, done) in enumerate(rows):
        col = i % 5
        row = i // 5
        x1 = 60 + col * (bw + 14)
        y1 = 224 + row * 62
        fill = GREEN if done else (ORANGE if "★" in plan or "新增" in plan else BG)
        b.append(hand_rect(x1, y1, bw, 50, fill,
                           0.6 if ("★" in plan or "新增" in plan) else 0.4,
                           INK, 1.8 if ("★" in plan or "新增" in plan) else 1.3))
        b.append(text(x1 + bw / 2, y1 + 20, name, 10.5, INK, "middle", True))
        tag = plan if done is None else ("✓ 已完成" if done else plan)
        b.append(text(x1 + bw / 2, y1 + 38, tag, 9.5,
                      MUTED if done else INK, "middle"))
    b.append(text(510, 352, "A4 是 Relu 进管道时暴露的缺口——清单第 10 行：新算子先进清单、再写模式（D14/D42 的纪律）；C1 是唯一剩下的欠账",
                  10, MUTED, "middle"))

    # 下排：今天策略链条
    b.append(text(48, 372, "今天的策略链条（为什么简单算子先行）", 12.5, INK, "start", True))
    steps = [
        (55, 210, "① 选无循环输入", "2×2 展开形态：C1 出局，", "残账才能清零", BLUE),
        (290, 210, "② 六类模式消费新类型", "M1/M2/M3 站在 D115 的", "描述符上，胶水自然消失", GREEN),
        (525, 210, "③ 三层参考验证", "契约/数值/布局——", "P1 告诉你缺一层就放 bug", ORANGE),
        (760, 215, "④ 边界包装", "_mlir_ciface：内部按值", "边界指针，两份合同", RED),
    ]
    for x, w, title, l1, l2, fill in steps:
        b.append(hand_rect(x, 388, w, 84, fill, 0.42, INK, 1.6))
        b.append(text(x + w / 2, 408, title, 11.5, INK, "middle", True))
        b.append(text(x + w / 2, 428, l1, 9.5, INK, "middle"))
        b.append(text(x + w / 2, 444, l2, 9.5, INK, "middle"))
    for x1, x2 in [(265, 290), (500, 525), (735, 760)]:
        b.append(arrow(x1 + 2, 430, x2 - 2, 430, INK, 1.8))

    # 底部：今日真实数字预告
    b.append(text(48, 510, "今天结束时的真实证据（全部来自本机冻结运行）", 12.5, INK, "start", True))
    facts = [
        (160, "21/21", "@add full 首次 SUCCESS（0 残账）"),
        (390, "14/18", "GEMM 只欠 C1×4（D117 的船票）"),
        (620, "0 胶水", "D115 的 8 条：3 条消亡＋5 条留守"),
        (852, "x0..x6", "56B 聚合返回拆 7 个寄存器（真机汇编）"),
    ]
    for x, big, small in facts:
        b.append(text(x, 548, big, 20, INK, "middle", True))
        b.append(text(x, 570, small, 9.5, MUTED, "middle"))
    b.append(hand_line(55, 592, 965, 593, BORDER, 2))
    b.append(text(510, 618, "策略回报：@add/@relu/@step 三个 full SUCCESS ＋ 三层 4/4 bitwise——路径点亮，D117 让 GEMM 走同一条线",
                  10.5, MUTED, "middle"))
    b.append(text(510, 640, "诚实声明：本机无 mlir-opt，驱动器/模式注册表为教学仿真；但 LLVM IR 由真 LLVM parse+verify+MCJIT 执行，汇编证据真实输出",
                  10.5, MUTED, "middle"))
    save("01-overview.svg", b)


# ======================= 图 2：机制图 =======================

def fig2():
    W, H = 1020, 800
    b = frame(W, H, "机制：一条 load 的 10 步展开、M3 的 7 次填表、三层验证与两份合同")
    b.append(hand_line(330, 44, 700, 45, ORANGE, 3))

    # 最上层：M1 解剖
    b.append(text(50, 70, "M1 解剖：memref.load %a[%c0, %c1] 怎么变成 10 条目标 op", 12.5, INK, "start", True))
    b.append(hand_rect(55, 82, 265, 56, BLUE, 0.5, INK, 1.6))
    b.append(text(187, 104, "源：memref.load", 11.5, INK, "middle", True))
    b.append(text(187, 124, "%a[%c0, %c1] : memref<2x2xf32>", 9.3, MUTED, "middle", mono=True))
    ops10 = [("extractvalue×4", "[1]aligned [2]off [4,0]s0 [4,1]s1"),
             ("mul×2＋add×2", "元素偏移＝off＋i·s0＋j·s1"),
             ("getelementptr", "元素偏移 → 字节地址（f32×4B）"),
             ("llvm.load", "读出 f32 → %a00")]
    ox = 345
    for i, (name, note) in enumerate(ops10):
        x1 = ox + i * 118
        b.append(hand_rect(x1, 82, 106, 56, GREEN if i < 3 else ORANGE, 0.45, INK, 1.6))
        b.append(text(x1 + 53, 102, name, 10.5, INK, "middle", True))
        b.append(text(x1 + 53, 122, note, 8.2, MUTED, "middle"))
        if i < 3:
            b.append(arrow(x1 + 106, 110, x1 + 118, 110, INK, 1.6))
    b.append(arrow(320, 110, 345, 110, INK, 1.8, label="M1"))
    b.append(text(50, 156, "乘加留在元素单位：getelementptr 天生按元素步进——M2 同一条公式，结尾换 llvm.store；A2/A3/A4 只是词汇映射（addi→add i64、addf→fadd、cmpf→fcmp＋select）",
                  9.8, MUTED, "start"))

    # 描述符字段条
    b.append(text(50, 180, "描述符（D115 的 56B/align8/偏移 0-8-16-24-40）今天原样使用：", 10.5, INK, "start", True))
    fields = [("allocated", 0), ("aligned", 8), ("offset", 16), ("sizes[2]", 24), ("strides[2]", 40)]
    x = 430
    for i, (name, off) in enumerate(fields):
        w = 72 if i < 3 else 96
        fill = [BLUE, BLUE, GREEN, ORANGE, ORANGE][i]
        b.append(hand_rect(x, 190, w, 36, fill, 0.5, INK, 1.5))
        b.append(text(x + w / 2, 206, name, 9.5, INK, "middle", True))
        b.append(text(x + w / 2, 220, f"@{off}", 8.5, MUTED, "middle"))
        x += w
    b.append(text(50, 198, "M1 只取 [1][2][4]；", 9.8, INK, "start"))
    b.append(text(50, 212, "M3 负责把 7 个字段全部填进去", 9.8, INK, "start"))

    # 中层左：M3 填表
    card(b, 55, 246, 430, 170, "M3 填表：输出描述符是怎么造出来的（共 15 条 op）",
         ["%b_c = llvm.mlir.constant(16 : i64)    ← 2×2×4B",
          "%mem_c = llvm.call @malloc(%b_c) : (i64) -> !llvm.ptr",
          "%u_c = llvm.mlir.undef : !llvm.struct<(...)>",
          "7 次 insertvalue 依次填：",
          "  [0] allocated ← %mem_c    [1] aligned ← %mem_c",
          "  [2] offset ← 0    [3,0] size0←2  [3,1] size1←2",
          "  [4,0] stride0←2   [4,1] stride1←1   → %c 就是描述符值",
          "P1 探针埋在 [4,0]/[4,1] 的填充顺序——填反后写读",
          "共用同一个错坐标系，数值层照样全对（见左下）"],
         GREEN, 11.5, 10.2, 0.42, True)

    # 中层右：词汇映射 + A4
    card(b, 510, 246, 465, 170, "词汇映射三行＋清单第 10 行的来历",
         ["A2  arith.addi/muli : index → add/mul i64（index 位宽＝指针宽度）",
          "A3  arith.addf/mulf : f32  → llvm.addf/mulf（IR 指令名是 fadd/fmul！）",
          "A4  arith.cmpf ogt → llvm.fcmp \"ogt\"（结果 i1）",
          "    arith.select → llvm.select : i1, f32",
          "A4 的来历：D114 写清单时输入里没有 cmpf/select；",
          "Relu（cmpf＋select）一进管道缺口就暴露——先补清单、",
          "再写模式。真实 MLIR 里是两个独立 ConversionPattern",
          "（CmpFOp / SelectOp），同一天落进同一行——分组只是",
          "清单的记法，模式仍按 op 各自注册"],
         ORANGE, 11.5, 10.2, 0.42, True)

    # 下层左：三层验证
    b.append(text(50, 448, "三层参考验证＋P1 的判读：谁咬住、谁放行", 12.5, INK, "start", True))
    layers = [
        ("契约层", "查描述符字段", "allocated≠0·aligned==allocated·offset 0·sizes [2,2]·strides [2,1]", "P1：✓ 咬住（strides=[1,2] 一眼定罪）", GREEN),
        ("数值层", "按描述符读回", "out[i,j]=mem[off+i·s0+j·s1]，与 np.where 参考 bitwise", "P1：✗ 放行（错误坐标系自洽，4/4 全对！）", RED),
        ("布局层", "按裸内存行主序", "frombuffer(allocated) 与参考 flatten() bitwise", "P1：✓ 咬住（只有 2/4 点对，2 点错位）", GREEN),
    ]
    for i, (name, what, how, p1, fill) in enumerate(layers):
        y1 = 462 + i * 58
        b.append(hand_rect(55, y1, 430, 50, fill, 0.4, INK, 1.5))
        b.append(text(70, y1 + 19, name, 11, INK, "start", True))
        b.append(text(122, y1 + 19, what, 9.5, INK, "start"))
        b.append(text(70, y1 + 38, how, 8.6, MUTED, "start"))
        b.append(text(255, y1 + 19, p1, 8.8, INK if fill == GREEN else RED, "start", True))
    b.append(text(55, 640, "教训：写读共用同一个描述符——填错它，数值层永远自洽；缺布局层＝缺唯一的逃逸出口检查",
                  9.8, MUTED, "start"))

    # 下层右：两份合同
    card(b, 510, 462, 465, 178, "边界包装：_mlir_ciface 存在的原因（两份合同）",
         ["内部合同（LLVM↔LLVM）：call %desc @add(%desc %a, %desc %b)",
          "  实测汇编（aarch64，noinline 保边界）：bl add 前用 3 条",
          "  stp/str 把 2×56B 入参复制上栈（14 个 8 字节 ＞ 8 个寄存器）；",
          "  调用后 4 条 stp x0,x1,[x19] … str x6,[x19,#48] 把 56B",
          "  返回值从 x0..x6 写回 outp——拆寄存器，不是 gcc 的 x8",
          "边界合同（JIT↔ctypes/libffi）：define _mlir_ciface_add(ptr,ptr,ptr)",
          "  三个指针＋store 回写——C 边界只信指针和标量",
          "D115 补完：gcc 实测 56B 聚合返回走 x8（sret）；byval/直接",
          "聚合配 ctypes 全部读错地方——边界必须降到指针合同"],
         RED, 11.5, 10.2, 0.42, True)

    b.append(hand_line(55, 662, 965, 663, BORDER, 2))
    b.append(text(510, 688, "链条闭合：源 IR →（六类模式）→ LLVM 方言 →（R2 内联常量）→ .ll →（包装两份合同）→ MCJIT → ctypes → numpy bitwise",
                  10.5, MUTED, "middle"))
    b.append(text(510, 710, "@add：21 op → 142 op（膨胀 6.8×）→ .ll 133 条指令（8 条常量内联消失）——膨胀在模式层，收敛在导出层",
                  10.5, MUTED, "middle"))
    save("02-mechanism.svg", b)


# ======================= 图 3：实例结果图 =======================

def fig3():
    W, H = 1020, 760
    b = frame(W, H, "真实运行结果：账本清零、三层 4/4、两份合同与三个探针（全部本机冻结数字）")
    b.append(hand_line(300, 44, 720, 45, ORANGE, 3))

    # 面板①：账本对比
    card(b, 45, 62, 300, 250, "① 账本：full 首次放行",
         ["@add   21/21  残账 0  full SUCCESS",
          "@relu  22/22  残账 0  full SUCCESS",
          "@step   5/5   残账 0  full SUCCESS",
          "@gemm 14/18  残账 C1×4 → D117",
          "  full FAIL＝导出前的门（非今天的失败）",
          "D114 实验 A 的预测（扣 C1→14/18）",
          "今天从'模拟'变成'实测'",
          "D115 的 8 条胶水去向：",
          "  desc→memref ×2、memref→desc ×1",
          "  → 死于 M1/M2/M3 直接消费新类型",
          "  i64→index ×5 → 留给 C1（D117 清零）",
          "膨胀：@add 21→142 op；.ll 133 条指令"],
         BLUE, 11.5, 10.2, 0.42, True)

    # 面板②：@add 三层验证
    card(b, 370, 62, 300, 250, "② @add 三层验证（第一个端到端算子）",
         ["契约层：allocated≠0 · aligned==allocated",
          "  offset 0 · sizes [2,2] · strides [2,1]  OK",
          "数值层（描述符读回）：4/4 bitwise",
          "布局层（裸内存行主序）：4/4 bitwise",
          "手算对照（可自己按计算器）：",
          "  1.5+10.25 = 11.75",
          "  -2.5+(-0.5) = -3.0",
          "  0.0+3.0 = 3.0",
          "  -0.0+7.75 = 7.75",
          "同一个 JIT 引擎换转置视图输入",
          "（元素 strides (1,2)）：仍 4/4——",
          "M1 地址公式对任意合法 strides 成立"],
         GREEN, 11.5, 10.2, 0.42, True)

    # 面板③：真机执行全家福
    card(b, 695, 62, 295, 250, "③ 真机执行全家福",
         ["@relu 主输入 [[1.5,-2.5],[0,-0]]：",
          "  → [[1.5,0],[0,0]]（-0.0→+0.0，符号位被 select 规整）",
          "@relu 边界输入 [[inf,-inf],[nan,3.25]]：",
          "  → [[inf,0],[0,3.25]]（NaN→0：cmpf ogt 为 false）",
          "@step (i,k)→(i+k)×2 五组全对（含 2⁴⁰ 的大数）：",
          "  0 / 10 / 4 / -4 / 4398046511104",
          "标量签名 (index,index)→(i64,i64)，无需包装",
          "环境：aarch64 · Python 3.11.4 · numpy 1.26.4",
          "  llvmlite 0.50.0（LLVM 22.1.0）",
          "全部结果与参考 bitwise 一致（tobytes 逐字节相等）"],
         ORANGE, 11.5, 10.2, 0.42, True)

    # 面板④：汇编证据
    b.append(text(50, 344, "汇编证据与探针判读：两层检查各抓各的", 12.5, INK, "start", True))
    card(b, 45, 360, 460, 200, "④ 边界包装的真实汇编（ciface-disasm.s，aarch64）",
         ["_mlir_ciface_add 共 27 条指令（noinline 保留调用边界）：",
          "  bl add 之前：3 条 stp/str 把按值入参复制上栈",
          "    ——2×56B＝14 个 8 字节，8 个可用寄存器装不下",
          "  bl add 之后：4 条写回 outp",
          "    stp x0, x1, [x19] … str x6, [x19, #48]",
          "    ——56B 聚合返回拆在 x0..x6（LLVM 内部合同）",
          "对照 D115 gcc 证据：C 合同的 56B 返回走 x8（sret）",
          "同是'56 字节按值'，两份合同机器形态不同——",
          "跨边界时哪份都不算数，必须降到指针（三 ptr 签名）"],
         GREEN, 11.5, 10.2, 0.42, True)

    card(b, 530, 360, 460, 200, "⑤ 探针三连：故意埋错，看哪一层咬得住",
         ["P1 M3 strides 填反：契约层✓（strides=[1,2]）",
          "   数值层✗ 放行——2×2 上反序是缓冲区双射，",
          "   写读共用错坐标系，4/4 照样全对（最狡猾的一课）",
          "   布局层✓ 只有 2/4 点对——缺这层 bug 就逃了",
          "   2×3 对照时干脆跳过：非方形反序 store 越界写坏堆",
          "P2 包装漏回写：契约层✓（allocated 为空）——",
          "   D115 的 sret 责任在包装里兑现",
          "P3 参考写成 np.maximum：NaN 点不一致——",
          "   where 版 4/4、maximum 版 3/4，参考也必须被验证语义"],
         RED, 11.5, 10.2, 0.42, True)

    # 底部：验收带
    b.append(hand_rect(45, 586, 945, 145, BG, 0.5, INK, 1.6))
    b.append(text(510, 612, "今日验收对照：主运行 9/9 PASS ＋ 形状对照（--shape 2 3）10/10 PASS", 14, INK, "middle", True))
    checks = ["TP1 账本四联", "TP2 目标图静态检查", "TP3 导出 verify", "TP4 真机 @add",
              "TP5 真机 @relu", "TP6 真机 @step", "TP7 转置视图", "TP8 探针三连",
              "DISASM 汇编证据", "TP9 形状对照（s23）"]
    for i, c in enumerate(checks):
        col = i % 2
        row = i // 2
        b.append(text(285 + col * 460, 638 + row * 21, f"✓ {c}", 11, GREEN, "middle"))
    b.append(text(510, 724, "环境：Python 3.11.4 / numpy 1.26.4 / llvmlite 0.50.0（LLVM 22.1.0）/ aarch64 Linux · 2026-11-13 冻结运行",
                  10, MUTED, "middle"))
    save("03-example.svg", b)


if __name__ == "__main__":
    print("生成第 116 天的 3 张手绘图（seed=116）：")
    fig1()
    fig2()
    fig3()
    print("完成。")
