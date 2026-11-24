// 第 50 天负例 1：bias 风格的 1x2 对 2x2 —— BroadcastOnly。
// fused_add_relu(2x2, 1x2)：numpy 意义下能广播成 2x2，但今天的
// 规则 1（与 mini.add 同款）只收完全一致的 shape。
// 预期：rc=1，报错带 "would broadcast ... see Day 60"。

func.func @fused_add_relu_broadcast(%a: tensor<2x2xf32>) -> tensor<2x2xf32> {
  %bias = mini.constant dense<[[1.0, 2.0]]> : tensor<1x2xf32>
  %r = mini.fused_add_relu %a, %bias : tensor<2x2xf32>, tensor<1x2xf32> -> tensor<2x2xf32>
  return %r : tensor<2x2xf32>
}
