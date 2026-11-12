// 负例 8：relu 2x3 -> 1x3 —— 结果"想广播"。分类是 BroadcastOnly，
// 但 relu 的结果侧没有广播语义（又不是加法），报错直说"必须相等"，
// 不需要 bias 那种两 flavor 诊断——结果侧的规则只有一条：和输入一致。
module {
  func.func @relu_broadcast_result(%s: tensor<2x3xf32>) -> tensor<1x3xf32> {
    %r = mini.relu %s : tensor<2x3xf32> -> tensor<1x3xf32>
    func.return %r : tensor<1x3xf32>
  }
}
