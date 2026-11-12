// M07 mixed_dtype_bias（负例·类型不支持，对应 Python C11）——
// matmul 乘积是 f32，bias 是 f64：add 的 Verifier 只看形状（Same 放行），
// 拦下它的是 P3 的类型闸门（涉及张量必须全 f32）。
// 期望判决 = identity（恒等拒绝，第二道防线）
func.func @graph_mixed_bias(%arg0: tensor<2x3xf32>, %arg1: tensor<3x2xf32>, %arg2: tensor<2x2xf64>) -> tensor<2x2xf32> {
  %0 = mini.matmul %arg0, %arg1 : tensor<2x3xf32>, tensor<3x2xf32> -> tensor<2x2xf32>
  %1 = mini.add %0, %arg2 : tensor<2x2xf32>, tensor<2x2xf64> -> tensor<2x2xf32>
  %2 = mini.relu %1 : tensor<2x2xf32>
  return %2 : tensor<2x2xf32>
}
