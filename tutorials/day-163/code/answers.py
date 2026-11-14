#!/usr/bin/env python3
"""第 163 天：融合、Layout 与正确性的两份标准回答。"""
from __future__ import annotations
import os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs")

ANSWERS = {
"融合为什么不一定更快": """## 结论
  融合省的是中间结果的搬运（访存），不是计算本身——当搬运不是瓶颈
  （数据已在 cache/寄存器）或融合破坏其他优化时，融合不带来收益。
## 机制
  类比：合并两站快递省的是中转装卸——但如果两站本来就在同一园区
  （cache 命中），省掉的装卸量≈0。
## 项目例子（本仓库实测）
  正例：D121 的融合让图 7→5 节点（结构收益真实）。反例 1：D125 实测
  .ll 规模与循环形态完全不变（教学规模 cache 命中——HBM 流量收益
  归零）。反例 2：D83 T10 多使用者不融（破坏语义）。反例 3：D151
  的 tile 融合 0.3×（重复计算吃掉复用）。
## 限制
  融合的收益＝中间结果的大小×访存代价；判断要做收益分析（D72 的
  ΔB 账本）而不是"融合总是好"。
""",
"如何保证 Pattern 不改变语义": """## 结论
  靠三层验证＋位等价测试：契约层（结构对）、数值层（结果对）、
  布局层（内存对），每层独立可断言；再加 fuzz 军团的量级保障。
## 机制
  类比：改了家里的电路——检查插座（契约）、电器（数值）、线路
  （布局）三层，每一层都有仪器（万用表）而不是"看起来能用"。
## 项目例子（本仓库实测）
  D116 的三层验证法（P1 探针的 strides 填反——数值层 4/4 放过、
  布局层 2/4 咬住）；D121 的位等价 3×10000（第一个随机输入就抓到
  量化语义 bug——DQ(Q(0.3))=0.296875≠0.3）；D135 的 fuzz 200 组。
## 限制
  位等价要求两侧同序（k 序 golden——D124 口径）；O2 展开会合法重排
  浮点序——此时判据升级为 allclose（D129 的教训）。
""",
}


def main():
    os.makedirs(OUT, exist_ok=True)
    for i, (q, a) in enumerate(ANSWERS.items()):
        open(os.path.join(OUT, f"answer-{i}.md"), "w").write(f"# {q}\\n\\n{a}")
        for seg in ("## 结论", "## 机制", "## 项目例子", "## 限制"):
            assert seg in a
    print("两份标准回答：四段式齐全——正反例来自 D121/D125/D83/D151/D116/D135")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
