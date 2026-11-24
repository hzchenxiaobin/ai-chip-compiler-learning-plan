// 实验 I（负例，输出类型）：fused_matmul_bias 的结果写成了 lhs 的形状 2x3。
// 期望：融合算子自己的 Verifier 拦下——结果 shape 必须跟 matmul 走（[M,N]），
// 不是 lhs 的 [M,K]，更不是 bias 的形状。
module {
  func.func @graph_bad_fused_result(%a: tensor<2x3xf32>, %b: tensor<3x2xf32>, %bias: tensor<2x3xf32>) -> tensor<2x3xf32> {
    %y = mini.fused_matmul_bias %a, %b, %bias : tensor<2x3xf32>, tensor<3x2xf32>, tensor<2x3xf32> -> tensor<2x3xf32>
    func.return %y : tensor<2x3xf32>
  }
}
