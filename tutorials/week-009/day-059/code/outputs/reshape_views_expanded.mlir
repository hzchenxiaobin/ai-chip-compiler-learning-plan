module {
  memref.global constant @data12 : memref<3x4xf32> = dense<[[0.000000e+00, 1.000000e+00, 2.000000e+00, 3.000000e+00], [4.000000e+00, 5.000000e+00, 6.000000e+00, 7.000000e+00], [8.000000e+00, 9.000000e+00, 1.000000e+01, 1.100000e+01]]>
  func.func @expand_metadata() -> (index, index, index, index, index, index, index) {
    %c0 = arith.constant 0 : index
    %c3 = arith.constant 3 : index
    %c2 = arith.constant 2 : index
    %c4 = arith.constant 4 : index
    %c1 = arith.constant 1 : index
    return %c0, %c3, %c2, %c2, %c4, %c2, %c1 : index, index, index, index, index, index, index
  }
  func.func @collapse_metadata() -> (index, index, index) {
    %c0 = arith.constant 0 : index
    %c6 = arith.constant 6 : index
    %c2 = arith.constant 2 : index
    return %c0, %c6, %c2 : index, index, index
  }
  func.func @roundtrip(%arg0: memref<3x4xf32>) -> memref<3x4xf32> {
    return %arg0 : memref<3x4xf32>
  }
  func.func private @printF32(f32)
  func.func private @printNewline()
  func.func @main() {
    %c6 = arith.constant 6 : index
    %c2 = arith.constant 2 : index
    %c4 = arith.constant 4 : index
    %c1 = arith.constant 1 : index
    %c0 = arith.constant 0 : index
    %0 = memref.get_global @data12 : memref<3x4xf32>
    %reinterpret_cast = memref.reinterpret_cast %0 to offset: [0], sizes: [3, 2, 2], strides: [4, 2, 1] : memref<3x4xf32> to memref<3x2x2xf32>
    %1 = memref.load %reinterpret_cast[%c1, %c1, %c0] : memref<3x2x2xf32>
    %reinterpret_cast_0 = memref.reinterpret_cast %0 to offset: [0], sizes: [6], strides: [2] : memref<3x4xf32> to memref<6xf32, strided<[2]>>
    %2 = memref.load %reinterpret_cast_0[%c4] : memref<6xf32, strided<[2]>>
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

