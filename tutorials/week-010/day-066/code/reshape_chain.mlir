// reshape_chain.mlir —— 第 66 天静态样例：连续两个 tensor.reshape。
//
// in 2x3x4 --reshape [6,4]--> 6x4 --reshape [24]--> 24
// 两次都是 C 序（行主序）reshape，元素数量 24 守恒：
// 整条链语义上等价于单个 tensor.reshape %in → tensor<24xf32>。
//
// 本机 LLVM 18.1.8 实测（2026-11-12）：
//   mlir-opt reshape_chain.mlir --canonicalize
//     → exit=0，输出里 tensor.reshape 仍剩 2 个（IR 原样保留）
//   tensor.reshape 没有注册链式合并的 canonicalization pattern——
//   这条优化在 stock 管道里不存在，要自己写。
//   对照：reassociative_chain.mlir 里的结构化 reshape（expand/collapse）
//   在同一条命令下会被组合成单 op、互逆对会被整体消除。
//
// mini 的 P2（merge_consecutive_reshape）会把这条链合并为：
//   %r = mini.reshape %in shape = [24] : (2x3x4xf32) -> (24xf32)
module {
  func.func @chain(%in: tensor<2x3x4xf32>) -> tensor<24xf32> {
    %s1 = arith.constant dense<[6, 4]> : tensor<2xi32>
    %s2 = arith.constant dense<[24]> : tensor<1xi32>
    %t = tensor.reshape %in(%s1) : (tensor<2x3x4xf32>, tensor<2xi32>) -> tensor<6x4xf32>
    %r = tensor.reshape %t(%s2) : (tensor<6x4xf32>, tensor<1xi32>) -> tensor<24xf32>
    return %r : tensor<24xf32>
  }
}
