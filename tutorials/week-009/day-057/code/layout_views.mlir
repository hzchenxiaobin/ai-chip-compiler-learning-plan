// layout_views.mlir —— 第 57 天：MLIR 里同一底层存储的连续视图与转置视图。
//
// 与 layout_lab.py 用同一份数据：2x3 f32，元素值 == 物理位置（0..5）。
// memref.transpose 是纯元信息操作（metadata-only）：不搬数据，
// 只把 sizes/strides 做一次置换，产出的类型正是 memref<3x2xf32, strided<[1, 3]>>。
//
// 运行（解析 + 验证 + 打印）：
//   mlir-opt layout_views.mlir
// 观察折叠（编译器静态读出布局元数据）：
//   mlir-opt --canonicalize layout_views.mlir

module {
  // 底层存储：一块 2x3 行主序的常量内存（对应 numpy 里那个 store.reshape(2,3)）
  memref.global constant @storage : memref<2x3xf32> =
    dense<[[0.0, 1.0, 2.0], [3.0, 4.0, 5.0]]>

  // 取出视图并转置：(i, j) -> (j, i) 只换元信息
  // 结果类型 strided<[1, 3], offset: 0> 与 numpy 的 T.strides=(1,3) 完全同口径
  func.func @transpose_view() -> (index, index, index) {
    %s = memref.get_global @storage : memref<2x3xf32>
    %t = memref.transpose %s (i, j) -> (j, i)
      : memref<2x3xf32> to memref<3x2xf32, strided<[1, 3]>>

    // 把转置视图的 (offset, sizes, strides) 拆成 SSA 值
    %base, %offset, %sizes:2, %strides:2 =
      memref.extract_strided_metadata %t
      : memref<3x2xf32, strided<[1, 3]>> -> memref<f32>, index, index, index, index, index
    return %offset, %strides#0, %strides#1 : index, index, index
  }

  // 非零偏移的视图：对应 layout_lab.py 里的 B = store[1:5].reshape(2,2)
  // reinterpret_cast 在「元素粒度」上改写 offset/sizes/strides，同样不搬数据
  func.func @offset_view(%base: memref<f32>) -> (index, index, index) {
    %b = memref.reinterpret_cast %base to
      offset: [1],
      sizes: [2, 2],
      strides: [2, 1]
      : memref<f32> to memref<2x2xf32, strided<[2, 1], offset: 1>>
    %base2, %offset, %sizes:2, %strides:2 =
      memref.extract_strided_metadata %b
      : memref<2x2xf32, strided<[2, 1], offset: 1>> -> memref<f32>, index, index, index, index, index
    return %offset, %strides#0, %strides#1 : index, index, index
  }
}
