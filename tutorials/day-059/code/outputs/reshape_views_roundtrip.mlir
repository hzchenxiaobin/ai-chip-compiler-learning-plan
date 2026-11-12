module {
  memref.global constant @data12 : memref<3x4xf32> = dense<[[0.000000e+00, 1.000000e+00, 2.000000e+00, 3.000000e+00], [4.000000e+00, 5.000000e+00, 6.000000e+00, 7.000000e+00], [8.000000e+00, 9.000000e+00, 1.000000e+01, 1.100000e+01]]>
  func.func @expand_metadata() -> (index, index, index, index, index, index, index) {
    %0 = memref.get_global @data12 : memref<3x4xf32>
    %expand_shape = memref.expand_shape %0 [[0], [1, 2]] : memref<3x4xf32> into memref<3x2x2xf32>
    %base_buffer, %offset, %sizes:3, %strides:3 = memref.extract_strided_metadata %expand_shape : memref<3x2x2xf32> -> memref<f32>, index, index, index, index, index, index, index
    return %offset, %sizes#0, %sizes#1, %sizes#2, %strides#0, %strides#1, %strides#2 : index, index, index, index, index, index, index
  }
  func.func @collapse_metadata() -> (index, index, index) {
    %0 = memref.get_global @data12 : memref<3x4xf32>
    %subview = memref.subview %0[0, 0] [3, 2] [1, 2] : memref<3x4xf32> to memref<3x2xf32, strided<[4, 2]>>
    %collapse_shape = memref.collapse_shape %subview [[0, 1]] : memref<3x2xf32, strided<[4, 2]>> into memref<6xf32, strided<[2]>>
    %base_buffer, %offset, %sizes, %strides = memref.extract_strided_metadata %collapse_shape : memref<6xf32, strided<[2]>> -> memref<f32>, index, index, index
    return %offset, %sizes, %strides : index, index, index
  }
  func.func @roundtrip(%arg0: memref<3x4xf32>) -> memref<3x4xf32> {
    %expand_shape = memref.expand_shape %arg0 [[0], [1, 2]] : memref<3x4xf32> into memref<3x2x2xf32>
    %collapse_shape = memref.collapse_shape %expand_shape [[0], [1, 2]] : memref<3x2x2xf32> into memref<3x4xf32>
    return %collapse_shape : memref<3x4xf32>
  }
  func.func private @printF32(f32)
  func.func private @printNewline()
  func.func @main() {
    %0 = memref.get_global @data12 : memref<3x4xf32>
    %c0 = arith.constant 0 : index
    %c1 = arith.constant 1 : index
    %c4 = arith.constant 4 : index
    %c2 = arith.constant 2 : index
    %c6 = arith.constant 6 : index
    %expand_shape = memref.expand_shape %0 [[0], [1, 2]] : memref<3x4xf32> into memref<3x2x2xf32>
    %1 = memref.load %expand_shape[%c1, %c1, %c0] : memref<3x2x2xf32>
    %subview = memref.subview %0[0, 0] [3, 2] [1, 2] : memref<3x4xf32> to memref<3x2xf32, strided<[4, 2]>>
    %collapse_shape = memref.collapse_shape %subview [[0, 1]] : memref<3x2xf32, strided<[4, 2]>> into memref<6xf32, strided<[2]>>
    %2 = memref.load %collapse_shape[%c4] : memref<6xf32, strided<[2]>>
    %alloca = memref.alloca() : memref<2xindex>
    memref.store %c2, %alloca[%c0] : memref<2xindex>
    memref.store %c6, %alloca[%c1] : memref<2xindex>
    %reshape = memref.reshape %0(%alloca) : (memref<3x4xf32>, memref<2xindex>) -> memref<2x6xf32>
    %3 = memref.load %reshape[%c1, %c4] : memref<2x6xf32>
    call @printF32(%1) : (f32) -> ()
    call @printNewline() : () -> ()
    call @printF32(%2) : (f32) -> ()
    call @printNewline() : () -> ()
    call @printF32(%3) : (f32) -> ()
    call @printNewline() : () -> ()
    return
  }
}

