// journey_bad.mlir —— 复盘对照 3：验证站拦截（旅程短路）
//
// 主线图的 f64 变体：matmul 的元素类型不是 f32，站 1 的
// parse + verify 直接拦下，后面三站（推导/折叠/融合）根本
// 没有机会运行——验证站站在最前面，失败即短路。

func.func @journey_bad(%a: tensor<2x3xf64>, %b: tensor<3x2xf64>)
    -> tensor<2x2xf64> {
  %m = mini.matmul %a, %b : tensor<2x3xf64>, tensor<3x2xf64> -> tensor<2x2xf64>
  return %m : tensor<2x2xf64>
}
