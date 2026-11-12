// M06 f64_add_relu（负例·类型不支持，对应 Python C09）——
// 全 f64 的 Add + Relu：mini.add / mini.relu 的 Verifier 不检查
// 元素类型（形状 Same 就放行），拦下它的是 Pattern 里的类型闸门：
// fused_add_relu 的语义只对 f32 验证过。
// 期望判决 = identity（恒等拒绝，第二道防线）
func.func @graph_f64_add_relu(%arg0: tensor<2x2xf64>, %arg1: tensor<2x2xf64>) -> tensor<2x2xf64> {
  %0 = mini.add %arg0, %arg1 : tensor<2x2xf64>, tensor<2x2xf64> -> tensor<2x2xf64>
  %1 = mini.relu %0 : tensor<2x2xf64>
  return %1 : tensor<2x2xf64>
}
