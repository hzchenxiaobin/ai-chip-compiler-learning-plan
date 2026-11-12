// 负例 1（今天的头条实验）：真实世界最常见的 bias 写法 2x2 + 1x2。
// NumPy/PyTorch 会把 1x2 广播成 2x2，但 mini 今天只收完全一致的 shape。
// 手写 Verifier 的价值就在这条报错：明确说出"这是 broadcast，Day 60 才支持"，
// 还给出当前出路（把 bias 展开成 2x2）——trait 时代只有一句"必须同类型"。
module {
  func.func @add_bias(%m: tensor<2x2xf32>, %bias: tensor<1x2xf32>) -> tensor<2x2xf32> {
    %s = mini.add %m, %bias : tensor<2x2xf32>, tensor<1x2xf32> -> tensor<2x2xf32>
    func.return %s : tensor<2x2xf32>
  }
}
