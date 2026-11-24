// journey_shared.mlir —— 复盘对照 2：加法结果被 return 共用（半融合不动点）
//
// %s 有两个使用者（return 和 relu）：P3 照融 MatMul+Add，
// 但不吸收 Relu；P2 随后访问 relu，发现融合结果仍有 2 个使用者，
// 也不能吸。任何遍历都停在同一形态：fused_matmul_bias + relu。
// 这是「融合不仅是图模式替换」的第一手证据：结构匹配成立了，
// use 表不答应。

func.func @journey_shared(%a: tensor<2x3xf32>, %b: tensor<3x2xf32>,
                          %bias: tensor<2x2xf32>)
    -> (tensor<2x2xf32>, tensor<2x2xf32>) {
  %m = mini.matmul %a, %b : tensor<2x3xf32>, tensor<3x2xf32> -> tensor<2x2xf32>
  %s = mini.add %m, %bias : tensor<2x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
  %r = mini.relu %s : tensor<2x2xf32>
  return %s, %r : tensor<2x2xf32>, tensor<2x2xf32>
}
