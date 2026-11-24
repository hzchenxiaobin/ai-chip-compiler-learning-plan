// 负例 4：2x2 + 2x3 —— 广播规则也救不了的永久不匹配
// （存在双方都静态、不等、且都不是 1 的维：2 vs 3）。
// 注意报错口径与负例 1 不同："not broadcast-compatible either"——
// 用户看到就知道改 shape 也没用（除非换算法），不是"等 Day 60"能解决的。
module {
  func.func @add_mismatch(%a: tensor<2x2xf32>, %b: tensor<2x3xf32>) -> tensor<2x2xf32> {
    %s = mini.add %a, %b : tensor<2x2xf32>, tensor<2x3xf32> -> tensor<2x2xf32>
    func.return %s : tensor<2x2xf32>
  }
}
