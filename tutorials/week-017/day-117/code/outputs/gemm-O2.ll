; ModuleID = 'outputs/gemm-3.ll'
source_filename = "LLVMDialectModule"

; Function Attrs: mustprogress nofree nounwind willreturn allockind("alloc,uninitialized") allocsize(0) memory(inaccessiblemem: readwrite)
declare noalias noundef ptr @malloc(i64 noundef) local_unnamed_addr #0

; Function Attrs: nofree nounwind memory(write, argmem: read, inaccessiblemem: readwrite)
define { ptr, ptr, i64, [2 x i64], [2 x i64] } @gemm(ptr nocapture readnone %0, ptr nocapture readonly %1, i64 %2, i64 %3, i64 %4, i64 %5, i64 %6, ptr nocapture readnone %7, ptr nocapture readonly %8, i64 %9, i64 %10, i64 %11, i64 %12, i64 %13) local_unnamed_addr #1 {
  %15 = tail call dereferenceable_or_null(48) ptr @malloc(i64 48)
  %gep.2.phi.trans.insert = getelementptr float, ptr %8, i64 6
  %.pre = load float, ptr %gep.2.phi.trans.insert, align 4
  %gep.3.phi.trans.insert = getelementptr float, ptr %8, i64 9
  %.pre2 = load float, ptr %gep.3.phi.trans.insert, align 4
  %gep.4.phi.trans.insert = getelementptr float, ptr %8, i64 12
  %.pre3 = load float, ptr %gep.4.phi.trans.insert, align 4
  %gep.5.phi.trans.insert = getelementptr float, ptr %8, i64 15
  %.pre4 = load float, ptr %gep.5.phi.trans.insert, align 4
  %invariant.gep.1.phi.trans.insert = getelementptr float, ptr %8, i64 1
  %.pre5 = load float, ptr %invariant.gep.1.phi.trans.insert, align 4
  %gep.1.1.phi.trans.insert = getelementptr float, ptr %8, i64 4
  %.pre7 = load float, ptr %gep.1.1.phi.trans.insert, align 4
  %gep.2.1.phi.trans.insert = getelementptr float, ptr %8, i64 7
  %.pre9 = load float, ptr %gep.2.1.phi.trans.insert, align 4
  %gep.3.1.phi.trans.insert = getelementptr float, ptr %8, i64 10
  %.pre11 = load float, ptr %gep.3.1.phi.trans.insert, align 4
  %gep.4.1.phi.trans.insert = getelementptr float, ptr %8, i64 13
  %.pre13 = load float, ptr %gep.4.1.phi.trans.insert, align 4
  %gep.5.1.phi.trans.insert = getelementptr float, ptr %8, i64 16
  %.pre15 = load float, ptr %gep.5.1.phi.trans.insert, align 4
  %invariant.gep.2.phi.trans.insert = getelementptr float, ptr %8, i64 2
  %.pre16 = load float, ptr %invariant.gep.2.phi.trans.insert, align 4
  %gep.1.2.phi.trans.insert = getelementptr float, ptr %8, i64 5
  %.pre18 = load float, ptr %gep.1.2.phi.trans.insert, align 4
  %gep.2.2.phi.trans.insert = getelementptr float, ptr %8, i64 8
  %.pre20 = load float, ptr %gep.2.2.phi.trans.insert, align 4
  %gep.3.2.phi.trans.insert = getelementptr float, ptr %8, i64 11
  %.pre22 = load float, ptr %gep.3.2.phi.trans.insert, align 4
  %gep.4.2.phi.trans.insert = getelementptr float, ptr %8, i64 14
  %.pre24 = load float, ptr %gep.4.2.phi.trans.insert, align 4
  %gep.5.2.phi.trans.insert = getelementptr float, ptr %8, i64 17
  %.pre26 = load float, ptr %gep.5.2.phi.trans.insert, align 4
  %16 = load float, ptr %8, align 4
  %gep.1 = getelementptr float, ptr %8, i64 3
  %17 = load float, ptr %gep.1, align 4
  br label %.preheader1

.preheader1:                                      ; preds = %14, %.preheader1
  %18 = phi i64 [ 0, %14 ], [ %72, %.preheader1 ]
  %19 = mul nuw nsw i64 %18, 6
  %20 = getelementptr float, ptr %1, i64 %19
  %21 = mul nuw nsw i64 %18, 3
  %22 = getelementptr float, ptr %15, i64 %21
  %23 = load float, ptr %20, align 4
  %24 = fmul float %23, %16
  %25 = fadd float %24, 0.000000e+00
  %26 = getelementptr float, ptr %20, i64 1
  %27 = load float, ptr %26, align 4
  %28 = fmul float %27, %17
  %29 = fadd float %25, %28
  %30 = getelementptr float, ptr %20, i64 2
  %31 = load float, ptr %30, align 4
  %32 = fmul float %31, %.pre
  %33 = fadd float %29, %32
  %34 = getelementptr float, ptr %20, i64 3
  %35 = load float, ptr %34, align 4
  %36 = fmul float %35, %.pre2
  %37 = fadd float %33, %36
  %38 = getelementptr float, ptr %20, i64 4
  %39 = load float, ptr %38, align 4
  %40 = fmul float %39, %.pre3
  %41 = fadd float %37, %40
  %42 = getelementptr float, ptr %20, i64 5
  %43 = load float, ptr %42, align 4
  %44 = fmul float %43, %.pre4
  %45 = fadd float %41, %44
  store float %45, ptr %22, align 4
  %46 = fmul float %23, %.pre5
  %47 = fadd float %46, 0.000000e+00
  %48 = fmul float %27, %.pre7
  %49 = fadd float %47, %48
  %50 = fmul float %31, %.pre9
  %51 = fadd float %49, %50
  %52 = fmul float %35, %.pre11
  %53 = fadd float %51, %52
  %54 = fmul float %39, %.pre13
  %55 = fadd float %53, %54
  %56 = fmul float %43, %.pre15
  %57 = fadd float %55, %56
  %58 = getelementptr float, ptr %22, i64 1
  store float %57, ptr %58, align 4
  %59 = fmul float %23, %.pre16
  %60 = fadd float %59, 0.000000e+00
  %61 = fmul float %27, %.pre18
  %62 = fadd float %60, %61
  %63 = fmul float %31, %.pre20
  %64 = fadd float %62, %63
  %65 = fmul float %35, %.pre22
  %66 = fadd float %64, %65
  %67 = fmul float %39, %.pre24
  %68 = fadd float %66, %67
  %69 = fmul float %43, %.pre26
  %70 = fadd float %68, %69
  %71 = getelementptr float, ptr %22, i64 2
  store float %70, ptr %71, align 4
  %72 = add nuw nsw i64 %18, 1
  %73 = icmp ult i64 %18, 3
  br i1 %73, label %.preheader1, label %74

74:                                               ; preds = %.preheader1
  %75 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } undef, ptr %15, 0
  %76 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %75, ptr %15, 1
  %77 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %76, i64 0, 2
  %78 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %77, i64 4, 3, 0
  %79 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %78, i64 3, 3, 1
  %80 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %79, i64 3, 4, 0
  %81 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %80, i64 1, 4, 1
  ret { ptr, ptr, i64, [2 x i64], [2 x i64] } %81
}

; Function Attrs: nofree nounwind
define void @_mlir_ciface_gemm(ptr nocapture writeonly %0, ptr nocapture readonly %1, ptr nocapture readonly %2) local_unnamed_addr #2 {
  %.elt1 = getelementptr inbounds { ptr, ptr, i64, [2 x i64], [2 x i64] }, ptr %1, i64 0, i32 1
  %.unpack2 = load ptr, ptr %.elt1, align 8
  %.elt16 = getelementptr inbounds { ptr, ptr, i64, [2 x i64], [2 x i64] }, ptr %2, i64 0, i32 1
  %.unpack17 = load ptr, ptr %.elt16, align 8
  %4 = tail call { ptr, ptr, i64, [2 x i64], [2 x i64] } @gemm(ptr poison, ptr %.unpack2, i64 poison, i64 poison, i64 poison, i64 poison, i64 poison, ptr poison, ptr %.unpack17, i64 poison, i64 poison, i64 poison, i64 poison, i64 poison)
  %.elt = extractvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %4, 0
  store ptr %.elt, ptr %0, align 8
  %.repack30 = getelementptr inbounds { ptr, ptr, i64, [2 x i64], [2 x i64] }, ptr %0, i64 0, i32 1
  %.elt31 = extractvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %4, 1
  store ptr %.elt31, ptr %.repack30, align 8
  %.repack32 = getelementptr inbounds { ptr, ptr, i64, [2 x i64], [2 x i64] }, ptr %0, i64 0, i32 2
  %.elt33 = extractvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %4, 2
  store i64 %.elt33, ptr %.repack32, align 8
  %.repack34 = getelementptr inbounds { ptr, ptr, i64, [2 x i64], [2 x i64] }, ptr %0, i64 0, i32 3
  %.elt35 = extractvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %4, 3
  %.elt35.elt = extractvalue [2 x i64] %.elt35, 0
  store i64 %.elt35.elt, ptr %.repack34, align 8
  %.repack34.repack38 = getelementptr inbounds { ptr, ptr, i64, [2 x i64], [2 x i64] }, ptr %0, i64 0, i32 3, i64 1
  %.elt35.elt39 = extractvalue [2 x i64] %.elt35, 1
  store i64 %.elt35.elt39, ptr %.repack34.repack38, align 8
  %.repack36 = getelementptr inbounds { ptr, ptr, i64, [2 x i64], [2 x i64] }, ptr %0, i64 0, i32 4
  %.elt37 = extractvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %4, 4
  %.elt37.elt = extractvalue [2 x i64] %.elt37, 0
  store i64 %.elt37.elt, ptr %.repack36, align 8
  %.repack36.repack40 = getelementptr inbounds { ptr, ptr, i64, [2 x i64], [2 x i64] }, ptr %0, i64 0, i32 4, i64 1
  %.elt37.elt41 = extractvalue [2 x i64] %.elt37, 1
  store i64 %.elt37.elt41, ptr %.repack36.repack40, align 8
  ret void
}

attributes #0 = { mustprogress nofree nounwind willreturn allockind("alloc,uninitialized") allocsize(0) memory(inaccessiblemem: readwrite) "alloc-family"="malloc" }
attributes #1 = { nofree nounwind memory(write, argmem: read, inaccessiblemem: readwrite) }
attributes #2 = { nofree nounwind }

!llvm.module.flags = !{!0}

!0 = !{i32 2, !"Debug Info Version", i32 3}
