module {
  func.func @main_kernel(%arg0: memref<4x6xf32, strided<[6, 1]>>, %arg1: memref<6x3xf32, strided<[3, 1]>>, %arg2: memref<3xf32, strided<[1]>>) -> memref<4x3xf32> attributes {llvm.emit_c_interface} {
    %cst = arith.constant 0.000000e+00 : f32
    %c6 = arith.constant 6 : index
    %c3 = arith.constant 3 : index
    %c4 = arith.constant 4 : index
    %c1 = arith.constant 1 : index
    %c0 = arith.constant 0 : index
    %alloc = memref.alloc() : memref<4x3xf32>
    cf.br ^bb1(%c0 : index)
  ^bb1(%0: index):  // 2 preds: ^bb0, ^bb11
    %1 = arith.cmpi slt, %0, %c6 : index
    cf.cond_br %1, ^bb2, ^bb12
  ^bb2:  // pred: ^bb1
    cf.br ^bb3(%c0 : index)
  ^bb3(%2: index):  // 2 preds: ^bb2, ^bb10
    %3 = arith.cmpi slt, %2, %c4 : index
    cf.cond_br %3, ^bb4, ^bb11
  ^bb4:  // pred: ^bb3
    cf.br ^bb5(%c0 : index)
  ^bb5(%4: index):  // 2 preds: ^bb4, ^bb9
    %5 = arith.cmpi slt, %4, %c3 : index
    cf.cond_br %5, ^bb6, ^bb10
  ^bb6:  // pred: ^bb5
    %6 = memref.load %arg2[%4] : memref<3xf32, strided<[1]>>
    cf.br ^bb7(%0, %6 : index, f32)
  ^bb7(%7: index, %8: f32):  // 2 preds: ^bb6, ^bb8
    %9 = arith.cmpi slt, %7, %c6 : index
    cf.cond_br %9, ^bb8, ^bb9
  ^bb8:  // pred: ^bb7
    %10 = memref.load %arg0[%2, %7] : memref<4x6xf32, strided<[6, 1]>>
    %11 = memref.load %arg1[%7, %4] : memref<6x3xf32, strided<[3, 1]>>
    %12 = arith.mulf %10, %11 : f32
    %13 = arith.addf %8, %12 : f32
    %14 = arith.addi %7, %c1 : index
    cf.br ^bb7(%14, %13 : index, f32)
  ^bb9:  // pred: ^bb7
    %15 = arith.cmpf ogt, %8, %cst : f32
    %16 = arith.select %15, %8, %cst : f32
    memref.store %16, %alloc[%2, %4] : memref<4x3xf32>
    %17 = arith.addi %4, %c1 : index
    cf.br ^bb5(%17 : index)
  ^bb10:  // pred: ^bb5
    %18 = arith.addi %2, %c1 : index
    cf.br ^bb3(%18 : index)
  ^bb11:  // pred: ^bb3
    %19 = arith.addi %0, %c3 : index
    cf.br ^bb1(%19 : index)
  ^bb12:  // pred: ^bb1
    return %alloc : memref<4x3xf32>
  }
}

