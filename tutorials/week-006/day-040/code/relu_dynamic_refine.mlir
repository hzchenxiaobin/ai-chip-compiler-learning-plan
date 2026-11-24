// 动态维度正例：relu ?x3 -> 2x3，同款"结果比输入更具体"。
// relu 只有一对类型要查，是恒等 shape 检查的最小样本。
module {
  func.func @relu_dynamic_refine(%s: tensor<?x3xf32>) -> tensor<2x3xf32> {
    %r = mini.relu %s : tensor<?x3xf32> -> tensor<2x3xf32>
    func.return %r : tensor<2x3xf32>
  }
}
