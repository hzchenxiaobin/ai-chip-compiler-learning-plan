// 第 41 天主角：第一张端到端 mini IR —— MatMul -> Add -> Relu。
// 数值约定沿用 Day 38/40（Lowering 之后对答案用）：
//   A = [[1,2,3],[4,5,6]], B = [[7,8],[9,10],[11,12]]
//   M = A·B = [[58, 64], [139, 154]]
//   bias = [[-100, 0], [-1, -200]]
//   relu(M + bias) = [[0, 64], [138, 0]]
//
// 这份文件要过的三关：解析（文本 -> Operation 树）、
// 验证（ODS 约束 + Day 39/40 的手写 Verifier）、打印（round-trip）。
module {
  func.func @matmul_bias_relu() -> tensor<2x2xf32> {
    %a = mini.constant dense<[[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]> : tensor<2x3xf32>
    %b = mini.constant dense<[[7.0, 8.0], [9.0, 10.0], [11.0, 12.0]]> : tensor<3x2xf32>
    %m = mini.matmul %a, %b : tensor<2x3xf32>, tensor<3x2xf32> -> tensor<2x2xf32>
    %bias = mini.constant dense<[[-100.0, 0.0], [-1.0, -200.0]]> : tensor<2x2xf32>
    %s = mini.add %m, %bias : tensor<2x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
    %r = mini.relu %s : tensor<2x2xf32> -> tensor<2x2xf32>
    func.return %r : tensor<2x2xf32>
  }
}
