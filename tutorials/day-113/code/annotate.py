#!/usr/bin/env python3
"""遍历真实 LLVM 模块（llvmlite 内嵌 LLVM），生成第 113 天的两份产出：

  1. 带注释的 LLVM IR：标注函数参数、返回值、基本块（含前驱/后继）；
  2. 概念对照表：LLVM Dialect（MLIR 侧）与 LLVM IR 的逐概念对应。

注释以 `;` 开头，输出仍是合法 LLVM IR——生成后会重新 parse+verify 证明
注释没有破坏文件。
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import mini_translate as mt
from llvmlite import binding as llvm

LABEL_RE = re.compile(r"label\s%([\w.$-]+)")
PHI_RE = re.compile(r"\[\s*%([\w.$-]+)\s*,\s*%([\w.$-]+)\s*\]")


def analyze(func_ref, mlir_f):
    """返回 [{label, preds, succs, instrs, opcodes}]，全部来自真实 LLVM。"""
    blocks = []
    for blk in func_ref.blocks:
        instrs = [str(ins).strip() for ins in blk.instructions]
        opcodes = [ins.opcode for ins in blk.instructions]
        succ_slots = []
        for s in instrs:
            if re.match(r"^(br|switch)\b", s):
                succ_slots += LABEL_RE.findall(s)
        blocks.append({"instrs": instrs, "opcodes": opcodes,
                       "succ_slots": succ_slots})

    # 块标签：入口块无标签；其余块 = MLIR 块序对应的槽位号
    order_slots = [b.slot for b in mlir_f.blocks]
    index_of_slot = {str(order_slots[bi]): bi
                     for bi in range(1, len(blocks))}
    for bi, b in enumerate(blocks):
        b["label"] = "entry" if bi == 0 else str(order_slots[bi])
        b["preds"] = []
    for bi, b in enumerate(blocks):
        for s in b["succ_slots"]:
            sj = index_of_slot.get(s)
            if sj is not None:
                blocks[sj]["preds"].append(b["label"])
    return blocks


def annotate(ll_path, mlir_path, out_ll, out_table):
    src = Path(ll_path).read_text(encoding="utf-8")
    mod = llvm.parse_assembly(src)          # 真实 LLVM：parse
    mod.verify()                            # 真实 LLVM：verify

    mlir_funcs = mt.parse_mlir(
        Path(mlir_path).read_text(encoding="utf-8"))
    lines_out, table_rows = [], []
    for fref in mod.functions:
        mlir_f = next(f for f in mlir_funcs if f.name == fref.name)
        f_names = mt.allocate(mlir_f)       # {mlir 名 → LLVM 操作数文本}
        arg_names = [a for a, _ in mlir_f.args]
        blocks = analyze(fref, mlir_f)
        n_blocks = len(blocks)
        rets = [i for b in blocks for i in b["instrs"]
                if i.startswith("ret")]

        lines_out.append(
            f"; ▼ 函数 @{mlir_f.name}：参数 {len(arg_names)} 个、"
            f"基本块 {n_blocks} 个、返回类型 {mlir_f.rty}")
        lines_out.append(";   参数对照：" + "，".join(
            f"%{i} ← MLIR %{arg_names[i]}"
            for i in range(len(arg_names))))
        lines_out.append(f";   返回点：{len(rets)} 处")
        lines_out.append(f"define {mlir_f.rty} @{mlir_f.name}("
                         + ", ".join(f"i32 %{i}" for i in range(len(arg_names)))
                         + ") {")

        for bi, b in enumerate(blocks):
            mlir_b = mlir_f.blocks[bi]
            where = (f"（MLIR ^{mlir_b.name}）"
                     if mlir_b.name != "entry" else "（MLIR 隐式入口块）")
            lines_out.append(f"; ── 基本块 {bi+1}/{n_blocks}：{b['label']}"
                             f"{where}")
            lines_out.append(
                ";    前驱 " + (
                    f"{len(b['preds'])} 个：" + "、".join(b["preds"])
                    if b["preds"]
                    else ("0 个（入口块）" if bi == 0 else "0 个")))
            lines_out.append(
                ";    后继 " + (
                    f"{len(b['succ_slots'])} 个："
                    + "、".join(f"%{s}" for s in b["succ_slots"])
                    if b["succ_slots"] else "0 个（出口块，含 ret）"))
            if bi > 0:
                lines_out.append(f"{mlir_b.slot}:")
            for ins, opcode in zip(b["instrs"], b["opcodes"]):
                note = ""
                if opcode == "phi":
                    slot = ins.split()[0].lstrip("%")
                    pairs = PHI_RE.findall(ins)
                    note = (f"phi：本块的块参数（MLIR ^{mlir_b.name} 的 "
                            f"%{mlir_b.arg}）；前驱各送一个值："
                            + "；".join(f"%{v} 来自 %{p}"
                                        for v, p in pairs))
                elif opcode == "ret":
                    note = f"返回值：{ins.split()[-1]}"
                elif opcode == "br" and "," in ins:
                    note = "条件跳转（llvm.cond_br）：真/假各走一个后继"
                elif opcode == "br":
                    note = "无条件跳转（llvm.br）"
                lines_out.append(f"  {ins}"
                                 + (f"   ; ← {note}" if note else ""))
        lines_out.append("}")

        # ---- 概念对照表（槽位编号全部来自真实导出结果） ----
        e, hi, lo, mg = mlir_f.blocks[:4]
        t = table_rows
        t.append(("函数",
                  f"llvm.func @{mlir_f.name}(%{arg_names[0]}: i32) -> i32",
                  f"define i32 @{mlir_f.name}(i32 %0)",
                  "函数名保留；参数重编号为 %0"))
        t.append(("函数参数", f"%{arg_names[0]}: i32（带名字）",
                  "%0（无名，按槽位编号）", f"%{arg_names[0]} → %0"))
        t.append(("常量", "llvm.mlir.constant(2 : i32) : i32（共 4 条）",
                  "立即数字面量 2（不占槽位、不产生指令）",
                  "2/3/4/0 全部内联进操作数位置"))
        t.append(("SSA 值", "%five / %s20 / %z / %cond（结果带名字）",
                  f"{f_names['five']} / {f_names['s20']} / {f_names['z']} / "
                  f"{f_names['cond']}", "名字不跨语言保留，改为槽位编号"))
        t.append(("基本块",
                  f"^entry（隐式） / ^{hi.name} / ^{lo.name} / ^{mg.name}"
                  "（块标签带名字）",
                  f"入口块无标签 / {hi.slot}: / {lo.slot}: / {mg.slot}:",
                  "块名不保留，改为槽位编号；入口块编号从不显示"))
        t.append(("块间传值", f"^{mg.name}(%{mg.arg}: i32)——块参数",
                  f"{f_names[mg.arg]} = phi i32 [ {f_names['x1']}, "
                  f"%{hi.slot} ], [ {f_names['x2']}, %{lo.slot} ]",
                  "MLIR 的块参数 = LLVM IR 的 phi 节点"))
        t.append(("无条件跳转",
                  f"llvm.br ^{mg.name}(%{mg.arg} : i32)（带传值）",
                  f"br label %{mg.slot}",
                  f"传值不出现在 br 里，而在 ^{mg.name} 块首的 phi 中"))
        t.append(("条件跳转",
                  f"llvm.cond_br %cond, ^{hi.name}, ^{lo.name}",
                  f"br i1 {f_names['cond']}, label %{hi.slot}, "
                  f"label %{lo.slot}",
                  "i1 条件值 + 两个后继块"))
        t.append(("返回", f"llvm.return %{mg.arg} : i32",
                  f"ret i32 {f_names[mg.arg]}",
                  f"返回 phi 结果 {f_names[mg.arg]}"))
        t.append(("模块容器", "module { … }",
                  "; ModuleID = 'LLVMDialectModule' + 顶层定义",
                  "MLIR module ↔ LLVM 编译单元"))

    out = [
        "; ──────────────────────────────────────────────────────",
        "; 第 113 天产出 1：带注释的 LLVM IR（自动生成）",
        f"; 输入：{mlir_path}（LLVM Dialect）→ mini_translate.py 导出"
        f" → {ll_path}",
        "; 注释由 annotate.py 遍历 llvmlite 解析出的真实 LLVM 结构生成",
        "; ──────────────────────────────────────────────────────",
    ] + lines_out
    out_text = "\n".join(out) + "\n"
    Path(out_ll).write_text(out_text, encoding="utf-8")

    md = ["# 概念对照表：LLVM Dialect ↔ LLVM IR",
          "",
          f"由 `annotate.py` 结合 `{mlir_path}` 与 `{ll_path}` 自动生成，"
          "槽位编号来自真实导出结果。",
          "",
          "| 概念 | LLVM Dialect（MLIR 侧） | LLVM IR（导出后） | 本例实例 |",
          "|---|---|---|---|"]
    for row in table_rows:
        md.append("| " + " | ".join(row) + " |")
    Path(out_table).write_text("\n".join(md) + "\n", encoding="utf-8")

    # 注释版仍是合法 LLVM IR：重新 parse+verify
    mod2 = llvm.parse_assembly(out_text)
    mod2.verify()

    print(f"已生成 {out_ll}")
    print(f"已生成 {out_table}")
    print("注释版重新 parse+verify 通过（注释没有破坏 IR）")
    for fref in mod.functions:
        print(f"  @{fref.name}：{len(list(fref.arguments))} 参数 / "
              f"{len(list(fref.blocks))} 基本块")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("ll", type=Path, help="mini_translate 导出的 .ll")
    ap.add_argument("--mlir", type=Path, default=Path("step.mlir"))
    ap.add_argument("--out-ll", type=Path,
                    default=Path("outputs/step_annotated.ll"))
    ap.add_argument("--out-table", type=Path,
                    default=Path("outputs/concept_table.md"))
    args = ap.parse_args()
    annotate(args.ll, args.mlir, args.out_ll, args.out_table)


if __name__ == "__main__":
    main()
