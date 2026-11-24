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
    %25 = builtin.unrealized_conversion_cast %15 : memref<160x160xf32, strided<[160, 1]>> to !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
    %26 = builtin.unrealized_conversion_cast %24 : memref<160x160xf32, strided<[160, 1]>> to !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
    %27 = builtin.unrealized_conversion_cast %6 : memref<160xf32, strided<[1]>> to !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)>
    %28 = llvm.mlir.constant(0.000000e+00 : f32) : f32
    %29 = llvm.mlir.constant(32 : index) : i64
    %30 = llvm.mlir.constant(160 : index) : i64
    %31 = llvm.mlir.constant(1 : index) : i64
    %32 = llvm.mlir.constant(0 : index) : i64
    %33 = builtin.unrealized_conversion_cast %32 : i64 to index
    %34 = builtin.unrealized_conversion_cast %33 : index to i64
    %35 = llvm.mlir.constant(160 : index) : i64
    %36 = llvm.mlir.constant(160 : index) : i64
    %37 = llvm.mlir.constant(1 : index) : i64
    %38 = llvm.mlir.constant(25600 : index) : i64
    %39 = llvm.mlir.zero : !llvm.ptr
    %40 = llvm.getelementptr %39[%38] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %41 = llvm.ptrtoint %40 : !llvm.ptr to i64
    %42 = llvm.call @malloc(%41) : (i64) -> !llvm.ptr
    %43 = llvm.mlir.poison : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
    %44 = llvm.insertvalue %42, %43[0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %45 = llvm.insertvalue %42, %44[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %46 = llvm.mlir.constant(0 : index) : i64
    %47 = llvm.insertvalue %46, %45[2] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %48 = llvm.insertvalue %35, %47[3, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %49 = llvm.insertvalue %36, %48[3, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %50 = llvm.insertvalue %36, %49[4, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %51 = llvm.insertvalue %37, %50[4, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %52 = builtin.unrealized_conversion_cast %51 : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> to memref<160x160xf32>
    llvm.br ^bb1(%34 : i64)
  ^bb1(%53: i64):  // 2 preds: ^bb0, ^bb14
    %54 = builtin.unrealized_conversion_cast %53 : i64 to index
    %55 = llvm.icmp "slt" %53, %30 : i64
    llvm.cond_br %55, ^bb2, ^bb15
  ^bb2:  // pred: ^bb1
    llvm.br ^bb3(%34 : i64)
  ^bb3(%56: i64):  // 2 preds: ^bb2, ^bb13
    %57 = builtin.unrealized_conversion_cast %56 : i64 to index
    %58 = llvm.icmp "slt" %56, %30 : i64
    llvm.cond_br %58, ^bb4, ^bb14
  ^bb4:  // pred: ^bb3
    llvm.br ^bb5(%53 : i64)
  ^bb5(%59: i64):  // 2 preds: ^bb4, ^bb12
    %60 = builtin.unrealized_conversion_cast %59 : i64 to index
    %61 = builtin.unrealized_conversion_cast %60 : index to i64
    %62 = llvm.icmp "slt" %59, %30 : i64
    llvm.cond_br %62, ^bb6, ^bb13
  ^bb6:  // pred: ^bb5
    llvm.br ^bb7(%56 : i64)
  ^bb7(%63: i64):  // 2 preds: ^bb6, ^bb11
    %64 = builtin.unrealized_conversion_cast %63 : i64 to index
    %65 = builtin.unrealized_conversion_cast %64 : index to i64
    %66 = llvm.icmp "slt" %63, %30 : i64
    llvm.cond_br %66, ^bb8, ^bb12
  ^bb8:  // pred: ^bb7
    %67 = llvm.extractvalue %27[1] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %68 = llvm.getelementptr inbounds|nuw %67[%65] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %69 = llvm.load %68 : !llvm.ptr -> f32
    llvm.br ^bb9(%34, %69 : i64, f32)
  ^bb9(%70: i64, %71: f32):  // 2 preds: ^bb8, ^bb10
    %72 = builtin.unrealized_conversion_cast %70 : i64 to index
    %73 = builtin.unrealized_conversion_cast %72 : index to i64
    %74 = llvm.icmp "slt" %70, %30 : i64
    llvm.cond_br %74, ^bb10, ^bb11
  ^bb10:  // pred: ^bb9
    %75 = llvm.extractvalue %26[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %76 = llvm.mlir.constant(160 : index) : i64
    %77 = llvm.mul %61, %76 overflow<nsw, nuw> : i64
    %78 = llvm.add %77, %73 overflow<nsw, nuw> : i64
    %79 = llvm.getelementptr inbounds|nuw %75[%78] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %80 = llvm.load %79 : !llvm.ptr -> f32
    %81 = llvm.extractvalue %25[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %82 = llvm.mlir.constant(160 : index) : i64
    %83 = llvm.mul %73, %82 overflow<nsw, nuw> : i64
    %84 = llvm.add %83, %65 overflow<nsw, nuw> : i64
    %85 = llvm.getelementptr inbounds|nuw %81[%84] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %86 = llvm.load %85 : !llvm.ptr -> f32
    %87 = llvm.fmul %80, %86 : f32
    %88 = llvm.fadd %71, %87 : f32
    %89 = llvm.add %70, %31 : i64
    %90 = builtin.unrealized_conversion_cast %89 : i64 to index
    %91 = builtin.unrealized_conversion_cast %90 : index to i64
    llvm.br ^bb9(%91, %88 : i64, f32)
  ^bb11:  // pred: ^bb9
    %92 = llvm.fcmp "ogt" %71, %28 : f32
    %93 = llvm.select %92, %71, %28 : i1, f32
    %94 = llvm.extractvalue %51[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %95 = llvm.mlir.constant(160 : index) : i64
    %96 = llvm.mul %61, %95 overflow<nsw, nuw> : i64
    %97 = llvm.add %96, %65 overflow<nsw, nuw> : i64
    %98 = llvm.getelementptr inbounds|nuw %94[%97] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    llvm.store %93, %98 : f32, !llvm.ptr
    %99 = llvm.add %63, %31 : i64
    %100 = builtin.unrealized_conversion_cast %99 : i64 to index
    %101 = builtin.unrealized_conversion_cast %100 : index to i64
    llvm.br ^bb7(%101 : i64)
  ^bb12:  // pred: ^bb7
    %102 = llvm.add %59, %31 : i64
    %103 = builtin.unrealized_conversion_cast %102 : i64 to index
    %104 = builtin.unrealized_conversion_cast %103 : index to i64
    llvm.br ^bb5(%104 : i64)
  ^bb13:  // pred: ^bb5
    %105 = llvm.add %56, %29 : i64
    %106 = builtin.unrealized_conversion_cast %105 : i64 to index
    %107 = builtin.unrealized_conversion_cast %106 : index to i64
    llvm.br ^bb3(%107 : i64)
  ^bb14:  // pred: ^bb3
    %108 = llvm.add %53, %29 : i64
    %109 = builtin.unrealized_conversion_cast %108 : i64 to index
    %110 = builtin.unrealized_conversion_cast %109 : index to i64
    llvm.br ^bb1(%110 : i64)
  ^bb15:  // pred: ^bb1
    llvm.return %51 : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
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

