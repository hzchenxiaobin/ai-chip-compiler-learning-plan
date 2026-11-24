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
    cf.br ^bb1(%c0 : index)
  ^bb1(%0: index):  // 2 preds: ^bb0, ^bb17
    %1 = arith.cmpi slt, %0, %c4 : index
    cf.cond_br %1, ^bb2, ^bb18
  ^bb2:  // pred: ^bb1
    cf.br ^bb3(%c0 : index)
  ^bb3(%2: index):  // 2 preds: ^bb2, ^bb16
    %3 = arith.cmpi slt, %2, %c3 : index
    cf.cond_br %3, ^bb4, ^bb17
  ^bb4:  // pred: ^bb3
    cf.br ^bb5(%c0 : index)
  ^bb5(%4: index):  // 2 preds: ^bb4, ^bb15
    %5 = arith.cmpi slt, %4, %c6 : index
    cf.cond_br %5, ^bb6, ^bb16
  ^bb6:  // pred: ^bb5
    cf.br ^bb7(%0 : index)
  ^bb7(%6: index):  // 2 preds: ^bb6, ^bb14
    %7 = arith.cmpi slt, %6, %c4 : index
    cf.cond_br %7, ^bb8, ^bb15
  ^bb8:  // pred: ^bb7
    cf.br ^bb9(%2 : index)
  ^bb9(%8: index):  // 2 preds: ^bb8, ^bb13
    %9 = arith.cmpi slt, %8, %c3 : index
    cf.cond_br %9, ^bb10, ^bb14
  ^bb10:  // pred: ^bb9
    %10 = memref.load %arg2[%8] : memref<3xf32, strided<[1]>>
    cf.br ^bb11(%4, %10 : index, f32)
  ^bb11(%11: index, %12: f32):  // 2 preds: ^bb10, ^bb12
    %13 = arith.cmpi slt, %11, %c6 : index
    cf.cond_br %13, ^bb12, ^bb13
  ^bb12:  // pred: ^bb11
    %14 = memref.load %arg0[%6, %11] : memref<4x6xf32, strided<[6, 1]>>
    %15 = memref.load %arg1[%11, %8] : memref<6x3xf32, strided<[3, 1]>>
    %16 = arith.mulf %14, %15 : f32
    %17 = arith.addf %12, %16 : f32
    %18 = arith.addi %11, %c1 : index
    cf.br ^bb11(%18, %17 : index, f32)
  ^bb13:  // pred: ^bb11
    %19 = arith.cmpf ogt, %12, %cst : f32
    %20 = arith.select %19, %12, %cst : f32
    memref.store %20, %alloc[%6, %8] : memref<4x3xf32>
    %21 = arith.addi %8, %c1 : index
    cf.br ^bb9(%21 : index)
  ^bb14:  // pred: ^bb9
    %22 = arith.addi %6, %c1 : index
    cf.br ^bb7(%22 : index)
  ^bb15:  // pred: ^bb7
    %23 = arith.addi %4, %c3 : index
    cf.br ^bb5(%23 : index)
  ^bb16:  // pred: ^bb5
    %24 = arith.addi %2, %c2 : index
    cf.br ^bb3(%24 : index)
  ^bb17:  // pred: ^bb3
    %25 = arith.addi %0, %c2 : index
    cf.br ^bb1(%25 : index)
  ^bb18:  // pred: ^bb1
    return %alloc : memref<4x3xf32>
  }
}

