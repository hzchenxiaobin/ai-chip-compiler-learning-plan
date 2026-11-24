module {
  memref.global constant @nchw : memref<1x4x2x4xf32> = dense<[[[[0.000000e+00, 1.000000e+00, 2.000000e+00, 3.000000e+00], [4.000000e+00, 5.000000e+00, 6.000000e+00, 7.000000e+00]], [[8.000000e+00, 9.000000e+00, 1.000000e+01, 1.100000e+01], [1.200000e+01, 1.300000e+01, 1.400000e+01, 1.500000e+01]], [[1.600000e+01, 1.700000e+01, 1.800000e+01, 1.900000e+01], [2.000000e+01, 2.100000e+01, 2.200000e+01, 2.300000e+01]], [[2.400000e+01, 2.500000e+01, 2.600000e+01, 2.700000e+01], [2.800000e+01, 2.900000e+01, 3.000000e+01, 3.100000e+01]]]]>
  memref.global constant @nhwc : memref<1x2x4x4xf32> = dense<[[[[0.000000e+00, 8.000000e+00, 1.600000e+01, 2.400000e+01], [1.000000e+00, 9.000000e+00, 1.700000e+01, 2.500000e+01], [2.000000e+00, 1.000000e+01, 1.800000e+01, 2.600000e+01], [3.000000e+00, 1.100000e+01, 1.900000e+01, 2.700000e+01]], [[4.000000e+00, 1.200000e+01, 2.000000e+01, 2.800000e+01], [5.000000e+00, 1.300000e+01, 2.100000e+01, 2.900000e+01], [6.000000e+00, 1.400000e+01, 2.200000e+01, 3.000000e+01], [7.000000e+00, 1.500000e+01, 2.300000e+01, 3.100000e+01]]]]>
  func.func @nhwc_view_metadata(%arg0: memref<1x4x2x4xf32>) -> (index, index, index, index, index) {
    %transpose = memref.transpose %arg0 (d0, d1, d2, d3) -> (d0, d2, d3, d1) : memref<1x4x2x4xf32> to memref<1x2x4x4xf32, strided<[32, 4, 1, 8]>>
    %base_buffer, %offset, %sizes:4, %strides:4 = memref.extract_strided_metadata %transpose : memref<1x2x4x4xf32, strided<[32, 4, 1, 8]>> -> memref<f32>, index, index, index, index, index, index, index, index, index
    return %offset, %strides#0, %strides#1, %strides#2, %strides#3 : index, index, index, index, index
  }
  func.func @same_pixel_two_offsets() -> (index, index) {
    %0 = memref.get_global @nchw : memref<1x4x2x4xf32>
    %1 = memref.get_global @nhwc : memref<1x2x4x4xf32>
    %base_buffer, %offset, %sizes:4, %strides:4 = memref.extract_strided_metadata %0 : memref<1x4x2x4xf32> -> memref<f32>, index, index, index, index, index, index, index, index, index
    %base_buffer_0, %offset_1, %sizes_2:4, %strides_3:4 = memref.extract_strided_metadata %1 : memref<1x2x4x4xf32> -> memref<f32>, index, index, index, index, index, index, index, index, index
    %c2 = arith.constant 2 : index
    %c1 = arith.constant 1 : index
    %c3 = arith.constant 3 : index
    %2 = arith.muli %c2, %strides#1 : index
    %3 = arith.muli %c1, %strides#2 : index
    %4 = arith.muli %c3, %strides#3 : index
    %5 = arith.addi %offset, %2 : index
    %6 = arith.addi %5, %3 : index
    %7 = arith.addi %6, %4 : index
    %8 = arith.muli %c1, %strides_3#1 : index
    %9 = arith.muli %c3, %strides_3#2 : index
    %10 = arith.muli %c2, %strides_3#3 : index
    %11 = arith.addi %offset_1, %8 : index
    %12 = arith.addi %11, %9 : index
    %13 = arith.addi %12, %10 : index
    return %7, %13 : index, index
  }
  func.func private @printF32(f32)
  func.func private @printNewline()
  func.func @main() {
    %0 = memref.get_global @nchw : memref<1x4x2x4xf32>
    %1 = memref.get_global @nhwc : memref<1x2x4x4xf32>
    %c0 = arith.constant 0 : index
    %c2 = arith.constant 2 : index
    %c1 = arith.constant 1 : index
    %c3 = arith.constant 3 : index
    %2 = memref.load %0[%c0, %c2, %c1, %c3] : memref<1x4x2x4xf32>
    %3 = memref.load %1[%c0, %c1, %c3, %c2] : memref<1x2x4x4xf32>
    call @printF32(%2) : (f32) -> ()
    call @printNewline() : () -> ()
    call @printF32(%3) : (f32) -> ()
    call @printNewline() : () -> ()
    return
  }
}

