// journey.mlir —— 第 56 天复盘主线：一条 IR 的四站旅程
//
// 链 1（大融合原料）：两个 0.5 常量相加（站 3 折叠），
//   matmul 结果故意写 ?x2（站 2 推导细化），
//   加 bias 再过 relu（站 4 三算子融合）。
// 链 2（小融合原料）：普通 add + relu（站 4 小融合）。
// 输入 8 个 mini.* 算子，四站走完剩 3 个。

func.func @journey(%a: tensor<2x3xf32>, %b: tensor<3x2xf32>,
                   %x: tensor<2x2xf32>, %w: tensor<2x2xf32>)
    -> (tensor<?x2xf32>, tensor<2x2xf32>) {
  %c0 = mini.constant dense<5.000000e-01> : tensor<2x2xf32>
  %c1 = mini.constant dense<5.000000e-01> : tensor<2x2xf32>
  %one = mini.add %c0, %c1 : tensor<2x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
  %m = mini.matmul %a, %b : tensor<2x3xf32>, tensor<3x2xf32> -> tensor<?x2xf32>
  %s = mini.add %m, %one : tensor<?x2xf32>, tensor<2x2xf32> -> tensor<?x2xf32>
  %r = mini.relu %s : tensor<?x2xf32>
  %t = mini.add %x, %w : tensor<2x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
  %u = mini.relu %t : tensor<2x2xf32>
  return %r, %u : tensor<?x2xf32>, tensor<2x2xf32>
}
