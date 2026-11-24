// 负例 A：结果类型写成 f64——违反 ODS 类型约束（元素必须是 f32）
module {
  func.func @matmul_bad_result(%a: tensor<2x3xf32>, %b: tensor<3x2xf32>) -> tensor<2x2xf64> {
    %c = mini.matmul %a, %b : tensor<2x3xf32>, tensor<3x2xf32> -> tensor<2x2xf64>
    func.return %c : tensor<2x2xf64>
  }
}
