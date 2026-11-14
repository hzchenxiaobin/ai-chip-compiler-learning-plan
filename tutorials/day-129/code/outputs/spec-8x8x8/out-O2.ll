; ModuleID = '/Users/chenbinbin/GitHub/ai-chip-compiler-learning-plan/tutorials/day-129/code/outputs/spec-8x8x8/out.ll'
source_filename = "LLVMDialectModule"

; Function Attrs: mustprogress nofree nounwind willreturn allockind("alloc,uninitialized") allocsize(0) memory(inaccessiblemem: readwrite, errnomem: write)
declare noalias noundef ptr @malloc(i64 noundef) local_unnamed_addr #0

; Function Attrs: nofree nounwind memory(write, argmem: read, inaccessiblemem: readwrite, target_mem: none)
define { ptr, ptr, i64, [2 x i64], [2 x i64] } @kernel_s8x8x8(ptr nofree readnone captures(none) %0, ptr nofree readonly captures(none) %1, i64 %2, i64 %3, i64 %4, i64 %5, i64 %6, ptr nofree readnone captures(none) %7, ptr nofree readonly captures(none) %8, i64 %9, i64 %10, i64 %11, i64 %12, i64 %13) local_unnamed_addr #1 {
  %15 = tail call dereferenceable_or_null(256) ptr @malloc(i64 256)
  br label %.preheader3

.preheader3:                                      ; preds = %14, %48
  %16 = phi i64 [ 0, %14 ], [ %49, %48 ]
  %.idx1 = shl nuw nsw i64 %16, 5
  %17 = getelementptr inbounds nuw i8, ptr %1, i64 %.idx1
  %18 = getelementptr inbounds nuw i8, ptr %15, i64 %.idx1
  %.pre = load float, ptr %17, align 4
  %.phi.trans.insert = getelementptr inbounds nuw i8, ptr %17, i64 4
  %.phi.trans.insert7 = getelementptr inbounds nuw i8, ptr %17, i64 12
  %19 = load <2 x float>, ptr %.phi.trans.insert, align 4
  %20 = load <4 x float>, ptr %.phi.trans.insert7, align 4
  %.phi.trans.insert15 = getelementptr inbounds nuw i8, ptr %17, i64 28
  %.pre16 = load float, ptr %.phi.trans.insert15, align 4
  %21 = insertelement <8 x float> <float poison, float 1.000000e+00, float poison, float poison, float poison, float poison, float poison, float poison>, float %.pre, i64 0
  %22 = shufflevector <4 x float> %20, <4 x float> poison, <8 x i32> <i32 0, i32 1, i32 2, i32 3, i32 poison, i32 poison, i32 poison, i32 poison>
  %23 = shufflevector <8 x float> %21, <8 x float> %22, <8 x i32> <i32 0, i32 1, i32 poison, i32 poison, i32 8, i32 9, i32 10, i32 11>
  %24 = shufflevector <2 x float> %19, <2 x float> poison, <8 x i32> <i32 0, i32 1, i32 poison, i32 poison, i32 poison, i32 poison, i32 poison, i32 poison>
  %25 = shufflevector <8 x float> %23, <8 x float> %24, <8 x i32> <i32 0, i32 1, i32 8, i32 9, i32 4, i32 5, i32 6, i32 7>
  br label %.preheader

.preheader:                                       ; preds = %.preheader3, %.preheader
  %26 = phi i64 [ 0, %.preheader3 ], [ %46, %.preheader ]
  %invariant.gep = getelementptr [4 x i8], ptr %8, i64 %26
  %27 = load float, ptr %invariant.gep, align 4
  %gep.1 = getelementptr i8, ptr %invariant.gep, i64 32
  %28 = load float, ptr %gep.1, align 4
  %gep.2 = getelementptr i8, ptr %invariant.gep, i64 64
  %29 = load float, ptr %gep.2, align 4
  %gep.3 = getelementptr i8, ptr %invariant.gep, i64 96
  %30 = load float, ptr %gep.3, align 4
  %gep.4 = getelementptr i8, ptr %invariant.gep, i64 128
  %31 = load float, ptr %gep.4, align 4
  %gep.5 = getelementptr i8, ptr %invariant.gep, i64 160
  %32 = load float, ptr %gep.5, align 4
  %gep.6 = getelementptr i8, ptr %invariant.gep, i64 192
  %33 = load float, ptr %gep.6, align 4
  %34 = insertelement <8 x float> <float poison, float 0.000000e+00, float poison, float poison, float poison, float poison, float poison, float poison>, float %27, i64 0
  %35 = insertelement <8 x float> %34, float %28, i64 2
  %36 = insertelement <8 x float> %35, float %29, i64 3
  %37 = insertelement <8 x float> %36, float %30, i64 4
  %38 = insertelement <8 x float> %37, float %31, i64 5
  %39 = insertelement <8 x float> %38, float %32, i64 6
  %40 = insertelement <8 x float> %39, float %33, i64 7
  %41 = fmul <8 x float> %40, %25
  %gep.7 = getelementptr i8, ptr %invariant.gep, i64 224
  %42 = load float, ptr %gep.7, align 4
  %43 = fmul float %.pre16, %42
  %44 = tail call float @llvm.vector.reduce.fadd.v8f32(float -0.000000e+00, <8 x float> %41)
  %op.rdx = fadd float %44, %43
  %45 = getelementptr inbounds nuw [4 x i8], ptr %18, i64 %26
  store float %op.rdx, ptr %45, align 4
  %46 = add nuw nsw i64 %26, 1
  %47 = icmp samesign ult i64 %26, 7
  br i1 %47, label %.preheader, label %48

48:                                               ; preds = %.preheader
  %49 = add nuw nsw i64 %16, 1
  %50 = icmp samesign ult i64 %16, 7
  br i1 %50, label %.preheader3, label %51

51:                                               ; preds = %48
  %52 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } poison, ptr %15, 0
  %53 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %52, ptr %15, 1
  %54 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %53, i64 0, 2
  %55 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %54, i64 8, 3, 0
  %56 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %55, i64 8, 3, 1
  %57 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %56, i64 8, 4, 0
  %58 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %57, i64 1, 4, 1
  ret { ptr, ptr, i64, [2 x i64], [2 x i64] } %58
}

; Function Attrs: nofree nounwind memory(readwrite, target_mem: none)
define void @_mlir_ciface_kernel_s8x8x8(ptr nofree writeonly captures(none) %0, ptr nofree readonly captures(none) %1, ptr nofree readonly captures(none) %2) local_unnamed_addr #2 {
  %.elt1 = getelementptr inbounds nuw i8, ptr %1, i64 8
  %.unpack2 = load ptr, ptr %.elt1, align 8
  %.elt16 = getelementptr inbounds nuw i8, ptr %2, i64 8
  %.unpack17 = load ptr, ptr %.elt16, align 8
  %4 = tail call dereferenceable_or_null(256) ptr @malloc(i64 256)
  br label %.preheader3.i

.preheader3.i:                                    ; preds = %37, %3
  %5 = phi i64 [ 0, %3 ], [ %38, %37 ]
  %.idx1.i = shl nuw nsw i64 %5, 5
  %6 = getelementptr inbounds nuw i8, ptr %.unpack2, i64 %.idx1.i
  %7 = getelementptr inbounds nuw i8, ptr %4, i64 %.idx1.i
  %.pre.i = load float, ptr %6, align 4
  %.phi.trans.insert.i = getelementptr inbounds nuw i8, ptr %6, i64 4
  %.phi.trans.insert7.i = getelementptr inbounds nuw i8, ptr %6, i64 12
  %8 = load <2 x float>, ptr %.phi.trans.insert.i, align 4
  %9 = load <4 x float>, ptr %.phi.trans.insert7.i, align 4
  %.phi.trans.insert15.i = getelementptr inbounds nuw i8, ptr %6, i64 28
  %.pre16.i = load float, ptr %.phi.trans.insert15.i, align 4
  %10 = insertelement <8 x float> <float poison, float 1.000000e+00, float poison, float poison, float poison, float poison, float poison, float poison>, float %.pre.i, i64 0
  %11 = shufflevector <4 x float> %9, <4 x float> poison, <8 x i32> <i32 0, i32 1, i32 2, i32 3, i32 poison, i32 poison, i32 poison, i32 poison>
  %12 = shufflevector <8 x float> %10, <8 x float> %11, <8 x i32> <i32 0, i32 1, i32 poison, i32 poison, i32 8, i32 9, i32 10, i32 11>
  %13 = shufflevector <2 x float> %8, <2 x float> poison, <8 x i32> <i32 0, i32 1, i32 poison, i32 poison, i32 poison, i32 poison, i32 poison, i32 poison>
  %14 = shufflevector <8 x float> %12, <8 x float> %13, <8 x i32> <i32 0, i32 1, i32 8, i32 9, i32 4, i32 5, i32 6, i32 7>
  br label %.preheader.i

.preheader.i:                                     ; preds = %.preheader.i, %.preheader3.i
  %15 = phi i64 [ 0, %.preheader3.i ], [ %35, %.preheader.i ]
  %invariant.gep.i = getelementptr [4 x i8], ptr %.unpack17, i64 %15
  %16 = load float, ptr %invariant.gep.i, align 4
  %gep.1.i = getelementptr i8, ptr %invariant.gep.i, i64 32
  %17 = load float, ptr %gep.1.i, align 4
  %gep.2.i = getelementptr i8, ptr %invariant.gep.i, i64 64
  %18 = load float, ptr %gep.2.i, align 4
  %gep.3.i = getelementptr i8, ptr %invariant.gep.i, i64 96
  %19 = load float, ptr %gep.3.i, align 4
  %gep.4.i = getelementptr i8, ptr %invariant.gep.i, i64 128
  %20 = load float, ptr %gep.4.i, align 4
  %gep.5.i = getelementptr i8, ptr %invariant.gep.i, i64 160
  %21 = load float, ptr %gep.5.i, align 4
  %gep.6.i = getelementptr i8, ptr %invariant.gep.i, i64 192
  %22 = load float, ptr %gep.6.i, align 4
  %23 = insertelement <8 x float> <float poison, float 0.000000e+00, float poison, float poison, float poison, float poison, float poison, float poison>, float %16, i64 0
  %24 = insertelement <8 x float> %23, float %17, i64 2
  %25 = insertelement <8 x float> %24, float %18, i64 3
  %26 = insertelement <8 x float> %25, float %19, i64 4
  %27 = insertelement <8 x float> %26, float %20, i64 5
  %28 = insertelement <8 x float> %27, float %21, i64 6
  %29 = insertelement <8 x float> %28, float %22, i64 7
  %30 = fmul <8 x float> %29, %14
  %gep.7.i = getelementptr i8, ptr %invariant.gep.i, i64 224
  %31 = load float, ptr %gep.7.i, align 4
  %32 = fmul float %.pre16.i, %31
  %33 = tail call float @llvm.vector.reduce.fadd.v8f32(float -0.000000e+00, <8 x float> %30)
  %op.rdx = fadd float %33, %32
  %34 = getelementptr inbounds nuw [4 x i8], ptr %7, i64 %15
  store float %op.rdx, ptr %34, align 4
  %35 = add nuw nsw i64 %15, 1
  %36 = icmp samesign ult i64 %15, 7
  br i1 %36, label %.preheader.i, label %37

37:                                               ; preds = %.preheader.i
  %38 = add nuw nsw i64 %5, 1
  %39 = icmp samesign ult i64 %5, 7
  br i1 %39, label %.preheader3.i, label %kernel_s8x8x8.exit

kernel_s8x8x8.exit:                               ; preds = %37
  store ptr %4, ptr %0, align 8
  %.repack30 = getelementptr inbounds nuw i8, ptr %0, i64 8
  store ptr %4, ptr %.repack30, align 8
  %.repack32 = getelementptr inbounds nuw i8, ptr %0, i64 16
  store i64 0, ptr %.repack32, align 8
  %.repack34 = getelementptr inbounds nuw i8, ptr %0, i64 24
  store i64 8, ptr %.repack34, align 8
  %.repack34.repack38 = getelementptr inbounds nuw i8, ptr %0, i64 32
  store i64 8, ptr %.repack34.repack38, align 8
  %.repack36 = getelementptr inbounds nuw i8, ptr %0, i64 40
  store i64 8, ptr %.repack36, align 8
  %.repack36.repack40 = getelementptr inbounds nuw i8, ptr %0, i64 48
  store i64 1, ptr %.repack36.repack40, align 8
  ret void
}

; Function Attrs: nocallback nocreateundeforpoison nofree nosync nounwind speculatable willreturn memory(none)
declare float @llvm.vector.reduce.fadd.v8f32(float, <8 x float>) #3

attributes #0 = { mustprogress nofree nounwind willreturn allockind("alloc,uninitialized") allocsize(0) memory(inaccessiblemem: readwrite, errnomem: write) "alloc-family"="malloc" }
attributes #1 = { nofree nounwind memory(write, argmem: read, inaccessiblemem: readwrite, target_mem: none) }
attributes #2 = { nofree nounwind memory(readwrite, target_mem: none) }
attributes #3 = { nocallback nocreateundeforpoison nofree nosync nounwind speculatable willreturn memory(none) }

!llvm.module.flags = !{!0}

!0 = !{i32 2, !"Debug Info Version", i32 3}
