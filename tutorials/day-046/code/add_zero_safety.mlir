// 第 46 天负例对照组（一）：Pattern 的"常量匹配"和"值判定"缺一不可。
//
//   @pos_zero：bias 写的是 +0.0（dense<0.0>）——最自然的写法，
//     但 IEEE 754 里 (-0.0) + (+0.0) = +0.0 ≠ -0.0：x 是 -0.0 时
//     这条 add 不是恒等运算，Pattern 必须不点火。这不是测试的礼貌，
//     是数学上的硬边界（3.3 节 IEEE 表的 x = -0.0 那一行）。
//   @from_arg：数值上确实是全 -0.0 的 tensor，但它从函数入口参数
//     传进来——def-use 边上一步找不到 mini.constant 定义者，
//     编译器无法证明"它是常量、且永远是 -0.0"，同样不许点火。
//
// 期望：两个函数原样 round-trip，一个 mini.add 都不许少。
// CHECK-LABEL: func.func @pos_zero(
// CHECK: %[[Z:.*]] = mini.constant
// CHECK: %[[S:.*]] = mini.add %arg0, %[[Z]]
// CHECK: return %[[S]]
// CHECK-LABEL: func.func @from_arg(
// CHECK: %[[S:.*]] = mini.add %arg0, %arg1
// CHECK: return %[[S]]
// CHECK-NOT: return %arg0
module {
  func.func @pos_zero(%arg0: tensor<2x2xf32>) -> tensor<2x2xf32> {
    %z = mini.constant dense<0.0> : tensor<2x2xf32>
    %s = mini.add %arg0, %z : tensor<2x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
    func.return %s : tensor<2x2xf32>
  }
  func.func @from_arg(%arg0: tensor<2x2xf32>, %arg1: tensor<2x2xf32>) -> tensor<2x2xf32> {
    %s = mini.add %arg0, %arg1 : tensor<2x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
    func.return %s : tensor<2x2xf32>
  }
}
