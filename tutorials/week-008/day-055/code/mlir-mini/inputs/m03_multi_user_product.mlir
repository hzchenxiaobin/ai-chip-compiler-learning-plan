// M03 multi_user_product（负例·多使用者，对应 Python C07）——
// 乘积 %0 被 add 和第二个 relu 同时使用：Day 52 铁律，
// 擦除生产者的前提是 use 表为空。期望判决 = identity（恒等拒绝）
func.func @graph_multi_product(%arg0: tensor<2x3xf32>, %arg1: tensor<3x2xf32>, %arg2: tensor<2x2xf32>) -> (tensor<2x2xf32>, tensor<2x2xf32>) {
  %0 = mini.matmul %arg0, %arg1 : tensor<2x3xf32>, tensor<3x2xf32> -> tensor<2x2xf32>
  %1 = mini.add %0, %arg2 : tensor<2x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
  %2 = mini.relu %1 : tensor<2x2xf32>
  %3 = mini.relu %0 : tensor<2x2xf32>
  return %2, %3 : tensor<2x2xf32>, tensor<2x2xf32>
}
