module {
  llvm.func @malloc(i64) -> !llvm.ptr
  llvm.func @kernel_dynamic(%arg0: !llvm.ptr, %arg1: !llvm.ptr, %arg2: i64, %arg3: i64, %arg4: i64, %arg5: i64, %arg6: i64, %arg7: !llvm.ptr, %arg8: !llvm.ptr, %arg9: i64, %arg10: i64, %arg11: i64, %arg12: i64, %arg13: i64) -> !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> attributes {llvm.emit_c_interface} {
    %0 = llvm.mlir.poison : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
    %1 = llvm.insertvalue %arg7, %0[0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %2 = llvm.insertvalue %arg8, %1[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %3 = llvm.insertvalue %arg9, %2[2] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %4 = llvm.insertvalue %arg10, %3[3, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %5 = llvm.insertvalue %arg12, %4[4, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %6 = llvm.insertvalue %arg11, %5[3, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %7 = llvm.insertvalue %arg13, %6[4, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %8 = builtin.unrealized_conversion_cast %7 : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> to memref<?x?xf32>
    %9 = llvm.mlir.poison : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
    %10 = llvm.insertvalue %arg0, %9[0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %11 = llvm.insertvalue %arg1, %10[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %12 = llvm.insertvalue %arg2, %11[2] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %13 = llvm.insertvalue %arg3, %12[3, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %14 = llvm.insertvalue %arg5, %13[4, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %15 = llvm.insertvalue %arg4, %14[3, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %16 = llvm.insertvalue %arg6, %15[4, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %17 = builtin.unrealized_conversion_cast %16 : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> to memref<?x?xf32>
    %18 = builtin.unrealized_conversion_cast %8 : memref<?x?xf32> to !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
    %19 = builtin.unrealized_conversion_cast %17 : memref<?x?xf32> to !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
    %20 = llvm.mlir.constant(0 : index) : i64
    %21 = builtin.unrealized_conversion_cast %20 : i64 to index
    %22 = builtin.unrealized_conversion_cast %21 : index to i64
    %23 = llvm.mlir.constant(1 : index) : i64
    %24 = llvm.mlir.constant(0.000000e+00 : f32) : f32
    %25 = llvm.extractvalue %19[3, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %26 = builtin.unrealized_conversion_cast %25 : i64 to index
    %27 = llvm.extractvalue %19[3, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %28 = builtin.unrealized_conversion_cast %27 : i64 to index
    %29 = llvm.extractvalue %18[3, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %30 = builtin.unrealized_conversion_cast %29 : i64 to index
    %31 = llvm.mlir.constant(1 : index) : i64
    %32 = llvm.mul %29, %25 : i64
    %33 = llvm.mlir.zero : !llvm.ptr
    %34 = llvm.getelementptr %33[%32] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %35 = llvm.ptrtoint %34 : !llvm.ptr to i64
    %36 = llvm.call @malloc(%35) : (i64) -> !llvm.ptr
    %37 = llvm.mlir.poison : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
    %38 = llvm.insertvalue %36, %37[0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %39 = llvm.insertvalue %36, %38[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %40 = llvm.mlir.constant(0 : index) : i64
    %41 = llvm.insertvalue %40, %39[2] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %42 = llvm.insertvalue %25, %41[3, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %43 = llvm.insertvalue %29, %42[3, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %44 = llvm.insertvalue %29, %43[4, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %45 = llvm.insertvalue %31, %44[4, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %46 = builtin.unrealized_conversion_cast %45 : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> to memref<?x?xf32>
    llvm.br ^bb1(%22 : i64)
  ^bb1(%47: i64):  // 2 preds: ^bb0, ^bb8
    %48 = builtin.unrealized_conversion_cast %47 : i64 to index
    %49 = builtin.unrealized_conversion_cast %48 : index to i64
    %50 = llvm.icmp "slt" %47, %25 : i64
    llvm.cond_br %50, ^bb2, ^bb9
  ^bb2:  // pred: ^bb1
    llvm.br ^bb3(%22 : i64)
  ^bb3(%51: i64):  // 2 preds: ^bb2, ^bb7
    %52 = builtin.unrealized_conversion_cast %51 : i64 to index
    %53 = builtin.unrealized_conversion_cast %52 : index to i64
    %54 = llvm.icmp "slt" %51, %29 : i64
    llvm.cond_br %54, ^bb4, ^bb8
  ^bb4:  // pred: ^bb3
    llvm.br ^bb5(%22, %24 : i64, f32)
  ^bb5(%55: i64, %56: f32):  // 2 preds: ^bb4, ^bb6
    %57 = builtin.unrealized_conversion_cast %55 : i64 to index
    %58 = builtin.unrealized_conversion_cast %57 : index to i64
    %59 = llvm.icmp "slt" %55, %27 : i64
    llvm.cond_br %59, ^bb6, ^bb7
  ^bb6:  // pred: ^bb5
    %60 = llvm.extractvalue %19[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %61 = llvm.extractvalue %19[4, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %62 = llvm.mul %49, %61 overflow<nsw> : i64
    %63 = llvm.add %62, %58 overflow<nsw> : i64
    %64 = llvm.getelementptr inbounds %60[%63] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %65 = llvm.load %64 : !llvm.ptr -> f32
    %66 = llvm.extractvalue %18[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %67 = llvm.extractvalue %18[4, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %68 = llvm.mul %58, %67 overflow<nsw> : i64
    %69 = llvm.add %68, %53 overflow<nsw> : i64
    %70 = llvm.getelementptr inbounds %66[%69] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %71 = llvm.load %70 : !llvm.ptr -> f32
    %72 = llvm.fmul %65, %71 : f32
    %73 = llvm.fadd %56, %72 : f32
    %74 = llvm.add %55, %23 : i64
    %75 = builtin.unrealized_conversion_cast %74 : i64 to index
    %76 = builtin.unrealized_conversion_cast %75 : index to i64
    llvm.br ^bb5(%76, %73 : i64, f32)
  ^bb7:  // pred: ^bb5
    %77 = llvm.extractvalue %45[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %78 = llvm.extractvalue %45[4, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %79 = llvm.mul %49, %78 overflow<nsw> : i64
    %80 = llvm.add %79, %53 overflow<nsw> : i64
    %81 = llvm.getelementptr inbounds %77[%80] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    llvm.store %56, %81 : f32, !llvm.ptr
    %82 = llvm.add %51, %23 : i64
    %83 = builtin.unrealized_conversion_cast %82 : i64 to index
    %84 = builtin.unrealized_conversion_cast %83 : index to i64
    llvm.br ^bb3(%84 : i64)
  ^bb8:  // pred: ^bb3
    %85 = llvm.add %47, %23 : i64
    %86 = builtin.unrealized_conversion_cast %85 : i64 to index
    %87 = builtin.unrealized_conversion_cast %86 : index to i64
    llvm.br ^bb1(%87 : i64)
  ^bb9:  // pred: ^bb1
    llvm.return %45 : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
  }
  llvm.func @_mlir_ciface_kernel_dynamic(%arg0: !llvm.ptr, %arg1: !llvm.ptr, %arg2: !llvm.ptr) attributes {llvm.emit_c_interface} {
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
    %16 = llvm.call @kernel_dynamic(%1, %2, %3, %4, %5, %6, %7, %9, %10, %11, %12, %13, %14, %15) : (!llvm.ptr, !llvm.ptr, i64, i64, i64, i64, i64, !llvm.ptr, !llvm.ptr, i64, i64, i64, i64, i64) -> !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
    llvm.store %16, %arg0 : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>, !llvm.ptr
    llvm.return
  }
}

