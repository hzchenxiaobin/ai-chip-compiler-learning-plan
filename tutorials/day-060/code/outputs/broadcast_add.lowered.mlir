module {
  llvm.func @malloc(i64) -> !llvm.ptr
  llvm.mlir.global private constant @ga(dense<[[1.000000e+00, 2.000000e+00, 3.000000e+00], [4.000000e+00, 5.000000e+00, 6.000000e+00]]> : tensor<2x3xf32>) {addr_space = 0 : i32} : !llvm.array<2 x array<3 x f32>>
  llvm.mlir.global private constant @gb(dense<[1.000000e+01, 2.000000e+01, 3.000000e+01]> : tensor<3xf32>) {addr_space = 0 : i32} : !llvm.array<3 x f32>
  llvm.mlir.global private constant @gc(dense<[[1.000000e+02], [2.000000e+02]]> : tensor<2x1xf32>) {addr_space = 0 : i32} : !llvm.array<2 x array<1 x f32>>
  llvm.func @printF32(f32) attributes {sym_visibility = "private"}
  llvm.func @printNewline() attributes {sym_visibility = "private"}
  llvm.func @main() {
    %0 = llvm.mlir.constant(3 : index) : i64
    %1 = llvm.mlir.constant(2 : index) : i64
    %2 = llvm.mlir.constant(1 : index) : i64
    %3 = llvm.mlir.constant(0 : index) : i64
    %4 = llvm.mlir.constant(2 : index) : i64
    %5 = llvm.mlir.constant(3 : index) : i64
    %6 = llvm.mlir.constant(1 : index) : i64
    %7 = llvm.mlir.constant(6 : index) : i64
    %8 = llvm.mlir.zero : !llvm.ptr
    %9 = llvm.getelementptr %8[6] : (!llvm.ptr) -> !llvm.ptr, f32
    %10 = llvm.ptrtoint %9 : !llvm.ptr to i64
    %11 = llvm.mlir.addressof @ga : !llvm.ptr
    %12 = llvm.getelementptr %11[0, 0, 0] : (!llvm.ptr) -> !llvm.ptr, !llvm.array<2 x array<3 x f32>>
    %13 = llvm.mlir.constant(3735928559 : index) : i64
    %14 = llvm.inttoptr %13 : i64 to !llvm.ptr
    %15 = llvm.mlir.undef : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
    %16 = llvm.insertvalue %14, %15[0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %17 = llvm.insertvalue %12, %16[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %18 = llvm.mlir.constant(0 : index) : i64
    %19 = llvm.insertvalue %18, %17[2] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %20 = llvm.insertvalue %4, %19[3, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %21 = llvm.insertvalue %5, %20[3, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %22 = llvm.insertvalue %5, %21[4, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %23 = llvm.insertvalue %6, %22[4, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %24 = llvm.mlir.constant(3 : index) : i64
    %25 = llvm.mlir.constant(1 : index) : i64
    %26 = llvm.mlir.zero : !llvm.ptr
    %27 = llvm.getelementptr %26[3] : (!llvm.ptr) -> !llvm.ptr, f32
    %28 = llvm.ptrtoint %27 : !llvm.ptr to i64
    %29 = llvm.mlir.addressof @gb : !llvm.ptr
    %30 = llvm.getelementptr %29[0, 0] : (!llvm.ptr) -> !llvm.ptr, !llvm.array<3 x f32>
    %31 = llvm.mlir.constant(3735928559 : index) : i64
    %32 = llvm.inttoptr %31 : i64 to !llvm.ptr
    %33 = llvm.mlir.undef : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)>
    %34 = llvm.insertvalue %32, %33[0] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %35 = llvm.insertvalue %30, %34[1] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %36 = llvm.mlir.constant(0 : index) : i64
    %37 = llvm.insertvalue %36, %35[2] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %38 = llvm.insertvalue %24, %37[3, 0] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %39 = llvm.insertvalue %25, %38[4, 0] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %40 = llvm.mlir.constant(2 : index) : i64
    %41 = llvm.mlir.constant(1 : index) : i64
    %42 = llvm.mlir.constant(1 : index) : i64
    %43 = llvm.mlir.zero : !llvm.ptr
    %44 = llvm.getelementptr %43[2] : (!llvm.ptr) -> !llvm.ptr, f32
    %45 = llvm.ptrtoint %44 : !llvm.ptr to i64
    %46 = llvm.mlir.addressof @gc : !llvm.ptr
    %47 = llvm.getelementptr %46[0, 0, 0] : (!llvm.ptr) -> !llvm.ptr, !llvm.array<2 x array<1 x f32>>
    %48 = llvm.mlir.constant(3735928559 : index) : i64
    %49 = llvm.inttoptr %48 : i64 to !llvm.ptr
    %50 = llvm.mlir.undef : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
    %51 = llvm.insertvalue %49, %50[0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %52 = llvm.insertvalue %47, %51[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %53 = llvm.mlir.constant(0 : index) : i64
    %54 = llvm.insertvalue %53, %52[2] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %55 = llvm.insertvalue %40, %54[3, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %56 = llvm.insertvalue %41, %55[3, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %57 = llvm.insertvalue %41, %56[4, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %58 = llvm.insertvalue %42, %57[4, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %59 = llvm.mlir.constant(2 : index) : i64
    %60 = llvm.mlir.constant(3 : index) : i64
    %61 = llvm.mlir.constant(1 : index) : i64
    %62 = llvm.mlir.constant(6 : index) : i64
    %63 = llvm.mlir.zero : !llvm.ptr
    %64 = llvm.getelementptr %63[6] : (!llvm.ptr) -> !llvm.ptr, f32
    %65 = llvm.ptrtoint %64 : !llvm.ptr to i64
    %66 = llvm.call @malloc(%65) : (i64) -> !llvm.ptr
    %67 = llvm.mlir.undef : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
    %68 = llvm.insertvalue %66, %67[0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %69 = llvm.insertvalue %66, %68[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %70 = llvm.mlir.constant(0 : index) : i64
    %71 = llvm.insertvalue %70, %69[2] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %72 = llvm.insertvalue %59, %71[3, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %73 = llvm.insertvalue %60, %72[3, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %74 = llvm.insertvalue %60, %73[4, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %75 = llvm.insertvalue %61, %74[4, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %76 = llvm.mlir.constant(2 : index) : i64
    %77 = llvm.mlir.constant(3 : index) : i64
    %78 = llvm.mlir.constant(1 : index) : i64
    %79 = llvm.mlir.constant(6 : index) : i64
    %80 = llvm.mlir.zero : !llvm.ptr
    %81 = llvm.getelementptr %80[6] : (!llvm.ptr) -> !llvm.ptr, f32
    %82 = llvm.ptrtoint %81 : !llvm.ptr to i64
    %83 = llvm.call @malloc(%82) : (i64) -> !llvm.ptr
    %84 = llvm.mlir.undef : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
    %85 = llvm.insertvalue %83, %84[0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %86 = llvm.insertvalue %83, %85[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %87 = llvm.mlir.constant(0 : index) : i64
    %88 = llvm.insertvalue %87, %86[2] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %89 = llvm.insertvalue %76, %88[3, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %90 = llvm.insertvalue %77, %89[3, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %91 = llvm.insertvalue %77, %90[4, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    %92 = llvm.insertvalue %78, %91[4, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> 
    llvm.br ^bb1(%3 : i64)
  ^bb1(%93: i64):  // 2 preds: ^bb0, ^bb5
    %94 = llvm.icmp "slt" %93, %1 : i64
    llvm.cond_br %94, ^bb2, ^bb6
  ^bb2:  // pred: ^bb1
    llvm.br ^bb3(%3 : i64)
  ^bb3(%95: i64):  // 2 preds: ^bb2, ^bb4
    %96 = llvm.icmp "slt" %95, %0 : i64
    llvm.cond_br %96, ^bb4, ^bb5
  ^bb4:  // pred: ^bb3
    %97 = llvm.mlir.constant(3 : index) : i64
    %98 = llvm.mul %93, %97  : i64
    %99 = llvm.add %98, %95  : i64
    %100 = llvm.getelementptr %12[%99] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %101 = llvm.load %100 : !llvm.ptr -> f32
    %102 = llvm.getelementptr %30[%95] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %103 = llvm.load %102 : !llvm.ptr -> f32
    %104 = llvm.fadd %101, %103  : f32
    %105 = llvm.mlir.constant(3 : index) : i64
    %106 = llvm.mul %93, %105  : i64
    %107 = llvm.add %106, %95  : i64
    %108 = llvm.getelementptr %66[%107] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    llvm.store %104, %108 : f32, !llvm.ptr
    %109 = llvm.add %95, %2  : i64
    llvm.br ^bb3(%109 : i64)
  ^bb5:  // pred: ^bb3
    %110 = llvm.add %93, %2  : i64
    llvm.br ^bb1(%110 : i64)
  ^bb6:  // pred: ^bb1
    llvm.br ^bb7(%3 : i64)
  ^bb7(%111: i64):  // 2 preds: ^bb6, ^bb11
    %112 = llvm.icmp "slt" %111, %1 : i64
    llvm.cond_br %112, ^bb8, ^bb12
  ^bb8:  // pred: ^bb7
    llvm.br ^bb9(%3 : i64)
  ^bb9(%113: i64):  // 2 preds: ^bb8, ^bb10
    %114 = llvm.icmp "slt" %113, %0 : i64
    llvm.cond_br %114, ^bb10, ^bb11
  ^bb10:  // pred: ^bb9
    %115 = llvm.mlir.constant(3 : index) : i64
    %116 = llvm.mul %111, %115  : i64
    %117 = llvm.add %116, %113  : i64
    %118 = llvm.getelementptr %12[%117] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %119 = llvm.load %118 : !llvm.ptr -> f32
    %120 = llvm.add %111, %3  : i64
    %121 = llvm.getelementptr %47[%120] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %122 = llvm.load %121 : !llvm.ptr -> f32
    %123 = llvm.fadd %119, %122  : f32
    %124 = llvm.mlir.constant(3 : index) : i64
    %125 = llvm.mul %111, %124  : i64
    %126 = llvm.add %125, %113  : i64
    %127 = llvm.getelementptr %83[%126] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    llvm.store %123, %127 : f32, !llvm.ptr
    %128 = llvm.add %113, %2  : i64
    llvm.br ^bb9(%128 : i64)
  ^bb11:  // pred: ^bb9
    %129 = llvm.add %111, %2  : i64
    llvm.br ^bb7(%129 : i64)
  ^bb12:  // pred: ^bb7
    %130 = llvm.mlir.constant(3 : index) : i64
    %131 = llvm.mul %3, %130  : i64
    %132 = llvm.add %131, %1  : i64
    %133 = llvm.getelementptr %66[%132] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %134 = llvm.load %133 : !llvm.ptr -> f32
    %135 = llvm.mlir.constant(3 : index) : i64
    %136 = llvm.mul %2, %135  : i64
    %137 = llvm.add %136, %2  : i64
    %138 = llvm.getelementptr %66[%137] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %139 = llvm.load %138 : !llvm.ptr -> f32
    %140 = llvm.mlir.constant(3 : index) : i64
    %141 = llvm.mul %3, %140  : i64
    %142 = llvm.add %141, %3  : i64
    %143 = llvm.getelementptr %83[%142] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %144 = llvm.load %143 : !llvm.ptr -> f32
    %145 = llvm.mlir.constant(3 : index) : i64
    %146 = llvm.mul %2, %145  : i64
    %147 = llvm.add %146, %1  : i64
    %148 = llvm.getelementptr %83[%147] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %149 = llvm.load %148 : !llvm.ptr -> f32
    llvm.call @printF32(%134) : (f32) -> ()
    llvm.call @printNewline() : () -> ()
    llvm.call @printF32(%139) : (f32) -> ()
    llvm.call @printNewline() : () -> ()
    llvm.call @printF32(%144) : (f32) -> ()
    llvm.call @printNewline() : () -> ()
    llvm.call @printF32(%149) : (f32) -> ()
    llvm.call @printNewline() : () -> ()
    llvm.return
  }
}

