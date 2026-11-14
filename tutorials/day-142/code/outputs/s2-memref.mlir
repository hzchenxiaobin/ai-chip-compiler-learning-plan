module {
  llvm.func @malloc(i64) -> !llvm.ptr
  func.func @kernel_tiled(%arg0: memref<4x6xf32, strided<[6, 1]>>, %arg1: memref<6x3xf32, strided<[3, 1]>>) -> memref<4x3xf32> attributes {llvm.emit_c_interface} {
    %0 = builtin.unrealized_conversion_cast %arg1 : memref<6x3xf32, strided<[3, 1]>> to !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
    %1 = builtin.unrealized_conversion_cast %arg0 : memref<4x6xf32, strided<[6, 1]>> to !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
    %cst = arith.constant 0.000000e+00 : f32
    %c2 = arith.constant 2 : index
    %c6 = arith.constant 6 : index
    %c3 = arith.constant 3 : index
    %c4 = arith.constant 4 : index
    %c1 = arith.constant 1 : index
    %c0 = arith.constant 0 : index
    %2 = llvm.mlir.constant(4 : index) : i64
    %3 = llvm.mlir.constant(3 : index) : i64
    %4 = llvm.mlir.constant(1 : index) : i64
    %5 = llvm.mlir.constant(12 : index) : i64
    %6 = llvm.mlir.zero : !llvm.ptr
    %7 = llvm.getelementptr %6[%5] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %8 = llvm.ptrtoint %7 : !llvm.ptr to i64
    %9 = llvm.call @malloc(%8) : (i64) -> !llvm.ptr
    %10 = llvm.mlir.poison : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
    %11 = llvm.insertvalue %9, %10[0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %12 = llvm.insertvalue %9, %11[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %13 = llvm.mlir.constant(0 : index) : i64
    %14 = llvm.insertvalue %13, %12[2] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %15 = llvm.insertvalue %2, %14[3, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %16 = llvm.insertvalue %3, %15[3, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %17 = llvm.insertvalue %3, %16[4, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %18 = llvm.insertvalue %4, %17[4, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %19 = builtin.unrealized_conversion_cast %18 : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> to memref<4x3xf32>
    cf.br ^bb1(%c0 : index)
  ^bb1(%20: index):  // 2 preds: ^bb0, ^bb17
    %21 = arith.cmpi slt, %20, %c4 : index
    cf.cond_br %21, ^bb2, ^bb18
  ^bb2:  // pred: ^bb1
    cf.br ^bb3(%c0 : index)
  ^bb3(%22: index):  // 2 preds: ^bb2, ^bb16
    %23 = arith.cmpi slt, %22, %c3 : index
    cf.cond_br %23, ^bb4, ^bb17
  ^bb4:  // pred: ^bb3
    cf.br ^bb5(%c0 : index)
  ^bb5(%24: index):  // 2 preds: ^bb4, ^bb15
    %25 = arith.cmpi slt, %24, %c6 : index
    cf.cond_br %25, ^bb6, ^bb16
  ^bb6:  // pred: ^bb5
    %26 = arith.minsi %20, %c4 : index
    cf.br ^bb7(%20 : index)
  ^bb7(%27: index):  // 2 preds: ^bb6, ^bb14
    %28 = builtin.unrealized_conversion_cast %27 : index to i64
    %29 = arith.cmpi slt, %27, %26 : index
    cf.cond_br %29, ^bb8, ^bb15
  ^bb8:  // pred: ^bb7
    cf.br ^bb9(%22 : index)
  ^bb9(%30: index):  // 2 preds: ^bb8, ^bb13
    %31 = builtin.unrealized_conversion_cast %30 : index to i64
    %32 = arith.cmpi slt, %30, %c3 : index
    cf.cond_br %32, ^bb10, ^bb14
  ^bb10:  // pred: ^bb9
    cf.br ^bb11(%24, %cst : index, f32)
  ^bb11(%33: index, %34: f32):  // 2 preds: ^bb10, ^bb12
    %35 = builtin.unrealized_conversion_cast %33 : index to i64
    %36 = arith.cmpi slt, %33, %c6 : index
    cf.cond_br %36, ^bb12, ^bb13
  ^bb12:  // pred: ^bb11
    %37 = llvm.extractvalue %1[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %38 = llvm.mlir.constant(6 : index) : i64
    %39 = llvm.mul %28, %38 overflow<nsw, nuw> : i64
    %40 = llvm.add %39, %35 overflow<nsw, nuw> : i64
    %41 = llvm.getelementptr inbounds|nuw %37[%40] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %42 = llvm.load %41 : !llvm.ptr -> f32
    %43 = llvm.extractvalue %0[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %44 = llvm.mlir.constant(3 : index) : i64
    %45 = llvm.mul %35, %44 overflow<nsw, nuw> : i64
    %46 = llvm.add %45, %31 overflow<nsw, nuw> : i64
    %47 = llvm.getelementptr inbounds|nuw %43[%46] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %48 = llvm.load %47 : !llvm.ptr -> f32
    %49 = arith.mulf %42, %48 : f32
    %50 = arith.addf %34, %49 : f32
    %51 = arith.addi %33, %c1 : index
    cf.br ^bb11(%51, %50 : index, f32)
  ^bb13:  // pred: ^bb11
    %52 = llvm.extractvalue %18[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %53 = llvm.mlir.constant(3 : index) : i64
    %54 = llvm.mul %28, %53 overflow<nsw, nuw> : i64
    %55 = llvm.add %54, %31 overflow<nsw, nuw> : i64
    %56 = llvm.getelementptr inbounds|nuw %52[%55] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    llvm.store %34, %56 : f32, !llvm.ptr
    %57 = arith.addi %30, %c1 : index
    cf.br ^bb9(%57 : index)
  ^bb14:  // pred: ^bb9
    %58 = arith.addi %27, %c1 : index
    cf.br ^bb7(%58 : index)
  ^bb15:  // pred: ^bb7
    %59 = arith.addi %24, %c3 : index
    cf.br ^bb5(%59 : index)
  ^bb16:  // pred: ^bb5
    %60 = arith.addi %22, %c2 : index
    cf.br ^bb3(%60 : index)
  ^bb17:  // pred: ^bb3
    %61 = arith.addi %20, %c2 : index
    cf.br ^bb1(%61 : index)
  ^bb18:  // pred: ^bb1
    return %19 : memref<4x3xf32>
  }
}

