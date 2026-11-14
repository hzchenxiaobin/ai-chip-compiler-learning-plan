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
    %28 = llvm.mlir.constant(0.000000e+00 : f32) : f32
    %29 = llvm.mlir.constant(1 : index) : i64
    %30 = llvm.mlir.constant(6 : index) : i64
    %31 = llvm.mlir.constant(3 : index) : i64
    %32 = llvm.mlir.constant(4 : index) : i64
    %33 = llvm.mlir.constant(0 : index) : i64
    %34 = builtin.unrealized_conversion_cast %33 : i64 to index
    %35 = builtin.unrealized_conversion_cast %34 : index to i64
    %36 = llvm.mlir.constant(4 : index) : i64
    %37 = llvm.mlir.constant(3 : index) : i64
    %38 = llvm.mlir.constant(1 : index) : i64
    %39 = llvm.mlir.constant(12 : index) : i64
    %40 = llvm.mlir.zero : !llvm.ptr
    %41 = llvm.getelementptr %40[%39] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %42 = llvm.ptrtoint %41 : !llvm.ptr to i64
    %43 = llvm.call @malloc(%42) : (i64) -> !llvm.ptr
    %44 = llvm.mlir.poison : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
    %45 = llvm.insertvalue %43, %44[0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %46 = llvm.insertvalue %43, %45[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %47 = llvm.mlir.constant(0 : index) : i64
    %48 = llvm.insertvalue %47, %46[2] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %49 = llvm.insertvalue %36, %48[3, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %50 = llvm.insertvalue %37, %49[3, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %51 = llvm.insertvalue %37, %50[4, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %52 = llvm.insertvalue %38, %51[4, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %53 = builtin.unrealized_conversion_cast %52 : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> to memref<4x3xf32>
    llvm.br ^bb1(%35 : i64)
  ^bb1(%54: i64):  // 2 preds: ^bb0, ^bb8
    %55 = builtin.unrealized_conversion_cast %54 : i64 to index
    %56 = builtin.unrealized_conversion_cast %55 : index to i64
    %57 = llvm.icmp "slt" %54, %32 : i64
    llvm.cond_br %57, ^bb2, ^bb9
  ^bb2:  // pred: ^bb1
    llvm.br ^bb3(%35 : i64)
  ^bb3(%58: i64):  // 2 preds: ^bb2, ^bb7
    %59 = builtin.unrealized_conversion_cast %58 : i64 to index
    %60 = builtin.unrealized_conversion_cast %59 : index to i64
    %61 = llvm.icmp "slt" %58, %31 : i64
    llvm.cond_br %61, ^bb4, ^bb8
  ^bb4:  // pred: ^bb3
    %62 = llvm.extractvalue %27[1] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %63 = llvm.getelementptr inbounds|nuw %62[%60] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %64 = llvm.load %63 : !llvm.ptr -> f32
    llvm.br ^bb5(%35, %64 : i64, f32)
  ^bb5(%65: i64, %66: f32):  // 2 preds: ^bb4, ^bb6
    %67 = builtin.unrealized_conversion_cast %65 : i64 to index
    %68 = builtin.unrealized_conversion_cast %67 : index to i64
    %69 = llvm.icmp "slt" %65, %30 : i64
    llvm.cond_br %69, ^bb6, ^bb7
  ^bb6:  // pred: ^bb5
    %70 = llvm.extractvalue %26[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %71 = llvm.mlir.constant(6 : index) : i64
    %72 = llvm.mul %56, %71 overflow<nsw, nuw> : i64
    %73 = llvm.add %72, %68 overflow<nsw, nuw> : i64
    %74 = llvm.getelementptr inbounds|nuw %70[%73] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %75 = llvm.load %74 : !llvm.ptr -> f32
    %76 = llvm.extractvalue %25[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %77 = llvm.mlir.constant(3 : index) : i64
    %78 = llvm.mul %68, %77 overflow<nsw, nuw> : i64
    %79 = llvm.add %78, %60 overflow<nsw, nuw> : i64
    %80 = llvm.getelementptr inbounds|nuw %76[%79] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %81 = llvm.load %80 : !llvm.ptr -> f32
    %82 = llvm.fmul %75, %81 : f32
    %83 = llvm.fadd %66, %82 : f32
    %84 = llvm.add %65, %29 : i64
    %85 = builtin.unrealized_conversion_cast %84 : i64 to index
    %86 = builtin.unrealized_conversion_cast %85 : index to i64
    llvm.br ^bb5(%86, %83 : i64, f32)
  ^bb7:  // pred: ^bb5
    %87 = llvm.fcmp "ogt" %66, %28 : f32
    %88 = llvm.select %87, %66, %28 : i1, f32
    %89 = llvm.extractvalue %52[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %90 = llvm.mlir.constant(3 : index) : i64
    %91 = llvm.mul %56, %90 overflow<nsw, nuw> : i64
    %92 = llvm.add %91, %60 overflow<nsw, nuw> : i64
    %93 = llvm.getelementptr inbounds|nuw %89[%92] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    llvm.store %88, %93 : f32, !llvm.ptr
    %94 = llvm.add %58, %29 : i64
    %95 = builtin.unrealized_conversion_cast %94 : i64 to index
    %96 = builtin.unrealized_conversion_cast %95 : index to i64
    llvm.br ^bb3(%96 : i64)
  ^bb8:  // pred: ^bb3
    %97 = llvm.add %54, %29 : i64
    %98 = builtin.unrealized_conversion_cast %97 : i64 to index
    %99 = builtin.unrealized_conversion_cast %98 : index to i64
    llvm.br ^bb1(%99 : i64)
  ^bb9:  // pred: ^bb1
    llvm.return %52 : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
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

