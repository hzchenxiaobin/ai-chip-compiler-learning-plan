#!/usr/bin/env python3
"""第 117 天的 op 计数器（账本）。

统计 .mlir 文件里的 op 数，口径对齐 D114~D116：函数头（func.func）
算 1 条，函数体里每个 op 算 1 条，方言间"胶水"
（builtin.unrealized_conversion_cast）单列。MLIR 打印自定义语法里
`return` 是 func.return 的短印法，计数时归一化。

用法：
    python3 census.py file1.mlir [file2.mlir ...]
"""

from __future__ import annotations

import re
import sys
from collections import Counter

# MLIR 打印时省略方言前缀的 op（短印法 -> 全名）
ALIASES = {
    "return": "func.return",
    "br": "cf.br",
    "cond_br": "cf.cond_br",
}

# 计数行匹配：缩进开头的 [%=] [op.name] —— 块标签（^bb0）和 } 行不会命中
OP_RE = re.compile(r"^\s+(?:%[\w.]+\s*=\s*)?([a-zA-Z_][\w.]*)")
FUNC_RE = re.compile(r"^\s*func\.func\s+@")
CAST_RE = re.compile(r"unrealized_conversion_cast")


def census(path: str) -> dict:
    """返回 {total, by_op, glue, llvm_ops, non_llvm_ops}。"""
    per_op: Counter[str] = Counter()
    glue = 0
    llvm_ops = 0
    non_llvm = 0
    for line in open(path):
        if FUNC_RE.match(line):
            per_op["func.func"] += 1
            continue
        m = OP_RE.match(line)
        if not m:
            continue
        name = ALIASES.get(m.group(1), m.group(1))
        if "." not in name:            # 不是方言 op（如属性行残留），跳过
            continue
        if CAST_RE.search(line):
            glue += 1
            continue
        per_op[name] += 1
        if name.startswith("llvm.") or name == "builtin.module":
            llvm_ops += 1
        else:
            non_llvm += 1
    return {
        "total": sum(per_op.values()) + glue,
        "by_op": dict(per_op),
        "glue": glue,
        "llvm_ops": llvm_ops,
        "non_llvm_ops": non_llvm,
    }


def fmt(path: str, r: dict) -> str:
    lines = [f"{path}: total {r['total']} op（胶水 {r['glue']} 条，"
             f"llvm.* {r['llvm_ops']}，非 llvm 残账 {r['non_llvm_ops']}）"]
    for name, n in sorted(r["by_op"].items()):
        lines.append(f"    {name:<16} x{n}")
    return "\n".join(lines)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("usage: census.py file.mlir [...]")
    for p in sys.argv[1:]:
        print(fmt(p, census(p)))
