// 5.4 节对照实验：只改一个"参数"——bias 的 shape。
// 与 bad_bias_shape.mlir（2x2 vs 2x3，永久 Mismatch）不同，
// 这里 bias 写成 1x2：shape 关系是 BroadcastOnly（每行加同一组数），
// 应触发 Day 40 写好的"暂不支持 broadcast"诊断，而不是笼统的 mismatch。
module {
  func.func @broadcast_bias() -> tensor<2x2xf32> {
    %a = mini.constant dense<[[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]> : tensor<2x3xf32>
    %b = mini.constant dense<[[7.0, 8.0], [9.0, 10.0], [11.0, 12.0]]> : tensor<3x2xf32>
    %m = mini.matmul %a, %b : tensor<2x3xf32>, tensor<3x2xf32> -> tensor<2x2xf32>
    %bias = mini.constant dense<[[1.0, 2.0]]> : tensor<1x2xf32>
    %s = mini.add %m, %bias : tensor<2x2xf32>, tensor<1x2xf32> -> tensor<2x2xf32>
    %r = mini.relu %s : tensor<2x2xf32> -> tensor<2x2xf32>
    func.return %r : tensor<2x2xf32>
  }
}
