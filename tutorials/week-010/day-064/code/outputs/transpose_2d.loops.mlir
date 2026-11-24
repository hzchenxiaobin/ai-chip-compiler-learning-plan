module {
  func.func @transpose(%arg0: memref<2x3xf32>, %arg1: memref<3x2xf32>) {
    %c0 = arith.constant 0 : index
    %c3 = arith.constant 3 : index
    %c1 = arith.constant 1 : index
    %c2 = arith.constant 2 : index
    scf.for %arg2 = %c0 to %c3 step %c1 {
      scf.for %arg3 = %c0 to %c2 step %c1 {
        %0 = memref.load %arg0[%arg3, %arg2] : memref<2x3xf32>
        memref.store %0, %arg1[%arg2, %arg3] : memref<3x2xf32>
      }
    }
    return
  }
}

