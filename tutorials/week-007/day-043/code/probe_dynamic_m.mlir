// 探针 2：M 动态——?x3 · 3x2 的结果类型写 ?x2，人肉算出来的，Verifier 放行。
func.func @dynamic_m(%a: tensor<?x3xf32>, %b: tensor<3x2xf32>) {
  %c = mini.matmul %a, %b : tensor<?x3xf32>, tensor<3x2xf32> -> tensor<?x2xf32>
  return
}
