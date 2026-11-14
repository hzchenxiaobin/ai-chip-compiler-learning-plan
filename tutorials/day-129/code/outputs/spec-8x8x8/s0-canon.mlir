module {
  func.func @kernel_s8x8x8(%arg0: memref<8x8xf32, strided<[8, 1]>>, %arg1: memref<8x8xf32, strided<[8, 1]>>) -> memref<8x8xf32> attributes {llvm.emit_c_interface} {
    %cst = arith.constant 0.000000e+00 : f32
    %c1 = arith.constant 1 : index
    %c8 = arith.constant 8 : index
    %c0 = arith.constant 0 : index
    %alloc = memref.alloc() : memref<8x8xf32>
    scf.for %arg2 = %c0 to %c8 step %c1 {
      scf.for %arg3 = %c0 to %c8 step %c1 {
        %0 = scf.for %arg4 = %c0 to %c8 step %c1 iter_args(%arg5 = %cst) -> (f32) {
          %1 = memref.load %arg0[%arg2, %arg4] : memref<8x8xf32, strided<[8, 1]>>
          %2 = memref.load %arg1[%arg4, %arg3] : memref<8x8xf32, strided<[8, 1]>>
          %3 = arith.mulf %1, %2 : f32
          %4 = arith.addf %arg5, %3 : f32
          scf.yield %4 : f32
        }
        memref.store %0, %alloc[%arg2, %arg3] : memref<8x8xf32>
      }
    }
    return %alloc : memref<8x8xf32>
  }
}

