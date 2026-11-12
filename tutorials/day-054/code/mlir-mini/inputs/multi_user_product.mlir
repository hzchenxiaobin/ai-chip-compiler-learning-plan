// multi_user_product.mlir —— 乘积 %0 被 add 和另一个 relu 同时使用：
// 默认策略下整条链原样保留（Day 52/53 规则），用于验证新管道下
// 「拒绝仍是恒等变换」。
func.func @graph_multi_product(%arg0: tensor<2x3xf32>, %arg1: tensor<3x2xf32>, %arg2: tensor<2x2xf32>) -> (tensor<2x2xf32>, tensor<2x2xf32>) {
  %0 = mini.matmul %arg0, %arg1 : tensor<2x3xf32>, tensor<3x2xf32> -> tensor<2x2xf32>
  %1 = mini.add %0, %arg2 : tensor<2x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
  %2 = mini.relu %1 : tensor<2x2xf32>
  %3 = mini.relu %0 : tensor<2x2xf32>
  return %2, %3 : tensor<2x2xf32>, tensor<2x2xf32>
}
