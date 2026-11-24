// 负例 4：batch 维不对齐。lhs 的 batch 维 #0 是 2，rhs 却是 3。
// 内维 3==3、输出 [2,4] 都对，但 batch 维对不上：2 != 3。
module {
  func.func @matmul_batch_mismatch(%a: tensor<2x2x3xf32>, %b: tensor<3x3x4xf32>) -> tensor<2x2x4xf32> {
    %c = mini.matmul %a, %b : tensor<2x2x3xf32>, tensor<3x3x4xf32> -> tensor<2x2x4xf32>
    func.return %c : tensor<2x2x4xf32>
  }
}
