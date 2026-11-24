module {
  func.func @main_kernel(%arg0: memref<96x96xf32, strided<[96, 1]>>, %arg1: memref<96x96xf32, strided<[96, 1]>>, %arg2: memref<96xf32, strided<[1]>>) -> memref<96x96xf32> attributes {llvm.emit_c_interface} {
    %cst = arith.constant 0.000000e+00 : f32
    %c96 = arith.constant 96 : index
    %c1 = arith.constant 1 : index
    %c0 = arith.constant 0 : index
    %alloc = memref.alloc() : memref<96x96xf32>
    cf.br ^bb1(%c0 : index)
  ^bb1(%0: index):  // 2 preds: ^bb0, ^bb8
    %1 = arith.cmpi slt, %0, %c96 : index
    cf.cond_br %1, ^bb2, ^bb9
  ^bb2:  // pred: ^bb1
    cf.br ^bb3(%c0 : index)
  ^bb3(%2: index):  // 2 preds: ^bb2, ^bb7
    %3 = arith.cmpi slt, %2, %c96 : index
    cf.cond_br %3, ^bb4, ^bb8
  ^bb4:  // pred: ^bb3
    %4 = memref.load %arg2[%2] : memref<96xf32, strided<[1]>>
    cf.br ^bb5(%c0, %4 : index, f32)
  ^bb5(%5: index, %6: f32):  // 2 preds: ^bb4, ^bb6
    %7 = arith.cmpi slt, %5, %c96 : index
    cf.cond_br %7, ^bb6, ^bb7
  ^bb6:  // pred: ^bb5
    %8 = memref.load %arg0[%0, %5] : memref<96x96xf32, strided<[96, 1]>>
    %9 = memref.load %arg1[%5, %2] : memref<96x96xf32, strided<[96, 1]>>
    %10 = arith.mulf %8, %9 : f32
    %11 = arith.addf %6, %10 : f32
    %12 = arith.addi %5, %c1 : index
    cf.br ^bb5(%12, %11 : index, f32)
  ^bb7:  // pred: ^bb5
    %13 = arith.cmpf ogt, %6, %cst : f32
    %14 = arith.select %13, %6, %cst : f32
    memref.store %14, %alloc[%0, %2] : memref<96x96xf32>
    %15 = arith.addi %2, %c1 : index
    cf.br ^bb3(%15 : index)
  ^bb8:  // pred: ^bb3
    %16 = arith.addi %0, %c1 : index
    cf.br ^bb1(%16 : index)
  ^bb9:  // pred: ^bb1
    return %alloc : memref<96x96xf32>
  }
}

