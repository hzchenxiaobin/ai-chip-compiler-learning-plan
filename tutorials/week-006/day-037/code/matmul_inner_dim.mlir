// 负例 C（今天故意放行）：内维不匹配 2x3 · 2x3 -> 2x3
// 三个操作数/结果都是"秩>=2 的 f32 张量"，今天的 ODS 约束全部满足，
// 所以它能通过验证——内维匹配和输出 Shape 检查是 Day 39 Verifier 的工作。
module {
  func.func @matmul_inner_dim(%a: tensor<2x3xf32>, %b: tensor<2x3xf32>) -> tensor<2x3xf32> {
    %c = mini.matmul %a, %b : tensor<2x3xf32>, tensor<2x3xf32> -> tensor<2x3xf32>
    func.return %c : tensor<2x3xf32>
  }
}
