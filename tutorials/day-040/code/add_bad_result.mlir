// 负例 6：操作数没问题（2x2 + 2x2），结果写成 2x3 —— add 规则 2 的靶子。
// 也是"只查操作数、忘了查结果"bug 的照妖镜（教程错误 2：那种版本会放行本文件）。
module {
  func.func @add_bad_result(%a: tensor<2x2xf32>, %b: tensor<2x2xf32>) -> tensor<2x3xf32> {
    %s = mini.add %a, %b : tensor<2x2xf32>, tensor<2x2xf32> -> tensor<2x3xf32>
    func.return %s : tensor<2x3xf32>
  }
}
