module {
  llvm.func @malloc(i64) -> !llvm.ptr
  llvm.func @main_kernel(%arg0: !llvm.ptr, %arg1: !llvm.ptr, %arg2: i64, %arg3: i64, %arg4: i64, %arg5: i64, %arg6: i64, %arg7: !llvm.ptr, %arg8: !llvm.ptr, %arg9: i64, %arg10: i64, %arg11: i64, %arg12: i64, %arg13: i64, %arg14: !llvm.ptr, %arg15: !llvm.ptr, %arg16: i64, %arg17: i64, %arg18: i64) -> !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> attributes {llvm.emit_c_interface} {
    %0 = llvm.mlir.poison : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)>
    %1 = llvm.insertvalue %arg14, %0[0] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %2 = llvm.insertvalue %arg15, %1[1] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %3 = llvm.insertvalue %arg16, %2[2] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %4 = llvm.insertvalue %arg17, %3[3, 0] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %5 = llvm.insertvalue %arg18, %4[4, 0] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %6 = builtin.unrealized_conversion_cast %5 : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> to memref<3xf32, strided<[1]>>
    %7 = llvm.mlir.poison : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
    %8 = llvm.insertvalue %arg7, %7[0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %9 = llvm.insertvalue %arg8, %8[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %10 = llvm.insertvalue %arg9, %9[2] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %11 = llvm.insertvalue %arg10, %10[3, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %12 = llvm.insertvalue %arg12, %11[4, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %13 = llvm.insertvalue %arg11, %12[3, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %14 = llvm.insertvalue %arg13, %13[4, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %15 = builtin.unrealized_conversion_cast %14 : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> to memref<6x3xf32, strided<[3, 1]>>
    %16 = llvm.mlir.poison : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
    %17 = llvm.insertvalue %arg0, %16[0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %18 = llvm.insertvalue %arg1, %17[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %19 = llvm.insertvalue %arg2, %18[2] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %20 = llvm.insertvalue %arg3, %19[3, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %21 = llvm.insertvalue %arg5, %20[4, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %22 = llvm.insertvalue %arg4, %21[3, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %23 = llvm.insertvalue %arg6, %22[4, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %24 = builtin.unrealized_conversion_cast %23 : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> to memref<4x6xf32, strided<[6, 1]>>
    %25 = builtin.unrealized_conversion_cast %15 : memref<6x3xf32, strided<[3, 1]>> to !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
    %26 = builtin.unrealized_conversion_cast %24 : memref<4x6xf32, strided<[6, 1]>> to !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
    %27 = builtin.unrealized_conversion_cast %6 : memref<3xf32, strided<[1]>> to !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)>
    %cst = arith.constant 0.000000e+00 : f32
    %c2 = arith.constant 2 : index
    %c6 = arith.constant 6 : index
    %c3 = arith.constant 3 : index
    %c4 = arith.constant 4 : index
    %c1 = arith.constant 1 : index
    %c0 = arith.constant 0 : index
    %28 = builtin.unrealized_conversion_cast %c0 : index to i64
    %29 = llvm.mlir.constant(4 : index) : i64
    %30 = llvm.mlir.constant(3 : index) : i64
    %31 = llvm.mlir.constant(1 : index) : i64
    %32 = llvm.mlir.constant(12 : index) : i64
    %33 = llvm.mlir.zero : !llvm.ptr
    %34 = llvm.getelementptr %33[%32] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %35 = llvm.ptrtoint %34 : !llvm.ptr to i64
    %36 = llvm.call @malloc(%35) : (i64) -> !llvm.ptr
    %37 = llvm.mlir.poison : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
    %38 = llvm.insertvalue %36, %37[0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %39 = llvm.insertvalue %36, %38[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %40 = llvm.mlir.constant(0 : index) : i64
    %41 = llvm.insertvalue %40, %39[2] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %42 = llvm.insertvalue %29, %41[3, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %43 = llvm.insertvalue %30, %42[3, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %44 = llvm.insertvalue %30, %43[4, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %45 = llvm.insertvalue %31, %44[4, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %46 = builtin.unrealized_conversion_cast %45 : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> to memref<4x3xf32>
    llvm.br ^bb1(%28 : i64)
  ^bb1(%47: i64):  // 2 preds: ^bb0, ^bb14
    %48 = builtin.unrealized_conversion_cast %47 : i64 to index
    %49 = arith.cmpi slt, %48, %c4 : index
    llvm.cond_br %49, ^bb2, ^bb15
  ^bb2:  // pred: ^bb1
    llvm.br ^bb3(%28 : i64)
  ^bb3(%50: i64):  // 2 preds: ^bb2, ^bb13
    %51 = builtin.unrealized_conversion_cast %50 : i64 to index
    %52 = arith.cmpi slt, %51, %c6 : index
    llvm.cond_br %52, ^bb4, ^bb14
  ^bb4:  // pred: ^bb3
    llvm.br ^bb5(%47 : i64)
  ^bb5(%53: i64):  // 2 preds: ^bb4, ^bb12
    %54 = builtin.unrealized_conversion_cast %53 : i64 to index
    %55 = builtin.unrealized_conversion_cast %54 : index to i64
    %56 = arith.cmpi slt, %54, %c4 : index
    llvm.cond_br %56, ^bb6, ^bb13
  ^bb6:  // pred: ^bb5
    llvm.br ^bb7(%28 : i64)
  ^bb7(%57: i64):  // 2 preds: ^bb6, ^bb11
    %58 = builtin.unrealized_conversion_cast %57 : i64 to index
    %59 = builtin.unrealized_conversion_cast %58 : index to i64
    %60 = arith.cmpi slt, %58, %c3 : index
    llvm.cond_br %60, ^bb8, ^bb12
  ^bb8:  // pred: ^bb7
    %61 = llvm.extractvalue %27[1] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %62 = llvm.getelementptr inbounds|nuw %61[%59] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %63 = llvm.load %62 : !llvm.ptr -> f32
    llvm.br ^bb9(%28, %63 : i64, f32)
  ^bb9(%64: i64, %65: f32):  // 2 preds: ^bb8, ^bb10
    %66 = builtin.unrealized_conversion_cast %64 : i64 to index
    %67 = builtin.unrealized_conversion_cast %66 : index to i64
    %68 = arith.cmpi slt, %66, %c6 : index
    llvm.cond_br %68, ^bb10, ^bb11
  ^bb10:  // pred: ^bb9
    %69 = llvm.extractvalue %26[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %70 = llvm.mlir.constant(6 : index) : i64
    %71 = llvm.mul %55, %70 overflow<nsw, nuw> : i64
    %72 = llvm.add %71, %67 overflow<nsw, nuw> : i64
    %73 = llvm.getelementptr inbounds|nuw %69[%72] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %74 = llvm.load %73 : !llvm.ptr -> f32
    %75 = llvm.extractvalue %25[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %76 = llvm.mlir.constant(3 : index) : i64
    %77 = llvm.mul %67, %76 overflow<nsw, nuw> : i64
    %78 = llvm.add %77, %59 overflow<nsw, nuw> : i64
    %79 = llvm.getelementptr inbounds|nuw %75[%78] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %80 = llvm.load %79 : !llvm.ptr -> f32
    %81 = arith.mulf %74, %80 : f32
    %82 = arith.addf %65, %81 : f32
    %83 = arith.addi %66, %c1 : index
    %84 = builtin.unrealized_conversion_cast %83 : index to i64
    llvm.br ^bb9(%84, %82 : i64, f32)
  ^bb11:  // pred: ^bb9
    %85 = arith.cmpf ogt, %65, %cst : f32
    %86 = arith.select %85, %65, %cst : f32
    %87 = llvm.extractvalue %45[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %88 = llvm.mlir.constant(3 : index) : i64
    %89 = llvm.mul %55, %88 overflow<nsw, nuw> : i64
    %90 = llvm.add %89, %59 overflow<nsw, nuw> : i64
    %91 = llvm.getelementptr inbounds|nuw %87[%90] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    llvm.store %86, %91 : f32, !llvm.ptr
    %92 = arith.addi %58, %c1 : index
    %93 = builtin.unrealized_conversion_cast %92 : index to i64
    llvm.br ^bb7(%93 : i64)
  ^bb12:  // pred: ^bb7
    %94 = arith.addi %54, %c1 : index
    %95 = builtin.unrealized_conversion_cast %94 : index to i64
    llvm.br ^bb5(%95 : i64)
  ^bb13:  // pred: ^bb5
    %96 = arith.addi %51, %c2 : index
    %97 = builtin.unrealized_conversion_cast %96 : index to i64
    llvm.br ^bb3(%97 : i64)
  ^bb14:  // pred: ^bb3
    %98 = arith.addi %48, %c2 : index
    %99 = builtin.unrealized_conversion_cast %98 : index to i64
    llvm.br ^bb1(%99 : i64)
  ^bb15:  // pred: ^bb1
    llvm.return %45 : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
  }
  llvm.func @_mlir_ciface_main_kernel(%arg0: !llvm.ptr, %arg1: !llvm.ptr, %arg2: !llvm.ptr, %arg3: !llvm.ptr) attributes {llvm.emit_c_interface} {
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
    %16 = llvm.load %arg3 : !llvm.ptr -> !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)>
    %17 = llvm.extractvalue %16[0] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %18 = llvm.extractvalue %16[1] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %19 = llvm.extractvalue %16[2] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %20 = llvm.extractvalue %16[3, 0] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %21 = llvm.extractvalue %16[4, 0] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %22 = llvm.call @main_kernel(%1, %2, %3, %4, %5, %6, %7, %9, %10, %11, %12, %13, %14, %15, %17, %18, %19, %20, %21) : (!llvm.ptr, !llvm.ptr, i64, i64, i64, i64, i64, !llvm.ptr, !llvm.ptr, i64, i64, i64, i64, i64, !llvm.ptr, !llvm.ptr, i64, i64, i64) -> !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
    llvm.store %22, %arg0 : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>, !llvm.ptr
    llvm.return
  }
}

