module {
  llvm.func @malloc(i64) -> !llvm.ptr
  llvm.func @gemm(%arg0: !llvm.ptr, %arg1: !llvm.ptr, %arg2: i64, %arg3: i64, %arg4: i64, %arg5: i64, %arg6: i64, %arg7: !llvm.ptr, %arg8: !llvm.ptr, %arg9: i64, %arg10: i64, %arg11: i64, %arg12: i64, %arg13: i64) -> !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> {
    %0 = llvm.mlir.undef : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
    %1 = llvm.insertvalue %arg0, %0[0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %2 = llvm.insertvalue %arg1, %1[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %3 = llvm.insertvalue %arg2, %2[2] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %4 = llvm.insertvalue %arg3, %3[3, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %5 = llvm.insertvalue %arg5, %4[4, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %6 = llvm.insertvalue %arg4, %5[3, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %7 = llvm.insertvalue %arg6, %6[4, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %8 = builtin.unrealized_conversion_cast %7 : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> to memref<4x6xf32, strided<[6, 1]>>
    %9 = llvm.mlir.undef : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
    %10 = llvm.insertvalue %arg7, %9[0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %11 = llvm.insertvalue %arg8, %10[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %12 = llvm.insertvalue %arg9, %11[2] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %13 = llvm.insertvalue %arg10, %12[3, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %14 = llvm.insertvalue %arg12, %13[4, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %15 = llvm.insertvalue %arg11, %14[3, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %16 = llvm.insertvalue %arg13, %15[4, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %17 = builtin.unrealized_conversion_cast %16 : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> to memref<6x3xf32, strided<[3, 1]>>
    %18 = llvm.mlir.constant(6 : index) : i64
    %19 = llvm.mlir.constant(3 : index) : i64
    %20 = llvm.mlir.constant(4 : index) : i64
    %21 = llvm.mlir.constant(1 : index) : i64
    %22 = llvm.mlir.constant(0 : index) : i64
    %23 = llvm.mlir.constant(0.000000e+00 : f32) : f32
    %24 = llvm.mlir.constant(4 : index) : i64
    %25 = llvm.mlir.constant(3 : index) : i64
    %26 = llvm.mlir.constant(1 : index) : i64
    %27 = llvm.mlir.constant(12 : index) : i64
    %28 = llvm.mlir.zero : !llvm.ptr
    %29 = llvm.getelementptr %28[%27] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %30 = llvm.ptrtoint %29 : !llvm.ptr to i64
    %31 = llvm.call @malloc(%30) : (i64) -> !llvm.ptr
    %32 = llvm.mlir.undef : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
    %33 = llvm.insertvalue %31, %32[0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %34 = llvm.insertvalue %31, %33[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %35 = llvm.mlir.constant(0 : index) : i64
    %36 = llvm.insertvalue %35, %34[2] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %37 = llvm.insertvalue %24, %36[3, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %38 = llvm.insertvalue %25, %37[3, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %39 = llvm.insertvalue %25, %38[4, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %40 = llvm.insertvalue %26, %39[4, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %41 = builtin.unrealized_conversion_cast %40 : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> to memref<4x3xf32>
    llvm.br ^bb1(%22 : i64)
  ^bb1(%42: i64):  // 2 preds: ^bb0, ^bb8
    %43 = builtin.unrealized_conversion_cast %42 : i64 to index
    %44 = llvm.icmp "slt" %42, %20 : i64
    llvm.cond_br %44, ^bb2, ^bb9
  ^bb2:  // pred: ^bb1
    llvm.br ^bb3(%22 : i64)
  ^bb3(%45: i64):  // 2 preds: ^bb2, ^bb7
    %46 = builtin.unrealized_conversion_cast %45 : i64 to index
    %47 = llvm.icmp "slt" %45, %19 : i64
    llvm.cond_br %47, ^bb4, ^bb8
  ^bb4:  // pred: ^bb3
    llvm.br ^bb5(%22, %23 : i64, f32)
  ^bb5(%48: i64, %49: f32):  // 2 preds: ^bb4, ^bb6
    %50 = builtin.unrealized_conversion_cast %48 : i64 to index
    %51 = llvm.icmp "slt" %48, %18 : i64
    llvm.cond_br %51, ^bb6, ^bb7
  ^bb6:  // pred: ^bb5
    %52 = llvm.extractvalue %7[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %53 = llvm.mlir.constant(6 : index) : i64
    %54 = llvm.mul %42, %53  : i64
    %55 = llvm.add %54, %48  : i64
    %56 = llvm.getelementptr %52[%55] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %57 = llvm.load %56 : !llvm.ptr -> f32
    %58 = llvm.extractvalue %16[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %59 = llvm.mlir.constant(3 : index) : i64
    %60 = llvm.mul %48, %59  : i64
    %61 = llvm.add %60, %45  : i64
    %62 = llvm.getelementptr %58[%61] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %63 = llvm.load %62 : !llvm.ptr -> f32
    %64 = llvm.fmul %57, %63  : f32
    %65 = llvm.fadd %49, %64  : f32
    %66 = llvm.add %48, %21  : i64
    llvm.br ^bb5(%66, %65 : i64, f32)
  ^bb7:  // pred: ^bb5
    %67 = llvm.extractvalue %40[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %68 = llvm.mlir.constant(3 : index) : i64
    %69 = llvm.mul %42, %68  : i64
    %70 = llvm.add %69, %45  : i64
    %71 = llvm.getelementptr %67[%70] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    llvm.store %49, %71 : f32, !llvm.ptr
    %72 = llvm.add %45, %21  : i64
    llvm.br ^bb3(%72 : i64)
  ^bb8:  // pred: ^bb3
    %73 = llvm.add %42, %21  : i64
    llvm.br ^bb1(%73 : i64)
  ^bb9:  // pred: ^bb1
    llvm.return %40 : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
  }
}

