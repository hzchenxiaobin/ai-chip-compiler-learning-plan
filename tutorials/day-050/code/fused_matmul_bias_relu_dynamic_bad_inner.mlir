// 第 50 天动态负例：M 未知救不了内维错误。
// ?x3 · 4x2：内维 lhs 3（静态）对 rhs 4（静态）—— 铁证非法。
// 预期：rc=1，报错带 "requires matching inner dimensions"。

func.func @fused_dynamic_bad_inner(%a: tensor<?x3xf32>, %bias: tensor<?x2xf32>) -> tensor<?x2xf32> {
  %b = mini.constant dense<[[1.0, 2.0], [3.0, 4.0], [5.0, 6.0], [7.0, 8.0]]> : tensor<4x2xf32>
  %y = mini.fused_matmul_bias_relu %a, %b, %bias :
       tensor<?x3xf32>, tensor<4x2xf32>, tensor<?x2xf32> -> tensor<?x2xf32>
  return %y : tensor<?x2xf32>
}
