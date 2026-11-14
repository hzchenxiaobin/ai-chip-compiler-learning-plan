#!/usr/bin/env python3
"""第 168 天：最终验收——168 天的收官检查。"""
from __future__ import annotations
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(HERE, "outputs")

# 最终验收清单（计划文档 1136~1178 行的教学版浓缩）
CHECKLIST = [
    ("1. 能写出带 Verifier/Shape 推导/融合/Layout 的图编译器", "D57~D112＋D121 五闸", "✓"),
    ("2. 能做 Lowering：多层 IR→LLVM→执行", "D113~D118 七层＋四路线 12/12", "✓"),
    ("3. 能集成统一编译入口", "D120~D126 minic S0~S6＋108 项", "✓"),
    ("4. 能建 Runtime 三件套", "D127~D133 特化/回退/池化＋40 项", "✓"),
    ("5. 能建测试调试回归体系", "D134~D140 金字塔/定位/冻结 v0.5.0", "✓"),
    ("6. 能做扩展开发", "D141~D147 块循环 Tiling＋10/10 验收", "✓"),
    ("7. 能做完整性能归因", "D148~D154 五步闭环＋反例", "✓"),
    ("8. 能整理项目资产", "D155~D161 五份文档＋8/8 走查", "✓"),
    ("9. 能做面试表达", "D162~D167 十份标答＋五幕讲解", "✓"),
]

DIRECTIONS = {
    "MLIR 图编译": "深入 linalg/transform 方言——教学 mini 前端的工业版",
    "LLVM 后端": "TableGen/指令选择/调度——D118 执行层的下一层",
    "自动调度": "TVM Ansor/TensorIR——D106~D111 搜索的工业版",
    "芯片工具链": "特定 NPU 的 toolchain——教学项目的落地形态",
}


def main():
    os.makedirs(OUT, exist_ok=True)
    print("第 168 天：最终验收——168 天收官检查\n")
    print("=" * 66)
    for item, evidence, status in CHECKLIST:
        print(f"  [{status}] {item}")
        print(f"        证据：{evidence}")
    print("=" * 66)
    n_ok = sum(1 for c in CHECKLIST if c[2] == "✓")
    print(f"\n验收结果：{n_ok}/{len(CHECKLIST)} 全过\n")

    print("四选一深入方向（下一阶段四周计划）：")
    for i, (name, note) in enumerate(DIRECTIONS.items(), 1):
        print(f"  {i}. {name}：{note}")
    chosen = "MLIR 图编译"
    print(f"\n选定：{chosen}")
    print("  理由：与 minic 的 mini 前端衔接最紧（D57~D112 的工业版）")
    print("  四周计划：linalg 方言→transform 方言→tile/schedule→完整案例\n")

    print("168 天能力总结：")
    print("  从 C++/编译器基础（D1~D28）→ MLIR 核心（D29~D56）")
    print("  →图算子与优化（D57~D84）→ Lowering/Tiling/性能（D85~D112）")
    print("  →端到端与 Runtime（D113~D140）→扩展/归因/文档/面试（D141~D168）")
    print("  产出：168 篇教程｜≈250 项测试判定｜v0.5.0 冻结版｜五份项目文档｜十份标答")

    summary = {
        "验收": f"{n_ok}/{len(CHECKLIST)}",
        "教程数": 168,
        "测试判定": "≈250 项",
        "版本": "v0.5.0-stage5",
        "下一方向": chosen,
    }
    import json
    json.dump(summary, open(os.path.join(OUT, "final-summary.json"), "w"),
              ensure_ascii=False, indent=2)
    ok = n_ok == len(CHECKLIST)
    print(f"\n最终判定：{'PASS——168 天全部完成' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
