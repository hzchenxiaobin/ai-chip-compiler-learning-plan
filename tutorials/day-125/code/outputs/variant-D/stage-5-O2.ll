; ModuleID = 'outputs/variant-D/stage-5.ll'
source_filename = "LLVMDialectModule"

; Function Attrs: mustprogress nofree nounwind willreturn allockind("alloc,uninitialized") allocsize(0) memory(inaccessiblemem: readwrite, errnomem: write)
declare noalias noundef ptr @malloc(i64 noundef) local_unnamed_addr #0

; Function Attrs: nofree nounwind memory(write, argmem: read, inaccessiblemem: readwrite, target_mem: none)
define { ptr, ptr, i64, [2 x i64], [2 x i64] } @main_kernel(ptr nofree readnone captures(none) %0, ptr nofree readonly captures(none) %1, i64 %2, i64 %3, i64 %4, i64 %5, i64 %6, ptr nofree readnone captures(none) %7, ptr nofree readonly captures(none) %8, i64 %9, i64 %10, i64 %11, i64 %12, i64 %13, ptr nofree readnone captures(none) %14, ptr nofree readonly captures(none) %15, i64 %16, i64 %17, i64 %18) local_unnamed_addr #1 {
  %20 = tail call dereferenceable_or_null(48) ptr @malloc(i64 48)
  %gep.4.phi.trans.insert = getelementptr inbounds nuw i8, ptr %8, i64 48
  %.pre = load float, ptr %gep.4.phi.trans.insert, align 4
  %gep.5.phi.trans.insert = getelementptr inbounds nuw i8, ptr %8, i64 60
  %.pre4 = load float, ptr %gep.5.phi.trans.insert, align 4
  %.phi.trans.insert = getelementptr inbounds nuw i8, ptr %15, i64 4
  %.pre5 = load float, ptr %.phi.trans.insert, align 4
  %invariant.gep.1.phi.trans.insert = getelementptr inbounds nuw i8, ptr %8, i64 4
  %.pre6 = load float, ptr %invariant.gep.1.phi.trans.insert, align 4
  %gep.1.1.phi.trans.insert = getelementptr inbounds nuw i8, ptr %8, i64 16
  %.pre8 = load float, ptr %gep.1.1.phi.trans.insert, align 4
  %gep.2.1.phi.trans.insert = getelementptr inbounds nuw i8, ptr %8, i64 28
  %.pre10 = load float, ptr %gep.2.1.phi.trans.insert, align 4
  %gep.3.1.phi.trans.insert = getelementptr inbounds nuw i8, ptr %8, i64 40
  %.pre12 = load float, ptr %gep.3.1.phi.trans.insert, align 4
  %gep.4.1.phi.trans.insert = getelementptr inbounds nuw i8, ptr %8, i64 52
  %.pre14 = load float, ptr %gep.4.1.phi.trans.insert, align 4
  %gep.5.1.phi.trans.insert = getelementptr inbounds nuw i8, ptr %8, i64 64
  %.pre16 = load float, ptr %gep.5.1.phi.trans.insert, align 4
  %.phi.trans.insert17 = getelementptr inbounds nuw i8, ptr %15, i64 8
  %.pre18 = load float, ptr %.phi.trans.insert17, align 4
  %invariant.gep.2.phi.trans.insert = getelementptr inbounds nuw i8, ptr %8, i64 8
  %.pre19 = load float, ptr %invariant.gep.2.phi.trans.insert, align 4
  %gep.1.2.phi.trans.insert = getelementptr inbounds nuw i8, ptr %8, i64 20
  %.pre21 = load float, ptr %gep.1.2.phi.trans.insert, align 4
  %gep.2.2.phi.trans.insert = getelementptr inbounds nuw i8, ptr %8, i64 32
  %.pre23 = load float, ptr %gep.2.2.phi.trans.insert, align 4
  %gep.3.2.phi.trans.insert = getelementptr inbounds nuw i8, ptr %8, i64 44
  %.pre25 = load float, ptr %gep.3.2.phi.trans.insert, align 4
  %gep.4.2.phi.trans.insert = getelementptr inbounds nuw i8, ptr %8, i64 56
  %.pre27 = load float, ptr %gep.4.2.phi.trans.insert, align 4
  %gep.5.2.phi.trans.insert = getelementptr inbounds nuw i8, ptr %8, i64 68
  %.pre29 = load float, ptr %gep.5.2.phi.trans.insert, align 4
  %21 = load float, ptr %15, align 4
  %22 = load float, ptr %8, align 4
  %gep.1 = getelementptr inbounds nuw i8, ptr %8, i64 12
  %23 = load float, ptr %gep.1, align 4
  %gep.2 = getelementptr inbounds nuw i8, ptr %8, i64 24
  %24 = load float, ptr %gep.2, align 4
  %gep.3 = getelementptr inbounds nuw i8, ptr %8, i64 36
  %25 = load float, ptr %gep.3, align 4
  %26 = insertelement <4 x float> poison, float %.pre18, i64 0
  %27 = insertelement <4 x float> <float 1.000000e+00, float poison, float poison, float poison>, float %.pre19, i64 1
  %28 = insertelement <4 x float> %27, float %.pre21, i64 2
  %29 = insertelement <4 x float> %28, float %.pre23, i64 3
  %30 = insertelement <4 x float> <float 1.000000e+00, float poison, float poison, float poison>, float %.pre25, i64 1
  %31 = insertelement <4 x float> %30, float %.pre27, i64 2
  %32 = insertelement <4 x float> %31, float %.pre29, i64 3
  %33 = insertelement <4 x float> poison, float %.pre5, i64 0
  %34 = insertelement <4 x float> <float 1.000000e+00, float poison, float poison, float poison>, float %.pre6, i64 1
  %35 = insertelement <4 x float> %34, float %.pre8, i64 2
  %36 = insertelement <4 x float> %35, float %.pre10, i64 3
  %37 = insertelement <4 x float> <float 1.000000e+00, float poison, float poison, float poison>, float %.pre12, i64 1
  %38 = insertelement <4 x float> %37, float %.pre14, i64 2
  %39 = insertelement <4 x float> %38, float %.pre16, i64 3
  %40 = insertelement <4 x float> poison, float %21, i64 0
  %41 = insertelement <4 x float> <float 1.000000e+00, float poison, float poison, float poison>, float %22, i64 1
  %42 = insertelement <4 x float> %41, float %23, i64 2
  %43 = insertelement <4 x float> %42, float %24, i64 3
  %44 = insertelement <4 x float> <float 1.000000e+00, float poison, float poison, float poison>, float %25, i64 1
  %45 = insertelement <4 x float> %44, float %.pre, i64 2
  %46 = insertelement <4 x float> %45, float %.pre4, i64 3
  br label %.preheader

.preheader:                                       ; preds = %19, %.preheader
  %47 = phi i64 [ 0, %19 ], [ %100, %.preheader ]
  %.idx2 = mul nuw nsw i64 %47, 24
  %48 = getelementptr inbounds nuw i8, ptr %1, i64 %.idx2
  %.idx = mul nuw nsw i64 %47, 12
  %49 = getelementptr inbounds nuw i8, ptr %20, i64 %.idx
  %50 = getelementptr inbounds nuw i8, ptr %48, i64 4
  %51 = getelementptr inbounds nuw i8, ptr %48, i64 12
  %52 = getelementptr inbounds nuw i8, ptr %48, i64 16
  %53 = getelementptr inbounds nuw i8, ptr %49, i64 4
  %54 = load <2 x float>, ptr %48, align 4
  %55 = load float, ptr %48, align 4
  %56 = load <2 x float>, ptr %50, align 4
  %57 = insertelement <4 x float> %40, float %55, i64 1
  %58 = shufflevector <2 x float> %56, <2 x float> poison, <4 x i32> <i32 0, i32 1, i32 poison, i32 poison>
  %59 = shufflevector <4 x float> %57, <4 x float> %58, <4 x i32> <i32 0, i32 1, i32 4, i32 5>
  %60 = fmul <4 x float> %59, %43
  %61 = shufflevector <2 x float> %54, <2 x float> poison, <4 x i32> <i32 0, i32 1, i32 poison, i32 poison>
  %62 = shufflevector <4 x float> %33, <4 x float> %61, <4 x i32> <i32 0, i32 4, i32 5, i32 poison>
  %63 = shufflevector <4 x float> %62, <4 x float> %58, <4 x i32> <i32 0, i32 1, i32 2, i32 5>
  %64 = fmul <4 x float> %63, %36
  %65 = shufflevector <2 x float> %54, <2 x float> poison, <4 x i32> <i32 0, i32 1, i32 poison, i32 poison>
  %66 = shufflevector <4 x float> %26, <4 x float> %65, <4 x i32> <i32 0, i32 4, i32 5, i32 poison>
  %67 = shufflevector <4 x float> %66, <4 x float> %58, <4 x i32> <i32 0, i32 1, i32 2, i32 5>
  %68 = fmul <4 x float> %67, %29
  %69 = load <2 x float>, ptr %51, align 4
  %70 = load float, ptr %51, align 4
  %71 = load <2 x float>, ptr %52, align 4
  %72 = tail call float @llvm.vector.reduce.fadd.v4f32(float -0.000000e+00, <4 x float> %60)
  %73 = insertelement <4 x float> poison, float %72, i64 0
  %74 = insertelement <4 x float> %73, float %70, i64 1
  %75 = shufflevector <2 x float> %71, <2 x float> poison, <4 x i32> <i32 0, i32 1, i32 poison, i32 poison>
  %76 = shufflevector <4 x float> %74, <4 x float> %75, <4 x i32> <i32 0, i32 1, i32 4, i32 5>
  %77 = fmul <4 x float> %76, %46
  %78 = tail call float @llvm.vector.reduce.fadd.v4f32(float -0.000000e+00, <4 x float> %77)
  %79 = fcmp ogt float %78, 0.000000e+00
  %80 = select i1 %79, float %78, float 0.000000e+00
  store float %80, ptr %49, align 4
  %81 = tail call float @llvm.vector.reduce.fadd.v4f32(float -0.000000e+00, <4 x float> %64)
  %82 = insertelement <4 x float> poison, float %81, i64 0
  %83 = shufflevector <2 x float> %69, <2 x float> poison, <4 x i32> <i32 0, i32 1, i32 poison, i32 poison>
  %84 = shufflevector <4 x float> %82, <4 x float> %83, <4 x i32> <i32 0, i32 4, i32 5, i32 poison>
  %85 = shufflevector <4 x float> %84, <4 x float> %75, <4 x i32> <i32 0, i32 1, i32 2, i32 5>
  %86 = fmul <4 x float> %85, %39
  %87 = tail call float @llvm.vector.reduce.fadd.v4f32(float -0.000000e+00, <4 x float> %86)
  %88 = fcmp ogt float %87, 0.000000e+00
  %89 = select i1 %88, float %87, float 0.000000e+00
  store float %89, ptr %53, align 4
  %90 = tail call float @llvm.vector.reduce.fadd.v4f32(float -0.000000e+00, <4 x float> %68)
  %91 = insertelement <4 x float> poison, float %90, i64 0
  %92 = shufflevector <2 x float> %69, <2 x float> poison, <4 x i32> <i32 0, i32 1, i32 poison, i32 poison>
  %93 = shufflevector <4 x float> %91, <4 x float> %92, <4 x i32> <i32 0, i32 4, i32 5, i32 poison>
  %94 = shufflevector <4 x float> %93, <4 x float> %75, <4 x i32> <i32 0, i32 1, i32 2, i32 5>
  %95 = fmul <4 x float> %94, %32
  %96 = tail call float @llvm.vector.reduce.fadd.v4f32(float -0.000000e+00, <4 x float> %95)
  %97 = fcmp ogt float %96, 0.000000e+00
  %98 = select i1 %97, float %96, float 0.000000e+00
  %99 = getelementptr inbounds nuw i8, ptr %49, i64 8
  store float %98, ptr %99, align 4
  %100 = add nuw nsw i64 %47, 1
  %101 = icmp samesign ult i64 %47, 3
  br i1 %101, label %.preheader, label %102

102:                                              ; preds = %.preheader
  %103 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } poison, ptr %20, 0
  %104 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %103, ptr %20, 1
  %105 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %104, i64 0, 2
  %106 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %105, i64 4, 3, 0
  %107 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %106, i64 3, 3, 1
  %108 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %107, i64 3, 4, 0
  %109 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %108, i64 1, 4, 1
  ret { ptr, ptr, i64, [2 x i64], [2 x i64] } %109
}

; Function Attrs: nofree nounwind memory(readwrite, target_mem: none)
define void @_mlir_ciface_main_kernel(ptr nofree writeonly captures(none) initializes((0, 56)) %0, ptr nofree readonly captures(none) %1, ptr nofree readonly captures(none) %2, ptr nofree readonly captures(none) %3) local_unnamed_addr #2 {
  %.elt1 = getelementptr inbounds nuw i8, ptr %1, i64 8
  %.unpack2 = load ptr, ptr %.elt1, align 8
  %.elt16 = getelementptr inbounds nuw i8, ptr %2, i64 8
  %.unpack17 = load ptr, ptr %.elt16, align 8
  %.elt31 = getelementptr inbounds nuw i8, ptr %3, i64 8
  %.unpack32 = load ptr, ptr %.elt31, align 8
  %5 = tail call { ptr, ptr, i64, [2 x i64], [2 x i64] } @main_kernel(ptr poison, ptr %.unpack2, i64 poison, i64 poison, i64 poison, i64 poison, i64 poison, ptr poison, ptr %.unpack17, i64 poison, i64 poison, i64 poison, i64 poison, i64 poison, ptr poison, ptr %.unpack32, i64 poison, i64 poison, i64 poison)
  %.elt = extractvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %5, 0
  store ptr %.elt, ptr %0, align 8
  %.repack41 = getelementptr inbounds nuw i8, ptr %0, i64 8
  %.elt42 = extractvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %5, 1
  store ptr %.elt42, ptr %.repack41, align 8
  %.repack43 = getelementptr inbounds nuw i8, ptr %0, i64 16
  %.elt44 = extractvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %5, 2
  store i64 %.elt44, ptr %.repack43, align 8
  %.repack45 = getelementptr inbounds nuw i8, ptr %0, i64 24
  %.elt46 = extractvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %5, 3
  %.elt46.elt = extractvalue [2 x i64] %.elt46, 0
  store i64 %.elt46.elt, ptr %.repack45, align 8
  %.repack45.repack49 = getelementptr inbounds nuw i8, ptr %0, i64 32
  %.elt46.elt50 = extractvalue [2 x i64] %.elt46, 1
  store i64 %.elt46.elt50, ptr %.repack45.repack49, align 8
  %.repack47 = getelementptr inbounds nuw i8, ptr %0, i64 40
  %.elt48 = extractvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %5, 4
  %.elt48.elt = extractvalue [2 x i64] %.elt48, 0
  store i64 %.elt48.elt, ptr %.repack47, align 8
  %.repack47.repack51 = getelementptr inbounds nuw i8, ptr %0, i64 48
  %.elt48.elt52 = extractvalue [2 x i64] %.elt48, 1
  store i64 %.elt48.elt52, ptr %.repack47.repack51, align 8
  ret void
}

; Function Attrs: nocallback nocreateundeforpoison nofree nosync nounwind speculatable willreturn memory(none)
declare float @llvm.vector.reduce.fadd.v4f32(float, <4 x float>) #3

attributes #0 = { mustprogress nofree nounwind willreturn allockind("alloc,uninitialized") allocsize(0) memory(inaccessiblemem: readwrite, errnomem: write) "alloc-family"="malloc" }
attributes #1 = { nofree nounwind memory(write, argmem: read, inaccessiblemem: readwrite, target_mem: none) }
attributes #2 = { nofree nounwind memory(readwrite, target_mem: none) }
attributes #3 = { nocallback nocreateundeforpoison nofree nosync nounwind speculatable willreturn memory(none) }

!llvm.module.flags = !{!0}

!0 = !{i32 2, !"Debug Info Version", i32 3}
