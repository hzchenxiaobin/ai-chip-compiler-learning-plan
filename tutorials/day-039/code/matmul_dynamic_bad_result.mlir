// 动态维度负例 2：内维动态（? vs ?，无法判定，放行），
// 但输出 N 写错：rhs 的 N=3，res 却写了 5 → 静态可查，报错。
//   lhs 2x? · rhs ?x3 -> res 2x5（错，应为 2x3）
module {
  func.func @matmul_dynamic_bad_result(%a: tensor<2x?xf32>, %b: tensor<?x3xf32>) -> tensor<2x5xf32> {
    %c = mini.matmul %a, %b : tensor<2x?xf32>, tensor<?x3xf32> -> tensor<2x5xf32>
    func.return %c : tensor<2x5xf32>
  }
}
