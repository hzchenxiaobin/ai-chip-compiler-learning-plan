// 第 50 天负例 3：操作数没问题，结果 shape 写错（2x2 -> 3x3）。
// 规则 2：res 必须与操作数 shape 一致（relu 不改变 shape，
// 所以 fused 的结果 = add 的结果 shape）。
// 预期：rc=1，报错带 "result shape must equal the operand shape"。

func.func @fused_add_relu_bad_result(%a: tensor<2x2xf32>) -> tensor<3x3xf32> {
  %b = mini.constant dense<[[1.0, 2.0], [3.0, 4.0]]> : tensor<2x2xf32>
  %r = mini.fused_add_relu %a, %b : tensor<2x2xf32>, tensor<2x2xf32> -> tensor<3x3xf32>
  return %r : tensor<3x3xf32>
}
