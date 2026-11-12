// 负例 A：bias 的 shape 是 1x2，而 %m 是 2x2 —— 逐元素加法要求类型完全一致。
// 很多人直觉上会以为 bias 会自动"广播"（broadcast）：1x2 加到 2x2 的每一行。
// 在 mini 里不会：SameOperandsAndResultType 只认"类型一模一样"，
// Broadcast 规则是第 60 天的内容。
//
// 预期：mini.opt 拒绝（rc=1），错误指向 mini.add。
module {
  func.func @bad_bias() -> tensor<2x2xf32> {
    %c0 = mini.constant dense<[[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]> : tensor<2x3xf32>
    %c1 = mini.constant dense<[[7.0, 8.0], [9.0, 10.0], [11.0, 12.0]]> : tensor<3x2xf32>
    %m = mini.matmul %c0, %c1 : tensor<2x3xf32>, tensor<3x2xf32> -> tensor<2x2xf32>
    %bias = mini.constant dense<[[1.0, 2.0]]> : tensor<1x2xf32>
    %s = mini.add %m, %bias : tensor<2x2xf32>, tensor<1x2xf32> -> tensor<2x2xf32>
    func.return %s : tensor<2x2xf32>
  }
}
