module {
  llvm.func @malloc(i64) -> !llvm.ptr
  llvm.func @kernel_tiled(%arg0: !llvm.ptr, %arg1: !llvm.ptr, %arg2: i64, %arg3: i64, %arg4: i64, %arg5: i64, %arg6: i64, %arg7: !llvm.ptr, %arg8: !llvm.ptr, %arg9: i64, %arg10: i64, %arg11: i64, %arg12: i64, %arg13: i64) -> !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> attributes {llvm.emit_c_interface} {
    %0 = llvm.mlir.poison : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
    %1 = llvm.insertvalue %arg7, %0[0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %2 = llvm.insertvalue %arg8, %1[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %3 = llvm.insertvalue %arg9, %2[2] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %4 = llvm.insertvalue %arg10, %3[3, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %5 = llvm.insertvalue %arg12, %4[4, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %6 = llvm.insertvalue %arg11, %5[3, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %7 = llvm.insertvalue %arg13, %6[4, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %8 = builtin.unrealized_conversion_cast %7 : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> to memref<6x3xf32, strided<[3, 1]>>
    %9 = llvm.mlir.poison : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
    %10 = llvm.insertvalue %arg0, %9[0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %11 = llvm.insertvalue %arg1, %10[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %12 = llvm.insertvalue %arg2, %11[2] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %13 = llvm.insertvalue %arg3, %12[3, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %14 = llvm.insertvalue %arg5, %13[4, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %15 = llvm.insertvalue %arg4, %14[3, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %16 = llvm.insertvalue %arg6, %15[4, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %17 = builtin.unrealized_conversion_cast %16 : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> to memref<4x6xf32, strided<[6, 1]>>
    %18 = builtin.unrealized_conversion_cast %8 : memref<6x3xf32, strided<[3, 1]>> to !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
    %19 = builtin.unrealized_conversion_cast %17 : memref<4x6xf32, strided<[6, 1]>> to !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
    %cst = arith.constant 0.000000e+00 : f32
    %c2 = arith.constant 2 : index
    %c6 = arith.constant 6 : index
    %c3 = arith.constant 3 : index
    %c4 = arith.constant 4 : index
    %c1 = arith.constant 1 : index
    %c0 = arith.constant 0 : index
    %20 = builtin.unrealized_conversion_cast %c0 : index to i64
    %21 = llvm.mlir.constant(4 : index) : i64
    %22 = llvm.mlir.constant(3 : index) : i64
    %23 = llvm.mlir.constant(1 : index) : i64
    %24 = llvm.mlir.constant(12 : index) : i64
    %25 = llvm.mlir.zero : !llvm.ptr
    %26 = llvm.getelementptr %25[%24] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %27 = llvm.ptrtoint %26 : !llvm.ptr to i64
    %28 = llvm.call @malloc(%27) : (i64) -> !llvm.ptr
    %29 = llvm.mlir.poison : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
    %30 = llvm.insertvalue %28, %29[0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %31 = llvm.insertvalue %28, %30[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %32 = llvm.mlir.constant(0 : index) : i64
    %33 = llvm.insertvalue %32, %31[2] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %34 = llvm.insertvalue %21, %33[3, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %35 = llvm.insertvalue %22, %34[3, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %36 = llvm.insertvalue %22, %35[4, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %37 = llvm.insertvalue %23, %36[4, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %38 = builtin.unrealized_conversion_cast %37 : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> to memref<4x3xf32>
    llvm.br ^bb1(%20 : i64)
  ^bb1(%39: i64):  // 2 preds: ^bb0, ^bb17
    %40 = builtin.unrealized_conversion_cast %39 : i64 to index
    %41 = arith.cmpi slt, %40, %c4 : index
    llvm.cond_br %41, ^bb2, ^bb18
  ^bb2:  // pred: ^bb1
    llvm.br ^bb3(%20 : i64)
  ^bb3(%42: i64):  // 2 preds: ^bb2, ^bb16
    %43 = builtin.unrealized_conversion_cast %42 : i64 to index
    %44 = arith.cmpi slt, %43, %c3 : index
    llvm.cond_br %44, ^bb4, ^bb17
  ^bb4:  // pred: ^bb3
    llvm.br ^bb5(%20 : i64)
  ^bb5(%45: i64):  // 2 preds: ^bb4, ^bb15
    %46 = builtin.unrealized_conversion_cast %45 : i64 to index
    %47 = arith.cmpi slt, %46, %c6 : index
    llvm.cond_br %47, ^bb6, ^bb16
  ^bb6:  // pred: ^bb5
    %48 = arith.minsi %40, %c4 : index
    llvm.br ^bb7(%39 : i64)
  ^bb7(%49: i64):  // 2 preds: ^bb6, ^bb14
    %50 = builtin.unrealized_conversion_cast %49 : i64 to index
    %51 = builtin.unrealized_conversion_cast %50 : index to i64
    %52 = arith.cmpi slt, %50, %48 : index
    llvm.cond_br %52, ^bb8, ^bb15
  ^bb8:  // pred: ^bb7
    llvm.br ^bb9(%42 : i64)
  ^bb9(%53: i64):  // 2 preds: ^bb8, ^bb13
    %54 = builtin.unrealized_conversion_cast %53 : i64 to index
    %55 = builtin.unrealized_conversion_cast %54 : index to i64
    %56 = arith.cmpi slt, %54, %c3 : index
    llvm.cond_br %56, ^bb10, ^bb14
  ^bb10:  // pred: ^bb9
    llvm.br ^bb11(%45, %cst : i64, f32)
  ^bb11(%57: i64, %58: f32):  // 2 preds: ^bb10, ^bb12
    %59 = builtin.unrealized_conversion_cast %57 : i64 to index
    %60 = builtin.unrealized_conversion_cast %59 : index to i64
    %61 = arith.cmpi slt, %59, %c6 : index
    llvm.cond_br %61, ^bb12, ^bb13
  ^bb12:  // pred: ^bb11
    %62 = llvm.extractvalue %19[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %63 = llvm.mlir.constant(6 : index) : i64
    %64 = llvm.mul %51, %63 overflow<nsw, nuw> : i64
    %65 = llvm.add %64, %60 overflow<nsw, nuw> : i64
    %66 = llvm.getelementptr inbounds|nuw %62[%65] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %67 = llvm.load %66 : !llvm.ptr -> f32
    %68 = llvm.extractvalue %18[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %69 = llvm.mlir.constant(3 : index) : i64
    %70 = llvm.mul %60, %69 overflow<nsw, nuw> : i64
    %71 = llvm.add %70, %55 overflow<nsw, nuw> : i64
    %72 = llvm.getelementptr inbounds|nuw %68[%71] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %73 = llvm.load %72 : !llvm.ptr -> f32
    %74 = arith.mulf %67, %73 : f32
    %75 = arith.addf %58, %74 : f32
    %76 = arith.addi %59, %c1 : index
    %77 = builtin.unrealized_conversion_cast %76 : index to i64
    llvm.br ^bb11(%77, %75 : i64, f32)
  ^bb13:  // pred: ^bb11
    %78 = llvm.extractvalue %37[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %79 = llvm.mlir.constant(3 : index) : i64
    %80 = llvm.mul %51, %79 overflow<nsw, nuw> : i64
    %81 = llvm.add %80, %55 overflow<nsw, nuw> : i64
    %82 = llvm.getelementptr inbounds|nuw %78[%81] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    llvm.store %58, %82 : f32, !llvm.ptr
    %83 = arith.addi %54, %c1 : index
    %84 = builtin.unrealized_conversion_cast %83 : index to i64
    llvm.br ^bb9(%84 : i64)
  ^bb14:  // pred: ^bb9
    %85 = arith.addi %50, %c1 : index
    %86 = builtin.unrealized_conversion_cast %85 : index to i64
    llvm.br ^bb7(%86 : i64)
  ^bb15:  // pred: ^bb7
    %87 = arith.addi %46, %c3 : index
    %88 = builtin.unrealized_conversion_cast %87 : index to i64
    llvm.br ^bb5(%88 : i64)
  ^bb16:  // pred: ^bb5
    %89 = arith.addi %43, %c2 : index
    %90 = builtin.unrealized_conversion_cast %89 : index to i64
    llvm.br ^bb3(%90 : i64)
  ^bb17:  // pred: ^bb3
    %91 = arith.addi %40, %c2 : index
    %92 = builtin.unrealized_conversion_cast %91 : index to i64
    llvm.br ^bb1(%92 : i64)
  ^bb18:  // pred: ^bb1
    llvm.return %37 : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
  }
  llvm.func @_mlir_ciface_kernel_tiled(%arg0: !llvm.ptr, %arg1: !llvm.ptr, %arg2: !llvm.ptr) attributes {llvm.emit_c_interface} {
    %0 = llvm.load %arg1 : !llvm.ptr -> !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
    %1 = llvm.extractvalue %0[0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %2 = llvm.extractvalue %0[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %3 = llvm.extractvalue %0[2] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %4 = llvm.extractvalue %0[3, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %5 = llvm.extractvalue %0[3, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %6 = llvm.extractvalue %0[4, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %7 = llvm.extractvalue %0[4, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %8 = llvm.load %arg2 : !llvm.ptr -> !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
    %9 = llvm.extractvalue %8[0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %10 = llvm.extractvalue %8[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %11 = llvm.extractvalue %8[2] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %12 = llvm.extractvalue %8[3, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %13 = llvm.extractvalue %8[3, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %14 = llvm.extractvalue %8[4, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %15 = llvm.extractvalue %8[4, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %16 = llvm.call @kernel_tiled(%1, %2, %3, %4, %5, %6, %7, %9, %10, %11, %12, %13, %14, %15) : (!llvm.ptr, !llvm.ptr, i64, i64, i64, i64, i64, !llvm.ptr, !llvm.ptr, i64, i64, i64, i64, i64) -> !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
    llvm.store %16, %arg0 : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>, !llvm.ptr
    llvm.return
  }
}

