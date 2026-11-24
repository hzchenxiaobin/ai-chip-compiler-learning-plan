// 第 50 天负例 6（今天最重要的一条）：经典 [N] 风格 bias。
// bias tensor<2xf32>（rank-1，torch.nn.Linear 的写法）对结果 2x2：
// 语义上完全合法（按行广播），但今天不支持广播 —— 规则 5 报
// BroadcastOnly，明说 "see Day 60"。
// 为什么这条最重要：它证明 bias 用 Mini_F32Tensor（不限秩）而不是
// Mini_F32Tensor2DPlus 是对的——[N] bias 能通过 ODS 落到 Verifier，
// 换来一句指明出路的诊断，而不是一句干巴巴的 "rank >= 2 required"。
// 预期：rc=1，报错带 "would broadcast ... (see Day 60)"。

func.func @fused_bias_broadcast(%a: tensor<2x3xf32>, %b: tensor<3x2xf32>) -> tensor<2x2xf32> {
  %bias = mini.constant dense<[0.5, -1.0]> : tensor<2xf32>
  %y = mini.fused_matmul_bias_relu %a, %b, %bias :
       tensor<2x3xf32>, tensor<3x2xf32>, tensor<2xf32> -> tensor<2x2xf32>
  return %y : tensor<2x2xf32>
}
