// 动态维度正例：M 未知，其余全部一致。
//   lhs ?x3 · rhs 3x2 -> res ?x2
//   内维 3==3 静态可查；res 的 M=? 与 lhs 的 M=? 都动态，无法判定 → 保守放行。
// 这是"动态维度 != 没有约束"的正面一半：能查的都查了，查不了的才放行。
module {
  func.func @matmul_dynamic_m(%a: tensor<?x3xf32>, %b: tensor<3x2xf32>) -> tensor<?x2xf32> {
    %c = mini.matmul %a, %b : tensor<?x3xf32>, tensor<3x2xf32> -> tensor<?x2xf32>
    func.return %c : tensor<?x2xf32>
  }
}
