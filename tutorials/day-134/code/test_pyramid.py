#!/usr/bin/env python3
"""第 134 天核心模块：test_pyramid.py——IR 与 Pass 测试整理。

计划条目："补齐 Verifier、Shape、融合、Layout 和 Lowering 的正反例；
产出：分类清晰的 IR 测试集。"

测试金字塔（今天的组织框架）：
  L1 单元测试   函数级（一个 Pattern 一个 case）——快、定位准
  L2 IR 文本测试  输入 IR → 期望 IR（mlir-opt 的 file-check 模式）——中速、
                 锁住 Pass 行为
  L3 端到端测试  输入图 → 执行 → golden（D124 模式）——慢、总闸

今天为五类组件各补正反例（正例=应通过、反例=应拒绝）：
  Verifier / Shape 推导 / 融合 / Layout / Lowering
"""
from __future__ import annotations

import os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs")

# ──────────────────────────────────────────────────────────
# 测试集：五类组件 × 正反例
# ──────────────────────────────────────────────────────────

CASES = [
    # (类别, 名称, 类型[正/反], 输入, 期望行为, 出处)
    ("Verifier", "V-pos-内维匹配", "正",
     "matmul(4x6, 6x3)——K 咬合", "闸0 通过",
     "D121 gate0"),
    ("Verifier", "V-neg-内维不匹配", "反",
     "matmul(4x6, 2x3)——K=6≠2", "闸0 拒绝：内维不匹配",
     "D83 T01"),
    ("Verifier", "V-neg-非法排列", "反",
     "transpose perm=[0,0,1]", "闸0 拒绝：非法排列",
     "D83 T03"),
    ("Shape", "S-pos-const推断", "正",
     "const shape=[3,6]", "shape 从属性读出",
     "D122 _infer_shape"),
    ("Shape", "S-pos-arg推断", "正",
     "arg tensor<2x12xf32>", "shape 从类型正则读出",
     "D122"),
    ("Shape", "S-pos-reshape推断", "正",
     "reshape new_shape=[4,6]", "shape 从 new_shape 读出",
     "D122"),
    ("Shape", "S-neg-不可推断", "反",
     "未知算子的输出 shape", "E202：无法推断",
     "D122 LowerError"),
    ("Shape", "S-neg-元素数不符", "反",
     "reshape (2,3)→(7,)", "闸0 拒绝：元素数不符",
     "D83 T02"),
    ("融合", "F-pos-单链融合", "正",
     "matmul→add(const bias)→relu 单使用者", "结构+收益双门通过→融合",
     "D121 闸4/D83 T09"),
    ("融合", "F-neg-多使用者", "反",
     "matmul 输出被两个下游用", "拒绝融合（边界）",
     "D83 T10"),
    ("融合", "F-neg-bias非const", "反",
     "add 的输入是动态张量", "拒绝融合（bias 必须常量）",
     "D121 闸4 条件"),
    ("Layout", "L-pos-转置常量折叠", "正",
     "transpose(const)", "编译期折叠→常量",
     "D121 闸2"),
    ("Layout", "L-neg-转置动态", "反",
     "transpose(输入张量)", "保留（不能折叠——运行时才知道数据）",
     "D121 闸2 条件"),
    ("Lowering", "L-pos-七pass通过", "正",
     "S2 生成的循环 IR", "七 pass 全过＋胶水 0",
     "D122/D124"),
    ("Lowering", "L-neg-vector残账", "反",
     "含 vector.reduce 的 IR", "E204：pass 拒收",
     "D122 TP5"),
    ("Lowering", "L-neg-胶水残留", "反",
     "缺 reconcile 的管道", "导出报错（D117 errors-3）",
     "D117"),
]


def main():
    os.makedirs(OUT, exist_ok=True)
    lines = ["第 134 天：IR 与 Pass 测试集（分类清单）", "=" * 70, ""]
    by_cat: dict = {}
    for cat, name, kind, inp, expect, source in CASES:
        by_cat.setdefault(cat, []).append((name, kind, inp, expect, source))

    pyramid = """测试金字塔（三层职责）：
  L1 单元测试（函数级）：一个 Pattern 一个 case——快（µs）、定位准
     → 本表的正反例主要在这一层
  L2 IR 文本测试：输入 IR → 期望 IR（file-check 模式）——中速、锁 Pass 行为
     → D117 的七 pass 管道＋D123 的改写记录是雏形
  L3 端到端测试：输入图 → 执行 → golden——慢（秒）、总闸
     → D124 的 12/12 bitwise 是这一层的唯一代表
  数量配比（健康金字塔）：L1:L2:L3 ≈ 10:3:1（大量快测试、少量慢总闸）
  当前项目：L1 本表 16 例｜L2 雏形（改写记录）｜L3 1 例——底部厚、顶部薄
"""
    lines.append(pyramid)

    for cat, cases in by_cat.items():
        lines.append(f"── {cat}（{len(cases)} 例）──")
        pos = sum(1 for c in cases if c[1] == "正")
        lines.append(f"   正例 {pos} ／ 反例 {len(cases)-pos}")
        for name, kind, inp, expect, source in cases:
            mark = "✓" if kind == "正" else "✗"
            lines.append(f"   [{mark}] {name}")
            lines.append(f"        输入：{inp}")
            lines.append(f"        期望：{expect}")
            lines.append(f"        出处：{source}")
        lines.append("")

    total_pos = sum(1 for c in CASES if c[1] == "正")
    total_neg = len(CASES) - total_pos
    lines.append("=" * 70)
    lines.append(f"合计：{len(CASES)} 例（正 {total_pos} ／ 反 {total_neg}）")
    lines.append("反例占比 %.0f%%——健康配比 ≈ 40%%（反例是免疫系统的记忆）" % (total_neg/len(CASES)*100))
    text = "\n".join(lines)
    open(os.path.join(OUT, "test-suite.txt"), "w").write(text)
    print(text[:1500])

    checks = [
        ("五类组件齐全", len(by_cat) == 5),
        ("16 例测试", len(CASES) == 16),
        ("反例 ≥ 6（免疫系统）", total_neg >= 6),
        ("每例带出处", all(c[5] for c in CASES)),
    ]
    for n, okk in checks:
        print(f"  [{'PASS' if okk else 'FAIL'}] {n}")
    return 0 if all(o for _, o in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
