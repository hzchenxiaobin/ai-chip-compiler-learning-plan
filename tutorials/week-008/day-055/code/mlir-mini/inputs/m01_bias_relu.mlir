// M01 bias_relu（正例，对应 Python C01）——主线图：
// MatMul -> Add(bias) -> Relu，全部单使用者。
// 期望判决 = fused（fused_matmul_bias_relu，一步到位）
func.func @graph_bias_relu(%arg0: tensor<2x3xf32>, %arg1: tensor<3x2xf32>, %arg2: tensor<2x2xf32>) -> tensor<2x2xf32> {
  %0 = mini.matmul %arg0, %arg1 : tensor<2x3xf32>, tensor<3x2xf32> -> tensor<2x2xf32>
  %1 = mini.add %0, %arg2 : tensor<2x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
  %2 = mini.relu %1 : tensor<2x2xf32>
  return %2 : tensor<2x2xf32>
}
