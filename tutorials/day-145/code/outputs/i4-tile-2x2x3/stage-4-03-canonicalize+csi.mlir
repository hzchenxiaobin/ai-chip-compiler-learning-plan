module {
  func.func @main_kernel(%arg0: memref<4x6xf32, strided<[6, 1]>>, %arg1: memref<6x3xf32, strided<[3, 1]>>, %arg2: memref<3xf32, strided<[1]>>) -> memref<4x3xf32> attributes {llvm.emit_c_interface} {
    %cst = arith.constant 0.000000e+00 : f32
    %c2 = arith.constant 2 : index
    %c6 = arith.constant 6 : index
    %c3 = arith.constant 3 : index
    %c4 = arith.constant 4 : index
    %c1 = arith.constant 1 : index
    %c0 = arith.constant 0 : index
    %alloc = memref.alloc() : memref<4x3xf32>
    scf.for %arg3 = %c0 to %c4 step %c2 {
      scf.for %arg4 = %c0 to %c3 step %c2 {
        scf.for %arg5 = %c0 to %c6 step %c3 {
          scf.for %arg6 = %arg3 to %c4 step %c1 {
            scf.for %arg7 = %arg4 to %c3 step %c1 {
              %0 = memref.load %arg2[%arg7] : memref<3xf32, strided<[1]>>
              %1 = scf.for %arg8 = %c0 to %c6 step %c1 iter_args(%arg9 = %0) -> (f32) {
                %4 = memref.load %arg0[%arg6, %arg8] : memref<4x6xf32, strided<[6, 1]>>
                %5 = memref.load %arg1[%arg8, %arg7] : memref<6x3xf32, strided<[3, 1]>>
                %6 = arith.mulf %4, %5 : f32
                %7 = arith.addf %arg9, %6 : f32
                scf.yield %7 : f32
              }
              %2 = arith.cmpf ogt, %1, %cst : f32
              %3 = arith.select %2, %1, %cst : f32
              memref.store %3, %alloc[%arg6, %arg7] : memref<4x3xf32>
            }
          }
        }
      }
    }
    return %alloc : memref<4x3xf32>
  }
}

