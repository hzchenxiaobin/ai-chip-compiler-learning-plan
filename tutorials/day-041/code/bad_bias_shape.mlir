// 负例：整条链路里埋一个 Day 40 的经典错误 ——
// bias 写成 2x3，而 matmul 的结果是 2x2。
// 看点：错误必须在“验证”这一关被 mini.add 的手写 Verifier 拦下，
// 并且报错要能定位到具体行列。
module {
  func.func @bad_bias() -> tensor<2x2xf32> {
    %a = mini.constant dense<[[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]> : tensor<2x3xf32>
    %b = mini.constant dense<[[7.0, 8.0], [9.0, 10.0], [11.0, 12.0]]> : tensor<3x2xf32>
    %m = mini.matmul %a, %b : tensor<2x3xf32>, tensor<3x2xf32> -> tensor<2x2xf32>
    %bias = mini.constant dense<[[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]> : tensor<2x3xf32>
    %s = mini.add %m, %bias : tensor<2x2xf32>, tensor<2x3xf32> -> tensor<2x2xf32>
    %r = mini.relu %s : tensor<2x2xf32> -> tensor<2x2xf32>
    func.return %r : tensor<2x2xf32>
  }
}
