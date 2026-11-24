// 正例：今天凑齐的最后一块拼图 —— MatMul -> Add(Bias) -> Relu 完整链路。
// 这是本学习计划的最终目标图（MLIR 教程版），今天第一次能完整写出来。
//
// 约定数值（后面 Lowering 之后要拿它对答案）：
//   A(2x3) = [[1, 2, 3],     B(3x2) = [[7,  8 ],
//             [4, 5, 6]]               [9,  10],
//                                      [11, 12]]
//   M = A·B  = [[58,  64],     bias(2x2) = [[-100,  0  ],
//                [139, 154]]                [ -1, -200]]
//   M + bias = [[-42,  64],    relu(M + bias) = [[  0, 64],
//                 [138, -46]]                    [138,  0]]
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
