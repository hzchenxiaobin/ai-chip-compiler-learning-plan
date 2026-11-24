// 第 46 天：使用者被正确替换——被消掉的 add 有两个使用者
// （func.return 和 mini.mul），替换后两条边都必须改指 %arg0。
// 与 Day 45 的 multi_user 测试同款：防"只改了 return、漏了 mul"的
// 半吊子重写；额外的观察点是 add 出局后，-0.0 常量同时失去唯一
// 使用者，也应被驱动收走。
//
// 期望：relu 和 mul 的操作数都换成 %arg0；mini.add、mini.constant 消失。
// CHECK-LABEL: func.func @multi_user(
// CHECK: %[[R:.*]] = mini.relu %arg0
// CHECK: %[[P:.*]] = mini.mul %arg0, %arg1
// CHECK: return %[[R]], %[[P]]
// CHECK-NOT: mini.add
// CHECK-NOT: mini.constant
module {
  func.func @multi_user(%arg0: tensor<2x2xf32>, %arg1: tensor<2x2xf32>)
      -> (tensor<2x2xf32>, tensor<2x2xf32>) {
    %z = mini.constant dense<-0.0> : tensor<2x2xf32>
    %s = mini.add %arg0, %z : tensor<2x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
    %r = mini.relu %s : tensor<2x2xf32> -> tensor<2x2xf32>
    %p = mini.mul %s, %arg1 : tensor<2x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
    func.return %r, %p : tensor<2x2xf32>, tensor<2x2xf32>
  }
}
