// 负例 2：输出 shape 错误。内维 3==3 没问题，但
//   期望 res 是 [M, N] = [2, 2]，实际写成 3x3。
module {
  func.func @matmul_bad_result(%a: tensor<2x3xf32>, %b: tensor<3x2xf32>) -> tensor<3x3xf32> {
    %c = mini.matmul %a, %b : tensor<2x3xf32>, tensor<3x2xf32> -> tensor<3x3xf32>
    func.return %c : tensor<3x3xf32>
  }
}
