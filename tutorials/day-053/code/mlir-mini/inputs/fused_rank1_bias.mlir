// 实验 J（负例，bias 规则）：融合算子带 [N] 向量 bias。
// 期望：fused_matmul_bias 的 Verifier 报「bias 需要广播——第 60 天放行」。
// 第 50 天的教训原样适用：融合算子绝不能比成员算子少查规则。
module {
  func.func @graph_fused_rank1_bias(%a: tensor<2x3xf32>, %b: tensor<3x2xf32>, %bias: tensor<2xf32>) -> tensor<2x2xf32> {
    %y = mini.fused_matmul_bias %a, %b, %bias : tensor<2x3xf32>, tensor<3x2xf32>, tensor<2xf32> -> tensor<2x2xf32>
    func.return %y : tensor<2x2xf32>
  }
}
