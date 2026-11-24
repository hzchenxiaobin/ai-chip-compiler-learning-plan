// 回归用例：原样照抄第 37 天的 matmul_ok.mlir。
// 今天给 mini 加了 3 个新算子，昨天的 matmul 必须原样通过——
// 这是每次扩展 dialect 后的固定动作：先跑旧测试，再看新功能。
module {
  func.func @matmul(%a: tensor<2x3xf32>, %b: tensor<3x2xf32>) -> tensor<2x2xf32> {
    %c = mini.matmul %a, %b : tensor<2x3xf32>, tensor<3x2xf32> -> tensor<2x2xf32>
    func.return %c : tensor<2x2xf32>
  }
}
