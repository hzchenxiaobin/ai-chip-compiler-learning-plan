// 正例 1：2x2 + 2x2 -> 2x2，贯穿全文的标准例子（目标图的 bias 加法）。
// 规则 1（两个操作数 shape 一致）与规则 2（结果与操作数一致）都过。
// SameOperandsAndResultType 时代它也能过——正例从来不是换 Verifier 的理由。
module {
  func.func @add(%m: tensor<2x2xf32>, %bias: tensor<2x2xf32>) -> tensor<2x2xf32> {
    %s = mini.add %m, %bias : tensor<2x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
    func.return %s : tensor<2x2xf32>
  }
}
