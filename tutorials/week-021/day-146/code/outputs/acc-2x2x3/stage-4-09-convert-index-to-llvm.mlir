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
    %25 = llvm.mlir.constant(0.000000e+00 : f32) : f32
    %26 = llvm.mlir.constant(2 : index) : i64
    %27 = llvm.mlir.constant(6 : index) : i64
    %28 = llvm.mlir.constant(3 : index) : i64
    %29 = llvm.mlir.constant(4 : index) : i64
    %30 = llvm.mlir.constant(1 : index) : i64
    %31 = llvm.mlir.constant(0 : index) : i64
    %32 = builtin.unrealized_conversion_cast %31 : i64 to index
    %33 = llvm.mlir.constant(4 : index) : i64
    %34 = llvm.mlir.constant(3 : index) : i64
    %35 = llvm.mlir.constant(1 : index) : i64
    %36 = llvm.mlir.constant(12 : index) : i64
    %37 = llvm.mlir.zero : !llvm.ptr
    %38 = llvm.getelementptr %37[%36] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %39 = llvm.ptrtoint %38 : !llvm.ptr to i64
    %40 = llvm.call @malloc(%39) : (i64) -> !llvm.ptr
    %41 = llvm.mlir.poison : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
    %42 = llvm.insertvalue %40, %41[0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %43 = llvm.insertvalue %40, %42[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %44 = llvm.mlir.constant(0 : index) : i64
    %45 = llvm.insertvalue %44, %43[2] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %46 = llvm.insertvalue %33, %45[3, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %47 = llvm.insertvalue %34, %46[3, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %48 = llvm.insertvalue %34, %47[4, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %49 = llvm.insertvalue %35, %48[4, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %50 = builtin.unrealized_conversion_cast %49 : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> to memref<4x3xf32>
    llvm.br ^bb1(%31 : i64)
  ^bb1(%51: i64):  // 2 preds: ^bb0, ^bb17
    %52 = builtin.unrealized_conversion_cast %51 : i64 to index
    %53 = llvm.icmp "slt" %51, %29 : i64
    llvm.cond_br %53, ^bb2, ^bb18
  ^bb2:  // pred: ^bb1
    llvm.br ^bb3(%31 : i64)
  ^bb3(%54: i64):  // 2 preds: ^bb2, ^bb16
    %55 = builtin.unrealized_conversion_cast %54 : i64 to index
    %56 = llvm.icmp "slt" %54, %28 : i64
    llvm.cond_br %56, ^bb4, ^bb17
  ^bb4:  // pred: ^bb3
    llvm.br ^bb5(%31 : i64)
  ^bb5(%57: i64):  // 2 preds: ^bb4, ^bb15
    %58 = builtin.unrealized_conversion_cast %57 : i64 to index
    %59 = llvm.icmp "slt" %57, %27 : i64
    llvm.cond_br %59, ^bb6, ^bb16
  ^bb6:  // pred: ^bb5
    llvm.br ^bb7(%51 : i64)
  ^bb7(%60: i64):  // 2 preds: ^bb6, ^bb14
    %61 = builtin.unrealized_conversion_cast %60 : i64 to index
    %62 = llvm.icmp "slt" %60, %29 : i64
    llvm.cond_br %62, ^bb8, ^bb15
  ^bb8:  // pred: ^bb7
    llvm.br ^bb9(%54 : i64)
  ^bb9(%63: i64):  // 2 preds: ^bb8, ^bb13
    %64 = builtin.unrealized_conversion_cast %63 : i64 to index
    %65 = llvm.icmp "slt" %63, %28 : i64
    llvm.cond_br %65, ^bb10, ^bb14
  ^bb10:  // pred: ^bb9
    %66 = llvm.extractvalue %5[1] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %67 = llvm.getelementptr inbounds|nuw %66[%63] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %68 = llvm.load %67 : !llvm.ptr -> f32
    llvm.br ^bb11(%31, %68 : i64, f32)
  ^bb11(%69: i64, %70: f32):  // 2 preds: ^bb10, ^bb12
    %71 = builtin.unrealized_conversion_cast %69 : i64 to index
    %72 = llvm.icmp "slt" %69, %27 : i64
    llvm.cond_br %72, ^bb12, ^bb13
  ^bb12:  // pred: ^bb11
    %73 = llvm.extractvalue %23[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %74 = llvm.mlir.constant(6 : index) : i64
    %75 = llvm.mul %60, %74 overflow<nsw, nuw> : i64
    %76 = llvm.add %75, %69 overflow<nsw, nuw> : i64
    %77 = llvm.getelementptr inbounds|nuw %73[%76] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %78 = llvm.load %77 : !llvm.ptr -> f32
    %79 = llvm.extractvalue %14[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %80 = llvm.mlir.constant(3 : index) : i64
    %81 = llvm.mul %69, %80 overflow<nsw, nuw> : i64
    %82 = llvm.add %81, %63 overflow<nsw, nuw> : i64
    %83 = llvm.getelementptr inbounds|nuw %79[%82] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %84 = llvm.load %83 : !llvm.ptr -> f32
    %85 = llvm.fmul %78, %84 : f32
    %86 = llvm.fadd %70, %85 : f32
    %87 = llvm.add %69, %30 : i64
    %88 = builtin.unrealized_conversion_cast %87 : i64 to index
    llvm.br ^bb11(%87, %86 : i64, f32)
  ^bb13:  // pred: ^bb11
    %89 = llvm.fcmp "ogt" %70, %25 : f32
    %90 = llvm.select %89, %70, %25 : i1, f32
    %91 = llvm.extractvalue %49[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %92 = llvm.mlir.constant(3 : index) : i64
    %93 = llvm.mul %60, %92 overflow<nsw, nuw> : i64
    %94 = llvm.add %93, %63 overflow<nsw, nuw> : i64
    %95 = llvm.getelementptr inbounds|nuw %91[%94] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    llvm.store %90, %95 : f32, !llvm.ptr
    %96 = llvm.add %63, %30 : i64
    %97 = builtin.unrealized_conversion_cast %96 : i64 to index
    llvm.br ^bb9(%96 : i64)
  ^bb14:  // pred: ^bb9
    %98 = llvm.add %60, %30 : i64
    %99 = builtin.unrealized_conversion_cast %98 : i64 to index
    llvm.br ^bb7(%98 : i64)
  ^bb15:  // pred: ^bb7
    %100 = llvm.add %57, %28 : i64
    %101 = builtin.unrealized_conversion_cast %100 : i64 to index
    llvm.br ^bb5(%100 : i64)
  ^bb16:  // pred: ^bb5
    %102 = llvm.add %54, %26 : i64
    %103 = builtin.unrealized_conversion_cast %102 : i64 to index
    llvm.br ^bb3(%102 : i64)
  ^bb17:  // pred: ^bb3
    %104 = llvm.add %51, %26 : i64
    %105 = builtin.unrealized_conversion_cast %104 : i64 to index
    llvm.br ^bb1(%104 : i64)
  ^bb18:  // pred: ^bb1
    llvm.return %49 : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
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

