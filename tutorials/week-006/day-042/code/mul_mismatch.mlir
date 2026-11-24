// 负例 1：shape 永久不匹配——2x2 * 2x3。
// 右对齐逐维比：右维 2 对 3，双方都静态、不等、也不是 1 → Mismatch。
// 预期报错：... do not match dimension by dimension and are not
// broadcast-compatible either（rc=1）。
func.func @mul_mismatch(%a: tensor<2x2xf32>, %b: tensor<2x3xf32>) -> tensor<2x2xf32> {
  %p = mini.mul %a, %b : tensor<2x2xf32>, tensor<2x3xf32> -> tensor<2x2xf32>
  func.return %p : tensor<2x2xf32>
}
