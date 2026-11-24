#!/usr/bin/env python3
"""第 19 天演练场：线性计算图的活跃区间、峰值内存与缓冲区复用。

用法：
    python3 live_range_playground.py                    # 默认：11 个值的线性图
    python3 live_range_playground.py --late-constant    # 把常量的创建挪到首次使用之前
    python3 live_range_playground.py --no-dead          # 先删掉死值（预演 Day 25 的 DCE）
    python3 live_range_playground.py --no-reuse         # 每个值单独一块缓冲区（不复用）

图用“语句序列”表示：每条语句定义至多一个值、使用若干值（Day 17 的 SSA + Use-Def）。
语句位置从 S1 开始编号；图输出当成一条 output 语句，算作该值的最后一次使用。
活跃区间采用保守口径：[定义位置, 最后使用位置] 闭区间，两端都算“占着内存”——
同一条语句“边读旧值边写新值”视为重叠，不允许共享缓冲区（matmul 之类的算子
把结果写进自己输入的内存并不安全）。
"""

import argparse

FP32 = 4  # 每个 fp32 元素 4 字节

# (op, 结果值, 使用的值, shape)；None 表示 output 语句不定义值
BASE_GRAPH = [
    ("input",     "%a",   [],           (2, 3)),
    ("input",     "%b",   [],           (3, 2)),
    ("input",     "%w",   [],           (2, 2)),
    ("const 0.5", "%s",   [],           (2, 2)),
    ("matmul",    "%c",   ["%a", "%b"], (2, 2)),
    ("add",       "%d",   ["%c", "%w"], (2, 2)),
    ("relu",      "%e",   ["%d"],       (2, 2)),
    ("mul",       "%f",   ["%e", "%s"], (2, 2)),
    ("add",       "%h",   ["%e", "%s"], (2, 2)),
    ("relu",      "%z",   ["%e"],       (2, 2)),   # ← %z 从未被使用：死值
    ("add",       "%out", ["%f", "%h"], (2, 2)),
    ("output",    None,   ["%out"],     None),
]

PURE_OPS = {"matmul", "add", "relu", "mul"}  # 无副作用，删掉不影响图输出


def shape_bytes(shape):
    if shape is None:
        return 0
    n = 1
    for d in shape:
        n *= d
    return n * FP32


def fmt_shape(shape):
    return "×".join(str(d) for d in shape) if shape else "标量"


def count_uses(graph):
    """每个值被使用的次数（按语句位置收集）。"""
    used_at = {}
    for i, (_, _, uses, _) in enumerate(graph):
        for u in uses:
            used_at.setdefault(u, []).append(i)
    return used_at


def drop_dead(graph):
    """删除“结果从未被使用”的纯算子语句（一遍遍删到稳定，防连锁死代码）。"""
    graph = [list(s) for s in graph]
    changed = True
    while changed:
        changed = False
        used_at = count_uses(graph)
        for i, (op, res, _, _) in enumerate(graph):
            if res is not None and res not in used_at and op in PURE_OPS:
                del graph[i]
                changed = True
                break
    return [tuple(s) for s in graph]


def hoist_constants(graph):
    """把常量语句挪到“首次使用它的语句”紧前面，缩短活跃区间。"""
    graph = [list(s) for s in graph]
    used_at = count_uses(graph)
    for i, (op, res, _, _) in enumerate(graph):
        if op.startswith("const") and not graph[i][2] and res in used_at:
            first_use = min(used_at[res])
            if first_use > i + 1:  # 只有隔得远才值得挪
                stmt = graph.pop(i)
                graph.insert(first_use - 1, stmt)
                break  # 重新计算使用位置后再继续（本图只有一个常量）
    return [tuple(s) for s in graph]


def analyze(graph):
    """返回 labels 与每个值的 (定义位置, 使用位置列表, 字节数)。"""
    labels = [f"S{i + 1}" for i in range(len(graph))]
    info = {}
    for i, (_, res, _, shape) in enumerate(graph):
        if res is not None:
            assert res not in info, f"{res} 被定义了两次（违反 SSA）"
            info[res] = {"def": i, "uses": [], "bytes": shape_bytes(shape)}
    for i, (_, _, uses, _) in enumerate(graph):
        for u in uses:
            assert u in info, f"{u} 被使用但从未定义"
            assert info[u]["def"] < i, f"{u} 在定义之前被使用（图没有排好序）"
            info[u]["uses"].append(i)
    return labels, info


def live_interval(v):
    """闭区间 [def, last]；死值返回 [def, def]（结果还是被写进了缓冲区）。"""
    d = v["def"]
    last = max(v["uses"]) if v["uses"] else d
    return d, last


def live_bytes_at(graph, info, i):
    """语句 i 执行时活跃的总字节数（含正在写入的结果）。"""
    total = 0
    for v in info.values():
        d, last = live_interval(v)
        if d <= i <= last:
            total += v["bytes"]
    return total


def plan_pool(graph, info, reuse=True):
    """按定义顺序做 first-fit 缓冲区规划。

    保守复用规则：缓冲区上一任的“最后使用”必须严格早于新值的“定义”，
    即两条活跃区间完全不重叠；缓冲区大小取首个入住者的字节数。
    """
    order = sorted(info, key=lambda name: info[name]["def"])
    buffers = []  # 每项: {"size": int, "slots": [(name, d, last)]}
    for name in order:
        v = info[name]
        d, last = live_interval(v)
        placed = False
        if reuse:
            for buf in buffers:
                if buf["size"] >= v["bytes"] and all(l < d for (_, _, l) in buf["slots"]):
                    buf["slots"].append((name, d, last))
                    placed = True
                    break
        if not placed:
            buffers.append({"size": v["bytes"], "slots": [(name, d, last)]})
    return buffers


def main():
    ap = argparse.ArgumentParser(description="活跃区间演练场")
    ap.add_argument("--late-constant", action="store_true",
                    help="把常量的创建挪到首次使用之前")
    ap.add_argument("--no-dead", action="store_true",
                    help="先删掉死值（预演 Day 25 的 DCE）")
    ap.add_argument("--no-reuse", action="store_true",
                    help="每个值单独一块缓冲区（不复用）")
    args = ap.parse_args()

    graph = [tuple(s) for s in BASE_GRAPH]
    notes = []
    if args.late_constant:
        graph = hoist_constants(graph)
        notes.append("常量创建被挪到首次使用之前（--late-constant）")
    if args.no_dead:
        before = len(graph)
        graph = drop_dead(graph)
        notes.append(f"先删掉死值再分析（--no-dead）：{before} 条语句 → {len(graph)} 条")

    labels, info = analyze(graph)

    print("== [1] 线性计算图（已排好的执行顺序） ==")
    for i, (op, res, uses, shape) in enumerate(graph):
        lhs = f"{res:<5}= " if res else "  →   "
        rhs = op if not uses else f"{op}({', '.join(uses)})"
        meta = f"shape {fmt_shape(shape)}" if shape else "图输出"
        b = shape_bytes(shape)
        btxt = f"   {b} B" if b else ""
        print(f"{labels[i]:<5}{lhs}{rhs:<24}{meta:<10}{btxt}")
    for n in notes:
        print("（" + n + "）")

    print("\n== [2] 活跃区间表：每个值的首次和最后使用 ==")
    print(f"{'值':<6}{'定义':<7}{'首次使用':<10}{'最后使用':<10}{'活跃区间':<20}{'字节':<6}备注")
    for name in sorted(info, key=lambda n: info[n]["def"]):
        v = info[name]
        d, last = live_interval(v)
        if not v["uses"]:
            interval, remark = "（死值：只写不读）", "从未被使用 ← 死代码"
        else:
            interval = f"[{labels[d]}, {labels[last]}]"
            remark = f"被使用 {len(v['uses'])} 次" if len(v["uses"]) > 1 else ""
            if labels[last] == labels[len(graph) - 1]:
                remark = (remark + "；" if remark else "") + "图输出"
        print(f"{name:<6}{labels[d]:<7}{labels[v['uses'][0]] if v['uses'] else '—':<10}"
              f"{labels[max(v['uses'])] if v['uses'] else '—':<10}{interval:<20}{v['bytes']:<6}{remark}")

    print("\n== [3] 每条语句执行时的活跃内存（含正在写入的结果） ==")
    curve = [live_bytes_at(graph, info, i) for i in range(len(graph))]
    peak_b = max(curve)
    peak_at = [labels[i] for i, b in enumerate(curve) if b == peak_b]
    for i, b in enumerate(curve):
        mark = "  ← 峰值" if b == peak_b else ""
        print(f"{labels[i]:<5}{b:>4} B  {'█' * (b // 8)}{mark}")
    print(f"峰值：{peak_b} B（出现在 {'、'.join(peak_at)}）")

    print("\n== [4] 缓冲区规划：区间完全不重叠才复用（保守规则） ==")
    buffers = plan_pool(graph, info, reuse=not args.no_reuse)
    for k, buf in enumerate(buffers, 1):
        chain = " → ".join(f"{name}[{labels[d]}..{labels[l]}]" for name, d, l in buf["slots"])
        print(f"buf{k}（{buf['size']} B）: {chain}")
    pool = sum(buf["size"] for buf in buffers)
    naive = sum(v["bytes"] for v in info.values())
    mode = "每个值单独一块" if args.no_reuse else "保守复用"
    print(f"模式：{mode}")
    print(f"每个值单独分配合计：{naive} B；缓冲区池子合计：{pool} B"
          f"（{'节省' if naive > pool else '相差'} {abs(naive - pool)} B）")

    print("\n== [5] 检查与发现 ==")
    dead = [n for n in info if not info[n]["uses"]]
    multi = [n for n in info if len(info[n]["uses"]) > 1]
    outputs = [n for n in info if info[n]["uses"] and info[n]["uses"][-1] == len(graph) - 1]
    if dead:
        print("死值：" + "、".join(f"{n}（{labels[info[n]['def']]} 定义，从未被使用）" for n in dead)
              + " —— Day 20 的未使用分析、Day 25 的 DCE 会处理它")
    else:
        print("死值：无（本图没有只写不读的值）")
    print("多次使用的值：" + "、".join(f"{n}（{len(info[n]['uses'])} 次）" for n in multi)
          + " —— 活跃区间必须延伸到最后一次使用" if multi else "多次使用的值：无")
    print("图输出：" + "、".join(f"{n}（最后使用是输出语句 {labels[len(graph) - 1]}）" for n in outputs))
    if dead:
        wasted = sum(info[n]["bytes"] for n in dead)
        print(f"死值白白占用的分配量：{wasted} B（它们的结果被写进内存，却从未被读过）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
