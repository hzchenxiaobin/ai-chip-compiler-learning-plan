module {
  llvm.mlir.global external constant @data12(dense<[[0.000000e+00, 1.000000e+00, 2.000000e+00, 3.000000e+00], [4.000000e+00, 5.000000e+00, 6.000000e+00, 7.000000e+00], [8.000000e+00, 9.000000e+00, 1.000000e+01, 1.100000e+01]]> : tensor<3x4xf32>) {addr_space = 0 : i32} : !llvm.array<3 x array<4 x f32>>
  llvm.func @expand_metadata() -> !llvm.struct<(i64, i64, i64, i64, i64, i64, i64)> {
    %0 = llvm.mlir.constant(0 : index) : i64
    %1 = llvm.mlir.constant(3 : index) : i64
    %2 = llvm.mlir.constant(2 : index) : i64
    %3 = llvm.mlir.constant(4 : index) : i64
    %4 = llvm.mlir.constant(1 : index) : i64
    %5 = llvm.mlir.undef : !llvm.struct<(i64, i64, i64, i64, i64, i64, i64)>
    %6 = llvm.insertvalue %0, %5[0] : !llvm.struct<(i64, i64, i64, i64, i64, i64, i64)> 
    %7 = llvm.insertvalue %1, %6[1] : !llvm.struct<(i64, i64, i64, i64, i64, i64, i64)> 
    %8 = llvm.insertvalue %2, %7[2] : !llvm.struct<(i64, i64, i64, i64, i64, i64, i64)> 
    %9 = llvm.insertvalue %2, %8[3] : !llvm.struct<(i64, i64, i64, i64, i64, i64, i64)> 
    %10 = llvm.insertvalue %3, %9[4] : !llvm.struct<(i64, i64, i64, i64, i64, i64, i64)> 
    %11 = llvm.insertvalue %2, %10[5] : !llvm.struct<(i64, i64, i64, i64, i64, i64, i64)> 
    %12 = llvm.insertvalue %4, %11[6] : !llvm.struct<(i64, i64, i64, i64, i64, i64, i64)> 
    llvm.return %12 : !llvm.struct<(i64, i64, i64, i64, i64, i64, i64)>
  }
  llvm.func @collapse_metadata() -> !llvm.struct<(i64, i64, i64)> {
    %0 = llvm.mlir.constant(0 : index) : i64
    %1 = llvm.mlir.constant(6 : index) : i64
    %2 = llvm.mlir.constant(2 : index) : i64
    %3 = llvm.mlir.undef : !llvm.struct<(i64, i64, i64)>
    %4 = llvm.insertvalue %0, %3[0] : !llvm.struct<(i64, i64, i64)> 
    %5 = llvm.insertvalue %1, %4[1] : !llvm.struct<(i64, i64, i64)> 
    %6 = llvm.insertvalue %2, %5[2] : !llvm.struct<(i64, i64, i64)> 
    llvm.return %6 : !llvm.struct<(i64, i64, i64)>
  }
  llvm.func @roundtrip(%arg0: !llvm.ptr, %arg1: !llvm.ptr, %arg2: i64, %arg3: i64, %arg4: i64, %arg5: i64, %arg6: i64) -> !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> {
    %0 = llvm.mlir.undef : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
    %1 = llvm.insertvalue %arg0, %0[0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %2 = llvm.insertvalue %arg1, %1[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %3 = llvm.insertvalue %arg2, %2[2] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %4 = llvm.insertvalue %arg3, %3[3, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %5 = llvm.insertvalue %arg5, %4[4, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %6 = llvm.insertvalue %arg4, %5[3, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %7 = llvm.insertvalue %arg6, %6[4, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    llvm.return %7 : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
  }
  llvm.func @printF32(f32) attributes {sym_visibility = "private"}
  llvm.func @printNewline() attributes {sym_visibility = "private"}
  llvm.func @main() {
    %0 = llvm.mlir.constant(6 : index) : i64
    %1 = llvm.mlir.constant(2 : index) : i64
    %2 = llvm.mlir.constant(4 : index) : i64
    %3 = llvm.mlir.constant(1 : index) : i64
    %4 = llvm.mlir.constant(0 : index) : i64
    %5 = llvm.mlir.constant(3 : index) : i64
    %6 = llvm.mlir.constant(4 : index) : i64
    %7 = llvm.mlir.constant(1 : index) : i64
    %8 = llvm.mlir.constant(12 : index) : i64
    %9 = llvm.mlir.zero : !llvm.ptr
    %10 = llvm.getelementptr %9[12] : (!llvm.ptr) -> !llvm.ptr, f32
    %11 = llvm.ptrtoint %10 : !llvm.ptr to i64
    %12 = llvm.mlir.addressof @data12 : !llvm.ptr
    %13 = llvm.getelementptr %12[0, 0, 0] : (!llvm.ptr) -> !llvm.ptr, !llvm.array<3 x array<4 x f32>>
    %14 = llvm.mlir.constant(3735928559 : index) : i64
    %15 = llvm.inttoptr %14 : i64 to !llvm.ptr
    %16 = llvm.mlir.undef : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
    %17 = llvm.insertvalue %15, %16[0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %18 = llvm.insertvalue %13, %17[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %19 = llvm.mlir.constant(0 : index) : i64
    %20 = llvm.insertvalue %19, %18[2] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %21 = llvm.insertvalue %5, %20[3, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %22 = llvm.insertvalue %6, %21[3, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %23 = llvm.insertvalue %6, %22[4, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %24 = llvm.insertvalue %7, %23[4, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %25 = llvm.mlir.undef : !llvm.struct<(ptr, ptr, i64, array<3 x i64>, array<3 x i64>)>
    %26 = llvm.insertvalue %15, %25[0] : !llvm.struct<(ptr, ptr, i64, array<3 x i64>, array<3 x i64>)> 
    %27 = llvm.insertvalue %13, %26[1] : !llvm.struct<(ptr, ptr, i64, array<3 x i64>, array<3 x i64>)> 
    %28 = llvm.mlir.constant(0 : index) : i64
    %29 = llvm.insertvalue %28, %27[2] : !llvm.struct<(ptr, ptr, i64, array<3 x i64>, array<3 x i64>)> 
    %30 = llvm.mlir.constant(3 : index) : i64
    %31 = llvm.insertvalue %30, %29[3, 0] : !llvm.struct<(ptr, ptr, i64, array<3 x i64>, array<3 x i64>)> 
    %32 = llvm.mlir.constant(4 : index) : i64
    %33 = llvm.insertvalue %32, %31[4, 0] : !llvm.struct<(ptr, ptr, i64, array<3 x i64>, array<3 x i64>)> 
    %34 = llvm.mlir.constant(2 : index) : i64
    %35 = llvm.insertvalue %34, %33[3, 1] : !llvm.struct<(ptr, ptr, i64, array<3 x i64>, array<3 x i64>)> 
    %36 = llvm.mlir.constant(2 : index) : i64
    %37 = llvm.insertvalue %36, %35[4, 1] : !llvm.struct<(ptr, ptr, i64, array<3 x i64>, array<3 x i64>)> 
    %38 = llvm.mlir.constant(2 : index) : i64
    %39 = llvm.insertvalue %38, %37[3, 2] : !llvm.struct<(ptr, ptr, i64, array<3 x i64>, array<3 x i64>)> 
    %40 = llvm.mlir.constant(1 : index) : i64
    %41 = llvm.insertvalue %40, %39[4, 2] : !llvm.struct<(ptr, ptr, i64, array<3 x i64>, array<3 x i64>)> 
    %42 = llvm.mlir.constant(4 : index) : i64
    %43 = llvm.mul %3, %42  : i64
    %44 = llvm.mlir.constant(2 : index) : i64
    %45 = llvm.mul %3, %44  : i64
    %46 = llvm.add %43, %45  : i64
    %47 = llvm.add %46, %4  : i64
    %48 = llvm.getelementptr %13[%47] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %49 = llvm.load %48 : !llvm.ptr -> f32
    %50 = llvm.mlir.undef : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)>
    %51 = llvm.insertvalue %15, %50[0] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %52 = llvm.insertvalue %13, %51[1] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %53 = llvm.mlir.constant(0 : index) : i64
    %54 = llvm.insertvalue %53, %52[2] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %55 = llvm.mlir.constant(6 : index) : i64
    %56 = llvm.insertvalue %55, %54[3, 0] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %57 = llvm.mlir.constant(2 : index) : i64
    %58 = llvm.insertvalue %57, %56[4, 0] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %59 = llvm.mlir.constant(2 : index) : i64
    %60 = llvm.mul %2, %59  : i64
    %61 = llvm.getelementptr %13[%60] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %62 = llvm.load %61 : !llvm.ptr -> f32
    %63 = llvm.mlir.constant(2 : index) : i64
    %64 = llvm.mlir.constant(1 : index) : i64
    %65 = llvm.alloca %63 x i64 : (i64) -> !llvm.ptr
    %66 = llvm.mlir.undef : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)>
    %67 = llvm.insertvalue %65, %66[0] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %68 = llvm.insertvalue %65, %67[1] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %69 = llvm.mlir.constant(0 : index) : i64
    %70 = llvm.insertvalue %69, %68[2] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %71 = llvm.insertvalue %63, %70[3, 0] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %72 = llvm.insertvalue %64, %71[4, 0] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    llvm.store %1, %65 : i64, !llvm.ptr
    %73 = llvm.getelementptr %65[1] : (!llvm.ptr) -> !llvm.ptr, i64
    llvm.store %0, %73 : i64, !llvm.ptr
    %74 = llvm.mlir.undef : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
    %75 = llvm.insertvalue %15, %74[0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %76 = llvm.insertvalue %13, %75[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %77 = llvm.mlir.constant(0 : index) : i64
    %78 = llvm.insertvalue %77, %76[2] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %79 = llvm.mlir.constant(1 : index) : i64
    %80 = llvm.mlir.constant(6 : index) : i64
    %81 = llvm.insertvalue %80, %78[3, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %82 = llvm.insertvalue %79, %81[4, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %83 = llvm.mul %79, %80  : i64
    %84 = llvm.mlir.constant(6 : index) : i64
    %85 = llvm.mlir.constant(2 : index) : i64
    %86 = llvm.insertvalue %85, %82[3, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %87 = llvm.insertvalue %84, %86[4, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %88 = llvm.mul %84, %85  : i64
    %89 = llvm.mlir.constant(6 : index) : i64
    %90 = llvm.mul %3, %89  : i64
    %91 = llvm.add %90, %2  : i64
    %92 = llvm.getelementptr %13[%91] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %93 = llvm.load %92 : !llvm.ptr -> f32
    llvm.call @printF32(%49) : (f32) -> ()
    llvm.call @printNewline() : () -> ()
    llvm.call @printF32(%62) : (f32) -> ()
    llvm.call @printNewline() : () -> ()
    llvm.call @printF32(%93) : (f32) -> ()
    llvm.call @printNewline() : () -> ()
    llvm.return
  }
}

