// M05 both_matmul（负例·歧义，对应 Python C10）——
// add 两侧都是 mini.matmul 乘积：分不清谁是 bias，拒绝融合。
// （形状上完全合法：两个 2x2 相加；拦下它的是 Pattern 的判定规则，
//   不是 Verifier——这正是「负例的第二道闸门」的实例。）
// 期望判决 = identity（恒等拒绝）
func.func @graph_both_matmul(%arg0: tensor<2x3xf32>, %arg1: tensor<3x2xf32>, %arg2: tensor<2x3xf32>, %arg3: tensor<3x2xf32>) -> tensor<2x2xf32> {
  %0 = mini.matmul %arg0, %arg1 : tensor<2x3xf32>, tensor<3x2xf32> -> tensor<2x2xf32>
  %1 = mini.matmul %arg2, %arg3 : tensor<2x3xf32>, tensor<3x2xf32> -> tensor<2x2xf32>
  %2 = mini.add %0, %1 : tensor<2x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
  %3 = mini.relu %2 : tensor<2x2xf32>
  return %3 : tensor<2x2xf32>
}
