// 负例 2：只差一个 broadcast——2x2 * 1x2（想把 scale"拉大"成 2x2）。
// 右维 2 对 2 相等；左维 2 对 1，有一方是 1 → BroadcastOnly。
// 预期报错：... would broadcast; broadcasting is not supported yet
// (see Day 60) -- expand the smaller operand to the exact shape（rc=1）。
// Day 60 打开广播支持时，这个文件翻成正例，一行 Verifier 不用改。
func.func @mul_scale(%m: tensor<2x2xf32>, %s: tensor<1x2xf32>) -> tensor<2x2xf32> {
  %p = mini.mul %m, %s : tensor<2x2xf32>, tensor<1x2xf32> -> tensor<2x2xf32>
  func.return %p : tensor<2x2xf32>
}
