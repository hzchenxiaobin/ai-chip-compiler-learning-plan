// 负例 5：? 救不了铁证——?x3 + 2x4。
// 维 1（最右）上 3 对 4：双方静态、不等、都不是 1 -> Mismatch。
// 维 0 的 ? 无法判定，但另一维的铁证足以拦截——"动态"不等于"没有约束"。
module {
  func.func @add_dynamic_bad(%a: tensor<?x3xf32>, %b: tensor<2x4xf32>) -> tensor<?x3xf32> {
    %s = mini.add %a, %b : tensor<?x3xf32>, tensor<2x4xf32> -> tensor<?x3xf32>
    func.return %s : tensor<?x3xf32>
  }
}
