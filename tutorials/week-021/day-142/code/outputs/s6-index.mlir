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
    %18 = llvm.mlir.constant(0.000000e+00 : f32) : f32
    %19 = llvm.mlir.constant(2 : index) : i64
    %20 = llvm.mlir.constant(6 : index) : i64
    %21 = llvm.mlir.constant(3 : index) : i64
    %22 = llvm.mlir.constant(4 : index) : i64
    %23 = llvm.mlir.constant(1 : index) : i64
    %24 = llvm.mlir.constant(0 : index) : i64
    %25 = builtin.unrealized_conversion_cast %24 : i64 to index
    %26 = llvm.mlir.constant(4 : index) : i64
    %27 = llvm.mlir.constant(3 : index) : i64
    %28 = llvm.mlir.constant(1 : index) : i64
    %29 = llvm.mlir.constant(12 : index) : i64
    %30 = llvm.mlir.zero : !llvm.ptr
    %31 = llvm.getelementptr %30[%29] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %32 = llvm.ptrtoint %31 : !llvm.ptr to i64
    %33 = llvm.call @malloc(%32) : (i64) -> !llvm.ptr
    %34 = llvm.mlir.poison : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
    %35 = llvm.insertvalue %33, %34[0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %36 = llvm.insertvalue %33, %35[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %37 = llvm.mlir.constant(0 : index) : i64
    %38 = llvm.insertvalue %37, %36[2] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %39 = llvm.insertvalue %26, %38[3, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %40 = llvm.insertvalue %27, %39[3, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %41 = llvm.insertvalue %27, %40[4, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %42 = llvm.insertvalue %28, %41[4, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %43 = builtin.unrealized_conversion_cast %42 : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> to memref<4x3xf32>
    llvm.br ^bb1(%24 : i64)
  ^bb1(%44: i64):  // 2 preds: ^bb0, ^bb17
    %45 = builtin.unrealized_conversion_cast %44 : i64 to index
    %46 = llvm.icmp "slt" %44, %22 : i64
    llvm.cond_br %46, ^bb2, ^bb18
  ^bb2:  // pred: ^bb1
    llvm.br ^bb3(%24 : i64)
  ^bb3(%47: i64):  // 2 preds: ^bb2, ^bb16
    %48 = builtin.unrealized_conversion_cast %47 : i64 to index
    %49 = llvm.icmp "slt" %47, %21 : i64
    llvm.cond_br %49, ^bb4, ^bb17
  ^bb4:  // pred: ^bb3
    llvm.br ^bb5(%24 : i64)
  ^bb5(%50: i64):  // 2 preds: ^bb4, ^bb15
    %51 = builtin.unrealized_conversion_cast %50 : i64 to index
    %52 = llvm.icmp "slt" %50, %20 : i64
    llvm.cond_br %52, ^bb6, ^bb16
  ^bb6:  // pred: ^bb5
    %53 = llvm.intr.smin(%44, %22) : (i64, i64) -> i64
    llvm.br ^bb7(%44 : i64)
  ^bb7(%54: i64):  // 2 preds: ^bb6, ^bb14
    %55 = builtin.unrealized_conversion_cast %54 : i64 to index
    %56 = llvm.icmp "slt" %54, %53 : i64
    llvm.cond_br %56, ^bb8, ^bb15
  ^bb8:  // pred: ^bb7
    llvm.br ^bb9(%47 : i64)
  ^bb9(%57: i64):  // 2 preds: ^bb8, ^bb13
    %58 = builtin.unrealized_conversion_cast %57 : i64 to index
    %59 = llvm.icmp "slt" %57, %21 : i64
    llvm.cond_br %59, ^bb10, ^bb14
  ^bb10:  // pred: ^bb9
    llvm.br ^bb11(%50, %18 : i64, f32)
  ^bb11(%60: i64, %61: f32):  // 2 preds: ^bb10, ^bb12
    %62 = builtin.unrealized_conversion_cast %60 : i64 to index
    %63 = llvm.icmp "slt" %60, %20 : i64
    llvm.cond_br %63, ^bb12, ^bb13
  ^bb12:  // pred: ^bb11
    %64 = llvm.extractvalue %16[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %65 = llvm.mlir.constant(6 : index) : i64
    %66 = llvm.mul %54, %65 overflow<nsw, nuw> : i64
    %67 = llvm.add %66, %60 overflow<nsw, nuw> : i64
    %68 = llvm.getelementptr inbounds|nuw %64[%67] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %69 = llvm.load %68 : !llvm.ptr -> f32
    %70 = llvm.extractvalue %7[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %71 = llvm.mlir.constant(3 : index) : i64
    %72 = llvm.mul %60, %71 overflow<nsw, nuw> : i64
    %73 = llvm.add %72, %57 overflow<nsw, nuw> : i64
    %74 = llvm.getelementptr inbounds|nuw %70[%73] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %75 = llvm.load %74 : !llvm.ptr -> f32
    %76 = llvm.fmul %69, %75 : f32
    %77 = llvm.fadd %61, %76 : f32
    %78 = llvm.add %60, %23 : i64
    %79 = builtin.unrealized_conversion_cast %78 : i64 to index
    llvm.br ^bb11(%78, %77 : i64, f32)
  ^bb13:  // pred: ^bb11
    %80 = llvm.extractvalue %42[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %81 = llvm.mlir.constant(3 : index) : i64
    %82 = llvm.mul %54, %81 overflow<nsw, nuw> : i64
    %83 = llvm.add %82, %57 overflow<nsw, nuw> : i64
    %84 = llvm.getelementptr inbounds|nuw %80[%83] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    llvm.store %61, %84 : f32, !llvm.ptr
    %85 = llvm.add %57, %23 : i64
    %86 = builtin.unrealized_conversion_cast %85 : i64 to index
    llvm.br ^bb9(%85 : i64)
  ^bb14:  // pred: ^bb9
    %87 = llvm.add %54, %23 : i64
    %88 = builtin.unrealized_conversion_cast %87 : i64 to index
    llvm.br ^bb7(%87 : i64)
  ^bb15:  // pred: ^bb7
    %89 = llvm.add %50, %21 : i64
    %90 = builtin.unrealized_conversion_cast %89 : i64 to index
    llvm.br ^bb5(%89 : i64)
  ^bb16:  // pred: ^bb5
    %91 = llvm.add %47, %19 : i64
    %92 = builtin.unrealized_conversion_cast %91 : i64 to index
    llvm.br ^bb3(%91 : i64)
  ^bb17:  // pred: ^bb3
    %93 = llvm.add %44, %19 : i64
    %94 = builtin.unrealized_conversion_cast %93 : i64 to index
    llvm.br ^bb1(%93 : i64)
  ^bb18:  // pred: ^bb1
    llvm.return %42 : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
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

