// 正例 1：2x3 · 3x2 -> 2x2，贯穿教程的标准例子。
// 四条规则全过：秩一致(2)、无 batch 维、内维 3==3、输出 [2,2] 正确。
module {
  func.func @matmul(%a: tensor<2x3xf32>, %b: tensor<3x2xf32>) -> tensor<2x2xf32> {
    %c = mini.matmul %a, %b : tensor<2x3xf32>, tensor<3x2xf32> -> tensor<2x2xf32>
    func.return %c : tensor<2x2xf32>
  }
}
