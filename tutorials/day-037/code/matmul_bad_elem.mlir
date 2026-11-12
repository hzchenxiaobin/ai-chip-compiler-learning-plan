// 负例 D：元素类型是 i32——违反 [F32] 元素类型约束
module {
  func.func @matmul_bad_elem(%a: tensor<2x3xi32>, %b: tensor<3x2xi32>) -> tensor<2x2xi32> {
    %c = mini.matmul %a, %b : tensor<2x3xi32>, tensor<3x2xi32> -> tensor<2x2xi32>
    func.return %c : tensor<2x2xi32>
  }
}
