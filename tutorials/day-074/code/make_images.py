#!/usr/bin/env python3
"""make_images.py —— 第 74 天（合法性与收益性分离）教程的四张手绘 sketch 风 SVG 信息图。

风格约定（与第 71–73 天一致，Excalidraw-like）：
  - 背景 #fdfaf2（米白），盒子白底 + 深灰 #6b6357 手绘描边
  - 强调色不超过 4 种柔和色：蓝 #4a7fa5 / 橙 #a8772e / 绿 #5a8a5a / 红 #b0605a
  - 线条带轻微抖动（L 段折线），圆头笔触，线宽 2 左右
  - 手写感字体栈：Comic Sans MS / Comic Neue / Kaiti SC / 楷体 / cursive
  - 只用矩形、格子、箭头、圆角框等简单几何形状

图中全部数字来自 2026-11-12 的真实运行（code/outputs/）：
  fusion_gate_lab 31/31；test_fusion_gate 32/32；
  接口：can_fuse(c) / should_fuse(c, m) / decide(leg, prof, policy)
  贯穿示例（2,3)@(3,2)+D→relu）：P1=P2 ΔB 32 B、P3 64 B，P3 活集 272 B；
  tile 扫描（M=N=2048, K=64，ΔB 恒 64 MiB）：
    32→4,352 B / 64→16,640 B / 128→65,792 B(reg+sram) / 256→262,400 B(spill 256)
    / 2048→16,777,472 B(spill 16,515,328，net 34,078,208=50.8%)；
    conservative fuse/fuse/fuse/refuse/refuse；auto、force 全 fuse；
  MM→MM（tile 128）：K1=64/256/1024/4096 活集 98,304/196,608/589,824/2,162,880 B，
    兑现 100/100/37.5/9.4%，净收益封顶 6 MiB，四档全合法；
  多使用者：keep E 合法净 48 B；删 E 非法（L4）；
  动态维度：合法但 known=False → 非 force 一律拒绝；
  决策日志共 11 行。

运行：python3 make_images.py   （在 code/ 目录下，输出到 ../images/）
"""

from __future__ import annotations

import math
import random
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "images"
OUT.mkdir(parents=True, exist_ok=True)

FONT = ("Comic Sans MS, Comic Neue, Segoe Print, Kaiti SC, KaiTi, 楷体, "
        "cursive")
INK = "#3b352d"
MUTED = "#84796a"
STROKE = "#6b6357"
BG = "#fdfaf2"
BLUE, ORANGE, GREEN, RED = "#4a7fa5", "#a8772e", "#5a8a5a", "#b0605a"
TINT = {"blue": "#eef3f7", "orange": "#f8f0e2", "green": "#edf4ee",
        "red": "#f7ecea", "white": "#ffffff", "gray": "#f1efe9"}

rng = random.Random(74)


def esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;")
              .replace(">", "&gt;"))


def tw(s: str, size: float) -> float:
    """粗略的字宽估算：CJK 约 1×size，ASCII 约 0.55×size。"""
    return sum(size if ord(c) > 0x2E80 else size * 0.55 for c in s)


def txt(x, y, s, size=12, fill=INK, anchor="start", bold=False,
        opacity=1.0):
    w = 'font-weight="bold"' if bold else 'font-weight="normal"'
    return (f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" '
            f'fill="{fill}" text-anchor="{anchor}" opacity="{opacity}" '
            f'{w}>{esc(s)}</text>')


def sketch_rect(x, y, w, h, fill="#ffffff", stroke=STROKE, sw=2.2, nseg=6):
    pts = []

    def seg(x0, y0, x1, y1):
        for i in range(nseg + 1):
            t = i / nseg
            jx = rng.uniform(-1.2, 1.2) if 0 < i < nseg else 0
            jy = rng.uniform(-1.2, 1.2) if 0 < i < nseg else 0
            pts.append((x0 + (x1 - x0) * t + jx, y0 + (y1 - y0) * t + jy))

    seg(x, y, x + w, y)
    seg(x + w, y, x + w, y + h)
    seg(x + w, y + h, x, y + h)
    seg(x, y + h, x, y)
    d = f"M {pts[0][0]:.1f},{pts[0][1]:.1f} " + " ".join(
        f"L {px:.1f},{py:.1f}" for px, py in pts[1:])
    return (f'<path d="{d}" fill="{fill}" stroke="{stroke}" '
            f'stroke-width="{sw}" stroke-linecap="round" '
            f'stroke-linejoin="round"/>')


def sketch_line(x0, y0, x1, y1, stroke=STROKE, sw=2.0, arrow=False,
                opacity=1.0, dashed=False):
    if dashed:
        main = (f'<path d="M {x0:.1f},{y0:.1f} L {x1:.1f},{y1:.1f}" '
                f'fill="none" stroke="{stroke}" stroke-width="{sw}" '
                f'stroke-linecap="round" stroke-dasharray="7 6" '
                f'opacity="{opacity}"/>')
    else:
        main = (f'<path d="M {x0:.1f},{y0:.1f} L {x1:.1f},{y1:.1f}" '
                f'fill="none" stroke="{stroke}" stroke-width="{sw}" '
                f'stroke-linecap="round" stroke-linejoin="round" '
                f'opacity="{opacity}"/>')
    out = [main]
    if arrow:
        ang = math.atan2(y1 - y0, x1 - x0)
        L, A = 11, 0.5
        ax, ay = x1 - L * math.cos(ang), y1 - L * math.sin(ang)
        out.append(f'<path d="M {x1:.1f},{y1:.1f} L {ax:.1f},{ay - 4:.1f}" '
                   f'fill="none" stroke="{stroke}" stroke-width="{sw}" '
                   f'stroke-linecap="round" opacity="{opacity}"/>')
        out.append(f'<path d="M {x1:.1f},{y1:.1f} L {ax:.1f},{ay + 4:.1f}" '
                   f'fill="none" stroke="{stroke}" stroke-width="{sw}" '
                   f'stroke-linecap="round" opacity="{opacity}"/>')
    return "".join(out)


def dot(x, y, r=5, fill=INK, stroke=STROKE):
    return (f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="1.8"/>')


def header(w, h, title, sub):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" '
            f'height="{h}" viewBox="0 0 {w} {h}">\n'
            f'<rect width="{w}" height="{h}" fill="{BG}"/>\n'
            + txt(40, 38, title, 20, INK, bold=True) + "\n"
            + txt(40, 61, sub, 12, MUTED) + "\n")


def save(name: str, body: str) -> None:
    path = OUT / name
    path.write_text(body + "</svg>\n", encoding="utf-8")
    print(f"wrote {path} ({path.stat().st_size} bytes)")


def panel_title(x, y, s, color=INK):
    return txt(x, y, s, 14, color, bold=True)


def badge(x, y, s, color, size=11.5, h=22, fill=None):
    w = tw(s, size) + 16
    return (sketch_rect(x, y, w, h, fill=fill or TINT["white"], stroke=color,
                        sw=1.8, nseg=4)
            + txt(x + w / 2, y + h - 7, s, size, color, anchor="middle",
                  bold=True))


# ============================================================
# 图 1：全貌
# ============================================================

def fig1() -> None:
    w, h = 1180, 840
    b = [header(w, h, "第 74 天全貌：合法性与收益性分离",
                 "第 11 周「融合收益与代价模型」第四天 —— 把「能否融合」和"
                 "「是否值得融合」拆成两个函数＋一个策略 ｜ "
                 "图中数字均为 2026-11-12 本机实测")]

    # ---- 顶部：阶段进度条 ----
    b.append(txt(40, 92, "学习计划位置（24 周 / 168 天）", 13, MUTED, bold=True))
    stages = [
        ("W1–4", "C++/IR/基础 Pass", False),
        ("W5–8", "MLIR/融合", False),
        ("W9–10", "Shape/Layout/图优化", False),
        ("W11", "融合收益与代价 ← 今天", True),
        ("W12", "数值精度与量化", False),
        ("W13–16", "Lowering/Tiling/调优", False),
        ("W17–24", "端到端与收口", False),
    ]
    bx, by, bw, bh, gap = 40, 100, 152, 50, 8
    for i, (rng_, theme, cur) in enumerate(stages):
        x = bx + i * (bw + gap)
        fill = TINT["orange"] if cur else TINT["gray"]
        b.append(sketch_rect(x, by, bw, bh, fill=fill,
                             stroke=ORANGE if cur else STROKE,
                             sw=2.6 if cur else 2.0))
        b.append(txt(x + bw / 2, by + 20, rng_, 12,
                     ORANGE if cur else MUTED, anchor="middle", bold=True))
        b.append(txt(x + bw / 2, by + 38, theme, 10.5,
                     INK if cur else MUTED, anchor="middle", bold=cur))

    # ---- 中排：本周七天 ----
    b.append(txt(40, 178, "本周链路（第 11 周：融合收益与代价模型）", 13, MUTED,
                 bold=True))
    days = [("D71", "计算量与访存量"), ("D72", "融合减少的流量"),
             ("D73", "融合的资源代价"), ("D74", "合法/收益分离 ←"),
             ("D75", "构造不融合案例"), ("D76", "简单 Cost Model"),
             ("D77", "复盘")]
    dx, dy, dw, dh = 40, 186, 152, 46
    for i, (d, t) in enumerate(days):
        x = dx + i * (dw + 8)
        cur = i == 3
        b.append(sketch_rect(x, dy, dw, dh,
                             fill=TINT["orange"] if cur else TINT["white"],
                             stroke=ORANGE if cur else STROKE,
                             sw=2.6 if cur else 1.8))
        b.append(txt(x + dw / 2, dy + 19, d, 12,
                     ORANGE if cur else INK, anchor="middle", bold=True))
        b.append(txt(x + dw / 2, dy + 36, t, 10.5, INK, anchor="middle"))
    b.append(sketch_line(40 + 7 * (dw + 8) - 4, dy + dh / 2, 1140,
                         dy + dh / 2, stroke=MUTED, sw=1.6, dashed=True))

    # ---- 盒 1：昨天留下的裂缝 ----
    x, y, bw2, bh2 = 40, 258, 552, 240
    b.append(sketch_rect(x, y, bw2, bh2, fill=TINT["white"], stroke=RED,
                         sw=2.4))
    b.append(txt(x + 14, y + 24, "① 昨天的反例今天必须接住", 13, RED, bold=True))
    b.append(txt(x + 14, y + 50, "D73 结尾：MatMul→MatMul 融合「合法」，"
                 "K1=4096 时兑现率只剩 9.4%", 11.5, INK))
    b.append(txt(x + 14, y + 72, "但 D50/52 的融合 Pattern 是「匹配上就替换」——"
                 "只回答能否，不回答值得", 11.5, ORANGE, bold=True))
    b.append(sketch_rect(x + 14, y + 88, 524, 74, fill=TINT["red"],
                         stroke=RED, sw=2.0, nseg=8))
    b.append(txt(x + 276, y + 112, "两层问题被塞在一个 Pattern 里：", 12.5, INK,
                 anchor="middle", bold=True))
    b.append(txt(x + 276, y + 134, "① 结构上能不能融合（改图，语义问题）",
                 11, INK, anchor="middle"))
    b.append(txt(x + 276, y + 152, "② 账本上值不值得融合（选图，策略问题）",
                 11, INK, anchor="middle"))
    b.append(txt(x + 14, y + 186, "而且 Pattern 手里没有机器卡、Shape 和 tile——"
                 "收益判断需要的信息它拿不到", 11, GREEN, bold=True))
    b.append(txt(x + 14, y + 208, "合并在一起的后果：换策略 = 改 Pattern = "
                 "重跑全部结构测试", 11.5, INK))

    # ---- 盒 2：今天的门 ----
    x, y = 612, 258
    b.append(sketch_rect(x, y, 528, 240, fill=TINT["white"], stroke=GREEN,
                         sw=2.4))
    b.append(txt(x + 14, y + 24, "② 今天的解法：一个候选过三道独立的门", 13,
                 GREEN, bold=True))
    rows = [
        ("can_fuse(c)", "能否融合：只读结构/语义（L1–L5），不读机器", BLUE),
        ("should_fuse(c, m)", "值不值得：D72 的 ΔB＋D73 的资源账（机器卡）",
         ORANGE),
        ("decide(leg, prof, policy)", "策略：conservative（默认）/auto/force，"
         "只读报告", GREEN),
    ]
    for i, (sig, desc, color) in enumerate(rows):
        yy = y + 52 + i * 56
        b.append(badge(x + 14, yy - 17, sig, color, size=10.5, h=21))
        b.append(txt(x + 22, yy + 24, desc, 10.8, INK))
        if i < 2:
            b.append(sketch_line(x + 250, yy + 6, x + 250, yy + 34,
                                 stroke=MUTED, sw=1.6, arrow=True))
    b.append(txt(x + 14, y + 220, "接口边界落在签名上（inspect 可查）："
                 "换策略不动前两层", 11, GREEN, bold=True))

    # ---- 盒 3：三个真实结论 ----
    x, y, bw2, bh2 = 40, 522, 552, 184
    b.append(sketch_rect(x, y, bw2, bh2, fill=TINT["white"], stroke=ORANGE,
                         sw=2.4))
    b.append(txt(x + 14, y + 24, "③ 三个决策结论（全部真实运行）", 13, ORANGE,
                 bold=True))
    b.append(txt(x + 14, y + 50, "P3(2048²,K=64) tile=2048：合法，净收益（下界）"
                 "+32.5 MiB，但 spill", 11.5, INK))
    b.append(txt(x + 14, y + 70, "  → conservative 拒绝、auto 接受：同一个候选，"
                 "策略不同答案不同", 11, RED, bold=True))
    b.append(txt(x + 14, y + 96, "MM→MM K1=4096：合法，下界净收益 +6 MiB，"
                 "保守门拒绝（spill>0）", 11.5, INK))
    b.append(txt(x + 14, y + 116, "  → auto 门放行：「把 6 MiB 留在桌上」"
                 "是保守策略的代价", 11, RED, bold=True))
    b.append(txt(x + 14, y + 142, "动态维度：合法性通过（-1 通配），但收益层"
                 " known=False", 11.5, INK))
    b.append(txt(x + 14, y + 162, "  → 非 force 一律拒绝；D62 特化成静态 Shape"
                 " 后重新进门", 11, RED, bold=True))

    # ---- 盒 4：输出去向 ----
    x, y = 612, 522
    b.append(sketch_rect(x, y, 528, 184, fill=TINT["white"], stroke=BLUE,
                         sw=2.4))
    b.append(txt(x + 14, y + 24, "④ 这张门交给谁（本周后半程）", 13, BLUE,
                 bold=True))
    b.append(txt(x + 14, y + 50, "D75 构造不融合案例：六类合法性负例＋"
                 "资源超限负例的来源", 11.5, INK))
    b.append(txt(x + 14, y + 70, "  就是今天 can_fuse 拦下的那批（L1–L5）",
                 11, MUTED))
    b.append(txt(x + 14, y + 96, "D76 Cost Model v0.1：只替换第三层策略——"
                 "前两层接口不动", 11.5, INK))
    b.append(txt(x + 14, y + 116, "  今天的 decide(leg, prof, policy) 就是它的插槽",
                 11, MUTED))
    b.append(txt(x + 14, y + 148, "今天的产出：三层门接口＋决策日志 11 行＋"
                 "假设清单 B1–B8", 11.5, GREEN, bold=True))

    # ---- 底部徽标 ----
    badges = [("主实验 31/31", GREEN), ("验收测试 32/32", GREEN),
              ("产出：收益判断接口＋决策日志", ORANGE),
              ("4 张图全部真实数字", BLUE)]
    bx3 = 40
    for s, c in badges:
        b.append(badge(bx3, 748, s, c))
        bx3 += tw(s, 11.5) + 34

    b.append(txt(40, 806, "运行入口：code/run_all.sh（主实验 → 独立测试 → "
                "重新生成本组图片）", 11, MUTED))
    save("01-overview.svg", "".join(b))


# ============================================================
# 图 2：核心机制（三层门的接口边界）
# ============================================================

def fig2() -> None:
    w, h = 1180, 830
    b = [header(w, h, "核心机制：一个候选过三道门——每道门只读自己该读的东西",
                 "左：三层门与数据流（接口边界）｜右：第一层门的五条规则与"
                 "六个真实负例 ｜ 图中数字均为真实运行")]

    # ================= 左：三层门数据流 =================
    b.append(panel_title(40, 100, "三层门：报告是唯一交流语言", BLUE))

    # 候选卡
    b.append(sketch_rect(60, 130, 470, 64, fill=TINT["gray"], stroke=STROKE,
                         sw=2.2))
    b.append(txt(295, 155, "FusionCandidate（融合候选）", 12.5, INK,
                 anchor="middle", bold=True))
    b.append(txt(295, 178, "ops 算子链 · intermediates 使用者关系 · "
                 "workload · tile", 10.5, MUTED, anchor="middle"))

    # 门 1
    b.append(sketch_line(295, 196, 295, 224, stroke=MUTED, sw=2.0, arrow=True))
    b.append(sketch_rect(60, 228, 470, 108, fill=TINT["blue"], stroke=BLUE,
                         sw=2.6))
    b.append(txt(295, 252, "第 1 层 can_fuse(c) → LegalityReport", 13, BLUE,
                 anchor="middle", bold=True))
    b.append(txt(295, 274, "能否融合：纯结构/语义问题", 11.5, INK,
                 anchor="middle", bold=True))
    b.append(txt(295, 294, "只读：模式、纯度、Shape、dtype、使用者", 10.5,
                 INK, anchor="middle"))
    b.append(txt(295, 312, "不读：Machine、tile、字节数（签名里没有 m）", 10.5,
                 RED, anchor="middle", bold=True))

    # 报告 1
    b.append(sketch_line(295, 338, 295, 366, stroke=MUTED, sw=2.0, arrow=True))
    b.append(badge(160, 368, "LegalityReport：ok / 理由 L1–L5 / 模式名 / 保留集 / dynamic",
                   BLUE, size=10, h=24))

    # 门 2
    b.append(sketch_line(295, 396, 295, 424, stroke=MUTED, sw=2.0, arrow=True))
    b.append(sketch_rect(60, 428, 470, 118, fill=TINT["orange"], stroke=ORANGE,
                         sw=2.6))
    b.append(txt(295, 452, "第 2 层 should_fuse(c, m) → ProfitReport", 13,
                 ORANGE, anchor="middle", bold=True))
    b.append(txt(295, 474, "值不值得：账本问题（假设卡是唯一机器依据）", 11.5,
                 INK, anchor="middle", bold=True))
    b.append(txt(295, 494, "ΔB（D72）＝Σ passes·elems·4 ＋ 资源账（D73）"
                 "→ 活集/落位/spill", 10.5, INK, anchor="middle"))
    b.append(txt(295, 514, "不重查结构（合法性上一层已把）；算不出 → known=False", 10.5,
                 INK, anchor="middle"))
    b.append(txt(295, 534, "贯穿示例：P3 ΔB 64 B、活集 272 B、零 spill → net 64 B",
                 10.5, GREEN, anchor="middle", bold=True))

    # 报告 2
    b.append(sketch_line(295, 548, 295, 576, stroke=MUTED, sw=2.0, arrow=True))
    b.append(badge(160, 578, "ProfitReport：known / ΔB / 活集 / spill / 净收益 / 兑现率",
                   ORANGE, size=10, h=24))

    # 门 3
    b.append(sketch_line(295, 606, 295, 634, stroke=MUTED, sw=2.0, arrow=True))
    b.append(sketch_rect(60, 638, 470, 96, fill=TINT["green"], stroke=GREEN,
                         sw=2.6))
    b.append(txt(295, 662, "第 3 层 decide(leg, prof, policy) → Decision", 13,
                 GREEN, anchor="middle", bold=True))
    b.append(txt(295, 684, "策略层：只读两份报告——签名里没有候选 c", 11.5, INK,
                 anchor="middle", bold=True))
    b.append(txt(295, 704, "conservative：拒 spill>0 与收益未知（默认）｜auto：只看 net>0", 10.5,
                 INK, anchor="middle"))
    b.append(txt(295, 722, "force：只看合法性（A/B 实验用）", 10.5, INK,
                 anchor="middle"))

    # 出口
    b.append(sketch_line(295, 736, 295, 764, stroke=MUTED, sw=2.0, arrow=True))
    b.append(badge(150, 766, "Decision：fuse / refuse ＋ 理由 ＋ hint（出口）",
                   GREEN, size=10, h=24))
    b.append(txt(60, 814, "拒绝 ≠ 报错：refuse = 回到恒可用的基线（不融合，net=0），"
                "hint 指出下一步出口", 10.5, MUTED))

    # ================= 右：第一层门规则 + 负例 =================
    b.append(panel_title(620, 100, "第一层门的五条规则与六个真实负例", GREEN))
    rules = [
        ("L1", "模式在支持列表里（D50 融合算子＋1 个实验模式）", BLUE),
        ("L2", "组内算子纯（无副作用，D25 口径）", BLUE),
        ("L3", "Shape 规则（D39/D40 Verifier 子集；-1 未知通配）", BLUE),
        ("L4", "中间使用者（D52：组外有人必须 kept）", BLUE),
        ("L5", "dtype 在支持集（今天只有 fp32）", BLUE),
    ]
    yy = 122
    for tag, desc, color in rules:
        b.append(badge(628, yy - 14, tag, color, size=11, h=20))
        b.append(txt(680, yy + 1, desc, 10.8, INK))
        yy += 30
    b.append(txt(628, yy + 10, "→ 合法性报告 = 正/负结论＋可定位的规则号"
                "（D75 负例来源）", 10.5, MUTED))

    # 负例表（真实运行结果）
    ty = yy + 34
    b.append(txt(628, ty, "六个负例全部被拦（主实验 §2 真实输出）：", 11.5,
                 INK, bold=True))
    negs = [
        ("Relu→MatMul", "False", "L1 模式不支持"),
        ("副作用 add", "False", "L2 不纯"),
        ("Shape 不一致", "False", "L3 逐元素形状不齐"),
        ("int8 全链", "False", "L5 dtype 暂不支持"),
        ("偷走 E（删中间）", "False", "L4 组外使用者没人喂"),
        ("无使用者的 C", "False", "L4 死代码不当候选"),
    ]
    ry = ty + 24
    for name, res, why in negs:
        b.append(txt(636, ry, name, 10.8, INK))
        b.append(txt(796, ry, res, 10.8, RED, bold=True))
        b.append(txt(846, ry, why, 10.8, MUTED))
        b.append(sketch_line(632, ry + 6, 1120, ry + 6, stroke=TINT["gray"],
                             sw=1.0, opacity=0.9))
        ry += 24
    b.append(txt(628, ry + 16, "P1/P2/P3 三种合法形式全过第一层；P2 保留 E 落盘"
                "（kept）——第二层", 10.5, INK))
    b.append(txt(628, ry + 36, "给它记 ΔB=48 B（C 两趟 32＋E 一趟 16，"
                "D72 §5 口径）", 10.5, INK))
    save("02-mechanism.svg", "".join(b))


# ============================================================
# 图 3：实例对照（决策矩阵——同一候选 × 三种策略）
# ============================================================

def fig3() -> None:
    w, h = 1180, 800
    b = [header(w, h, "实例对照：合法 ≠ 值得——策略让同一个候选有三种答案",
                 "数据来自 code/outputs/fusion_gate_lab.txt 第 4、5 节真实运行"
                 "（P3：M=N=2048, K=64，ΔB 恒 64 MiB；MM→MM：tile 128）")]

    # ================= 上：tile 扫描 × 三策略 =================
    b.append(panel_title(40, 100, "P3 × 5 档 tile × 3 种策略（今天的核心表）",
                         BLUE))
    cols = [("tile", 70), ("活集", 140), ("落位", 250), ("spill", 330),
            ("净收益(下界)", 400), ("conservative", 510), ("auto", 660),
            ("force", 760)]
    ty = 126
    for name, cxx in cols:
        b.append(txt(cxx, ty, name, 11, MUTED, bold=True))
    b.append(sketch_line(60, ty + 8, 850, ty + 8, stroke=MUTED, sw=1.2))
    rows = [
        ("32", "4,352 B", "reg", "0 B", "67,108,864 B",
         "fuse", "fuse", "fuse", False),
        ("64", "16,640 B", "reg", "0 B", "67,108,864 B",
         "fuse", "fuse", "fuse", False),
        ("128", "65,792 B", "reg+sram", "0 B", "67,108,864 B",
         "fuse", "fuse", "fuse", False),
        ("256", "262,400 B", "spill", "256 B", "67,108,352 B",
         "refuse", "fuse", "fuse", True),
        ("2048", "16,777,472 B", "spill", "16,515,328 B", "34,078,208 B",
         "refuse", "fuse", "fuse", True),
    ]
    ry = ty + 28
    for tile, live, place, spill, net, c1, c2, c3, hot in rows:
        emph = hot
        base = RED if hot else INK
        b.append(txt(70, ry, tile, 11.5, base, bold=emph))
        b.append(txt(140, ry, live, 11, base))
        b.append(txt(250, ry, place, 11, base))
        b.append(txt(330, ry, spill, 11, base))
        b.append(txt(400, ry, net, 10.5, base))
        b.append(badge(510, ry - 17, c1,
                       GREEN if c1 == "fuse" else RED, size=10.5, h=20))
        b.append(badge(660, ry - 17, c2,
                       GREEN if c2 == "fuse" else RED, size=10.5, h=20))
        b.append(badge(760, ry - 17, c3,
                       GREEN if c3 == "fuse" else RED, size=10.5, h=20))
        ry += 30
    b.append(txt(70, ry + 6, "conservative 只收零 spill（32/64/128 融，256/2048 拒）；"
                "auto 五档全收（net>0）；force 只看合法性。", 11, MUTED))
    b.append(txt(70, ry + 26, "2048 的拒绝不是终局：hint 说「先缩小 tile 再重试」，"
                "64 就能过门——拒绝带出口。", 11, ORANGE, bold=True))

    # ================= 下左：MM→MM K1 扫描 =================
    b.append(panel_title(40, ry + 60, "MM→MM（tile 128）：四档全合法，值得与否"
                         "随 K1 变", GREEN))
    ty2 = ry + 86
    cols2 = [("K1", 70), ("活集", 130), ("落位", 240), ("ΔB", 320),
             ("净收益", 400), ("兑现率", 480), ("conservative", 550)]
    for name, cxx in cols2:
        b.append(txt(cxx, ty2, name, 11, MUTED, bold=True))
    b.append(sketch_line(60, ty2 + 8, 760, ty2 + 8, stroke=MUTED, sw=1.2))
    rows2 = [
        ("64", "98,304 B", "reg+sram", "1 MiB", "1 MiB", "100.0%", "fuse",
         False),
        ("256", "196,608 B", "reg+sram", "4 MiB", "4 MiB", "100.0%", "fuse",
         False),
        ("1024", "589,824 B", "spill", "16 MiB", "6 MiB", "37.5%", "refuse",
         True),
        ("4096", "2,162,688 B", "spill", "64 MiB", "6 MiB", "9.4%", "refuse",
         True),
    ]
    ry2 = ty2 + 28
    for k1, live, place, db, net, rate, act, hot in rows2:
        base = RED if hot else INK
        b.append(txt(70, ry2, k1, 11.5, base, bold=hot))
        b.append(txt(130, ry2, live, 11, base))
        b.append(txt(240, ry2, place, 11, base))
        b.append(txt(320, ry2, db, 11, base))
        b.append(txt(400, ry2, net, 11, base, bold=hot))
        b.append(txt(480, ry2, rate, 11, ORANGE, bold=True))
        b.append(badge(550, ry2 - 17, act,
                       GREEN if act == "fuse" else RED, size=10.5, h=20))
        ry2 += 30
    b.append(txt(70, ry2 + 6, "四档全部合法（合法性不读机器卡：与 K1 无关）；"
                "K1=1024/4096 spill>0 → 保守门拒绝，", 11, MUTED))
    b.append(txt(70, ry2 + 26, "但下界净收益同为 6 MiB——auto 门放行："
                "「把 6 MiB 留在桌上」是保守的代价（D75/D76 再细化）", 11,
                RED, bold=True))

    # ================= 下右：三句话卡 =================
    x, y = 810, ry + 60
    b.append(sketch_rect(x, y, 330, 300, fill=TINT["white"], stroke=BLUE,
                         sw=2.2))
    b.append(txt(x + 14, y + 24, "读这两张表的三句话", 12.5, BLUE, bold=True))
    lines = [
        ("1  拒绝理由能分清层次：", INK, True),
        ("   非法 →「合法性：L4…」", RED, False),
        ("   不值 →「保守策略：spill…」", ORANGE, False),
        ("   （检查 4d/5e 验证归属）", MUTED, False),
        ("2  合法性过滤非法形式，", INK, True),
        ("   收益性排序合法形式：", INK, True),
        ("   B(48B) > 基线(0) > C(非法)", GREEN, False),
        ("3  收益未知 ≠ 收益为负：", INK, True),
        ("   动态维度 known=False", INK, False),
        ("   → 非 force 一律拒绝", RED, False),
        ("   → hint：D62 特化再进门", MUTED, False),
    ]
    yy = y + 50
    for s, color, bold_ in lines:
        b.append(txt(x + 14, yy, s, 10.8, color, bold=bold_))
        yy += 24
    b.append(txt(x, y + 330 - 16, "拒绝 = 回到基线（恒合法），不是报错", 10.5,
                 MUTED, anchor="start"))
    save("03-comparison.svg", "".join(b))


# ============================================================
# 图 4：决策日志（11 行真实记录，理由归属可视化）
# ============================================================

def fig4() -> None:
    w, h = 1180, 830
    b = [header(w, h, "第二份产出：决策日志——每行一个候选的完整判决书",
                 "数据来自 code/outputs/fusion_gate_lab.txt 第 8 节真实运行"
                 "（11 行，conservative 策略）｜ 理由前缀标明归属层次")]

    b.append(panel_title(40, 100, "决策日志（D75 负例库与 D76 Cost Model 的输入）",
                         ORANGE))
    # 列头
    cols = [("候选", 66), ("策略", 250), ("合法", 372), ("净收益", 434),
            ("动作", 570), ("理由（截选，前缀＝归属层次）", 640)]
    ty = 128
    for name, cxx in cols:
        b.append(txt(cxx, ty, name, 11, MUTED, bold=True))
    b.append(sketch_line(56, ty + 8, 1140, ty + 8, stroke=MUTED, sw=1.2))

    log = [
        ("P3 tile=32", "conservative", "True", "67,108,864", "fuse",
         "合法性通过；净收益 > 0 且零 spill（落位 reg）", GREEN),
        ("P3 tile=64", "conservative", "True", "67,108,864", "fuse",
         "合法性通过；净收益 > 0 且零 spill（落位 reg）", GREEN),
        ("P3 tile=128", "conservative", "True", "67,108,864", "fuse",
         "合法性通过；零 spill（落位 reg+sram 不设门）", GREEN),
        ("P3 tile=256", "conservative", "True", "67,108,352", "refuse",
         "保守策略：spill 256 B > 0（D73 阶梯第 3 级）", RED),
        ("P3 tile=2048", "conservative", "True", "34,078,208", "refuse",
         "保守策略：spill 16,515,328 B > 0（下界 50.8%）", RED),
        ("MM→MM K1=64", "conservative", "True", "1,048,576", "fuse",
         "合法性通过；净收益 > 0 且零 spill", GREEN),
        ("MM→MM K1=256", "conservative", "True", "4,194,304", "fuse",
         "合法性通过；净收益 > 0 且零 spill", GREEN),
        ("MM→MM K1=1024", "conservative", "True", "6,291,456", "refuse",
         "保守策略：spill 327,680 B > 0（下界仍 +6 MiB）", RED),
        ("MM→MM K1=4096", "conservative", "True", "6,291,456", "refuse",
         "保守策略：spill 1,900,544 B > 0（兑现率仅 9.4%）", RED),
        ("B: 融合但保留 E", "conservative", "True", "48", "fuse",
         "合法性通过；ΔB 48 B = C 两趟＋E 一趟（D72 §5）", GREEN),
        ("C: 融合并删除 E", "conservative", "False", "—", "refuse",
         "合法性：L4 组外使用者没人喂（D52）", RED),
    ]
    ry = ty + 26
    for name, pol, legal, net, act, why, color in log:
        hot = act == "refuse"
        if hot:
            b.append(sketch_rect(56, ry - 17, 1086, 24,
                                 fill=TINT["red"] if legal == "True"
                                 else TINT["gray"],
                                 stroke=STROKE, sw=1.0, nseg=4))
        b.append(txt(66, ry, name, 11, INK, bold=True))
        b.append(txt(250, ry, pol, 10.5, MUTED))
        b.append(txt(372, ry, legal, 10.5, GREEN if legal == "True" else RED,
                     bold=True))
        b.append(txt(434, ry, net + " B" if net != "—" else "—", 10.5, INK))
        b.append(badge(570, ry - 16, act, GREEN if act == "fuse" else RED,
                       size=10, h=19))
        b.append(txt(640, ry, why, 10.3, color if hot else INK))
        ry += 26

    b.append(txt(56, ry + 10, "读法：前 9 行全部「合法」，动作却分两半——"
                "拒绝理由都以「保守策略：」开头（收益层）；", 11, INK))
    b.append(txt(66, ry + 30, "最后一行以「合法性：」开头（结构层）。理由归属"
                "可机检：D8 检查用前缀断言。", 11, INK))
    b.append(txt(66, ry + 50, "每一行 refuse 都带 hint（先缩小 tile / 先修结构 /"
                " 特化再进门）——拒绝带出口。", 11, ORANGE, bold=True))

    # 底部：三策略速查卡
    y0 = ry + 76
    b.append(panel_title(40, y0, "策略速查（第三层可整体替换，前两层不动）",
                         BLUE))
    cards = [
        ("conservative（默认）", "拒 spill>0 ＋ 收益未知；只收零 spill 且 net>0",
         "理由＝保守策略：… ｜ 拒绝回到基线", GREEN),
        ("auto", "只看净收益（下界）> 0，敢赌下界成本",
         "2048/4096 也放行：把 6 MiB 留在桌上的是它不是它——是保守", ORANGE),
        ("force", "只看合法性（A/B 实验用），不能越过非法",
         "删 E 的候选在 force 下仍拒（检查 D5）", RED),
    ]
    for i, (name, rule, note, color) in enumerate(cards):
        x = 56 + i * 366
        b.append(sketch_rect(x, y0 + 14, 348, 118, fill=TINT["white"],
                             stroke=color, sw=2.0))
        b.append(txt(x + 14, y0 + 38, name, 11.5, color, bold=True))
        b.append(txt(x + 14, y0 + 62, rule, 10, INK))
        b.append(txt(x + 14, y0 + 88, note, 9.8, MUTED))
        if i < 2:
            b.append(sketch_line(x + 352, y0 + 70, x + 364, y0 + 70,
                                 stroke=MUTED, sw=1.6, arrow=True))
    b.append(txt(56, y0 + 158, "接口价值：策略是第三层的一块插拔件——D76 的 Cost "
                "Model v0.1 只换这层，can_fuse/should_fuse 与全部结构测试原样复用",
                 11, GREEN, bold=True))
    save("04-decision-log.svg", "".join(b))


if __name__ == "__main__":
    fig1()
    fig2()
    fig3()
    fig4()
    print("done.")
