module {
  func.func @probe(%arg0: memref<2x2xf32, strided<[2, 1]>>) -> f32 {
    %0 = builtin.unrealized_conversion_cast %arg0 : memref<2x2xf32, strided<[2, 1]>> to !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
    %c0 = arith.constant 0 : index
    %1 = builtin.unrealized_conversion_cast %c0 : index to i64
    %c1 = arith.constant 1 : index
    %2 = builtin.unrealized_conversion_cast %c1 : index to i64
    %3 = llvm.extractvalue %0[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %4 = llvm.mlir.constant(2 : index) : i64
    %5 = llvm.mul %1, %4 overflow<nsw, nuw> : i64
    %6 = llvm.add %5, %1 overflow<nsw, nuw> : i64
    %7 = llvm.getelementptr inbounds|nuw %3[%6] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %8 = llvm.load %7 : !llvm.ptr -> f32
    %9 = llvm.extractvalue %0[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %10 = llvm.mlir.constant(2 : index) : i64
    %11 = llvm.mul %2, %10 overflow<nsw, nuw> : i64
    %12 = llvm.add %11, %2 overflow<nsw, nuw> : i64
    %13 = llvm.getelementptr inbounds|nuw %9[%12] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %14 = llvm.load %13 : !llvm.ptr -> f32
    %15 = arith.addf %8, %14 : f32
    return %15 : f32
  }
}

