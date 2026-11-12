// Pass 集成探针：同一个 (s, gate) 乘两遍，再各自 add + return。
// mini.mul 带 Pure trait（无副作用）→ -cse 应该把 %p2 这行合并掉。
// 看点 1：输出里 mini.mul 只剩一个（%p1），%p2 消失；
// 看点 2：mini-opt / MiniOpt.cpp 一行没改，CSE 就认识新算子——
//         因为 CSE 读的是 op 的 Pure trait，不是算子名单。
// 再跑 -mini-count-ops：remark 里应该数出 mini.mul=1（CSE 之后）。
module {
  func.func @dup_mul(%s: tensor<2x2xf32>, %bias: tensor<2x2xf32>) -> (tensor<2x2xf32>, tensor<2x2xf32>) {
    %gate = mini.constant dense<[[1.0, 0.5], [2.0, 1.0]]> : tensor<2x2xf32>
    %p1 = mini.mul %s, %gate : tensor<2x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
    %p2 = mini.mul %s, %gate : tensor<2x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
    %r1 = mini.add %p1, %bias : tensor<2x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
    %r2 = mini.add %p2, %bias : tensor<2x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
    func.return %r1, %r2 : tensor<2x2xf32>, tensor<2x2xf32>
  }
}
