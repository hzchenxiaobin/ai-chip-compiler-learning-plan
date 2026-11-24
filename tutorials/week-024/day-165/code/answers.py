#!/usr/bin/env python3
"""第 165 天：Tiling、内存与性能的两份标准回答。"""
from __future__ import annotations
import os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs")

ANSWERS = {
"Tile 由什么决定": """## 结论
  三个约束的三角：片上容量（装不装得下）、数据复用（省多少搬运）、
  边界代价（余数 tile 的额外开销）——Tile 是三者的平衡点。
## 机制
  类比：搬家用箱子大小——太大（装不下电梯）/太小（搬运次数多/箱子
  本身的开销）/合适（一趟搬完且不空载）。
## 项目例子（本仓库实测）
  D101 的五项记账（A/B×2＋C＋bias——×2 只加在 DMA 流入项）；
  D104 的闸门（128³ 超 256KiB 拒收）；D143~146 的 tile 参数化
  （validate_tile 五负例＋三极端）；D151 的反例（教学 tile 0.3×
  ——重复计算吃掉复用——完整版块内边界是前提）。
## 限制
  教学 CPU 版测不出块复用的收益（L1 全命中）；真实收益要 GPU/SRAM
  （D100 的片外工作区规划）＋完整版 tile（future F-01 后续）。
""",
"如何判断计算或访存瓶颈": """## 结论
  用 Roofline：算术强度 AI=FLOP/Byte 与机器拐点 AI*=峰值算力/带宽
  对照——AI<AI* 访存受限、AI>AI* 计算受限；但两个屋顶都远时是
  第三种：执行效率瓶颈。
## 机制
  类比：判断快递慢是包装慢（计算）还是运输慢（访存）——算日均
  单量比（AI）与车队/仓库的容量比（拐点）。都远低于极限？那是
  分拣流程慢（执行效率）。
## 项目例子（本仓库实测）
  D150 的 160³ 分析：AI=0.13、拐点 1.0——实测 0.39GF 离计算屋顶
  128×、离访存屋顶 32×——两个都远→执行效率瓶颈（循环控制指令
  稀释有效算力）；D151 的验证（O2 展开 8.4×——消除开销的收益
  证明定性正确）。
## 限制
  屋顶数字要同口径（教学版用单核朴素序下界——不用营销峰值）；
  AI 的访存量估算有最坏/带 cache 两种（差 2.4×）——结论可能不同。
""",
}


def main():
    os.makedirs(OUT, exist_ok=True)
    for i, (q, a) in enumerate(ANSWERS.items()):
        open(os.path.join(OUT, f"answer-{i}.md"), "w").write(f"# {q}\\n\\n{a}")
        for seg in ("## 结论", "## 机制", "## 项目例子", "## 限制"):
            assert seg in a
    print("两份标准回答：Tile 三角＋五项记账｜Roofline 三分支＋实测对照")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
