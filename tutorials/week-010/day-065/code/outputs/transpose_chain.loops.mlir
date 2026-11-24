module {
  func.func @chain(%arg0: memref<2x3x4xf32>) -> memref<2x3x4xf32> {
    %c2 = arith.constant 2 : index
    %c4 = arith.constant 4 : index
    %c1 = arith.constant 1 : index
    %c3 = arith.constant 3 : index
    %c0 = arith.constant 0 : index
    %alloc = memref.alloc() : memref<3x4x2xf32>
    scf.for %arg1 = %c0 to %c3 step %c1 {
      scf.for %arg2 = %c0 to %c4 step %c1 {
        scf.for %arg3 = %c0 to %c2 step %c1 {
          %0 = memref.load %arg0[%arg3, %arg1, %arg2] : memref<2x3x4xf32>
          memref.store %0, %alloc[%arg1, %arg2, %arg3] : memref<3x4x2xf32>
        }
      }
    }
    %alloc_0 = memref.alloc() : memref<2x3x4xf32>
    scf.for %arg1 = %c0 to %c2 step %c1 {
      scf.for %arg2 = %c0 to %c3 step %c1 {
        scf.for %arg3 = %c0 to %c4 step %c1 {
          %0 = memref.load %alloc[%arg2, %arg3, %arg1] : memref<3x4x2xf32>
          memref.store %0, %alloc_0[%arg1, %arg2, %arg3] : memref<2x3x4xf32>
        }
      }
    }
    return %alloc_0 : memref<2x3x4xf32>
  }
}

