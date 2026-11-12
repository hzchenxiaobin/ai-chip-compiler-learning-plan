// 探针 1：全静态。2x3 · 3x2 的结果类型早已写死 2x2，
// 推导算出的也是 2x2 —— 无信息可补，Pass 应原样放行（统计为 0）。
//
// 注意：函数没有结果值，matmul 的结果也不 return 出去。
// 这不是偷懒：结果类型一旦被细化，func.return 的操作数类型
// 就和函数签名对不上（详见 probe_return_mismatch.mlir 的实测）。

func.func @static_ok(%a: tensor<2x3xf32>, %b: tensor<3x2xf32>) {
  %0 = mini.matmul %a, %b : tensor<2x3xf32>, tensor<3x2xf32> -> tensor<2x2xf32>
  func.return
}
