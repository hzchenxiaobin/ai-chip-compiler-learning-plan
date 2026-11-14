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
  %39 = call ptr @malloc(i64 65536)
  %40 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } poison, ptr %39, 0
  %41 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %40, ptr %39, 1
  %42 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %41, i64 0, 2
  %43 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %42, i64 128, 3, 0
  %44 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %43, i64 128, 3, 1
  %45 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %44, i64 128, 4, 0
  %46 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %45, i64 1, 4, 1
  br label %47

47:                                               ; preds = %84, %19
  %48 = phi i64 [ %85, %84 ], [ 0, %19 ]
  %49 = icmp slt i64 %48, 128
  br i1 %49, label %50, label %86

50:                                               ; preds = %47
  br label %51

51:                                               ; preds = %76, %50
  %52 = phi i64 [ %83, %76 ], [ 0, %50 ]
  %53 = icmp slt i64 %52, 128
  br i1 %53, label %54, label %84

54:                                               ; preds = %51
  %55 = extractvalue { ptr, ptr, i64, [1 x i64], [1 x i64] } %24, 1
  %56 = getelementptr inbounds nuw float, ptr %55, i64 %52
  %57 = load float, ptr %56, align 4
  br label %58

58:                                               ; preds = %62, %54
  %59 = phi i64 [ %75, %62 ], [ 0, %54 ]
  %60 = phi float [ %74, %62 ], [ %57, %54 ]
  %61 = icmp slt i64 %59, 128
  br i1 %61, label %62, label %76

62:                                               ; preds = %58
  %63 = extractvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %38, 1
  %64 = mul nuw nsw i64 %48, 128
  %65 = add nuw nsw i64 %64, %59
  %66 = getelementptr inbounds nuw float, ptr %63, i64 %65
  %67 = load float, ptr %66, align 4
  %68 = extractvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %31, 1
  %69 = mul nuw nsw i64 %59, 128
  %70 = add nuw nsw i64 %69, %52
  %71 = getelementptr inbounds nuw float, ptr %68, i64 %70
  %72 = load float, ptr %71, align 4
  %73 = fmul float %67, %72
  %74 = fadd float %60, %73
  %75 = add i64 %59, 1
  br label %58

76:                                               ; preds = %58
  %77 = fcmp ogt float %60, 0.000000e+00
  %78 = select i1 %77, float %60, float 0.000000e+00
  %79 = extractvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %46, 1
  %80 = mul nuw nsw i64 %48, 128
  %81 = add nuw nsw i64 %80, %52
  %82 = getelementptr inbounds nuw float, ptr %79, i64 %81
  store float %78, ptr %82, align 4
  %83 = add i64 %52, 1
  br label %51

84:                                               ; preds = %51
  %85 = add i64 %48, 1
  br label %47

86:                                               ; preds = %47
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
