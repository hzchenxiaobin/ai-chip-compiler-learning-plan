; ModuleID = 'LLVMDialectModule'
source_filename = "LLVMDialectModule"

declare ptr @malloc(i64)

define { ptr, ptr, i64, [2 x i64], [2 x i64] } @kernel_tiled(ptr %0, ptr %1, i64 %2, i64 %3, i64 %4, i64 %5, i64 %6, ptr %7, ptr %8, i64 %9, i64 %10, i64 %11, i64 %12, i64 %13) {
  %15 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } poison, ptr %7, 0
  %16 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %15, ptr %8, 1
  %17 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %16, i64 %9, 2
  %18 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %17, i64 %10, 3, 0
  %19 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %18, i64 %12, 4, 0
  %20 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %19, i64 %11, 3, 1
  %21 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %20, i64 %13, 4, 1
  %22 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } poison, ptr %0, 0
  %23 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %22, ptr %1, 1
  %24 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %23, i64 %2, 2
  %25 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %24, i64 %3, 3, 0
  %26 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %25, i64 %5, 4, 0
  %27 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %26, i64 %4, 3, 1
  %28 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %27, i64 %6, 4, 1
  %29 = call ptr @malloc(i64 48)
  %30 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } poison, ptr %29, 0
  %31 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %30, ptr %29, 1
  %32 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %31, i64 0, 2
  %33 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %32, i64 4, 3, 0
  %34 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %33, i64 3, 3, 1
  %35 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %34, i64 3, 4, 0
  %36 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %35, i64 1, 4, 1
  br label %37

37:                                               ; preds = %88, %14
  %38 = phi i64 [ %89, %88 ], [ 0, %14 ]
  %39 = icmp slt i64 %38, 4
  br i1 %39, label %40, label %90

40:                                               ; preds = %37
  br label %41

41:                                               ; preds = %86, %40
  %42 = phi i64 [ %87, %86 ], [ 0, %40 ]
  %43 = icmp slt i64 %42, 3
  br i1 %43, label %44, label %88

44:                                               ; preds = %41
  br label %45

45:                                               ; preds = %84, %44
  %46 = phi i64 [ %85, %84 ], [ 0, %44 ]
  %47 = icmp slt i64 %46, 6
  br i1 %47, label %48, label %86

48:                                               ; preds = %45
  %49 = call i64 @llvm.smin.i64(i64 %38, i64 4)
  br label %50

50:                                               ; preds = %82, %48
  %51 = phi i64 [ %83, %82 ], [ %38, %48 ]
  %52 = icmp slt i64 %51, %49
  br i1 %52, label %53, label %84

53:                                               ; preds = %50
  br label %54

54:                                               ; preds = %76, %53
  %55 = phi i64 [ %81, %76 ], [ %42, %53 ]
  %56 = icmp slt i64 %55, 3
  br i1 %56, label %57, label %82

57:                                               ; preds = %54
  br label %58

58:                                               ; preds = %62, %57
  %59 = phi i64 [ %75, %62 ], [ %46, %57 ]
  %60 = phi float [ %74, %62 ], [ 0.000000e+00, %57 ]
  %61 = icmp slt i64 %59, 6
  br i1 %61, label %62, label %76

62:                                               ; preds = %58
  %63 = extractvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %28, 1
  %64 = mul nuw nsw i64 %51, 6
  %65 = add nuw nsw i64 %64, %59
  %66 = getelementptr inbounds nuw float, ptr %63, i64 %65
  %67 = load float, ptr %66, align 4
  %68 = extractvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %21, 1
  %69 = mul nuw nsw i64 %59, 3
  %70 = add nuw nsw i64 %69, %55
  %71 = getelementptr inbounds nuw float, ptr %68, i64 %70
  %72 = load float, ptr %71, align 4
  %73 = fmul float %67, %72
  %74 = fadd float %60, %73
  %75 = add i64 %59, 1
  br label %58

76:                                               ; preds = %58
  %77 = extractvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %36, 1
  %78 = mul nuw nsw i64 %51, 3
  %79 = add nuw nsw i64 %78, %55
  %80 = getelementptr inbounds nuw float, ptr %77, i64 %79
  store float %60, ptr %80, align 4
  %81 = add i64 %55, 1
  br label %54

82:                                               ; preds = %54
  %83 = add i64 %51, 1
  br label %50

84:                                               ; preds = %50
  %85 = add i64 %46, 3
  br label %45

86:                                               ; preds = %45
  %87 = add i64 %42, 2
  br label %41

88:                                               ; preds = %41
  %89 = add i64 %38, 2
  br label %37

90:                                               ; preds = %37
  ret { ptr, ptr, i64, [2 x i64], [2 x i64] } %36
}

define void @_mlir_ciface_kernel_tiled(ptr %0, ptr %1, ptr %2) {
  %4 = load { ptr, ptr, i64, [2 x i64], [2 x i64] }, ptr %1, align 8
  %5 = extractvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %4, 0
  %6 = extractvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %4, 1
  %7 = extractvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %4, 2
  %8 = extractvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %4, 3, 0
  %9 = extractvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %4, 3, 1
  %10 = extractvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %4, 4, 0
  %11 = extractvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %4, 4, 1
  %12 = load { ptr, ptr, i64, [2 x i64], [2 x i64] }, ptr %2, align 8
  %13 = extractvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %12, 0
  %14 = extractvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %12, 1
  %15 = extractvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %12, 2
  %16 = extractvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %12, 3, 0
  %17 = extractvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %12, 3, 1
  %18 = extractvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %12, 4, 0
  %19 = extractvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %12, 4, 1
  %20 = call { ptr, ptr, i64, [2 x i64], [2 x i64] } @kernel_tiled(ptr %5, ptr %6, i64 %7, i64 %8, i64 %9, i64 %10, i64 %11, ptr %13, ptr %14, i64 %15, i64 %16, i64 %17, i64 %18, i64 %19)
  store { ptr, ptr, i64, [2 x i64], [2 x i64] } %20, ptr %0, align 8
  ret void
}

; Function Attrs: nocallback nocreateundeforpoison nofree nosync nounwind speculatable willreturn memory(none)
declare i64 @llvm.smin.i64(i64, i64) #0

attributes #0 = { nocallback nocreateundeforpoison nofree nosync nounwind speculatable willreturn memory(none) }

!llvm.module.flags = !{!0}

!0 = !{i32 2, !"Debug Info Version", i32 3}
