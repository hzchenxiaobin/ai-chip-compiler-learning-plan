// 第 46 天主角用例：Add(x, -0.0) → x 的两个方向。
// 数学事实：IEEE 754 里 x + (-0.0) = x 对一切 x 成立（含 ±0.0、±Inf）；
// 加法交换律保证常量在右边（@rhs_zero）或在左边（@lhs_zero）是同一个恒等式。
//
// 命令：mini-opt -canonicalize add_negzero_basic.mlir | FileCheck-18 add_negzero_basic.mlir
//
// 期望：两个函数里的 mini.add 全部消失，return 直接使用 %arg0；
// 连带地，失去唯一使用者的 -0.0 常量也会被驱动的简单 DCE 收走
// （无使用者 + Pure —— 第 45 天 dead_op 实验看过的机制）。
// CHECK-LABEL: func.func @rhs_zero(
// CHECK: return %arg0 : tensor<2x2xf32>
// CHECK-LABEL: func.func @lhs_zero(
// CHECK: return %arg0 : tensor<2x2xf32>
// CHECK-NOT: mini.add
// CHECK-NOT: mini.constant
module {
  func.func @rhs_zero(%arg0: tensor<2x2xf32>) -> tensor<2x2xf32> {
    %z = mini.constant dense<-0.0> : tensor<2x2xf32>
    %s = mini.add %arg0, %z : tensor<2x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
    func.return %s : tensor<2x2xf32>
  }
  func.func @lhs_zero(%arg0: tensor<2x2xf32>) -> tensor<2x2xf32> {
    %z = mini.constant dense<-0.0> : tensor<2x2xf32>
    %s = mini.add %z, %arg0 : tensor<2x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
    func.return %s : tensor<2x2xf32>
  }
}
