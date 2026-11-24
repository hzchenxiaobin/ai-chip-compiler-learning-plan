// 目标图的“参数版”：常量换成函数入参，测试带签名函数的解析与验证。
// 形状信息全部写在签名里 —— 这张图离“真实模型的一层”又近了一步：
// 权重来自外部，mini IR 只描述结构。
module {
  func.func @matmul_bias_relu(
    %a: tensor<2x3xf32>,
    %b: tensor<3x2xf32>,
    %bias: tensor<2x2xf32>) -> tensor<2x2xf32> {
    %m = mini.matmul %a, %b : tensor<2x3xf32>, tensor<3x2xf32> -> tensor<2x2xf32>
    %s = mini.add %m, %bias : tensor<2x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
    %r = mini.relu %s : tensor<2x2xf32> -> tensor<2x2xf32>
    func.return %r : tensor<2x2xf32>
  }
}
