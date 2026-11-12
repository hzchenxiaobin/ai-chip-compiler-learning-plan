// 对照实验（下半场）：把"标量"tensor<f32>（秩 0）接进 mini.matmul。
// matmul 的类型约束是 Mini_F32Tensor2DPlus（秩 >= 2），所以这里应该被拒。
// 对照 scalar_play.mlir：同样的标量，add/relu 全程放行。
module {
  func.func @scalar_matmul() -> tensor<2x2xf32> {
    %z = mini.constant dense<5.0> : tensor<f32>
    %c0 = mini.constant dense<[[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]> : tensor<2x3xf32>
    %m = mini.matmul %c0, %z : tensor<2x3xf32>, tensor<f32> -> tensor<2x2xf32>
    func.return %m : tensor<2x2xf32>
  }
}
