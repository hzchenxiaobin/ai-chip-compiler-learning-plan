// M09 bad_bias_shape（负例·Shape，对应 Python C12）——
// bias 是 2x3、乘积是 2x2：连广播都对不上（Mismatch），
// add 的 Verifier 直接报「两个操作数 shape 不匹配」。
// 期望判决 = verifier_reject（第一道闸门）
func.func @graph_bad_shape(%arg0: tensor<2x3xf32>, %arg1: tensor<3x2xf32>) -> tensor<2x2xf32> {
  %0 = mini.matmul %arg0, %arg1 : tensor<2x3xf32>, tensor<3x2xf32> -> tensor<2x2xf32>
  %1 = mini.add %0, %arg0 : tensor<2x2xf32>, tensor<2x3xf32> -> tensor<2x2xf32>
  %2 = mini.relu %1 : tensor<2x2xf32>
  return %2 : tensor<2x2xf32>
}
