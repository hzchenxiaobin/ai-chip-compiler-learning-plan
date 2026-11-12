// 实验 D：乘积 %m 被 add 和另一个 relu 同时使用 —— 今天的「更致命」反例。
// 默认策略：整条链原样返回（拒绝必须无副作用）。
// --strategy=keep：融合 Relu 分支，保留 mini.matmul（整次 matmul 将重算）。
// 参考数值：%r = [[22,0],[0,8]]，%t = relu(A·B) = [[12,0],[0,28]]。
module {
  func.func @graph_multi_product(%a: tensor<2x3xf32>, %b: tensor<3x2xf32>, %bias: tensor<2x2xf32>) -> (tensor<2x2xf32>, tensor<2x2xf32>) {
    %m = mini.matmul %a, %b : tensor<2x3xf32>, tensor<3x2xf32> -> tensor<2x2xf32>
    %s = mini.add %m, %bias : tensor<2x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
    %r = mini.relu %s : tensor<2x2xf32>
    %t = mini.relu %m : tensor<2x2xf32>
    func.return %r, %t : tensor<2x2xf32>, tensor<2x2xf32>
  }
}
