// bad_reshape.mlir —— 第 59 天常见错误现场：Verifier 应拒绝的 reshape。
//
// 运行：mlir-opt bad_reshape.mlir   （预期 exit=1，逐条打印诊断）
//
// 三个「房间」，对应三类真实错误（mlir-opt 遇到第一个错误即停止）：
//   房间 1：非连续视图上合并维度（最经典的 Reshape 错误）
//   房间 2：memref.reshape 的源不是 identity 布局
//   房间 3：expand_shape 的重关联尺寸对不上（元素数量违规）

// ---- 房间 1：转置视图 (4,3) strided<[1,4]> 上 collapse 成 (12,) ----
// 外维步长 1 != 内维容量 3 x 内维步长 4 = 12，打包条件不成立，
// (12,) 需要等差读序，而转置读序是 [0,4,8,1,5,9,...]——必须搬家。
func.func @collapse_transposed(%arg0: memref<3x4xf32>) -> memref<12xf32> {
  %t = memref.transpose %arg0 (d0, d1) -> (d1, d0)
    : memref<3x4xf32> to memref<4x3xf32, strided<[1, 4]>>
  %0 = memref.collapse_shape %t [[0, 1]]
    : memref<4x3xf32, strided<[1, 4]>> into memref<12xf32>
  return %0 : memref<12xf32>
}

// ---- 房间 2：memref.reshape 只接受 identity 布局的源 ----
// 转置视图的布局是 strided<[1,4]>，不是行主序——直接拒绝。
func.func @reshape_strided_source(%arg0: memref<3x4xf32>,
                                  %shape: memref<1xindex>) -> memref<12xf32> {
  %t = memref.transpose %arg0 (d0, d1) -> (d1, d0)
    : memref<3x4xf32> to memref<4x3xf32, strided<[1, 4]>>
  %0 = memref.reshape %t(%shape)
    : (memref<4x3xf32, strided<[1, 4]>>, memref<1xindex>) -> memref<12xf32>
  return %0 : memref<12xf32>
}

// ---- 房间 3：expand_shape 的分组尺寸对不上 ----
// 源第 1 维大小是 4，重关联组 [1,2] 对应的结果维 3x2=6，4 != 6。
func.func @expand_wrong_group(%arg0: memref<3x4xf32>) -> memref<3x3x2xf32> {
  %0 = memref.expand_shape %arg0 [[0], [1, 2]]
    : memref<3x4xf32> into memref<3x3x2xf32>
  return %0 : memref<3x3x2xf32>
}
