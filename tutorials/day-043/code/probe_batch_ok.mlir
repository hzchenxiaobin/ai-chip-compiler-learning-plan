// 探针 5：batch 维静态正例——2x2x3 · 2x3x2 -> 2x2x2（Day 39 规则 2 的地盘）。
func.func @batch_ok(%a: tensor<2x2x3xf32>, %b: tensor<2x3x2xf32>) {
  %c = mini.matmul %a, %b : tensor<2x2x3xf32>, tensor<2x3x2xf32> -> tensor<2x2x2xf32>
  return
}
