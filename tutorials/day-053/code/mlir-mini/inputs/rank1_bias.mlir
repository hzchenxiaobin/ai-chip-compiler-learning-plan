// 实验 G（负例）：bias 是 [N] 向量 —— 经典的 torch.nn.Linear bias 写法。
// 这张图本身过不了 mini.add 的 Verifier（第 40 天：需要广播，故意不支持），
// 期望：verify 阶段就报错退出，根本轮不到融合 Pattern。
module {
  func.func @graph_rank1_bias(%a: tensor<2x3xf32>, %b: tensor<3x2xf32>, %bias: tensor<2xf32>) -> tensor<2x2xf32> {
    %m = mini.matmul %a, %b : tensor<2x3xf32>, tensor<3x2xf32> -> tensor<2x2xf32>
    %s = mini.add %m, %bias : tensor<2x2xf32>, tensor<2xf32> -> tensor<2x2xf32>
    %r = mini.relu %s : tensor<2x2xf32>
    func.return %r : tensor<2x2xf32>
  }
}
