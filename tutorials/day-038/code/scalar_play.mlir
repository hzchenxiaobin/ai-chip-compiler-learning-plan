// 对照实验（上半场）：把 bias 从 2x2 换成"标量"tensor<f32>（秩 0）会发生什么？
//
// 观察点：
//   1. mini.constant dense<5.0> : tensor<f32> —— 秩 0 常量合法吗？
//   2. mini.add 接两个 tensor<f32> —— SameOperandsAndResultType 在乎"秩"吗？
//      （它只比较类型是否完全一致，0 秩对 0 秩也算一致）
//   3. relu(-3 + 5) = relu(2) = 2 —— 链路语义自检。
// 下半场见 scalar_matmul.mlir：同样的标量接进 matmul 会被拒。
module {
  func.func @scalar_play() -> tensor<f32> {
    %z = mini.constant dense<5.0> : tensor<f32>
    %neg = mini.constant dense<-3.0> : tensor<f32>
    %s = mini.add %z, %neg : tensor<f32>, tensor<f32> -> tensor<f32>
    %r = mini.relu %s : tensor<f32> -> tensor<f32>
    func.return %r : tensor<f32>
  }
}

