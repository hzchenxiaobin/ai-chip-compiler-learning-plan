// 负例 3：秩不一致。lhs 是 2 维 2x3，rhs 却是 3 维 2x2x3。
// ODS 只保证各自秩 >= 2，"秩必须相等"是 Verifier 的规则 1。
module {
  func.func @matmul_rank_mismatch(%a: tensor<2x3xf32>, %b: tensor<2x2x3xf32>) -> tensor<2x2xf32> {
    %c = mini.matmul %a, %b : tensor<2x3xf32>, tensor<2x2x3xf32> -> tensor<2x2xf32>
    func.return %c : tensor<2x2xf32>
  }
}
