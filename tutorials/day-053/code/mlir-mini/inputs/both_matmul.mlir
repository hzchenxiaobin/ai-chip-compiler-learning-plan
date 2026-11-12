// 实验 F：两侧操作数都是 mini.matmul —— 没有 bias 可言，拒绝融合。
// 语义上把某一侧当 bias 也说得通，但 Pattern 只做它说得清的事（保守策略）。
module {
  func.func @graph_both_matmul(%a: tensor<2x3xf32>, %b: tensor<3x2xf32>, %c: tensor<2x4xf32>, %d: tensor<4x2xf32>) -> tensor<2x2xf32> {
    %m1 = mini.matmul %a, %b : tensor<2x3xf32>, tensor<3x2xf32> -> tensor<2x2xf32>
    %m2 = mini.matmul %c, %d : tensor<2x4xf32>, tensor<4x2xf32> -> tensor<2x2xf32>
    %s = mini.add %m1, %m2 : tensor<2x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
    func.return %s : tensor<2x2xf32>
  }
}
