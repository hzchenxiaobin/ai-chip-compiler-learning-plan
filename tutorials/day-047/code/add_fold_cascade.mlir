// 第 47 天机制用例：级联折叠——(1+2)+3 在一轮 -canonicalize 里折到 6。
//
// 命令：mini-opt -canonicalize add_fold_cascade.mlir | FileCheck-18 add_fold_cascade.mlir
//
// 图里有两层 add：内层 1.0+2.0，外层 (内层结果)+3.0。驱动不是一次
// 只折一层：OperationFolder 折叠外层 add 时，通过 mini.constant 的
// fold 钩子"递纸条"拿到内层已物化的常量值 3.0，外层随之折成 6.0。
// 一次 -canonicalize 就到不动点，不需要跑两遍。
//
// 同款用例 @partial：不是所有操作数都是常量时只折能折的那部分——
// %x 来自函数入口，add(x, 1.0+2.0 的结果) 里内层折成 3.0，外层
// （x + 常量）没有恒等式可用了（Day 46 已论证 +0.0/-0.0 之外的
// 常量加法不能消），原样保留。fold 只在"证明得了"的地方动手。
// CHECK-LABEL: func.func @cascade(
// CHECK: mini.constant dense<6.000000e+00> : tensor<f32>
// CHECK: return
// CHECK-NOT: mini.add
// CHECK-LABEL: func.func @partial(
// CHECK: %[[C:.*]] = mini.constant dense<3.000000e+00> : tensor<f32>
// CHECK: mini.add %arg0, %[[C]] : tensor<f32>, tensor<f32> -> tensor<f32>
module {
  func.func @cascade() -> tensor<f32> {
    %a = mini.constant dense<1.0> : tensor<f32>
    %b = mini.constant dense<2.0> : tensor<f32>
    %c = mini.constant dense<3.0> : tensor<f32>
    %s1 = mini.add %a, %b : tensor<f32>, tensor<f32> -> tensor<f32>
    %s2 = mini.add %s1, %c : tensor<f32>, tensor<f32> -> tensor<f32>
    func.return %s2 : tensor<f32>
  }
  func.func @partial(%arg0: tensor<f32>) -> tensor<f32> {
    %a = mini.constant dense<1.0> : tensor<f32>
    %b = mini.constant dense<2.0> : tensor<f32>
    %s1 = mini.add %a, %b : tensor<f32>, tensor<f32> -> tensor<f32>
    %s2 = mini.add %arg0, %s1 : tensor<f32>, tensor<f32> -> tensor<f32>
    func.return %s2 : tensor<f32>
  }
}
