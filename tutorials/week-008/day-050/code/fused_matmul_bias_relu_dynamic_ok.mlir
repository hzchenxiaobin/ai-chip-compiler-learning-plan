// 第 50 天动态正例：?x3 · 3x2 + ?x2 -> ?x2。
// M 全程未知：lhs 的 ?、bias 的 ?、结果的 ? 互相无法反驳，
// 内维 3==3 静态铁证通过 —— 保守放行（Day 39/40 同款策略）。
// 预期：rc=0。

func.func @fused_dynamic_ok(%a: tensor<?x3xf32>, %b: tensor<3x2xf32>, %bias: tensor<?x2xf32>) -> tensor<?x2xf32> {
  %y = mini.fused_matmul_bias_relu %a, %b, %bias :
       tensor<?x3xf32>, tensor<3x2xf32>, tensor<?x2xf32> -> tensor<?x2xf32>
  return %y : tensor<?x2xf32>
}
