// reassociative_chain.mlir —— 第 66 天静态样例 2：结构化 reshape 的对照。
//
// 四个函数覆盖四种命运（本机 LLVM 18.1.8 实测，2026-11-12）：
//   @cc  连续两个 collapse（(2,3,4)→(6,4)→(24,)）
//        --canonicalize → 折叠成单 op，reassociation 组合成 [[0, 1, 2]]
//   @ee  连续两个 expand（(24,)→(6,4)→(2,3,4)）
//        --canonicalize → 折叠成单 op [[0, 1, 2]]
//   @ec  expand→collapse 互逆对（(24,)→(6,4)→(24,)）
//        --canonicalize → 整体消除，剩 return %arg0
//   @ce  collapse→expand 非互逆（(2,3,4)→(6,4)→(6,2,2)）
//        --canonicalize → 原样保留 2 个 op——组合出的变换无法用单个
//        reassociative reshape 表达，stock 也不重写成 tensor.reshape
//
// 与 reshape_chain.mlir 对照的结论：结构化信息（reassociation 分组）
// 决定 stock 管道里有没有组合规则；普通 tensor.reshape 的链合并要自己写。
// 注意 @cc/@ee 折叠的前提是分组「可组合」：连续 reshape 的 reassociation
// 必须首尾衔接；mini 的 P2 没有这个约束——判据只有元素数量守恒。
module {
  func.func @cc(%in: tensor<2x3x4xf32>) -> tensor<24xf32> {
    %t = tensor.collapse_shape %in [[0, 1], [2]] : tensor<2x3x4xf32> into tensor<6x4xf32>
    %r = tensor.collapse_shape %t [[0, 1]] : tensor<6x4xf32> into tensor<24xf32>
    return %r : tensor<24xf32>
  }
  func.func @ee(%in: tensor<24xf32>) -> tensor<2x3x4xf32> {
    %t = tensor.expand_shape %in [[0, 1]] : tensor<24xf32> into tensor<6x4xf32>
    %r = tensor.expand_shape %t [[0, 1], [2]] : tensor<6x4xf32> into tensor<2x3x4xf32>
    return %r : tensor<2x3x4xf32>
  }
  func.func @ec(%in: tensor<24xf32>) -> tensor<24xf32> {
    %t = tensor.expand_shape %in [[0, 1]] : tensor<24xf32> into tensor<6x4xf32>
    %r = tensor.collapse_shape %t [[0, 1]] : tensor<6x4xf32> into tensor<24xf32>
    return %r : tensor<24xf32>
  }
  func.func @ce(%in: tensor<2x3x4xf32>) -> tensor<6x2x2xf32> {
    %t = tensor.collapse_shape %in [[0, 1], [2]] : tensor<2x3x4xf32> into tensor<6x4xf32>
    %r = tensor.expand_shape %t [[0], [1, 2]] : tensor<6x4xf32> into tensor<6x2x2xf32>
    return %r : tensor<6x2x2xf32>
  }
}
