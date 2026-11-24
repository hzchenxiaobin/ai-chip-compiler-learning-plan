// 第 47 天对照用例：把"Pattern 路线"的结果手工摆出来，量 uniquing 的差距。
//
// add_fold_uniquing.mlir 折叠后，OperationFolder 按 (方言, 属性, 类型)
// 去重，图里只剩一个 dense<3.0>。如果 fold 是 Pattern（各自物化
// 各自的常量），结果就是下面这个文件的样子：两个一模一样的
// mini.constant dense<3.0> 各守各的返回值。
//
// 命令：
//   mini-opt uniquing_pattern_style.mlir                    # 什么都不跑：2 个常量
//   mini-opt -cse uniquing_pattern_style.mlir               # CSE：合并成 1 个
//   mini-opt -canonicalize uniquing_pattern_style.mlir      # 对照：也是 1 个
//
// 用 grep -c mini.constant 数节点。结论：fold 的 uniquing 在
// -canonicalize 内部一次到位；Pattern 路线要再跑一遍 -cse 才追平。
// CHECK-LABEL: func.func @pattern_style(
// CHECK-COUNT-2: mini.constant dense<3.000000e+00> : tensor<f32>
module {
  func.func @pattern_style() -> (tensor<f32>, tensor<f32>) {
    %c1 = mini.constant dense<3.0> : tensor<f32>
    %c2 = mini.constant dense<3.0> : tensor<f32>
    func.return %c1, %c2 : tensor<f32>, tensor<f32>
  }
}
