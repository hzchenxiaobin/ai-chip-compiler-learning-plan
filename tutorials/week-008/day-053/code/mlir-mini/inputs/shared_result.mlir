// 实验 E：加法结果 %s 被 relu 和 func.return 同时使用。
// 期望：Relu 不能吸收（%s 的别的使用者要的是 A·B+bias，不是 relu 后的值），
// 只做两算子融合；留下的 mini.relu(fused_matmul_bias) 是第 54 天的入口。
// 参考数值：%r = [[22,0],[0,8]]，%s = [[22,-23],[-7,8]]。
module {
  func.func @graph_shared_result(%a: tensor<2x3xf32>, %b: tensor<3x2xf32>, %bias: tensor<2x2xf32>) -> (tensor<2x2xf32>, tensor<2x2xf32>) {
    %m = mini.matmul %a, %b : tensor<2x3xf32>, tensor<3x2xf32> -> tensor<2x2xf32>
    %s = mini.add %m, %bias : tensor<2x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
    %r = mini.relu %s : tensor<2x2xf32>
    func.return %r, %s : tensor<2x2xf32>, tensor<2x2xf32>
  }
}
