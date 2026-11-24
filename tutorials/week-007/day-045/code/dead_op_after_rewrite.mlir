// 第 45 天观察实验：Pattern 重写之外，贪婪驱动自带的“简单死代码消除”。
// %junk = mini.add 的结果没有任何使用者——这不是我们 Pattern 的事
// （Pattern 只认 Relu(Relu(x))），但驱动在匹配 Pattern 之前会先做
// folding 和简单 DCE（头文件原文：Also performs folding and simple
// dead-code elimination before attempting to match any of the provided
// patterns）。合法依据：mini.add 带 Pure trait，删掉无使用者的纯算子
// 不可能改变任何可观察行为。
//
// 期望：relu 链照常塌缩；%junk 连同它的两次被替换的操作数一起消失。
// CHECK-LABEL: func.func @dead_op(
// CHECK: %[[R:.*]] = mini.relu %arg0
// CHECK: return %[[R]]
// CHECK-NOT: mini.add
// CHECK-NOT: mini.relu
module {
  func.func @dead_op(%arg0: tensor<2x2xf32>) -> tensor<2x2xf32> {
    %r1 = mini.relu %arg0 : tensor<2x2xf32> -> tensor<2x2xf32>
    %r2 = mini.relu %r1 : tensor<2x2xf32> -> tensor<2x2xf32>
    %junk = mini.add %r2, %r1 : tensor<2x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
    %r3 = mini.relu %r2 : tensor<2x2xf32> -> tensor<2x2xf32>
    func.return %r3 : tensor<2x2xf32>
  }
}
