// 第 47 天主线用例：fold 不是孤军——它和 Day 45/46 的 Pattern 在同一条
// -canonicalize 流水线里接力。
//
// 命令：mini-opt -canonicalize add_fold_pipeline.mlir | FileCheck-18 add_fold_pipeline.mlir
//
//   @fold_then_pattern：relu(relu(add(1.0, 2.0)))
//       第 1 棒 fold  ：add 折成常量 3.0（今天）；
//       第 2 棒 Pattern：relu(relu(x)) → relu(x)（Day 45）。
//       最终只剩 relu(常量 3.0)——relu 没实现 fold（它对常量也能算，
//       但教学上留给练习），到它这里停住。
//   @pattern_then_fold：add(add(1.0, 2.0), -0.0)
//       内层 add 折成常量 3.0 后，外层变成 add(3.0, -0.0)——常量碰常量，
//       fold 直接算出 3.0 + (-0.0) = 3.0（IEEE：x + (-0.0) = x）。
//       注意这里 Day 46 的代数化简 Pattern 和今天的 fold 都能处理它，
//       两条生产线指向同一个结果，谁先点火都安全。
// CHECK-LABEL: func.func @fold_then_pattern(
// CHECK: %[[C:.*]] = mini.constant dense<3.000000e+00> : tensor<f32>
// CHECK: mini.relu %[[C]] : tensor<f32> -> tensor<f32>
// CHECK: return %{{.*}} : tensor<f32>
// CHECK-NOT: mini.add
// CHECK-NOT: mini.relu
// CHECK-LABEL: func.func @pattern_then_fold(
// CHECK: mini.constant dense<3.000000e+00> : tensor<f32>
// CHECK-NOT: mini.add
// CHECK-NOT: mini.constant dense<-0.000000e+00>
module {
  func.func @fold_then_pattern() -> tensor<f32> {
    %a = mini.constant dense<1.0> : tensor<f32>
    %b = mini.constant dense<2.0> : tensor<f32>
    %s = mini.add %a, %b : tensor<f32>, tensor<f32> -> tensor<f32>
    %r1 = mini.relu %s : tensor<f32> -> tensor<f32>
    %r2 = mini.relu %r1 : tensor<f32> -> tensor<f32>
    func.return %r2 : tensor<f32>
  }
  func.func @pattern_then_fold() -> tensor<f32> {
    %a = mini.constant dense<1.0> : tensor<f32>
    %b = mini.constant dense<2.0> : tensor<f32>
    %s = mini.add %a, %b : tensor<f32>, tensor<f32> -> tensor<f32>
    %z = mini.constant dense<-0.0> : tensor<f32>
    %t = mini.add %s, %z : tensor<f32>, tensor<f32> -> tensor<f32>
    func.return %t : tensor<f32>
  }
}
