// 正例：2x3 · 3x2 -> 2x2 的 mini.matmul
// 这是贯穿本周的标准例子：A(2x3) * B(3x2) = C(2x2)
module {
  func.func @matmul(%a: tensor<2x3xf32>, %b: tensor<3x2xf32>) -> tensor<2x2xf32> {
    %c = mini.matmul %a, %b : tensor<2x3xf32>, tensor<3x2xf32> -> tensor<2x2xf32>
    func.return %c : tensor<2x2xf32>
  }
}
