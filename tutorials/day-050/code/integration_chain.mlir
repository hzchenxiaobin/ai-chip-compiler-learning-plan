// 第 50 天回归测试 2：融合算子与普通算子在同一张图里共处。
// fused_matmul_bias_relu 吐出 2x2，接一个 fused_add_relu 再加一层
// 常量，最后 mini.relu 收尾——新算子是注册表里的普通公民，
// 与第 37～47 天的全部算子同等地位。
// 预期：rc=0。

func.func @integration(%a: tensor<2x3xf32>, %b: tensor<3x2xf32>) -> tensor<2x2xf32> {
  %bias = mini.constant dense<[[0.5, -1.0], [-2.0, 3.5]]> : tensor<2x2xf32>
  %y = mini.fused_matmul_bias_relu %a, %b, %bias :
       tensor<2x3xf32>, tensor<3x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
  %extra = mini.constant dense<[[1.0, 0.0], [0.0, 1.0]]> : tensor<2x2xf32>
  %z = mini.fused_add_relu %y, %extra : tensor<2x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
  return %z : tensor<2x2xf32>
}
