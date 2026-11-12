// 第 49 天（第 7 周复盘）的组合用例：必须连续执行三种机制才能完全优化。
//
//   %c0, %c1 : 常量 0.5
//   %one     : add(0.5, 0.5)      —— 只有 fold 能把它变成常量 1.0
//   %r       : relu(%x)
//   %m       : mul(%r, %one)      —— 只有 %one 变成常量 1.0 后，Mul(x,1)->x 才能匹配
//   %rr      : relu(%m)          —— 只有 %m 被改写成 %r 后，Relu(Relu)->Relu 才能匹配
//
// 三步依赖链：fold → 代数化简 → 双 Relu 消除，环环相扣，缺一不可。

func.func @combo(%x: tensor<2x2xf32>) -> tensor<2x2xf32> {
  %c0 = mini.constant dense<0.5> : tensor<2x2xf32>
  %c1 = mini.constant dense<0.5> : tensor<2x2xf32>
  %one = mini.add %c0, %c1 : tensor<2x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
  %r = mini.relu %x : tensor<2x2xf32> -> tensor<2x2xf32>
  %m = mini.mul %r, %one : tensor<2x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
  %rr = mini.relu %m : tensor<2x2xf32> -> tensor<2x2xf32>
  return %rr : tensor<2x2xf32>
}
