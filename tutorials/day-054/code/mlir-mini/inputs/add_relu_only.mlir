// add_relu_only.mlir —— 纯 Add + Relu 图（没有 matmul）：
// 小融合 fused_add_relu 在这张图上才是正确答案——修法不能误伤它。
func.func @graph_add_relu(%arg0: tensor<2x2xf32>, %arg1: tensor<2x2xf32>) -> tensor<2x2xf32> {
  %0 = mini.add %arg0, %arg1 : tensor<2x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
  %1 = mini.relu %0 : tensor<2x2xf32>
  return %1 : tensor<2x2xf32>
}
