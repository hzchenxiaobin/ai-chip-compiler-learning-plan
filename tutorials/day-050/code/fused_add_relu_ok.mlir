// 第 50 天正例 1：mini.fused_add_relu 的 round-trip。
// 语义：res = relu(lhs + rhs)，2x2 + 2x2 -> 2x2。
// 预期：解析 → 验证（两条规则全过）→ 原样打印，rc=0。

func.func @fused_add_relu_ok(%a: tensor<2x2xf32>, %b: tensor<2x2xf32>) -> tensor<2x2xf32> {
  %r = mini.fused_add_relu %a, %b : tensor<2x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
  return %r : tensor<2x2xf32>
}
