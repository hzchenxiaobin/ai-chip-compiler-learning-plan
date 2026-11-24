// bad_layout.mlir —— 第 58 天错误现场：把「重排后的布局」谎报成「转置视图的布局」。
//
// memref.transpose 是纯元信息操作：在 strides=(32,8,4,1) 的 NCHW 存储
// 上做 (n,c,h,w)->(n,h,w,c)，唯一合法的结果 strides 是 (32,4,1,8)。
// 下面故意写成 (32,16,4,1)——那是「数据真的搬过家」之后的 strides
// （对应 layout_orders.mlir 里的 @nhwc）。Verifier 会在解析后立即拒绝：
// 元信息可以免费置换，但必须自洽，不能凭空捏造。

module {
  func.func @lied_layout(%x: memref<1x4x2x4xf32>)
      -> (index, index, index, index) {
    %t = memref.transpose %x (n, c, h, w) -> (n, h, w, c)
      : memref<1x4x2x4xf32> to memref<1x2x4x4xf32, strided<[32, 16, 4, 1]>>

    %base, %offset, %sizes:4, %strides:4 =
      memref.extract_strided_metadata %t
      : memref<1x2x4x4xf32, strided<[32, 16, 4, 1]>>
        -> memref<f32>, index, index, index, index, index,
           index, index, index, index
    return %strides#0, %strides#1, %strides#2, %strides#3
      : index, index, index, index
  }
}
