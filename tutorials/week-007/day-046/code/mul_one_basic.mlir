// 第 46 天正例（二）：Mul(x, 1.0) → x 的两个方向。
// 数学事实：1.0 乘任何值数值都不变——NaN、±Inf 原样返回，
// -0.0 乘 1.0 还是 -0.0，+0.0 乘 1.0 还是 +0.0。在 f32 上这是
// 比加零更干净的恒等式，没有符号零的坑。
//
// 命令：mini-opt -canonicalize mul_one_basic.mlir | FileCheck-18 mul_one_basic.mlir
//
// 期望：两个函数里的 mini.mul 全部消失。
// CHECK-LABEL: func.func @rhs_one(
// CHECK: return %arg0 : tensor<2x2xf32>
// CHECK-LABEL: func.func @lhs_one(
// CHECK: return %arg0 : tensor<2x2xf32>
// CHECK-NOT: mini.mul
module {
  func.func @rhs_one(%arg0: tensor<2x2xf32>) -> tensor<2x2xf32> {
    %o = mini.constant dense<1.0> : tensor<2x2xf32>
    %p = mini.mul %arg0, %o : tensor<2x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
    func.return %p : tensor<2x2xf32>
  }
  func.func @lhs_one(%arg0: tensor<2x2xf32>) -> tensor<2x2xf32> {
    %o = mini.constant dense<1.0> : tensor<2x2xf32>
    %p = mini.mul %o, %arg0 : tensor<2x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
    func.return %p : tensor<2x2xf32>
  }
}
