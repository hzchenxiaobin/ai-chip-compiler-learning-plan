module {
  func.func private @printF32(f32)
  func.func private @printNewline()
  func.func @matmul_m_dynamic(%arg0: memref<?x3xf32>, %arg1: memref<3x2xf32>, %arg2: memref<?x2xf32>) {
    linalg.matmul ins(%arg0, %arg1 : memref<?x3xf32>, memref<3x2xf32>) outs(%arg2 : memref<?x2xf32>)
    return
  }
  func.func @matmul_all_dynamic(%arg0: memref<?x?xf32>, %arg1: memref<?x?xf32>, %arg2: memref<?x?xf32>) {
    linalg.matmul ins(%arg0, %arg1 : memref<?x?xf32>, memref<?x?xf32>) outs(%arg2 : memref<?x?xf32>)
    return
  }
  func.func @main() {
    %c0 = arith.constant 0 : index
    %c1 = arith.constant 1 : index
    %c2 = arith.constant 2 : index
    %alloc = memref.alloc() : memref<2x3xf32>
    %alloc_0 = memref.alloc() : memref<3x2xf32>
    %alloc_1 = memref.alloc() : memref<2x2xf32>
    %cst = arith.constant 1.000000e+00 : f32
    %cst_2 = arith.constant 2.000000e+00 : f32
    %cst_3 = arith.constant 3.000000e+00 : f32
    %cst_4 = arith.constant 4.000000e+00 : f32
    %cst_5 = arith.constant 5.000000e+00 : f32
    %cst_6 = arith.constant 6.000000e+00 : f32
    memref.store %cst, %alloc[%c0, %c0] : memref<2x3xf32>
    memref.store %cst_2, %alloc[%c0, %c1] : memref<2x3xf32>
    memref.store %cst_3, %alloc[%c0, %c2] : memref<2x3xf32>
    memref.store %cst_4, %alloc[%c1, %c0] : memref<2x3xf32>
    memref.store %cst_5, %alloc[%c1, %c1] : memref<2x3xf32>
    memref.store %cst_6, %alloc[%c1, %c2] : memref<2x3xf32>
    %cst_7 = arith.constant 1.000000e+01 : f32
    %cst_8 = arith.constant 2.000000e+01 : f32
    %cst_9 = arith.constant 3.000000e+01 : f32
    %cst_10 = arith.constant 4.000000e+01 : f32
    %cst_11 = arith.constant 5.000000e+01 : f32
    %cst_12 = arith.constant 6.000000e+01 : f32
    memref.store %cst_7, %alloc_0[%c0, %c0] : memref<3x2xf32>
    memref.store %cst_8, %alloc_0[%c0, %c1] : memref<3x2xf32>
    memref.store %cst_9, %alloc_0[%c1, %c0] : memref<3x2xf32>
    memref.store %cst_10, %alloc_0[%c1, %c1] : memref<3x2xf32>
    memref.store %cst_11, %alloc_0[%c2, %c0] : memref<3x2xf32>
    memref.store %cst_12, %alloc_0[%c2, %c1] : memref<3x2xf32>
    %cst_13 = arith.constant 0.000000e+00 : f32
    memref.store %cst_13, %alloc_1[%c0, %c0] : memref<2x2xf32>
    memref.store %cst_13, %alloc_1[%c0, %c1] : memref<2x2xf32>
    memref.store %cst_13, %alloc_1[%c1, %c0] : memref<2x2xf32>
    memref.store %cst_13, %alloc_1[%c1, %c1] : memref<2x2xf32>
    %cast = memref.cast %alloc : memref<2x3xf32> to memref<?x3xf32>
    %cast_14 = memref.cast %alloc_1 : memref<2x2xf32> to memref<?x2xf32>
    call @matmul_m_dynamic(%cast, %alloc_0, %cast_14) : (memref<?x3xf32>, memref<3x2xf32>, memref<?x2xf32>) -> ()
    %0 = memref.load %alloc_1[%c0, %c0] : memref<2x2xf32>
    %1 = memref.load %alloc_1[%c0, %c1] : memref<2x2xf32>
    %2 = memref.load %alloc_1[%c1, %c0] : memref<2x2xf32>
    %3 = memref.load %alloc_1[%c1, %c1] : memref<2x2xf32>
    call @printF32(%0) : (f32) -> ()
    call @printNewline() : () -> ()
    call @printF32(%1) : (f32) -> ()
    call @printNewline() : () -> ()
    call @printF32(%2) : (f32) -> ()
    call @printNewline() : () -> ()
    call @printF32(%3) : (f32) -> ()
    call @printNewline() : () -> ()
    memref.dealloc %alloc : memref<2x3xf32>
    memref.dealloc %alloc_0 : memref<3x2xf32>
    memref.dealloc %alloc_1 : memref<2x2xf32>
    return
  }
}

