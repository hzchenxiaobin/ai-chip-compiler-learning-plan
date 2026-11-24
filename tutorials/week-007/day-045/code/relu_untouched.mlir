// 第 45 天负例对照组：Pattern 只在“输入恰好由另一个 mini.relu 定义”
// 时才点火，其余情况一律 failure 返回，驱动的其他环节也不得多管闲事。
//
//   @single_relu：只有一个 relu——不能消（消了就改变语义）；
//   @relu_of_add：relu 的输入是 mini.add——结构不匹配，原样保留。
//
// 期望：两个函数原样 round-trip，一个 relu 都不许少。
// CHECK-LABEL: func.func @single_relu(
// CHECK: %[[R:.*]] = mini.relu %arg0
// CHECK: return %[[R]]
// CHECK-LABEL: func.func @relu_of_add(
// CHECK: %[[S:.*]] = mini.add %arg0, %arg1
// CHECK: %[[R:.*]] = mini.relu %[[S]]
// CHECK: return %[[R]]
// CHECK-NOT: mini.add
module {
  func.func @single_relu(%arg0: tensor<2x2xf32>) -> tensor<2x2xf32> {
    %r = mini.relu %arg0 : tensor<2x2xf32> -> tensor<2x2xf32>
    func.return %r : tensor<2x2xf32>
  }
  func.func @relu_of_add(%arg0: tensor<2x2xf32>, %arg1: tensor<2x2xf32>) -> tensor<2x2xf32> {
    %s = mini.add %arg0, %arg1 : tensor<2x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
    %r = mini.relu %s : tensor<2x2xf32> -> tensor<2x2xf32>
    func.return %r : tensor<2x2xf32>
  }
}
