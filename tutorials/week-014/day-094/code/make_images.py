#!/usr/bin/env python3
"""生成第 94 天教程的 4 张手绘风（Excalidraw-like）SVG 技术图。

运行方式：
    python3 make_images.py

输出到 ../images/ 目录：
    01-overview.svg          第 94 天在第 14 周与编译链路中的位置（tile 开张）
    02-tiling-mechanism.svg  核心机制：块循环×点循环的 6 层骨架＋跨块累加接力
    03-tail-preview.svg     整除 vs 非整除：尾部为什么是 Day 95 的内容
    04-results.svg           实测结果：Tk 换档的 C 流量＋512B 缓存缺失对比

风格与 Day 78~93 保持一致：手绘抖动线条、马克笔笔触、米白背景、
蓝/橙/绿/红四种柔和强调色、简单几何形状。
图中文字与数字全部来自 tiling_pass.py 的真实运行结果（TL1~TL6）。
"""

import math
import random
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent.parent / "day-093" / "code"))
sys.path.insert(0, str(HERE.parent.parent / "day-092" / "code"))
sys.path.insert(0, str(HERE.parent.parent / "day-090" / "code"))

import loop_options as lo   # noqa: E402
import order_pass as od     # noqa: E402
import tiling_pass as tp    # noqa: E402  （真实数据来源）

random.seed(94)

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
# 真实数据：与 tiling_pass.py 同源（import 复跑，不是手抄）
# ============================================================

M, K, N = tp.M, tp.K, tp.N
SM = tp.SIM_SHAPE


def _real_msg(thunk, exc_type):
    try:
        thunk()
        return "（竟然通过）"
    except exc_type as e:
        return str(e)


# —— 小例流量（TL3 实测） ——
_T211 = tp.traffic_of(tp.run_tiled((2, 2, 1), M, K, N))
_T213 = tp.traffic_of(tp.run_tiled((2, 2, 3), M, K, N))
TRAFFIC_211 = f"{_T211['c_loads']}L+{_T211['c_stores']}S+{_T211['init_stores']}清"
TRAFFIC_213 = f"{_T213['c_loads']}L+{_T213['c_stores']}S+{_T213['init_stores']}清"

# —— 16³ 缓存实验（TL5 实测） ——
_CACHE_ROWS = []
for label, run in (
        ("untiled i-j-k", od.run_order(("i", "j", "k"), *SM, seed=94)),
        ("untiled i-k-j", od.run_order(("i", "k", "j"), *SM, seed=94)),
        ("tiled 2x2x2", tp.run_tiled((2, 2, 2), *SM)),
        ("tiled 4x4x4", tp.run_tiled((4, 4, 4), *SM)),
        ("tiled 8x8x8", tp.run_tiled((8, 8, 8), *SM))):
    s32 = od.cache_sim(run["interp"].access_log, *SM, lines=32)
    s64 = od.cache_sim(run["interp"].access_log, *SM, lines=64)
    _CACHE_ROWS.append(dict(name=label, total=s32["total"], m32=s32["misses"],
                            m64=s64["misses"], b32=s32["per_mem"].get("%b", 0),
                            hr=s32["hit_rate"]))

# —— 真实报错（§6 / TL6b / 探针） ——
NONDIV_GATE_MSG = _real_msg(lambda: tp.run_with_config("tile=2x2x2"),
                             lo.OptionsNotConsumedError)
OOB_MSG = tp.run_tiled((2, 2, 2), M, K, N)["err"] or "（探针没拦住）"
UNROLL_MSG = _real_msg(lambda: tp.run_with_config("unroll=2"),
                       lo.OptionsNotConsumedError)
MIX_MSG = _real_msg(lambda: tp.run_with_config("order=ikj,tile=2x2x3"),
                    lo.OptionsNotConsumedError)


# ============================================================
# 图 1：全局定位——tile 开张
# ============================================================

def fig1():
    w, h = 1080, 700
    b = title_block(w, "第 94 天定位：tile 开张——被拒了一天的配置今天驱动生成",
                    "第 14 周链条：D93 把选择做成配置 → D94 消费 tile（今天）→ D95 尾部 / D96 展开 / D97 组合")

    # —— 上：第 14 周七天链 ——
    days = [("D92", ["循环顺序", "局部性"], False), ("D93", ["参数化", "LoopOptions"], False),
            ("D94", ["基础 Tiling", "tile 开张"], True), ("D95", ["非整除", "尾部"], False),
            ("D96", ["展开", "unroll 开张"], False), ("D97", ["多配置", "实验"], False),
            ("D98", ["第 14 周", "复盘"], False)]
    x0, bw, bh, gap = 30, 138, 78, 15
    for idx, (tag, lines, hot) in enumerate(days):
        x = x0 + idx * (bw + gap)
        f = L_ORANGE if hot else "white"
        s = ORANGE if hot else INK
        b += srect(x, 104, bw, bh, f, s, 2.6 if hot else 2.0)
        b += text(x + bw / 2, 128, tag, 17, s, anchor="middle", bold=hot)
        b += mtext(x + bw / 2, 150, lines, 12, INK if not hot else INK, "middle", 16)
    b += text(30, 206, "D93 的第④道门昨天说：『Tiling 的 lowering 是 Day 94 的内容』——今天兑现这句承诺；"
                       "同一天出生的还有尾部问题的边界（D95 的预告）。", 13, SOFT)

    # —— 中：配置驱动流水线 ——
    b += text(30, 248, "一条配置串的今天旅程（真实路径，tiling_pass.py 的 run_with_config）：", 14, INK, bold=True)
    steps = [("LoopOptions", ["tile=2x2x1", "（D93 的配置）"], "white", INK),
             ("①② 类型/取值门", ["构造层校验", "原样沿用 D93"], "white", INK),
             ("③ 形状门", ["整除 ✓", "块>维度 ✗"], "white", INK),
             ("④ 消费门", ["tile 开张 ✓", "unroll ✗ D96"], L_GREEN, GREEN),
             ("TilingPattern", ["6 层循环", "31 op"], L_BLUE, BLUE),
             ("TilingInterp", ["＋arith.addi", "探针原样"], "white", INK),
             ("整除测试", ["26/26 √", "位等价"], L_GREEN, GREEN)]
    sx, sw_, sh, sgap = 30, 132, 86, 12
    for idx, (t1, lines, f, s) in enumerate(steps):
        x = sx + idx * (sw_ + sgap)
        b += srect(x, 264, sw_, sh, f, s, 2.2)
        b += text(x + sw_ / 2, 290, t1, 13.5, s, anchor="middle", bold=True)
        b += mtext(x + sw_ / 2, 312, lines, 11.5, INK, "middle", 15)
        if idx < len(steps) - 1:
            b += arrow(x + sw_ + 1, 264 + sh / 2, x + sw_ + sgap - 1, 264 + sh / 2, INK, 2.0)
    b += mtext(30, 378, [
        "第④道门的今天分工（fail-closed 原则不变）：tile 设置且整除 → 消费（今天）；不整除 → 拒（点名 Day 95：尾部）；",
        f"unroll=2 → 拒（点名 Day 96）；tile×order 组合 → 拒（点名 Day 97）——报错原文见 §6 与 outputs/consume-guard.txt"], 12.5, SOFT)

    # —— 下：输入 / 产出 ——
    b += srect(30, 424, 470, 120, "white", INK, 2.0)
    b += text(48, 450, "今天复用（只取不改）", 14, BLUE, bold=True)
    b += mtext(48, 474, [
        "· Day 87：%zero 零起点 / iter_args 寄存器累加 / 内存垃圾模型",
        "· Day 92：形态 B（k 外层 → 内存累加 + 清零 nest）/ cache_sim 回放器",
        "· Day 93：LoopOptions 四道门（①②③原样；④今天更新）/ od.run_order"], 12.5)
    b += srect(580, 424, 470, 120, L_ORANGE, ORANGE, 2.2)
    b += text(598, 450, "今天产出（全部真实运行）", 14, ORANGE, bold=True)
    b += mtext(598, 474, [
        "· TilingPattern＋TilingInterp：31 op 的 6 层循环（tiled-ir.txt）",
        "· 整除测试 26/26：小例 8＋16³ 10＋非方形 8（divisible-tests.txt）",
        "· 缓存实验：512B 缺失 4764→1082；B缺 4096→398（cache-blocking.txt）"], 12.5)
    b += carrow((500, 484), (540, 484), (578, 484), INK, 2.0)

    b += srect(30, 570, 1020, 92, "white", INK, 2.0, dash="8 7")
    b += text(48, 598, "与第 112 天里程碑的关系", 14, GREEN, bold=True)
    b += mtext(48, 622, [
        "里程碑写的是『循环 Lowering、Tiling、内存规划和自动调优』——今天 Tiling 主线正式开工：块循环/点循环",
        "是骨架（今天）、尾部是完备性（D95）、展开是密度（D96）、多配置实验是搜索（D97）——四周连成一条 Tiling 线。"], 12.5)
    save("01-overview.svg", w, h, b)


# ============================================================
# 图 2：核心机制——块循环 × 点循环 × 跨块接力
# ============================================================

def fig2():
    w, h = 1080, 780
    b = title_block(w, "核心机制：三维循环怎么被切成方块（16³，tile=4x4x4）",
                    "左：C 被切成 4×4 个 4×4 方块——块循环跳整块；右：6 层骨架与跨块累加接力（小例实测）")

    # —— 左：C 的方块视图 ——
    gx, gy, cell, dim = 60, 130, 34, 4   # 4×4 个块，每块代表 4×4
    grid_w = dim * cell
    b += text(gx, 116, "C(16,16) 切成 4×4 个方块（每块 4×4）", 14, INK, bold=True)
    for r_ in range(dim):
        for c_ in range(dim):
            x, y = gx + c_ * cell, gy + r_ * cell
            hot = (r_ == 1 and c_ == 2)
            f = L_GREEN if hot else (L_BLUE if r_ == 1 else (L_ORANGE if c_ == 2 else "white"))
            b += srect(x, y, cell, cell, f, SOFT if not hot else GREEN, 1.8 if not hot else 2.4)
    b += srect(gx, gy + cell, cell * 4, cell, "none", BLUE, 2.4, dash="9 6")
    b += text(gx + grid_w + 12, gy + cell + 12, "i0 面板：A 的 4 行", 12, BLUE)
    b += srect(gx + cell * 2, gy, cell, cell * 4, "none", ORANGE, 2.4, dash="9 6")
    b += text(gx + grid_w + 12, gy + 30, "j0 面板：B 的 4 列", 12, ORANGE)
    b += text(gx + cell * 2 + 4, gy + cell + 22, "C 方块", 11, GREEN, bold=True)
    # 块循环箭头
    b += arrow(gx - 8, gy + grid_w + 6, gx + grid_w + 2, gy + grid_w + 6, BLUE, 2.2)
    b += text(gx + grid_w / 2, gy + grid_w + 30, "块循环 i0：step = tile_m = 4（一圈跳一整行方块）", 12.5, BLUE, anchor="middle")
    b += arrow(gx + grid_w + 6, gy - 4, gx + grid_w + 6, gy + grid_w + 2, ORANGE, 2.2)
    b += text(gx + grid_w + 14, gy + grid_w / 2, "块循环 j0：step = tile_n", 12.5, ORANGE, rot=90)
    b += mtext(gx, gy + grid_w + 58, [
        "· k0 也被切：K=16 → 4 个 k-块（每个 (i0,j0) 要扫 4 轮）",
        "· A 面板 16 行→4 行、B 列面板 16 列→4 列：工作集从 3KB 缩到 192B",
        "→ 512B 缓存装得下 → B缺 4096→398（实测，图 4）"], 12.5)

    # —— 右：6 层骨架（小例 tile=2x2x1 的真实循环头） ——
    nx, ny, nw = 520, 130, 530
    b += text(nx, 116, "6 层骨架：块循环（蓝）套点循环（绿）——小例 A(2,3)@B(3,2)，tile=2x2x1", 14, INK, bold=True)
    nest = [
        ("scf.for %i0 = 0 to 2 step 2", "块循环 i0：trip = M/Tm = 1", BLUE, L_BLUE),
        ("scf.for %j0 = 0 to 2 step 2", "块循环 j0：trip = N/Tn = 1", BLUE, L_BLUE),
        ("scf.for %k0 = 0 to 3 step 1", "块循环 k0：trip = K/Tk = 3（归约被切）", BLUE, L_BLUE),
        ("scf.for %i = %i0 to %ub_i step 1", "点循环 i：[%i0, %i0+2)——ub=addi(%i0,%cTm)", GREEN, L_GREEN),
        ("scf.for %j = %j0 to %ub_j step 1", "点循环 j：[%j0, %j0+2)", GREEN, L_GREEN),
        ("scf.for %k = %k0 to %ub_k iter_args(%acc=%cv)", "点循环 k：块内寄存器乘加（Day 87 的 %acc）", GREEN, L_GREEN),
    ]
    for idx, (head_, note, s, f) in enumerate(nest):
        y = ny + idx * 52
        b += srect(nx + idx * 14, y, nw - idx * 14, 42, f, s, 2.0)
        b += text(nx + idx * 14 + 14, y + 18, head_, 12.5, INK, bold=True)
        b += text(nx + idx * 14 + 14, y + 34, note, 11.5, SOFT)
    b += mtext(nx, ny + 6 * 52 + 8, [
        "· 块循环的 step 是块尺寸（跳整块）；点循环的 lb 是块起点（块内一格一格走）",
        "· 三个 %ub 都是 arith.addi 现算（真实 MLIR 的 Tiling 分解同款）",
        "· 载荷（load A/B、mulf、addf、yield）与 Day 89 逐字相同——只换了骨架"], 12.5)

    # —— 下：跨块累加接力（小例实测 12L+12S+4清） ——
    ry = 580
    b += srect(30, ry, 1020, 165, "white", INK, 2.2)
    b += text(48, ry + 26, f"跨块累加接力：k 被切成 3 块后的 C[i,j]（小例实测 C 流量 {TRAFFIC_211}）", 14, INK, bold=True)
    stations = [("清零 nest", "store 0", "4 次", L_ORANGE, ORANGE),
                ("k-块 0（k0=0）", "load 0 → 块内乘加 → store 部分和", "1L+1S", L_BLUE, BLUE),
                ("k-块 1（k0=1）", "load 部分和 → 乘加 → store", "1L+1S", L_BLUE, BLUE),
                ("k-块 2（k0=2）", "load → 乘加 → store 终值", "1L+1S", L_BLUE, BLUE)]
    sx_, sw2 = 60, 216
    for idx, (t1, t2, t3, f, s) in enumerate(stations):
        x = sx_ + idx * (sw2 + 42)
        b += srect(x, ry + 44, sw2, 62, f, s, 2.0)
        b += text(x + sw2 / 2, ry + 64, t1, 12.5, INK, anchor="middle", bold=True)
        b += text(x + sw2 / 2, ry + 82, t2, 11.5, SOFT, anchor="middle")
        b += text(x + sw2 / 2, ry + 99, t3, 12, s, anchor="middle", bold=True)
        if idx < 3:
            b += arrow(x + sw2 + 3, ry + 75, x + sw2 + 39, ry + 75, INK, 2.0)
    b += mtext(60, ry + 128, [
        "块内：iter_args 寄存器累加（Tk 次乘加不碰内存）；跨块：部分和落 C（读-改-写）——Day 92『k 不在最内层 → 累加器住内存』",
        "在 Tiling 世界的重现，所以清零 nest 必须在（第一个块的 load 读到的 0 就是它铺的）。位等价机制：k0 升序 × 块内 k 升序 = 全局升序。"], 12)
    save("02-tiling-mechanism.svg", w, h, b)


# ============================================================
# 图 3：整除 vs 非整除——尾部为什么是 Day 95
# ============================================================

def fig3():
    w, h = 1080, 660
    b = title_block(w, "整除 vs 非整除：尾部（tail）为什么先欠着、明天还",
                    "今天的学习目标里有『尾部处理』——先看清问题在哪，实现留给 Day 95；今天对不整除 fail-closed 拒绝")

    def numline(y, kdim, tk, title, ok):
        x0, x1 = 90, 990
        scale = (x1 - x0) / 12.0
        b_ = text(x0, y - 26, title, 14.5, INK, bold=True)
        b_ += sline(x0, y, x1, y, INK, 2.2)
        for v in range(0, 13):
            b_ += sline(x0 + v * scale, y - 6, x0 + v * scale, y + 6, INK, 1.8)
            b_ += text(x0 + v * scale, y + 24, str(v), 11.5, SOFT, anchor="middle")
        for start in range(0, kdim, tk):
            end = start + tk
            clipped = min(end, kdim)
            good = end <= kdim
            x, xe = x0 + start * scale, x0 + clipped * scale
            f = L_GREEN if good else L_RED
            s_ = GREEN if good else RED
            b_ += srect(x, y - 34, xe - x, 22, f, s_, 2.2)
            b_ += text((x + xe) / 2, y - 19, f"[{start},{end})", 12.5, s_, anchor="middle", bold=True)
            if not good:
                xo = x0 + kdim * scale
                b_ += srect(xo, y - 34, xe - xo, 22, L_RED, RED, 2.2, dash="5 4")
                b_ += text((xo + xe) / 2, y - 19, "越界!", 12, RED, anchor="middle", bold=True)
                b_ += arrow(xo, y - 46, xo, y - 60, RED, 2.0)
                b_ += text(xo + 10, y - 64, f"点循环 ub = k0+Tk = {end} > K={kdim}", 12, RED)
        return b_

    b += numline(150, 6, 3, "整除场景（今天管）：K=6，tile_k=3 → 两个完整块 [0,3) + [3,6)", True)
    b += mtext(90, 200, [
        "点循环 ub = k0+3 恰好落在维度边界——26 组整除测试全过（TL4）；每格 C 恰好被写 K/Tk 次（TL3 公式成立）。"], 12.5)
    b += numline(320, 6, 4, "非整除（Day 95 的债）：K=6，tile_k=4 → 第二块 [4,8) 越过 K=6", False)
    b += mtext(90, 370, [
        "剩下 [4,6) 的『尾部』只有 2 格：点循环 ub = 4+4 = 8 会多算 k=6、k=7——要么越界（探针拦下），",
        "要么重复计算（语义直接错）。真实编译器的两个修法：上界夹 min(k0+Tk, K)（剩余循环）或掩掉越界趟（掩码）——都在 Day 95。"], 12.5)

    # 真实报错对照
    b += srect(60, 430, 460, 190, L_RED, RED, 2.2)
    b += text(78, 456, "绕过配置层直接跑（§6 错误 1 的真实输出）：", 13, RED, bold=True)
    b += mtext(78, 480, ["A(2,3)@B(3,2)，tile=2x2x2（Tk=2 ∤ K=3）："] +
               [f"“{OOB_MSG[:56]}”", f"“{OOB_MSG[56:104]}”"], 11.5)
    b += mtext(78, 560, [
        "转换照常成功（31 op）——IR 生成不讲武德，",
        "是 Day 88 的按维越界探针在执行期拦下的。"], 12)

    b += srect(560, 430, 460, 190, "white", INK, 2.2)
    b += text(578, 456, "从正门走：第④道消费门 fail-closed（TL6b 真实报错）：", 13, GREEN, bold=True)
    msg = NONDIV_GATE_MSG
    seg = [msg[i:i + 36] for i in range(0, min(len(msg), 108), 36)]
    b += mtext(578, 480, ["“" + s_ + "”" for s_ in seg], 11.5)
    b += mtext(578, 560, [
        "同一份配置，正门给的是「点名 Day 95 的拒绝」，",
        "而不是生成一份越界的 IR——宁可拒绝运行，不可静默忽略。"], 12)
    save("03-tail-preview.svg", w, h, b)


# ============================================================
# 图 4：实测结果——Tk 换档与缓存收益
# ============================================================

def fig4():
    w, h = 1080, 740
    b = title_block(w, "实测结果：Tk 一个数字改 C 流量；块循环让 512B 缺失掉到 1/4",
                    "数字全部来自真实回放（16³ 直接映射缓存，行 16B——Day 92 口径；小例为解释执行日志计数）")

    # —— 左上：小例 Tk 换档表 ——
    b += text(40, 122, "① 同一形状，只换 Tk（小例 A(2,3)@B(3,2) 实测）", 14, INK, bold=True)
    rows = [("tile=2x2x1", "K/Tk = 3", TRAFFIC_211, "3 轮接力"),
            ("tile=2x2x3", "K/Tk = 1", TRAFFIC_213, "单块，无需接力")]
    b += srect(40, 136, 480, 30, GREY, SOFT, 1.6)
    cols = [(52, "配置"), (180, "k-块数"), (280, "C 流量（实测）"), (415, "跨块接力")]
    for cx, ct in cols:
        b += text(cx, 156, ct, 12, SOFT, bold=True)
    for ri, (cfg, kt, flow, note) in enumerate(rows):
        y = 166 + ri * 40
        f = L_BLUE if ri == 0 else "white"
        b += srect(40, y, 480, 40, f, INK, 1.8)
        b += text(52, y + 25, cfg, 13, INK, bold=True)
        b += text(180, y + 25, kt, 13, BLUE, bold=True)
        b += text(280, y + 25, flow, 13, INK)
        b += text(415, y + 25, note, 12, SOFT)
    b += srect(40, 250, 480, 76, L_ORANGE, ORANGE, 2.2)
    b += mtext(56, 274, [
        "公式（TL3 实测对齐）：C 读 = C 写 = M·N·K/Tk，清零 = M·N",
        "A/B 的 load 恒 2·M·N·K（12 次）——切块改『时机』不改『次数』；",
        "位等价两份都是 True：Tk 是性能旋钮，不是正确性旋钮"], 12.5)

    # —— 左下：512B 缺失柱状（真实数字） ——
    b += text(40, 372, "② 512B（32 行）缓存缺失对比（16³ 真实轨迹回放）", 14, INK, bold=True)
    bx, by, bw2, bh2 = 40, 396, 480, 250
    b += srect(bx, by, bw2, bh2, "white", INK, 2.0)
    maxv = 4764.0
    bar_h = 170
    names = [r["name"] for r in _CACHE_ROWS]
    vals = [r["m32"] for r in _CACHE_ROWS]
    colors = [SOFT, SOFT, BLUE, GREEN, BLUE]
    for i, (nm, v, c_) in enumerate(zip(names, vals, colors)):
        x = bx + 40 + i * 84
        hgt = v / maxv * bar_h
        b += srect(x, by + bh2 - 56 - hgt, 52, hgt, L_GREEN if c_ == GREEN else "white", c_, 2.0)
        b += text(x + 26, by + bh2 - 64 - hgt, str(v), 12.5, c_, anchor="middle", bold=True)
        for li, ln_ in enumerate(nm.split()):
            b += text(x + 26, by + bh2 - 38 + li * 15, ln_, 10.5, INK, anchor="middle")
    b += arrow(bx + 20, by + bh2 - 56, bx + 20, by + 16, INK, 1.8)
    b += text(bx + 8, by + 14, "miss", 11, SOFT)
    b += text(bx + bw2 / 2, by + bh2 - 8, "总缺失：4764 → 1082（tiled 4x4x4，↓77%）；B缺：4096 → 398（↓90%）", 12.5, GREEN, anchor="middle", bold=True)

    # —— 右：读数与代价 ——
    rx, rw = 560, 480
    b += text(rx, 122, "③ 两个容量档 ＋ 诚实的代价列", 14, INK, bold=True)
    b += srect(rx, 136, rw, 190, "white", INK, 2.0)
    b += text(rx + 16, 160, "配置", 12, SOFT, bold=True)
    b += text(rx + 190, 160, "总访问", 12, SOFT, anchor="end", bold=True)
    b += text(rx + 290, 160, "512B缺失", 12, SOFT, anchor="end", bold=True)
    b += text(rx + 400, 160, "1KB缺失", 12, SOFT, anchor="end", bold=True)
    for i, r in enumerate(_CACHE_ROWS):
        y = 182 + i * 26
        hot = r["name"] == "tiled 4x4x4"
        if hot:
            b += srect(rx + 6, y - 16, rw - 12, 24, L_GREEN, "none", 1.2)
        b += text(rx + 16, y, r["name"], 12.5, GREEN if hot else INK, bold=hot)
        b += text(rx + 190, y, str(r["total"]), 12.5, INK, anchor="end")
        b += text(rx + 290, y, str(r["m32"]), 12.5, GREEN if hot else INK, anchor="end", bold=hot)
        b += text(rx + 400, y, str(r["m64"]), 12.5, INK, anchor="end")
    b += mtext(rx + 16, 316, [
        "两个容量档 tiled 4x4x4 都占优（823 vs 950/1584 @1KB）——这不是碰运气：",
        "每块工作集 A 16格+B 16格+C 16格 = 12 行，32 行的 512B 也装得下。"], 12)

    b += srect(rx, 344, rw, 150, L_ORANGE, ORANGE, 2.2)
    b += mtext(rx + 16, 370, [
        "代价（TL5d 实测）：总访问 8448 → 10496（+24%）",
        "多出来的 2048 次访问全是 C 的跨块读-改-写——但它们",
        "几乎全部命中（512B 命中率 43.6% → 89.7%）：用便宜的",
        "命中换昂贵的缺失，这笔账在 512B 下是划算的。"], 12.5)
    b += mtext(rx + 16, 512, [
        "注意：8x8x8（1238）没有 4x4x4（1082）好——块不是越大越好：",
        "8×8×8 的工作集 56 行 > 32 行（512B），自己把自己挤出缓存。",
        "『最优块尺寸取决于容量 vs 工作集』——Day 97 多配置实验的主菜。"], 12.5)
    b += sline(rx + 10, 496, rx + rw - 10, 496, SOFT, 1.5, dash="6 5")

    b += srect(40, 664, 1000, 54, "white", INK, 2.0, dash="8 7")
    b += mtext(56, 686, [
        "口径：直接映射、无预取、无写缓冲（Day 92 模型）；数字只用于配置之间的对比。4KB 档 5 个配置全部 192 miss（=强制缺失）——",
        "tiled 的收益全部来自『装不装得下』这一个变量；真实硬件的组相联/预取会改变绝对数，但不改变块循环的方向性优势。"], 12)
    save("04-results.svg", w, h, b)


def main():
    fig1()
    fig2()
    fig3()
    fig4()


if __name__ == "__main__":
    main()
