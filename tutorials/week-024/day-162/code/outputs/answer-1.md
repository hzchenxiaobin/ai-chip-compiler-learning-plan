# MLIR 解决什么问题\n\n## 结论
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
