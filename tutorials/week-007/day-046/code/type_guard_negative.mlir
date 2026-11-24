// 第 46 天护栏实验：合法的 IR、保守的 Pattern。
//
//   %s = mini.add %arg0(类型 ?x3), dense<-0.0>(2x3) -> tensor<2x3xf32>
//
// Verifier 全程放行：classifyShapePair 对 ? 维保守跳过（?x3 与 2x3
// 记 Same，Day 40 的三分类裁判）。常量一侧也确实是全 -0.0。但
// SimplifyAddNegZero 的类型护栏发现 lhs 是 ?x3、结果是 2x3——两个
// 不同类型，替换会把 2x3 的值换成 ?x3 的值，func.return 的操作数
// 类型随之对不上。所以 Pattern 拒绝点火：这条 add 是"看得见、
// 动不得"的合法 IR。
//
// 期望：round-trip 原样（rc=0，一个 op 都不许少）。
// 把护栏删掉的变体里，这份文件会变成"优化后过不了验证"的反例
// （run_all.sh 第 6 步；第 6 节错误 3 的真实复现）。
// CHECK-LABEL: func.func @guard(
// CHECK: %[[Z:.*]] = mini.constant
// CHECK: %[[S:.*]] = mini.add %arg0, %[[Z]]
// CHECK: return %[[S]]
// CHECK-NOT: return %arg0
module {
  func.func @guard(%arg0: tensor<?x3xf32>) -> tensor<2x3xf32> {
    %z = mini.constant dense<-0.0> : tensor<2x3xf32>
    %s = mini.add %arg0, %z : tensor<?x3xf32>, tensor<2x3xf32> -> tensor<2x3xf32>
    func.return %s : tensor<2x3xf32>
  }
}
