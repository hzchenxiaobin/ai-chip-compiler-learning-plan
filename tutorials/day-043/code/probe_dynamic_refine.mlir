// 探针 3：手写“超承诺”——输入只有 ?x3 · 3x2，结果却写了 2x2。
// Verifier 规则 4 对 M 一侧是 ? 无法反驳，放行：这是人额外承诺的信息。
func.func @dynamic_refine(%a: tensor<?x3xf32>, %b: tensor<3x2xf32>) {
  %c = mini.matmul %a, %b : tensor<?x3xf32>, tensor<3x2xf32> -> tensor<2x2xf32>
  return
}
