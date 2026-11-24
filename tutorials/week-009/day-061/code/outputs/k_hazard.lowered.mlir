module {
  llvm.func @free(!llvm.ptr)
  llvm.func @malloc(i64) -> !llvm.ptr
  llvm.func @printF32(f32) attributes {sym_visibility = "private"}
  llvm.func @printNewline() attributes {sym_visibility = "private"}
  llvm.func @matmul_all_dynamic(%arg0: !llvm.ptr, %arg1: !llvm.ptr, %arg2: i64, %arg3: i64, %arg4: i64, %arg5: i64, %arg6: i64, %arg7: !llvm.ptr, %arg8: !llvm.ptr, %arg9: i64, %arg10: i64, %arg11: i64, %arg12: i64, %arg13: i64, %arg14: !llvm.ptr, %arg15: !llvm.ptr, %arg16: i64, %arg17: i64, %arg18: i64, %arg19: i64, %arg20: i64) {
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
    %16 = llvm.mlir.undef : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
    %17 = llvm.insertvalue %arg14, %16[0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %18 = llvm.insertvalue %arg15, %17[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %19 = llvm.insertvalue %arg16, %18[2] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %20 = llvm.insertvalue %arg17, %19[3, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %21 = llvm.insertvalue %arg19, %20[4, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %22 = llvm.insertvalue %arg18, %21[3, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %23 = llvm.insertvalue %arg20, %22[4, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %24 = llvm.mlir.constant(1 : index) : i64
    %25 = llvm.mlir.constant(0 : index) : i64
    %26 = llvm.mlir.constant(1 : index) : i64
    %27 = llvm.extractvalue %6[3] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %28 = llvm.alloca %26 x !llvm.array<2 x i64> : (i64) -> !llvm.ptr
    llvm.store %27, %28 : !llvm.array<2 x i64>, !llvm.ptr
    %29 = llvm.getelementptr %28[0, 0] : (!llvm.ptr) -> !llvm.ptr, !llvm.array<2 x i64>
    %30 = llvm.load %29 : !llvm.ptr -> i64
    %31 = llvm.mlir.constant(1 : index) : i64
    %32 = llvm.extractvalue %6[3] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %33 = llvm.alloca %31 x !llvm.array<2 x i64> : (i64) -> !llvm.ptr
    llvm.store %32, %33 : !llvm.array<2 x i64>, !llvm.ptr
    %34 = llvm.getelementptr %33[0, 1] : (!llvm.ptr) -> !llvm.ptr, !llvm.array<2 x i64>
    %35 = llvm.load %34 : !llvm.ptr -> i64
    %36 = llvm.mlir.constant(1 : index) : i64
    %37 = llvm.extractvalue %14[3] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %38 = llvm.alloca %36 x !llvm.array<2 x i64> : (i64) -> !llvm.ptr
    llvm.store %37, %38 : !llvm.array<2 x i64>, !llvm.ptr
    %39 = llvm.getelementptr %38[0, 1] : (!llvm.ptr) -> !llvm.ptr, !llvm.array<2 x i64>
    %40 = llvm.load %39 : !llvm.ptr -> i64
    llvm.br ^bb1(%25 : i64)
  ^bb1(%41: i64):  // 2 preds: ^bb0, ^bb8
    %42 = llvm.icmp "slt" %41, %30 : i64
    llvm.cond_br %42, ^bb2, ^bb9
  ^bb2:  // pred: ^bb1
    llvm.br ^bb3(%25 : i64)
  ^bb3(%43: i64):  // 2 preds: ^bb2, ^bb7
    %44 = llvm.icmp "slt" %43, %40 : i64
    llvm.cond_br %44, ^bb4, ^bb8
  ^bb4:  // pred: ^bb3
    llvm.br ^bb5(%25 : i64)
  ^bb5(%45: i64):  // 2 preds: ^bb4, ^bb6
    %46 = llvm.icmp "slt" %45, %35 : i64
    llvm.cond_br %46, ^bb6, ^bb7
  ^bb6:  // pred: ^bb5
    %47 = llvm.mul %41, %arg5  : i64
    %48 = llvm.add %47, %45  : i64
    %49 = llvm.getelementptr %arg1[%48] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %50 = llvm.load %49 : !llvm.ptr -> f32
    %51 = llvm.mul %45, %arg12  : i64
    %52 = llvm.add %51, %43  : i64
    %53 = llvm.getelementptr %arg8[%52] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %54 = llvm.load %53 : !llvm.ptr -> f32
    %55 = llvm.mul %41, %arg19  : i64
    %56 = llvm.add %55, %43  : i64
    %57 = llvm.getelementptr %arg15[%56] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %58 = llvm.load %57 : !llvm.ptr -> f32
    %59 = llvm.fmul %50, %54  : f32
    %60 = llvm.fadd %58, %59  : f32
    %61 = llvm.mul %41, %arg19  : i64
    %62 = llvm.add %61, %43  : i64
    %63 = llvm.getelementptr %arg15[%62] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    llvm.store %60, %63 : f32, !llvm.ptr
    %64 = llvm.add %45, %24  : i64
    llvm.br ^bb5(%64 : i64)
  ^bb7:  // pred: ^bb5
    %65 = llvm.add %43, %24  : i64
    llvm.br ^bb3(%65 : i64)
  ^bb8:  // pred: ^bb3
    %66 = llvm.add %41, %24  : i64
    llvm.br ^bb1(%66 : i64)
  ^bb9:  // pred: ^bb1
    llvm.return
  }
  llvm.func @main() {
    %0 = llvm.mlir.constant(0.000000e+00 : f32) : f32
    %1 = llvm.mlir.constant(4.000000e+01 : f32) : f32
    %2 = llvm.mlir.constant(3.000000e+01 : f32) : f32
    %3 = llvm.mlir.constant(2.000000e+01 : f32) : f32
    %4 = llvm.mlir.constant(1.000000e+01 : f32) : f32
    %5 = llvm.mlir.constant(6.000000e+00 : f32) : f32
    %6 = llvm.mlir.constant(5.000000e+00 : f32) : f32
    %7 = llvm.mlir.constant(4.000000e+00 : f32) : f32
    %8 = llvm.mlir.constant(3.000000e+00 : f32) : f32
    %9 = llvm.mlir.constant(2.000000e+00 : f32) : f32
    %10 = llvm.mlir.constant(1.000000e+00 : f32) : f32
    %11 = llvm.mlir.constant(0 : index) : i64
    %12 = llvm.mlir.constant(1 : index) : i64
    %13 = llvm.mlir.constant(2 : index) : i64
    %14 = llvm.mlir.constant(2 : index) : i64
    %15 = llvm.mlir.constant(3 : index) : i64
    %16 = llvm.mlir.constant(1 : index) : i64
    %17 = llvm.mlir.constant(6 : index) : i64
    %18 = llvm.mlir.zero : !llvm.ptr
    %19 = llvm.getelementptr %18[6] : (!llvm.ptr) -> !llvm.ptr, f32
    %20 = llvm.ptrtoint %19 : !llvm.ptr to i64
    %21 = llvm.call @malloc(%20) : (i64) -> !llvm.ptr
    %22 = llvm.mlir.undef : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
    %23 = llvm.insertvalue %21, %22[0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %24 = llvm.insertvalue %21, %23[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %25 = llvm.mlir.constant(0 : index) : i64
    %26 = llvm.insertvalue %25, %24[2] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %27 = llvm.insertvalue %14, %26[3, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %28 = llvm.insertvalue %15, %27[3, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %29 = llvm.insertvalue %15, %28[4, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %30 = llvm.insertvalue %16, %29[4, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %31 = llvm.mlir.constant(2 : index) : i64
    %32 = llvm.mlir.constant(2 : index) : i64
    %33 = llvm.mlir.constant(1 : index) : i64
    %34 = llvm.mlir.constant(4 : index) : i64
    %35 = llvm.mlir.zero : !llvm.ptr
    %36 = llvm.getelementptr %35[4] : (!llvm.ptr) -> !llvm.ptr, f32
    %37 = llvm.ptrtoint %36 : !llvm.ptr to i64
    %38 = llvm.call @malloc(%37) : (i64) -> !llvm.ptr
    %39 = llvm.mlir.undef : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
    %40 = llvm.insertvalue %38, %39[0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %41 = llvm.insertvalue %38, %40[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %42 = llvm.mlir.constant(0 : index) : i64
    %43 = llvm.insertvalue %42, %41[2] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %44 = llvm.insertvalue %31, %43[3, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %45 = llvm.insertvalue %32, %44[3, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %46 = llvm.insertvalue %32, %45[4, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %47 = llvm.insertvalue %33, %46[4, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %48 = llvm.mlir.constant(2 : index) : i64
    %49 = llvm.mlir.constant(2 : index) : i64
    %50 = llvm.mlir.constant(1 : index) : i64
    %51 = llvm.mlir.constant(4 : index) : i64
    %52 = llvm.mlir.zero : !llvm.ptr
    %53 = llvm.getelementptr %52[4] : (!llvm.ptr) -> !llvm.ptr, f32
    %54 = llvm.ptrtoint %53 : !llvm.ptr to i64
    %55 = llvm.call @malloc(%54) : (i64) -> !llvm.ptr
    %56 = llvm.mlir.undef : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
    %57 = llvm.insertvalue %55, %56[0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %58 = llvm.insertvalue %55, %57[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %59 = llvm.mlir.constant(0 : index) : i64
    %60 = llvm.insertvalue %59, %58[2] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %61 = llvm.insertvalue %48, %60[3, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %62 = llvm.insertvalue %49, %61[3, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %63 = llvm.insertvalue %49, %62[4, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %64 = llvm.insertvalue %50, %63[4, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %65 = llvm.mlir.constant(3 : index) : i64
    %66 = llvm.mul %11, %65  : i64
    %67 = llvm.add %66, %11  : i64
    %68 = llvm.getelementptr %21[%67] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    llvm.store %10, %68 : f32, !llvm.ptr
    %69 = llvm.mlir.constant(3 : index) : i64
    %70 = llvm.mul %11, %69  : i64
    %71 = llvm.add %70, %12  : i64
    %72 = llvm.getelementptr %21[%71] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    llvm.store %9, %72 : f32, !llvm.ptr
    %73 = llvm.mlir.constant(3 : index) : i64
    %74 = llvm.mul %11, %73  : i64
    %75 = llvm.add %74, %13  : i64
    %76 = llvm.getelementptr %21[%75] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    llvm.store %8, %76 : f32, !llvm.ptr
    %77 = llvm.mlir.constant(3 : index) : i64
    %78 = llvm.mul %12, %77  : i64
    %79 = llvm.add %78, %11  : i64
    %80 = llvm.getelementptr %21[%79] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    llvm.store %7, %80 : f32, !llvm.ptr
    %81 = llvm.mlir.constant(3 : index) : i64
    %82 = llvm.mul %12, %81  : i64
    %83 = llvm.add %82, %12  : i64
    %84 = llvm.getelementptr %21[%83] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    llvm.store %6, %84 : f32, !llvm.ptr
    %85 = llvm.mlir.constant(3 : index) : i64
    %86 = llvm.mul %12, %85  : i64
    %87 = llvm.add %86, %13  : i64
    %88 = llvm.getelementptr %21[%87] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    llvm.store %5, %88 : f32, !llvm.ptr
    %89 = llvm.mlir.constant(2 : index) : i64
    %90 = llvm.mul %11, %89  : i64
    %91 = llvm.add %90, %11  : i64
    %92 = llvm.getelementptr %38[%91] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    llvm.store %4, %92 : f32, !llvm.ptr
    %93 = llvm.mlir.constant(2 : index) : i64
    %94 = llvm.mul %11, %93  : i64
    %95 = llvm.add %94, %12  : i64
    %96 = llvm.getelementptr %38[%95] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    llvm.store %3, %96 : f32, !llvm.ptr
    %97 = llvm.mlir.constant(2 : index) : i64
    %98 = llvm.mul %12, %97  : i64
    %99 = llvm.add %98, %11  : i64
    %100 = llvm.getelementptr %38[%99] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    llvm.store %2, %100 : f32, !llvm.ptr
    %101 = llvm.mlir.constant(2 : index) : i64
    %102 = llvm.mul %12, %101  : i64
    %103 = llvm.add %102, %12  : i64
    %104 = llvm.getelementptr %38[%103] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    llvm.store %1, %104 : f32, !llvm.ptr
    %105 = llvm.mlir.constant(2 : index) : i64
    %106 = llvm.mul %11, %105  : i64
    %107 = llvm.add %106, %11  : i64
    %108 = llvm.getelementptr %55[%107] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    llvm.store %0, %108 : f32, !llvm.ptr
    %109 = llvm.mlir.constant(2 : index) : i64
    %110 = llvm.mul %11, %109  : i64
    %111 = llvm.add %110, %12  : i64
    %112 = llvm.getelementptr %55[%111] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    llvm.store %0, %112 : f32, !llvm.ptr
    %113 = llvm.mlir.constant(2 : index) : i64
    %114 = llvm.mul %12, %113  : i64
    %115 = llvm.add %114, %11  : i64
    %116 = llvm.getelementptr %55[%115] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    llvm.store %0, %116 : f32, !llvm.ptr
    %117 = llvm.mlir.constant(2 : index) : i64
    %118 = llvm.mul %12, %117  : i64
    %119 = llvm.add %118, %12  : i64
    %120 = llvm.getelementptr %55[%119] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    llvm.store %0, %120 : f32, !llvm.ptr
    %121 = llvm.extractvalue %30[0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %122 = llvm.extractvalue %30[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %123 = llvm.extractvalue %30[2] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %124 = llvm.extractvalue %30[3, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %125 = llvm.extractvalue %30[3, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %126 = llvm.extractvalue %30[4, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %127 = llvm.extractvalue %30[4, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %128 = llvm.extractvalue %47[0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %129 = llvm.extractvalue %47[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %130 = llvm.extractvalue %47[2] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %131 = llvm.extractvalue %47[3, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %132 = llvm.extractvalue %47[3, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %133 = llvm.extractvalue %47[4, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %134 = llvm.extractvalue %47[4, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %135 = llvm.extractvalue %64[0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %136 = llvm.extractvalue %64[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %137 = llvm.extractvalue %64[2] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %138 = llvm.extractvalue %64[3, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %139 = llvm.extractvalue %64[3, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %140 = llvm.extractvalue %64[4, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %141 = llvm.extractvalue %64[4, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    llvm.call @matmul_all_dynamic(%121, %122, %123, %124, %125, %126, %127, %128, %129, %130, %131, %132, %133, %134, %135, %136, %137, %138, %139, %140, %141) : (!llvm.ptr, !llvm.ptr, i64, i64, i64, i64, i64, !llvm.ptr, !llvm.ptr, i64, i64, i64, i64, i64, !llvm.ptr, !llvm.ptr, i64, i64, i64, i64, i64) -> ()
    %142 = llvm.mlir.constant(2 : index) : i64
    %143 = llvm.mul %11, %142  : i64
    %144 = llvm.add %143, %11  : i64
    %145 = llvm.getelementptr %55[%144] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %146 = llvm.load %145 : !llvm.ptr -> f32
    %147 = llvm.mlir.constant(2 : index) : i64
    %148 = llvm.mul %11, %147  : i64
    %149 = llvm.add %148, %12  : i64
    %150 = llvm.getelementptr %55[%149] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %151 = llvm.load %150 : !llvm.ptr -> f32
    %152 = llvm.mlir.constant(2 : index) : i64
    %153 = llvm.mul %12, %152  : i64
    %154 = llvm.add %153, %11  : i64
    %155 = llvm.getelementptr %55[%154] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %156 = llvm.load %155 : !llvm.ptr -> f32
    %157 = llvm.mlir.constant(2 : index) : i64
    %158 = llvm.mul %12, %157  : i64
    %159 = llvm.add %158, %12  : i64
    %160 = llvm.getelementptr %55[%159] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %161 = llvm.load %160 : !llvm.ptr -> f32
    llvm.call @printF32(%146) : (f32) -> ()
    llvm.call @printNewline() : () -> ()
    llvm.call @printF32(%151) : (f32) -> ()
    llvm.call @printNewline() : () -> ()
    llvm.call @printF32(%156) : (f32) -> ()
    llvm.call @printNewline() : () -> ()
    llvm.call @printF32(%161) : (f32) -> ()
    llvm.call @printNewline() : () -> ()
    llvm.call @free(%21) : (!llvm.ptr) -> ()
    llvm.call @free(%38) : (!llvm.ptr) -> ()
    llvm.call @free(%55) : (!llvm.ptr) -> ()
    llvm.return
  }
}

