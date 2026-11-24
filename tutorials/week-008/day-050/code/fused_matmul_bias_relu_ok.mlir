// 第 50 天正例 2（今天的旗舰例子）：mini.fused_matmul_bias_relu。
// 语义：res[m,n] = relu( sum_k lhs[m,k]*rhs[k,n] + bias[m,n] )
//   lhs 2x3 · rhs 3x2 = 2x2（matmul 规则 1~4 全过）
//   bias 2x2 与结果一致（规则 5 过）
// 预期：rc=0，round-trip 原样打印。
// 这个 shape 家族（2x3 · 3x2 -> 2x2）从第 37 天沿用至今。

func.func @fused_matmul_bias_relu_ok(%a: tensor<2x3xf32>, %b: tensor<3x2xf32>) -> tensor<2x2xf32> {
  %bias = mini.constant dense<[[0.5, -1.0], [-2.0, 3.5]]> : tensor<2x2xf32>
  %y = mini.fused_matmul_bias_relu %a, %b, %bias :
       tensor<2x3xf32>, tensor<3x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
  return %y : tensor<2x2xf32>
}
