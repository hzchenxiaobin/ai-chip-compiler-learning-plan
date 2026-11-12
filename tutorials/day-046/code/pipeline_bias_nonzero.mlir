// 第 46 天回归：bias 是实打实的非零张量时，一个字节都不许动。
// 与 Day 45 的 pipeline 用例同构（数值约定同源）：
//   A = [[1,2,3],[4,5,6]], B = [[7,8],[9,10],[11,12]]
//   M = A·B = [[58, 64], [139, 154]]，bias = [[-1,-2],[-3,-4]]
//   M + bias = [[57, 62], [136, 150]]，relu 一次与两次相同。
//
// 跑 -mini-infer-shape -canonicalize：?x2 细化成 2x2，relu(relu(x))
// 塌缩成单 relu（Day 45 的 Pattern 照常工作），但带非零 bias 的 add
// 必须原样保留——代数化简只对恒等运算动手。
// 注意输出的块顺序：-canonicalize 的驱动会把 ConstantLike 常量 hoist
// 到入口块最前面（OperationFolder 的登记动作，教程 5.3 节展开），
// 所以打印出来 bias 常量排在 matmul 之前。
// CHECK-LABEL: func.func @regression(
// CHECK: %[[B:.*]] = mini.constant dense<{{\[\[}}-1.000000e+00, -2.000000e+00], [-3.000000e+00, -4.000000e+00{{\]\]}}>
// CHECK: %[[M:.*]] = mini.matmul %arg0, %arg1 : tensor<2x3xf32>, tensor<3x2xf32> -> tensor<2x2xf32>
// CHECK: %[[S:.*]] = mini.add %[[M]], %[[B]]
// CHECK: %[[R:.*]] = mini.relu %[[S]]
// CHECK: return %[[R]]
// CHECK-NOT: mini.relu
module {
  func.func @regression(%a: tensor<2x3xf32>, %b: tensor<3x2xf32>) -> tensor<2x2xf32> {
    %m = mini.matmul %a, %b : tensor<2x3xf32>, tensor<3x2xf32> -> tensor<?x2xf32>
    %bias = mini.constant dense<[[-1.0, -2.0], [-3.0, -4.0]]> : tensor<2x2xf32>
    %s = mini.add %m, %bias : tensor<?x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
    %r1 = mini.relu %s : tensor<2x2xf32> -> tensor<2x2xf32>
    %r2 = mini.relu %r1 : tensor<2x2xf32> -> tensor<2x2xf32>
    func.return %r2 : tensor<2x2xf32>
  }
}
