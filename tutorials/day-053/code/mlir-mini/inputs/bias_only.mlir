// 实验 B：没有 Relu —— 两算子融合成 mini.fused_matmul_bias。
// 参考数值：%s = A·B + bias = [[22,-23],[-7,8]]。
module {
  func.func @graph_bias_only(%a: tensor<2x3xf32>, %b: tensor<3x2xf32>, %bias: tensor<2x2xf32>) -> tensor<2x2xf32> {
    %m = mini.matmul %a, %b : tensor<2x3xf32>, tensor<3x2xf32> -> tensor<2x2xf32>
    %s = mini.add %m, %bias : tensor<2x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
    func.return %s : tensor<2x2xf32>
  }
}
