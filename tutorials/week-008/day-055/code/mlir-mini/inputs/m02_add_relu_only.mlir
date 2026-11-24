// M02 add_relu_only（正例，对应 Python C03）——纯 Add + Relu：
// 小融合 fused_add_relu 的正确主场，验收管道不能误伤它。
// 期望判决 = fused（fused_add_relu，由让位版 P51g 完成）
func.func @graph_add_relu(%arg0: tensor<2x2xf32>, %arg1: tensor<2x2xf32>) -> tensor<2x2xf32> {
  %0 = mini.add %arg0, %arg1 : tensor<2x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
  %1 = mini.relu %0 : tensor<2x2xf32>
  return %1 : tensor<2x2xf32>
}
