module {
  llvm.func @malloc(i64) -> !llvm.ptr
  func.func @main_kernel(%arg0: memref<4x6xf32, strided<[6, 1]>>, %arg1: memref<6x3xf32, strided<[3, 1]>>, %arg2: memref<3xf32, strided<[1]>>) -> memref<4x3xf32> attributes {llvm.emit_c_interface} {
    %0 = builtin.unrealized_conversion_cast %arg1 : memref<6x3xf32, strided<[3, 1]>> to !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
    %1 = builtin.unrealized_conversion_cast %arg0 : memref<4x6xf32, strided<[6, 1]>> to !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
    %2 = builtin.unrealized_conversion_cast %arg2 : memref<3xf32, strided<[1]>> to !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)>
    %cst = arith.constant 0.000000e+00 : f32
    %c2 = arith.constant 2 : index
    %c6 = arith.constant 6 : index
    %c3 = arith.constant 3 : index
    %c4 = arith.constant 4 : index
    %c1 = arith.constant 1 : index
    %c0 = arith.constant 0 : index
    %3 = llvm.mlir.constant(4 : index) : i64
    %4 = llvm.mlir.constant(3 : index) : i64
    %5 = llvm.mlir.constant(1 : index) : i64
    %6 = llvm.mlir.constant(12 : index) : i64
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
    %20 = builtin.unrealized_conversion_cast %19 : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> to memref<4x3xf32>
    cf.br ^bb1(%c0 : index)
  ^bb1(%21: index):  // 2 preds: ^bb0, ^bb17
    %22 = arith.cmpi slt, %21, %c4 : index
    cf.cond_br %22, ^bb2, ^bb18
  ^bb2:  // pred: ^bb1
    cf.br ^bb3(%c0 : index)
  ^bb3(%23: index):  // 2 preds: ^bb2, ^bb16
    %24 = arith.cmpi slt, %23, %c3 : index
    cf.cond_br %24, ^bb4, ^bb17
  ^bb4:  // pred: ^bb3
    cf.br ^bb5(%c0 : index)
  ^bb5(%25: index):  // 2 preds: ^bb4, ^bb15
    %26 = arith.cmpi slt, %25, %c6 : index
    cf.cond_br %26, ^bb6, ^bb16
  ^bb6:  // pred: ^bb5
    cf.br ^bb7(%21 : index)
  ^bb7(%27: index):  // 2 preds: ^bb6, ^bb14
    %28 = builtin.unrealized_conversion_cast %27 : index to i64
    %29 = arith.cmpi slt, %27, %c4 : index
    cf.cond_br %29, ^bb8, ^bb15
  ^bb8:  // pred: ^bb7
    cf.br ^bb9(%23 : index)
  ^bb9(%30: index):  // 2 preds: ^bb8, ^bb13
    %31 = builtin.unrealized_conversion_cast %30 : index to i64
    %32 = arith.cmpi slt, %30, %c3 : index
    cf.cond_br %32, ^bb10, ^bb14
  ^bb10:  // pred: ^bb9
    %33 = llvm.extractvalue %2[1] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %34 = llvm.getelementptr inbounds|nuw %33[%31] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %35 = llvm.load %34 : !llvm.ptr -> f32
    cf.br ^bb11(%c0, %35 : index, f32)
  ^bb11(%36: index, %37: f32):  // 2 preds: ^bb10, ^bb12
    %38 = builtin.unrealized_conversion_cast %36 : index to i64
    %39 = arith.cmpi slt, %36, %c6 : index
    cf.cond_br %39, ^bb12, ^bb13
  ^bb12:  // pred: ^bb11
    %40 = llvm.extractvalue %1[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %41 = llvm.mlir.constant(6 : index) : i64
    %42 = llvm.mul %28, %41 overflow<nsw, nuw> : i64
    %43 = llvm.add %42, %38 overflow<nsw, nuw> : i64
    %44 = llvm.getelementptr inbounds|nuw %40[%43] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %45 = llvm.load %44 : !llvm.ptr -> f32
    %46 = llvm.extractvalue %0[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %47 = llvm.mlir.constant(3 : index) : i64
    %48 = llvm.mul %38, %47 overflow<nsw, nuw> : i64
    %49 = llvm.add %48, %31 overflow<nsw, nuw> : i64
    %50 = llvm.getelementptr inbounds|nuw %46[%49] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %51 = llvm.load %50 : !llvm.ptr -> f32
    %52 = arith.mulf %45, %51 : f32
    %53 = arith.addf %37, %52 : f32
    %54 = arith.addi %36, %c1 : index
    cf.br ^bb11(%54, %53 : index, f32)
  ^bb13:  // pred: ^bb11
    %55 = arith.cmpf ogt, %37, %cst : f32
    %56 = arith.select %55, %37, %cst : f32
    %57 = llvm.extractvalue %19[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %58 = llvm.mlir.constant(3 : index) : i64
    %59 = llvm.mul %28, %58 overflow<nsw, nuw> : i64
    %60 = llvm.add %59, %31 overflow<nsw, nuw> : i64
    %61 = llvm.getelementptr inbounds|nuw %57[%60] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    llvm.store %56, %61 : f32, !llvm.ptr
    %62 = arith.addi %30, %c1 : index
    cf.br ^bb9(%62 : index)
  ^bb14:  // pred: ^bb9
    %63 = arith.addi %27, %c1 : index
    cf.br ^bb7(%63 : index)
  ^bb15:  // pred: ^bb7
    %64 = arith.addi %25, %c3 : index
    cf.br ^bb5(%64 : index)
  ^bb16:  // pred: ^bb5
    %65 = arith.addi %23, %c2 : index
    cf.br ^bb3(%65 : index)
  ^bb17:  // pred: ^bb3
    %66 = arith.addi %21, %c2 : index
    cf.br ^bb1(%66 : index)
  ^bb18:  // pred: ^bb1
    return %20 : memref<4x3xf32>
  }
}

