// M04 shared_result（负例·额外使用，对应 Python C08）——
// 加法结果 %1 被 relu 和 return 同时使用：不能吸收 Relu，
// 半融合形态（fused_matmul_bias + relu）是所有路线的不动点。
// 期望判决 = fused（半融合，注意不是 fused_matmul_bias_relu）
func.func @graph_shared_result(%arg0: tensor<2x3xf32>, %arg1: tensor<3x2xf32>, %arg2: tensor<2x2xf32>) -> (tensor<2x2xf32>, tensor<2x2xf32>) {
  %0 = mini.matmul %arg0, %arg1 : tensor<2x3xf32>, tensor<3x2xf32> -> tensor<2x2xf32>
  %1 = mini.add %0, %arg2 : tensor<2x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
  %2 = mini.relu %1 : tensor<2x2xf32>
  return %2, %1 : tensor<2x2xf32>, tensor<2x2xf32>
}
