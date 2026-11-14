module {
  llvm.func @malloc(i64) -> !llvm.ptr
  func.func @main_kernel(%arg0: memref<160x160xf32, strided<[160, 1]>>, %arg1: memref<160x160xf32, strided<[160, 1]>>, %arg2: memref<160xf32, strided<[1]>>) -> memref<160x160xf32> attributes {llvm.emit_c_interface} {
    %0 = builtin.unrealized_conversion_cast %arg1 : memref<160x160xf32, strided<[160, 1]>> to !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
    %1 = builtin.unrealized_conversion_cast %arg0 : memref<160x160xf32, strided<[160, 1]>> to !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
    %2 = builtin.unrealized_conversion_cast %arg2 : memref<160xf32, strided<[1]>> to !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)>
    %cst = arith.constant 0.000000e+00 : f32
    %c64 = arith.constant 64 : index
    %c160 = arith.constant 160 : index
    %c1 = arith.constant 1 : index
    %c0 = arith.constant 0 : index
    %3 = llvm.mlir.constant(160 : index) : i64
    %4 = llvm.mlir.constant(160 : index) : i64
    %5 = llvm.mlir.constant(1 : index) : i64
    %6 = llvm.mlir.constant(25600 : index) : i64
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
    %20 = builtin.unrealized_conversion_cast %19 : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> to memref<160x160xf32>
    cf.br ^bb1(%c0 : index)
  ^bb1(%21: index):  // 2 preds: ^bb0, ^bb14
    %22 = arith.cmpi slt, %21, %c160 : index
    cf.cond_br %22, ^bb2, ^bb15
  ^bb2:  // pred: ^bb1
    cf.br ^bb3(%c0 : index)
  ^bb3(%23: index):  // 2 preds: ^bb2, ^bb13
    %24 = arith.cmpi slt, %23, %c160 : index
    cf.cond_br %24, ^bb4, ^bb14
  ^bb4:  // pred: ^bb3
    cf.br ^bb5(%21 : index)
  ^bb5(%25: index):  // 2 preds: ^bb4, ^bb12
    %26 = builtin.unrealized_conversion_cast %25 : index to i64
    %27 = arith.cmpi slt, %25, %c160 : index
    cf.cond_br %27, ^bb6, ^bb13
  ^bb6:  // pred: ^bb5
    cf.br ^bb7(%23 : index)
  ^bb7(%28: index):  // 2 preds: ^bb6, ^bb11
    %29 = builtin.unrealized_conversion_cast %28 : index to i64
    %30 = arith.cmpi slt, %28, %c160 : index
    cf.cond_br %30, ^bb8, ^bb12
  ^bb8:  // pred: ^bb7
    %31 = llvm.extractvalue %2[1] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %32 = llvm.getelementptr inbounds|nuw %31[%29] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %33 = llvm.load %32 : !llvm.ptr -> f32
    cf.br ^bb9(%c0, %33 : index, f32)
  ^bb9(%34: index, %35: f32):  // 2 preds: ^bb8, ^bb10
    %36 = builtin.unrealized_conversion_cast %34 : index to i64
    %37 = arith.cmpi slt, %34, %c160 : index
    cf.cond_br %37, ^bb10, ^bb11
  ^bb10:  // pred: ^bb9
    %38 = llvm.extractvalue %1[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %39 = llvm.mlir.constant(160 : index) : i64
    %40 = llvm.mul %26, %39 overflow<nsw, nuw> : i64
    %41 = llvm.add %40, %36 overflow<nsw, nuw> : i64
    %42 = llvm.getelementptr inbounds|nuw %38[%41] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %43 = llvm.load %42 : !llvm.ptr -> f32
    %44 = llvm.extractvalue %0[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %45 = llvm.mlir.constant(160 : index) : i64
    %46 = llvm.mul %36, %45 overflow<nsw, nuw> : i64
    %47 = llvm.add %46, %29 overflow<nsw, nuw> : i64
    %48 = llvm.getelementptr inbounds|nuw %44[%47] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %49 = llvm.load %48 : !llvm.ptr -> f32
    %50 = arith.mulf %43, %49 : f32
    %51 = arith.addf %35, %50 : f32
    %52 = arith.addi %34, %c1 : index
    cf.br ^bb9(%52, %51 : index, f32)
  ^bb11:  // pred: ^bb9
    %53 = arith.cmpf ogt, %35, %cst : f32
    %54 = arith.select %53, %35, %cst : f32
    %55 = llvm.extractvalue %19[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %56 = llvm.mlir.constant(160 : index) : i64
    %57 = llvm.mul %26, %56 overflow<nsw, nuw> : i64
    %58 = llvm.add %57, %29 overflow<nsw, nuw> : i64
    %59 = llvm.getelementptr inbounds|nuw %55[%58] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    llvm.store %54, %59 : f32, !llvm.ptr
    %60 = arith.addi %28, %c1 : index
    cf.br ^bb7(%60 : index)
  ^bb12:  // pred: ^bb7
    %61 = arith.addi %25, %c1 : index
    cf.br ^bb5(%61 : index)
  ^bb13:  // pred: ^bb5
    %62 = arith.addi %23, %c64 : index
    cf.br ^bb3(%62 : index)
  ^bb14:  // pred: ^bb3
    %63 = arith.addi %21, %c64 : index
    cf.br ^bb1(%63 : index)
  ^bb15:  // pred: ^bb1
    return %20 : memref<160x160xf32>
  }
}

