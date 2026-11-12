// 负例 B：秩为 1 的向量——违反自制约束 Mini_F32Tensor2DPlus（秩 >= 2）
module {
  func.func @matmul_bad_rank(%v: tensor<3xf32>, %w: tensor<3xf32>) -> tensor<3xf32> {
    %c = mini.matmul %v, %w : tensor<3xf32>, tensor<3xf32> -> tensor<3xf32>
    func.return %c : tensor<3xf32>
  }
}
