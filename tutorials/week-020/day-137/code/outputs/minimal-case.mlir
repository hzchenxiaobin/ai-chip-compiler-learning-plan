func @main(%x: tensor<2x3xf32>) -> (%5: tensor<2x2xf32>) {
  %x = arg : tensor<2x3xf32>
  %w = const shape=[4, 2] values=[...] : tensor<4x2xf32>
  %t = transpose %x perm=[1, 0] : tensor<3x2xf32>
  %5 = matmul %t, %w : tensor<3x2xf32>   // 3≠4——内维不匹配
  return %5
}
