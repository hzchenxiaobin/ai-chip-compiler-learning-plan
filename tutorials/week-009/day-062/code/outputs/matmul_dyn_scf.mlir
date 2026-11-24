module {
  func.func @matmul(%arg0: memref<?x3xf32>, %arg1: memref<3x2xf32>, %arg2: memref<?x2xf32>) {
    %c3 = arith.constant 3 : index
    %c2 = arith.constant 2 : index
    %c1 = arith.constant 1 : index
    %c0 = arith.constant 0 : index
    %dim = memref.dim %arg0, %c0 : memref<?x3xf32>
    scf.for %arg3 = %c0 to %dim step %c1 {
      scf.for %arg4 = %c0 to %c2 step %c1 {
        scf.for %arg5 = %c0 to %c3 step %c1 {
          %0 = memref.load %arg0[%arg3, %arg5] : memref<?x3xf32>
          %1 = memref.load %arg1[%arg5, %arg4] : memref<3x2xf32>
          %2 = memref.load %arg2[%arg3, %arg4] : memref<?x2xf32>
          %3 = arith.mulf %0, %1 : f32
          %4 = arith.addf %2, %3 : f32
          memref.store %4, %arg2[%arg3, %arg4] : memref<?x2xf32>
        }
      }
    }
    return
  }
}

