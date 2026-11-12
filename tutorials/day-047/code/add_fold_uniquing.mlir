// 第 47 天机制用例：uniquing——fold 出的相同常量只物化一次。
//
// 命令：mini-opt -canonicalize add_fold_uniquing.mlir | FileCheck-18 add_fold_uniquing.mlir
//
// 两条互不相干的 add：1.0+2.0 和 0.5+2.5，都折出 3.0。
// 如果 fold 是 Pattern（各自物化各自的常量），图里会出现两个
// dense<3.0> 节点；实测驱动（OperationFolder）按 (方言, 属性, 类型)
// 三元组去重——第二个 3.0 直接复用第一个物化出的节点：
//   %0 = mini.constant dense<3.000000e+00>
//   return %0, %0        ← 两个返回值共用同一个 %0
//
// 这是"fold 返回值、驱动管节点"分工的直接红利：Pattern 拿不到这张
// 全局去重表，fold 有。第 5.4 节用 -cse 做对照：Pattern 路线得靠
// 额外跑一遍 CSE 才能追平。
// CHECK-LABEL: func.func @uniquing(
// CHECK: %[[C:.*]] = mini.constant dense<3.000000e+00> : tensor<f32>
// CHECK: return %[[C]], %[[C]] : tensor<f32>, tensor<f32>
// CHECK-NOT: mini.add
// CHECK-NOT: mini.constant
module {
  func.func @uniquing() -> (tensor<f32>, tensor<f32>) {
    %a1 = mini.constant dense<1.0> : tensor<f32>
    %b1 = mini.constant dense<2.0> : tensor<f32>
    %s1 = mini.add %a1, %b1 : tensor<f32>, tensor<f32> -> tensor<f32>
    %a2 = mini.constant dense<0.5> : tensor<f32>
    %b2 = mini.constant dense<2.5> : tensor<f32>
    %s2 = mini.add %a2, %b2 : tensor<f32>, tensor<f32> -> tensor<f32>
    func.return %s1, %s2 : tensor<f32>, tensor<f32>
  }
}
