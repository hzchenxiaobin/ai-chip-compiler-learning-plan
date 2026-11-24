module {
  llvm.func @probe(%arg0: !llvm.ptr, %arg1: !llvm.ptr, %arg2: i64, %arg3: i64, %arg4: i64, %arg5: i64, %arg6: i64) -> f32 {
    %0 = llvm.mlir.poison : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
    %1 = llvm.insertvalue %arg0, %0[0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %2 = llvm.insertvalue %arg1, %1[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %3 = llvm.insertvalue %arg2, %2[2] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %4 = llvm.insertvalue %arg3, %3[3, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %5 = llvm.insertvalue %arg5, %4[4, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %6 = llvm.insertvalue %arg4, %5[3, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %7 = llvm.insertvalue %arg6, %6[4, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %8 = builtin.unrealized_conversion_cast %7 : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> to memref<2x2xf32, strided<[2, 1]>>
    %9 = builtin.unrealized_conversion_cast %8 : memref<2x2xf32, strided<[2, 1]>> to !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
    %10 = llvm.mlir.constant(0 : index) : i64
    %11 = builtin.unrealized_conversion_cast %10 : i64 to index
    %12 = builtin.unrealized_conversion_cast %11 : index to i64
    %13 = llvm.mlir.constant(1 : index) : i64
    %14 = builtin.unrealized_conversion_cast %13 : i64 to index
    %15 = builtin.unrealized_conversion_cast %14 : index to i64
    %16 = llvm.extractvalue %9[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %17 = llvm.mlir.constant(2 : index) : i64
    %18 = llvm.mul %12, %17 overflow<nsw, nuw> : i64
    %19 = llvm.add %18, %12 overflow<nsw, nuw> : i64
    %20 = llvm.getelementptr inbounds|nuw %16[%19] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %21 = llvm.load %20 : !llvm.ptr -> f32
    %22 = llvm.extractvalue %9[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %23 = llvm.mlir.constant(2 : index) : i64
    %24 = llvm.mul %15, %23 overflow<nsw, nuw> : i64
    %25 = llvm.add %24, %15 overflow<nsw, nuw> : i64
    %26 = llvm.getelementptr inbounds|nuw %22[%25] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %27 = llvm.load %26 : !llvm.ptr -> f32
    %28 = llvm.fsub %21, %27 : f32
    llvm.return %28 : f32
  }
}

