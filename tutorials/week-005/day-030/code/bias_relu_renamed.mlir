// bias_relu_renamed.mlir —— 实验②的对照文件：
// 与 bias_relu.mlir 结构完全相同，只是所有 SSA 名字换了一整套。
// 预测：round-trip（不加任何 Pass）之后，两份文件的打印输出是否完全一样？
// 答案：一样（diff 输出为空）——名字是糖，结构才是身份。

module {
  func.func @bias_relu(%input_value: i32, %bias_value: i32) -> i32 {
    %zero = arith.constant 0 : i32
    %sum_out = arith.addi %input_value, %bias_value : i32
    %relu_out = arith.maxsi %sum_out, %zero : i32
    return %relu_out : i32
  }
}
