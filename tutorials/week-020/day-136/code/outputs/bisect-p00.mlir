module {
  func.func @probe(%arg0: memref<2x2xf32, strided<[2, 1]>>) -> f32 {
    %c0 = arith.constant 0 : index
    %c1 = arith.constant 1 : index
    %0 = memref.load %arg0[%c0, %c0] : memref<2x2xf32, strided<[2, 1]>>
    %1 = memref.load %arg0[%c1, %c1] : memref<2x2xf32, strided<[2, 1]>>
    %2 = arith.addf %0, %1 : f32
    return %2 : f32
  }
}

