// 正例 2：带 batch 维的 3 维情形。
// lhs 2x2x3 · rhs 2x3x4 -> res 2x2x4：
//   batch 维 #0：lhs 2 == rhs 2 == res 2；
//   内维：lhs 最后一维 3 == rhs 倒数第二维 3；
//   输出：res 最后两维 [2,4] == [lhs 的 M=2, rhs 的 N=4]。
module {
  func.func @matmul_batched(%a: tensor<2x2x3xf32>, %b: tensor<2x3x4xf32>) -> tensor<2x2x4xf32> {
    %c = mini.matmul %a, %b : tensor<2x2x3xf32>, tensor<2x3x4xf32> -> tensor<2x2x4xf32>
    func.return %c : tensor<2x2x4xf32>
  }
}
