// 第 46 天组合实验：洋葱式嵌套，两条 Pattern 分属两天、协同剥壳。
//
//   relu( add( relu( add(x, -0.0) ), -0.0 ) )
//
// 剥壳过程（贪婪驱动迭代到不动点，每一步只动一个根节点）：
//   ① 内层 add(x, -0) 塌缩成 x          —— 今天的 SimplifyAddNegZero
//   ② 外层 add(relu(x), -0) 塌缩成 relu(x) —— 同上（第一轮之后才轮到它）
//   ③ relu(relu(x)) 塌缩成 relu(x)        —— Day 45 的 SimplifyDoubleRelu
//
// 期望：整颗洋葱只剩一个 relu 挂在 %arg0 上。
// CHECK-LABEL: func.func @onion(
// CHECK: %[[R:.*]] = mini.relu %arg0
// CHECK: return %[[R]]
// CHECK-NOT: mini.add
// CHECK-NOT: mini.constant
// CHECK-NOT: mini.relu
module {
  func.func @onion(%arg0: tensor<2x2xf32>) -> tensor<2x2xf32> {
    %z = mini.constant dense<-0.0> : tensor<2x2xf32>
    %a1 = mini.add %arg0, %z : tensor<2x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
    %r1 = mini.relu %a1 : tensor<2x2xf32> -> tensor<2x2xf32>
    %a2 = mini.add %r1, %z : tensor<2x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
    %r2 = mini.relu %a2 : tensor<2x2xf32> -> tensor<2x2xf32>
    func.return %r2 : tensor<2x2xf32>
  }
}
