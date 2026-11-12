// 第 45 天：三层 relu 链——验证驱动的“迭代到不动点”。
// 一次应用 Pattern 只剥一层（外层被换掉），贪婪驱动会把新暴露出来的
// 外层（原来的中层）重新排进工作表再匹配一次，直到再也匹配不上。
//
// 期望：三层塌缩成一层。
// CHECK-LABEL: func.func @triple_relu(
// CHECK: %[[R:.*]] = mini.relu %arg0
// CHECK: return %[[R]]
// CHECK-NOT: mini.relu
module {
  func.func @triple_relu(%arg0: tensor<2x2xf32>) -> tensor<2x2xf32> {
    %r1 = mini.relu %arg0 : tensor<2x2xf32> -> tensor<2x2xf32>
    %r2 = mini.relu %r1 : tensor<2x2xf32> -> tensor<2x2xf32>
    %r3 = mini.relu %r2 : tensor<2x2xf32> -> tensor<2x2xf32>
    func.return %r3 : tensor<2x2xf32>
  }
}
