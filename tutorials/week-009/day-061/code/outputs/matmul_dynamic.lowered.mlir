module {
  llvm.func @free(!llvm.ptr)
  llvm.func @malloc(i64) -> !llvm.ptr
  llvm.func @printF32(f32) attributes {sym_visibility = "private"}
  llvm.func @printNewline() attributes {sym_visibility = "private"}
  llvm.func @matmul_m_dynamic(%arg0: !llvm.ptr, %arg1: !llvm.ptr, %arg2: i64, %arg3: i64, %arg4: i64, %arg5: i64, %arg6: i64, %arg7: !llvm.ptr, %arg8: !llvm.ptr, %arg9: i64, %arg10: i64, %arg11: i64, %arg12: i64, %arg13: i64, %arg14: !llvm.ptr, %arg15: !llvm.ptr, %arg16: i64, %arg17: i64, %arg18: i64, %arg19: i64, %arg20: i64) {
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
    %24 = llvm.mlir.constant(3 : index) : i64
    %25 = llvm.mlir.constant(2 : index) : i64
    %26 = llvm.mlir.constant(1 : index) : i64
    %27 = llvm.mlir.constant(0 : index) : i64
    %28 = llvm.mlir.constant(1 : index) : i64
    %29 = llvm.extractvalue %6[3] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %30 = llvm.alloca %28 x !llvm.array<2 x i64> : (i64) -> !llvm.ptr
    llvm.store %29, %30 : !llvm.array<2 x i64>, !llvm.ptr
    %31 = llvm.getelementptr %30[0, 0] : (!llvm.ptr) -> !llvm.ptr, !llvm.array<2 x i64>
    %32 = llvm.load %31 : !llvm.ptr -> i64
    llvm.br ^bb1(%27 : i64)
  ^bb1(%33: i64):  // 2 preds: ^bb0, ^bb8
    %34 = llvm.icmp "slt" %33, %32 : i64
    llvm.cond_br %34, ^bb2, ^bb9
  ^bb2:  // pred: ^bb1
    llvm.br ^bb3(%27 : i64)
  ^bb3(%35: i64):  // 2 preds: ^bb2, ^bb7
    %36 = llvm.icmp "slt" %35, %25 : i64
    llvm.cond_br %36, ^bb4, ^bb8
  ^bb4:  // pred: ^bb3
    llvm.br ^bb5(%27 : i64)
  ^bb5(%37: i64):  // 2 preds: ^bb4, ^bb6
    %38 = llvm.icmp "slt" %37, %24 : i64
    llvm.cond_br %38, ^bb6, ^bb7
  ^bb6:  // pred: ^bb5
    %39 = llvm.mlir.constant(3 : index) : i64
    %40 = llvm.mul %33, %39  : i64
    %41 = llvm.add %40, %37  : i64
    %42 = llvm.getelementptr %arg1[%41] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %43 = llvm.load %42 : !llvm.ptr -> f32
    %44 = llvm.mlir.constant(2 : index) : i64
    %45 = llvm.mul %37, %44  : i64
    %46 = llvm.add %45, %35  : i64
    %47 = llvm.getelementptr %arg8[%46] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %48 = llvm.load %47 : !llvm.ptr -> f32
    %49 = llvm.mlir.constant(2 : index) : i64
    %50 = llvm.mul %33, %49  : i64
    %51 = llvm.add %50, %35  : i64
    %52 = llvm.getelementptr %arg15[%51] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %53 = llvm.load %52 : !llvm.ptr -> f32
    %54 = llvm.fmul %43, %48  : f32
    %55 = llvm.fadd %53, %54  : f32
    %56 = llvm.mlir.constant(2 : index) : i64
    %57 = llvm.mul %33, %56  : i64
    %58 = llvm.add %57, %35  : i64
    %59 = llvm.getelementptr %arg15[%58] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    llvm.store %55, %59 : f32, !llvm.ptr
    %60 = llvm.add %37, %26  : i64
    llvm.br ^bb5(%60 : i64)
  ^bb7:  // pred: ^bb5
    %61 = llvm.add %35, %26  : i64
    llvm.br ^bb3(%61 : i64)
  ^bb8:  // pred: ^bb3
    %62 = llvm.add %33, %26  : i64
    llvm.br ^bb1(%62 : i64)
  ^bb9:  // pred: ^bb1
    llvm.return
  }
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
    %1 = llvm.mlir.constant(6.000000e+01 : f32) : f32
    %2 = llvm.mlir.constant(5.000000e+01 : f32) : f32
    %3 = llvm.mlir.constant(4.000000e+01 : f32) : f32
    %4 = llvm.mlir.constant(3.000000e+01 : f32) : f32
    %5 = llvm.mlir.constant(2.000000e+01 : f32) : f32
    %6 = llvm.mlir.constant(1.000000e+01 : f32) : f32
    %7 = llvm.mlir.constant(6.000000e+00 : f32) : f32
    %8 = llvm.mlir.constant(5.000000e+00 : f32) : f32
    %9 = llvm.mlir.constant(4.000000e+00 : f32) : f32
    %10 = llvm.mlir.constant(3.000000e+00 : f32) : f32
    %11 = llvm.mlir.constant(2.000000e+00 : f32) : f32
    %12 = llvm.mlir.constant(1.000000e+00 : f32) : f32
    %13 = llvm.mlir.constant(0 : index) : i64
    %14 = llvm.mlir.constant(1 : index) : i64
    %15 = llvm.mlir.constant(2 : index) : i64
    %16 = llvm.mlir.constant(2 : index) : i64
    %17 = llvm.mlir.constant(3 : index) : i64
    %18 = llvm.mlir.constant(1 : index) : i64
    %19 = llvm.mlir.constant(6 : index) : i64
    %20 = llvm.mlir.zero : !llvm.ptr
    %21 = llvm.getelementptr %20[6] : (!llvm.ptr) -> !llvm.ptr, f32
    %22 = llvm.ptrtoint %21 : !llvm.ptr to i64
    %23 = llvm.call @malloc(%22) : (i64) -> !llvm.ptr
    %24 = llvm.mlir.undef : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
    %25 = llvm.insertvalue %23, %24[0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %26 = llvm.insertvalue %23, %25[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %27 = llvm.mlir.constant(0 : index) : i64
    %28 = llvm.insertvalue %27, %26[2] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %29 = llvm.insertvalue %16, %28[3, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %30 = llvm.insertvalue %17, %29[3, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %31 = llvm.insertvalue %17, %30[4, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %32 = llvm.insertvalue %18, %31[4, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %33 = llvm.mlir.constant(3 : index) : i64
    %34 = llvm.mlir.constant(2 : index) : i64
    %35 = llvm.mlir.constant(1 : index) : i64
    %36 = llvm.mlir.constant(6 : index) : i64
    %37 = llvm.mlir.zero : !llvm.ptr
    %38 = llvm.getelementptr %37[6] : (!llvm.ptr) -> !llvm.ptr, f32
    %39 = llvm.ptrtoint %38 : !llvm.ptr to i64
    %40 = llvm.call @malloc(%39) : (i64) -> !llvm.ptr
    %41 = llvm.mlir.undef : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
    %42 = llvm.insertvalue %40, %41[0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %43 = llvm.insertvalue %40, %42[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %44 = llvm.mlir.constant(0 : index) : i64
    %45 = llvm.insertvalue %44, %43[2] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %46 = llvm.insertvalue %33, %45[3, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %47 = llvm.insertvalue %34, %46[3, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %48 = llvm.insertvalue %34, %47[4, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %49 = llvm.insertvalue %35, %48[4, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %50 = llvm.mlir.constant(2 : index) : i64
    %51 = llvm.mlir.constant(2 : index) : i64
    %52 = llvm.mlir.constant(1 : index) : i64
    %53 = llvm.mlir.constant(4 : index) : i64
    %54 = llvm.mlir.zero : !llvm.ptr
    %55 = llvm.getelementptr %54[4] : (!llvm.ptr) -> !llvm.ptr, f32
    %56 = llvm.ptrtoint %55 : !llvm.ptr to i64
    %57 = llvm.call @malloc(%56) : (i64) -> !llvm.ptr
    %58 = llvm.mlir.undef : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
    %59 = llvm.insertvalue %57, %58[0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %60 = llvm.insertvalue %57, %59[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %61 = llvm.mlir.constant(0 : index) : i64
    %62 = llvm.insertvalue %61, %60[2] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %63 = llvm.insertvalue %50, %62[3, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %64 = llvm.insertvalue %51, %63[3, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %65 = llvm.insertvalue %51, %64[4, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %66 = llvm.insertvalue %52, %65[4, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %67 = llvm.mlir.constant(3 : index) : i64
    %68 = llvm.mul %13, %67  : i64
    %69 = llvm.add %68, %13  : i64
    %70 = llvm.getelementptr %23[%69] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    llvm.store %12, %70 : f32, !llvm.ptr
    %71 = llvm.mlir.constant(3 : index) : i64
    %72 = llvm.mul %13, %71  : i64
    %73 = llvm.add %72, %14  : i64
    %74 = llvm.getelementptr %23[%73] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    llvm.store %11, %74 : f32, !llvm.ptr
    %75 = llvm.mlir.constant(3 : index) : i64
    %76 = llvm.mul %13, %75  : i64
    %77 = llvm.add %76, %15  : i64
    %78 = llvm.getelementptr %23[%77] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    llvm.store %10, %78 : f32, !llvm.ptr
    %79 = llvm.mlir.constant(3 : index) : i64
    %80 = llvm.mul %14, %79  : i64
    %81 = llvm.add %80, %13  : i64
    %82 = llvm.getelementptr %23[%81] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    llvm.store %9, %82 : f32, !llvm.ptr
    %83 = llvm.mlir.constant(3 : index) : i64
    %84 = llvm.mul %14, %83  : i64
    %85 = llvm.add %84, %14  : i64
    %86 = llvm.getelementptr %23[%85] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    llvm.store %8, %86 : f32, !llvm.ptr
    %87 = llvm.mlir.constant(3 : index) : i64
    %88 = llvm.mul %14, %87  : i64
    %89 = llvm.add %88, %15  : i64
    %90 = llvm.getelementptr %23[%89] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    llvm.store %7, %90 : f32, !llvm.ptr
    %91 = llvm.mlir.constant(2 : index) : i64
    %92 = llvm.mul %13, %91  : i64
    %93 = llvm.add %92, %13  : i64
    %94 = llvm.getelementptr %40[%93] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    llvm.store %6, %94 : f32, !llvm.ptr
    %95 = llvm.mlir.constant(2 : index) : i64
    %96 = llvm.mul %13, %95  : i64
    %97 = llvm.add %96, %14  : i64
    %98 = llvm.getelementptr %40[%97] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    llvm.store %5, %98 : f32, !llvm.ptr
    %99 = llvm.mlir.constant(2 : index) : i64
    %100 = llvm.mul %14, %99  : i64
    %101 = llvm.add %100, %13  : i64
    %102 = llvm.getelementptr %40[%101] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    llvm.store %4, %102 : f32, !llvm.ptr
    %103 = llvm.mlir.constant(2 : index) : i64
    %104 = llvm.mul %14, %103  : i64
    %105 = llvm.add %104, %14  : i64
    %106 = llvm.getelementptr %40[%105] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    llvm.store %3, %106 : f32, !llvm.ptr
    %107 = llvm.mlir.constant(2 : index) : i64
    %108 = llvm.mul %15, %107  : i64
    %109 = llvm.add %108, %13  : i64
    %110 = llvm.getelementptr %40[%109] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    llvm.store %2, %110 : f32, !llvm.ptr
    %111 = llvm.mlir.constant(2 : index) : i64
    %112 = llvm.mul %15, %111  : i64
    %113 = llvm.add %112, %14  : i64
    %114 = llvm.getelementptr %40[%113] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    llvm.store %1, %114 : f32, !llvm.ptr
    %115 = llvm.mlir.constant(2 : index) : i64
    %116 = llvm.mul %13, %115  : i64
    %117 = llvm.add %116, %13  : i64
    %118 = llvm.getelementptr %57[%117] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    llvm.store %0, %118 : f32, !llvm.ptr
    %119 = llvm.mlir.constant(2 : index) : i64
    %120 = llvm.mul %13, %119  : i64
    %121 = llvm.add %120, %14  : i64
    %122 = llvm.getelementptr %57[%121] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    llvm.store %0, %122 : f32, !llvm.ptr
    %123 = llvm.mlir.constant(2 : index) : i64
    %124 = llvm.mul %14, %123  : i64
    %125 = llvm.add %124, %13  : i64
    %126 = llvm.getelementptr %57[%125] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    llvm.store %0, %126 : f32, !llvm.ptr
    %127 = llvm.mlir.constant(2 : index) : i64
    %128 = llvm.mul %14, %127  : i64
    %129 = llvm.add %128, %14  : i64
    %130 = llvm.getelementptr %57[%129] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    llvm.store %0, %130 : f32, !llvm.ptr
    %131 = llvm.extractvalue %32[0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %132 = llvm.extractvalue %32[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %133 = llvm.extractvalue %32[2] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %134 = llvm.extractvalue %32[3, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %135 = llvm.extractvalue %32[3, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %136 = llvm.extractvalue %32[4, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %137 = llvm.extractvalue %32[4, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %138 = llvm.extractvalue %49[0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %139 = llvm.extractvalue %49[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %140 = llvm.extractvalue %49[2] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %141 = llvm.extractvalue %49[3, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %142 = llvm.extractvalue %49[3, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %143 = llvm.extractvalue %49[4, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %144 = llvm.extractvalue %49[4, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %145 = llvm.extractvalue %66[0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %146 = llvm.extractvalue %66[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %147 = llvm.extractvalue %66[2] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %148 = llvm.extractvalue %66[3, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %149 = llvm.extractvalue %66[3, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %150 = llvm.extractvalue %66[4, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %151 = llvm.extractvalue %66[4, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    llvm.call @matmul_m_dynamic(%131, %132, %133, %134, %135, %136, %137, %138, %139, %140, %141, %142, %143, %144, %145, %146, %147, %148, %149, %150, %151) : (!llvm.ptr, !llvm.ptr, i64, i64, i64, i64, i64, !llvm.ptr, !llvm.ptr, i64, i64, i64, i64, i64, !llvm.ptr, !llvm.ptr, i64, i64, i64, i64, i64) -> ()
    %152 = llvm.mlir.constant(2 : index) : i64
    %153 = llvm.mul %13, %152  : i64
    %154 = llvm.add %153, %13  : i64
    %155 = llvm.getelementptr %57[%154] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %156 = llvm.load %155 : !llvm.ptr -> f32
    %157 = llvm.mlir.constant(2 : index) : i64
    %158 = llvm.mul %13, %157  : i64
    %159 = llvm.add %158, %14  : i64
    %160 = llvm.getelementptr %57[%159] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %161 = llvm.load %160 : !llvm.ptr -> f32
    %162 = llvm.mlir.constant(2 : index) : i64
    %163 = llvm.mul %14, %162  : i64
    %164 = llvm.add %163, %13  : i64
    %165 = llvm.getelementptr %57[%164] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %166 = llvm.load %165 : !llvm.ptr -> f32
    %167 = llvm.mlir.constant(2 : index) : i64
    %168 = llvm.mul %14, %167  : i64
    %169 = llvm.add %168, %14  : i64
    %170 = llvm.getelementptr %57[%169] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %171 = llvm.load %170 : !llvm.ptr -> f32
    llvm.call @printF32(%156) : (f32) -> ()
    llvm.call @printNewline() : () -> ()
    llvm.call @printF32(%161) : (f32) -> ()
    llvm.call @printNewline() : () -> ()
    llvm.call @printF32(%166) : (f32) -> ()
    llvm.call @printNewline() : () -> ()
    llvm.call @printF32(%171) : (f32) -> ()
    llvm.call @printNewline() : () -> ()
    llvm.call @free(%23) : (!llvm.ptr) -> ()
    llvm.call @free(%40) : (!llvm.ptr) -> ()
    llvm.call @free(%57) : (!llvm.ptr) -> ()
    llvm.return
  }
}

