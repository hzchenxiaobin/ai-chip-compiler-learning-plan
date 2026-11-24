// 第 50 天负例 2：2x2 对 2x3 —— Mismatch，广播也救不了。
// 预期：rc=1，报错带 "do not match dimension by dimension"。

func.func @fused_add_relu_mismatch(%a: tensor<2x2xf32>) -> tensor<2x2xf32> {
  %b = mini.constant dense<[[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]> : tensor<2x3xf32>
  %r = mini.fused_add_relu %a, %b : tensor<2x2xf32>, tensor<2x3xf32> -> tensor<2x2xf32>
  return %r : tensor<2x2xf32>
}
