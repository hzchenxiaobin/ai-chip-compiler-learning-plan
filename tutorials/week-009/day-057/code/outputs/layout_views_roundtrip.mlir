module {
  memref.global constant @storage : memref<2x3xf32> = dense<[[0.000000e+00, 1.000000e+00, 2.000000e+00], [3.000000e+00, 4.000000e+00, 5.000000e+00]]>
  func.func @transpose_view() -> (index, index, index) {
    %0 = memref.get_global @storage : memref<2x3xf32>
    %transpose = memref.transpose %0 (d0, d1) -> (d1, d0) : memref<2x3xf32> to memref<3x2xf32, strided<[1, 3]>>
    %base_buffer, %offset, %sizes:2, %strides:2 = memref.extract_strided_metadata %transpose : memref<3x2xf32, strided<[1, 3]>> -> memref<f32>, index, index, index, index, index
    return %offset, %strides#0, %strides#1 : index, index, index
  }
  func.func @offset_view(%arg0: memref<f32>) -> (index, index, index) {
    %reinterpret_cast = memref.reinterpret_cast %arg0 to offset: [1], sizes: [2, 2], strides: [2, 1] : memref<f32> to memref<2x2xf32, strided<[2, 1], offset: 1>>
    %base_buffer, %offset, %sizes:2, %strides:2 = memref.extract_strided_metadata %reinterpret_cast : memref<2x2xf32, strided<[2, 1], offset: 1>> -> memref<f32>, index, index, index, index, index
    return %offset, %strides#0, %strides#1 : index, index, index
  }
}

