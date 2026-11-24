// 探针 1：全静态正例——今天结果类型 tensor<2x2xf32> 由人手写。
func.func @static(%a: tensor<2x3xf32>, %b: tensor<3x2xf32>) {
  %c = mini.matmul %a, %b : tensor<2x3xf32>, tensor<3x2xf32> -> tensor<2x2xf32>
  return
}
