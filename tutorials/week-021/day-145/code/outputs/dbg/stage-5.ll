; ModuleID = 'LLVMDialectModule'
source_filename = "LLVMDialectModule"

declare ptr @malloc(i64)

define { ptr, ptr, i64, [2 x i64], [2 x i64] } @main_kernel(ptr %0, ptr %1, i64 %2, i64 %3, i64 %4, i64 %5, i64 %6, ptr %7, ptr %8, i64 %9, i64 %10, i64 %11, i64 %12, i64 %13, ptr %14, ptr %15, i64 %16, i64 %17, i64 %18) {
  %20 = insertvalue { ptr, ptr, i64, [1 x i64], [1 x i64] } poison, ptr %14, 0
  %21 = insertvalue { ptr, ptr, i64, [1 x i64], [1 x i64] } %20, ptr %15, 1
  %22 = insertvalue { ptr, ptr, i64, [1 x i64], [1 x i64] } %21, i64 %16, 2
  %23 = insertvalue { ptr, ptr, i64, [1 x i64], [1 x i64] } %22, i64 %17, 3, 0
  %24 = insertvalue { ptr, ptr, i64, [1 x i64], [1 x i64] } %23, i64 %18, 4, 0
  %25 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } poison, ptr %7, 0
  %26 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %25, ptr %8, 1
  %27 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %26, i64 %9, 2
  %28 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %27, i64 %10, 3, 0
  %29 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %28, i64 %12, 4, 0
  %30 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %29, i64 %11, 3, 1
  %31 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %30, i64 %13, 4, 1
  %32 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } poison, ptr %0, 0
  %33 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %32, ptr %1, 1
  %34 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %33, i64 %2, 2
  %35 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %34, i64 %3, 3, 0
  %36 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %35, i64 %5, 4, 0
  %37 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %36, i64 %4, 3, 1
  %38 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %37, i64 %6, 4, 1
  %39 = call ptr @malloc(i64 48)
  %40 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } poison, ptr %39, 0
  %41 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %40, ptr %39, 1
  %42 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %41, i64 0, 2
  %43 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %42, i64 4, 3, 0
  %44 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %43, i64 3, 3, 1
  %45 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %44, i64 3, 4, 0
  %46 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %45, i64 1, 4, 1
  br label %47

47:                                               ; preds = %102, %19
  %48 = phi i64 [ %103, %102 ], [ 0, %19 ]
  %49 = icmp slt i64 %48, 4
  br i1 %49, label %50, label %104

50:                                               ; preds = %47
  br label %51

51:                                               ; preds = %100, %50
  %52 = phi i64 [ %101, %100 ], [ 0, %50 ]
  %53 = icmp slt i64 %52, 3
  br i1 %53, label %54, label %102

54:                                               ; preds = %51
  br label %55

55:                                               ; preds = %98, %54
  %56 = phi i64 [ %99, %98 ], [ 0, %54 ]
  %57 = icmp slt i64 %56, 6
  br i1 %57, label %58, label %100

58:                                               ; preds = %55
  br label %59

59:                                               ; preds = %96, %58
  %60 = phi i64 [ %97, %96 ], [ %48, %58 ]
  %61 = icmp slt i64 %60, 4
  br i1 %61, label %62, label %98

62:                                               ; preds = %59
  br label %63

63:                                               ; preds = %88, %62
  %64 = phi i64 [ %95, %88 ], [ %52, %62 ]
  %65 = icmp slt i64 %64, 3
  br i1 %65, label %66, label %96

66:                                               ; preds = %63
  %67 = extractvalue { ptr, ptr, i64, [1 x i64], [1 x i64] } %24, 1
  %68 = getelementptr inbounds nuw float, ptr %67, i64 %64
  %69 = load float, ptr %68, align 4
  br label %70

70:                                               ; preds = %74, %66
  %71 = phi i64 [ %87, %74 ], [ %56, %66 ]
  %72 = phi float [ %86, %74 ], [ %69, %66 ]
  %73 = icmp slt i64 %71, 6
  br i1 %73, label %74, label %88

74:                                               ; preds = %70
  %75 = extractvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %38, 1
  %76 = mul nuw nsw i64 %60, 6
  %77 = add nuw nsw i64 %76, %71
  %78 = getelementptr inbounds nuw float, ptr %75, i64 %77
  %79 = load float, ptr %78, align 4
  %80 = extractvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %31, 1
  %81 = mul nuw nsw i64 %71, 3
  %82 = add nuw nsw i64 %81, %64
  %83 = getelementptr inbounds nuw float, ptr %80, i64 %82
  %84 = load float, ptr %83, align 4
  %85 = fmul float %79, %84
  %86 = fadd float %72, %85
  %87 = add i64 %71, 1
  br label %70

88:                                               ; preds = %70
  %89 = fcmp ogt float %72, 0.000000e+00
  %90 = select i1 %89, float %72, float 0.000000e+00
  %91 = extractvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %46, 1
  %92 = mul nuw nsw i64 %60, 3
  %93 = add nuw nsw i64 %92, %64
  %94 = getelementptr inbounds nuw float, ptr %91, i64 %93
  store float %90, ptr %94, align 4
  %95 = add i64 %64, 1
  br label %63

96:                                               ; preds = %63
  %97 = add i64 %60, 1
  br label %59

98:                                               ; preds = %59
  %99 = add i64 %56, 3
  br label %55

100:                                              ; preds = %55
  %101 = add i64 %52, 2
  br label %51

102:                                              ; preds = %51
  %103 = add i64 %48, 2
  br label %47

104:                                              ; preds = %47
  ret { ptr, ptr, i64, [2 x i64], [2 x i64] } %46
}

define void @_mlir_ciface_main_kernel(ptr %0, ptr %1, ptr %2, ptr %3) {
  %5 = load { ptr, ptr, i64, [2 x i64], [2 x i64] }, ptr %1, align 8
  %6 = extractvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %5, 0
  %7 = extractvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %5, 1
  %8 = extractvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %5, 2
  %9 = extractvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %5, 3, 0
  %10 = extractvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %5, 3, 1
  %11 = extractvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %5, 4, 0
  %12 = extractvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %5, 4, 1
  %13 = load { ptr, ptr, i64, [2 x i64], [2 x i64] }, ptr %2, align 8
  %14 = extractvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %13, 0
  %15 = extractvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %13, 1
  %16 = extractvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %13, 2
  %17 = extractvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %13, 3, 0
  %18 = extractvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %13, 3, 1
  %19 = extractvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %13, 4, 0
  %20 = extractvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %13, 4, 1
  %21 = load { ptr, ptr, i64, [1 x i64], [1 x i64] }, ptr %3, align 8
  %22 = extractvalue { ptr, ptr, i64, [1 x i64], [1 x i64] } %21, 0
  %23 = extractvalue { ptr, ptr, i64, [1 x i64], [1 x i64] } %21, 1
  %24 = extractvalue { ptr, ptr, i64, [1 x i64], [1 x i64] } %21, 2
  %25 = extractvalue { ptr, ptr, i64, [1 x i64], [1 x i64] } %21, 3, 0
  %26 = extractvalue { ptr, ptr, i64, [1 x i64], [1 x i64] } %21, 4, 0
  %27 = call { ptr, ptr, i64, [2 x i64], [2 x i64] } @main_kernel(ptr %6, ptr %7, i64 %8, i64 %9, i64 %10, i64 %11, i64 %12, ptr %14, ptr %15, i64 %16, i64 %17, i64 %18, i64 %19, i64 %20, ptr %22, ptr %23, i64 %24, i64 %25, i64 %26)
  store { ptr, ptr, i64, [2 x i64], [2 x i64] } %27, ptr %0, align 8
  ret void
}

!llvm.module.flags = !{!0}

!0 = !{i32 2, !"Debug Info Version", i32 3}
