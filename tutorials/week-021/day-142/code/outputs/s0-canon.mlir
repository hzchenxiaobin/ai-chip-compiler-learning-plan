module {
  func.func @kernel_tiled(%arg0: memref<4x6xf32, strided<[6, 1]>>, %arg1: memref<6x3xf32, strided<[3, 1]>>) -> memref<4x3xf32> attributes {llvm.emit_c_interface} {
    %cst = arith.constant 0.000000e+00 : f32
    %c2 = arith.constant 2 : index
    %c6 = arith.constant 6 : index
    %c3 = arith.constant 3 : index
    %c4 = arith.constant 4 : index
    %c1 = arith.constant 1 : index
    %c0 = arith.constant 0 : index
    %alloc = memref.alloc() : memref<4x3xf32>
    scf.for %arg2 = %c0 to %c4 step %c2 {
      scf.for %arg3 = %c0 to %c3 step %c2 {
        scf.for %arg4 = %c0 to %c6 step %c3 {
          %0 = arith.minsi %arg2, %c4 : index
          scf.for %arg5 = %arg2 to %0 step %c1 {
            scf.for %arg6 = %arg3 to %c3 step %c1 {
              %1 = scf.for %arg7 = %arg4 to %c6 step %c1 iter_args(%arg8 = %cst) -> (f32) {
                %2 = memref.load %arg0[%arg5, %arg7] : memref<4x6xf32, strided<[6, 1]>>
                %3 = memref.load %arg1[%arg7, %arg6] : memref<6x3xf32, strided<[3, 1]>>
                %4 = arith.mulf %2, %3 : f32
                %5 = arith.addf %arg8, %4 : f32
                scf.yield %5 : f32
              }
              memref.store %1, %alloc[%arg5, %arg6] : memref<4x3xf32>
            }
          }
        }
      }
    }
    return %alloc : memref<4x3xf32>
  }
}

