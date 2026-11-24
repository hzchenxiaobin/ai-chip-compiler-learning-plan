module {
  func.func @sandwich(%arg0: memref<2x3xf32>) -> memref<2x3xf32> {
    %c2 = arith.constant 2 : index
    %c1 = arith.constant 1 : index
    %c3 = arith.constant 3 : index
    %c0 = arith.constant 0 : index
    %cst = arith.constant 0.000000e+00 : f32
    %alloc = memref.alloc() : memref<3x2xf32>
    scf.for %arg1 = %c0 to %c3 step %c1 {
      scf.for %arg2 = %c0 to %c2 step %c1 {
        %0 = memref.load %arg0[%arg2, %arg1] : memref<2x3xf32>
        memref.store %0, %alloc[%arg1, %arg2] : memref<3x2xf32>
      }
    }
    %alloc_0 = memref.alloc() : memref<3x2xf32>
    scf.for %arg1 = %c0 to %c3 step %c1 {
      scf.for %arg2 = %c0 to %c2 step %c1 {
        %0 = memref.load %alloc[%arg1, %arg2] : memref<3x2xf32>
        %1 = arith.cmpf ogt, %0, %cst : f32
        %2 = arith.select %1, %0, %cst : f32
        memref.store %2, %alloc_0[%arg1, %arg2] : memref<3x2xf32>
      }
    }
    %alloc_1 = memref.alloc() : memref<2x3xf32>
    scf.for %arg1 = %c0 to %c2 step %c1 {
      scf.for %arg2 = %c0 to %c3 step %c1 {
        %0 = memref.load %alloc_0[%arg2, %arg1] : memref<3x2xf32>
        memref.store %0, %alloc_1[%arg1, %arg2] : memref<2x3xf32>
      }
    }
    return %alloc_1 : memref<2x3xf32>
  }
}

