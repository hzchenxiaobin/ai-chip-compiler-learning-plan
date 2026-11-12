#!/usr/bin/env python3
"""第 18 天演练场：支配关系、支配树与“定义支配使用”检查。

用法：
    python3 dominator_playground.py                # 菱形 CFG + 一处非法使用
    python3 dominator_playground.py --trace        # 额外打印每轮迭代后的 Dom 集
    python3 dominator_playground.py --shortcut     # 加一条 B2→B6 近路
    python3 dominator_playground.py --loop         # 加一条 B6→B1 回边（构成环）
    python3 dominator_playground.py --add-ghost    # 加一个无人跳转到它的不可达块 G

CFG 用“后继表”表示：键是块名，值是该块的所有后继。
程序用 DEF_USE 表示：每块记录 (定义的变量列表, 使用的变量列表)；
入口参数视作定义在入口块 B0。
"""

import argparse

ENTRY = "B0"

# 菱形 CFG：B1 处分支，B2 这条路与 B3→B4 这条路在 B5 汇合
DIAMOND = {
    "B0": ["B1"],
    "B1": ["B2", "B3"],
    "B2": ["B5"],
    "B3": ["B4"],
    "B4": ["B5"],
    "B5": ["B6"],
    "B6": [],
}

# 每块的语句，简化成 定义/使用 两个集合：
#   B0: x = 输入参数          B3: b = x - 1
#   B1: a = x + 1             B4: s = b + a
#   B2: t = a * 2             B5: u = t + a   ← t 的使用有问题！
#   B6: 输出 u
DEF_USE = {
    "B0": (["x"], []),
    "B1": (["a"], ["x"]),
    "B2": (["t"], ["a"]),
    "B3": (["b"], ["x"]),
    "B4": (["s"], ["b", "a"]),
    "B5": (["u"], ["t", "a"]),
    "B6": ([], ["u"]),
}


def predecessors(cfg):
    preds = {b: [] for b in cfg}
    for b, succs in cfg.items():
        for s in succs:
            preds[s].append(b)
    return preds


def reachable_from(cfg, entry):
    """从 entry 出发能走到的块集合（DFS）。"""
    seen, stack = {entry}, [entry]
    while stack:
        b = stack.pop()
        for s in cfg[b]:
            if s not in seen:
                seen.add(s)
                stack.append(s)
    return seen


def iterative_dominators(cfg, entry, trace=False):
    """迭代法求支配集：Dom(b) = {b} ∪ ⋂_{p∈前驱(b)} Dom(p)。

    只处理从 entry 可达的块：不可达块没有“从入口来的路径”，
    支配关系对它无定义（详见教程第 6 节错误三）。
    其余块初始化为全集——必须从“谁都支配它”开始往小收缩，
    从空集开始会收敛到过小的错误不动点（错误二）。
    """
    live = reachable_from(cfg, entry)
    order = [b for b in cfg if b in live]
    preds = predecessors(cfg)
    dom = {b: ({entry} if b == entry else set(order)) for b in order}
    rounds = 0
    changed = True
    while changed:
        changed = False
        rounds += 1
        for b in order:
            if b == entry:
                continue
            new = set(order)
            for p in preds[b]:
                if p in dom:
                    new &= dom[p]
            new.add(b)
            if new != dom[b]:
                dom[b] = new
                changed = True
        if trace:
            print(f"  -- 第 {rounds} 轮后 --")
            for b in order:
                print(f"     {b}: {{{', '.join(sorted(dom[b]))}}}")
    return dom, rounds


def simple_paths(cfg, entry, target):
    """枚举 entry→target 的全部简单路径（不重复经过任何块）。"""
    paths = []

    def dfs(node, path):
        if node == target:
            paths.append(list(path))
            return
        for s in cfg[node]:
            if s not in path:
                path.append(s)
                dfs(s, path)
                path.pop()

    dfs(entry, [entry])
    return paths


def brute_dominators(cfg, entry):
    """暴力法交叉验证：d 支配 b ⟺ d 出现在每条 entry→b 的简单路径里。

    “所有路径”可以只看“所有简单路径”：任何路径都能剪掉中途的环变成
    简单路径，剪枝只会删块不会加块，所以绕开 d 的路径若存在，
    必存在一条同样绕开 d 的简单路径。
    """
    live = reachable_from(cfg, entry)
    dom = {}
    for b in live:
        common = None
        for p in simple_paths(cfg, entry, b):
            s = set(p)
            common = s if common is None else common & s
        dom[b] = common
    return dom


def idom_of(b, dom, entry):
    """直接支配者：b 的严格支配者中离 b 最近的那个。

    b 的所有严格支配者在“支配”关系下构成一条链，
    离 b 越近的支配者自己被支配得越多、支配集越大，
    所以取 |Dom| 最大的那个就是 idom。先按名字排序再取 max，
    保证在病态图（支配集并列，比如不可达块）下结果也可复现。
    """
    if b == entry:
        return None
    strict = dom[b] - {b}
    return max(sorted(strict), key=lambda d: len(dom[d]))


def dominator_tree(dom, entry):
    """支配树：父节点 = idom；返回 children 映射。"""
    children = {b: [] for b in dom}
    for b in dom:
        if b != entry:
            children[idom_of(b, dom, entry)].append(b)
    for kids in children.values():
        kids.sort()
    return children


def tree_lines(children, node, prefix="", is_last=True, is_root=False):
    """把支配树渲染成带 ├─ └─ 的文本行。"""
    if is_root:
        lines = [node]
        kids = children.get(node, [])
        for i, k in enumerate(kids):
            lines += tree_lines(children, k, "", i == len(kids) - 1)
        return lines
    connector = "└─ " if is_last else "├─ "
    lines = [prefix + connector + node]
    new_prefix = prefix + ("   " if is_last else "│  ")
    kids = children.get(node, [])
    for i, k in enumerate(kids):
        lines += tree_lines(children, k, new_prefix, i == len(kids) - 1)
    return lines


def find_witness_path(cfg, entry, use_block, def_block):
    """找一条 entry→use_block 且不经过 def_block 的简单路径（反例路径）。"""
    for p in simple_paths(cfg, entry, use_block):
        if def_block not in p:
            return p
    return None


def check_def_dominates_use(cfg, entry, dom):
    """检查“每个使用都被它的定义支配”。

    名字只有唯一定义点 d 时：任何使用块 u 必须满足 d ∈ Dom(u)，
    否则存在入口→u 的路径不经过 d，执行到 u 时值还没出生。
    多个定义点需要 φ 函数在汇合处合并版本（今天只报告，不展开）。
    """
    def_sites = {}
    for b, (defs, _) in DEF_USE.items():
        for name in defs:
            def_sites.setdefault(name, []).append(b)

    all_names = set()
    for defs, uses in DEF_USE.values():
        all_names.update(defs)
        all_names.update(uses)

    problems, notes = [], []
    for name in sorted(all_names):
        sites = def_sites.get(name, [])
        users = [b for b, (_, uses) in DEF_USE.items() if name in uses]
        if not users:
            continue
        if not sites:
            problems.append(f"{name} 被使用但没有任何定义")
            continue
        if len(sites) > 1:
            notes.append(f"{name} 定义于 {' 和 '.join(sites)}——多处定义，"
                         f"汇合处需要 φ 函数选择版本，本教程不展开")
            continue
        d = sites[0]
        for u in users:
            if d not in dom.get(u, set()):
                witness = find_witness_path(cfg, entry, u, d)
                w = "→".join(witness) if witness else "（未找到，实现有 bug）"
                problems.append(
                    f"{u} 使用 {name}，但 {name} 定义在 {d}，{d} 不支配 {u}；"
                    f"反例路径 {w} 不经过 {d}，走这条路时 {name} 还没定义")
    return problems, notes


def fmt_set(s):
    return "{" + ", ".join(sorted(s)) + "}"


def main():
    ap = argparse.ArgumentParser(description="支配关系演练场")
    ap.add_argument("--shortcut", action="store_true", help="加一条 B2→B6 的近路")
    ap.add_argument("--loop", action="store_true", help="加一条 B6→B1 的回边（构成环）")
    ap.add_argument("--add-ghost", action="store_true", help="加一个无人跳转到它的不可达块 G")
    ap.add_argument("--trace", action="store_true", help="打印每轮迭代后的 Dom 集")
    args = ap.parse_args()

    cfg = {b: list(succ) for b, succ in DIAMOND.items()}
    extra = []
    if args.shortcut:
        cfg["B2"].append("B6")
        extra.append("近路 B2→B6")
    if args.loop:
        cfg["B6"].append("B1")
        extra.append("回边 B6→B1")
    if args.add_ghost:
        cfg["G"] = ["B5"]
        extra.append("孤块 G→B5")

    print("== [1] CFG（后继表） ==")
    for b, succs in cfg.items():
        print(f"{b} → {', '.join(succs) if succs else '（出口）'}")
    if extra:
        print("在菱形基础上增加：" + "；".join(extra))
    dead = [b for b in cfg if b not in reachable_from(cfg, ENTRY)]
    if dead:
        print("不可达块（没有从入口来的路径，不参与支配计算）：" + "、".join(dead))

    print("\n== [2] 迭代法求支配集：Dom(b) = {b} ∪ ⋂ Dom(前驱) ==")
    if args.trace:
        print("（--trace 打开：每轮结束后打印全部 Dom 集）")
    dom, rounds = iterative_dominators(cfg, ENTRY, trace=args.trace)
    print(f"收敛：{rounds} 轮")
    print(f"{'块':<5}{'支配集 Dom(b)':<20}{'严格支配（去掉自己）':<22}直接支配者 idom")
    for b in sorted(dom):
        strict = fmt_set(dom[b] - {b})
        idom = idom_of(b, dom, ENTRY) or "—（入口）"
        print(f"{b:<5}{fmt_set(dom[b]):<20}{strict:<22}{idom}")

    print("\n== [3] 支配树（父节点 = idom） ==")
    children = dominator_tree(dom, ENTRY)
    for line in tree_lines(children, ENTRY, is_root=True):
        print(line)

    print("\n== [4] 与暴力路径枚举交叉验证 ==")
    bdom = brute_dominators(cfg, ENTRY)
    if bdom == dom:
        print(f"一致：{len(dom)} 个可达块的支配集两种算法完全相同。")
    else:
        print("不一致！两种算法结果不同：")
        for b in sorted(set(dom) | set(bdom)):
            if dom.get(b) != bdom.get(b):
                dv = fmt_set(dom[b]) if b in dom else "无"
                bv = fmt_set(bdom[b]) if b in bdom else "无"
                print(f"  {b}: 迭代法={dv}  路径枚举={bv}")

    print("\n== [5] 检查：定义是否支配使用 ==")
    problems, notes = check_def_dominates_use(cfg, ENTRY, dom)
    for n in notes:
        print("提示：" + n)
    if not problems:
        print("通过：每个使用都被唯一定义支配。")
    else:
        for p in problems:
            print("未通过：" + p)
        print("（存在不被定义支配的使用，编译器应拒绝或要求插入 φ —— 退出码 1）")
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
