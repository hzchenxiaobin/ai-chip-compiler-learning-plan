// 动态维度正例 2：结果比输入"更具体"（合法！）。
//   lhs ?x3 · rhs 3x2 -> res 2x2
//   lhs 的 M 未知，但结果声明 M=2：语义上完全成立——结果类型比
//   操作数更具体，正是后面 Shape 推导要利用的方向（Day 43/44）。
//   Verifier 对 M 的检查：一方动态 → 无法判定 → 放行；N 的检查：2==2 通过。
//   （这个用例也是"严格相等"bug 的照妖镜：把动态当非法会误拒它。）
module {
  func.func @matmul_dynamic_refine(%a: tensor<?x3xf32>, %b: tensor<3x2xf32>) -> tensor<2x2xf32> {
    %c = mini.matmul %a, %b : tensor<?x3xf32>, tensor<3x2xf32> -> tensor<2x2xf32>
    func.return %c : tensor<2x2xf32>
  }
}
