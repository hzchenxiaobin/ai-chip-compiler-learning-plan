#!/usr/bin/env python3
"""第 166 天：调试与数值问题的两份标准回答。"""
from __future__ import annotations
import os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs")

ANSWERS = {
"如何定位一个 Pass 引入的错误": """## 结论
  五站流水线：发现→看清→锁定→缩小→修死——核心是定位
  「最早语义破坏点」（首次变坏的 pass）。
## 机制
  类比：水管漏水——分段关阀找最早漏点（二分）而不是满屋挖；
  挖到后取水样化验（Reduce 到最小标本）再修（修死＋免疫）。
## 项目例子（本仓库实测）
  D136 的注入定位：前缀递增判定 ✓✓✓✗✗✗——首次变坏＝
  convert-func-to-llvm（与注入点一致）；D137 的 Reduce：19→4 节点
  （79% 缩减）；D145 的 k0 bug：集成测试抓到（形态对执行错——
  组合是新的失败面）；D135 的 fuzz：种子＋trial 精确复现。
## 限制
  首次变坏的推理前提是语义单调（错误不自我修复）；非单调场景
  要逐条开关；fuzz 无种子＝不可复现＝抽奖。
""",
"数值差异是否都能归因于浮点误差": """## 结论
  不能——浮点误差有可计算的界（K·eps·Σ|a·b|）；超出界的差异
  是 bug；界内的差异要区分「序差」（合法）与「真错」。
## 机制
  类比：两地称重差 1 克（系统误差·合法）vs 差 500 克（秤坏了·
  bug）——判据是误差界，不是「都差不多」。
## 项目例子（本仓库实测）
  D78~80 的浮点课：换求和序≠换值（k 序 vs BLAS 序——24.625 vs
  24.25 的实测）；D124 的 golden 口径（k 序手写——bitwise 的
  前提是两侧同序）；D121 的量化语义 bug（DQ(Q(0.3))=0.296875
  ——位等价第一个随机输入抓到）；D129 的判据升级（O2 展开合法
  重排→bitwise 改 allclose）。
## 限制
  atol/rtol 的阈值要按误差账本算（(2K+2)·eps·maxΣ|a·b|）不能拍
  脑袋；随机大矩阵下序差与 bug 的区分靠量级（1~2 ULP vs 系统性
  偏移）。
""",
}


def main():
    os.makedirs(OUT, exist_ok=True)
    for i, (q, a) in enumerate(ANSWERS.items()):
        open(os.path.join(OUT, f"answer-{i}.md"), "w").write(f"# {q}\\n\\n{a}")
        for seg in ("## 结论", "## 机制", "## 项目例子", "## 限制"):
            assert seg in a
    print("两份标准回答：五站流水线＋最早破坏点｜误差界与序差")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
