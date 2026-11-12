// 动态维度正例（今天的头条实验之二）：?x3 + 2x3 -> 2x3。
// 三个类型字面上并不相等——SameOperandsAndResultType 时代会被误拒
// （Day 39 的 mini-opt 实测 rc=1，见教程 5.3 节）。
// 手写 Verifier 逐维判定：维 1（最右）3==3；维 0 一方是 ? -> 无法判定，
// 保守放行。语义上：lhs 的 ? 在运行期就是 2，结果声明 2x3 是合法"细化"，
// 和 Day 39 的 ?x3 · 3x2 -> 2x2 同一个方向。
module {
  func.func @add_dynamic_refine(%a: tensor<?x3xf32>, %b: tensor<2x3xf32>) -> tensor<2x3xf32> {
    %s = mini.add %a, %b : tensor<?x3xf32>, tensor<2x3xf32> -> tensor<2x3xf32>
    func.return %s : tensor<2x3xf32>
  }
}
