// 实验 C：bias 写在左边 —— mini.add %bias, %m。
// Pattern 必须左右都认：乘积在 rhs，bias 在 lhs，融合后操作数归一成 (a, b, bias)。
module {
  func.func @graph_bias_on_left(%a: tensor<2x3xf32>, %b: tensor<3x2xf32>, %bias: tensor<2x2xf32>) -> tensor<2x2xf32> {
    %m = mini.matmul %a, %b : tensor<2x3xf32>, tensor<3x2xf32> -> tensor<2x2xf32>
    %s = mini.add %bias, %m : tensor<2x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
    func.return %s : tensor<2x2xf32>
  }
}
