// 第 45 天：使用者被正确替换——外层 relu 的结果有两个使用者
// （func.return 和 mini.add），替换后两条边都必须改指内层结果。
// 这条测试防的是“只改了 return、漏了 add”这类半吊子重写。
//
// 期望：内层 relu 保留；add 的第一个操作数和 return 的第一个返回值
// 都换成内层结果；外层 relu 消失。
// CHECK-LABEL: func.func @multi_user(
// CHECK: %[[R:.*]] = mini.relu %arg0
// CHECK: %[[S:.*]] = mini.add %[[R]], %arg1
// CHECK: return %[[R]], %[[S]]
// CHECK-NOT: mini.relu
module {
  func.func @multi_user(%arg0: tensor<2x2xf32>, %arg1: tensor<2x2xf32>) -> (tensor<2x2xf32>, tensor<2x2xf32>) {
    %r1 = mini.relu %arg0 : tensor<2x2xf32> -> tensor<2x2xf32>
    %r2 = mini.relu %r1 : tensor<2x2xf32> -> tensor<2x2xf32>
    %s = mini.add %r2, %arg1 : tensor<2x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
    func.return %r2, %s : tensor<2x2xf32>, tensor<2x2xf32>
  }
}
