// 第 114 天对照输入 B：把“第一次 Lowering 之前”的源图直接喂给最终 Lowering。
// 这是 D83 五道闸管道交付的干净 tensor 图（mini 方言），本来应该先进 D85~D105
// 的第一段 Lowering（tensor -> memref，mini.matmul -> 循环），才轮到今天。
// 用它检验：ConversionTarget（mini 非法）＋ TypeConverter（tensor 拒收）
// 这两道闸是不是真的会把管道顺序错误拦下来，而不是悄悄漏过去。
func @main(%x: tensor<4x6xf32>, %w: tensor<6x3xf32>) -> tensor<4x3xf32> {
  %c = mini.matmul(%x, %w) : (tensor<4x6xf32>, tensor<6x3xf32>) -> tensor<4x3xf32>
  return %c : tensor<4x3xf32>
}
