#!/usr/bin/env python3
"""生成第 93 天教程的 4 张手绘风（Excalidraw-like）SVG 技术图。

运行方式：
    python3 make_images.py

输出到 ../images/ 目录：
    01-overview.svg          第 93 天在第 14 周与编译链路中的位置（配置层插在哪）
    02-config-anatomy.svg    LoopOptions 剖面：字段×默认值×四道门×消费契约
    03-validation-gates.svg  校验电池实测：17 个坏输入被拒 vs 好输入的四类归宿
    04-presets-results.svg   端到端实测：6 份配置 6 份 IR、1 个答案 ＋ fail-closed 实录

风格与 Day 78~92 保持一致：手绘抖动线条、马克笔笔触、米白背景、
蓝/橙/绿/红四种柔和强调色、简单几何形状。
图中文字与数字全部来自 loop_options.py 的真实运行结果（LO0~LO6）。
"""

import math
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent.parent / "day-092" / "code"))
sys.path.insert(0, str(HERE.parent.parent / "day-090" / "code"))

import loop_options as lo   # noqa: E402  （真实数据来源）

random.seed(93)

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
    ang = math.atan2(y2 - y1, x2 - y1)
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


def wrap(s, n):
    out, cur = [], ""
    for ch in s:
        cur += ch
        if len(cur) >= n:
            out.append(cur)
            cur = ""
    if cur:
        out.append(cur)
    return out


# ============================================================
# 真实数据：与 loop_options.py 同源（import 复跑，不是手抄）
# ============================================================

ROWS = lo.measure_orders()                      # 6 种顺序：op/流量/位等价/miss（真实执行）
BY = {r["name"]: r for r in ROWS}


def real_msg(thunk, exc_type):
    try:
        thunk()
        return "（竟然通过）"
    except exc_type as e:
        return str(e)


GATE1_MSG = real_msg(lambda: lo.LoopOptions(tile=(True, 2, 2)),
                     lo.OptionsValidationError)                       # bool 冒充 int
GATE2_MSG = real_msg(lambda: lo.LoopOptions.parse("foo=1"),
                     lo.OptionsValidationError)                       # 未知键
GATE3_MSG = [m for l, m in lo.LoopOptions(tile=(2, 2, 2))
             .validate_for_shape(lo.M, lo.K, lo.N) if l == "warn"][0]  # 不整除 warn
GATE4_MSG = real_msg(lambda: lo.run_with_options(lo.PRESETS["tile-16"], *lo.SIM_SHAPE),
                     lo.OptionsNotConsumedError)                      # fail-closed
TRIVIAL_NOTE = lo.LoopOptions(tile=(1, 1, 1)).consume_guard()[0]       # 平凡块附注
BAD_MSGS = {}
for _desc, _thunk, _frag in lo.BAD_CASES:
    BAD_MSGS[_desc] = real_msg(_thunk, lo.OptionsValidationError)


# ============================================================
# 图 1：全局定位
# ============================================================

def fig1():
    w, h = 1080, 660
    b = title_block(w, "第 93 天定位：把「怎么循环」从代码常量收进一份配置",
                    "第 14 周链条：昨天量化了自由度（D92）→ 今天把它做成配置（D93）→ 明天配置驱动 Tiling（D94）")

    # —— 上：第 14 周七天链 ——
    days = [("D92", ["循环顺序", "与局部性"], False), ("D93", ["参数化", "循环生成"], True),
            ("D94", ["基础 Tiling", "（tile 开张）"], False), ("D95", ["非整除", "尾部"], False),
            ("D96", ["展开向量化", "（unroll 开张）"], False), ("D97", ["多配置", "实验"], False),
            ("D98", ["复盘"], False)]
    x, y, bw, bh = 30, 104, 140, 66
    for i, (tag, sub, hot) in enumerate(days):
        bx = x + i * 150
        b += srect(bx, y, bw, bh, L_ORANGE if hot else "white",
                   ORANGE if hot else INK, 2.4 if hot else 1.8, rx=6)
        b += text(bx + 8, y + 22, tag, 14, ORANGE if hot else BLUE, bold=True)
        b += mtext(bx + bw / 2, y + 38, sub, 10.5, INK, "middle", 14)
        if i < len(days) - 1:
            b += arrow(bx + bw + 3, y + bh / 2, bx + 149, y + bh / 2, SOFT, 1.8)
    b += text(30, y + bh + 22, "本周主线：循环变换——一切变换的第一问都是「配置从哪来、校验谁把关」；今天的 LoopOptions 就是这周的「点菜单」",
              11.5, SOFT)

    # —— 中：编译链路（配置层插在 Pattern 装配之前）——
    py = 230
    b += srect(30, py, 1010, 235, "white", INK, 1.8, rx=8)
    b += text(46, py + 20, "编译链路：今天的动作 = 在「Pattern 装配」之前插入一个配置层", 13.5, INK, bold=True)
    boxes = [
        (46, 264, 180, 96, "配置入口", ["配置串 / preset", "「order=ikj,", "tile=2x2x3」"], BLUE),
        (256, 256, 210, 112, "LoopOptions", ["解析 → 四道门 → 冻结", "①类型 ②取值", "③形状 ④消费", "frozen dataclass"], ORANGE),
        (496, 264, 190, 96, "生成器", ["Day 92 的", "LoopOrderPattern", "（order=… 装配循环）"], BLUE),
        (716, 264, 140, 96, "循环 IR", ["18 / 21 op", "三重循环", "（同一批积木）"], GREEN),
        (886, 264, 138, 96, "执行验证", ["解释执行", "＋访存日志", "位等价 ✓"], GREEN),
    ]
    for i, (bx, by, bw2, bh2, name, lines, col) in enumerate(boxes):
        hot = name == "LoopOptions"
        b += srect(bx, by, bw2, bh2, L_ORANGE if hot else "white", col, 2.2, rx=6)
        b += text(bx + bw2 / 2, by + (22 if len(lines) < 4 else 20), name, 13.5, col, "middle", bold=True)
        b += mtext(bx + bw2 / 2, by + (40 if len(lines) < 4 else 38), lines, 11, INK, "middle", 15)
    b += arrow(226 + 4, 312, 256 - 4, 312, INK, 2.2)
    b += arrow(466 + 4, 312, 496 - 4, 312, INK, 2.2)
    b += arrow(686 + 4, 312, 716 - 4, 312, INK, 2.2)
    b += arrow(856 + 4, 312, 886 - 4, 312, INK, 2.2)
    # 消费门：tile / unroll 停在这里（fail-closed）
    fy = 384
    b += carrow((330, 370), (300, 402), (180, fy - 4), RED, 1.8, dash="6 5")
    b += carrow((390, 370), (430, 402), (580, fy - 4), RED, 1.8, dash="6 5")
    b += srect(60, fy, 240, 54, L_RED, RED, 1.8, dash="7 5", rx=6)
    b += mtext(180, fy + 16, ["TilingPattern（Day 94 才出生）", "tile 停在④门：明确拒绝"], 10.5, RED, "middle", 14)
    b += srect(460, fy, 240, 54, L_RED, RED, 1.8, dash="7 5", rx=6)
    b += mtext(580, fy + 16, ["展开 lowering（Day 96 才出生）", "unroll 停在④门：明确拒绝"], 10.5, RED, "middle", 14)
    b += mtext(760, 392, ["④门原则：宁可拒绝运行，", "绝不静默忽略——配了没生效", "必须有响声（报错点名归属日）"], 10.5, RED, "start", 15)

    # —— 下：输入与产出 ——
    iy = 520
    b += srect(30, iy, 460, 96, "white", BLUE, 1.8, rx=6)
    b += text(46, iy + 22, "输入（只取不改）", 13, BLUE, bold=True)
    b += mtext(46, iy + 40, ["Day 92：LoopOrderPattern——order 已是构造参数（雏形）",
                             "Day 87：%zero 出门 / 清零 nest（k 外层的前置）",
                             "Day 90：动态 Shape 宁拒不猜（今天在③门复用）"], 11, INK, "start", 17)
    b += arrow(496, iy + 48, 548, iy + 48, ORANGE, 2.4)
    b += srect(560, iy, 480, 96, "white", ORANGE, 1.8, rx=6)
    b += text(576, iy + 22, "产出（计划点名：配置结构、参数校验、默认值）", 13, ORANGE, bold=True)
    b += mtext(576, iy + 40, ["LoopOptions：结构 × 四道门 × 默认值 三合一",
                              "outputs/options-table.txt（配置结构表）＋ shape-check.txt",
                              "validate-battery.txt（17 拒）＋ presets-run.txt（6 顺序实测）"], 11, INK, "start", 17)
    save("01-overview.svg", w, h, b)


# ============================================================
# 图 2：LoopOptions 剖面（字段 × 默认值 × 四道门 × 消费契约）
# ============================================================

def fig2():
    w, h = 1080, 780
    b = title_block(w, "LoopOptions 剖面：字段 × 默认值 × 四道门 × 消费契约",
                    "frozen dataclass——结构、校验、默认值三合一（第 93 天交付物；报错均为真实输出）")

    # —— 左：配置卡片 ——
    cx, cy = 30, 110
    b += srect(cx, cy, 400, 560, "white", INK, 2.2, rx=8)
    b += srect(cx + 6, cy + 6, 388, 40, L_BLUE, BLUE, 1.8, rx=5)
    b += text(cx + 200, cy + 32, "LoopOptions ❄ frozen（不可变）", 15, BLUE, "middle", bold=True)
    fields = [
        ("order", "tuple (i, j, k)（外→内）",
         ["默认 i-j-k（Day 89~92 的教科书顺序）", "合法取值恰好 6 种排列（3!）",
          "校验：①类型门（序列）②取值门（3 个、各不相同）"],
         "消费：今天 D93 → LoopOrderPattern", "今天 D93", GREEN),
        ("tile", "3 个正整数 | None",
         ["默认 None = 不做 Tiling；tile=1x1x1 是平凡块", "③形状门：块>维度 error；不整除 warn→Day 95",
          "校验：①类型门（bool/float 拒）②取值门（长度 3、≥1）"],
         "消费：Day 94 → 今天④门拒绝", "D94（④门拒）", ORANGE),
        ("unroll", "int（展开因子）",
         ["默认 1 = 不展开；合法取值 ≥ 1",
          "③形状门：不整除最内层 trip → warn→Day 96", "校验：①类型门（int）②取值门（≥1）"],
         "消费：Day 96 → 今天④门拒绝", "D96（④门拒）", RED),
    ]
    fy = cy + 62
    for name, typ, lines, consume, tag, col in fields:
        b += srect(cx + 16, fy, 368, 138, L_ORANGE if col == ORANGE else
                   (L_GREEN if col == GREEN else L_RED), col, 1.8, rx=6)
        b += text(cx + 30, fy + 24, f"{name} ： {typ}", 13.5, col, bold=True)
        b += mtext(cx + 30, fy + 44, lines, 10.5, INK, "start", 15)
        b += srect(cx + 278, fy + 106, 92, 22, "white", col, 1.5, rx=4)
        b += text(cx + 324, fy + 121, tag, 9.2, col, "middle", bold=True)
        b += text(cx + 30, fy + 123, consume, 10.5, col)
        fy += 152
    b += mtext(cx + 16, fy + 6,
               ["全字段不可变：要改用 dataclasses.replace() 生成新对象（LO1d）",
                "两个入口（构造器 / parse）共用同一段 __post_init__ 校验——",
                "不存在「字符串入口查得松」的旁路（LO2 用 17 个坏输入验证）"],
               10.5, SOFT, "start", 15)

    # —— 右：四道门流水 ——
    gx = 470
    b += srect(gx, 110, 580, 560, "white", INK, 2.2, rx=8)
    b += text(gx + 16, 132, "一个字段的完整旅程：两个入口 → 四道门 → 冻结 → 生成器", 13.5, INK, bold=True)
    steps = [
        ("入口", ["LoopOptions(order='ikj', …)（构造器入口）",
                   "LoopOptions.parse('order=i-k-j,tile=2x2x3')（配置串入口）"], BLUE, None),
        ("① 类型门", ["挡：非序列 / float / bool 冒充 int",
                      GATE1_MSG], BLUE, "✗ 当场抛 OptionsValidationError"),
        ("② 取值门", ["挡：未知变量 / 重复 / 非正 / 未知键 / 键重复",
                      GATE2_MSG], BLUE, "✗ 当场抛 OptionsValidationError"),
        ("③ 形状门（需要具体 Shape）", ["分级：error 块>维度 ｜ warn 不整除（点名归属日）｜ info 动态跳过",
                      GATE3_MSG], ORANGE, "error → 拒；warn → 附注；info → 跳过（宁拒不猜）"),
        ("④ 消费门（校验通过 ≠ 已经生效）", ["挡：校验通过但今天的 lowering 不消费该字段",
                      GATE4_MSG], RED, "✗ OptionsNotConsumedError（绝不静默忽略）"),
        ("冻结的 LoopOptions → 生成器", ["run_with_options：order → Day 92 的 LoopOrderPattern",
                      "生成 18/21 op 循环 IR → 解释执行 → 位等价 ✓"], GREEN, None),
    ]
    sy = 148
    for i, (name, lines, col, side) in enumerate(steps):
        bh2 = 62 if i not in (0, 5) else 58
        b += srect(gx + 16, sy, 548, bh2, "white", col, 2.0, rx=6)
        b += srect(gx + 16, sy, 548, 24, L_ORANGE if col == ORANGE else
                   (L_RED if col == RED else (L_GREEN if col == GREEN else L_BLUE)), col, 1.5, rx=5)
        b += text(gx + 28, sy + 17, name, 12.5, col, bold=True)
        if side:
            b += text(gx + 556, sy + 16, side, 9.2, col, "end")
        b += mtext(gx + 28, sy + 36, [lines[0]], 10.5, INK, "start", 14)
        b += mtext(gx + 28, sy + 50, wrap(lines[1], 52), 9.8, SOFT, "start", 13)
        if i < len(steps) - 1:
            b += arrow(gx + 290, sy + bh2 + 2, gx + 290, sy + bh2 + 16, col, 2.0)
        sy += bh2 + 18
    save("02-config-anatomy.svg", w, h, b)


# ============================================================
# 图 3：校验电池实测（真实报错摘录）
# ============================================================

def fig3():
    w, h = 1080, 680
    b = title_block(w, "校验电池实测：17 个坏输入全被拒；好输入各有归宿",
                    "真实运行摘录（--battery / --show）；报错家族统一为 LoopOptionsError——驱动器一把抓")

    # —— 左：被拒 ——
    lx, ly = 30, 100
    b += srect(lx, ly, 515, 470, "white", RED, 2.0, rx=8)
    b += srect(lx + 6, ly + 6, 503, 34, L_RED, RED, 1.6, rx=5)
    b += text(lx + 16, ly + 29, "✗ 被拒（fail-closed，17/17，摘录 8 例）", 13.5, RED, bold=True)
    rejects = [
        ("order='ikm'", BAD_MSGS["order='ikm'：不认识 m"]),
        ("order='iij'", BAD_MSGS["order='iij'：归纳变量重复"]),
        ("tile=(True,2,2)", BAD_MSGS["tile=(True,2,2)：bool 冒充 int"]),
        ("tile=(1.5,2,2)", BAD_MSGS["tile=(1.5,2,2)：float 不是维度"]),
        ("unroll=0", BAD_MSGS["unroll=0：展开 0 次没意义"]),
        ("parse('foo=1')", BAD_MSGS["parse('foo=1')：未知键"]),
        ("parse('order=ikj,order=kij')", BAD_MSGS["parse('order=ikj,order=kij')：同一键两次"]),
        ("parse('tile=2xXx3')", BAD_MSGS["parse('tile=2xXx3')：分量不是整数"]),
    ]
    ry = ly + 52
    for inp, msg in rejects:
        b += text(lx + 16, ry, inp, 11.5, INK, bold=True)
        b += text(lx + 250, ry, "→", 11.5, RED, "middle")
        b += mtext(lx + 16, ry + 15, wrap(msg, 50), 9.6, SOFT, "start", 12.5)
        b += sline(lx + 12, ry + 26, lx + 503, ry + 26, GREY, 0.8, amp=0.5)
        ry += 52

    # —— 右：通过的四类归宿 ——
    rx_, ry2 = 570, 100
    b += srect(rx_, ry2, 480, 470, "white", GREEN, 2.0, rx=8)
    b += srect(rx_ + 6, ry2 + 6, 468, 34, L_GREEN, GREEN, 1.6, rx=5)
    b += text(rx_ + 16, ry2 + 29, "✓ 通过（四类归宿，全部真实行为）", 13.5, GREEN, bold=True)
    rrow = BY["i-k-j"]
    accepts = [
        ("（空串）", ["全默认：order=i-j-k、不 tiling、不展开", "＝ Day 89~92 的默认跑法（18 op，LO4c 复现）"], GREEN),
        ("order=ikj", [f"端到端：{rrow['ops']} op；C 流量 12L+12S+4 清零", "与同序参考位等价 ✓（LO4b）"], GREEN),
        ("tile=2x2x3", ["③形状门全绿：2×3·3×2 三维整除（ok×3）", "→ ④门拒（Day 94）——校验通过 ≠ 已经生效"], ORANGE),
        ("tile=2x2x2", ["③形状门 warn：tile_k=2 ∤ K=3（→ Day 95 尾部）", "→ ④门拒（Day 94）"], ORANGE),
        ("tile=1x1x1", ["放行 ＋ 附注：「平凡块（= 不分块）」", "不是静默忽略——没生效也有案可查（LO6c）"], GREEN),
        ("unroll=2", ["③形状门 warn：∤ 最内层 k 的 trip 3（→ Day 96）", "→ ④门拒（Day 96）"], ORANGE),
    ]
    ry = ry2 + 52
    for inp, lines, col in accepts:
        b += srect(rx_ + 12, ry - 14, 456, 60, L_ORANGE if col == ORANGE else L_GREEN, col, 1.4, rx=4)
        b += text(rx_ + 24, ry, inp, 12, col, bold=True)
        b += mtext(rx_ + 150, ry - 2, lines, 10, INK, "start", 14)
        ry += 70

    # —— 底部判据 ——
    b += srect(30, 590, 1020, 52, GREY, SOFT, 1.6, rx=5)
    b += mtext(46, 610,
               ["判据（LO2）：每个坏输入必须抛 OptionsValidationError，且报错含定位片段——错在哪个字段、为什么、合法值是什么；",
                "宽容式实现（filter 掉不认识的键、把坏值改成默认值）会让这 17 个错误全部静默消失——这正是 fail-closed 要防的世界。"],
               11.5, SOFT, "start", 19)
    save("03-validation-gates.svg", w, h, b)


# ============================================================
# 图 4：端到端实测（配置是数据）
# ============================================================

def fig4():
    w, h = 1120, 780
    b = title_block(w, "实测：配置是数据——6 份配置 6 份 IR、1 个答案",
                    "A(2,3)@B(3,2) 种子 93 端到端（op／C 流量／位等价）＋ 16³ 真实轨迹回放（Day 92 口径）")

    # —— 左：配置 × 实测表 ——
    x0, y0 = 30, 100
    cols = [("配置（最小规范形）", 150), ("最内", 38), ("op", 36), ("C 流量", 106),
            ("位等价", 46), ("miss\n@512B", 74), ("miss\n@1KB", 62)]
    hh = 46
    tw = sum(cw for _, cw in cols)
    b += srect(x0, y0, tw, hh + 8 * 40 + 8, "white", INK, 2.2, rx=6)
    cx = x0
    for name, cw in cols:
        b += srect(cx, y0, cw, hh, GREY, INK, 1.6, amp=0.8)
        lines = name.split("\n")
        b += mtext(cx + cw / 2, y0 + (20 if len(lines) == 1 else 15), lines, 11.5, INK, "middle", 15)
        cx += cw
    ri = 0
    for r in ROWS:
        ry = y0 + hh + ri * 40
        t = r["traffic"]
        cflow = (f"{t['c_loads']}L+{t['c_stores']}S"
                 + (f"+{t['init_stores']}清" if t["init_stores"] else ""))
        vals = [r["cfg"], r["inner"], str(r["ops"]), cflow,
                "✓" if r["eq"] else "✗", str(r["m32"]), str(r["m64"])]
        cx = x0
        for (name, cw), v in zip(cols, vals):
            b += text(cx + cw / 2, ry + 25, v, 11.5, INK, "middle",
                      bold=(name == "配置（最小规范形）"))
            cx += cw
        b += sline(x0, ry, x0 + tw, ry, GREY, 1.0, amp=0.6)
        ri += 1
    for nm, note, col in [("tile-16", "tile=16x16x16", ORANGE), ("unroll-2", "unroll=2", RED)]:
        ry = y0 + hh + ri * 40
        b += srect(x0 + 2, ry + 3, tw - 4, 34, L_RED, col, 1.4, amp=0.6, rx=4)
        b += text(x0 + 16, ry + 25, note, 11.5, col, bold=True)
        b += text(x0 + tw / 2 + 30, ry + 25,
                  "— → ④门拒（点名 " + ("Day 94" if col == ORANGE else "Day 96") + "）",
                  11.5, RED, "middle")
        ri += 1
    # 高亮两个赢家（圈住 miss 列的实测值）
    b += scirc(443, y0 + hh + 1 * 40 + 20, 25, "none", ORANGE, 2.4)
    b += scirc(511, y0 + hh + 0 * 40 + 20, 23, "none", GREEN, 2.4)
    b += mtext(x0, y0 + hh + 8 * 40 + 32,
               ["高亮：512B 下 i-k-j 缺失最少（2580，橙圈）；1KB 下 i-j-k 反超（950，绿圈）——排名随容量翻转（Day 92 的发现，今天由配置触发）。",
                "位等价 6/6：k 处处升序 → 舍入顺序不变——换配置不换数（Day 92 结论由配置触发）。",
                "miss 列与 Day 92 的 order-table.txt 逐格一致——今天换的是「配置从哪来」，不是行为口径。",
                "全默认也是一份合法配置：空串 → parse('') == LoopOptions()（无 flag = 默认行为）。"],
               11, SOFT, "start", 16)

    # —— 右上：④门实录 ——
    bx, by = 620, 104
    b += srect(bx, by, 470, 150, L_RED, RED, 2.0, rx=8)
    b += text(bx + 16, by + 24, "④门实录：校验通过 ≠ 已经生效", 13.5, RED, bold=True)
    b += mtext(bx + 16, by + 44, wrap(GATE4_MSG, 44), 10.5, INK, "start", 15)
    b += mtext(bx + 16, by + 118,
               ["宁可拒绝运行，不可静默忽略——", "配了没生效必须有响声（LO6a）"], 10.5, RED, "start", 14)

    # —— 右中：op 序列对照 ——
    by2 = by + 166
    b += srect(bx, by2, 470, 150, "white", BLUE, 1.8, rx=8)
    b += text(bx + 16, by2 + 24, "op 序列对照（真实转换输出）", 13.5, BLUE, bold=True)

    def short_seq(seq):
        return lo.seq_compact(seq).replace("func.func → ", "").replace(" → func.return", "") \
            .replace("memref.", "").replace("arith.", "").replace("scf.", "")

    b += mtext(bx + 16, by2 + 46,
               ["i-j-k（18 op，空配置）：",
                *wrap(short_seq(BY["i-j-k"]["seq"]), 66)],
               10, INK, "start", 15)
    b += mtext(bx + 16, by2 + 92,
               ["i-k-j（21 op，order=ikj）：",
                *wrap(short_seq(BY["i-k-j"]["seq"]), 66)],
               10, INK, "start", 15)
    b += mtext(bx + 16, by2 + 136,
               ["差别：清零 nest＋3、体内多 1 个 load（读 C）、多 1 个 store（写回 C）。"], 10, SOFT, "start", 14)

    # —— 右下：数字卡片 ——
    by3 = by2 + 166
    cards = [("坏输入", "17/17", "全部按预期拒绝，报错含定位片段（LO2）", RED),
             ("位等价", "6/6", "6 份顺序配置端到端，与同序参考逐位相同（LO4）", GREEN),
             ("停在④门", "2", "tile → D94；unroll → D96：校验过、消费没到（LO6）", ORANGE),
             ("静默忽略", "0", "没有任何配置被悄悄丢掉——fail-closed 的底线", BLUE)]
    for i, (t1, t2, t3, col) in enumerate(cards):
        yy = by3 + i * 56
        b += srect(bx, yy, 470, 48, "white", col, 2.0, rx=6)
        b += text(bx + 14, yy + 30, t1, 13, col, bold=True)
        b += text(bx + 96, yy + 31, t2, 17, col, "middle", bold=True)
        b += text(bx + 130, yy + 30, t3, 10.5, INK)

    # —— 底部口径 ——
    b += srect(30, 722, 1060, 46, GREY, SOFT, 1.6, rx=5)
    b += mtext(46, 740,
               ["口径：miss 来自对解释执行器真实访存日志的直接映射缓存回放（行 16B、矩阵间 1 行、write-allocate、无预取）——",
                "模拟测量，不是真实硬件实测；数字用于配置之间的对比（与 Day 92 的 order-table.txt 同源同口径）。"],
               11.5, SOFT, "start", 17)
    save("04-presets-results.svg", w, h, b)


if __name__ == "__main__":
    fig1()
    fig2()
    fig3()
    fig4()
