// 回归：Day 38 的完整目标图必须原样通过（rc=0）。
// 新 Verifier 不能误伤任何合法 IR——这是它存在的底线。
//
// 约定数值（Lowering 之后对答案用）：
//   M = A·B = [[58,  64], [139, 154]]，relu(M+bias) = [[0, 64], [138, 0]]
module {
  func.func @matmul_bias_relu() -> tensor<2x2xf32> {
    %c0 = mini.constant dense<[[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]> : tensor<2x3xf32>
    %c1 = mini.constant dense<[[7.0, 8.0], [9.0, 10.0], [11.0, 12.0]]> : tensor<3x2xf32>
    %m = mini.matmul %c0, %c1 : tensor<2x3xf32>, tensor<3x2xf32> -> tensor<2x2xf32>
    %bias = mini.constant dense<[[-100.0, 0.0], [-1.0, -200.0]]> : tensor<2x2xf32>
    %s = mini.add %m, %bias : tensor<2x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
    %r = mini.relu %s : tensor<2x2xf32> -> tensor<2x2xf32>
    func.return %r : tensor<2x2xf32>
  }
}
