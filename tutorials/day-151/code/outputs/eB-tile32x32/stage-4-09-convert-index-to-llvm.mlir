module {
  llvm.func @malloc(i64) -> !llvm.ptr
  llvm.func @main_kernel(%arg0: !llvm.ptr, %arg1: !llvm.ptr, %arg2: i64, %arg3: i64, %arg4: i64, %arg5: i64, %arg6: i64, %arg7: !llvm.ptr, %arg8: !llvm.ptr, %arg9: i64, %arg10: i64, %arg11: i64, %arg12: i64, %arg13: i64, %arg14: !llvm.ptr, %arg15: !llvm.ptr, %arg16: i64, %arg17: i64, %arg18: i64) -> !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> attributes {llvm.emit_c_interface} {
    %0 = llvm.mlir.poison : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)>
    %1 = llvm.insertvalue %arg14, %0[0] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %2 = llvm.insertvalue %arg15, %1[1] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %3 = llvm.insertvalue %arg16, %2[2] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %4 = llvm.insertvalue %arg17, %3[3, 0] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %5 = llvm.insertvalue %arg18, %4[4, 0] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %6 = builtin.unrealized_conversion_cast %5 : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> to memref<160xf32, strided<[1]>>
    %7 = llvm.mlir.poison : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
    %8 = llvm.insertvalue %arg7, %7[0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %9 = llvm.insertvalue %arg8, %8[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %10 = llvm.insertvalue %arg9, %9[2] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %11 = llvm.insertvalue %arg10, %10[3, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %12 = llvm.insertvalue %arg12, %11[4, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %13 = llvm.insertvalue %arg11, %12[3, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %14 = llvm.insertvalue %arg13, %13[4, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %15 = builtin.unrealized_conversion_cast %14 : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> to memref<160x160xf32, strided<[160, 1]>>
    %16 = llvm.mlir.poison : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
    %17 = llvm.insertvalue %arg0, %16[0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %18 = llvm.insertvalue %arg1, %17[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %19 = llvm.insertvalue %arg2, %18[2] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %20 = llvm.insertvalue %arg3, %19[3, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %21 = llvm.insertvalue %arg5, %20[4, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %22 = llvm.insertvalue %arg4, %21[3, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %23 = llvm.insertvalue %arg6, %22[4, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %24 = builtin.unrealized_conversion_cast %23 : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> to memref<160x160xf32, strided<[160, 1]>>
    %25 = llvm.mlir.constant(0.000000e+00 : f32) : f32
    %26 = llvm.mlir.constant(32 : index) : i64
    %27 = llvm.mlir.constant(160 : index) : i64
    %28 = llvm.mlir.constant(1 : index) : i64
    %29 = llvm.mlir.constant(0 : index) : i64
    %30 = builtin.unrealized_conversion_cast %29 : i64 to index
    %31 = llvm.mlir.constant(160 : index) : i64
    %32 = llvm.mlir.constant(160 : index) : i64
    %33 = llvm.mlir.constant(1 : index) : i64
    %34 = llvm.mlir.constant(25600 : index) : i64
    %35 = llvm.mlir.zero : !llvm.ptr
    %36 = llvm.getelementptr %35[%34] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %37 = llvm.ptrtoint %36 : !llvm.ptr to i64
    %38 = llvm.call @malloc(%37) : (i64) -> !llvm.ptr
    %39 = llvm.mlir.poison : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
    %40 = llvm.insertvalue %38, %39[0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %41 = llvm.insertvalue %38, %40[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %42 = llvm.mlir.constant(0 : index) : i64
    %43 = llvm.insertvalue %42, %41[2] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %44 = llvm.insertvalue %31, %43[3, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %45 = llvm.insertvalue %32, %44[3, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %46 = llvm.insertvalue %32, %45[4, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %47 = llvm.insertvalue %33, %46[4, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %48 = builtin.unrealized_conversion_cast %47 : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> to memref<160x160xf32>
    llvm.br ^bb1(%29 : i64)
  ^bb1(%49: i64):  // 2 preds: ^bb0, ^bb14
    %50 = builtin.unrealized_conversion_cast %49 : i64 to index
    %51 = llvm.icmp "slt" %49, %27 : i64
    llvm.cond_br %51, ^bb2, ^bb15
  ^bb2:  // pred: ^bb1
    llvm.br ^bb3(%29 : i64)
  ^bb3(%52: i64):  // 2 preds: ^bb2, ^bb13
    %53 = builtin.unrealized_conversion_cast %52 : i64 to index
    %54 = llvm.icmp "slt" %52, %27 : i64
    llvm.cond_br %54, ^bb4, ^bb14
  ^bb4:  // pred: ^bb3
    llvm.br ^bb5(%49 : i64)
  ^bb5(%55: i64):  // 2 preds: ^bb4, ^bb12
    %56 = builtin.unrealized_conversion_cast %55 : i64 to index
    %57 = llvm.icmp "slt" %55, %27 : i64
    llvm.cond_br %57, ^bb6, ^bb13
  ^bb6:  // pred: ^bb5
    llvm.br ^bb7(%52 : i64)
  ^bb7(%58: i64):  // 2 preds: ^bb6, ^bb11
    %59 = builtin.unrealized_conversion_cast %58 : i64 to index
    %60 = llvm.icmp "slt" %58, %27 : i64
    llvm.cond_br %60, ^bb8, ^bb12
  ^bb8:  // pred: ^bb7
    %61 = llvm.extractvalue %5[1] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %62 = llvm.getelementptr inbounds|nuw %61[%58] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %63 = llvm.load %62 : !llvm.ptr -> f32
    llvm.br ^bb9(%29, %63 : i64, f32)
  ^bb9(%64: i64, %65: f32):  // 2 preds: ^bb8, ^bb10
    %66 = builtin.unrealized_conversion_cast %64 : i64 to index
    %67 = llvm.icmp "slt" %64, %27 : i64
    llvm.cond_br %67, ^bb10, ^bb11
  ^bb10:  // pred: ^bb9
    %68 = llvm.extractvalue %23[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %69 = llvm.mlir.constant(160 : index) : i64
    %70 = llvm.mul %55, %69 overflow<nsw, nuw> : i64
    %71 = llvm.add %70, %64 overflow<nsw, nuw> : i64
    %72 = llvm.getelementptr inbounds|nuw %68[%71] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %73 = llvm.load %72 : !llvm.ptr -> f32
    %74 = llvm.extractvalue %14[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %75 = llvm.mlir.constant(160 : index) : i64
    %76 = llvm.mul %64, %75 overflow<nsw, nuw> : i64
    %77 = llvm.add %76, %58 overflow<nsw, nuw> : i64
    %78 = llvm.getelementptr inbounds|nuw %74[%77] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %79 = llvm.load %78 : !llvm.ptr -> f32
    %80 = llvm.fmul %73, %79 : f32
    %81 = llvm.fadd %65, %80 : f32
    %82 = llvm.add %64, %28 : i64
    %83 = builtin.unrealized_conversion_cast %82 : i64 to index
    llvm.br ^bb9(%82, %81 : i64, f32)
  ^bb11:  // pred: ^bb9
    %84 = llvm.fcmp "ogt" %65, %25 : f32
    %85 = llvm.select %84, %65, %25 : i1, f32
    %86 = llvm.extractvalue %47[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %87 = llvm.mlir.constant(160 : index) : i64
    %88 = llvm.mul %55, %87 overflow<nsw, nuw> : i64
    %89 = llvm.add %88, %58 overflow<nsw, nuw> : i64
    %90 = llvm.getelementptr inbounds|nuw %86[%89] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    llvm.store %85, %90 : f32, !llvm.ptr
    %91 = llvm.add %58, %28 : i64
    %92 = builtin.unrealized_conversion_cast %91 : i64 to index
    llvm.br ^bb7(%91 : i64)
  ^bb12:  // pred: ^bb7
    %93 = llvm.add %55, %28 : i64
    %94 = builtin.unrealized_conversion_cast %93 : i64 to index
    llvm.br ^bb5(%93 : i64)
  ^bb13:  // pred: ^bb5
    %95 = llvm.add %52, %26 : i64
    %96 = builtin.unrealized_conversion_cast %95 : i64 to index
    llvm.br ^bb3(%95 : i64)
  ^bb14:  // pred: ^bb3
    %97 = llvm.add %49, %26 : i64
    %98 = builtin.unrealized_conversion_cast %97 : i64 to index
    llvm.br ^bb1(%97 : i64)
  ^bb15:  // pred: ^bb1
    llvm.return %47 : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
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

