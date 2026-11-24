// 负例 7：relu 2x3 -> 3x3 —— 恒等 shape 检查，Mismatch。
module {
  func.func @relu_bad_result(%s: tensor<2x3xf32>) -> tensor<3x3xf32> {
    %r = mini.relu %s : tensor<2x3xf32> -> tensor<3x3xf32>
    func.return %r : tensor<3x3xf32>
  }
}
