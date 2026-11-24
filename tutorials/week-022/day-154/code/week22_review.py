#!/usr/bin/env python3
"""第 154 天：第 22 周复盘——性能归因闭环报告。"""
from __future__ import annotations
import os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs")

REPORT = """第 22 周性能归因：闭环报告（瓶颈→假设→优化→验证→范围）

一、问题定义（D148 基线）
  用例：160³ matmul+bias+relu 朴素 O0 kernel
  基线：20.91ms / 0.392 GFLOPS（离峰值 ~50GF 差百倍）
  口径：7 轮×3 次中位＋环境五要素

二、开销拆解（D149）
  首次调用：编译 97.7%（JIT 冷启动）
  稳态：kernel 执行 100%（21.4ms 是唯一嫌疑）

三、瓶颈定性（D150 Roofline）
  AI=0.13 FLOP/Byte｜实测离计算屋顶 128×、离访存屋顶 32×
  → 不是经典二分——执行效率瓶颈（非计算指令稀释有效算力）
  三假设：H1 循环开销｜H2 复用不足｜H3 依赖链（不做）

四、优化验证（D151）
  H1（O2 展开）：25.36→3.00ms＝8.4× ✓ 成立
  H2（tile 复用）：93.95ms＝0.3× ✗ 证伪（重复计算 ×6.25 抵消收益）
  组合：2.5× 非正交（tile 拖累 O2）

五、适用范围（D152~D153）
  跨 7 shape：加速 1.7×~14.1×（8 倍离散）
  最差解剖：K=32 展开空间受限
  反例发现：反例本身是环境函数（D125 的 LLVM 18 反例在 LLVM 23 不复现）
  边界文档：三区（收益/存疑/反例）＋一行判据＋环境戳

六、结论与建议
  · O2 展开是本用例最有效的优化（中位 9.4×）——建议默认开
  · tile 化的教学实现不能带来收益（负优化）——完整版（块内边界）是后续工作
  · 反例意识：适用条件带环境戳——跨环境复用与复用优化同样危险
  · 方法论沉淀：五步闭环每步实测——从数字到边界文档的完整链
"""

LEDGER = """第 22 周账本（每周模板）

本周目标：完整性能归因——基线、拆解、Roofline、优化、跨 Shape、反例、闭环。

本周可运行产出：baseline.json（五要素基线）；breakdown.json（两视角
          拆解）；roofline.json（AI/屋顶/三假设）；optimize.json
          （三实验 8.4×/0.3×/2.5×）；cross-shape.json（7 shape 分布
          1.7~14.1×）；counterexample.json＋applicability.txt
          （反例三候选＋三区边界文档）。

新增测试数量：约 30 项判定（各天实验的正确性断言＋分布检查）。

最重要的一个技术问题：性能问题怎么从「一个慢数字」走到
          「带适用条件的优化结论」？

问题根因：慢是表象——归因要经过「拆解（哪段）→定性（什么性质）→
          假设（为什么）→验证（对策有效吗）→范围（何时有效）」五步，
          每步都有测不到的暗区。

如何验证修复：每步配实测——基线五要素、拆解两视角、Roofline 三假设、
          优化三实验（含证伪）、分布三数、反例环境戳。

一个优化前后对照：20.91ms（朴素 O0）→ 3.00ms（O2 展开）＝8.4×；
          但 64×160×32 上只 1.7×、教学 tile 反而 0.3×——
          「8.4×」只是分布的一个点。

能脱稿回答的问题：基线五要素；两视角归因（首次/稳态）；AI 与拐点；
          第三种瓶颈（执行效率）；假设三件套；分布三数；
          反例是环境函数；正确与快是独立维度。

仍然讲不清楚的问题：完整版 tile（块内边界）的真实收益；依赖链重排
          （H3）的工程实现；多核/向量化（SIMD）的教学版。

下周唯一核心目标：项目整理（D155~D161）——架构图、Pass 文档、
          Lowering 文档、测试文档、性能材料、干净环境复现——
          把 22 周的积累变成「他人能理解、能验证」的项目资产。
"""


def main():
    os.makedirs(OUT, exist_ok=True)
    open(os.path.join(OUT, "perf-report.txt"), "w").write(REPORT)
    open(os.path.join(OUT, "week-ledger.txt"), "w").write(LEDGER)
    checks = [
        ("闭环五步齐全", all(k in REPORT for k in ("基线", "拆解", "Roofline", "优化", "适用范围"))),
        ("账本 10 问", LEDGER.count("：") >= 10),
        ("核心数字在档", "8.4×" in REPORT and "0.3×" in REPORT and "14.1×" in REPORT),
    ]
    for n, okk in checks:
        print(f"  [{'PASS' if okk else 'FAIL'}] {n}")
    return 0 if all(o for _, o in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
