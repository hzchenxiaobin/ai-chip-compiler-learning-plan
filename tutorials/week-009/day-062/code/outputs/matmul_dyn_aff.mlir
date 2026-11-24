module {
  func.func @matmul(%arg0: memref<?x3xf32>, %arg1: memref<3x2xf32>, %arg2: memref<?x2xf32>) {
    %c0 = arith.constant 0 : index
    %dim = memref.dim %arg0, %c0 : memref<?x3xf32>
    affine.for %arg3 = 0 to %dim {
      affine.for %arg4 = 0 to 2 {
        affine.for %arg5 = 0 to 3 {
          %0 = affine.load %arg0[%arg3, %arg5] : memref<?x3xf32>
          %1 = affine.load %arg1[%arg5, %arg4] : memref<3x2xf32>
          %2 = affine.load %arg2[%arg3, %arg4] : memref<?x2xf32>
          %3 = arith.mulf %0, %1 : f32
          %4 = arith.addf %2, %3 : f32
          affine.store %4, %arg2[%arg3, %arg4] : memref<?x2xf32>
        }
      }
    }
    return
  }
}

