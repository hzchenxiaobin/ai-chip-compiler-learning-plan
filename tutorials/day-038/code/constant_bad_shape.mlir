// 负例 D（探针）：mini.constant 的属性形状与结果类型"打架"。
// 这里 dense<[1.0, 2.0]> 只有 2 个元素，却要当作 tensor<2x2xf32>（4 个元素）。
// 问题：ODS 层面拦得住吗？——亲自跑一遍看真实行为。
module {
  func.func @bad_const() -> tensor<2x2xf32> {
    %c = mini.constant dense<[1.0, 2.0]> : tensor<2x2xf32>
    func.return %c : tensor<2x2xf32>
  }
}
