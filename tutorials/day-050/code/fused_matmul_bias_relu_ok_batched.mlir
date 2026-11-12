// 第 50 天正例 3：batch 版融合算子。
// 2x2x3 · 2x3x2 = 2x2x2，bias 2x2x2 与结果一致。
// 走 verifyMatmulShapes 的规则 2（batch 维对齐）分支——
// 共享规则在融合算子上原样生效。
// 预期：rc=0。

func.func @fused_batched(%a: tensor<2x2x3xf32>, %b: tensor<2x3x2xf32>) -> tensor<2x2x2xf32> {
  %bias = mini.constant dense<[[[1.0, 0.0], [0.0, 1.0]], [[2.0, 0.0], [0.0, 2.0]]]> : tensor<2x2x2xf32>
  %y = mini.fused_matmul_bias_relu %a, %b, %bias :
       tensor<2x2x3xf32>, tensor<2x3x2xf32>, tensor<2x2x2xf32> -> tensor<2x2x2xf32>
  return %y : tensor<2x2x2xf32>
}
