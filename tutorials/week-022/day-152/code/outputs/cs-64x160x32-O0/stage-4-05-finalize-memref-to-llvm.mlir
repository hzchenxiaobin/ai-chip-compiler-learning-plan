module {
  llvm.func @malloc(i64) -> !llvm.ptr
  func.func @main_kernel(%arg0: memref<64x160xf32, strided<[160, 1]>>, %arg1: memref<160x32xf32, strided<[32, 1]>>, %arg2: memref<32xf32, strided<[1]>>) -> memref<64x32xf32> attributes {llvm.emit_c_interface} {
    %0 = builtin.unrealized_conversion_cast %arg1 : memref<160x32xf32, strided<[32, 1]>> to !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
    %1 = builtin.unrealized_conversion_cast %arg0 : memref<64x160xf32, strided<[160, 1]>> to !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
    %2 = builtin.unrealized_conversion_cast %arg2 : memref<32xf32, strided<[1]>> to !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)>
    %cst = arith.constant 0.000000e+00 : f32
    %c160 = arith.constant 160 : index
    %c32 = arith.constant 32 : index
    %c64 = arith.constant 64 : index
    %c1 = arith.constant 1 : index
    %c0 = arith.constant 0 : index
    %3 = llvm.mlir.constant(64 : index) : i64
    %4 = llvm.mlir.constant(32 : index) : i64
    %5 = llvm.mlir.constant(1 : index) : i64
    %6 = llvm.mlir.constant(2048 : index) : i64
    %7 = llvm.mlir.zero : !llvm.ptr
    %8 = llvm.getelementptr %7[%6] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %9 = llvm.ptrtoint %8 : !llvm.ptr to i64
    %10 = llvm.call @malloc(%9) : (i64) -> !llvm.ptr
    %11 = llvm.mlir.poison : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
    %12 = llvm.insertvalue %10, %11[0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %13 = llvm.insertvalue %10, %12[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %14 = llvm.mlir.constant(0 : index) : i64
    %15 = llvm.insertvalue %14, %13[2] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %16 = llvm.insertvalue %3, %15[3, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %17 = llvm.insertvalue %4, %16[3, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %18 = llvm.insertvalue %4, %17[4, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %19 = llvm.insertvalue %5, %18[4, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %20 = builtin.unrealized_conversion_cast %19 : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> to memref<64x32xf32>
    cf.br ^bb1(%c0 : index)
  ^bb1(%21: index):  // 2 preds: ^bb0, ^bb8
    %22 = builtin.unrealized_conversion_cast %21 : index to i64
    %23 = arith.cmpi slt, %21, %c64 : index
    cf.cond_br %23, ^bb2, ^bb9
  ^bb2:  // pred: ^bb1
    cf.br ^bb3(%c0 : index)
  ^bb3(%24: index):  // 2 preds: ^bb2, ^bb7
    %25 = builtin.unrealized_conversion_cast %24 : index to i64
    %26 = arith.cmpi slt, %24, %c32 : index
    cf.cond_br %26, ^bb4, ^bb8
  ^bb4:  // pred: ^bb3
    %27 = llvm.extractvalue %2[1] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %28 = llvm.getelementptr inbounds|nuw %27[%25] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %29 = llvm.load %28 : !llvm.ptr -> f32
    cf.br ^bb5(%c0, %29 : index, f32)
  ^bb5(%30: index, %31: f32):  // 2 preds: ^bb4, ^bb6
    %32 = builtin.unrealized_conversion_cast %30 : index to i64
    %33 = arith.cmpi slt, %30, %c160 : index
    cf.cond_br %33, ^bb6, ^bb7
  ^bb6:  // pred: ^bb5
    %34 = llvm.extractvalue %1[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %35 = llvm.mlir.constant(160 : index) : i64
    %36 = llvm.mul %22, %35 overflow<nsw, nuw> : i64
    %37 = llvm.add %36, %32 overflow<nsw, nuw> : i64
    %38 = llvm.getelementptr inbounds|nuw %34[%37] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %39 = llvm.load %38 : !llvm.ptr -> f32
    %40 = llvm.extractvalue %0[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %41 = llvm.mlir.constant(32 : index) : i64
    %42 = llvm.mul %32, %41 overflow<nsw, nuw> : i64
    %43 = llvm.add %42, %25 overflow<nsw, nuw> : i64
    %44 = llvm.getelementptr inbounds|nuw %40[%43] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %45 = llvm.load %44 : !llvm.ptr -> f32
    %46 = arith.mulf %39, %45 : f32
    %47 = arith.addf %31, %46 : f32
    %48 = arith.addi %30, %c1 : index
    cf.br ^bb5(%48, %47 : index, f32)
  ^bb7:  // pred: ^bb5
    %49 = arith.cmpf ogt, %31, %cst : f32
    %50 = arith.select %49, %31, %cst : f32
    %51 = llvm.extractvalue %19[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %52 = llvm.mlir.constant(32 : index) : i64
    %53 = llvm.mul %22, %52 overflow<nsw, nuw> : i64
    %54 = llvm.add %53, %25 overflow<nsw, nuw> : i64
    %55 = llvm.getelementptr inbounds|nuw %51[%54] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    llvm.store %50, %55 : f32, !llvm.ptr
    %56 = arith.addi %24, %c1 : index
    cf.br ^bb3(%56 : index)
  ^bb8:  // pred: ^bb3
    %57 = arith.addi %21, %c1 : index
    cf.br ^bb1(%57 : index)
  ^bb9:  // pred: ^bb1
    return %20 : memref<64x32xf32>
  }
}

