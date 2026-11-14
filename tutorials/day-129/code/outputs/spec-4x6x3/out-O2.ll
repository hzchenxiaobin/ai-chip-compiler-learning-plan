; ModuleID = '/Users/chenbinbin/GitHub/ai-chip-compiler-learning-plan/tutorials/day-129/code/outputs/spec-4x6x3/out.ll'
source_filename = "LLVMDialectModule"

; Function Attrs: mustprogress nofree nounwind willreturn allockind("alloc,uninitialized") allocsize(0) memory(inaccessiblemem: readwrite, errnomem: write)
declare noalias noundef ptr @malloc(i64 noundef) local_unnamed_addr #0

; Function Attrs: nofree nounwind memory(write, argmem: read, inaccessiblemem: readwrite, target_mem: none)
define { ptr, ptr, i64, [2 x i64], [2 x i64] } @kernel_s4x6x3(ptr nofree readnone captures(none) %0, ptr nofree readonly captures(none) %1, i64 %2, i64 %3, i64 %4, i64 %5, i64 %6, ptr nofree readnone captures(none) %7, ptr nofree readonly captures(none) %8, i64 %9, i64 %10, i64 %11, i64 %12, i64 %13) local_unnamed_addr #1 {
  %15 = tail call dereferenceable_or_null(48) ptr @malloc(i64 48)
  %gep.2.phi.trans.insert = getelementptr i8, ptr %8, i64 24
  %.pre = load float, ptr %gep.2.phi.trans.insert, align 4
  %gep.3.phi.trans.insert = getelementptr i8, ptr %8, i64 36
  %.pre4 = load float, ptr %gep.3.phi.trans.insert, align 4
  %gep.4.phi.trans.insert = getelementptr i8, ptr %8, i64 48
  %.pre5 = load float, ptr %gep.4.phi.trans.insert, align 4
  %gep.5.phi.trans.insert = getelementptr i8, ptr %8, i64 60
  %.pre6 = load float, ptr %gep.5.phi.trans.insert, align 4
  %invariant.gep.1.phi.trans.insert = getelementptr i8, ptr %8, i64 4
  %.pre7 = load float, ptr %invariant.gep.1.phi.trans.insert, align 4
  %gep.1.1.phi.trans.insert = getelementptr i8, ptr %8, i64 16
  %.pre9 = load float, ptr %gep.1.1.phi.trans.insert, align 4
  %gep.2.1.phi.trans.insert = getelementptr i8, ptr %8, i64 28
  %.pre11 = load float, ptr %gep.2.1.phi.trans.insert, align 4
  %gep.3.1.phi.trans.insert = getelementptr i8, ptr %8, i64 40
  %.pre13 = load float, ptr %gep.3.1.phi.trans.insert, align 4
  %gep.4.1.phi.trans.insert = getelementptr i8, ptr %8, i64 52
  %.pre15 = load float, ptr %gep.4.1.phi.trans.insert, align 4
  %gep.5.1.phi.trans.insert = getelementptr i8, ptr %8, i64 64
  %.pre17 = load float, ptr %gep.5.1.phi.trans.insert, align 4
  %invariant.gep.2.phi.trans.insert = getelementptr i8, ptr %8, i64 8
  %.pre18 = load float, ptr %invariant.gep.2.phi.trans.insert, align 4
  %gep.1.2.phi.trans.insert = getelementptr i8, ptr %8, i64 20
  %.pre20 = load float, ptr %gep.1.2.phi.trans.insert, align 4
  %gep.2.2.phi.trans.insert = getelementptr i8, ptr %8, i64 32
  %.pre22 = load float, ptr %gep.2.2.phi.trans.insert, align 4
  %gep.3.2.phi.trans.insert = getelementptr i8, ptr %8, i64 44
  %.pre24 = load float, ptr %gep.3.2.phi.trans.insert, align 4
  %gep.4.2.phi.trans.insert = getelementptr i8, ptr %8, i64 56
  %.pre26 = load float, ptr %gep.4.2.phi.trans.insert, align 4
  %gep.5.2.phi.trans.insert = getelementptr i8, ptr %8, i64 68
  %.pre28 = load float, ptr %gep.5.2.phi.trans.insert, align 4
  %16 = load float, ptr %8, align 4
  %gep.1 = getelementptr i8, ptr %8, i64 12
  %17 = load float, ptr %gep.1, align 4
  br label %.preheader3

.preheader3:                                      ; preds = %14, %.preheader3
  %18 = phi i64 [ 0, %14 ], [ %70, %.preheader3 ]
  %.idx1 = mul nuw nsw i64 %18, 24
  %19 = getelementptr inbounds nuw i8, ptr %1, i64 %.idx1
  %.idx = mul nuw nsw i64 %18, 12
  %20 = getelementptr inbounds nuw i8, ptr %15, i64 %.idx
  %21 = load float, ptr %19, align 4
  %22 = fmul float %21, %16
  %23 = fadd float %22, 0.000000e+00
  %24 = getelementptr inbounds nuw i8, ptr %19, i64 4
  %25 = load float, ptr %24, align 4
  %26 = fmul float %25, %17
  %27 = fadd float %23, %26
  %28 = getelementptr inbounds nuw i8, ptr %19, i64 8
  %29 = load float, ptr %28, align 4
  %30 = fmul float %29, %.pre
  %31 = fadd float %27, %30
  %32 = getelementptr inbounds nuw i8, ptr %19, i64 12
  %33 = load float, ptr %32, align 4
  %34 = fmul float %33, %.pre4
  %35 = fadd float %31, %34
  %36 = getelementptr inbounds nuw i8, ptr %19, i64 16
  %37 = load float, ptr %36, align 4
  %38 = fmul float %37, %.pre5
  %39 = fadd float %35, %38
  %40 = getelementptr inbounds nuw i8, ptr %19, i64 20
  %41 = load float, ptr %40, align 4
  %42 = fmul float %41, %.pre6
  %43 = fadd float %39, %42
  store float %43, ptr %20, align 4
  %44 = fmul float %21, %.pre7
  %45 = fadd float %44, 0.000000e+00
  %46 = fmul float %25, %.pre9
  %47 = fadd float %45, %46
  %48 = fmul float %29, %.pre11
  %49 = fadd float %47, %48
  %50 = fmul float %33, %.pre13
  %51 = fadd float %49, %50
  %52 = fmul float %37, %.pre15
  %53 = fadd float %51, %52
  %54 = fmul float %41, %.pre17
  %55 = fadd float %53, %54
  %56 = getelementptr inbounds nuw i8, ptr %20, i64 4
  store float %55, ptr %56, align 4
  %57 = fmul float %21, %.pre18
  %58 = fadd float %57, 0.000000e+00
  %59 = fmul float %25, %.pre20
  %60 = fadd float %58, %59
  %61 = fmul float %29, %.pre22
  %62 = fadd float %60, %61
  %63 = fmul float %33, %.pre24
  %64 = fadd float %62, %63
  %65 = fmul float %37, %.pre26
  %66 = fadd float %64, %65
  %67 = fmul float %41, %.pre28
  %68 = fadd float %66, %67
  %69 = getelementptr inbounds nuw i8, ptr %20, i64 8
  store float %68, ptr %69, align 4
  %70 = add nuw nsw i64 %18, 1
  %71 = icmp samesign ult i64 %18, 3
  br i1 %71, label %.preheader3, label %72

72:                                               ; preds = %.preheader3
  %73 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } poison, ptr %15, 0
  %74 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %73, ptr %15, 1
  %75 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %74, i64 0, 2
  %76 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %75, i64 4, 3, 0
  %77 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %76, i64 3, 3, 1
  %78 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %77, i64 3, 4, 0
  %79 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %78, i64 1, 4, 1
  ret { ptr, ptr, i64, [2 x i64], [2 x i64] } %79
}

; Function Attrs: nofree nounwind memory(readwrite, target_mem: none)
define void @_mlir_ciface_kernel_s4x6x3(ptr nofree writeonly captures(none) initializes((0, 56)) %0, ptr nofree readonly captures(none) %1, ptr nofree readonly captures(none) %2) local_unnamed_addr #2 {
  %.elt1 = getelementptr inbounds nuw i8, ptr %1, i64 8
  %.unpack2 = load ptr, ptr %.elt1, align 8
  %.elt16 = getelementptr inbounds nuw i8, ptr %2, i64 8
  %.unpack17 = load ptr, ptr %.elt16, align 8
  %4 = tail call { ptr, ptr, i64, [2 x i64], [2 x i64] } @kernel_s4x6x3(ptr poison, ptr %.unpack2, i64 poison, i64 poison, i64 poison, i64 poison, i64 poison, ptr poison, ptr %.unpack17, i64 poison, i64 poison, i64 poison, i64 poison, i64 poison)
  %.elt = extractvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %4, 0
  store ptr %.elt, ptr %0, align 8
  %.repack30 = getelementptr inbounds nuw i8, ptr %0, i64 8
  %.elt31 = extractvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %4, 1
  store ptr %.elt31, ptr %.repack30, align 8
  %.repack32 = getelementptr inbounds nuw i8, ptr %0, i64 16
  %.elt33 = extractvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %4, 2
  store i64 %.elt33, ptr %.repack32, align 8
  %.repack34 = getelementptr inbounds nuw i8, ptr %0, i64 24
  %.elt35 = extractvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %4, 3
  %.elt35.elt = extractvalue [2 x i64] %.elt35, 0
  store i64 %.elt35.elt, ptr %.repack34, align 8
  %.repack34.repack38 = getelementptr inbounds nuw i8, ptr %0, i64 32
  %.elt35.elt39 = extractvalue [2 x i64] %.elt35, 1
  store i64 %.elt35.elt39, ptr %.repack34.repack38, align 8
  %.repack36 = getelementptr inbounds nuw i8, ptr %0, i64 40
  %.elt37 = extractvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %4, 4
  %.elt37.elt = extractvalue [2 x i64] %.elt37, 0
  store i64 %.elt37.elt, ptr %.repack36, align 8
  %.repack36.repack40 = getelementptr inbounds nuw i8, ptr %0, i64 48
  %.elt37.elt41 = extractvalue [2 x i64] %.elt37, 1
  store i64 %.elt37.elt41, ptr %.repack36.repack40, align 8
  ret void
}

attributes #0 = { mustprogress nofree nounwind willreturn allockind("alloc,uninitialized") allocsize(0) memory(inaccessiblemem: readwrite, errnomem: write) "alloc-family"="malloc" }
attributes #1 = { nofree nounwind memory(write, argmem: read, inaccessiblemem: readwrite, target_mem: none) }
attributes #2 = { nofree nounwind memory(readwrite, target_mem: none) }

!llvm.module.flags = !{!0}

!0 = !{i32 2, !"Debug Info Version", i32 3}
