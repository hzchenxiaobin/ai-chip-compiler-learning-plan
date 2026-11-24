; ModuleID = 'LLVMDialectModule'
source_filename = "LLVMDialectModule"

declare ptr @malloc(i64)

define { ptr, ptr, i64, [2 x i64], [2 x i64] } @gemm(ptr %0, ptr %1, i64 %2, i64 %3, i64 %4, i64 %5, i64 %6, ptr %7, ptr %8, i64 %9, i64 %10, i64 %11, i64 %12, i64 %13) {
  %15 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } undef, ptr %0, 0
  %16 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %15, ptr %1, 1
  %17 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %16, i64 %2, 2
  %18 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %17, i64 %3, 3, 0
  %19 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %18, i64 %5, 4, 0
  %20 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %19, i64 %4, 3, 1
  %21 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %20, i64 %6, 4, 1
  %22 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } undef, ptr %7, 0
  %23 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %22, ptr %8, 1
  %24 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %23, i64 %9, 2
  %25 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %24, i64 %10, 3, 0
  %26 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %25, i64 %12, 4, 0
  %27 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %26, i64 %11, 3, 1
  %28 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %27, i64 %13, 4, 1
  %29 = call ptr @malloc(i64 ptrtoint (ptr getelementptr (float, ptr null, i32 12) to i64))
  %30 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } undef, ptr %29, 0
  %31 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %30, ptr %29, 1
  %32 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %31, i64 0, 2
  %33 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %32, i64 4, 3, 0
  %34 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %33, i64 3, 3, 1
  %35 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %34, i64 3, 4, 0
  %36 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %35, i64 1, 4, 1
  br label %37

37:                                               ; preds = %66, %14
  %38 = phi i64 [ %67, %66 ], [ 0, %14 ]
  %39 = icmp slt i64 %38, 4
  br i1 %39, label %40, label %68

40:                                               ; preds = %37
  br label %41

41:                                               ; preds = %61, %40
  %42 = phi i64 [ %65, %61 ], [ 0, %40 ]
  %43 = icmp slt i64 %42, 3
  br i1 %43, label %44, label %66

44:                                               ; preds = %41
  br label %45

45:                                               ; preds = %49, %44
  %46 = phi i64 [ %60, %49 ], [ 0, %44 ]
  %47 = phi float [ %59, %49 ], [ 0.000000e+00, %44 ]
  %48 = icmp slt i64 %46, 6
  br i1 %48, label %49, label %61

49:                                               ; preds = %45
  %50 = mul i64 %38, 6
  %51 = add i64 %50, %46
  %52 = getelementptr float, ptr %1, i64 %51
  %53 = load float, ptr %52, align 4
  %54 = mul i64 %46, 3
  %55 = add i64 %54, %42
  %56 = getelementptr float, ptr %8, i64 %55
  %57 = load float, ptr %56, align 4
  %58 = fmul float %53, %57
  %59 = fadd float %47, %58
  %60 = add i64 %46, 1
  br label %45

61:                                               ; preds = %45
  %62 = mul i64 %38, 3
  %63 = add i64 %62, %42
  %64 = getelementptr float, ptr %29, i64 %63
  store float %47, ptr %64, align 4
  %65 = add i64 %42, 1
  br label %41

66:                                               ; preds = %41
  %67 = add i64 %38, 1
  br label %37

68:                                               ; preds = %37
  ret { ptr, ptr, i64, [2 x i64], [2 x i64] } %36
}

define void @_mlir_ciface_gemm(ptr %0, ptr %1, ptr %2) {
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
  %20 = call { ptr, ptr, i64, [2 x i64], [2 x i64] } @gemm(ptr %5, ptr %6, i64 %7, i64 %8, i64 %9, i64 %10, i64 %11, ptr %13, ptr %14, i64 %15, i64 %16, i64 %17, i64 %18, i64 %19)
  store { ptr, ptr, i64, [2 x i64], [2 x i64] } %20, ptr %0, align 8
  ret void
}

!llvm.module.flags = !{!0}

!0 = !{i32 2, !"Debug Info Version", i32 3}
; 第 118 天路线 3：JIT——lli 解释执行入口。
; 与 gemm-3.ll 拼接成单模块（run_all.sh 完成 cat），lli 不产任何中间文件：
; parse ->（可选 opt）-> MCJIT 编译到内存 -> 执行 main。
; 数据以全局常量内嵌（教学规模）；描述符在全局区构造后传给包装函数。
@A = global [24 x float] [float 5.000000e-01, float -1.000000e+00, float 2.000000e+00, float 0.000000e+00, float 1.500000e+00, float -5.000000e-01,
                          float 1.000000e+00, float 1.000000e+00, float 1.000000e+00, float 1.000000e+00, float 1.000000e+00, float 1.000000e+00,
                          float -2.000000e+00, float 5.000000e-01, float 0.000000e+00, float 3.000000e+00, float -1.000000e+00, float 2.000000e+00,
                          float 0.000000e+00, float 0.000000e+00, float 5.000000e-01, float 5.000000e-01, float 5.000000e-01, float 5.000000e-01]
@B = global [18 x float] [float 1.000000e+00, float 2.000000e+00, float 3.000000e+00,
                          float 4.000000e+00, float 5.000000e+00, float 6.000000e+00,
                          float 7.000000e+00, float 8.000000e+00, float 9.000000e+00,
                          float 1.000000e+01, float 1.100000e+01, float 1.200000e+01,
                          float 1.300000e+01, float 1.400000e+01, float 1.500000e+01,
                          float 1.600000e+01, float 1.700000e+01, float 1.800000e+01]
@Adesc = global { ptr, ptr, i64, [2 x i64], [2 x i64] } { ptr @A, ptr @A, i64 0, [2 x i64] [i64 4, i64 6], [2 x i64] [i64 6, i64 1] }
@Bdesc = global { ptr, ptr, i64, [2 x i64], [2 x i64] } { ptr @B, ptr @B, i64 0, [2 x i64] [i64 6, i64 3], [2 x i64] [i64 3, i64 1] }
@Cdesc = global { ptr, ptr, i64, [2 x i64], [2 x i64] } zeroinitializer

@.fmt = private constant [12 x i8] c"C[%d]=%.2f\0A\00"
declare i32 @printf(ptr, ...)

define i32 @main() {
entry:
  call void @_mlir_ciface_gemm(ptr @Cdesc, ptr @Adesc, ptr @Bdesc)
  br label %loop
loop:
  %i = phi i64 [ 0, %entry ], [ %next, %body ]
  %done = icmp sge i64 %i, 12
  br i1 %done, label %exit, label %body
body:
  %cptr = load ptr, ptr @Cdesc                 ; 读回 kernel 填充的 malloc 指针
  %addr = getelementptr float, ptr %cptr, i64 %i
  %v = load float, ptr %addr
  %idx32 = trunc i64 %i to i32
  call i32 (ptr, ...) @printf(ptr @.fmt, i32 %idx32, float %v)
  %next = add i64 %i, 1
  br label %loop
exit:
  ret i32 0
}
