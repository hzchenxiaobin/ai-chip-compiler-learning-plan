// probe_reshape_chain.mlir —— 探针 2（反例 R2：形状语义）
//
// Reshape 链 (2,3) -> (6,) -> (3,2)：值上等价于直接 (2,3) -> (3,2)。
// mini 侧（Day 66）用带守卫的 Pattern 合并成一层；
// stock --canonicalize 不做这个合并——两层 tensor.reshape 原样保留。
// 注意 Day 69 的真实 bug：错误版本把 Reshape(Reshape(x,t),t) 透传成 x，
// 被 Verifier 拦截（[V1] perm 对 rank 不合法）。

func.func @reshape_chain(%x: tensor<2x3xf32>) -> tensor<3x2xf32> {
  %c6 = arith.constant dense<[6]> : tensor<1xi32>
  %c32 = arith.constant dense<[3, 2]> : tensor<2xi32>
  %a = tensor.reshape %x(%c6) : (tensor<2x3xf32>, tensor<1xi32>) -> tensor<6xf32>
  %b = tensor.reshape %a(%c32) : (tensor<6xf32>, tensor<2xi32>) -> tensor<3x2xf32>
  return %b : tensor<3x2xf32>
}
