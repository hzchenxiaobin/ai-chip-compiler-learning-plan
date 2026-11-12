// 第 50 天动态正例：?x3 + 2x3 -> 2x3。
// lhs 的 M 是动态维，无法证明不等于 2 —— 保守放行（Day 39/40 同款策略，
// 结果比操作数更具体是合法的细化 IR）。
// 预期：rc=0。

func.func @fused_add_relu_dynamic_ok(%a: tensor<?x3xf32>, %b: tensor<2x3xf32>) -> tensor<2x3xf32> {
  %r = mini.fused_add_relu %a, %b : tensor<?x3xf32>, tensor<2x3xf32> -> tensor<2x3xf32>
  return %r : tensor<2x3xf32>
}
