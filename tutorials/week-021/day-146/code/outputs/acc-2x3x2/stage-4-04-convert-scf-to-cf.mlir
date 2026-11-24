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
  ^bb1(%0: index):  // 2 preds: ^bb0, ^bb14
    %1 = arith.cmpi slt, %0, %c4 : index
    cf.cond_br %1, ^bb2, ^bb15
  ^bb2:  // pred: ^bb1
    cf.br ^bb3(%c0 : index)
  ^bb3(%2: index):  // 2 preds: ^bb2, ^bb13
    %3 = arith.cmpi slt, %2, %c6 : index
    cf.cond_br %3, ^bb4, ^bb14
  ^bb4:  // pred: ^bb3
    cf.br ^bb5(%0 : index)
  ^bb5(%4: index):  // 2 preds: ^bb4, ^bb12
    %5 = arith.cmpi slt, %4, %c4 : index
    cf.cond_br %5, ^bb6, ^bb13
  ^bb6:  // pred: ^bb5
    cf.br ^bb7(%c0 : index)
  ^bb7(%6: index):  // 2 preds: ^bb6, ^bb11
    %7 = arith.cmpi slt, %6, %c3 : index
    cf.cond_br %7, ^bb8, ^bb12
  ^bb8:  // pred: ^bb7
    %8 = memref.load %arg2[%6] : memref<3xf32, strided<[1]>>
    cf.br ^bb9(%c0, %8 : index, f32)
  ^bb9(%9: index, %10: f32):  // 2 preds: ^bb8, ^bb10
    %11 = arith.cmpi slt, %9, %c6 : index
    cf.cond_br %11, ^bb10, ^bb11
  ^bb10:  // pred: ^bb9
    %12 = memref.load %arg0[%4, %9] : memref<4x6xf32, strided<[6, 1]>>
    %13 = memref.load %arg1[%9, %6] : memref<6x3xf32, strided<[3, 1]>>
    %14 = arith.mulf %12, %13 : f32
    %15 = arith.addf %10, %14 : f32
    %16 = arith.addi %9, %c1 : index
    cf.br ^bb9(%16, %15 : index, f32)
  ^bb11:  // pred: ^bb9
    %17 = arith.cmpf ogt, %10, %cst : f32
    %18 = arith.select %17, %10, %cst : f32
    memref.store %18, %alloc[%4, %6] : memref<4x3xf32>
    %19 = arith.addi %6, %c1 : index
    cf.br ^bb7(%19 : index)
  ^bb12:  // pred: ^bb7
    %20 = arith.addi %4, %c1 : index
    cf.br ^bb5(%20 : index)
  ^bb13:  // pred: ^bb5
    %21 = arith.addi %2, %c2 : index
    cf.br ^bb3(%21 : index)
  ^bb14:  // pred: ^bb3
    %22 = arith.addi %0, %c2 : index
    cf.br ^bb1(%22 : index)
  ^bb15:  // pred: ^bb1
    return %alloc : memref<4x3xf32>
  }
}

