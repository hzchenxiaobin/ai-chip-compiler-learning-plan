#!/usr/bin/env python3
"""第 141 天核心模块：choose_target.py——确定唯一扩展目标。

计划条目："比较动态 Shape、INT8、Conv 和自动调优的岗位相关性与实现成本；
只选择一个主目标，写清输入、输出、完成标准和明确不做的内容；
产出：一页扩展设计，避免范围继续扩大。"
"""
from __future__ import annotations

import os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs")

CANDIDATES = [
    # (名称, 岗位相关性, 实现成本, 与现有代码的衔接, 判定)
    ("动态 Shape＋自动调度", "高（TVM/Triton 核心话题）",
     "中（已有 D128 动态签名＋D129 特化分发打底，缺块循环 Tiling）",
     "直接承接第 19 周的三件套", "✓ 选定"),
    ("INT8 量化", "中高（推理部署热点）",
     "高（QDQ 图优化已有 D82/D83，但 kernel 侧 INT8 计算＋requant 链全新）",
     "图侧衔接好、kernel 侧断裂", "× 不选"),
    ("Conv 算子", "中（视觉场景常用）",
     "高（im2col/直接卷积/Winograd 任一路径都是独立工程）",
     "与 MatMul 的循环结构差异大", "× 不选"),
    ("自动调优（搜索）", "高（AutoTVM/Ansor 话题）",
     "中高（D106~D111 的搜索管道已有，但接入 minic 的反馈闭环要重做）",
     "搜索器在、但与 minic 的接口未通", "× 不选（并入主目标的「调度」部分）"),
]

DESIGN = """第 21 周扩展设计（一页）

唯一主目标：块循环 Tiling 的 minic 化——让 --tile 参数真实生效

为什么是它：
  · D125 证明教学版 tile 是空变量（朴素循环不消费 tile 参数）
  · D129 的特化层已就位（分发器在等有意义的差异化产物）
  · future F-01 的正主；「动态 Shape＋自动调度」轻量组合的最后一块
  · 岗位相关性：Tiling 是所有 AI 编译器的核心 pass（TVM schedule/
    Triton block/TensorIR tile）——面试必考

输入：main.graph（图 IR）＋ --tile M,N,K（CLI 已有）
输出：块循环形态的 kernel（外层 tile 壳＋内层点循环）
      特化产物的性能差异（tile 变化 → 产物变化 → 性能变化）

完成标准（可验收）：
  [ ] S2 生成块循环 IR（外层 i0/j0/k0 步长=tile＋min 钳制边界）
  [ ] tile 参数改变 → stage-2-loop.mlir 改变（产物差异可 grep）
  [ ] 正确性：D135 的 fuzz 引擎全过（块循环下 200 组仍 bitwise）
  [ ] 性能：至少一个 shape 上 tile 版 ≠ 朴素版的可测差异
  [ ] 与 D129 分发器集成：不同 tile 的特化产物可注册

明确不做（防火墙）：
  × tile 的自动搜索（那是 D106~D111 的世界，本周 tile 是手选参数）
  × 双缓冲/流水线（D102~D103 的内存课，CPU 教学版测不出收益）
  × 跨 tile 的数据依赖重排（教学规模不需要）
  × GPU/CUDA 任何内容（CPU 教学版自足）

风险与预案：
  · 块循环的边界钳制（min()）写错 → 正确性 fuzz 会抓住（D135）
  · tile 太小导致循环开销反超 → 性能反例是合法结果（D153 的伏笔）
"""


def main():
    os.makedirs(OUT, exist_ok=True)
    print("== 四个候选的对比（计划条目：岗位相关性×实现成本）==\n")
    for name, rel, cost, link, verdict in CANDIDATES:
        print(f"  {name}")
        print(f"    岗位相关性：{rel}")
        print(f"    实现成本：{cost}")
        print(f"    衔接：{link}")
        print(f"    判定：{verdict}\n")
    print("== 选定设计（一页扩展设计的正文见 design.txt）==")
    print("  主目标：块循环 Tiling 的 minic 化（--tile 真实生效）")
    print("  完成标准 5 条／明确不做 4 条——范围防火墙已立")
    open(os.path.join(OUT, "design.txt"), "w").write(DESIGN)
    checks = [
        ("四候选齐全", len(CANDIDATES) == 4),
        ("唯一选定", sum(1 for c in CANDIDATES if "✓" in c[4]) == 1),
        ("完成标准 ≥5", DESIGN.count("[ ]") >= 5),
        ("明确不做 ≥4", DESIGN.count("×") >= 4),
    ]
    for n, okk in checks:
        print(f"  [{'PASS' if okk else 'FAIL'}] {n}")
    return 0 if all(o for _, o in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
