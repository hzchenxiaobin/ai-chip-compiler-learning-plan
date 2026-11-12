// 实验 H（负例）：bias shape 与乘积连广播都对不上（3x2 对 2x2）。
// 期望：mini.add 的 Verifier 报 shape 不匹配，verify 阶段退出。
module {
  func.func @graph_bad_bias_shape(%a: tensor<2x3xf32>, %b: tensor<3x2xf32>, %bias: tensor<3x2xf32>) -> tensor<2x2xf32> {
    %m = mini.matmul %a, %b : tensor<2x3xf32>, tensor<3x2xf32> -> tensor<2x2xf32>
    %s = mini.add %m, %bias : tensor<2x2xf32>, tensor<3x2xf32> -> tensor<2x2xf32>
    %r = mini.relu %s : tensor<2x2xf32>
    func.return %r : tensor<2x2xf32>
  }
}
