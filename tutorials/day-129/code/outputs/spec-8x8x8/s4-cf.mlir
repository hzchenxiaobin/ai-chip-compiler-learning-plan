module {
  llvm.func @malloc(i64) -> !llvm.ptr
  llvm.func @kernel_s8x8x8(%arg0: !llvm.ptr, %arg1: !llvm.ptr, %arg2: i64, %arg3: i64, %arg4: i64, %arg5: i64, %arg6: i64, %arg7: !llvm.ptr, %arg8: !llvm.ptr, %arg9: i64, %arg10: i64, %arg11: i64, %arg12: i64, %arg13: i64) -> !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> attributes {llvm.emit_c_interface} {
    %0 = llvm.mlir.poison : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
    %1 = llvm.insertvalue %arg7, %0[0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %2 = llvm.insertvalue %arg8, %1[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %3 = llvm.insertvalue %arg9, %2[2] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %4 = llvm.insertvalue %arg10, %3[3, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %5 = llvm.insertvalue %arg12, %4[4, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %6 = llvm.insertvalue %arg11, %5[3, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %7 = llvm.insertvalue %arg13, %6[4, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %8 = builtin.unrealized_conversion_cast %7 : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> to memref<8x8xf32, strided<[8, 1]>>
    %9 = llvm.mlir.poison : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
    %10 = llvm.insertvalue %arg0, %9[0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %11 = llvm.insertvalue %arg1, %10[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %12 = llvm.insertvalue %arg2, %11[2] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %13 = llvm.insertvalue %arg3, %12[3, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %14 = llvm.insertvalue %arg5, %13[4, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %15 = llvm.insertvalue %arg4, %14[3, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %16 = llvm.insertvalue %arg6, %15[4, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %17 = builtin.unrealized_conversion_cast %16 : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> to memref<8x8xf32, strided<[8, 1]>>
    %18 = builtin.unrealized_conversion_cast %8 : memref<8x8xf32, strided<[8, 1]>> to !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
    %19 = builtin.unrealized_conversion_cast %17 : memref<8x8xf32, strided<[8, 1]>> to !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
    %cst = arith.constant 0.000000e+00 : f32
    %c1 = arith.constant 1 : index
    %c8 = arith.constant 8 : index
    %c0 = arith.constant 0 : index
    %20 = builtin.unrealized_conversion_cast %c0 : index to i64
    %21 = llvm.mlir.constant(8 : index) : i64
    %22 = llvm.mlir.constant(8 : index) : i64
    %23 = llvm.mlir.constant(1 : index) : i64
    %24 = llvm.mlir.constant(64 : index) : i64
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
    %38 = builtin.unrealized_conversion_cast %37 : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> to memref<8x8xf32>
    llvm.br ^bb1(%20 : i64)
  ^bb1(%39: i64):  // 2 preds: ^bb0, ^bb8
    %40 = builtin.unrealized_conversion_cast %39 : i64 to index
    %41 = builtin.unrealized_conversion_cast %40 : index to i64
    %42 = arith.cmpi slt, %40, %c8 : index
    llvm.cond_br %42, ^bb2, ^bb9
  ^bb2:  // pred: ^bb1
    llvm.br ^bb3(%20 : i64)
  ^bb3(%43: i64):  // 2 preds: ^bb2, ^bb7
    %44 = builtin.unrealized_conversion_cast %43 : i64 to index
    %45 = builtin.unrealized_conversion_cast %44 : index to i64
    %46 = arith.cmpi slt, %44, %c8 : index
    llvm.cond_br %46, ^bb4, ^bb8
  ^bb4:  // pred: ^bb3
    llvm.br ^bb5(%20, %cst : i64, f32)
  ^bb5(%47: i64, %48: f32):  // 2 preds: ^bb4, ^bb6
    %49 = builtin.unrealized_conversion_cast %47 : i64 to index
    %50 = builtin.unrealized_conversion_cast %49 : index to i64
    %51 = arith.cmpi slt, %49, %c8 : index
    llvm.cond_br %51, ^bb6, ^bb7
  ^bb6:  // pred: ^bb5
    %52 = llvm.extractvalue %19[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %53 = llvm.mlir.constant(8 : index) : i64
    %54 = llvm.mul %41, %53 overflow<nsw, nuw> : i64
    %55 = llvm.add %54, %50 overflow<nsw, nuw> : i64
    %56 = llvm.getelementptr inbounds|nuw %52[%55] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %57 = llvm.load %56 : !llvm.ptr -> f32
    %58 = llvm.extractvalue %18[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %59 = llvm.mlir.constant(8 : index) : i64
    %60 = llvm.mul %50, %59 overflow<nsw, nuw> : i64
    %61 = llvm.add %60, %45 overflow<nsw, nuw> : i64
    %62 = llvm.getelementptr inbounds|nuw %58[%61] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %63 = llvm.load %62 : !llvm.ptr -> f32
    %64 = arith.mulf %57, %63 : f32
    %65 = arith.addf %48, %64 : f32
    %66 = arith.addi %49, %c1 : index
    %67 = builtin.unrealized_conversion_cast %66 : index to i64
    llvm.br ^bb5(%67, %65 : i64, f32)
  ^bb7:  // pred: ^bb5
    %68 = llvm.extractvalue %37[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %69 = llvm.mlir.constant(8 : index) : i64
    %70 = llvm.mul %41, %69 overflow<nsw, nuw> : i64
    %71 = llvm.add %70, %45 overflow<nsw, nuw> : i64
    %72 = llvm.getelementptr inbounds|nuw %68[%71] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    llvm.store %48, %72 : f32, !llvm.ptr
    %73 = arith.addi %44, %c1 : index
    %74 = builtin.unrealized_conversion_cast %73 : index to i64
    llvm.br ^bb3(%74 : i64)
  ^bb8:  // pred: ^bb3
    %75 = arith.addi %40, %c1 : index
    %76 = builtin.unrealized_conversion_cast %75 : index to i64
    llvm.br ^bb1(%76 : i64)
  ^bb9:  // pred: ^bb1
    llvm.return %37 : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
  }
  llvm.func @_mlir_ciface_kernel_s8x8x8(%arg0: !llvm.ptr, %arg1: !llvm.ptr, %arg2: !llvm.ptr) attributes {llvm.emit_c_interface} {
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
    %16 = llvm.call @kernel_s8x8x8(%1, %2, %3, %4, %5, %6, %7, %9, %10, %11, %12, %13, %14, %15) : (!llvm.ptr, !llvm.ptr, i64, i64, i64, i64, i64, !llvm.ptr, !llvm.ptr, i64, i64, i64, i64, i64) -> !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
    llvm.store %16, %arg0 : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>, !llvm.ptr
    llvm.return
  }
}

