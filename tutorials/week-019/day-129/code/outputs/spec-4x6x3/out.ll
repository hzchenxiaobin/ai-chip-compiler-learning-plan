; ModuleID = 'LLVMDialectModule'
source_filename = "LLVMDialectModule"

declare ptr @malloc(i64)

define { ptr, ptr, i64, [2 x i64], [2 x i64] } @kernel_s4x6x3(ptr %0, ptr %1, i64 %2, i64 %3, i64 %4, i64 %5, i64 %6, ptr %7, ptr %8, i64 %9, i64 %10, i64 %11, i64 %12, i64 %13) {
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

37:                                               ; preds = %69, %14
  %38 = phi i64 [ %70, %69 ], [ 0, %14 ]
  %39 = icmp slt i64 %38, 4
  br i1 %39, label %40, label %71

40:                                               ; preds = %37
  br label %41

41:                                               ; preds = %63, %40
  %42 = phi i64 [ %68, %63 ], [ 0, %40 ]
  %43 = icmp slt i64 %42, 3
  br i1 %43, label %44, label %69

44:                                               ; preds = %41
  br label %45

45:                                               ; preds = %49, %44
  %46 = phi i64 [ %62, %49 ], [ 0, %44 ]
  %47 = phi float [ %61, %49 ], [ 0.000000e+00, %44 ]
  %48 = icmp slt i64 %46, 6
  br i1 %48, label %49, label %63

49:                                               ; preds = %45
  %50 = extractvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %28, 1
  %51 = mul nuw nsw i64 %38, 6
  %52 = add nuw nsw i64 %51, %46
  %53 = getelementptr inbounds nuw float, ptr %50, i64 %52
  %54 = load float, ptr %53, align 4
  %55 = extractvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %21, 1
  %56 = mul nuw nsw i64 %46, 3
  %57 = add nuw nsw i64 %56, %42
  %58 = getelementptr inbounds nuw float, ptr %55, i64 %57
  %59 = load float, ptr %58, align 4
  %60 = fmul float %54, %59
  %61 = fadd float %47, %60
  %62 = add i64 %46, 1
  br label %45

63:                                               ; preds = %45
  %64 = extractvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %36, 1
  %65 = mul nuw nsw i64 %38, 3
  %66 = add nuw nsw i64 %65, %42
  %67 = getelementptr inbounds nuw float, ptr %64, i64 %66
  store float %47, ptr %67, align 4
  %68 = add i64 %42, 1
  br label %41

69:                                               ; preds = %41
  %70 = add i64 %38, 1
  br label %37

71:                                               ; preds = %37
  ret { ptr, ptr, i64, [2 x i64], [2 x i64] } %36
}

define void @_mlir_ciface_kernel_s4x6x3(ptr %0, ptr %1, ptr %2) {
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
  %20 = call { ptr, ptr, i64, [2 x i64], [2 x i64] } @kernel_s4x6x3(ptr %5, ptr %6, i64 %7, i64 %8, i64 %9, i64 %10, i64 %11, ptr %13, ptr %14, i64 %15, i64 %16, i64 %17, i64 %18, i64 %19)
  store { ptr, ptr, i64, [2 x i64], [2 x i64] } %20, ptr %0, align 8
  ret void
}

!llvm.module.flags = !{!0}

!0 = !{i32 2, !"Debug Info Version", i32 3}
