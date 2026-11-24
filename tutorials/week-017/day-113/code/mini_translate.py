#!/usr/bin/env python3
"""教学版 mlir-translate：把 LLVM Dialect（MLIR）子集导出成 LLVM IR。

真实工具链：mlir-translate --mlir-to-llvmir 覆盖整个 LLVM Dialect。
本环境没有 mlir-translate（见 README 第 1 节），所以实现一个只覆盖
第 113 天例子里 9 个 op 的教学版，刻意复刻真实导出的三条关键规则：

  R1  重编号：MLIR 侧的值名（%five）和块名（^hi）不跨语言保留，
      LLVM IR 侧按"槽位"顺序编号（%2、%6…），函数参数从 %0 起；
      未命名的基本块和指令结果共用同一个编号池（真实 LLVM 行为，
      本教程用 llvmlite 实验验证过，见 README 5.3）；
  R2  常量内联：llvm.mlir.constant 的结果在 LLVM IR 里直接写成
      立即数字面量（2、3、4、0），不再产生名字，也不占槽位；
  R3  块参数变 phi：MLIR 用块参数（^merge(%m: i32)）在块间传值，
      LLVM IR 没有"块参数"这个概念，等价形式是 phi 节点。

输出是真实的 LLVM IR 文本，随后由 pipeline.py 交给真正的 LLVM
（llvmlite 内嵌的 LLVM）做 parse/verify/优化/生成汇编。
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# ---------------- MLIR 解析（只认今天的子集） ----------------

FUNC_RE = re.compile(
    r"^\s*llvm\.func\s+@([\w.$-]+)\s*\(([^)]*)\)\s*->\s*(\w+)\s*\{")
CONST_RE = re.compile(
    r"^\s*%(?P<res>[\w.$-]+)\s*=\s*llvm\.mlir\.constant\("
    r"(?P<lit>-?\d+)\s*:\s*(?P<ty>\w+)\)\s*:\s*(?P=ty)\s*$")
BINOP_RE = re.compile(
    r"^\s*%(?P<res>[\w.$-]+)\s*=\s*llvm\.(?P<op>add|sub|mul)\s+"
    r"%(?P<a>[\w.$-]+)\s*,\s*%(?P<b>[\w.$-]+)\s*:\s*(?P<ty>\w+)\s*$")
ICMP_RE = re.compile(
    r"^\s*%(?P<res>[\w.$-]+)\s*=\s*llvm\.icmp\s+\"(?P<pred>\w+)\"\s+"
    r"%(?P<a>[\w.$-]+)\s*,\s*%(?P<b>[\w.$-]+)\s*:\s*(?P<ty>\w+)\s*$")
CONDBR_RE = re.compile(
    r"^\s*llvm\.cond_br\s+%(?P<c>[\w.$-]+)\s*,\s*"
    r"\^(?P<t>[\w.$-]+)\s*,\s*\^(?P<f>[\w.$-]+)\s*$")
BR_RE = re.compile(
    r"^\s*llvm\.br\s+\^(?P<dst>[\w.$-]+)"
    r"(?:\(\s*%(?P<arg>[\w.$-]+)\s*:\s*(?P<ty>\w+)\s*\))?\s*$")
RET_RE = re.compile(
    r"^\s*llvm\.return(?:\s+%(?P<v>[\w.$-]+)\s*:\s*(?P<ty>\w+))?\s*$")
BLOCK_RE = re.compile(
    r"^\s*\^(?P<name>[\w.$-]+)(?:\(\s*%(?P<arg>[\w.$-]+)\s*:\s*"
    r"(?P<ty>\w+)\s*\))?:\s*$")
ARG_RE = re.compile(r"^\s*%(?P<name>[\w.$-]+)\s*:\s*(?P<ty>\w+)\s*$")

TERMINATORS = ("cond_br", "br", "return")


class Op:
    def __init__(self, kind, **kw):
        self.kind = kind
        self.__dict__.update(kw)

    @property
    def is_terminator(self):
        return self.kind in TERMINATORS

    @property
    def has_result(self):
        return self.kind in ("constant", "binop", "icmp")


class Block:
    def __init__(self, name, arg=None, arg_ty=None):
        self.name = name
        self.arg = arg          # 块参数的 MLIR 名（没有则 None）
        self.arg_ty = arg_ty
        self.ops = []
        self.slot = None        # LLVM IR 里的块编号
        self.pred_transfers = []  # [(前驱块名, 传值名)]


def strip_comments(line):
    pos = line.find("//")
    return line if pos < 0 else line[:pos]


def parse_args_list(text):
    args = []
    for part in text.split(","):
        if not part.strip():
            continue
        m = ARG_RE.match(part)
        if not m:
            raise ValueError(f"无法解析函数参数：{part.strip()!r}")
        args.append((m.group("name"), m.group("ty")))
    return args


def parse_mlir(src):
    """行级解析。MLIR 允许入口块不写标签：第一条 op 前没有 ^label:
    就归入隐式入口块（内部记作 ^entry）。"""
    funcs = []
    lines = [strip_comments(ln) for ln in src.splitlines()]
    i = 0
    while i < len(lines):
        line = lines[i]
        m = FUNC_RE.match(line)
        if not m:
            if line.strip() in ("module {", "}", ""):
                i += 1
                continue
            raise ValueError(f"第 {i+1} 行无法解析：{line.strip()!r}"
                             "（本教学版只支持 llvm.func，不支持 func.func）")
        func = type("Func", (), {})()
        func.name, func.args, func.rty = (
            m.group(1), parse_args_list(m.group(2)), m.group(3))
        func.blocks = []
        i += 1
        cur = None
        while i < len(lines):
            raw = lines[i]
            line = raw.strip()
            if line == "}":
                i += 1
                break
            if not line:
                i += 1
                continue
            bm = BLOCK_RE.match(raw)
            if bm:
                cur = Block(bm.group("name"), bm.group("arg"), bm.group("ty"))
                func.blocks.append(cur)
                i += 1
                continue
            if cur is None:
                cur = Block("entry")   # 隐式入口块：没有 ^label: 标签
                func.blocks.append(cur)
            for regex, kind in ((CONST_RE, "constant"), (BINOP_RE, "binop"),
                                (ICMP_RE, "icmp"), (CONDBR_RE, "cond_br"),
                                (BR_RE, "br"), (RET_RE, "return")):
                m2 = regex.match(raw)
                if m2:
                    cur.ops.append(Op(kind, **m2.groupdict()))
                    break
            else:
                raise ValueError(f"第 {i+1} 行的 op 不在今天的子集内："
                                 f"{line!r}")
            i += 1
        if not func.blocks:
            raise ValueError(f"函数 @{func.name} 没有基本块")
        funcs.append(func)
    return funcs


def _uses(op):
    out = []
    for attr in ("a", "b", "c", "v", "arg"):
        val = getattr(op, attr, None)
        if val:
            out.append(val)
    return out


def _find(func, name):
    for b in func.blocks:
        if b.name == name:
            return b
    raise ValueError(f"跳转到不存在的块 ^{name}")


def _pred_ops(func, name):
    """所有跳向 name 的 terminator：[(op, 所在块名)]。"""
    out = []
    for b in func.blocks:
        for op in b.ops:
            dsts = [op.t, op.f] if op.kind == "cond_br" else (
                [op.dst] if op.kind == "br" else [])
            if name in dsts:
                out.append((op, b.name))
    return out


def check_ssa(func):
    """教学版静态检查：单次定值 + 块序近似支配性 + 块参数传值完整。

    真实工具链里这由 MLIR 的 Verifier 做（完整支配性分析）；
    这里用"值必须在参数、更早的块或本块更早的行里定义过"近似，
    对今天这种结构化例子和真实判定一致。
    """
    problems = []
    defined = {a for a, _ in func.args}
    block_names = [b.name for b in func.blocks]
    if len(set(block_names)) != len(block_names):
        problems.append("有重名基本块")

    for b in func.blocks:
        if b.arg and b.arg in defined:
            problems.append(f"块 ^{b.name} 的参数 %{b.arg} 被重复定义")
        if b.arg:
            defined.add(b.arg)
        for op in b.ops:
            if op.has_result and op.res in defined:
                problems.append(f"%{op.res} 被定义了两次（SSA 单次定值被破坏）")
            if op.has_result:
                defined.add(op.res)
        terms = [o for o in b.ops if o.is_terminator]
        if not terms or terms[0] is not b.ops[-1]:
            problems.append(f"块 ^{b.name} 必须以一个 terminator 结尾")
    if problems:
        raise ValueError("SSA 检查未通过：\n  - " + "\n  - ".join(problems))

    # 使用点检查（块序近似支配性）
    visible = {a for a, _ in func.args}
    for b in func.blocks:
        local = set()
        if b.arg:
            local.add(b.arg)
        for op in b.ops:
            for use in _uses(op):
                if use not in visible and use not in local:
                    raise ValueError(f"块 ^{b.name} 使用了尚未定义的值 %{use}")
            if op.has_result:
                local.add(op.res)
        visible |= local

    # 带参数块：每个前驱的跳转都必须传值
    for b in func.blocks:
        if not b.arg:
            continue
        for _op, src in _pred_ops(func, b.name):
            if not any(s == src for s, _v in b.pred_transfers) and \
               not any(op.kind == "br" and op.arg and op.dst == b.name
                       for op in _find(func, src).ops):
                raise ValueError(f"块 ^{b.name} 有块参数 %{b.arg}，"
                                 f"但前驱 ^{src} 的跳转没有传值")


# ---------------- LLVM IR 生成（复刻 mlir-translate 的关键规则） ----------------

def allocate(func):
    """R1/R2 槽位分配：填 b.slot，返回 {mlir 值名 → LLVM 操作数文本}。

    槽位规则（复刻真实 LLVM/mlir-translate）：参数 0..n-1；随后按块序，
    每个块占一个槽位（入口块也占，只是从不显示），块内每个有结果的
    指令再各占一个。names 的值是可直接拼接的操作数文本：
    槽位值 → "%2"；R2 内联常量 → 裸字面量 "2"。
    """
    slot = -1
    names = {}
    for a, _ty in func.args:
        slot += 1
        names[a] = f"%{slot}"
    for b in func.blocks:
        slot += 1
        b.slot = slot
        for op in b.ops:
            if op.kind == "constant":
                names[op.res] = op.lit       # R2：常量内联，不占槽位
            elif op.has_result:
                slot += 1
                names[op.res] = f"%{slot}"
    for b in func.blocks:      # 块参数 → phi 结果，占槽位
        if b.arg:
            slot += 1
            names[b.arg] = f"%{slot}"
    return names


def translate(func):
    names = allocate(func)

    # R3：收集每个带参数块的前驱传值
    for b in func.blocks:
        for op in b.ops:
            if op.kind == "br" and op.arg:
                _find(func, op.dst).pred_transfers.append((b.name, op.arg))

    ref = lambda n: names[n]
    lines = ["; ModuleID = 'LLVMDialectModule'"]
    arg_list = ", ".join(f"{ty} {ref(a)}" for a, ty in func.args)
    lines.append(f"define {func.rty} @{func.name}({arg_list}) {{")
    for bi, b in enumerate(func.blocks):
        if bi > 0:
            lines.append(f"{b.slot}:")
        if b.arg:                 # phi 必须位于块首（紧跟标签）
            entries = ", ".join(f"[ {ref(v)}, %{_find(func, s).slot} ]"
                                for s, v in b.pred_transfers)
            lines.append(f"  {ref(b.arg)} = phi {b.arg_ty} {entries}")
        for op in b.ops:
            if op.kind == "binop":
                lines.append(f"  {ref(op.res)} = {op.op} {op.ty} "
                              f"{ref(op.a)}, {ref(op.b)}")
            elif op.kind == "icmp":
                lines.append(f"  {ref(op.res)} = icmp {op.pred} {op.ty} "
                             f"{ref(op.a)}, {ref(op.b)}")
            elif op.kind == "cond_br":
                lines.append(f"  br i1 {ref(op.c)}, label "
                              f"%{_find(func, op.t).slot}, "
                              f"label %{_find(func, op.f).slot}")
            elif op.kind == "br":
                lines.append(f"  br label %{_find(func, op.dst).slot}")
            elif op.kind == "return":
                lines.append(f"  ret {op.ty} {ref(op.v)}" if op.v
                             else "  ret void")
            # constant：R2 内联，不产生任何指令
    lines.append("}")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(
        description="教学版 mlir-translate（LLVM Dialect 子集 → LLVM IR）")
    ap.add_argument("input", type=Path, help="输入 .mlir 文件")
    ap.add_argument("-o", "--output", type=Path, default=None,
                    help="输出 .ll 文件（默认打印到 stdout）")
    args = ap.parse_args()

    funcs = parse_mlir(args.input.read_text(encoding="utf-8"))
    parts, stats = [], []
    for f in funcs:
        check_ssa(f)
        parts.append(translate(f))
        n_instr = sum(len(b.ops) for b in f.blocks)
        n_const = sum(1 for b in f.blocks for o in b.ops
                      if o.kind == "constant")
        n_phi = sum(1 for b in f.blocks if b.arg)
        stats.append(
            f"@{f.name}: 参数 {len(f.args)} 个；基本块 {len(f.blocks)} 个；"
            f"MLIR 指令 {n_instr} 条（其中常量 {n_const} 条内联消失）；"
            f"块参数 {n_phi} 个 → phi {n_phi} 个")
    out = "\n".join(parts)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(out, encoding="utf-8")
        print(f"已导出 LLVM IR：{args.output}")
    else:
        sys.stdout.write(out)
    for s in stats:
        print(f"  {s}")


if __name__ == "__main__":
    main()
