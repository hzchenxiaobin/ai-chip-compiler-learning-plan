module {
  func.func @main_kernel(%arg0: memref<128x128xf32, strided<[128, 1]>>, %arg1: memref<128x128xf32, strided<[128, 1]>>, %arg2: memref<128xf32, strided<[1]>>) -> memref<128x128xf32> attributes {llvm.emit_c_interface} {
    %cst = arith.constant 0.000000e+00 : f32
    %c128 = arith.constant 128 : index
    %c1 = arith.constant 1 : index
    %c0 = arith.constant 0 : index
    %alloc = memref.alloc() : memref<128x128xf32>
    scf.for %arg3 = %c0 to %c128 step %c1 {
      scf.for %arg4 = %c0 to %c128 step %c1 {
        %0 = memref.load %arg2[%arg4] : memref<128xf32, strided<[1]>>
        %1 = scf.for %arg5 = %c0 to %c128 step %c1 iter_args(%arg6 = %0) -> (f32) {
          %4 = memref.load %arg0[%arg3, %arg5] : memref<128x128xf32, strided<[128, 1]>>
          %5 = memref.load %arg1[%arg5, %arg4] : memref<128x128xf32, strided<[128, 1]>>
          %6 = arith.mulf %4, %5 : f32
          %7 = arith.addf %arg6, %6 : f32
          scf.yield %7 : f32
        }
        %2 = arith.cmpf ogt, %1, %cst : f32
        %3 = arith.select %2, %1, %cst : f32
        memref.store %3, %alloc[%arg3, %arg4] : memref<128x128xf32>
      }
    }
    return %alloc : memref<128x128xf32>
  }
}

