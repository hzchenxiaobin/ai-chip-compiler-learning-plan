module {
  llvm.func @malloc(i64) -> !llvm.ptr
  func.func @main_kernel(%arg0: memref<4x6xf32, strided<[6, 1]>>, %arg1: memref<6x3xf32, strided<[3, 1]>>, %arg2: memref<3xf32, strided<[1]>>) -> memref<4x3xf32> attributes {llvm.emit_c_interface} {
    %0 = builtin.unrealized_conversion_cast %arg1 : memref<6x3xf32, strided<[3, 1]>> to !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
    %1 = builtin.unrealized_conversion_cast %arg0 : memref<4x6xf32, strided<[6, 1]>> to !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
    %2 = builtin.unrealized_conversion_cast %arg2 : memref<3xf32, strided<[1]>> to !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)>
    %cst = arith.constant 0.000000e+00 : f32
    %c6 = arith.constant 6 : index
    %c3 = arith.constant 3 : index
    %c4 = arith.constant 4 : index
    %c1 = arith.constant 1 : index
    %c0 = arith.constant 0 : index
    %3 = llvm.mlir.constant(4 : index) : i64
    %4 = llvm.mlir.constant(3 : index) : i64
    %5 = llvm.mlir.constant(1 : index) : i64
    %6 = llvm.mlir.constant(12 : index) : i64
    %7 = llvm.mlir.zero : !llvm.ptr
    %8 = llvm.getelementptr %7[%6] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %9 = llvm.ptrtoint %8 : !llvm.ptr to i64
    %10 = llvm.call @malloc(%9) : (i64) -> !llvm.ptr
    %11 = llvm.mlir.poison : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
    %12 = llvm.insertvalue %10, %11[0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %13 = llvm.insertvalue %10, %12[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %14 = llvm.mlir.constant(0 : index) : i64
    %15 = llvm.insertvalue %14, %13[2] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %16 = llvm.insertvalue %3, %15[3, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %17 = llvm.insertvalue %4, %16[3, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %18 = llvm.insertvalue %4, %17[4, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %19 = llvm.insertvalue %5, %18[4, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %20 = builtin.unrealized_conversion_cast %19 : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> to memref<4x3xf32>
    cf.br ^bb1(%c0 : index)
  ^bb1(%21: index):  // 2 preds: ^bb0, ^bb11
    %22 = arith.cmpi slt, %21, %c6 : index
    cf.cond_br %22, ^bb2, ^bb12
  ^bb2:  // pred: ^bb1
    cf.br ^bb3(%c0 : index)
  ^bb3(%23: index):  // 2 preds: ^bb2, ^bb10
    %24 = builtin.unrealized_conversion_cast %23 : index to i64
    %25 = arith.cmpi slt, %23, %c4 : index
    cf.cond_br %25, ^bb4, ^bb11
  ^bb4:  // pred: ^bb3
    cf.br ^bb5(%c0 : index)
  ^bb5(%26: index):  // 2 preds: ^bb4, ^bb9
    %27 = builtin.unrealized_conversion_cast %26 : index to i64
    %28 = arith.cmpi slt, %26, %c3 : index
    cf.cond_br %28, ^bb6, ^bb10
  ^bb6:  // pred: ^bb5
    %29 = llvm.extractvalue %2[1] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %30 = llvm.getelementptr inbounds|nuw %29[%27] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %31 = llvm.load %30 : !llvm.ptr -> f32
    cf.br ^bb7(%c0, %31 : index, f32)
  ^bb7(%32: index, %33: f32):  // 2 preds: ^bb6, ^bb8
    %34 = builtin.unrealized_conversion_cast %32 : index to i64
    %35 = arith.cmpi slt, %32, %c6 : index
    cf.cond_br %35, ^bb8, ^bb9
  ^bb8:  // pred: ^bb7
    %36 = llvm.extractvalue %1[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %37 = llvm.mlir.constant(6 : index) : i64
    %38 = llvm.mul %24, %37 overflow<nsw, nuw> : i64
    %39 = llvm.add %38, %34 overflow<nsw, nuw> : i64
    %40 = llvm.getelementptr inbounds|nuw %36[%39] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %41 = llvm.load %40 : !llvm.ptr -> f32
    %42 = llvm.extractvalue %0[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %43 = llvm.mlir.constant(3 : index) : i64
    %44 = llvm.mul %34, %43 overflow<nsw, nuw> : i64
    %45 = llvm.add %44, %27 overflow<nsw, nuw> : i64
    %46 = llvm.getelementptr inbounds|nuw %42[%45] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %47 = llvm.load %46 : !llvm.ptr -> f32
    %48 = arith.mulf %41, %47 : f32
    %49 = arith.addf %33, %48 : f32
    %50 = arith.addi %32, %c1 : index
    cf.br ^bb7(%50, %49 : index, f32)
  ^bb9:  // pred: ^bb7
    %51 = arith.cmpf ogt, %33, %cst : f32
    %52 = arith.select %51, %33, %cst : f32
    %53 = llvm.extractvalue %19[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %54 = llvm.mlir.constant(3 : index) : i64
    %55 = llvm.mul %24, %54 overflow<nsw, nuw> : i64
    %56 = llvm.add %55, %27 overflow<nsw, nuw> : i64
    %57 = llvm.getelementptr inbounds|nuw %53[%56] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    llvm.store %52, %57 : f32, !llvm.ptr
    %58 = arith.addi %26, %c1 : index
    cf.br ^bb5(%58 : index)
  ^bb10:  // pred: ^bb5
    %59 = arith.addi %23, %c1 : index
    cf.br ^bb3(%59 : index)
  ^bb11:  // pred: ^bb3
    %60 = arith.addi %21, %c3 : index
    cf.br ^bb1(%60 : index)
  ^bb12:  // pred: ^bb1
    return %20 : memref<4x3xf32>
  }
}

