// 负例 4：动态维救不了 shape 错——?x3 * 4x2。
// 左维 ? 对 4：跳过（保守）；右维 3 对 2：双方静态、不等、无 1 → Mismatch。
// 预期报错：not broadcast-compatible（rc=1）。
// 和 Day 39 的 matmul_dynamic_bad_inner 同款思想：? 只放过"无法判定"的维，
// 铁证非法的维照样拦。
func.func @mul_dyn_bad(%a: tensor<?x3xf32>, %b: tensor<4x2xf32>) -> tensor<?x2xf32> {
  %p = mini.mul %a, %b : tensor<?x3xf32>, tensor<4x2xf32> -> tensor<?x2xf32>
  func.return %p : tensor<?x2xf32>
}
