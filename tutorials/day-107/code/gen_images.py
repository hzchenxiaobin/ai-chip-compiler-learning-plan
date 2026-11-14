#!/usr/bin/env python3
"""生成第 107 天的 3 张手绘 sketch 风 SVG 技术图（Excalidraw-like）。

风格约定：白板涂鸦感——线条用带抖动的贝塞尔手绘路径、马克笔笔触、
3～4 种柔和强调色（橙/蓝/绿/红）＋米白背景、简单几何形状、手写感字体。
所有数字来自 bench.py 真实运行结果（code/outputs/，2026-11-13 最终一轮）。
固定随机种子，保证图可复现。
"""

from __future__ import annotations

import math
import os
import random

random.seed(107)

BG = "#FDFBF6"
BORDER = "#E7DFCE"
INK = "#3B3B3B"
MUTED = "#6b6257"
ORANGE = "#E8A87C"
BLUE = "#A9C4D4"
GREEN = "#9CBF8E"
RED = "#C97B7B"
FONT = "'Comic Sans MS','Kaiti SC','KaiTi','STKaiti',cursive"
W, H = 980, 640


def jit(m=1.6):
    return random.uniform(-m, m)


def hand_rect(x, y, w, h, fill=BG, opacity=0.65, stroke=INK, sw=1.4):
    pts = [(x + jit(), y + jit()), (x + w + jit(), y + jit()),
           (x + w + jit(), y + h + jit()), (x + jit(), y + h + jit())]
    d = f"M {pts[0][0]:.1f},{pts[0][1]:.1f} "
    for i in range(4):
        a, b = pts[i], pts[(i + 1) % 4]
        mx, my = (a[0] + b[0]) / 2 + jit(2.2), (a[1] + b[1]) / 2 + jit(2.2)
        d += f"Q {mx:.1f},{my:.1f} {b[0]:.1f},{b[1]:.1f} "
    d += "Z"
    return (f'<path d="{d}" stroke="{stroke}" stroke-width="{sw}" '
            f'stroke-linecap="round" stroke-linejoin="round" '
            f'fill="{fill}" fill-opacity="{opacity}"/>')


def hand_line(x1, y1, x2, y2, stroke=INK, sw=1.4, dash=None):
    dd = f' stroke-dasharray="{dash}"' if dash else ""
    mx, my = (x1 + x2) / 2 + jit(2.5), (y1 + y2) / 2 + jit(2.5)
    d = f"M {x1 + jit():.1f},{y1 + jit():.1f} Q {mx:.1f},{my:.1f} {x2 + jit():.1f},{y2 + jit():.1f}"
    return (f'<path d="{d}" stroke="{stroke}" stroke-width="{sw}" '
            f'stroke-linecap="round" fill="none"{dd}/>')


def arrow(x1, y1, x2, y2, stroke=INK, sw=1.8, dash=None):
    dd = f' stroke-dasharray="{dash}"' if dash else ""
    mx, my = (x1 + x2) / 2 + jit(2.0), (y1 + y2) / 2 + jit(2.0)
    ang = math.atan2(y2 - y1, x2 - y1)
    hx, hy = x2 - 9 * math.cos(ang), y2 - 9 * math.sin(ang)
    a1 = (hx + 5 * math.cos(ang + 2.5), hy + 5 * math.sin(ang + 2.5))
    a2 = (hx + 5 * math.cos(ang - 2.5), hy + 5 * math.sin(ang - 2.5))
    d = (f"M {x1 + jit():.1f},{y1 + jit():.1f} Q {mx:.1f},{my:.1f} "
         f"{x2:.1f},{y2:.1f} M {a1[0]:.1f},{a1[1]:.1f} L {x2:.1f},{y2:.1f} "
         f"L {a2[0]:.1f},{a2[1]:.1f}")
    return (f'<path d="{d}" stroke="{stroke}" stroke-width="{sw}" '
            f'stroke-linecap="round" fill="none"{dd}/>')


def text(x, y, s, size=13, fill=INK, anchor="middle", bold=False):
    wt = ' font-weight="bold"' if bold else ""
    return (f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" '
            f'text-anchor="{anchor}"{wt}>{s}</text>')


def frame(title):
    return [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
            f'font-family="{FONT}">',
            hand_rect(4, 4, W - 8, H - 8, BG, 1.0, BORDER, 2),
            text(W / 2, 36, title, 21, INK, "middle", True)]


def save(name, body):
    out = os.path.join(os.path.dirname(__file__), "..", "images", name)
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(body) + "\n</svg>\n")
    print(f"  已生成 images/{name}")


# ======================= 图 1：全局定位图 =======================

def fig1():
    b = frame("第 107 天定位：统一 Benchmark 工具——测量协议第一次成为基础设施")
    b.append(hand_line(330, 47, 650, 48, ORANGE, 3))

    # ---- 上排：调优主线 ----
    b.append(text(60, 68, "调优主线", 13, INK, "start", True))
    steps = [("图优化·融合", "D48~56"), ("循环 Lowering", "D85~89"),
             ("Tiling", "D92~96"), ("候选生成", "D106"),
             ("统一 Benchmark", "D107"), ("Auto-tuning", "D108"),
             ("验收·GFLOPS", "D109/111")]
    for i, (nm, day) in enumerate(steps):
        x = 60 + i * 132
        hot = day == "D107"
        b.append(hand_rect(x, 76 if hot else 80, 118, 58 if hot else 50,
                           ORANGE if hot else BG, 0.8 if hot else 1.0,
                           INK, 2.2 if hot else 1.4))
        b.append(text(x + 59, 101, nm, 11.5, INK, "middle", True))
        b.append(text(x + 59, 121 if hot else 119, day, 10, MUTED))
        if i < 6:
            b.append(arrow(x + 120, 104, x + 130, 104, MUTED, 1.6))
    b.append(text(490, 150, "D106 喂来 12,970 个幸存者；今天给它们一条统一的『测量流水线』", 10.5, RED))

    # ---- 中排：D97 一次性脚本 vs D107 统一工具 ----
    b.append(text(60, 176, "从一次性实验到统一工具（D97 → D107）", 13, INK, "start", True))
    b.append(hand_rect(56, 186, 300, 92, "#EDE7DA", 0.9, MUTED, 1.4))
    b.append(text(206, 208, "D97：一次性实验脚本", 12, MUTED, "middle", True))
    b.append(text(206, 230, "协议写死在 main 里，换配置要手搓", 10, MUTED))
    b.append(text(206, 248, "结果只有文本表，程序没法消费", 10, MUTED))
    b.append(text(206, 266, "env 单独躺在 env.txt，和表不绑定", 10, MUTED))
    b.append(arrow(362, 232, 396, 232, INK, 2.2))
    b.append(hand_rect(400, 186, 300, 92, GREEN, 0.35, INK, 1.8))
    b.append(text(550, 208, "D107：统一 Benchmark 工具", 12, INK, "middle", True))
    b.append(text(550, 230, "bench_one(cfg) 一个入口，协议一处默认", 10, INK))
    b.append(text(550, 248, "JSONL 每条自包含 env+protocol+原始样本", 10, INK))
    b.append(text(550, 266, "被拒配置也留记录：fail-visible", 10, INK))
    b.append(hand_rect(716, 186, 220, 92, BLUE, 0.3, INK, 1.6))
    b.append(text(826, 208, "D97 的遗产原样继承", 11.5, INK, "middle", True))
    b.append(text(826, 228, "warmup=3 · repeats=21", 10, INK))
    b.append(text(826, 244, "正确性门先行 · 中位数口径", 10, INK))
    b.append(text(826, 262, "差距要大于波动才下结论", 10, INK))

    # ---- 下排：工具流水线 5 步 ----
    b.append(text(60, 302, "统一入口 bench_one(cfg, spec, protocol)：一条流水线五道工序", 13, INK, "start", True))
    stages = [
        ("① 固定输入", "seed=42", "同一 spec 永远\n同一份 A/B/bias"),
        ("② 正确性门", "54/54 + 1 拒", "逐位相等；被拒\n不计时（no-tail ✗）"),
        ("③ 预热 ×3", "全部丢弃", "冷启动成本：首调\n分配器 / 缺页"),
        ("④ 计时 ×21", "perf_counter", "每样本同一初始态\n时钟只包住内核"),
        ("⑤ 统计+记录", "JSONL", "median/MAD/mean\n/outl + 原始样本"),
    ]
    for i, (t1, t2, t3) in enumerate(stages):
        x = 56 + i * 180
        b.append(hand_rect(x, 316, 164, 108, [BLUE, GREEN, GREEN, GREEN, ORANGE][i],
                           0.4, INK, 1.8))
        b.append(text(x + 82, 338, t1, 11.5, INK, "middle", True))
        b.append(text(x + 82, 356, t2, 10.5, RED if i == 1 else INK, "middle", True))
        for j, ln in enumerate(t3.split("\n")):
            b.append(text(x + 82, 376 + j * 16, ln, 9.5, MUTED, "middle"))
        if i < 4:
            b.append(arrow(x + 166, 370, x + 178, 370, INK, 2.0))

    # ---- 底部：格式卡 ----
    b.append(hand_rect(56, 444, 880, 96, "#F5EFE0", 1.0, BORDER, 1.4))
    b.append(text(76, 468, "结果格式 d107.bench-result/1（一行一条 JSON）：", 12, INK, "start", True))
    b.append(text(76, 490, "schema 版本号 · kernel(workload 身份) · env 快照 · protocol(warmup/repeats/gc/policy)", 10.5, INK, "start"))
    b.append(text(76, 510, "correctness(过门/误差) · stats_ms(median/mean/MAD/spread/outl) · samples_ms 原始样本全落盘", 10.5, INK, "start"))
    b.append(text(76, 530, "统计可换口径重算（重复次数扫描不用重跑）· 被拒也留痕 · 记录离开目录不失户口", 10, MUTED, "start"))
    b.append(text(490, 558, "分工边界：工具只测量只记录；搜索给 D108，GFLOPS 给 D109，排序给 D110", 11, RED, "middle", True))

    save("01-overview.svg", b)


# ======================= 图 2：协议机制图 =======================

def fig2():
    b = frame("bench_one 解剖：门→预热→计时→统计，以及三个口径怎么分家")
    b.append(hand_line(330, 47, 650, 48, ORANGE, 3))

    # ---- 左：时间线 ----
    b.append(text(60, 70, "一次 bench_one 调用（真实时序）", 13, INK, "start", True))
    # 门
    b.append(hand_rect(56, 84, 400, 52, GREEN, 0.4, INK, 1.8))
    b.append(text(256, 106, "② 正确性门（不计时）", 11.5, INK, "middle", True))
    b.append(text(256, 126, "逐位比对参考实现；no-tail 内核 max_abs_err=3.77 → REJECTED", 9.5, MUTED))
    # 预热
    b.append(hand_rect(56, 146, 400, 52, "#EDE7DA", 0.9, MUTED, 1.5))
    b.append(text(256, 168, "③ 预热 ×3（划掉=丢弃）", 11.5, MUTED, "middle", True))
    b.append(text(256, 188, "冷启动：首次调用 / 分配器冷态 / 缺页——与快慢无关的系统性偏差", 9, MUTED))
    b.append(hand_line(76, 164, 200, 165, RED, 2.4))
    b.append(hand_line(320, 164, 436, 165, RED, 2.4))
    # 计时
    b.append(hand_rect(56, 208, 400, 84, BLUE, 0.4, INK, 1.8))
    b.append(text(256, 230, "④ 计时 ×21", 11.5, INK, "middle", True))
    b.append(text(256, 248, "每个样本：C 重置回同一初始态（时钟外）", 9.5, MUTED))
    b.append(text(256, 264, "t0=perf_counter() → 只跑内核 → t1", 9.5, MUTED))
    b.append(text(256, 282, "21 个样本 = 21 个『有效计算+噪声』的混合物", 9.5, MUTED))
    # 统计
    b.append(hand_rect(56, 302, 400, 64, ORANGE, 0.4, INK, 1.8))
    b.append(text(256, 324, "⑤ 统计 + 记录", 11.5, INK, "middle", True))
    b.append(text(256, 342, "median · MAD · mean · spread% · outliers(MAD 规则)", 9.5, MUTED))
    b.append(text(256, 358, "原始 samples 全部落盘 → 换口径重算不用重跑", 9.5, MUTED))
    for y0, y1 in ((136, 146), (198, 208), (292, 302)):
        b.append(arrow(256, y0, 256, y1, INK, 2.0))

    # 左下：门与拒绝对照小卡
    b.append(hand_rect(56, 380, 400, 58, "#F5EFE0", 1.0, BORDER, 1.4))
    b.append(text(76, 402, "门成绩（outputs/correctness.txt）：", 10.5, INK, "start", True))
    b.append(text(76, 420, "3 个奇数 shape × 6 顺序 × 3 展开 = 54/54 逐位相等", 10, INK, "start"))
    b.append(text(76, 436, "靶子 no-tail 内核：passed=False，不计时也照样产记录", 10, RED, "start"))

    # ---- 右：样本点图（真实 201 样本统计）----
    b.append(text(740, 70, "三个口径怎么分家（201 样本长跑，真实数据）", 12.5, INK, "middle", True))
    b.append(hand_rect(490, 82, 480, 176, BG, 1.0, INK, 1.6))
    # 时间轴
    ax0, ax1 = 516, 944
    b.append(hand_line(ax0, 216, ax1, 214, MUTED, 1.4))
    # 基线中位数带
    y_med = 152
    b.append(hand_line(ax0, y_med, ax1, y_med - 1, GREEN, 2.6))
    b.append(text(946, y_med - 4, "median 57.91", 9.5, "#5a7d4e", "end", True))
    # 均值线
    y_mean = 143
    b.append(hand_line(ax0, y_mean, ax1, y_mean - 1, ORANGE, 2.6, "6 5"))
    b.append(text(946, y_mean - 6, "mean 58.36", 9.5, "#a4652f", "end", True))
    # 样本散点：干净主体 + 离群（按真实比例放 36 个代表点）
    for i in range(36):
        x = ax0 + 6 + i * 11.6
        if i == 31:      # #178 的 +48.5% 离群
            b.append(text(x, 106, "★", 15, RED, "middle"))
            b.append(text(x - 6, 92, "#178: 85.98 (+48.5%)", 9.5, RED, "end", True))
        elif i in (7, 17, 27):   # 小离群
            b.append(text(x, 136 + jit(4), "•", 12, RED, "middle"))
        else:
            b.append(text(x, 150 + jit(3.5), "•", 12, INK, "middle"))
    b.append(text(730, 236, "23/201 个 MAD 离群，聚成 15 个连续短串——离群在时间上成串：", 9.5, MUTED))
    b.append(text(730, 251, "一次机器忙碌让相邻几个样本一起变慢，不是 23 个独立噪声", 9.5, MUTED))

    # 右中：离群规则卡
    b.append(hand_rect(490, 270, 480, 76, BLUE, 0.3, INK, 1.6))
    b.append(text(730, 292, "离群规则：|x − median| > 3.5 × 1.4826 × MAD（修正 z 分数）", 10.5, INK, "middle", True))
    b.append(text(730, 310, "本轮阈值 0.31 ms（MAD 只有 0.06：主体越稳阈值越紧，规则自适应）", 9.5, MUTED))
    b.append(text(730, 328, "只标记只计数，不悄悄删——离群值是数据，不是污点", 9.5, MUTED))

    # 右下：median vs mean 用途分家 + 稀释账
    b.append(hand_rect(490, 358, 232, 108, GREEN, 0.3, INK, 1.6))
    b.append(text(606, 380, "median：典型一次", 11, INK, "middle", True))
    b.append(text(606, 398, "『这个内核一般多快』", 9.5, MUTED))
    b.append(text(606, 416, "排名、比较、下结论用它", 9.5, MUTED))
    b.append(text(606, 434, "对离群免疫（201 个样本", 9.5, MUTED))
    b.append(text(606, 450, "里 23 个离群都拉不动）", 9.5, MUTED))
    b.append(hand_rect(738, 358, 232, 108, ORANGE, 0.35, INK, 1.6))
    b.append(text(854, 380, "mean：总量估算", 11, INK, "middle", True))
    b.append(text(854, 398, "『整晚 auto-tuning 跑多久』", 9.5, MUTED))
    b.append(text(854, 416, "总时长=Σ样本，mean 才对", 9.5, MUTED))
    b.append(text(854, 434, "脆弱度 ∝ 离群÷样本数：", 9.5, MUTED))
    b.append(text(854, 452, "repeats=3 时 +48.5%→拖 +16.2%", 9.5, RED, "middle", True))

    # 底部
    b.append(hand_rect(56, 466, 914, 60, "#F5EFE0", 1.0, BORDER, 1.4))
    b.append(text(490, 490, "gc 口径（同进程背靠背）：gc=off 62.30 vs gc=on 63.32，差 +1.64%——读数就是读数，写进 protocol.gc", 10.5, INK))
    b.append(text(490, 512, "但跨进程漂移更大：同配置主表 57.36 / 长跑 57.91 / 口径实验 62.30（8.6%）→ 配置间排名必须同进程测", 10.5, RED, "middle", True))

    save("02-mechanism.svg", b)


# ======================= 图 3：实测结果图 =======================

def fig3():
    b = frame("实测 7 配置：中位数排名 + 两个『直觉翻车』现场（全部真实数据）")
    b.append(hand_line(330, 47, 650, 48, ORANGE, 3))

    # ---- 主条形图：中位数 ----
    data = [
        ("96³ ikj U=1", "单 tile：无外壳开销", 50.59, BLUE, ""),
        ("32³ ikj U=1", "行访问（D96/D97 reorder 同构）", 57.36, GREEN, ""),
        ("32³ kij U=1", "k 最外层的行访问变体", 63.26, GREEN, ""),
        ("32³ ijk U=1", "B 跨步（D97 baseline 同构）", 63.87, GREEN, ""),
        ("32³ jik U=1", "本轮 spread 19.6%：被干扰段打中", 64.67, GREEN, ""),
        ("32³ ikj U=8", "展开比 U=1 慢 +23.6%！", 70.93, RED, ""),
        ("32³ jki U=1", "C/A 双跨步，最惨（方向同 D92）", 76.97, RED, ""),
    ]
    b.append(text(60, 72, "负载 matmul_bias 96×96×96 seed=42 · 协议 warmup=3 repeats=21 gc=off · 门 54/54 逐位", 10.5, MUTED, "start"))
    x0, y0, bh, gap = 250, 88, 22, 16
    scale = 6.5
    for i, (name, note, med, color, _) in enumerate(data):
        y = y0 + i * (bh + gap)
        b.append(text(x0 - 14, y + bh / 2 + 2, name, 10.5, INK, "end", True))
        b.append(text(x0 - 14, y + bh / 2 + 15, note, 8.5, MUTED, "end"))
        b.append(hand_rect(x0, y, med * scale, bh, color, 0.6, INK, 1.5))
        b.append(text(x0 + med * scale + 8, y + bh / 2 + 4, f"{med:.2f} ms", 11, INK, "start", True))
    b.append(text(60, y0 + 7 * (bh + gap) + 4, "中位数口径，单位 ms，越短越好；MAD 离群拉不动排名", 9.5, MUTED, "start"))

    # ---- 右上：结论有效性卡 ----
    b.append(hand_rect(786, 84, 192, 96, "#F5EFE0", 1.0, BORDER, 1.6))
    b.append(text(882, 106, "结论有效性（D97 规则）", 10, INK, "middle", True))
    b.append(text(882, 126, "第 1~2 名差距 13.37%", 10, INK, "middle", True))
    b.append(text(882, 142, "vs 2×MAD 口径 0.20%", 10, INK, "middle", True))
    b.append(text(882, 164, "→ 结论成立", 12, "#5a7d4e", "middle", True))

    # ---- 底部左：翻车现场 1：展开 ----
    b.append(hand_rect(56, 400, 440, 132, RED, 0.22, INK, 1.8))
    b.append(text(276, 422, "翻车现场 ①：U=8 在 CPython 里反而慢", 11.5, INK, "middle", True))
    b.append(text(276, 442, "D96 的 C++ 账：展开省循环开销（U=8 机器码 3.2×）", 10, MUTED))
    b.append(text(276, 460, "CPython 的账：Ci[v3 + u] 每条多一次加法＋下标，", 10, INK))
    b.append(text(276, 478, "比省下的 FOR_ITER 更贵 → 57.36 → 70.93（+23.6%）", 10, INK))
    b.append(text(276, 500, "『看起来该快的变换』必须实测——这就是工具存在的理由", 10.5, RED, "middle", True))
    b.append(text(276, 518, "（内核性能反映字节码成本模型，不代表硬件，见 README 边界）", 9, MUTED, "middle"))

    # ---- 底部右：翻车现场 2：spread ----
    b.append(hand_rect(516, 400, 440, 132, BLUE, 0.25, INK, 1.8))
    b.append(text(736, 422, "翻车现场 ②：同一张表里藏着一次干扰", 11.5, INK, "middle", True))
    b.append(text(736, 442, "jik 的 spread=19.64%、mean−med=+0.67%", 10, INK))
    b.append(text(736, 460, "（21 个样本里混进一个慢尾；别的配置 spread 只有 0.4~3.5%）", 9.5, MUTED))
    b.append(text(736, 478, "中位数 64.67 稳住；均值 65.11 被拖走", 10, INK))
    b.append(text(736, 500, "spread/outl 两列是机器当时忙不忙的『体检指标』", 10.5, INK, "middle", True))
    b.append(text(736, 518, "报性能不带这两列 = 把天平精度藏起来", 9.5, MUTED, "middle"))

    save("03-results.svg", b)


if __name__ == "__main__":
    print("生成第 107 天手绘图：")
    fig1()
    fig2()
    fig3()
