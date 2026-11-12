// 负例 B：mini.relu 的结果类型写成了 1x2，与输入 2x2 不一致。
// SameOperandsAndResultType 约束的是"操作数与结果全都同类型"，
// relu 也不例外：输出必须和输入一样大。
module {
  func.func @bad_relu() -> tensor<1x2xf32> {
    %x = mini.constant dense<[[1.0, 2.0], [3.0, 4.0]]> : tensor<2x2xf32>
    %r = mini.relu %x : tensor<2x2xf32> -> tensor<1x2xf32>
    func.return %r : tensor<1x2xf32>
  }
}
