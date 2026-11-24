// 第 45 天主角用例：Relu(Relu(x)) —— 同一个 mini.relu 套两层。
// 数学事实：relu 的输出已经 >= 0，再套一层 max(0, .) 不改变任何元素，
// max(0, max(0, x)) == max(0, x) 对一切实数成立。
//
// FileCheck 用法与上游 lit 相同：CHECK 行写在本文件注释里，
// 命令是：mini-opt -canonicalize double_relu_basic.mlir | FileCheck double_relu_basic.mlir
//
// 期望：外层 relu 消失，return 直接使用内层 relu 的结果。
// CHECK-LABEL: func.func @double_relu(
// CHECK: %[[R:.*]] = mini.relu %arg0
// CHECK-NOT: mini.relu
// CHECK: return %[[R]]
// CHECK-NOT: mini.relu
module {
  func.func @double_relu(%arg0: tensor<2x2xf32>) -> tensor<2x2xf32> {
    %r1 = mini.relu %arg0 : tensor<2x2xf32> -> tensor<2x2xf32>
    %r2 = mini.relu %r1 : tensor<2x2xf32> -> tensor<2x2xf32>
    func.return %r2 : tensor<2x2xf32>
  }
}
