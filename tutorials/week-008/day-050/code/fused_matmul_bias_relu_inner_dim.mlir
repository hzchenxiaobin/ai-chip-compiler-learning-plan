// 第 50 天负例 4：内维不匹配（Day 39 的老探针，换到融合算子上）。
// lhs 2x3 · rhs 2x2：内维 3 != 2 —— 规则 3 拦截。
// 关键观察：报错前缀是 'mini.fused_matmul_bias_relu' op，
// 但规则本体与 mini.matmul 是同一个函数（MatmulRules.h）。
// 预期：rc=1，报错带 "requires matching inner dimensions"。

func.func @fused_inner_dim(%a: tensor<2x3xf32>, %b: tensor<2x2xf32>) -> tensor<2x2xf32> {
  %bias = mini.constant dense<[[1.0, 2.0], [3.0, 4.0]]> : tensor<2x2xf32>
  %y = mini.fused_matmul_bias_relu %a, %b, %bias :
       tensor<2x3xf32>, tensor<2x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
  return %y : tensor<2x2xf32>
}
