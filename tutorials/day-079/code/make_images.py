#!/usr/bin/env python3
"""生成第 79 天教程的 4 张手绘风（Excalidraw-like）SVG 技术图。

运行方式：
    python3 make_images.py

输出到 ../images/ 目录：
    01-overview.svg   今天在验证链路中的位置
    02-metrics.svg    三种误差指标（绝对/相对/ULP）的适用场景与盲区
    03-ulp.svg        ULP 的机制：浮点刻度上数格子
    04-verdicts.svg   真实实验的判定对照矩阵（数据来自 ref_check.py 实际运行）

风格与 Day 78 保持一致：手绘抖动线条、马克笔笔触、米白背景、
蓝/橙/绿/红四种柔和强调色、简单几何形状。
"""

import math
import random
from pathlib import Path

random.seed(79)

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
    s = f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round"'
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
    ang = math.atan2(y2 - y1, x2 - y1)
    return (f'<path d="{jseg(x1, y1, x2, y2)}" {style("none", stroke, sw, dash)}/>'
            + head(x2, y2, ang, stroke, sw))


def carrow(p0, ctrl, p1, stroke=INK, sw=2.2, dash=None):
    d = f"M {p0[0]:.1f},{p0[1]:.1f} Q {ctrl[0]:.1f},{ctrl[1]:.1f} {p1[0]:.1f},{p1[1]:.1f}"
    ang = math.atan2(p1[1] - ctrl[1], p1[0] - ctrl[0])
    return f'<path d="{d}" {style("none", stroke, sw, dash)}/>' + head(p1[0], p1[1], ang, stroke, sw)


def text(x, y, s, size=16, fill=INK, anchor="start", rot=None):
    t = f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-size="{size}" fill="{fill}"'
    if rot:
        t += f' transform="rotate({rot} {x} {y})"'
    return t + f">{s}</text>"


def svg_doc(w, h, body):
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d">' % (w, h, w, h)
            + f'<rect x="3" y="3" width="{w - 6}" height="{h - 6}" rx="7" fill="{BG}"/>'
            + f'<g font-family="{FONT}">' + body + "</g></svg>")


def dot(x, y, color, r=7):
    return (f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{color}" '
            f'stroke="{INK}" stroke-width="1.8"/>')


# ---------------------------------------------------------------------------
# 图 1：全局定位 + 今天的验证流水线
# ---------------------------------------------------------------------------

def fig1():
    b = []
    b.append(text(55, 54, "第 79 天：参考实现与误差指标", 27))
    b.append(text(55, 82, "—— 把昨天的浮点直觉，变成能判 PASS / FAIL 的工具", 16, SOFT, rot=-0.4))

    b.append(text(55, 120, "本周：数值精度周（第 12 周）", 13, SOFT))
    week = [
        ("Day 77", "融合复盘", None, None),
        ("Day 78", "浮点格式 + 累加误差", "知道误差为什么会来", None),
        ("Day 79 · 今天", "参考实现 + 误差指标", "给误差定判据", None),
        ("Day 80", "FP16 / BF16 对照", None, "明天用今天的工具"),
    ]
    xs = [50, 272, 494, 716]
    for i, ((cap, main, sub, sub2), x) in enumerate(zip(week, xs)):
        hot = i == 2
        b.append(srect(x, 130, 205, 70,
                       L_ORANGE if hot else "none",
                       ORANGE if hot else INK, 3.0 if hot else 2.2))
        b.append(text(x + 102, 152, cap, 14, SOFT, "middle"))
        b.append(text(x + 102, 172, main, 14.5, INK, "middle"))
        if sub:
            b.append(text(x + 102, 192, sub, 12, RED if hot else SOFT, "middle"))
        if sub2:
            b.append(text(x + 102, 192, sub2, 12, BLUE, "middle"))
    for x in (258, 480, 702):
        b.append(arrow(x, 165, x + 11, 165))

    b.append(text(55, 252, "今天搭的验证流水线（今日产出：参考测试工具 ref_check.py）", 13, SOFT))
    steps = [
        ("① 固定输入", "种子可复现", 150, None),
        ("② Golden", "FP64 参考结果", 150, BLUE),
        ("③ 被测实现", "FP16/FP32/BF16", 150, None),
        ("④ 误差指标", "abs / rel / ULP", 150, None),
        ("⑤ 阈值表", "按 dtype 配置", 118, None),
        ("⑥ 判定", "PASS / FAIL", 90, None),
    ]
    x = 50
    xs2 = []
    for t1, t2, w, hc in steps:
        xs2.append((x, w))
        hot = hc is not None
        b.append(srect(x, 264, w, 64, L_BLUE if hot else "none",
                       hc if hot else INK, 2.6 if hot else 2.2))
        b.append(text(x + w / 2, 288, t1, 15, INK, "middle"))
        b.append(text(x + w / 2, 312, t2, 12.5, SOFT, "middle"))
        x += w + 15
    for i in range(len(xs2) - 1):
        x0, w0 = xs2[i]
        x1, _ = xs2[i + 1]
        b.append(arrow(x0 + w0 + 3, 296, x1 - 4, 296))

    b.append(text(55, 372, "三种误差指标各管一段（第 3~4 节展开）：", 14.5, INK))
    cards = [
        ("绝对误差 abs", "|a - b|", "量纲明确；但大数区过松、不看比例", None),
        ("相对误差 rel", "|a - b| / |ref|", "看比例；但 ref 接近 0 时爆炸", None),
        ("ULP", "数浮点格子", "最懂浮点；但近零区格数失真", ORANGE),
    ]
    cx = [50, 355, 660]
    for (t1, t2, t3, hc), x in zip(cards, cx):
        hot = hc is not None
        b.append(srect(x, 386, 290, 88, L_ORANGE if hot else "none", hc if hot else INK,
                       2.6 if hot else 2.2))
        b.append(text(x + 16, 412, t1, 16, INK))
        b.append(text(x + 16, 436, t2, 14, BLUE if not hot else INK))
        b.append(text(x + 16, 460, t3, 12.5, SOFT))

    b.append(srect(50, 506, 880, 76, L_RED, RED, 2.4))
    b.append(text(66, 534, "贯穿问题：NPU 算子和 CPU 参考结果对不上，是算子写错了，", 15.5, INK))
    b.append(text(66, 558, "还是浮点本来就允许差一点？—— 今天给出能自动回答它的“判官”。", 15.5, INK))
    b.append(text(66, 578, "（昨天只解释了“为什么会有误差”，今天回答“差多少才算错”。）", 12.5, SOFT))
    return svg_doc(960, 606, "".join(b))


# ---------------------------------------------------------------------------
# 图 2：三把误差尺子的适用场景与盲区
# ---------------------------------------------------------------------------

def fig2():
    b = []
    b.append(text(55, 50, "三把误差尺子：绝对 / 相对 / ULP", 26))
    b.append(text(55, 78, "同一个「差多少」的问题，在数轴不同区段要用不同的尺子量", 15, SOFT))

    # 中央数轴：刻度从密到疏
    ax_y = 128
    b.append(sline(80, ax_y, 880, ax_y, INK, 2.4) + head(880, ax_y, 0, INK, 2.4))
    b.append(text(884, 110, "数值变大 →", 13, SOFT))
    dens = [(90 + i * 4.5) for i in range(9)] + \
           [(150 + i * 14) for i in range(8)] + \
           [(270 + i * 42) for i in range(7)] + \
           [(540 + i * 60) for i in range(6)]
    for x in dens:
        b.append(sline(x, ax_y - 9, x, ax_y + 9, INK, 1.8, amp=0.6))
    b.append(text(90, ax_y + 28, "0", 13, SOFT, "middle"))
    b.append(text(300, ax_y + 28, "1 附近", 13, SOFT, "middle"))
    b.append(text(660, ax_y + 28, "1e8 附近", 13, SOFT, "middle"))
    b.append(text(460, ax_y - 22, "浮点数轴：越往大数走，格子越疏（Day 78 的刻度尺）", 13.5, SOFT, "middle"))

    # 三个放大区
    zones = [
        (60, 230, "近零区（残差 / 差分）", RED, L_RED,
         ["abs：唯一有意义的尺子（差 1.9e-8 确实小）",
          "rel：|ref|→0，误差爆炸到 19% —— 误报",
          "ULP：格子细到 7e-15，差出 270 万格 —— 失真",
          "对策：用 atol 兜底（见下方组合公式）"]),
        (355, 230, "中庸量级区（常规激活 / 权重）", GREEN, L_GREEN,
         ["abs：可用，但阈值要跟量纲绑定",
          "rel：最常用 —— rtol=1e-5 (FP32) 一档",
          "ULP：数学算子验收的黄金标尺（≤4 格）",
          "对策：rtol 为主，ULP 做精密诊断"]),
        (650, 230, "大数区（大 loss / 大坐标）", BLUE, L_BLUE,
         ["abs：过松 —— 差 1.0 也只占 1e-8",
          "rel：合适（比例才是关心的东西）",
          "ULP：格子粗到 8 —— 装不下就显示 0 格",
          "对策：rtol 为主；ULP 只说「已到最近格」"]),
    ]
    for x, y, title, color, fill, lines in zones:
        b.append(carrow((x + 150, y - 6), (x + 150, y - 40), (x + 150, ax_y + 46),
                        color, 2.0, dash="5 4"))
        b.append(srect(x, y, 300, 150, fill, color, 2.4))
        b.append(text(x + 150, y + 26, title, 15, color, "middle"))
        for i, ln in enumerate(lines):
            b.append(text(x + 14, y + 54 + i * 24, ln, 12.5, INK))

    # 组合公式
    b.append(srect(60, 430, 840, 92, L_ORANGE, ORANGE, 2.6))
    b.append(text(76, 458, "取长补短的组合判定（np.allclose / torch.assert_close 同款公式）：", 15.5, INK))
    b.append(text(480, 490, "|actual - desired|  ≤  atol  +  rtol × |desired|", 19, BLUE, "middle"))
    b.append(text(480, 514, "rtol 管住「按比例该多大」，atol 兜住「接近 0 时别误报」", 13, SOFT, "middle"))
    return svg_doc(960, 544, "".join(b))


# ---------------------------------------------------------------------------
# 图 3：ULP 的机制
# ---------------------------------------------------------------------------

def fig3():
    b = []
    b.append(text(55, 50, "ULP：在浮点刻度上数格子", 26))
    b.append(text(55, 78, "绝对/相对误差给出一个小数，ULP 直接回答「差几格」—— 昨天讲的刻度间距，今天变成指标", 14.5, SOFT))

    # 左：fp16 数轴放大
    b.append(text(55, 118, "例 1：FP16 里 0.1 + 0.2 vs 0.3（真实运行结果）", 15.5, INK))
    b.append(srect(55, 130, 480, 220, "none", INK, 2.2))
    gy = 250
    b.append(sline(85, gy, 505, gy, INK, 2.4))
    grids = [(110, "0x34CB"), (220, "0x34CC"), (330, "0x34CD"), (440, "0x34CE")]
    for x, lab in grids:
        b.append(sline(x, gy - 10, x, gy + 10, INK, 2.0, amp=0.7))
        b.append(text(x, gy + 30, lab, 12.5, SOFT, "middle"))
    b.append(text(110, gy - 18, "0.29956", 12, SOFT, "middle"))
    b.append(text(220, gy - 18, "0.29980", 12, SOFT, "middle"))
    b.append(text(330, gy - 18, "0.30005", 12, SOFT, "middle"))
    b.append(text(440, gy - 18, "0.30029", 12, SOFT, "middle"))
    b.append(text(505, gy + 30, "每格 = 1 ULP ≈ 2.4e-4", 12.5, SOFT, "end"))
    # 两个点
    b.append(dot(220, gy - 46, BLUE))
    b.append(text(220, gy - 58, "0.1f16 + 0.2f16 = 0.2998046875", 13, BLUE, "middle"))
    b.append(dot(330, gy + 56, ORANGE))
    b.append(text(330, gy + 82, "0.3f16 = 0.300048828125", 13, ORANGE, "middle"))
    b.append(text(275, gy + 6, "1 ULP", 14, RED, "middle"))
    b.append(srect(240, gy - 8, 70, 16, "none", RED, 1.8, dash="4 4"))
    b.append(text(75, 158, "两数各落在相邻的格子上，差 1 格；abs=2.4e-4 看不出", 13, INK))
    b.append(text(75, 178, "「差几格」，ULP = 1 一眼看清 —— 这不是 bug，是舍入路径不同。", 13, INK))

    # 右：位模式 -> 单调整数
    b.append(text(570, 118, "怎么数格子：位模式 → 单调整数", 15.5, INK))
    b.append(srect(570, 130, 360, 220, "none", INK, 2.2))
    b.append(text(588, 156, "把浮点位模式当整数读，负数折叠：", 13, INK))
    rows = [
        ("+0", "0x0000", "… 编号居中"),
        ("正数", "0x3C00(=1)", "编号 = 位模式 + 2^15"),
        ("负数", "0xBC00(=-1)", "编号 = 2^16 - 位模式"),
    ]
    for i, (sign, bits, note) in enumerate(rows):
        y = 184 + i * 34
        b.append(srect(588, y - 18, 56, 24, L_BLUE, INK, 1.6, amp=0.7))
        b.append(text(616, y - 1, sign, 12.5, INK, "middle"))
        b.append(text(660, y - 1, bits, 13, INK))
        b.append(text(760, y - 1, note, 12, SOFT))
    b.append(text(588, 296, "折叠后：编号随浮点值严格递增 →", 13, INK))
    b.append(text(588, 318, "ULP 距离 = |编号(a) - 编号(舍入后的 ref)|", 13, BLUE))

    # 底部：两个真实案例
    b.append(text(55, 384, "例 2：两个边角案例（真实运行结果，方向相反）", 15.5, INK))
    b.append(srect(55, 396, 430, 140, L_GREEN, GREEN, 2.4))
    b.append(text(71, 424, "1e8 + 1（FP32）vs 真值 100000001：", 13.5, INK))
    b.append(text(71, 448, "abs = 1.0，rel = 1e-8，ULP = 0", 14, GREEN))
    b.append(text(71, 472, "100000001 舍入到 FP32 最近的格子还是 1e8", 12.5, SOFT))
    b.append(text(71, 494, "（该区间间距 8）→ 不是算错，是格子装不下。", 12.5, SOFT))
    b.append(text(71, 518, "ULP = 0 的含义：已经在最近的格子上了。", 13, INK))

    b.append(srect(510, 396, 420, 140, L_RED, RED, 2.4))
    b.append(text(526, 424, "近零残差 1e-7（FP32）：", 13.5, INK))
    b.append(text(526, 448, "abs = 1.9e-8，rel = 19%，ULP = 2,703,467 格", 14, RED))
    b.append(text(526, 472, "1e-7 附近一格只有 7.1e-15，格子极细，", 12.5, SOFT))
    b.append(text(526, 494, "数格子数出几百万 —— ULP 在近零区失真，", 12.5, SOFT))
    b.append(text(526, 518, "这里的「差多少」要用 atol 说话。", 13, INK))
    return svg_doc(960, 558, "".join(b))


# ---------------------------------------------------------------------------
# 图 4：真实实验的判定对照矩阵（数据来自 ref_check.py 实际运行）
# ---------------------------------------------------------------------------

def fig4():
    b = []
    b.append(text(55, 48, "真实运行：同一批实验，不同 golden / 不同阈值 → 判定翻转", 24))
    b.append(text(55, 76, "数据来自 python3 ref_check.py（Python 3.11.4 + numpy 1.26.4 实际输出）；判定规则见 TOLERANCES",
                  13.5, SOFT))

    # 表头
    hx = [55, 400, 520, 640, 760]
    hy = 100
    heads = ["案例（被测 vs 参考）", "max_abs", "max_rel", "max_ulp", "判定"]
    widths = [345, 120, 120, 120, 120]
    b.append(srect(55, hy, 865, 34, L_BLUE, INK, 2.2))
    for x, w, h_ in zip(hx, widths, heads):
        b.append(text(x + w / 2, hy + 23, h_, 14, INK, "middle"))

    rows = [
        ("MatMul fp32入·fp32累加 vs FP64 golden", "9.5e-8", "6.8e-8", "1 格", "PASS", GREEN),
        ("MatMul fp16入·fp32累·fp32出 vs FP64 golden", "2.0e-4", "6.1e-5", "819 格", "FAIL", RED),
        ("同一实现 vs 量化输入版 golden（实验 1b）", "0", "0", "0 格", "PASS", GREEN),
        ("MatMul fp16入·fp16累·fp16出（fp16 阈值）", "1.2e-3", "5.5e-4", "1 格", "PASS", GREEN),
        ("MatMul bf16入·fp32累·bf16出（bf16 阈值）", "6.3e-3", "4.5e-3", "-", "PASS", GREEN),
        ("1e8 + 1（FP32）vs 真值 100000001", "1.0", "1e-8", "0 格", "PASS", GREEN),
        ("近零残差 1e-7（FP32）vs fsum 真值", "1.9e-8", "19%", "270万格", "FAIL", RED),
    ]
    y = hy + 34
    rh = 44
    for i, (name, ab, rel, ulp, verdict, color) in enumerate(rows):
        special = i == 2
        fill = L_ORANGE if special else ("#f7f2e8" if i % 2 == 0 else "none")
        b.append(srect(55, y, 865, rh, fill, INK, 1.6, amp=0.9))
        b.append(text(hx[0] + 14, y + 27, name, 13, INK))
        for x, w, v in zip(hx[1:], widths[1:], (ab, rel, ulp)):
            b.append(text(x + w / 2, y + 27, v, 13, INK, "middle"))
        b.append(srect(hx[4] + 25, y + 8, 70, rh - 16,
                       "#e5f1dc" if verdict == "PASS" else "#f9dfd9",
                       color, 2.4, amp=0.8))
        b.append(text(hx[4] + 60, y + 28, verdict, 15, color, "middle"))
        if special:
            b.append(text(hx[0] + 14, y + 40, "↑ 只换了 golden（输入先量化到 FP16 再用 FP64 算）",
                          11.5, RED))
        y += rh

    # 结论框
    b.append(srect(55, y + 16, 865, 96, L_ORANGE, ORANGE, 2.4))
    b.append(text(71, y + 42, "读图三个信号：", 14.5, INK))
    b.append(text(71, y + 66, "① 第 2 行 FAIL、第 3 行 PASS：被测实现没变，只把 golden 对齐输入约定，判定就翻转 ——", 13.5, INK))
    b.append(text(71, y + 86, "② 第 1 行 819 格 vs 第 4 行 1 格：ULP 数值只能在同一 dtype 刻度内比较；", 13.5, INK))
    b.append(text(71, y + 106, "③ 第 7 行：abs 极小但 rel=19%、ULP 巨大 —— 近零区三把尺子打架，atol 说了算。", 13.5, INK))
    return svg_doc(960, y + 128, "".join(b))


# ---------------------------------------------------------------------------

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    figs = {
        "01-overview.svg": fig1(),
        "02-metrics.svg": fig2(),
        "03-ulp.svg": fig3(),
        "04-verdicts.svg": fig4(),
    }
    for name, content in figs.items():
        path = OUT / name
        path.write_text(content, encoding="utf-8")
        print(f"写入 {path}（{path.stat().st_size} 字节）")


if __name__ == "__main__":
    main()
