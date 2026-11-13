// tosa_const_probe.mlir —— 探针 4：转置推到常量边上会发生什么？
//
// Layout 传播的收益路径之一：把转置推到常量（权重）一侧，
// 得到 Transpose(constant)——理想情况下这是编译期常量折叠
// （权重离线转置，运行时零开销）。
//
// 本机 LLVM 18.1.8 实测（2026-11-12）：
//   mlir-opt tosa_const_probe.mlir --tosa-layerwise-constant-fold
//     → tosa.transpose 消失，tosa.const 的值变成转置后的
//       dense<[[1,-4],[-2,5],[3,-6]]> —— 这条收益路径真实存在。
// 对照：linalg 侧 --canonicalize 不折 linalg.transpose(constant)。

module {
  func.func @const_transpose() -> tensor<3x2xf32> {
    %c = arith.constant dense<[[1.0, -2.0, 3.0], [-4.0, 5.0, -6.0]]> : tensor<2x3xf32>
    %p = arith.constant dense<[1, 0]> : tensor<2xi32>
    %t = tosa.transpose %c, %p : (tensor<2x3xf32>, tensor<2xi32>) -> tensor<3x2xf32>
    return %t : tensor<3x2xf32>
  }
}
