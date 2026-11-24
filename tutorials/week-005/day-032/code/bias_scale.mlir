// bias_scale.mlir —— 第 32 天主示例（张量版，用于读／拆／验证）
// bias_scale(x) = (x + bias) × scale
// 输入输出：tensor<2x3xf32>（静态维：2 行 3 列，元素 f32）
// 两种常量属性各出现一次：
//   dense<[[…]]> ：逐元素给出数据的 DenseElementsAttr
//   dense<2.0>   ：splat——一个数铺满整个形状
// 注意：arith 的张量级算术 op 在 one-shot-bufferize 里没有转换规则
// （逐元素张量计算在 MLIR 生态里通常由 linalg 承接，后面的路），
// 所以这个文件用于第 5.3 节实验①②（round-trip 与 generic form）；
// 可执行版本见 bias_scale_run.mlir（亲手展开成标量循环）。
func.func @bias_scale(%x: tensor<2x3xf32>) -> tensor<2x3xf32> {
  // [值] %bias  [类型] tensor<2x3xf32>  [属性] value = dense<[[…]]>
  %bias = arith.constant dense<[[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]> : tensor<2x3xf32>
  // [值] %scale [类型] tensor<2x3xf32>  [属性] value = dense<2.0>（splat）
  %scale = arith.constant dense<2.0> : tensor<2x3xf32>
  // [使用] %x, %bias → [定义] %b：两个操作数类型必须与签名一致
  %b = arith.addf %x, %bias : tensor<2x3xf32>
  %s = arith.mulf %b, %scale : tensor<2x3xf32>
  return %s : tensor<2x3xf32>
}
