#!/usr/bin/env python3
"""第 162 天：多层 IR、MLIR 与 SSA 的三份标准回答（四段式）。"""
from __future__ import annotations
import os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs")

ANSWERS = {
"为什么需要多层 IR": """## 结论
  多层 IR 让编译器在每一层只面对一类问题——高层的领域语义（算子/图）与
  低层的执行细节（指令/寄存器）分开处理，每层配专用的优化与分析。
## 机制
  类比：翻译一篇专业文章不是一次从中文直译甲骨文——先语义理解（高层
  IR）、再结构重组（中层）、再字符映射（低层）。每层的 pass 只需要
  理解本层的语义；跨层的复杂性被分层吸收。
## 项目例子（本仓库实测）
  minic 的七层：图 IR（融合决策在这层做——D121）→循环 IR（循环序/tiling
  ——D143）→LLVM IR（指令优化——D151 的 O2 展开 8.4×）。融合决策在
  图层做因为它需要算子语义；展开在 LLVM 层做因为它需要指令级信息——
  两个优化都不可能在对的层做对的事。
## 限制
  层多了有转换开销（D119 的信息守恒：每层丢一些上层信息）；层的选择
  是权衡不是越多越好——minic 七层是教学选择。
""",
"MLIR 解决什么问题": """## 结论
  MLIR 给"造 DSL 编译器"提供了基础设施——Dialect/Pass/Conversion 的
  框架让新语言只写"差异部分"（自己的 op 与转换），通用部分（SSA/
  优化框架/LLVM 对接）复用。
## 机制
  类比：开餐厅不用自己种菜——MLIR 是供应链（SSA 基础设施/Pass 管道/
  dialect 机制），餐厅只写菜单（自己的 dialect）。
## 项目例子（本仓库实测）
  mini 前端（D57~112 的图优化）用自己的方言；Lowering 用 MLIR 的
  DialectConversion 框架（D114~117 的七 pass）；执行对接 LLVM
  （D118 的四路线）。没有 MLIR 的话这三块都要从零造。
## 限制
  MLIR 的学习曲线陡（D113~119 花了一整周才理清 LLVM Dialect vs
  LLVM IR 的关系）；对超小项目（几百行）直接生成 LLVM IR 更快。
""",
"SSA 有什么价值": """## 结论
  SSA（静态单赋值）让"每个值只有一个定义"——数据流显式化，优化
  分析（死代码/常量传播/公共子表达式）变得简单且正确。
## 机制
  类比：每件快递有唯一单号（SSA 值）——查"这个包裹从哪来到哪去"
  （def-use 链）一目了然；如果同一地址收多人的件（非 SSA 的变量
  复用），追踪就乱。
## 项目例子（本仓库实测）
  D113 的导出规则 R3（块参数→phi）：MLIR 的函数式风格（块参数）与
  LLVM 的 phi 节点是同一 SSA 语义的两种语法；D151 的 O2 展开
  （fmul 1→18）依赖 SSA 才能安全重排指令——非 SSA 下要保守得多。
## 限制
  SSA 会让可变状态（循环变量/数组元素）的表达变绕（phi/memref）；
  值的数量膨胀（D117 的 62 个 SSA 值 vs 源码 21 op）。
""",
}


def main():
    os.makedirs(OUT, exist_ok=True)
    n = 0
    for q, a in ANSWERS.items():
        open(os.path.join(OUT, f"answer-{n}.md"), "w").write(f"# {q}\\n\\n{a}")
        n += 1
        for seg in ("## 结论", "## 机制", "## 项目例子", "## 限制"):
            assert seg in a, f"'{q}' 缺 {seg}"
    print(f"三份标准回答：四段式齐全（结论/机制/例子/限制）")
    print(f"例子全部来自本仓库：七层对账/D57~118 的 dialect 链/D113 R3＋D151 展开")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
