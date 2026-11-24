#!/usr/bin/env python3
"""第 17 天演练场：直线程序的 SSA 化 + Use-Def 表 + 常量传播 + 死代码消除。

用法：
    python3 ssa_playground.py                  # 默认只把 d1 当作输出
    python3 ssa_playground.py --outputs d1,e1  # 让 e1 也变成被观察的输出
    python3 ssa_playground.py --outputs ""     # 没有任何输出 -> 全部是死代码

语句用元组表示：(被赋值变量, 右边表达式)
右边表达式递归定义为三种节点：
    ("const", 整数)                     常量
    ("var", 变量名)                      变量使用
    (运算符, 左表达式, 右表达式)          二元运算，支持 + - *
"""

import argparse

# 原程序：S1~S7，变量 a 被赋值 3 次，e 从未被使用
ORIGINAL = [
    ("a", ("const", 1)),                          # S1  a = 1
    ("b", ("const", 2)),                          # S2  b = 2
    ("a", ("+", ("var", "a"), ("var", "b"))),     # S3  a = a + b
    ("c", ("*", ("var", "a"), ("const", 3))),     # S4  c = a * 3
    ("e", ("+", ("var", "a"), ("const", 100))),   # S5  e = a + 100
    ("a", ("-", ("var", "c"), ("const", 1))),     # S6  a = c - 1
    ("d", ("+", ("var", "a"), ("var", "b"))),     # S7  d = a + b
]


def fmt(expr, env=None):
    """把表达式打印成文本；给定 env 时把已知值代入，便于展示传播过程。"""
    if expr[0] == "const":
        return str(expr[1])
    if expr[0] == "var":
        name = expr[1]
        return str(env[name]) if env is not None and name in env else name
    return f"{fmt(expr[1], env)} {expr[0]} {fmt(expr[2], env)}"


def collect_vars(expr):
    """收集一条表达式里使用的全部变量名。"""
    if expr[0] == "const":
        return []
    if expr[0] == "var":
        return [expr[1]]
    return collect_vars(expr[1]) + collect_vars(expr[2])


def to_ssa(program):
    """直线程序的 SSA 改写。

    规则只有两条，且顺序固定：
      1. 右边的『使用』换成该变量当前版本；
      2. 左边的『定义』领取下一个新版本。
    所以 a = a + b 会改写成 a2 = a1 + b1，右边用的是旧版本。
    """
    current = {}
    ssa = []
    for idx, (lhs, rhs) in enumerate(program, start=1):
        rewritten = rewrite_uses(rhs, current)
        current[lhs] = current.get(lhs, 0) + 1
        ssa.append((f"{lhs}{current[lhs]}", rewritten, idx))
    return ssa


def rewrite_uses(expr, current):
    if expr[0] == "const":
        return expr
    if expr[0] == "var":
        if expr[1] not in current:
            raise SystemExit(f"错误：语句使用了未定义变量 {expr[1]}")
        return ("var", f"{expr[1]}{current[expr[1]]}")
    return (expr[0], rewrite_uses(expr[1], current), rewrite_uses(expr[2], current))


def use_def(ssa):
    """返回两张表：每个 SSA 值定义在哪条语句、被哪些语句使用。"""
    defs, uses = {}, {}
    for name, rhs, idx in ssa:
        defs[name] = idx
        for v in collect_vars(rhs):
            uses.setdefault(v, []).append(idx)
    return defs, uses


def check_ssa(ssa):
    """检查两条 SSA 性质：单赋值；定义先于使用（直线代码的最低要求）。"""
    defs, uses = use_def(ssa)
    problems = []
    names = [name for name, _, _ in ssa]
    if len(names) != len(set(names)):
        problems.append("存在同一个名字被定义多次")
    for user, stmts in uses.items():
        if user not in defs:
            problems.append(f"{user} 被使用但从未定义")
            continue
        for s in stmts:
            if s <= defs[user]:
                problems.append(f"S{s} 使用 {user}，但定义不早于使用（S{defs[user]}）")
    return problems


def const_prop(ssa):
    """SSA 常量传播：直线 SSA 按序遍历一次，每个值查唯一定义即可确定。"""
    env, rows = {}, []
    for name, rhs, idx in ssa:
        value = eval_expr(rhs, env)
        if rhs[0] == "const":
            rows.append(f"S{idx}  {name} = {value}")
        else:
            rows.append(f"S{idx}  {name} = {fmt(rhs)} = {fmt(rhs, env)} = {value}")
        env[name] = value
    return env, rows


def eval_expr(expr, env):
    if expr[0] == "const":
        return expr[1]
    if expr[0] == "var":
        return env[expr[1]]
    left, right = eval_expr(expr[1], env), eval_expr(expr[2], env)
    return {"+": left + right, "-": left - right, "*": left * right}[expr[0]]


def dce(ssa, outputs):
    """SSA 死代码消除：从输出出发反查，够不着的值就是死代码。"""
    defs, uses = use_def(ssa)
    rhs_of = {name: rhs for name, rhs, _ in ssa}
    missing = [o for o in outputs if o not in defs]
    live, stack = set(), [o for o in outputs if o in defs]
    while stack:
        name = stack.pop()
        if name in live:
            continue
        live.add(name)
        for v in collect_vars(rhs_of[name]):
            if v not in live:
                stack.append(v)
    kept = [(n, r, i) for n, r, i in ssa if n in live]
    removed = [n for n, _, _ in ssa if n not in live]
    return kept, removed, missing, uses


def main():
    ap = argparse.ArgumentParser(description="SSA 演练场")
    ap.add_argument("--outputs", default="d1",
                    help="逗号分隔的输出 SSA 值；空字符串表示程序没有任何输出")
    args = ap.parse_args()
    outputs = [o.strip() for o in args.outputs.split(",") if o.strip()]

    print("== [1] 原程序 ==")
    for idx, (lhs, rhs) in enumerate(ORIGINAL, start=1):
        print(f"S{idx}  {lhs} = {fmt(rhs)}")

    ssa = to_ssa(ORIGINAL)
    print("\n== [2] SSA 版本 ==")
    for name, rhs, idx in ssa:
        print(f"S{idx}  {name} = {fmt(rhs)}")

    defs, uses = use_def(ssa)
    print("\n== [3] Use-Def 对照表 ==")
    print(f"{'SSA值':<6}{'定义于':<8}使用于")
    for name, _, idx in ssa:
        markers = [f"S{s}" for s in uses.get(name, [])]
        if name in outputs:
            markers.append("(输出)")
        if not markers:
            markers.append("(无)")
        print(f"{name:<6}S{idx:<7}{'、'.join(markers)}")

    print("\n== [4] SSA 合法性检查 ==")
    problems = check_ssa(ssa)
    if problems:
        for p in problems:
            print(f"未通过：{p}")
        print("SSA 检查未通过，已停止后续优化步骤。")
        return 1
    print("通过：每个 SSA 值只有 1 个定义，且定义先于使用。")

    env, rows = const_prop(ssa)
    print("\n== [5] 常量传播（在 SSA 上一次正向遍历） ==")
    for row in rows:
        print(row)

    kept, removed, missing, uses = dce(ssa, outputs)
    print(f"\n== [6] 死代码消除（输出集合 = {{{', '.join(outputs) or '空'}}}） ==")
    for p in missing:
        print(f"注意：{p} 不是程序里的值，已忽略")
    if removed:
        print("删除：" + "、".join(removed))
    else:
        print("删除：无")
    print(f"保留 {len(kept)} 条语句：" + ("、".join(n for n, _, _ in kept) or "（空）"))


if __name__ == "__main__":
    main()
