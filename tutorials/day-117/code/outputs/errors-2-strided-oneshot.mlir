module {
  llvm.func @gemm(%arg0: !llvm.ptr, %arg1: !llvm.ptr, %arg2: i64, %arg3: i64, %arg4: i64, %arg5: i64, %arg6: i64, %arg7: !llvm.ptr, %arg8: !llvm.ptr, %arg9: i64, %arg10: i64, %arg11: i64, %arg12: i64, %arg13: i64) -> !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> {
    %0 = llvm.mlir.undef : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
    %1 = llvm.insertvalue %arg0, %0[0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %2 = llvm.insertvalue %arg1, %1[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %3 = llvm.insertvalue %arg2, %2[2] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %4 = llvm.insertvalue %arg3, %3[3, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %5 = llvm.insertvalue %arg5, %4[4, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %6 = llvm.insertvalue %arg4, %5[3, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %7 = llvm.insertvalue %arg6, %6[4, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %8 = llvm.mlir.undef : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
    %9 = llvm.insertvalue %arg7, %8[0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %10 = llvm.insertvalue %arg8, %9[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %11 = llvm.insertvalue %arg9, %10[2] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %12 = llvm.insertvalue %arg10, %11[3, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %13 = llvm.insertvalue %arg12, %12[4, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %14 = llvm.insertvalue %arg11, %13[3, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %15 = llvm.insertvalue %arg13, %14[4, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %alloc = memref.alloc() : memref<4x3xf32, strided<[3, 1]>>
    %16 = builtin.unrealized_conversion_cast %alloc : memref<4x3xf32, strided<[3, 1]>> to !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
    %17 = llvm.mlir.constant(0.000000e+00 : f32) : f32
    %18 = llvm.mlir.constant(0 : index) : i64
    %19 = llvm.mlir.constant(1 : index) : i64
    %20 = llvm.mlir.constant(4 : index) : i64
    %21 = llvm.mlir.constant(3 : index) : i64
    %22 = llvm.mlir.constant(6 : index) : i64
    llvm.br ^bb1(%18 : i64)
  ^bb1(%23: i64):  // 2 preds: ^bb0, ^bb8
    %24 = llvm.icmp "slt" %23, %20 : i64
    llvm.cond_br %24, ^bb2, ^bb9
  ^bb2:  // pred: ^bb1
    llvm.br ^bb3(%18 : i64)
  ^bb3(%25: i64):  // 2 preds: ^bb2, ^bb7
    %26 = llvm.icmp "slt" %25, %21 : i64
    llvm.cond_br %26, ^bb4, ^bb8
  ^bb4:  // pred: ^bb3
    llvm.br ^bb5(%18, %17 : i64, f32)
  ^bb5(%27: i64, %28: f32):  // 2 preds: ^bb4, ^bb6
    %29 = llvm.icmp "slt" %27, %22 : i64
    llvm.cond_br %29, ^bb6, ^bb7
  ^bb6:  // pred: ^bb5
    %30 = llvm.extractvalue %7[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %31 = llvm.mlir.constant(6 : index) : i64
    %32 = llvm.mul %23, %31  : i64
    %33 = llvm.add %32, %27  : i64
    %34 = llvm.getelementptr %30[%33] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %35 = llvm.load %34 : !llvm.ptr -> f32
    %36 = llvm.extractvalue %15[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %37 = llvm.mlir.constant(3 : index) : i64
    %38 = llvm.mul %27, %37  : i64
    %39 = llvm.add %38, %25  : i64
    %40 = llvm.getelementptr %36[%39] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %41 = llvm.load %40 : !llvm.ptr -> f32
    %42 = llvm.fmul %35, %41  : f32
    %43 = llvm.fadd %28, %42  : f32
    %44 = llvm.add %27, %19  : i64
    llvm.br ^bb5(%44, %43 : i64, f32)
  ^bb7:  // pred: ^bb5
    %45 = llvm.extractvalue %16[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %46 = llvm.mlir.constant(3 : index) : i64
    %47 = llvm.mul %23, %46  : i64
    %48 = llvm.add %47, %25  : i64
    %49 = llvm.getelementptr %45[%48] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    llvm.store %28, %49 : f32, !llvm.ptr
    %50 = llvm.add %25, %19  : i64
    llvm.br ^bb3(%50 : i64)
  ^bb8:  // pred: ^bb3
    %51 = llvm.add %23, %19  : i64
    llvm.br ^bb1(%51 : i64)
  ^bb9:  // pred: ^bb1
    llvm.return %16 : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
  }
}

