module {
  memref.global constant @nchw : memref<1x4x2x4xf32> = dense<[[[[0.000000e+00, 1.000000e+00, 2.000000e+00, 3.000000e+00], [4.000000e+00, 5.000000e+00, 6.000000e+00, 7.000000e+00]], [[8.000000e+00, 9.000000e+00, 1.000000e+01, 1.100000e+01], [1.200000e+01, 1.300000e+01, 1.400000e+01, 1.500000e+01]], [[1.600000e+01, 1.700000e+01, 1.800000e+01, 1.900000e+01], [2.000000e+01, 2.100000e+01, 2.200000e+01, 2.300000e+01]], [[2.400000e+01, 2.500000e+01, 2.600000e+01, 2.700000e+01], [2.800000e+01, 2.900000e+01, 3.000000e+01, 3.100000e+01]]]]>
  memref.global constant @nhwc : memref<1x2x4x4xf32> = dense<[[[[0.000000e+00, 8.000000e+00, 1.600000e+01, 2.400000e+01], [1.000000e+00, 9.000000e+00, 1.700000e+01, 2.500000e+01], [2.000000e+00, 1.000000e+01, 1.800000e+01, 2.600000e+01], [3.000000e+00, 1.100000e+01, 1.900000e+01, 2.700000e+01]], [[4.000000e+00, 1.200000e+01, 2.000000e+01, 2.800000e+01], [5.000000e+00, 1.300000e+01, 2.100000e+01, 2.900000e+01], [6.000000e+00, 1.400000e+01, 2.200000e+01, 3.000000e+01], [7.000000e+00, 1.500000e+01, 2.300000e+01, 3.100000e+01]]]]>
  func.func @nhwc_view_metadata(%arg0: memref<1x4x2x4xf32>) -> (index, index, index, index, index) {
    %c0 = arith.constant 0 : index
    %c32 = arith.constant 32 : index
    %c4 = arith.constant 4 : index
    %c1 = arith.constant 1 : index
    %c8 = arith.constant 8 : index
    return %c0, %c32, %c4, %c1, %c8 : index, index, index, index, index
  }
  func.func @same_pixel_two_offsets() -> (index, index) {
    %c23 = arith.constant 23 : index
    %c30 = arith.constant 30 : index
    return %c23, %c30 : index, index
  }
  func.func private @printF32(f32)
  func.func private @printNewline()
  func.func @main() {
    %c3 = arith.constant 3 : index
    %c1 = arith.constant 1 : index
    %c2 = arith.constant 2 : index
    %c0 = arith.constant 0 : index
    %0 = memref.get_global @nchw : memref<1x4x2x4xf32>
    %1 = memref.get_global @nhwc : memref<1x2x4x4xf32>
    %2 = memref.load %0[%c0, %c2, %c1, %c3] : memref<1x4x2x4xf32>
    %3 = memref.load %1[%c0, %c1, %c3, %c2] : memref<1x2x4x4xf32>
    call @printF32(%2) : (f32) -> ()
    call @printNewline() : () -> ()
    call @printF32(%3) : (f32) -> ()
    call @printNewline() : () -> ()
    return
  }
}

