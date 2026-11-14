module {
  llvm.func @malloc(i64) -> !llvm.ptr
  func.func @kernel_s8x8x8(%arg0: memref<8x8xf32, strided<[8, 1]>>, %arg1: memref<8x8xf32, strided<[8, 1]>>) -> memref<8x8xf32> attributes {llvm.emit_c_interface} {
    %0 = builtin.unrealized_conversion_cast %arg1 : memref<8x8xf32, strided<[8, 1]>> to !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
    %1 = builtin.unrealized_conversion_cast %arg0 : memref<8x8xf32, strided<[8, 1]>> to !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
    %cst = arith.constant 0.000000e+00 : f32
    %c1 = arith.constant 1 : index
    %c8 = arith.constant 8 : index
    %c0 = arith.constant 0 : index
    %2 = llvm.mlir.constant(8 : index) : i64
    %3 = llvm.mlir.constant(8 : index) : i64
    %4 = llvm.mlir.constant(1 : index) : i64
    %5 = llvm.mlir.constant(64 : index) : i64
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
    %19 = builtin.unrealized_conversion_cast %18 : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> to memref<8x8xf32>
    cf.br ^bb1(%c0 : index)
  ^bb1(%20: index):  // 2 preds: ^bb0, ^bb8
    %21 = builtin.unrealized_conversion_cast %20 : index to i64
    %22 = arith.cmpi slt, %20, %c8 : index
    cf.cond_br %22, ^bb2, ^bb9
  ^bb2:  // pred: ^bb1
    cf.br ^bb3(%c0 : index)
  ^bb3(%23: index):  // 2 preds: ^bb2, ^bb7
    %24 = builtin.unrealized_conversion_cast %23 : index to i64
    %25 = arith.cmpi slt, %23, %c8 : index
    cf.cond_br %25, ^bb4, ^bb8
  ^bb4:  // pred: ^bb3
    cf.br ^bb5(%c0, %cst : index, f32)
  ^bb5(%26: index, %27: f32):  // 2 preds: ^bb4, ^bb6
    %28 = builtin.unrealized_conversion_cast %26 : index to i64
    %29 = arith.cmpi slt, %26, %c8 : index
    cf.cond_br %29, ^bb6, ^bb7
  ^bb6:  // pred: ^bb5
    %30 = llvm.extractvalue %1[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %31 = llvm.mlir.constant(8 : index) : i64
    %32 = llvm.mul %21, %31 overflow<nsw, nuw> : i64
    %33 = llvm.add %32, %28 overflow<nsw, nuw> : i64
    %34 = llvm.getelementptr inbounds|nuw %30[%33] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %35 = llvm.load %34 : !llvm.ptr -> f32
    %36 = llvm.extractvalue %0[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %37 = llvm.mlir.constant(8 : index) : i64
    %38 = llvm.mul %28, %37 overflow<nsw, nuw> : i64
    %39 = llvm.add %38, %24 overflow<nsw, nuw> : i64
    %40 = llvm.getelementptr inbounds|nuw %36[%39] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %41 = llvm.load %40 : !llvm.ptr -> f32
    %42 = arith.mulf %35, %41 : f32
    %43 = arith.addf %27, %42 : f32
    %44 = arith.addi %26, %c1 : index
    cf.br ^bb5(%44, %43 : index, f32)
  ^bb7:  // pred: ^bb5
    %45 = llvm.extractvalue %18[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %46 = llvm.mlir.constant(8 : index) : i64
    %47 = llvm.mul %21, %46 overflow<nsw, nuw> : i64
    %48 = llvm.add %47, %24 overflow<nsw, nuw> : i64
    %49 = llvm.getelementptr inbounds|nuw %45[%48] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    llvm.store %27, %49 : f32, !llvm.ptr
    %50 = arith.addi %23, %c1 : index
    cf.br ^bb3(%50 : index)
  ^bb8:  // pred: ^bb3
    %51 = arith.addi %20, %c1 : index
    cf.br ^bb1(%51 : index)
  ^bb9:  // pred: ^bb1
    return %19 : memref<8x8xf32>
  }
}

