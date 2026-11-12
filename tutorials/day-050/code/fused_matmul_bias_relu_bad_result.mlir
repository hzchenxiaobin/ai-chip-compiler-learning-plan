// 第 50 天负例 7：结果 shape 写错（2x2 写成 3x3）。
// 规则 4 先于规则 5 触发：报错说的是 matmul 的 [M,N]，
// 还轮不到 bias 出场——规则顺序 = 复用顺序。
// 预期：rc=1，报错带 "result shape must be [M, N] derived from the operands"。

func.func @fused_bad_result(%a: tensor<2x3xf32>, %b: tensor<3x2xf32>) -> tensor<3x3xf32> {
  %bias = mini.constant dense<[[1.0, 2.0], [3.0, 4.0]]> : tensor<2x2xf32>
  %y = mini.fused_matmul_bias_relu %a, %b, %bias :
       tensor<2x3xf32>, tensor<3x2xf32>, tensor<2x2xf32> -> tensor<3x3xf32>
  return %y : tensor<3x3xf32>
}
