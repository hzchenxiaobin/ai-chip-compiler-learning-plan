// M10 bad_bias_broadcast（负例·Shape，对应 Python C13）——
// bias 是 [2] 向量、乘积是 2x2：需要广播——第 40 天起故意不支持
// （第 60 天才放行），add 的 Verifier 报「需要广播」。
// 期望判决 = verifier_reject（第一道闸门）
func.func @graph_bad_broadcast(%arg0: tensor<2x3xf32>, %arg1: tensor<3x2xf32>, %arg2: tensor<2xf32>) -> tensor<2x2xf32> {
  %0 = mini.matmul %arg0, %arg1 : tensor<2x3xf32>, tensor<3x2xf32> -> tensor<2x2xf32>
  %1 = mini.add %0, %arg2 : tensor<2x2xf32>, tensor<2xf32> -> tensor<2x2xf32>
  %2 = mini.relu %1 : tensor<2x2xf32>
  return %2 : tensor<2x2xf32>
}
