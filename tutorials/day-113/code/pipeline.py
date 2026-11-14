#!/usr/bin/env python3
"""第 113 天主线实验：同一份 LLVM IR 的两段旅程。

  目标无关优化（IR → IR）：
      只看 IR 本身能证明的事实，不需要任何 CPU 信息。
      显式跑 3 个 pass（O0 基线之上）：
        instcombine（指令化简：常量折叠、加零消除、分支变 select）
        sccp（稀疏条件常量传播）
        simplifycfg（控制流化简：合并/删除基本块）
  目标相关编译（IR → 汇编）：
      同一份优化后的 IR，分别交给 aarch64 和 x86_64 两个 TargetMachine，
      由目标各自做指令选择、寄存器分配、指令调度——产物不同。

用法：python3 pipeline.py outputs/step.ll [--tag step]
"""

from __future__ import annotations

import argparse
import json
import platform
from pathlib import Path

from llvmlite import binding as llvm

TARGETS = [
    ("aarch64-unknown-linux-gnu", "step_aarch64.s"),
    ("x86_64-unknown-linux-gnu", "step_x86_64.s"),
]


def stats(mod):
    """数出模块的结构指标（用真实 LLVM 结构，不是数文本）。"""
    out = []
    for f in mod.functions:
        blocks = list(f.blocks)
        n_instr = n_values = 0
        for blk in blocks:
            for ins in blk.instructions:
                n_instr += 1
                if str(ins).lstrip().startswith("%"):
                    n_values += 1
        out.append({"function": f.name, "blocks": len(blocks),
                    "instructions": n_instr, "ssa_values": n_values})
    return out


def count_asm_lines(text):
    """数真实指令行：去掉空行、标签、伪指令（. 开头）。"""
    n = 0
    for ln in text.splitlines():
        s = ln.strip()
        if not s or s.startswith((".", ";", "#")) or s.endswith(":"):
            continue
        n += 1
    return n


def run(ll_path: Path, tag: str, outdir: Path):
    src = ll_path.read_text(encoding="utf-8")

    # ---- 1. 真实 LLVM：parse + verify ----
    mod = llvm.parse_assembly(src)
    mod.verify()
    before = stats(mod)
    # 优化前的"官方打印"（LLVM 自己的排版，含前驱注释）
    before_text = str(mod)

    llvm.initialize_all_targets()
    llvm.initialize_all_asmprinters()

    # ---- 2. 目标无关优化：IR → IR ----
    # PassBuilder 挂在 aarch64 的 TargetMachine 上，但下面 3 个 pass
    # 只读 IR 本身、不看目标——所以结果对任何目标都一样（这正是"目标无关"）。
    tm_arm = llvm.Target.from_triple(TARGETS[0][0]).create_target_machine(opt=2)
    pto = llvm.create_pipeline_tuning_options(speed_level=0)  # O0 基线
    pb = llvm.create_pass_builder(tm_arm, pto)
    npm = pb.getModulePassManager()
    npm.add_instruction_combine_pass()
    npm.add_sccp_pass()
    npm.add_simplify_cfg_pass()
    npm.run(mod, pb)
    mod.verify()
    after = stats(mod)

    (outdir / f"opt_before_{tag}.ll").write_text(
        before_text, encoding="utf-8")
    (outdir / f"opt_after_{tag}.ll").write_text(str(mod), encoding="utf-8")

    # ---- 3. 目标相关编译：同一份优化后 IR → 两个目标的汇编 ----
    asm_counts = {}
    for triple, fname in TARGETS:
        tm = llvm.Target.from_triple(triple).create_target_machine(opt=2)
        asm = tm.emit_assembly(mod)
        path = outdir / fname if tag == "step" else \
            outdir / f"{tag}_{fname}"
        path.write_text(asm, encoding="utf-8")
        asm_counts[triple] = count_asm_lines(asm)

    # ---- 4. 机器可读摘要（图片和 README 的数字来源） ----
    summary = {
        "input": str(ll_path),
        "tag": tag,
        "llvm_version": ".".join(map(str, llvm.llvm_version_info)),
        "python": platform.python_version(),
        "machine": platform.machine(),
        "passes": ["instcombine", "sccp", "simplifycfg"],
        "before": before,
        "after": after,
        "asm_instruction_lines": asm_counts,
    }
    (outdir / f"stats_{tag}.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[{tag}] 输入：{ll_path}")
    for b in before:
        print(f"  优化前 @{b['function']}：{b['blocks']} 块 / "
              f"{b['instructions']} 条指令 / {b['ssa_values']} 个 SSA 值")
    for a in after:
        print(f"  优化后 @{a['function']}：{a['blocks']} 块 / "
              f"{a['instructions']} 条指令 / {a['ssa_values']} 个 SSA 值"
              "（instcombine + sccp + simplifycfg，目标无关）")
    print(f"  优化前/后 IR：outputs/opt_before_{tag}.ll → "
          f"outputs/opt_after_{tag}.ll")
    for triple, n in asm_counts.items():
        print(f"  {triple}（-O2，目标相关）：{n} 条指令行")
    print(f"  机器可读摘要：outputs/stats_{tag}.json")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("ll", type=Path)
    ap.add_argument("--tag", default="step")
    ap.add_argument("--outdir", type=Path, default=Path("outputs"))
    args = ap.parse_args()
    args.outdir.mkdir(parents=True, exist_ok=True)
    run(args.ll, args.tag, args.outdir)


if __name__ == "__main__":
    main()
