// 第 46 天负例对照组（二）：常量的"形状"看数据，不看写法。
//
//   @uniform_negzero：dense<[[-0.0, -0.0]]> 写成长形式，但每个元素
//     逐位相等——DenseElementsAttr::isSplat() 判定的是数据本身，
//     所以它照样算 splat，恒等式照样成立、照样塌缩。round-trip 后
//     打印器也把它打印成 splat 形式 dense<-0.0>。
//   @mixed_zero：dense<[[0.0, -0.0]]> 每个元素"都是零"，但 +0.0 与
//     -0.0 位模式不同，数据不均匀——isSplat() 为假；而且逐元素看，
//     左半边是 +0.0（x = -0.0 时加它会翻符号），右半边是 -0.0
//     （恒等），对任何 x 都不存在整体恒等式。这一条 isSplat 检查
//     不是性能优化，是安全边界本身。
//
// 期望：@uniform_negzero 塌缩成 return %arg0；@mixed_zero 原样保留。
// CHECK-LABEL: func.func @uniform_negzero(
// CHECK: return %arg0 : tensor<1x2xf32>
// CHECK-NOT: mini.add
// CHECK-LABEL: func.func @mixed_zero(
// CHECK: %[[Z:.*]] = mini.constant dense<{{\[\[}}0.000000e+00, -0.000000e+00{{\]\]}}>
// CHECK: %[[S:.*]] = mini.add %arg0, %[[Z]]
// CHECK: return %[[S]]
// CHECK-NOT: func.return %arg0
module {
  func.func @uniform_negzero(%arg0: tensor<1x2xf32>) -> tensor<1x2xf32> {
    %z = mini.constant dense<[[-0.0, -0.0]]> : tensor<1x2xf32>
    %s = mini.add %arg0, %z : tensor<1x2xf32>, tensor<1x2xf32> -> tensor<1x2xf32>
    func.return %s : tensor<1x2xf32>
  }
  func.func @mixed_zero(%arg0: tensor<1x2xf32>) -> tensor<1x2xf32> {
    %z = mini.constant dense<[[0.0, -0.0]]> : tensor<1x2xf32>
    %s = mini.add %arg0, %z : tensor<1x2xf32>, tensor<1x2xf32> -> tensor<1x2xf32>
    func.return %s : tensor<1x2xf32>
  }
}
