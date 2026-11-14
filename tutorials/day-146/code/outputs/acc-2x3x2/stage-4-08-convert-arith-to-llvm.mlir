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
    %29 = llvm.mlir.constant(2 : index) : i64
    %30 = llvm.mlir.constant(6 : index) : i64
    %31 = llvm.mlir.constant(3 : index) : i64
    %32 = llvm.mlir.constant(4 : index) : i64
    %33 = llvm.mlir.constant(1 : index) : i64
    %34 = llvm.mlir.constant(0 : index) : i64
    %35 = builtin.unrealized_conversion_cast %34 : i64 to index
    %36 = builtin.unrealized_conversion_cast %35 : index to i64
    %37 = llvm.mlir.constant(4 : index) : i64
    %38 = llvm.mlir.constant(3 : index) : i64
    %39 = llvm.mlir.constant(1 : index) : i64
    %40 = llvm.mlir.constant(12 : index) : i64
    %41 = llvm.mlir.zero : !llvm.ptr
    %42 = llvm.getelementptr %41[%40] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %43 = llvm.ptrtoint %42 : !llvm.ptr to i64
    %44 = llvm.call @malloc(%43) : (i64) -> !llvm.ptr
    %45 = llvm.mlir.poison : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
    %46 = llvm.insertvalue %44, %45[0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %47 = llvm.insertvalue %44, %46[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %48 = llvm.mlir.constant(0 : index) : i64
    %49 = llvm.insertvalue %48, %47[2] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %50 = llvm.insertvalue %37, %49[3, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %51 = llvm.insertvalue %38, %50[3, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %52 = llvm.insertvalue %38, %51[4, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %53 = llvm.insertvalue %39, %52[4, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %54 = builtin.unrealized_conversion_cast %53 : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> to memref<4x3xf32>
    llvm.br ^bb1(%36 : i64)
  ^bb1(%55: i64):  // 2 preds: ^bb0, ^bb14
    %56 = builtin.unrealized_conversion_cast %55 : i64 to index
    %57 = llvm.icmp "slt" %55, %32 : i64
    llvm.cond_br %57, ^bb2, ^bb15
  ^bb2:  // pred: ^bb1
    llvm.br ^bb3(%36 : i64)
  ^bb3(%58: i64):  // 2 preds: ^bb2, ^bb13
    %59 = builtin.unrealized_conversion_cast %58 : i64 to index
    %60 = llvm.icmp "slt" %58, %30 : i64
    llvm.cond_br %60, ^bb4, ^bb14
  ^bb4:  // pred: ^bb3
    llvm.br ^bb5(%55 : i64)
  ^bb5(%61: i64):  // 2 preds: ^bb4, ^bb12
    %62 = builtin.unrealized_conversion_cast %61 : i64 to index
    %63 = builtin.unrealized_conversion_cast %62 : index to i64
    %64 = llvm.icmp "slt" %61, %32 : i64
    llvm.cond_br %64, ^bb6, ^bb13
  ^bb6:  // pred: ^bb5
    llvm.br ^bb7(%36 : i64)
  ^bb7(%65: i64):  // 2 preds: ^bb6, ^bb11
    %66 = builtin.unrealized_conversion_cast %65 : i64 to index
    %67 = builtin.unrealized_conversion_cast %66 : index to i64
    %68 = llvm.icmp "slt" %65, %31 : i64
    llvm.cond_br %68, ^bb8, ^bb12
  ^bb8:  // pred: ^bb7
    %69 = llvm.extractvalue %27[1] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %70 = llvm.getelementptr inbounds|nuw %69[%67] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %71 = llvm.load %70 : !llvm.ptr -> f32
    llvm.br ^bb9(%36, %71 : i64, f32)
  ^bb9(%72: i64, %73: f32):  // 2 preds: ^bb8, ^bb10
    %74 = builtin.unrealized_conversion_cast %72 : i64 to index
    %75 = builtin.unrealized_conversion_cast %74 : index to i64
    %76 = llvm.icmp "slt" %72, %30 : i64
    llvm.cond_br %76, ^bb10, ^bb11
  ^bb10:  // pred: ^bb9
    %77 = llvm.extractvalue %26[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %78 = llvm.mlir.constant(6 : index) : i64
    %79 = llvm.mul %63, %78 overflow<nsw, nuw> : i64
    %80 = llvm.add %79, %75 overflow<nsw, nuw> : i64
    %81 = llvm.getelementptr inbounds|nuw %77[%80] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %82 = llvm.load %81 : !llvm.ptr -> f32
    %83 = llvm.extractvalue %25[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %84 = llvm.mlir.constant(3 : index) : i64
    %85 = llvm.mul %75, %84 overflow<nsw, nuw> : i64
    %86 = llvm.add %85, %67 overflow<nsw, nuw> : i64
    %87 = llvm.getelementptr inbounds|nuw %83[%86] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %88 = llvm.load %87 : !llvm.ptr -> f32
    %89 = llvm.fmul %82, %88 : f32
    %90 = llvm.fadd %73, %89 : f32
    %91 = llvm.add %72, %33 : i64
    %92 = builtin.unrealized_conversion_cast %91 : i64 to index
    %93 = builtin.unrealized_conversion_cast %92 : index to i64
    llvm.br ^bb9(%93, %90 : i64, f32)
  ^bb11:  // pred: ^bb9
    %94 = llvm.fcmp "ogt" %73, %28 : f32
    %95 = llvm.select %94, %73, %28 : i1, f32
    %96 = llvm.extractvalue %53[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %97 = llvm.mlir.constant(3 : index) : i64
    %98 = llvm.mul %63, %97 overflow<nsw, nuw> : i64
    %99 = llvm.add %98, %67 overflow<nsw, nuw> : i64
    %100 = llvm.getelementptr inbounds|nuw %96[%99] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    llvm.store %95, %100 : f32, !llvm.ptr
    %101 = llvm.add %65, %33 : i64
    %102 = builtin.unrealized_conversion_cast %101 : i64 to index
    %103 = builtin.unrealized_conversion_cast %102 : index to i64
    llvm.br ^bb7(%103 : i64)
  ^bb12:  // pred: ^bb7
    %104 = llvm.add %61, %33 : i64
    %105 = builtin.unrealized_conversion_cast %104 : i64 to index
    %106 = builtin.unrealized_conversion_cast %105 : index to i64
    llvm.br ^bb5(%106 : i64)
  ^bb13:  // pred: ^bb5
    %107 = llvm.add %58, %29 : i64
    %108 = builtin.unrealized_conversion_cast %107 : i64 to index
    %109 = builtin.unrealized_conversion_cast %108 : index to i64
    llvm.br ^bb3(%109 : i64)
  ^bb14:  // pred: ^bb3
    %110 = llvm.add %55, %29 : i64
    %111 = builtin.unrealized_conversion_cast %110 : i64 to index
    %112 = builtin.unrealized_conversion_cast %111 : index to i64
    llvm.br ^bb1(%112 : i64)
  ^bb15:  // pred: ^bb1
    llvm.return %53 : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
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

