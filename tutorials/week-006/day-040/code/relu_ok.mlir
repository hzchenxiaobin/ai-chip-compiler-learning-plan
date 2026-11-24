// 正例 2：relu 的 shape 恒等检查。逐元素算子不限秩——
// 矩阵 2x2、标量 tensor<f32>（秩 0）、三维 2x3x4 都合法。
// 这正是 Mini_F32Tensor（不限秩）与 matmul 的 Mini_F32Tensor2DPlus（秩>=2）
// 的区别：relu 没有"内维"可言，任何形状进来、同样形状出去。
module {
  func.func @relu_matrix(%s: tensor<2x2xf32>) -> tensor<2x2xf32> {
    %r = mini.relu %s : tensor<2x2xf32> -> tensor<2x2xf32>
    func.return %r : tensor<2x2xf32>
  }
  func.func @relu_scalar(%s: tensor<f32>) -> tensor<f32> {
    %r = mini.relu %s : tensor<f32> -> tensor<f32>
    func.return %r : tensor<f32>
  }
  func.func @relu_3d(%s: tensor<2x3x4xf32>) -> tensor<2x3x4xf32> {
    %r = mini.relu %s : tensor<2x3x4xf32> -> tensor<2x3x4xf32>
    func.return %r : tensor<2x3x4xf32>
  }
}
