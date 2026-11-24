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
    %20 = llvm.mlir.constant(0.000000e+00 : f32) : f32
    %21 = llvm.mlir.constant(2 : index) : i64
    %22 = llvm.mlir.constant(6 : index) : i64
    %23 = llvm.mlir.constant(3 : index) : i64
    %24 = llvm.mlir.constant(4 : index) : i64
    %25 = llvm.mlir.constant(1 : index) : i64
    %26 = llvm.mlir.constant(0 : index) : i64
    %27 = builtin.unrealized_conversion_cast %26 : i64 to index
    %28 = builtin.unrealized_conversion_cast %27 : index to i64
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
  ^bb1(%47: i64):  // 2 preds: ^bb0, ^bb17
    %48 = builtin.unrealized_conversion_cast %47 : i64 to index
    %49 = llvm.icmp "slt" %47, %24 : i64
    llvm.cond_br %49, ^bb2, ^bb18
  ^bb2:  // pred: ^bb1
    llvm.br ^bb3(%28 : i64)
  ^bb3(%50: i64):  // 2 preds: ^bb2, ^bb16
    %51 = builtin.unrealized_conversion_cast %50 : i64 to index
    %52 = llvm.icmp "slt" %50, %23 : i64
    llvm.cond_br %52, ^bb4, ^bb17
  ^bb4:  // pred: ^bb3
    llvm.br ^bb5(%28 : i64)
  ^bb5(%53: i64):  // 2 preds: ^bb4, ^bb15
    %54 = builtin.unrealized_conversion_cast %53 : i64 to index
    %55 = llvm.icmp "slt" %53, %22 : i64
    llvm.cond_br %55, ^bb6, ^bb16
  ^bb6:  // pred: ^bb5
    %56 = llvm.intr.smin(%47, %24) : (i64, i64) -> i64
    llvm.br ^bb7(%47 : i64)
  ^bb7(%57: i64):  // 2 preds: ^bb6, ^bb14
    %58 = builtin.unrealized_conversion_cast %57 : i64 to index
    %59 = builtin.unrealized_conversion_cast %58 : index to i64
    %60 = llvm.icmp "slt" %57, %56 : i64
    llvm.cond_br %60, ^bb8, ^bb15
  ^bb8:  // pred: ^bb7
    llvm.br ^bb9(%50 : i64)
  ^bb9(%61: i64):  // 2 preds: ^bb8, ^bb13
    %62 = builtin.unrealized_conversion_cast %61 : i64 to index
    %63 = builtin.unrealized_conversion_cast %62 : index to i64
    %64 = llvm.icmp "slt" %61, %23 : i64
    llvm.cond_br %64, ^bb10, ^bb14
  ^bb10:  // pred: ^bb9
    llvm.br ^bb11(%53, %20 : i64, f32)
  ^bb11(%65: i64, %66: f32):  // 2 preds: ^bb10, ^bb12
    %67 = builtin.unrealized_conversion_cast %65 : i64 to index
    %68 = builtin.unrealized_conversion_cast %67 : index to i64
    %69 = llvm.icmp "slt" %65, %22 : i64
    llvm.cond_br %69, ^bb12, ^bb13
  ^bb12:  // pred: ^bb11
    %70 = llvm.extractvalue %19[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %71 = llvm.mlir.constant(6 : index) : i64
    %72 = llvm.mul %59, %71 overflow<nsw, nuw> : i64
    %73 = llvm.add %72, %68 overflow<nsw, nuw> : i64
    %74 = llvm.getelementptr inbounds|nuw %70[%73] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %75 = llvm.load %74 : !llvm.ptr -> f32
    %76 = llvm.extractvalue %18[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %77 = llvm.mlir.constant(3 : index) : i64
    %78 = llvm.mul %68, %77 overflow<nsw, nuw> : i64
    %79 = llvm.add %78, %63 overflow<nsw, nuw> : i64
    %80 = llvm.getelementptr inbounds|nuw %76[%79] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %81 = llvm.load %80 : !llvm.ptr -> f32
    %82 = llvm.fmul %75, %81 : f32
    %83 = llvm.fadd %66, %82 : f32
    %84 = llvm.add %65, %25 : i64
    %85 = builtin.unrealized_conversion_cast %84 : i64 to index
    %86 = builtin.unrealized_conversion_cast %85 : index to i64
    llvm.br ^bb11(%86, %83 : i64, f32)
  ^bb13:  // pred: ^bb11
    %87 = llvm.extractvalue %45[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %88 = llvm.mlir.constant(3 : index) : i64
    %89 = llvm.mul %59, %88 overflow<nsw, nuw> : i64
    %90 = llvm.add %89, %63 overflow<nsw, nuw> : i64
    %91 = llvm.getelementptr inbounds|nuw %87[%90] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    llvm.store %66, %91 : f32, !llvm.ptr
    %92 = llvm.add %61, %25 : i64
    %93 = builtin.unrealized_conversion_cast %92 : i64 to index
    %94 = builtin.unrealized_conversion_cast %93 : index to i64
    llvm.br ^bb9(%94 : i64)
  ^bb14:  // pred: ^bb9
    %95 = llvm.add %57, %25 : i64
    %96 = builtin.unrealized_conversion_cast %95 : i64 to index
    %97 = builtin.unrealized_conversion_cast %96 : index to i64
    llvm.br ^bb7(%97 : i64)
  ^bb15:  // pred: ^bb7
    %98 = llvm.add %53, %23 : i64
    %99 = builtin.unrealized_conversion_cast %98 : i64 to index
    %100 = builtin.unrealized_conversion_cast %99 : index to i64
    llvm.br ^bb5(%100 : i64)
  ^bb16:  // pred: ^bb5
    %101 = llvm.add %50, %21 : i64
    %102 = builtin.unrealized_conversion_cast %101 : i64 to index
    %103 = builtin.unrealized_conversion_cast %102 : index to i64
    llvm.br ^bb3(%103 : i64)
  ^bb17:  // pred: ^bb3
    %104 = llvm.add %47, %21 : i64
    %105 = builtin.unrealized_conversion_cast %104 : i64 to index
    %106 = builtin.unrealized_conversion_cast %105 : index to i64
    llvm.br ^bb1(%106 : i64)
  ^bb18:  // pred: ^bb1
    llvm.return %45 : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
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

