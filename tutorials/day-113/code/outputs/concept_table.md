# 概念对照表：LLVM Dialect ↔ LLVM IR

由 `annotate.py` 结合 `step.mlir` 与 `outputs/step.ll` 自动生成，槽位编号来自真实导出结果。

| 概念 | LLVM Dialect（MLIR 侧） | LLVM IR（导出后） | 本例实例 |
|---|---|---|---|
| 函数 | llvm.func @step(%arg0: i32) -> i32 | define i32 @step(i32 %0) | 函数名保留；参数重编号为 %0 |
| 函数参数 | %arg0: i32（带名字） | %0（无名，按槽位编号） | %arg0 → %0 |
| 常量 | llvm.mlir.constant(2 : i32) : i32（共 4 条） | 立即数字面量 2（不占槽位、不产生指令） | 2/3/4/0 全部内联进操作数位置 |
| SSA 值 | %five / %s20 / %z / %cond（结果带名字） | %2 / %3 / %4 / %5 | 名字不跨语言保留，改为槽位编号 |
| 基本块 | ^entry（隐式） / ^hi / ^lo / ^merge（块标签带名字） | 入口块无标签 / 6: / 8: / 10: | 块名不保留，改为槽位编号；入口块编号从不显示 |
| 块间传值 | ^merge(%m: i32)——块参数 | %11 = phi i32 [ %7, %6 ], [ %9, %8 ] | MLIR 的块参数 = LLVM IR 的 phi 节点 |
| 无条件跳转 | llvm.br ^merge(%m : i32)（带传值） | br label %10 | 传值不出现在 br 里，而在 ^merge 块首的 phi 中 |
| 条件跳转 | llvm.cond_br %cond, ^hi, ^lo | br i1 %5, label %6, label %8 | i1 条件值 + 两个后继块 |
| 返回 | llvm.return %m : i32 | ret i32 %11 | 返回 phi 结果 %11 |
| 模块容器 | module { … } | ; ModuleID = 'LLVMDialectModule' + 顶层定义 | MLIR module ↔ LLVM 编译单元 |
