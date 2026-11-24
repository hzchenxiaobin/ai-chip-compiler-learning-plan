#!/usr/bin/env python3
"""生成第 112 天的 3 张手绘 sketch 风 SVG 技术图（Excalidraw-like）。

风格约定与 D110/D111 一致：白板涂鸦感——带抖动的贝塞尔手绘路径、
马克笔笔触、3～4 种柔和强调色（橙/蓝/绿/红）＋米白背景、简单几何
形状、手写感字体。所有数字来自 2026-11-13 13:52~13:54 的最终冻结运行
（code/outputs/ 下的 a-narrow / b-resolution / c-regime / d-wide 四份报告）。
固定随机种子，图可复现。
"""

from __future__ import annotations

import math
import os
import random

random.seed(112)

BG = "#FDFBF6"
BORDER = "#E7DFCE"
INK = "#3B3B3B"
MUTED = "#6b6257"
ORANGE = "#E8A87C"
BLUE = "#A9C4D4"
GREEN = "#9CBF8E"
RED = "#C97B7B"
GRAYC = "#EDE7DA"
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


def dot(x, y, r=5.5, fill=ORANGE, stroke=INK, sw=1.3):
    return (f'<circle cx="{x + jit(0.8):.1f}" cy="{y + jit(0.8):.1f}" r="{r}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')


def text(x, y, s, size=13, fill=INK, anchor="middle", bold=False, rotate=None):
    import xml.sax.saxutils as su
    s = su.escape(s)
    wt = ' font-weight="bold"' if bold else ""
    tr = f' transform="rotate({rotate} {x} {y})"' if rotate is not None else ""
    return (f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" '
            f'text-anchor="{anchor}"{wt}{tr}>{s}</text>')


def frame(w, h, title):
    body = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
            f'font-family="{FONT}">',
            hand_rect(4, 4, w - 8, h - 8, BG, 1.0, BORDER, 2),
            text(w / 2, 34, title, 18, INK, "middle", True)]
    return body


def save(name, body):
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "..", "images", name)
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(body) + "\n</svg>\n")
    print(f"  已生成 images/{name}")


def card(b, x, y, w, h, title, lines, fill, tsize=11.5, lsize=10, opacity=0.42,
         tcolor=INK, anchor_left=False):
    b.append(hand_rect(x, y, w, h, fill, opacity, INK, 1.6))
    ax = x + 12 if anchor_left else x + w / 2
    aanchor = "start" if anchor_left else "middle"
    if title:
        b.append(text(ax, y + 19, title, tsize, tcolor, aanchor, True))
    for i, ln in enumerate(lines):
        b.append(text(ax, y + 38 + i * 16.5, ln, lsize, INK, aanchor))


# ======================= 图 1：全局定位图 =======================

def fig1():
    W, H = 1000, 660
    b = frame(W, H, "第 112 天定位：第四阶段收官复盘——把四周装进『两条信息链』")
    b.append(hand_line(300, 44, 700, 45, ORANGE, 3))

    # ---- 上排：第四阶段四周 ----
    b.append(text(48, 70, "第四阶段的链路（D85~D112，每站都有各自验收）", 12.5, INK,
                  "start", True))
    weeks = [
        ("第 13 周｜Lowering", BLUE,
         ["mini.matmul → 三重循环", "输出初始化 / 尾部 / 边界", "D90：8 组 Shape 对照"]),
        ("第 14 周｜Tiling", GREEN,
         ["循环顺序家族（j/k/i 内层）", "Tile 外壳 + 点循环 + min 钳制", "Unroll / 多配置实验"]),
        ("第 15 周｜内存", ORANGE,
         ["生命周期 → 复用（峰值 −30%）", "片上空间 256 KiB fail-closed", "DMA 依赖 / 双缓冲"]),
        ("第 16 周｜自动调优", RED,
         ["25.77B → 12,970 候选", "3+7 / 3+21 测量纪律", "Cost Model ρ≈0.97 · 引导 20.0 s"]),
    ]
    x0, y0, cw, ch, gap = 48, 82, 210, 118, 22
    for i, (title, col, lines) in enumerate(weeks):
        x = x0 + i * (cw + gap)
        card(b, x, y0, cw, ch, title, lines, col, 11, 9.6, 0.4)
        if i < 3:
            arrow(x + cw + 2, y0 + ch / 2, x + cw + gap - 2, y0 + ch / 2, INK, 2)

    # ---- 中间：今天 ----
    cx, cy, cw2, ch2 = 250, 258, 500, 120
    b.append(hand_rect(cx, cy, cw2, ch2, BG, 1.0, ORANGE, 2.6))
    b.append(text(cx + cw2 / 2, cy + 24, "D112 · 第 16 周复盘（今天）", 13.5, INK, "middle", True))
    b.append(text(cx + cw2 / 2, cy + 46,
                  "学习：『生成正确代码』和『生成高性能代码』需要的信息不一样", 10.8, INK))
    b.append(text(cx + cw2 / 2, cy + 65,
                  "实践：准备性能反例——Cost Model 为什么可能选错（a/b/c/d 四组实验）", 10.8, INK))
    b.append(text(cx + cw2 / 2, cy + 84,
                  "产出：第四阶段总结 + 性能调优标准回答 + 本周复盘", 10.8, INK))
    b.append(text(cx + cw2 / 2, cy + 106,
                  "结账对象：D111 验收 ③ 的 agree=false 3/3（冠军 ikj vs D108 kij）", 10.2, MUTED))
    arrow(cx + cw2 / 2, y0 + ch + 4, cx + cw2 / 2, cy - 4, INK, 2)
    b.append(text(cx + cw2 / 2 + 8, y0 + ch + 22, "四周攒下的零件，今天拆开看『信息』", 9.5, MUTED, "start"))

    # ---- 下排：两条信息链 ----
    b.append(text(48, 424, "复盘落点：同样的编译器，两种信息、两种交付物", 12.5, INK, "start", True))
    card(b, 48, 438, 440, 180,
         "正确性信息（语义链）：编译期可判定，与环境无关",
         ["输入：Shape / 类型 / 循环边界 / 累加序 / 尾部 / use-def",
          "判定：Verifier + 正确性门（bitwise ==，先于计时）",
          "证据：今天 S1 24/24、W1 36/36 全过门——",
          "　　哪个进程、哪个时间窗测，答案都逐位相同",
          "类比：数学证明——谁看都一样（但证明不保证快）"],
         GREEN, 11, 9.8, 0.34, anchor_left=True)
    card(b, 512, 438, 440, 180,
         "性能信息（环境链）：必须测量，绑定 (进程, regime, 窗口)",
         ["输入：结构差（语句行数）× 单价（校准 = 测量）",
          "纪律：3+7 / 3+21、中位数、MAD、Roofline 参照",
          "证据：j0 窄 55.7 → 宽 59.9 ns（+7.5%）、loop +85%",
          "　　近对符号 j0−k0：−4.6 → −2.3 → +4.3 ns（翻面）",
          "类比：体重秤——每台每天读数都不同，要的是纪律"],
         ORANGE, 11, 9.8, 0.34, anchor_left=True)
    arrow(488, 528, 510, 528, INK, 2)
    b.append(text(500, 646,
                  "结论预告：正确性靠推理可以『证』，性能只能『测＋管理不确定度』——这就是模型会选错的根源",
                  10.5, MUTED))
    save("01-overview.svg", b)


# ======================= 图 2：两条信息链机制图 =======================

def fig2():
    W, H = 1000, 700
    b = frame(W, H, "两条信息链 + Cost Model 选错的三层机理（每层都有今天的实测兜底）")
    b.append(hand_line(300, 44, 700, 45, ORANGE, 3))

    # ---- 左：正确性链 ----
    lx, ly, lw, lh = 40, 66, 430, 300
    b.append(hand_rect(lx, ly, lw, lh, GREEN, 0.16, INK, 2))
    b.append(text(lx + lw / 2, ly + 24, "生成正确代码：语义链（推理）", 13.5, INK, "middle", True))
    steps_l = [
        ("① 约束从哪来", "IR 语义：Shape、类型、循环边界 [lb,ub)、", "累加顺序、初始化、尾部、活跃区间"),
        ("② 为什么可判定", "全部是关于『程序本身』的事实，", "不依赖跑在哪个进程 / 哪台机器"),
        ("③ 怎么交付", "Verifier（构造期拒绝）＋ 正确性门", "（执行期 bitwise ==，先于计时）"),
        ("④ 今天的新证据", "S1 24/24、W1 36/36 逐位相等；", "窗口 a / 窗口 b / 子进程——都一样"),
    ]
    yy = ly + 52
    for t, l1, l2 in steps_l:
        b.append(dot(lx + 26, yy + 4, 4, GREEN))
        b.append(text(lx + 40, yy + 8, t, 11, INK, "start", True))
        b.append(text(lx + 40, yy + 23, l1, 9.6, INK, "start"))
        b.append(text(lx + 40, yy + 36, l2, 9.6, INK, "start"))
        yy += 58
    b.append(text(lx + lw / 2, ly + lh - 14,
                  "性质：可证明、可复现、永不漂移——代价是它不告诉你谁快", 9.8, MUTED))

    # ---- 右：性能链 ----
    rx, ry, rw, rh = 530, 66, 430, 300
    b.append(hand_rect(rx, ry, rw, rh, ORANGE, 0.16, INK, 2))
    b.append(text(rx + rw / 2, ry + 24, "生成高性能代码：环境链（测量）", 13.5, INK, "middle", True))
    steps_r = [
        ("① 约束从哪来", "结构差：语句行数、tile 外壳、range、hoist", "——这些是程序事实（模型数得对）"),
        ("② 但结构差不等于时间", "还要乘单价——单价 = f(进程, regime, 窗口)，", "校准就是测量，测量就会漂"),
        ("③ 怎么交付", "Cost Model（砍数量）＋ Benchmark 纪律", "（3+7 / 3+21）＋ 出域闸门"),
        ("④ 今天的新证据", "j0 窄 55.7 → 宽 59.9 ns；loop +85%；", "j0−k0：−4.6 → −2.3 → +4.3 ns"),
    ]
    yy = ry + 52
    for t, l1, l2 in steps_r:
        b.append(dot(rx + 26, yy + 4, 4, ORANGE))
        b.append(text(rx + 40, yy + 8, t, 11, INK, "start", True))
        b.append(text(rx + 40, yy + 23, l1, 9.6, INK, "start"))
        b.append(text(rx + 40, yy + 36, l2, 9.6, INK, "start"))
        yy += 58
    b.append(text(rx + rw / 2, ry + rh - 14,
                  "性质：永远带不确定度——管理它，别假装它不存在", 9.8, MUTED))
    arrow(472, 216, 528, 216, RED, 2.2, dash="6 5")
    b.append(text(500, 202, "同一条流水线", 9.6, RED))
    b.append(text(500, 234, "两种证据", 9.6, RED))

    # ---- 底部：三层失效与兜底 ----
    b.append(text(48, 396, "Cost Model 选错的三层机理（今天的实测）与对应的工程兜底", 12.5, INK,
                  "start", True))
    fails = [
        ("失效①：近对无分辨率", BLUE,
         ["预测差 0.10%（S1）/ 0.01%（W1）", "实测摆动 ±5.9~8.0%，窗口间翻号",
          "→ 兜底：recall@K（top-5 实测）"],
         ["今天：K=1 付 +6.4%（S1）", "K=5＋决赛零损失"]),
        ("失效②：系统性偏差", GREEN,
         ["同进程预测 +7~16% 高估", "j/k 家族偏差不同（+16.4 vs +7.0）",
          "→ 兜底：同窗口决赛定名次"],
         ["名次用实测，模型只砍数量", "跨窗口比较只能当参考"]),
        ("失效③：regime 外推", RED,
         ["宽表 j0−k0 塌零→翻面（+4.3）", "ρ 0.985 → 0.945 → 0.883",
          "→ 兜底：出域闸门＋整体重校"],
         ["W1（512>256）亮灯：拒绝", "静默外推 = 拿噪声当偏好"]),
    ]
    x0, y0, cw, ch, gap = 40, 410, 300, 216, 20
    for i, (title, col, left, right) in enumerate(fails):
        x = x0 + i * (cw + gap)
        b.append(hand_rect(x, y0, cw, ch, col, 0.24, INK, 1.8))
        b.append(text(x + cw / 2, y0 + 20, title, 11.5, INK, "middle", True))
        for j, ln in enumerate(left):
            b.append(text(x + 14, y0 + 42 + j * 17, ln, 9.4, INK, "start"))
        b.append(hand_line(x + 12, y0 + 42 + len(left) * 17 + 4,
                           x + cw - 12, y0 + 42 + len(left) * 17 + 4, MUTED, 1.2, dash="4 4"))
        for j, ln in enumerate(right):
            b.append(text(x + 14, y0 + 46 + len(left) * 17 + 16 + j * 17, ln, 9.4, MUTED, "start"))
    b.append(text(W / 2, H - 22,
                  "一句话：语义链负责『能不能跑对』，环境链负责『谁更快』——模型选错，永远错在把环境链当语义链用",
                  10.5, MUTED))
    save("02-mechanism.svg", b)


# ======================= 图 3：反例结账图 =======================

def fig3():
    W, H = 1000, 660
    b = frame(W, H, "性能反例结账（数字全部来自 outputs/，2026-11-13 13:52 冻结运行）")
    b.append(hand_line(320, 44, 680, 45, ORANGE, 3))

    # ---- 左上：分辨率 vs 稳定度 ----
    card(b, 40, 64, 450, 268,
         "① 分辨率 vs 稳定度（exp a/b）",
         ["模型预测差：S1 = 0.10%，W1 = 0.01%（并列）",
          "窗口内实测差：5.85% ~ 7.81%（5 轮 A/B）",
          "→ 分辨率低世界 1~2 个数量级，近对名次 = 掷硬币",
          "",
          "画廊（同一对内核，谁快随窗口变）：",
          "　D110 进程：kij 快 6.5%　 D111 进程：ikj 快 8.2%",
          "　本进程·窗口 a（全测）：kij 快 6.4%",
          "　本进程·窗口 b（5 轮 A/B）：ikj 快 6.7% ←同进程翻号",
          "　子进程 #1 / #2（今天）：ikj 快 8.02% / 7.84%"],
         BLUE, 11.5, 10, 0.24, anchor_left=True)

    # ---- 右上：两枚硬币 ----
    card(b, 510, 64, 450, 268,
         "② K=1 的账：今天两枚硬币都输（exp a/d）",
         ["S1 64³：模型 top-1 = ikj（预测差 0.10%）",
          "　决赛：kij 15.99 vs ikj 17.01 ms → K=1 付 +6.4%",
          "W1 64×512×64：两表对近对并列（0.01%）",
          "　决赛：kij 130.92 vs ikj 139.42 ms → K=1 付 +6.5%",
          "",
          "D110 记录（topk-sensitivity）：K=1 三连错，",
          "　+4.8% / +6.6% / +8.1%——加上今天，五连错",
          "",
          "→ 模型选错不是『可能』，是 K=1 政策的常态；",
          "　 好消息：top-5＋同窗口决赛把损失归零（同批读数）"],
         RED, 11.5, 10, 0.24, anchor_left=True)

    # ---- 左下：regime 符号翻转 ----
    card(b, 40, 352, 450, 258,
         "③ regime 把家族符号翻了面（exp c）",
         ["窄表　j0−k0 = −4.6 ns（j 家族占优，ρ=0.985）",
          "宽表#1 j0−k0 = −2.3 ns（塌向零，ρ=0.945）",
          "宽表#2 j0−k0 = +4.3 ns（翻面！ρ=0.883）",
          "　→ 同一进程、同款探针、量两遍，符号不一致",
          "",
          "宽表#2 重排 S1：top-1 翻到 64³ ijk（另一家族）",
          "　实测慢 +10.6%，真冠军掉到第 4 名",
          "单价漂移：j0 +7.5%、ju +15.9%、loop +85.3%",
          "　（loop：宽 regime 里 v≥257 要现场分配整数对象）"],
         ORANGE, 11.5, 10, 0.24, anchor_left=True)

    # ---- 右下：出域对照 ----
    card(b, 510, 352, 450, 258,
         "④ 出域对照：W1 64×512×64 全测 36 候选（exp d）",
         ["闸门 domain_check 亮灯：512 > 校准边界 256",
          "　→ 窄表预测属外推：重校准或加大 K",
          "正确性门：36/36 bitwise 通过（语义链稳如泰山）",
          "",
          "结构排序皮实：两表 top-1 都是大 tile j 内层家族",
          "　但冠军是它的近对 kij：122.04 vs 132.52 ms",
          "　近对预测差 0.01% —— 结构能排，近对只能并列",
          "",
          "→ 出域腐蚀的是分辨率；闸门的价值：",
          "　 不指望模型自己发现自己在外推"],
         GREEN, 11.5, 10, 0.24, anchor_left=True)

    b.append(text(W / 2, H - 20,
                  "复盘答案：Cost Model 选错 = 分辨率失效（近对）× 偏差失效（绝对值）× regime 失效（符号）——工程答案分别是 top-K、决赛、闸门",
                  10, MUTED))
    save("03-counterexample.svg", b)


def main():
    os.makedirs(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "..", "images"), exist_ok=True)
    fig1()
    fig2()
    fig3()


if __name__ == "__main__":
    main()
