// 正例 1：最普通的逐元素乘——2x2 * 2x2 -> 2x2，两条规则全过。
// 用函数参数当输入，文件最小化，只盯着 mini.mul 一行看。
func.func @mul_ok(%a: tensor<2x2xf32>, %b: tensor<2x2xf32>) -> tensor<2x2xf32> {
  %p = mini.mul %a, %b : tensor<2x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
  func.return %p : tensor<2x2xf32>
}
