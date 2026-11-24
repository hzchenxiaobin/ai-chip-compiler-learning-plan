// bias_relu.mlir —— 第 30 天主示例：逐行标注「读 IR」要看的五个概念
//
// 标记约定（与教程正文一致）：
//   [定义]  本行产出的 SSA 值（结果）
//   [使用]  本行读取的 SSA 值（操作数）
//   [类型]  本行涉及的类型
//   [属性]  编译期常量，不是 SSA 值
//
// 整个函数合计：定义 5 个值（%x、%b、%c0、%sum、%r），5 次使用（各值恰好被用 1 次）。

// 文件最外层本身就是一条 Operation：builtin.module。
// 它没有操作数、没有结果，只有一个装函数用的 Region（Day 31 展开）。
module {

  // func.func 也是一条 Operation：
  //   函数名 @bias_relu 与签名 (i32, i32) -> i32 存在「属性」里（sym_name / function_type）。
  //   %x、%b 是 BlockArgument：由函数体的入口块定义，不是任何 op 的结果。
  //   [定义] %x %b  [类型] i32
  func.func @bias_relu(%x: i32, %b: i32) -> i32 {

    // [定义] %c0  [使用] 无  [属性] value = 0 : i32
    // 常量 0 不走操作数，走属性——Day 9「算子属性」的工业版。
    %c0 = arith.constant 0 : i32

    // [定义] %sum  [使用] %x, %b（两个操作数）  [类型] (i32, i32) -> i32
    %sum = arith.addi %x, %b : i32

    // [定义] %r  [使用] %sum, %c0  [类型] (i32, i32) -> i32
    // ReLU 的标量版：max(x, 0)——上一行的和与零比较，负数归零。
    %r = arith.maxsi %sum, %c0 : i32

    // [使用] %r；本行定义 0 个值——操作可以没有结果。
    // 操作数 1 个（%r），类型 i32 与函数签名的返回类型一致。
    return %r : i32
  }
}
