// 探针 6：K 不匹配——2x3 · 2x2，内维 3 != 2。
// 这是 Verifier 规则 3 的职责：推导接口正常管线里永远看不到这种 IR。
func.func @k_mismatch(%a: tensor<2x3xf32>, %b: tensor<2x2xf32>) {
  %c = mini.matmul %a, %b : tensor<2x3xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
  return
}
