// 第 45 天组合实验：Day 44 的 shape 推导 + Day 45 的规范化接进同一条
// 流水线。MatMul 的结果类型故意写成 ?x2（动态 M），让 -mini-infer-shape
// 细化成 2x2；后面的 Relu(Relu(x)) 交给 -canonicalize 去消。
//
// 数值约定（手算，供 Day 124 之后对答案）：
//   A = [[1,2,3],[4,5,6]], B = [[7,8],[9,10],[11,12]]
//   M = A·B = [[58, 64], [139, 154]]，bias = [[-1, -2], [-3, -4]]
//   M + bias = [[57, 62], [136, 150]]，relu 一次和 relu 两次结果相同。
//
// 期望：?x2 被细化为 2x2；double relu 塌缩成单 relu。
// CHECK-LABEL: func.func @pipeline(
// CHECK: %[[M:.*]] = mini.matmul %arg0, %arg1 : tensor<2x3xf32>, tensor<3x2xf32> -> tensor<2x2xf32>
// CHECK: %[[S:.*]] = mini.add %[[M]], %arg2
// CHECK: %[[R:.*]] = mini.relu %[[S]]
// CHECK: return %[[R]]
// CHECK-NOT: mini.relu
module {
  func.func @pipeline(%a: tensor<2x3xf32>, %b: tensor<3x2xf32>, %bias: tensor<2x2xf32>) -> tensor<2x2xf32> {
    %m = mini.matmul %a, %b : tensor<2x3xf32>, tensor<3x2xf32> -> tensor<?x2xf32>
    %s = mini.add %m, %bias : tensor<?x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
    %r1 = mini.relu %s : tensor<2x2xf32> -> tensor<2x2xf32>
    %r2 = mini.relu %r1 : tensor<2x2xf32> -> tensor<2x2xf32>
    func.return %r2 : tensor<2x2xf32>
  }
}
