// 负例 3：秩不同——2x2 * 2（矩阵乘向量）。
// 右对齐缺位补 1：右维 2 对 2 相等；左维 2 对隐式 1 → BroadcastOnly。
// 预期报错：同负例 2 的"would broadcast"口味（rc=1）。
// 看点：报错里能同时看到 tensor<2x2xf32> 和 tensor<2xf32> 两个原始类型。
func.func @mul_vec(%m: tensor<2x2xf32>, %v: tensor<2xf32>) -> tensor<2x2xf32> {
  %p = mini.mul %m, %v : tensor<2x2xf32>, tensor<2xf32> -> tensor<2x2xf32>
  func.return %p : tensor<2x2xf32>
}
