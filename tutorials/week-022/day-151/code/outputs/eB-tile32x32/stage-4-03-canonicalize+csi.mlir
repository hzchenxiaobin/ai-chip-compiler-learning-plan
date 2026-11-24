module {
  func.func @main_kernel(%arg0: memref<160x160xf32, strided<[160, 1]>>, %arg1: memref<160x160xf32, strided<[160, 1]>>, %arg2: memref<160xf32, strided<[1]>>) -> memref<160x160xf32> attributes {llvm.emit_c_interface} {
    %cst = arith.constant 0.000000e+00 : f32
    %c32 = arith.constant 32 : index
    %c160 = arith.constant 160 : index
    %c1 = arith.constant 1 : index
    %c0 = arith.constant 0 : index
    %alloc = memref.alloc() : memref<160x160xf32>
    scf.for %arg3 = %c0 to %c160 step %c32 {
      scf.for %arg4 = %c0 to %c160 step %c32 {
        scf.for %arg5 = %arg3 to %c160 step %c1 {
          scf.for %arg6 = %arg4 to %c160 step %c1 {
            %0 = memref.load %arg2[%arg6] : memref<160xf32, strided<[1]>>
            %1 = scf.for %arg7 = %c0 to %c160 step %c1 iter_args(%arg8 = %0) -> (f32) {
              %4 = memref.load %arg0[%arg5, %arg7] : memref<160x160xf32, strided<[160, 1]>>
              %5 = memref.load %arg1[%arg7, %arg6] : memref<160x160xf32, strided<[160, 1]>>
              %6 = arith.mulf %4, %5 : f32
              %7 = arith.addf %arg8, %6 : f32
              scf.yield %7 : f32
            }
            %2 = arith.cmpf ogt, %1, %cst : f32
            %3 = arith.select %2, %1, %cst : f32
            memref.store %3, %alloc[%arg5, %arg6] : memref<160x160xf32>
          }
        }
      }
    }
    return %alloc : memref<160x160xf32>
  }
}

