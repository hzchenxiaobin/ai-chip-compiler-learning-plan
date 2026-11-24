module {
  func.func @gemm(%arg0: memref<4x6xf32, strided<[6, 1]>>, %arg1: memref<6x3xf32, strided<[3, 1]>>) -> memref<4x3xf32> {
    %c6 = arith.constant 6 : index
    %c3 = arith.constant 3 : index
    %c4 = arith.constant 4 : index
    %c1 = arith.constant 1 : index
    %c0 = arith.constant 0 : index
    %cst = arith.constant 0.000000e+00 : f32
    %alloc = memref.alloc() : memref<4x3xf32>
    cf.br ^bb1(%c0 : index)
  ^bb1(%0: index):  // 2 preds: ^bb0, ^bb8
    %1 = arith.cmpi slt, %0, %c4 : index
    cf.cond_br %1, ^bb2, ^bb9
  ^bb2:  // pred: ^bb1
    cf.br ^bb3(%c0 : index)
  ^bb3(%2: index):  // 2 preds: ^bb2, ^bb7
    %3 = arith.cmpi slt, %2, %c3 : index
    cf.cond_br %3, ^bb4, ^bb8
  ^bb4:  // pred: ^bb3
    cf.br ^bb5(%c0, %cst : index, f32)
  ^bb5(%4: index, %5: f32):  // 2 preds: ^bb4, ^bb6
    %6 = arith.cmpi slt, %4, %c6 : index
    cf.cond_br %6, ^bb6, ^bb7
  ^bb6:  // pred: ^bb5
    %7 = memref.load %arg0[%0, %4] : memref<4x6xf32, strided<[6, 1]>>
    %8 = memref.load %arg1[%4, %2] : memref<6x3xf32, strided<[3, 1]>>
    %9 = arith.mulf %7, %8 : f32
    %10 = arith.addf %5, %9 : f32
    %11 = arith.addi %4, %c1 : index
    cf.br ^bb5(%11, %10 : index, f32)
  ^bb7:  // pred: ^bb5
    memref.store %5, %alloc[%0, %2] : memref<4x3xf32>
    %12 = arith.addi %2, %c1 : index
    cf.br ^bb3(%12 : index)
  ^bb8:  // pred: ^bb3
    %13 = arith.addi %0, %c1 : index
    cf.br ^bb1(%13 : index)
  ^bb9:  // pred: ^bb1
    return %alloc : memref<4x3xf32>
  }
}

