// 第 50 天负例 5：bias 与结果 shape 不匹配（Mismatch）。
// matmul 部分没问题（2x3·3x2=2x2），bias 却是 3x2 —— 规则 5 拦截。
// 预期：rc=1，报错带 "do not match dimension by dimension"。

func.func @fused_bias_mismatch(%a: tensor<2x3xf32>, %b: tensor<3x2xf32>) -> tensor<2x2xf32> {
  %bias = mini.constant dense<[[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]]> : tensor<3x2xf32>
  %y = mini.fused_matmul_bias_relu %a, %b, %bias :
       tensor<2x3xf32>, tensor<3x2xf32>, tensor<3x2xf32> -> tensor<2x2xf32>
  return %y : tensor<2x2xf32>
}
