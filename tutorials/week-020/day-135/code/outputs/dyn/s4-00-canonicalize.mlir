module {
  func.func @kernel_dynamic(%arg0: memref<?x?xf32>, %arg1: memref<?x?xf32>) -> memref<?x?xf32> attributes {llvm.emit_c_interface} {
    %c0 = arith.constant 0 : index
    %c1 = arith.constant 1 : index
    %cst = arith.constant 0.000000e+00 : f32
    %dim = memref.dim %arg0, %c0 : memref<?x?xf32>
    %dim_0 = memref.dim %arg0, %c1 : memref<?x?xf32>
    %dim_1 = memref.dim %arg1, %c1 : memref<?x?xf32>
    %alloc = memref.alloc(%dim, %dim_1) : memref<?x?xf32>
    scf.for %arg2 = %c0 to %dim step %c1 {
      scf.for %arg3 = %c0 to %dim_1 step %c1 {
        %0 = scf.for %arg4 = %c0 to %dim_0 step %c1 iter_args(%arg5 = %cst) -> (f32) {
          %1 = memref.load %arg0[%arg2, %arg4] : memref<?x?xf32>
          %2 = memref.load %arg1[%arg4, %arg3] : memref<?x?xf32>
          %3 = arith.mulf %1, %2 : f32
          %4 = arith.addf %arg5, %3 : f32
          scf.yield %4 : f32
        }
        memref.store %0, %alloc[%arg2, %arg3] : memref<?x?xf32>
      }
    }
    return %alloc : memref<?x?xf32>
  }
}

