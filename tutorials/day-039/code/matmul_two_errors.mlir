// 对照实验：一条 IR 里埋两个错（内维 3!=2，输出 shape 也应为 [2,2] 而非 3x3）。
// 观察：只报第一个错。Verifier 的惯例是"找到第一个错误就返回 failure"，
// 把 IR 修到能过第一条，才能看到第二条。
module {
  func.func @matmul_two_errors(%a: tensor<2x3xf32>, %b: tensor<2x3xf32>) -> tensor<3x3xf32> {
    %c = mini.matmul %a, %b : tensor<2x3xf32>, tensor<2x3xf32> -> tensor<3x3xf32>
    func.return %c : tensor<3x3xf32>
  }
}
