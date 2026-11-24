// 第 46 天负例/边界对照组（三）：mini.mul 的三个"先想清楚再动手"。
//
//   @mul_by_zero：Mul(x, 0.0) → 0 看似更省，实则两个独立的否决理由：
//     1. 数值上不安全——NaN × 0 = NaN、±Inf × 0 = NaN、-0.0 × 0 = -0.0，
//        结果根本不是 +0.0（3.3 节 IEEE 表最后一列）；
//     2. 收益前提不成立——要把图换成"常量 0"，就得凭空物化一个新
//        mini.constant；x 是动态 shape（?x2）时连物化都无从下手。
//   @mul_uniform_one：dense<[[1.0, 1.0]]> 写成长形式，但元素全体
//     逐位相等，isSplat() 看数据不看写法——它就是 1.0 的 splat，
//     恒等式成立，塌缩（与 add_nonsplat_safety 的 @uniform_negzero
//     同一现象）。
//   @mul_true_nonsplat：dense<[[1.0, 2.0]]> 数据真的不均匀——一半
//     乘 1、一半乘 2，不存在单一恒等值，必须原样保留。
//
// 期望：@mul_by_zero、@mul_true_nonsplat 保留；@mul_uniform_one 塌缩。
// CHECK-LABEL: func.func @mul_by_zero(
// CHECK: %[[P:.*]] = mini.mul %arg0, %[[Z:.*]]
// CHECK: return %[[P]]
// CHECK-LABEL: func.func @uniform_one(
// CHECK: return %arg0 : tensor<1x2xf32>
// CHECK-NOT: mini.mul
// CHECK-LABEL: func.func @true_nonsplat(
// CHECK: %[[P:.*]] = mini.mul %arg0, %[[Z:.*]]
// CHECK: return %[[P]]
// CHECK-NOT: return %arg0
module {
  func.func @mul_by_zero(%arg0: tensor<2x2xf32>) -> tensor<2x2xf32> {
    %z = mini.constant dense<0.0> : tensor<2x2xf32>
    %p = mini.mul %arg0, %z : tensor<2x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
    func.return %p : tensor<2x2xf32>
  }
  func.func @uniform_one(%arg0: tensor<1x2xf32>) -> tensor<1x2xf32> {
    %o = mini.constant dense<[[1.0, 1.0]]> : tensor<1x2xf32>
    %p = mini.mul %arg0, %o : tensor<1x2xf32>, tensor<1x2xf32> -> tensor<1x2xf32>
    func.return %p : tensor<1x2xf32>
  }
  func.func @true_nonsplat(%arg0: tensor<1x2xf32>) -> tensor<1x2xf32> {
    %o = mini.constant dense<[[1.0, 2.0]]> : tensor<1x2xf32>
    %p = mini.mul %arg0, %o : tensor<1x2xf32>, tensor<1x2xf32> -> tensor<1x2xf32>
    func.return %p : tensor<1x2xf32>
  }
}
