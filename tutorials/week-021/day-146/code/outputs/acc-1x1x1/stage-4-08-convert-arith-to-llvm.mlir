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
    %29 = llvm.mlir.constant(6 : index) : i64
    %30 = llvm.mlir.constant(3 : index) : i64
    %31 = llvm.mlir.constant(4 : index) : i64
    %32 = llvm.mlir.constant(1 : index) : i64
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
  ^bb1(%54: i64):  // 2 preds: ^bb0, ^bb17
    %55 = builtin.unrealized_conversion_cast %54 : i64 to index
    %56 = llvm.icmp "slt" %54, %31 : i64
    llvm.cond_br %56, ^bb2, ^bb18
  ^bb2:  // pred: ^bb1
    llvm.br ^bb3(%35 : i64)
  ^bb3(%57: i64):  // 2 preds: ^bb2, ^bb16
    %58 = builtin.unrealized_conversion_cast %57 : i64 to index
    %59 = llvm.icmp "slt" %57, %30 : i64
    llvm.cond_br %59, ^bb4, ^bb17
  ^bb4:  // pred: ^bb3
    llvm.br ^bb5(%35 : i64)
  ^bb5(%60: i64):  // 2 preds: ^bb4, ^bb15
    %61 = builtin.unrealized_conversion_cast %60 : i64 to index
    %62 = llvm.icmp "slt" %60, %29 : i64
    llvm.cond_br %62, ^bb6, ^bb16
  ^bb6:  // pred: ^bb5
    llvm.br ^bb7(%54 : i64)
  ^bb7(%63: i64):  // 2 preds: ^bb6, ^bb14
    %64 = builtin.unrealized_conversion_cast %63 : i64 to index
    %65 = builtin.unrealized_conversion_cast %64 : index to i64
    %66 = llvm.icmp "slt" %63, %31 : i64
    llvm.cond_br %66, ^bb8, ^bb15
  ^bb8:  // pred: ^bb7
    llvm.br ^bb9(%57 : i64)
  ^bb9(%67: i64):  // 2 preds: ^bb8, ^bb13
    %68 = builtin.unrealized_conversion_cast %67 : i64 to index
    %69 = builtin.unrealized_conversion_cast %68 : index to i64
    %70 = llvm.icmp "slt" %67, %30 : i64
    llvm.cond_br %70, ^bb10, ^bb14
  ^bb10:  // pred: ^bb9
    %71 = llvm.extractvalue %27[1] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %72 = llvm.getelementptr inbounds|nuw %71[%69] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %73 = llvm.load %72 : !llvm.ptr -> f32
    llvm.br ^bb11(%35, %73 : i64, f32)
  ^bb11(%74: i64, %75: f32):  // 2 preds: ^bb10, ^bb12
    %76 = builtin.unrealized_conversion_cast %74 : i64 to index
    %77 = builtin.unrealized_conversion_cast %76 : index to i64
    %78 = llvm.icmp "slt" %74, %29 : i64
    llvm.cond_br %78, ^bb12, ^bb13
  ^bb12:  // pred: ^bb11
    %79 = llvm.extractvalue %26[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %80 = llvm.mlir.constant(6 : index) : i64
    %81 = llvm.mul %65, %80 overflow<nsw, nuw> : i64
    %82 = llvm.add %81, %77 overflow<nsw, nuw> : i64
    %83 = llvm.getelementptr inbounds|nuw %79[%82] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %84 = llvm.load %83 : !llvm.ptr -> f32
    %85 = llvm.extractvalue %25[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %86 = llvm.mlir.constant(3 : index) : i64
    %87 = llvm.mul %77, %86 overflow<nsw, nuw> : i64
    %88 = llvm.add %87, %69 overflow<nsw, nuw> : i64
    %89 = llvm.getelementptr inbounds|nuw %85[%88] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %90 = llvm.load %89 : !llvm.ptr -> f32
    %91 = llvm.fmul %84, %90 : f32
    %92 = llvm.fadd %75, %91 : f32
    %93 = llvm.add %74, %32 : i64
    %94 = builtin.unrealized_conversion_cast %93 : i64 to index
    %95 = builtin.unrealized_conversion_cast %94 : index to i64
    llvm.br ^bb11(%95, %92 : i64, f32)
  ^bb13:  // pred: ^bb11
    %96 = llvm.fcmp "ogt" %75, %28 : f32
    %97 = llvm.select %96, %75, %28 : i1, f32
    %98 = llvm.extractvalue %52[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %99 = llvm.mlir.constant(3 : index) : i64
    %100 = llvm.mul %65, %99 overflow<nsw, nuw> : i64
    %101 = llvm.add %100, %69 overflow<nsw, nuw> : i64
    %102 = llvm.getelementptr inbounds|nuw %98[%101] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    llvm.store %97, %102 : f32, !llvm.ptr
    %103 = llvm.add %67, %32 : i64
    %104 = builtin.unrealized_conversion_cast %103 : i64 to index
    %105 = builtin.unrealized_conversion_cast %104 : index to i64
    llvm.br ^bb9(%105 : i64)
  ^bb14:  // pred: ^bb9
    %106 = llvm.add %63, %32 : i64
    %107 = builtin.unrealized_conversion_cast %106 : i64 to index
    %108 = builtin.unrealized_conversion_cast %107 : index to i64
    llvm.br ^bb7(%108 : i64)
  ^bb15:  // pred: ^bb7
    %109 = llvm.add %60, %32 : i64
    %110 = builtin.unrealized_conversion_cast %109 : i64 to index
    %111 = builtin.unrealized_conversion_cast %110 : index to i64
    llvm.br ^bb5(%111 : i64)
  ^bb16:  // pred: ^bb5
    %112 = llvm.add %57, %32 : i64
    %113 = builtin.unrealized_conversion_cast %112 : i64 to index
    %114 = builtin.unrealized_conversion_cast %113 : index to i64
    llvm.br ^bb3(%114 : i64)
  ^bb17:  // pred: ^bb3
    %115 = llvm.add %54, %32 : i64
    %116 = builtin.unrealized_conversion_cast %115 : i64 to index
    %117 = builtin.unrealized_conversion_cast %116 : index to i64
    llvm.br ^bb1(%117 : i64)
  ^bb18:  // pred: ^bb1
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

