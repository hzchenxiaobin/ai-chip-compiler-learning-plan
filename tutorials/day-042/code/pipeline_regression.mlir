// 回归：Day 41 的目标图 MatMul -> Add -> Relu 原样保留。
// 新增 mini.mul 不许弄坏任何旧算子——这一关过了，
// "新增算子的改动半径"才算真的被验证过。
// 数值约定沿用 Day 38/40/41：
//   relu(M + bias) = relu([[58,64],[139,154]] + [[-100,0],[-1,-200]])
//                  = relu([[-42,64],[138,-46]]) = [[0,64],[138,0]]
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
