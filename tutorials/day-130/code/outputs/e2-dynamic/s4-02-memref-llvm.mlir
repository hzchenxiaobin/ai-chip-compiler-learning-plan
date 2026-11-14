module {
  llvm.func @malloc(i64) -> !llvm.ptr
  func.func @kernel_dynamic(%arg0: memref<?x?xf32>, %arg1: memref<?x?xf32>) -> memref<?x?xf32> attributes {llvm.emit_c_interface} {
    %0 = builtin.unrealized_conversion_cast %arg1 : memref<?x?xf32> to !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
    %1 = builtin.unrealized_conversion_cast %arg0 : memref<?x?xf32> to !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
    %c0 = arith.constant 0 : index
    %c1 = arith.constant 1 : index
    %cst = arith.constant 0.000000e+00 : f32
    %2 = llvm.extractvalue %1[3, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %3 = builtin.unrealized_conversion_cast %2 : i64 to index
    %4 = llvm.extractvalue %1[3, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %5 = builtin.unrealized_conversion_cast %4 : i64 to index
    %6 = llvm.extractvalue %0[3, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %7 = builtin.unrealized_conversion_cast %6 : i64 to index
    %8 = llvm.mlir.constant(1 : index) : i64
    %9 = llvm.mul %6, %2 : i64
    %10 = llvm.mlir.zero : !llvm.ptr
    %11 = llvm.getelementptr %10[%9] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %12 = llvm.ptrtoint %11 : !llvm.ptr to i64
    %13 = llvm.call @malloc(%12) : (i64) -> !llvm.ptr
    %14 = llvm.mlir.poison : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
    %15 = llvm.insertvalue %13, %14[0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %16 = llvm.insertvalue %13, %15[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %17 = llvm.mlir.constant(0 : index) : i64
    %18 = llvm.insertvalue %17, %16[2] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %19 = llvm.insertvalue %2, %18[3, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %20 = llvm.insertvalue %6, %19[3, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %21 = llvm.insertvalue %6, %20[4, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %22 = llvm.insertvalue %8, %21[4, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %23 = builtin.unrealized_conversion_cast %22 : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> to memref<?x?xf32>
    cf.br ^bb1(%c0 : index)
  ^bb1(%24: index):  // 2 preds: ^bb0, ^bb8
    %25 = builtin.unrealized_conversion_cast %24 : index to i64
    %26 = arith.cmpi slt, %24, %3 : index
    cf.cond_br %26, ^bb2, ^bb9
  ^bb2:  // pred: ^bb1
    cf.br ^bb3(%c0 : index)
  ^bb3(%27: index):  // 2 preds: ^bb2, ^bb7
    %28 = builtin.unrealized_conversion_cast %27 : index to i64
    %29 = arith.cmpi slt, %27, %7 : index
    cf.cond_br %29, ^bb4, ^bb8
  ^bb4:  // pred: ^bb3
    cf.br ^bb5(%c0, %cst : index, f32)
  ^bb5(%30: index, %31: f32):  // 2 preds: ^bb4, ^bb6
    %32 = builtin.unrealized_conversion_cast %30 : index to i64
    %33 = arith.cmpi slt, %30, %5 : index
    cf.cond_br %33, ^bb6, ^bb7
  ^bb6:  // pred: ^bb5
    %34 = llvm.extractvalue %1[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %35 = llvm.extractvalue %1[4, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %36 = llvm.mul %25, %35 overflow<nsw> : i64
    %37 = llvm.add %36, %32 overflow<nsw> : i64
    %38 = llvm.getelementptr inbounds %34[%37] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %39 = llvm.load %38 : !llvm.ptr -> f32
    %40 = llvm.extractvalue %0[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %41 = llvm.extractvalue %0[4, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %42 = llvm.mul %32, %41 overflow<nsw> : i64
    %43 = llvm.add %42, %28 overflow<nsw> : i64
    %44 = llvm.getelementptr inbounds %40[%43] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %45 = llvm.load %44 : !llvm.ptr -> f32
    %46 = arith.mulf %39, %45 : f32
    %47 = arith.addf %31, %46 : f32
    %48 = arith.addi %30, %c1 : index
    cf.br ^bb5(%48, %47 : index, f32)
  ^bb7:  // pred: ^bb5
    %49 = llvm.extractvalue %22[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %50 = llvm.extractvalue %22[4, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %51 = llvm.mul %25, %50 overflow<nsw> : i64
    %52 = llvm.add %51, %28 overflow<nsw> : i64
    %53 = llvm.getelementptr inbounds %49[%52] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    llvm.store %31, %53 : f32, !llvm.ptr
    %54 = arith.addi %27, %c1 : index
    cf.br ^bb3(%54 : index)
  ^bb8:  // pred: ^bb3
    %55 = arith.addi %24, %c1 : index
    cf.br ^bb1(%55 : index)
  ^bb9:  // pred: ^bb1
    return %23 : memref<?x?xf32>
  }
}

