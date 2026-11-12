// 第 42 天主角图：第 41 天的端到端图 MatMul -> Add -> Relu 长出一个
// 新节点 mini.mul，变成 MatMul -> Add -> Mul -> Relu——五种算子全体报到。
// 数值约定（手算，供 Day 124 之后接执行框架时对答案）：
//   A = [[1,2,3],[4,5,6]], B = [[7,8],[9,10],[11,12]]
//   M = A·B = [[58, 64], [139, 154]]
//   bias = [[-100, 0], [-1, -200]]
//   M + bias = [[-42, 64], [138, -46]]
//   gate = [[1.0, 0.5], [2.0, 1.0]]
//   (M + bias) * gate = [[-42, 32], [276, -46]]
//   relu(...) = [[0, 32], [276, 0]]
//
// 这份文件过三关：解析（认识 mini.mul 这个新名字）、
// 验证（ODS + 手写 Verifier 逐个过堂）、打印（round-trip 原样回来）。
module {
  func.func @matmul_bias_mul_relu() -> tensor<2x2xf32> {
    %a = mini.constant dense<[[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]> : tensor<2x3xf32>
    %b = mini.constant dense<[[7.0, 8.0], [9.0, 10.0], [11.0, 12.0]]> : tensor<3x2xf32>
    %m = mini.matmul %a, %b : tensor<2x3xf32>, tensor<3x2xf32> -> tensor<2x2xf32>
    %bias = mini.constant dense<[[-100.0, 0.0], [-1.0, -200.0]]> : tensor<2x2xf32>
    %s = mini.add %m, %bias : tensor<2x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
    %gate = mini.constant dense<[[1.0, 0.5], [2.0, 1.0]]> : tensor<2x2xf32>
    %g = mini.mul %s, %gate : tensor<2x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
    %r = mini.relu %g : tensor<2x2xf32> -> tensor<2x2xf32>
    func.return %r : tensor<2x2xf32>
  }
}
