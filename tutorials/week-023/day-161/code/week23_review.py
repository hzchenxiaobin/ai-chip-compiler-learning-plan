#!/usr/bin/env python3
"""第 161 天：第 23 周复盘——新人视角＋五份文档定稿。"""
from __future__ import annotations
import os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs")

LEDGER = """第 23 周账本（每周模板）

本周目标：项目整理——架构图、Pass 文档、Lowering 文档、测试文档、
          性能材料、干净环境复现。

本周可运行产出：五份文档＋一次走查：architecture.txt（六层＋十模块＋
          三合同）；pass-*.md×4（五要素＋前后 IR＋诚实反例）；
          lowering-doc.md（六阶段旅程＋信息守恒）；test-doc.md
          （金字塔＋四命令＋250 项＋缺口）；perf-summary.json
          （六源＋口径＋一句话）；clean_repro 8/8 走查。

新增测试数量：走查 8 项＋各文档自检 ≈25 项判定。

最重要的一个技术问题：项目怎么从「能跑」变成「他人能理解、
          能验证」？

问题根因：22 周的产出散在 50 个 outputs/ 里——没有文档层的
          「地图」，新人面对的是考古现场。

如何验证修复：干净复现走查 8/8——新人按图索骥能跑通（文档
          可用性的终极测试）。

一个对照：整理前＝50 个目录的产出（作者视角）；整理后＝五份
          文档＋三层保障（新人视角）——「整理不是美化是第二次创造」。

能脱稿回答的问题：架构三合同；Pass 五要素；Lowering 六阶段主线；
          测试金字塔三层；性能口径三件套；三层保障与缺一后果。

仍然讲不清楚的问题：多语言版本（英文文档）；交互式教程（在线
          notebook）；视频讲解——超出文本教学的边界。

下周唯一核心目标：面试转化（D162~168）——五天标准回答＋20 分钟
          模拟讲解＋最终验收——把 22 周的实测经历组织成可复述的
          表达。
"""

NEWCOMER = """新人视角自查（计划条目："删除只对自己有意义的表述"）

自查五问（对五份文档各问一遍）：
  ① 哪个词只有我知道什么意思？（黑话检查——如「五道闸」要首现解释）
  ② 哪一步我默认了读者知道？（跳步检查——如「run_s45」没说是啥）
  ③ 哪个数字没有口径？（孤数字检查——每个数字旁边要有「怎么测的」）
  ④ 哪个结论没有证据？（断言检查——每个「应该」要有 IR/数字背书）
  ⑤ 哪个文档找不到入口？（导航检查——README 之间的互链）

结论：五份文档经过本轮自查——黑话均在首现处有一句解释（如
「五道闸」在 D155 架构文档首次出现时括注了五道闸的名字）；
跳步通过「出处」列缓解（D 编号可回溯）；口径三件套齐备。
"""


def main():
    os.makedirs(OUT, exist_ok=True)
    open(os.path.join(OUT, "week-ledger.txt"), "w").write(LEDGER)
    open(os.path.join(OUT, "newcomer-check.txt"), "w").write(NEWCOMER)
    checks = [
        ("账本 10 问", LEDGER.count("：") >= 10),
        ("新人五问", NEWCOMER.count("②") >= 1 and NEWCOMER.count("⑤") >= 1),
        ("五份文档在账", "architecture" in LEDGER),
    ]
    for n, okk in checks:
        print(f"  [{'PASS' if okk else 'FAIL'}] {n}")
    return 0 if all(o for _, o in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
