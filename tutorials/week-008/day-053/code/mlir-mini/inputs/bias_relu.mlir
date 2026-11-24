// 实验 A：主线图 MatMul -> Add(bias) -> Relu，全部单使用者。
// 期望：三算子直接吸收成 mini.fused_matmul_bias_relu。
// 参考数值（教程 §1 的 A、B、bias）：%r = [[22,0],[0,8]]。
module {
  func.func @graph_bias_relu(%a: tensor<2x3xf32>, %b: tensor<3x2xf32>, %bias: tensor<2x2xf32>) -> tensor<2x2xf32> {
    %m = mini.matmul %a, %b : tensor<2x3xf32>, tensor<3x2xf32> -> tensor<2x2xf32>
    %s = mini.add %m, %bias : tensor<2x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
    %r = mini.relu %s : tensor<2x2xf32>
    func.return %r : tensor<2x2xf32>
  }
}
