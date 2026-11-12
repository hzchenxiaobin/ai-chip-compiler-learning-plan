// 动态维度负例：M 未知救不了内维错误。
//   lhs ?x3 · rhs 4x2 -> ...
//   内维：lhs 最后一维 3（静态）vs rhs 倒数第二维 4（静态）→ 3 != 4，铁证非法。
// "动态维度 != 没有约束"的反面一半：静态可知的部分照样要查。
module {
  func.func @matmul_dynamic_bad_inner(%a: tensor<?x3xf32>, %b: tensor<4x2xf32>) -> tensor<?x2xf32> {
    %c = mini.matmul %a, %b : tensor<?x3xf32>, tensor<4x2xf32> -> tensor<?x2xf32>
    func.return %c : tensor<?x2xf32>
  }
}
