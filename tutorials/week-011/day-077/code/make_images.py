#!/usr/bin/env python3
"""make_images.py —— 第 77 天（第 11 周复盘）教程的四张手绘 sketch 风 SVG 信息图。

风格约定（与第 71–76 天一致，Excalidraw-like）：
  - 背景 #fdfaf2（米白），盒子白底 + 深灰 #6b6357 手绘描边
  - 强调色不超过 4 种柔和色：蓝 #4a7fa5 / 橙 #a8772e / 绿 #5a8a5a / 红 #b0605a
  - 线条带轻微抖动（L 段折线），圆头笔触，线宽 2 左右
  - 手写感字体栈：Comic Sans MS / Comic Neue / Kaiti SC / 楷体 / cursive
  - 只用矩形、格子、箭头、圆角框等简单几何形状

图中全部数字来自 2026-11-13 的真实运行（code/outputs/）：
  主实验 week11_review 18/18；独立验收 test_week11_review 17/17；
  贯穿 Shape R4ctl MatMul(2048,64)@B(64,2048)→+D→relu tile=64：
    FLOPs 融合前后同为 545,259,520；
    流量 P0 101,711,872 = 任务 34,603,008 + 中间 67,108,864（=ΔB=D76 评分）；
    AI 5.36 → 15.76（平衡点 12.54，D71 口径）；
    活集 16,384 → 16,640 B（+256 B bias 在飞，epilogue 2/K=3.125%）；并发 4 → 3；
    tile 拧 128：评分不变、并发 1 → auto refuse；
  数值实弹：小链 F=[[0,65],[0,157]] 独立=融合；随机 12+8 组逐位全对；
    A5 关掉 L4 硬融：F 仍对、组外 G 读到 999 垃圾；
  三维巡检：16 例组合分布 8 非法 / 3 合法∧正确∧快 / 5 合法∧正确∧不快 / 0 合法∧不正确；
  本周检查数：D71 26+23、D72 25+16、D73 22+25、D74 31+32、D75 30+34、D76 31+33。

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

rng = random.Random(77)


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


def cell(x, y, w, h, s, color, size=10.5, tint=None):
    """矩阵/表格格子：底色 + 居中文字。"""
    return (sketch_rect(x, y, w, h, fill=tint or TINT["white"], stroke=color,
                        sw=1.6, nseg=4)
            + txt(x + w / 2, y + h / 2 + size * 0.36, s, size, color,
                  anchor="middle", bold=True))


def lines_txt(x, y, rows, size=11.5, fill=INK, gap=None, bold_first=False):
    """多行左对齐文字。"""
    gap = gap or size * 1.55
    out = []
    for i, s in enumerate(rows):
        out.append(txt(x, y + i * gap, s, size, fill,
                       bold=bold_first and i == 0))
    return "\n".join(out)


# ============================================================
# 图 1：全貌——第 11 周复盘在三张 certificate 上的位置
# ============================================================

def fig1() -> None:
    w, h = 1180, 900
    body = header(w, h, "第 77 天全貌：第 11 周复盘——「能融」「融了没错」「融了更快」是三张不同的 certificate",
                  "本周 D71–D76 造了账本、规则和报价机；今天把它们拆成三个独立维度，各配各的证据类型。数字全部来自本日真实运行。")

    # ---- 面板①：编译链路里的位置 ----
    body += panel_title(40, 108, "① 编译链路里的位置：本周全部工作住在「图优化」的收益判断层")
    pipe = [("前端图\n(mini-IR)", 44, 130, "gray"),
            ("验证 +\nShape 推导", 240, 116, "gray"),
            ("图优化：融合\n＋ Cost Model ★", 412, 152, "orange"),
            ("Lowering\n(D85→)", 630, 116, "gray"),
            ("LLVM /\n执行", 800, 100, "gray")]
    y0 = 122
    for label, x, bw, col in pipe:
        body += sketch_rect(x, y0, bw, 58, fill=TINT["white"] if col == "gray"
                            else TINT["orange"],
                            stroke={"gray": STROKE, "orange": ORANGE}[col],
                            sw=2.2 if col == "orange" else 1.8, nseg=5)
        body += txt(x + bw / 2, y0 + 25, label.split("\n")[0], 12,
                    INK if col == "gray" else ORANGE, anchor="middle", bold=True)
        body += txt(x + bw / 2, y0 + 43, label.split("\n")[1], 11,
                    MUTED if col == "gray" else ORANGE, anchor="middle")
    body += sketch_line(196, y0 + 29, 234, y0 + 29, arrow=True)
    body += sketch_line(362, y0 + 29, 406, y0 + 29, arrow=True)
    body += sketch_line(568, y0 + 29, 624, y0 + 29, arrow=True)
    body += sketch_line(752, y0 + 29, 794, y0 + 29, arrow=True)
    body += txt(920, y0 + 20, "★ 第 11 周在这里", 12, ORANGE, bold=True)
    body += txt(920, y0 + 38, "「值不值得融」的裁判席", 11, ORANGE)

    # ---- 面板②：本周时间线 ----
    body += panel_title(40, 232, "② 第 11 周时间线：前六天造零件，今天拆维度")
    days = [("D71", "计算量\n与访存量"), ("D72", "融合减少\n的流量 ΔB"),
            ("D73", "融合的\n资源代价"), ("D74", "合法性/收益\n性分离"),
            ("D75", "构造不\n融合案例"), ("D76", "Cost Model\nv0.1 集成"),
            ("D77", "三维复盘\n（今天）")]
    dx, dw, dy, dh = 44, 146, 246, 64
    for i, (d, topic) in enumerate(days):
        x = dx + i * (dw + 8)
        today = d == "D77"
        body += sketch_rect(x, dy, dw, dh, fill=TINT["orange"] if today
                            else TINT["white"],
                            stroke=ORANGE if today else STROKE,
                            sw=2.4 if today else 1.8, nseg=5)
        body += txt(x + dw / 2, dy + 22, d, 12.5,
                    ORANGE if today else MUTED, anchor="middle", bold=True)
        body += txt(x + dw / 2, dy + 40, topic.split("\n")[0], 10.5, INK,
                    anchor="middle")
        body += txt(x + dw / 2, dy + 54, topic.split("\n")[1], 10.5, INK,
                    anchor="middle")
        if i < 6:
            body += sketch_line(x + dw, dy + dh / 2, x + dw + 8, dy + dh / 2,
                                arrow=True, sw=1.6)

    # ---- 面板③：三张 certificate ----
    body += panel_title(40, 352, "③ 三张 certificate：三个问题、三种证据、三套工具")
    certs = [
        ("合法 legality", BLUE, "「这个改写本身说不说得通？」",
         ["证据：结构规则 L1–L6", "（模式/纯度/Shape/使用者/dtype/拓扑）",
          "工具：can_fuse（D74/D75）",
          "特点：不吃机器卡，与收益无关",
          "本周实弹：翼 A 8 例全被拦"],
         "失败方式：图换了规则就得重查"),
        ("正确 correctness", GREEN, "「算出来的数还对不对？」",
         ["证据：独立 vs 融合逐位对拍",
          "工具：数值执行器（D71/72＋今天补跑）",
          "本周实弹：小链＋随机 12＋8 组全对",
          "keep / recompute / MM→MM 三形式",
          "A5 事故：正确性是全图性质"],
         "边界：逐位相等依赖同一累加顺序（→D78）"),
        ("更快 profitability", ORANGE, "「值不值得做？」",
         ["证据：三本账 ＋ 三门槛",
          "评分 = ΔB − spill − 重读罚（字节）",
          "门槛：>0 ∧ 零 spill ∧ 并发≥3",
          "工具：CostModel v0.1（D76）",
          "本周实弹：16 例判决 8 拒 8 融"],
         "失败方式：模型误差四轴（参数/输入/口径/未计价）"),
    ]
    cy, cw, ch = 366, 352, 268
    for i, (name, col, q, rows, fail) in enumerate(certs):
        x = 44 + i * (cw + 12)
        body += sketch_rect(x, cy, cw, ch, fill=TINT["white"], stroke=col,
                            sw=2.4, nseg=6)
        body += badge(x + 12, cy + 12, name, col, size=12.5, h=24,
                      fill=TINT["white"])
        body += txt(x + 14, cy + 62, q, 12, INK, bold=True)
        body += lines_txt(x + 14, cy + 88, rows, size=10.8, gap=19.5)
        body += sketch_line(x + 12, cy + ch - 40, x + cw - 12, cy + ch - 40,
                            stroke=col, sw=1.2, dashed=True, opacity=0.7)
        body += txt(x + 14, cy + ch - 18, fail, 10.2, col)

    # ---- 面板④：16 例在三维空间的分布 ----
    body += panel_title(40, 678, "④ 本周 16 例案例库的三维落位：三个维度各自翻车，互不牵连")
    bar_y, bar_h = 694, 46
    total_w = 1096
    segs = [(8, RED, "不合法 8 例", "翼 A：连跑都不能跑"),
            (5, ORANGE, "合法∧正确∧不快 5 例", "R1/R1ctl/R2/R3重算/R4"),
            (3, GREEN, "合法∧正确∧快 3 例", "R2ctl/R3keep/R4ctl")]
    x = 44
    for n, col, label, sub in segs:
        seg_w = total_w * n / 16
        body += sketch_rect(x, bar_y, seg_w, bar_h, fill=TINT[
            {RED: "red", ORANGE: "orange", GREEN: "green"}[col]],
            stroke=col, sw=2.0, nseg=5)
        body += txt(x + seg_w / 2, bar_y + 19, label, 11.5, col,
                    anchor="middle", bold=True)
        body += txt(x + seg_w / 2, bar_y + 36, sub, 9.8, MUTED, anchor="middle")
        x += seg_w
    body += txt(44, bar_y + 74,
                "第 4 种组合「合法∧不正确」= 0 不是运气：L4/L3b 把会算错的图拦成了「非法」——"
                "合法性规则正是正确性的守门员（今天 §2g 用「关掉 L4」的数值事故证明了反面）。", 11, INK)
    body += txt(44, bar_y + 96,
                "对应明天预告：D78 浮点表示与累加误差——「正确」的下一层：本周的逐位相等依赖同样的计算顺序，顺序变了会怎样？", 11, MUTED)

    save("01-overview.svg", body)


# ============================================================
# 图 2：核心机制——三问三证据的验证链路与三条「不蕴含」
# ============================================================

def fig2() -> None:
    w, h = 1180, 930
    body = header(w, h, "第 77 天核心机制：三问三证据——每张 certificate 管一段验证链路",
                  "读法：三列泳道各管一问；底部三条「不蕴含」箭头是今天的主题——任何一列的证据都不能替另外两列背书。")

    lanes = [
        ("① 合法？", BLUE, "can_fuse（L1–L6）",
         ["输入：候选图（ops/中间/使用者）",
          "输出：ok + 理由（L 编号）",
          "机器卡：不吃（与收益无关）"],
         ["A5「偷走中间」：E 有 1 个组外使用者",
          "却想删——L4 拦下（D52 口径）",
          "A8 隐式 Reshape：(2,4)≠(4,2)，",
          "L3b 拦下（D75 新增规则）"],
         ["今天 §2g 反面实弹：故意关掉 L4 硬融，",
          "融合核自己的 F 仍正确，",
          "但组外 G 读到旧内存 999（垃圾）",
          "——合法性的边界正是正确性"]),
        ("② 正确？", GREEN, "独立 vs 融合逐位对拍",
         ["独立执行：3 kernel，中间落盘",
          "融合执行：1 kernel，寄存器直传",
          "判定：F 逐位相等（含中间值）"],
         ["小链 (2,3)@(3,2)：F=[[0,65],[0,157]]",
          "  与 D71 手算值逐位一致",
          "随机 12 组 ＋ 测试新种子 8 组全对",
          "keep/recompute/MM→MM 三形式过"],
         ["关键边界：对拍只证明「没算错」，",
          "不证明「图没被改坏」（A5 的组外",
          "读数对拍覆盖不到，靠 L4 守）",
          "浮点顺序问题 → 明天 D78 讲"]),
        ("③ 更快？", ORANGE, "CostModel v0.1：评分＋门槛",
         ["评分 = ΔB − spill − 重读罚（字节）",
          "门槛：>0 ∧ 零 spill ∧ 并发 ≥ 3",
          "模式：auto（默认）/ force（测量）"],
         ["R1ctl：评分 +6,291,456 B 为正，",
          "  spill 327,680 B 一票否决",
          "R4：评分 +67,108,864 B、零 spill，",
          "  并发 1 < 3 仍拒——数值全对也白搭"],
         ["拧 tile 64→128：评分一字不差，",
          "并发 3→1，auto fuse→refuse——",
          "只有这一列翻，另外两列纹丝不动",
          "（三维独立性的实弹，今天 §4）"]),
    ]
    lx, lw = 44, 352
    ly, lh = 96, 560
    tint_key = {BLUE: "blue", GREEN: "green", ORANGE: "orange"}
    for i, (title, col, tool, io_rows, demo_rows, edge_rows) in enumerate(lanes):
        x = lx + i * (lw + 12)
        body += sketch_rect(x, ly, lw, lh, fill=TINT["white"], stroke=col,
                            sw=2.4, nseg=6)
        body += badge(x + 12, ly + 12, title, col, size=13, h=25,
                      fill=TINT["white"])
        body += txt(x + 14, ly + 62, "工具：" + tool, 11.5, INK, bold=True)
        yy = ly + 86
        for sec, rows, scol in (("证据链路", io_rows, col),
                                ("本周实弹", demo_rows, col),
                                ("边界与失效", edge_rows, col)):
            body += sketch_rect(x + 10, yy, lw - 20, 24 + len(rows) * 17.5,
                                fill=TINT[tint_key[col]],
                                stroke=scol, sw=1.4, nseg=4)
            body += txt(x + 18, yy + 17, sec, 10.8, scol, bold=True)
            for j, r in enumerate(rows):
                body += txt(x + 18, yy + 35 + j * 17.5, r, 10.2, INK)
            yy += 24 + len(rows) * 17.5 + 12

    # ---- 底部：三条「不蕴含」 ----
    body += panel_title(40, 692, "④ 三条「不蕴含」：任何一张 certificate 都不能替另外两张背书")
    arrows = [
        (BLUE, GREEN, "合法 ⊬ 正确",
         "关掉 L4 的 A5：图「合法」了，组外 G 却读到 999——结构放行不等于数值安全"),
        (GREEN, ORANGE, "正确 ⊬ 更快",
         "R1ctl：数值逐位全对、评分 +6 MiB，auto 仍拒（spill 一票否决）"),
        (ORANGE, RED, "更快 ⊬ 实测时间",
         "评分单位是字节（省的 DRAM 流量），不是毫秒——折算时间要带宽，要实测（D76 误差口径轴）"),
    ]
    ay = 712
    for c1, c2, label, desc in arrows:
        body += sketch_rect(44, ay, 1096, 52, fill=TINT["white"], stroke=STROKE,
                            sw=1.8, nseg=5)
        body += badge(60, ay + 13, label, c2, size=11.5, h=24)
        body += txt(200, ay + 30, desc, 11.2, INK)
        ay += 62

    body += txt(44, ay + 10,
                "工程含义：验收清单要按列写——结构负例进 can_fuse 测试、数值进对拍测试、收益进 ground truth 回归；"
                "「跑通了」只覆盖中间一列。", 11.5, INK, bold=True)

    save("02-three-questions.svg", body)


# ============================================================
# 图 3：实例对照——一个 Shape 讲完三本账
# ============================================================

def fig3() -> None:
    w, h = 1180, 920
    body = header(w, h, "一个 Shape 讲完三本账：MatMul(2048,64)@B(64,2048) → +D(2048,2048) → relu，tile=64",
                  "这是 D75/D76 案例库的 R4ctl（auto 判 fuse 的那个）。三本账的变化方向各不相同——这正是「更快」要算净账的原因。数字为今日真实运行。")

    # ---- 顶部 Shape 盒 ----
    body += sketch_rect(44, 84, 1096, 44, fill=TINT["gray"], stroke=STROKE,
                        sw=1.8, nseg=5)
    body += txt(60, 111, "P0（不融合）= 3 个 kernel，中间 C、E 落盘 ｜ P3（全融合）= 1 个 kernel，"
               "寄存器直传 ｜ dtype fp32 ｜ 机器卡 toy-core v0（64 KiB reg / 192 KiB SRAM / 64 lanes）", 11.5, INK)

    # ---- 三栏账单 ----
    cols = [
        ("账一 · 计算量（D71）", BLUE,
         ["MatMul 2·M·N·K = 536,870,912", "Add ＝ 4,194,304",
          "Relu ＝ 4,194,304"],
         "P0 545,259,520 FLOPs", "P3 545,259,520 FLOPs",
         "＝ 不变",
         "融合不发明也不消灭计算；\n「更快」的收益全部来自\n流量与资源，不来自少算"),
        ("账二 · 流量（D72）", GREEN,
         ["任务流量（读A/B/D＋写F）", "  = 34,603,008 B",
          "中间两遍税 C、E 各写＋读", "  = 67,108,864 B（=ΔB）"],
         "P0 101,711,872 B", "P3 34,603,008 B",
         "−64 MiB（省 65.9%）",
         "AI：P0 5.36 → P3 15.76\nFLOP/B，越过平衡点 12.54\n（A100 FP32，D71 口径）——\n从访存受限翻进算力受限"),
        ("账三 · 资源（D73）", ORANGE,
         ["P0 峰值活集 = max(累加器", "  16,384，add 768，relu 512)",
          "P3 活集 = 累加器 16,384", "  ＋ bias 在飞 256"],
         "P0 活集 16,384 B", "P3 活集 16,640 B",
         "＋256 B（2/K = 3.125%）",
         "落位 reg → reg，零 spill；\n寄存器并发 4 → 3（−25%，\nD75 软代价：更快维里\n也有代价项"),
    ]
    cx, cw = 44, 352
    cy, ch = 148, 470
    for i, (title, col, detail, p0, p3, delta, note) in enumerate(cols):
        x = cx + i * (cw + 12)
        body += sketch_rect(x, cy, cw, ch, fill=TINT["white"], stroke=col,
                            sw=2.4, nseg=6)
        body += badge(x + 12, cy + 12, title, col, size=12, h=24,
                      fill=TINT["white"])
        yy = cy + 56
        for d in detail:
            body += txt(x + 16, yy, d, 10.8, INK)
            yy += 18
        yy += 10
        body += sketch_rect(x + 14, yy, cw - 28, 40, fill=TINT["gray"],
                            stroke=STROKE, sw=1.6, nseg=4)
        body += txt(x + 24, yy + 16, p0, 11.5, MUTED, bold=True)
        body += txt(x + 24, yy + 32, p3, 12.5, col, bold=True)
        yy += 52
        body += badge(x + 14, yy, delta, col, size=11.5, h=24)
        yy += 40
        for ln in note.split("\n"):
            body += txt(x + 16, yy, ln, 10.4, INK)
            yy += 16.5

    # ---- AI 对比条（账二内补充，画在第三块下方统一） ----
    body += panel_title(40, 646, "三账并排读：变化方向各不相同")
    body += sketch_rect(44, 660, 1096, 74, fill=TINT["white"], stroke=STROKE,
                        sw=1.8, nseg=5)
    tri = [("计算量", "545,259,520 → 545,259,520", "不变（＝）", BLUE),
           ("流量", "101,711,872 → 34,603,008 B", "−64 MiB", GREEN),
           ("资源", "16,384 → 16,640 B ／ 并发 4→3", "＋256 B", ORANGE)]
    for i, (name, nums, d, col) in enumerate(tri):
        x = 60 + i * 364
        body += txt(x, 684, name, 12, col, bold=True)
        body += txt(x, 702, nums, 11, INK)
        body += txt(x, 720, "变化：" + d, 11, col, bold=True)

    # ---- 底部：三维体检表 + 拧 tile ----
    body += panel_title(40, 766, "同一张图的三维体检表：拧一格 tile（64→128），只有「更快」列翻车")
    hdr_y = 780
    cols4 = [("候选", 300), ("合法?", 150), ("正确?", 300), ("更快?", 346)]
    x = 44
    for name, cwid in cols4:
        body += cell(x, hdr_y, cwid, 26, name, STROKE, size=11.5,
                     tint=TINT["gray"])
        x += cwid
    rows4 = [
        ("tile=64（R4ctl）", "合法 ✓", "正确 ✓（对拍全过）",
         "快：fuse（评分 67,108,864 B，并发 3）", GREEN),
        ("tile=128（R4）", "合法 ✓（没变）", "正确 ✓（数值执行器看不见 tile）",
         "不快：refuse（评分不变，并发 1 < 3）", ORANGE),
    ]
    ry = hdr_y + 26
    for name, legal, corr, fast, col in rows4:
        x = 44
        vals = [name, legal, corr, fast]
        for j, (_, cwid) in enumerate(cols4):
            c_col = col if j == 3 else (GREEN if j in (1, 2) else STROKE)
            tint = TINT["white"] if j == 0 else TINT[
                "green" if j in (1, 2) else ("orange" if col == ORANGE else "green")]
            if j == 3 and col == ORANGE:
                tint = TINT["orange"]
            body += cell(x, ry, cwid, 30, vals[j], c_col, size=10.6, tint=tint)
            x += cwid
        ry += 30

    save("03-shape-anatomy.svg", body)


# ============================================================
# 图 4：三维落位矩阵 ＋ 本周实验数据汇总
# ============================================================

def fig4() -> None:
    w, h = 1180, 1000
    body = header(w, h, "本周成果总账：16 例三维落位矩阵 ＋ D71–D77 实验数据汇总",
                  "左：第 75/76 天案例库在三个维度上的判定（今天 §3 重跑）；右：本周七天的检查与对拍账本。数字均为真实运行。")

    # ---- 左：16 例矩阵 ----
    body += panel_title(40, 108, "① 16 例 ×（合法 / 正确 / 更快）三维落位")
    mx, my = 44, 122
    name_w, col_w = 214, 108
    row_h = 40
    body += cell(mx, my, name_w, 28, "案例", STROKE, 11.5, TINT["gray"])
    for j, cname in enumerate(("合法?", "正确?", "更快?")):
        body += cell(mx + name_w + j * col_w, my, col_w, 28, cname, STROKE,
                     11.5, TINT["gray"])

    cases = [
        ("A1 模式不支持", "L1", "禁跑", "拒", RED, "gray", "red"),
        ("A2 副作用算子", "L2", "禁跑", "拒", RED, "gray", "red"),
        ("A3 Shape 不齐", "L3", "禁跑", "拒", RED, "gray", "red"),
        ("A4 int8 全链", "L5", "禁跑", "拒", RED, "gray", "red"),
        ("A5 偷走中间", "L4", "事故!", "拒", RED, "red", "red"),
        ("A6 无使用者", "L4", "禁跑", "拒", RED, "gray", "red"),
        ("A7 循环依赖", "L6", "禁跑", "拒", RED, "gray", "red"),
        ("A8 隐式 Reshape", "L3b", "禁跑", "拒", RED, "gray", "red"),
        ("R1 多使用者", "✓", "✓", "拒", GREEN, "green", "orange"),
        ("R1ctl 无组外", "✓", "✓", "拒", GREEN, "green", "orange"),
        ("R2 资源超限", "✓", "✓", "拒", GREEN, "green", "orange"),
        ("R2ctl tile64", "✓", "✓", "融", GREEN, "green", "green"),
        ("R3keep keep", "✓", "✓", "融", GREEN, "green", "green"),
        ("R3重算 recompute", "✓", "✓", "拒", GREEN, "green", "orange"),
        ("R4 tile128", "✓", "✓", "拒", GREEN, "green", "orange"),
        ("R4ctl tile64", "✓", "✓", "融", GREEN, "green", "green"),
    ]
    ry = my + 28
    for name, legal, corr, fast, c_legal, c_corr, c_fast in cases:
        body += cell(mx, ry, name_w, row_h - 6, name, STROKE, 10.2,
                     TINT["white"])
        body += cell(mx + name_w, ry, col_w, row_h - 6, legal,
                     RED if legal.startswith("L") else GREEN, 10.2,
                     TINT["red"] if legal.startswith("L") else TINT["green"])
        body += cell(mx + name_w + col_w, ry, col_w, row_h - 6, corr,
                     RED if corr == "事故!" else (MUTED if corr == "禁跑" else GREEN),
                     10.2, TINT[c_corr])
        body += cell(mx + name_w + 2 * col_w, ry, col_w, row_h - 6, fast,
                     GREEN if fast == "融" else ORANGE, 10.2, TINT[c_fast])
        ry += row_h
    body += txt(mx, ry + 18,
                "A5 的「事故!」：今天 §2g 故意关掉 L4 硬融——F 仍正确、组外 G 读到 999 垃圾；"
                "「合法∧不正确 = 0」正是 L4/L3b 守门的结果。", 10.5, INK)
    body += txt(mx, ry + 38, "「正确 ✓」的证据 = §2 模式级对拍（小链 ＋ 随机 12 组 ＋ 测试新种子 8 组，"
                "keep / recompute / MM→MM 三形式）。", 10.5, MUTED)

    # ---- 右：本周数据汇总 ----
    rx = mx + name_w + 3 * col_w + 24
    body += panel_title(rx, 108, "② 本周实验数据汇总（检查 / 对拍）")
    week = [
        ("D71", "计算量与访存量", "26/26", "23/23", "计数＋数值双对拍 25 组"),
        ("D72", "融合减少的流量", "25/25", "16/16", "公式 vs 执行器 25 组"),
        ("D73", "融合的资源代价", "22/22", "25/25", "四计划资源账逐位"),
        ("D74", "合法性/收益分离", "31/31", "32/32", "接口边界机检"),
        ("D75", "构造不融合案例", "30/30", "34/34", "d74 规则集回归"),
        ("D76", "Cost Model 集成", "31/31", "33/33", "16/16＋20/20＋13/13"),
        ("D77", "三维复盘（今天）", "18/18", "17/17", "数值 12 组＋16 例三维"),
    ]
    tws = [46, 150, 62, 62, 150]
    tx, ty = rx, 122
    x = tx
    for j, hname in enumerate(("天", "主题", "主实验", "测试", "关键对拍")):
        body += cell(x, ty, tws[j], 28, hname, STROKE, 11, TINT["gray"])
        x += tws[j]
    ry2 = ty + 28
    for d, topic, m1, m2, cross in week:
        x = tx
        today = d == "D77"
        for j, v in enumerate((d, topic, m1, m2, cross)):
            col = ORANGE if today else (GREEN if j in (2, 3) else INK)
            body += cell(x, ry2, tws[j], 34, v, ORANGE if today else STROKE,
                         10 if j == 1 else 10.5,
                         TINT["orange"] if today else TINT["white"])
            x += tws[j]
        ry2 += 34
    body += txt(tx, ry2 + 20, "本周合计 363 项检查（主实验 183 ＋ 独立测试 180），全部真实运行、可一键复跑。", 10.5, INK)
    body += txt(tx, ry2 + 40, "对拍口径：数值=逐位相等；流量=公式 vs 仪器化记账；判决=16 例 ground truth 回归。", 10.5, MUTED)

    # ---- 底部：一页标准回答 ----
    body += panel_title(40, 918, "③ 一页标准回答（面试口径，全文见 code/review-onepage.md）")
    body += sketch_rect(44, 930, 1096, 52, fill=TINT["blue"], stroke=BLUE,
                        sw=2.0, nseg=5)
    body += txt(60, 950, "①「能不能融」是结构问题：L1–L6 查模式/纯度/Shape/使用者/dtype/拓扑，与机器无关；"
               "②「融完对不对」是数值问题：独立 vs 融合逐位对拍，全图性质；", 11.2, INK)
    body += txt(60, 970, "③「融完快不快」是账本问题：ΔB−spill−重读罚评分＋三门槛，流量口径下界、不是实测时间。"
               "三者证据不能互替——R1ctl 数值全对仍拒、A5 图面能融却会算错。", 11.2, INK)

    save("04-week-matrix.svg", body)


if __name__ == "__main__":
    fig1()
    fig2()
    fig3()
    fig4()
    print("done.")
