// 第 48 天 Pattern 冲突实验：同一个 mini.add 根节点，三种适用局面。
//
//   (1) %both    = add(常量 5.0, 常量 -0.0)
//       两条生产线都想动手：SimplifyAddNegZero 说“右侧是 -0.0，换成
//       左侧”；fold 说“两个常量，我直接算出 5.0 + (-0.0) = 5.0”。
//       这是 mini 里真实存在的“冲突”——两条路算出的最终值相同
//       （IEEE：5.0 + (-0.0) = 5.0），所以无论谁先动手，输出收敛到
//       同一个 IR：一个值 5.0 的常量。
//   (2) %foldonly = add(非 splat 常量, splat 常量 2.0)
//       只有 fold 适用：代数化简的常量匹配要求 splat（全体元素同一
//       恒等值），dense<[[1,2],[3,4]]> 没有整体恒等元；fold 逐元素
//       照算不误 → [[3,4],[5,6]]。
//   (3) %patonly  = add(入口参数, 常量 -0.0)
//       只有 Pattern 适用：fold 需要两个操作数都是常量，%x 是运行期
//       才知道的值；代数化简只要求“被加的数是常量 -0.0”→ 换成 %x。
//
// CHECK 行断言三个局面合力之后的最终形态（三层 add 全部级联折叠 +
// %patonly 被 Pattern 塌缩成入口参数，只剩一个 add）：
//
// CHECK-LABEL: func.func @conflict(
// CHECK: %[[C:.*]] = mini.constant dense<{{\[\[8\.000000e\+00, 9\.000000e\+00\], \[1\.000000e\+01, 1\.100000e\+01\]\]}}> : tensor<2x2xf32>
// CHECK: %[[S:.*]] = mini.add %[[C]], %arg0 : tensor<2x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
// CHECK: return %[[S]] : tensor<2x2xf32>
// CHECK-NOT: mini.mul
// CHECK-NOT: mini.relu
module {
  func.func @conflict(%x: tensor<2x2xf32>) -> tensor<2x2xf32> {
    %c5 = mini.constant dense<5.0> : tensor<2x2xf32>
    %cnz = mini.constant dense<-0.0> : tensor<2x2xf32>
    %both = mini.add %c5, %cnz : tensor<2x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
    %cns = mini.constant dense<[[1.0, 2.0], [3.0, 4.0]]> : tensor<2x2xf32>
    %c2 = mini.constant dense<2.0> : tensor<2x2xf32>
    %foldonly = mini.add %cns, %c2 : tensor<2x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
    %patonly = mini.add %x, %cnz : tensor<2x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
    %r = mini.add %both, %foldonly : tensor<2x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
    %r2 = mini.add %r, %patonly : tensor<2x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
    func.return %r2 : tensor<2x2xf32>
  }
}
