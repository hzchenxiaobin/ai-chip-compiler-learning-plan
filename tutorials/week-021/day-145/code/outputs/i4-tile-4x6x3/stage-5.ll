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

47:                                               ; preds = %90, %19
  %48 = phi i64 [ %91, %90 ], [ 0, %19 ]
  %49 = icmp slt i64 %48, 6
  br i1 %49, label %50, label %92

50:                                               ; preds = %47
  br label %51

51:                                               ; preds = %88, %50
  %52 = phi i64 [ %89, %88 ], [ 0, %50 ]
  %53 = icmp slt i64 %52, 4
  br i1 %53, label %54, label %90

54:                                               ; preds = %51
  br label %55

55:                                               ; preds = %80, %54
  %56 = phi i64 [ %87, %80 ], [ 0, %54 ]
  %57 = icmp slt i64 %56, 3
  br i1 %57, label %58, label %88

58:                                               ; preds = %55
  %59 = extractvalue { ptr, ptr, i64, [1 x i64], [1 x i64] } %24, 1
  %60 = getelementptr inbounds nuw float, ptr %59, i64 %56
  %61 = load float, ptr %60, align 4
  br label %62

62:                                               ; preds = %66, %58
  %63 = phi i64 [ %79, %66 ], [ 0, %58 ]
  %64 = phi float [ %78, %66 ], [ %61, %58 ]
  %65 = icmp slt i64 %63, 6
  br i1 %65, label %66, label %80

66:                                               ; preds = %62
  %67 = extractvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %38, 1
  %68 = mul nuw nsw i64 %52, 6
  %69 = add nuw nsw i64 %68, %63
  %70 = getelementptr inbounds nuw float, ptr %67, i64 %69
  %71 = load float, ptr %70, align 4
  %72 = extractvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %31, 1
  %73 = mul nuw nsw i64 %63, 3
  %74 = add nuw nsw i64 %73, %56
  %75 = getelementptr inbounds nuw float, ptr %72, i64 %74
  %76 = load float, ptr %75, align 4
  %77 = fmul float %71, %76
  %78 = fadd float %64, %77
  %79 = add i64 %63, 1
  br label %62

80:                                               ; preds = %62
  %81 = fcmp ogt float %64, 0.000000e+00
  %82 = select i1 %81, float %64, float 0.000000e+00
  %83 = extractvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %46, 1
  %84 = mul nuw nsw i64 %52, 3
  %85 = add nuw nsw i64 %84, %56
  %86 = getelementptr inbounds nuw float, ptr %83, i64 %85
  store float %82, ptr %86, align 4
  %87 = add i64 %56, 1
  br label %55

88:                                               ; preds = %55
  %89 = add i64 %52, 1
  br label %51

90:                                               ; preds = %51
  %91 = add i64 %48, 3
  br label %47

92:                                               ; preds = %47
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
