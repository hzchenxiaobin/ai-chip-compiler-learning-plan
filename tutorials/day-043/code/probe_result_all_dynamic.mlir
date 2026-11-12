// 探针 4：信息丢失现场——输入 2x3 · 3x2 全静态，结果却写 ?x?。
// Verifier 只拦“可证明非法”，? 无法反驳 → rc=0，但下游再也拿不回 2x2。
func.func @all_dynamic_result(%a: tensor<2x3xf32>, %b: tensor<3x2xf32>) {
  %c = mini.matmul %a, %b : tensor<2x3xf32>, tensor<3x2xf32> -> tensor<?x?xf32>
  return
}
