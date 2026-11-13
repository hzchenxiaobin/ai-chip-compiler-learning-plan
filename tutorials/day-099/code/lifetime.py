#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第 99 天：Tensor 生命周期分析器。

对一个优化后的计算图（双分支特征块）选择一种拓扑执行顺序，计算：
  1. 每个 Tensor 的定义点（def）、最后使用点（last use）和活跃区间（闭区间）；
  2. 每个执行步骤上同时存活的动态张量与内存量；
  3. 峰值内存，以及全部合法拓扑序的峰值分布；
  4. 一张可打开的 SVG 活跃区间时间线（手绘 sketch 风）。

约定：
  - 步骤编号 1..N 按执行顺序给每个算子编号；
  - 图输入与参数的定义点记为 0（图执行前就存在）；
  - 活跃区间是闭区间 [def, last_use]：算子执行期间输入在被读、输出在被写，
    朴素（非 in-place）实现下它们必须同时占用缓冲区；
  - 图输出没有图内使用者，last_use 记为 N+1（活到图结束之后）；
  - 参数（权重）常驻，单独统计，不计入动态峰值。
"""
from __future__ import annotations

import argparse
import itertools
import sys
from dataclasses import dataclass
from pathlib import Path

DTYPE_NAME = "float32"
DTYPE_BYTES = 4


@dataclass(frozen=True)
class TensorInfo:
    name: str
    kind: str  # input / param / intermediate / output
    shape: tuple


@dataclass(frozen=True)
class Op:
    out: str
    kind: str
    inputs: tuple


def numel(shape: tuple) -> int:
    n = 1
    for d in shape:
        n *= d
    return n


def build_graph(skip_width: int = 128):
    """双分支特征块（教学用缩小版）：
    主干： x --matmul(w_exp)--> t1(256) --matmul(w_dn)--> t2(32)
    捷径： x --matmul(w_sk)--> s(skip_width)
    汇聚： y = concat(t2, s)
    第 8 周的算子融合已把逐元素算子并入 matmul，图中只剩这 4 个算子。
    """
    tensors = {
        "x": TensorInfo("x", "input", (1, 32)),
        "w_exp": TensorInfo("w_exp", "param", (32, 256)),
        "w_dn": TensorInfo("w_dn", "param", (256, 32)),
        "w_sk": TensorInfo("w_sk", "param", (32, skip_width)),
        "t1": TensorInfo("t1", "intermediate", (1, 256)),
        "t2": TensorInfo("t2", "intermediate", (1, 32)),
        "s": TensorInfo("s", "intermediate", (1, skip_width)),
        "y": TensorInfo("y", "output", (1, 32 + skip_width)),
    }
    ops = [
        Op("t1", "matmul", ("x", "w_exp")),
        Op("t2", "matmul", ("t1", "w_dn")),
        Op("s", "matmul", ("x", "w_sk")),
        Op("y", "concat", ("t2", "s")),
    ]
    return tensors, ops


ORDER_PRESETS = {
    "main-first": ("主干优先", ("t1", "t2", "s", "y")),
    "interleaved": ("交错", ("t1", "s", "t2", "y")),
    "skip-first": ("捷径优先", ("s", "t1", "t2", "y")),
}


def is_valid_order(order: tuple, tensors: dict, ops: dict) -> bool:
    produced = {name for name, t in tensors.items() if t.kind in ("input", "param")}
    for out in order:
        if out not in ops:
            return False
        for arg in ops[out].inputs:
            if arg not in produced:
                return False
        produced.add(out)
    return all(t.kind != "intermediate" or t.name in order for t in tensors.values())


def all_valid_orders(tensors: dict, ops: dict) -> list:
    names = [op.out for op in ops.values()] if isinstance(ops, dict) else [op.out for op in ops]
    return [o for o in itertools.permutations(names) if is_valid_order(o, tensors, ops)]


def compute_intervals(order: tuple, tensors: dict, ops: dict) -> dict:
    """返回 {tensor: (def, last_use)}，闭区间；输入/参数 def=0；输出 last_use=N+1。"""
    pos = {out: i + 1 for i, out in enumerate(order)}
    n = len(order)
    intervals = {}
    for name, t in tensors.items():
        if t.kind in ("input", "param"):
            d = 0
        else:
            d = pos[name]                                   # 定义点 = 产生它的算子
        uses = [pos[out] for out, op in ops.items() if name in op.inputs]
        if uses:
            last = max(uses)                                # 最后使用点 = 使用步的最大值
        elif t.kind == "output":
            last = n + 1                                    # 图输出活到图结束之后
        else:
            raise ValueError(f"中间张量 {name} 没有任何使用者（死代码）")
        intervals[name] = (d, last)
    return intervals


def dynamic_live_at(step: int, intervals: dict, tensors: dict) -> list:
    return [
        name
        for name, (d, u) in intervals.items()
        if tensors[name].kind != "param" and d <= step <= u
    ]


def peak_and_steps(order: tuple, intervals: dict, tensors: dict):
    """按区间定义计算每个步骤的动态活跃内存，返回 (峰值元素数, 峰值步列表, 每步明细)。"""
    per_step = {}
    for step in range(1, len(order) + 1):
        live = dynamic_live_at(step, intervals, tensors)
        per_step[step] = (live, sum(numel(tensors[n].shape) for n in live))
    peak = max(v for _, v in per_step.values())
    steps = sorted(k for k, (_, v) in per_step.items() if v == peak)
    return peak, steps, per_step


def simulate_peak(order: tuple, tensors: dict, ops: dict) -> int:
    """独立复核：事件驱动模拟——定义点出生、最后使用步之后死亡，逐步累计峰值。"""
    n = len(order)
    pos = {out: i + 1 for i, out in enumerate(order)}
    births, deaths = {}, {}
    for name, t in tensors.items():
        if t.kind == "param":
            continue
        d = 0 if t.kind == "input" else pos[name]
        uses = [pos[o] for o, op in ops.items() if name in op.inputs]
        if t.kind == "output":
            uses = [n + 1]
        births.setdefault(d, []).append(name)
        deaths.setdefault(max(uses), []).append(name)
    alive, peak = set(), 0
    for step in range(0, n + 2):
        for name in births.get(step, []):
            alive.add(name)
        peak = max(peak, sum(numel(tensors[a].shape) for a in alive))
        for name in deaths.get(step, []):
            alive.discard(name)
    return peak


def verify(order: tuple, tensors: dict, ops: dict) -> list:
    checks = []

    def ok(msg):
        checks.append(("通过", msg))

    def bad(msg):
        checks.append(("失败", msg))

    if is_valid_order(order, tensors, ops):
        ok("拓扑合法性：每个算子的输入都由更早的算子或图输入提供")
    else:
        bad("拓扑不合法：存在输入未就绪就被调度的算子")
        return checks

    intervals = compute_intervals(order, tensors, ops)
    pos = {out: i + 1 for i, out in enumerate(order)}
    for name, t in tensors.items():
        d, u = intervals[name]
        uses = [pos[o] for o, op in ops.items() if name in op.inputs]
        if t.kind == "output":
            uses = [len(order) + 1]
        if uses and u != max(uses):
            bad(f"{name}: last_use={u} ≠ 实际最大使用步 {max(uses)}")
        elif not uses and t.kind != "output":
            bad(f"{name}: 无使用者却不是图输出")
        elif any(not (d <= step <= u) for step in uses):
            bad(f"{name}: 存在使用步落在区间 [{d},{u}] 之外")
        elif t.kind in ("input", "param") and d != 0:
            bad(f"{name}: 输入/参数定义点应为 0，实际 {d}")
        else:
            ok(f"{name}: 区间 [{d},{u}] 覆盖全部使用步，def/last_use 一致")

    peak, _, _ = peak_and_steps(order, intervals, tensors)
    sim = simulate_peak(order, tensors, ops)
    if peak == sim:
        ok(f"峰值交叉验证：区间法 = 事件模拟法 = {peak} 元素")
    else:
        bad(f"峰值交叉验证不一致：区间法 {peak} ≠ 模拟法 {sim}")
    return checks


# ---------------------------------------------------------------- 输出：文本报告

KIND_CN = {"input": "输入", "param": "参数(常驻)", "intermediate": "中间", "output": "输出"}


def print_report(order_name: str, order: tuple, tensors: dict, ops: dict, out=sys.stdout):
    intervals = compute_intervals(order, tensors, ops)
    peak, steps, per_step = peak_and_steps(order, intervals, tensors)
    n = len(order)

    w = out.write
    w("=" * 72 + "\n")
    w(f"执行顺序「{order_name}」：{' → '.join(order)}   （共 {n} 个算子，步骤 1..{n}）\n")
    w("=" * 72 + "\n\n")

    w("-- 生命周期表（活跃区间为闭区间 [def, last_use]）--\n")
    w(f"{'张量':<6}{'类别':<10}{'形状':<12}{'元素':>7}{'字节':>8}"
      f"{'def':>6}{'last_use':>10}{'活跃区间':>12}\n")
    for name in tensors:
        t = tensors[name]
        d, u = intervals[name]
        last_txt = f"{u}(图结束)" if t.kind == "output" and u == n + 1 else str(u)
        w(f"{name:<6}{KIND_CN[t.kind]:<10}{str(t.shape):<12}{numel(t.shape):>7}"
          f"{numel(t.shape) * DTYPE_BYTES:>8}{d:>6}{last_txt:>10}{f'[{d}, {u}]':>12}\n")

    param_elems = sum(numel(t.shape) for t in tensors.values() if t.kind == "param")
    w(f"\n参数合计 {param_elems} 元素（{param_elems * DTYPE_BYTES} B）常驻，"
      f"不计入下面的动态峰值。\n\n")

    w("-- 每步活跃内存（动态张量：输入 + 中间 + 输出）--\n")
    w(f"{'步骤':<5}{'执行的算子':<26}{'存活的动态张量':<20}{'元素':>7}{'字节':>8}\n")
    for step in range(1, n + 1):
        out_name = order[step - 1]
        op = ops[out_name]
        live, elems = per_step[step]
        mark = "   ← 峰值" if step in steps else ""
        op_txt = "%s = %s(%s)" % (out_name, op.kind, ", ".join(op.inputs))
        w("%-5s%-26s%-20s%7d%8d%s\n" % (step, op_txt, ", ".join(live), elems,
                                         elems * DTYPE_BYTES, mark))
    w(f"\n步骤 0（图前）存活：{', '.join(dynamic_live_at(0, intervals, tensors))}"
      f" = {sum(numel(tensors[x].shape) for x in dynamic_live_at(0, intervals, tensors))} 元素；"
      f"步骤 {n + 1}（图后）存活：{', '.join(dynamic_live_at(n + 1, intervals, tensors))}"
      f"（图输出）。\n")

    w("\n-- 活跃区间条（█ 存活；D 在此步定义；K 在此步最后使用后死亡）--\n")
    head = f"{'':<10}" + "".join(
        f"{'图前' if i == 0 else '图后' if i == n + 1 else order[i - 1]:>7}" for i in range(n + 2)
    )
    w(head + "\n")
    for name, t in tensors.items():
        if t.kind == "param":
            continue
        d, u = intervals[name]
        row = f"{name:<10}"
        for i in range(n + 2):
            if not (d <= i <= u):
                row += f"{'·':>7}"
            elif i == d and i != 0:
                row += f"{'D':>7}"
            elif i == u and not (t.kind == "output" and u == n + 1):
                row += f"{'K':>7}"
            else:
                row += f"{'█':>7}"
        w(row + "\n")
    sums = []
    for i in range(n + 2):
        live = dynamic_live_at(i, intervals, tensors)
        sums.append(sum(numel(tensors[x].shape) for x in live))
    w(f"{'动态合计':<10}" + "".join(f"{v:>7}" for v in sums) + "   （元素）\n")

    w(f"\n峰值内存 = {peak} 元素（{peak * DTYPE_BYTES} B），出现在步骤 "
      f"{', '.join(map(str, steps))}。\n\n")

    w("-- 校验 --\n")
    checks = verify(order, tensors, ops)
    for status, msg in checks:
        w(f"[{status}] {msg}\n")
    failed = [c for c in checks if c[0] == "失败"]
    w(f"校验结果：{len(checks) - len(failed)}/{len(checks)} 项通过"
      + ("" if not failed else "（存在失败项！）") + "\n\n")
    return peak, steps


def print_all_orders(tensors: dict, ops: dict, out=sys.stdout):
    w = out.write
    rows = []
    for order in all_valid_orders(tensors, ops):
        intervals = compute_intervals(order, tensors, ops)
        peak, steps, _ = peak_and_steps(order, intervals, tensors)
        rows.append((order, peak, steps))
    rows.sort(key=lambda r: r[1])
    best, worst = rows[0][1], rows[-1][1]
    w("-- 全部合法拓扑序的峰值分布 --\n")
    w(f"约束：t1 必须先于 t2；t2 和 s 都必须先于 y。共 {len(rows)} 种合法顺序。\n\n")
    w(f"{'#':<4}{'执行顺序':<26}{'峰值(元素)':>10}{'峰值(字节)':>10}{'峰值步':>10}\n")
    for i, (order, peak, steps) in enumerate(rows, 1):
        tag = ""
        if peak == best:
            tag = "   ← 最低"
        elif peak == worst and worst > best:
            tag = "   ← 最高"
        w(f"{i:<4}{' → '.join(order):<26}{peak:>10}{peak * DTYPE_BYTES:>10}"
          f"{', '.join(map(str, steps)):>10}{tag}\n")
    if worst > best:
        w(f"\n最低 {best} vs 最高 {worst} 元素：仅调换执行顺序，峰值相差 "
          f"{(worst - best) * DTYPE_BYTES} B（+{(worst / best - 1) * 100:.0f}%）。\n")
    return rows


# ---------------------------------------------------------------- 输出：SVG

SKETCH_FILTER = """  <filter id="sketch">
    <feTurbulence type="fractalNoise" baseFrequency="0.018" numOctaves="2" seed="11" result="n"/>
    <feDisplacementMap in="SourceGraphic" in2="n" scale="3.2"/>
  </filter>"""


def svg_timeline(order_name: str, order: tuple, tensors: dict, ops: dict) -> str:
    intervals = compute_intervals(order, tensors, ops)
    peak, steps, per_step = peak_and_steps(order, intervals, tensors)
    n = len(order)
    dyn = [name for name, t in tensors.items() if t.kind != "param"]
    param_elems = sum(numel(t.shape) for t in tensors.values() if t.kind == "param")

    label_w, col_w, row_h = 168, 122, 46
    x0, y_head, y_rows = 24, 118, 158
    width = x0 + label_w + (n + 2) * col_w + 16
    height = y_rows + len(dyn) * row_h + 78
    col_x = lambda i: x0 + label_w + i * col_w
    bar = []

    bar.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
               f'font-family="\'Comic Sans MS\',\'Kaiti SC\',\'KaiTi\',\'STKaiti\',cursive">')
    bar.append(f"<style>text {{ fill:#3B3B3B; }} .t {{ font-size:23px; font-weight:bold; }}"
               ".s { font-size:13.5px; fill:#6b6257; } .h { font-size:13px; font-weight:bold; }"
               ".n { font-size:15px; font-weight:bold; } .d { font-size:11.5px; fill:#5a554d; }"
               ".v { font-size:13.5px; font-weight:bold; }"
               ".box { stroke:#3B3B3B; stroke-width:2; stroke-linecap:round; stroke-linejoin:round; }"
               "</style>")
    bar.append(SKETCH_FILTER)
    bar.append(f'<rect x="4" y="4" width="{width - 8}" height="{height - 8}" rx="14" '
               f'fill="#FDFBF6" stroke="#E7DFCE" stroke-width="2"/>')
    bar.append('<g filter="url(#sketch)">')

    bar.append(f'<text x="{width / 2:.0f}" y="40" text-anchor="middle" class="t">'
               f'执行顺序「{order_name}」：{" → ".join(order)}</text>')
    bar.append(f'<path d="M {width / 2 - 240},50 Q {width / 2},46 {width / 2 + 240},51" '
               f'stroke="#E8A87C" stroke-width="3" fill="none" stroke-linecap="round"/>')
    bar.append(f'<text x="{width / 2:.0f}" y="68" text-anchor="middle" class="s">'
               f'活跃区间 = [定义点, 最后使用点]（闭区间）· 峰值只计动态张量，参数 '
               f'{param_elems} 元素常驻另计</text>')

    heads = ["图前"] + [f"{order[i]}" for i in range(n)] + ["图后"]
    subs = [""] + [f"{ops[order[i]].kind}" for i in range(n)] + ["输出"]
    for i, (h, s) in enumerate(zip(heads, subs)):
        cx = col_x(i) + col_w / 2
        hl = (i in steps)
        if hl:
            bar.append(f'<rect x="{col_x(i) + 4}" y="{y_head - 26}" width="{col_w - 8}" '
                       f'height="{y_rows + len(dyn) * row_h - y_head + 20}" rx="8" '
                       f'fill="#E8A87C" fill-opacity="0.30" stroke="#D98484" '
                       f'stroke-width="1.6" stroke-dasharray="7 5"/>')
        hl_color = ' fill="#D98484"' if hl else ""
        bar.append(f'<text x="{cx:.0f}" y="{y_head - 6}" text-anchor="middle" class="h"'
                   f'{hl_color}>步骤 {i}</text>')
        bar.append(f'<text x="{cx:.0f}" y="{y_head + 12}" text-anchor="middle" class="n">{h}</text>')
        bar.append(f'<text x="{cx:.0f}" y="{y_head + 28}" text-anchor="middle" class="d">'
                   f'{s if s else " "}</text>')

    for r, name in enumerate(dyn):
        t = tensors[name]
        d, u = intervals[name]
        cy = y_rows + r * row_h
        bar.append(f'<text x="{x0 + 8}" y="{cy + 19}" class="n">{name}'
                   f'<tspan class="d">  {str(t.shape)} · {numel(t.shape)} 元素</tspan></text>')
        bx, bw = col_x(d) + 6, (u - d + 1) * col_w - 12
        bar.append(f'<rect x="{bx}" y="{cy + 4}" width="{bw}" height="26" rx="9" '
                   f'fill="#7FA8D9" fill-opacity="0.45" stroke="#3B3B3B" stroke-width="2.2"/>')
        if d != 0:
            bar.append(f'<text x="{bx + 12}" y="{cy + 23}" class="v">D</text>')
        if not (t.kind == "output" and u == n + 1):
            bar.append(f'<text x="{bx + bw - 12}" y="{cy + 23}" text-anchor="end" class="v">K</text>')

    sum_y = y_rows + len(dyn) * row_h + 14
    bar.append(f'<path d="M {x0},{sum_y - 6} Q {width / 2:.0f},{sum_y - 2} {width - 20},{sum_y - 6}" '
               f'stroke="#3B3B3B" stroke-width="1.8" fill="none"/>')
    bar.append(f'<text x="{x0 + 8}" y="{sum_y + 16}" class="n">动态合计（元素）</text>')
    for i in range(n + 2):
        live = dynamic_live_at(i, intervals, tensors)
        v = sum(numel(tensors[x].shape) for x in live)
        cx = col_x(i) + col_w / 2
        color = "#D98484" if i in steps else "#3B3B3B"
        bar.append(f'<text x="{cx:.0f}" y="{sum_y + 16}" text-anchor="middle" class="v" '
                   f'fill="{color}">{v}</text>')
    bar.append(f'<text x="{width / 2:.0f}" y="{sum_y + 44}" text-anchor="middle" class="s">'
               f'峰值 {peak} 元素（{peak * DTYPE_BYTES} B）出现在步骤 '
               f'{", ".join(map(str, steps))}；D=定义点，K=最后使用点</text>')
    bar.append("</g>\n</svg>")
    return "\n".join(bar)


# ---------------------------------------------------------------- main

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="第 99 天：Tensor 生命周期分析器")
    parser.add_argument("--order", default="main-first",
                        choices=["main-first", "interleaved", "skip-first", "all"],
                        help="执行顺序预设，或 all 枚举全部合法拓扑序")
    parser.add_argument("--skip-width", type=int, default=128,
                        help="捷径投影输出宽度（元素数），默认 128")
    parser.add_argument("--svg-prefix", default=None,
                        help="把每个顺序的时间线 SVG 写到该前缀路径（如 outputs/timeline）")
    args = parser.parse_args(argv)

    tensors, op_list = build_graph(args.skip_width)
    ops = {op.out: op for op in op_list}

    if args.order == "all":
        print_all_orders(tensors, ops)
        return 0

    name, order = ORDER_PRESETS[args.order]
    print_report(name, order, tensors, ops)
    if args.svg_prefix:
        path = Path(f"{args.svg_prefix}-{args.order}.svg")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(svg_timeline(name, order, tensors, ops), encoding="utf-8")
        print(f"SVG 时间线已写入：{path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
