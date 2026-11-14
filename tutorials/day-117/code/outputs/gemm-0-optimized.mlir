module {
  func.func @gemm(%arg0: memref<4x6xf32, strided<[6, 1]>>, %arg1: memref<6x3xf32, strided<[3, 1]>>) -> memref<4x3xf32> attributes {llvm.emit_c_interface} {
    %c4 = arith.constant 4 : index
    %c0 = arith.constant 0 : index
    %c3 = arith.constant 3 : index
    %c6 = arith.constant 6 : index
    %c1 = arith.constant 1 : index
    %cst = arith.constant 0.000000e+00 : f32
    %alloc = memref.alloc() : memref<4x3xf32>
    scf.for %arg2 = %c0 to %c4 step %c1 {
      scf.for %arg3 = %c0 to %c3 step %c1 {
        %0 = scf.for %arg4 = %c0 to %c6 step %c1 iter_args(%arg5 = %cst) -> (f32) {
          %1 = memref.load %arg0[%arg2, %arg4] : memref<4x6xf32, strided<[6, 1]>>
          %2 = memref.load %arg1[%arg4, %arg3] : memref<6x3xf32, strided<[3, 1]>>
          %3 = arith.mulf %1, %2 : f32
          %4 = arith.addf %arg5, %3 : f32
          scf.yield %4 : f32
        }
        memref.store %0, %alloc[%arg2, %arg3] : memref<4x3xf32>
      }
    }
    return %alloc : memref<4x3xf32>
  }
}

