; ModuleID = '/Users/chenbinbin/GitHub/ai-chip-compiler-learning-plan/tutorials/day-129/code/outputs/e2-dynamic/out.ll'
source_filename = "LLVMDialectModule"

; Function Attrs: mustprogress nofree nounwind willreturn allockind("alloc,uninitialized") allocsize(0) memory(inaccessiblemem: readwrite, errnomem: write)
declare noalias noundef ptr @malloc(i64 noundef) local_unnamed_addr #0

; Function Attrs: nofree nounwind memory(write, argmem: read, inaccessiblemem: readwrite, target_mem: none)
define { ptr, ptr, i64, [2 x i64], [2 x i64] } @kernel_dynamic(ptr nofree readnone captures(none) %0, ptr nofree readonly captures(none) %1, i64 %2, i64 %3, i64 %4, i64 %5, i64 %6, ptr nofree readnone captures(none) %7, ptr nofree readonly captures(none) %8, i64 %9, i64 %10, i64 %11, i64 %12, i64 %13) local_unnamed_addr #1 {
  %15 = shl i64 %3, 2
  %.idx = mul i64 %15, %11
  %16 = tail call ptr @malloc(i64 %.idx)
  %17 = icmp sgt i64 %3, 0
  br i1 %17, label %.preheader1.lr.ph, label %._crit_edge3.split

.preheader1.lr.ph:                                ; preds = %14
  %18 = icmp sgt i64 %11, 0
  %19 = icmp sgt i64 %4, 0
  br i1 %18, label %.preheader1, label %._crit_edge3.split

.preheader1:                                      ; preds = %.preheader1.lr.ph, %._crit_edge2
  %20 = phi i64 [ %39, %._crit_edge2 ], [ 0, %.preheader1.lr.ph ]
  %21 = mul nsw i64 %20, %5
  %22 = getelementptr [4 x i8], ptr %1, i64 %21
  %23 = mul nuw nsw i64 %20, %11
  %24 = getelementptr [4 x i8], ptr %16, i64 %23
  br label %.preheader

.preheader:                                       ; preds = %.preheader1, %._crit_edge
  %25 = phi i64 [ 0, %.preheader1 ], [ %37, %._crit_edge ]
  %invariant.gep = getelementptr [4 x i8], ptr %8, i64 %25
  br i1 %19, label %.lr.ph, label %._crit_edge

.lr.ph:                                           ; preds = %.preheader, %.lr.ph
  %26 = phi float [ %33, %.lr.ph ], [ 0.000000e+00, %.preheader ]
  %27 = phi i64 [ %34, %.lr.ph ], [ 0, %.preheader ]
  %28 = getelementptr [4 x i8], ptr %22, i64 %27
  %29 = load float, ptr %28, align 4
  %30 = mul nsw i64 %27, %12
  %gep = getelementptr [4 x i8], ptr %invariant.gep, i64 %30
  %31 = load float, ptr %gep, align 4
  %32 = fmul float %29, %31
  %33 = fadd float %26, %32
  %34 = add nuw nsw i64 %27, 1
  %35 = icmp slt i64 %34, %4
  br i1 %35, label %.lr.ph, label %._crit_edge

._crit_edge:                                      ; preds = %.lr.ph, %.preheader
  %.lcssa = phi float [ 0.000000e+00, %.preheader ], [ %33, %.lr.ph ]
  %36 = getelementptr [4 x i8], ptr %24, i64 %25
  store float %.lcssa, ptr %36, align 4
  %37 = add nuw nsw i64 %25, 1
  %38 = icmp slt i64 %37, %11
  br i1 %38, label %.preheader, label %._crit_edge2

._crit_edge2:                                     ; preds = %._crit_edge
  %39 = add nuw nsw i64 %20, 1
  %40 = icmp slt i64 %39, %3
  br i1 %40, label %.preheader1, label %._crit_edge3.split

._crit_edge3.split:                               ; preds = %._crit_edge2, %.preheader1.lr.ph, %14
  %41 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } poison, ptr %16, 0
  %42 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %41, ptr %16, 1
  %43 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %42, i64 0, 2
  %44 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %43, i64 %3, 3, 0
  %45 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %44, i64 %11, 3, 1
  %46 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %45, i64 %11, 4, 0
  %47 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %46, i64 1, 4, 1
  ret { ptr, ptr, i64, [2 x i64], [2 x i64] } %47
}

; Function Attrs: nofree nounwind memory(readwrite, target_mem: none)
define void @_mlir_ciface_kernel_dynamic(ptr nofree writeonly captures(none) %0, ptr nofree readonly captures(none) %1, ptr nofree readonly captures(none) %2) local_unnamed_addr #2 {
  %.elt1 = getelementptr inbounds nuw i8, ptr %1, i64 8
  %.unpack2 = load ptr, ptr %.elt1, align 8
  %.elt5 = getelementptr inbounds nuw i8, ptr %1, i64 24
  %.unpack6.unpack = load i64, ptr %.elt5, align 8
  %.unpack6.elt9 = getelementptr inbounds nuw i8, ptr %1, i64 32
  %.unpack6.unpack10 = load i64, ptr %.unpack6.elt9, align 8
  %.elt7 = getelementptr inbounds nuw i8, ptr %1, i64 40
  %.unpack8.unpack = load i64, ptr %.elt7, align 8
  %.elt16 = getelementptr inbounds nuw i8, ptr %2, i64 8
  %.unpack17 = load ptr, ptr %.elt16, align 8
  %.unpack21.elt24 = getelementptr inbounds nuw i8, ptr %2, i64 32
  %.unpack21.unpack25 = load i64, ptr %.unpack21.elt24, align 8
  %.elt22 = getelementptr inbounds nuw i8, ptr %2, i64 40
  %.unpack23.unpack = load i64, ptr %.elt22, align 8
  %4 = shl i64 %.unpack6.unpack, 2
  %.idx.i = mul i64 %4, %.unpack21.unpack25
  %5 = tail call ptr @malloc(i64 %.idx.i)
  %6 = icmp sgt i64 %.unpack6.unpack, 0
  br i1 %6, label %.preheader1.lr.ph.i, label %kernel_dynamic.exit

.preheader1.lr.ph.i:                              ; preds = %3
  %7 = icmp sgt i64 %.unpack21.unpack25, 0
  %8 = icmp sgt i64 %.unpack6.unpack10, 0
  br i1 %7, label %.preheader1.i, label %kernel_dynamic.exit

.preheader1.i:                                    ; preds = %.preheader1.lr.ph.i, %._crit_edge2.i
  %9 = phi i64 [ %28, %._crit_edge2.i ], [ 0, %.preheader1.lr.ph.i ]
  %10 = mul nsw i64 %9, %.unpack8.unpack
  %11 = getelementptr [4 x i8], ptr %.unpack2, i64 %10
  %12 = mul nuw nsw i64 %9, %.unpack21.unpack25
  %13 = getelementptr [4 x i8], ptr %5, i64 %12
  br label %.preheader.i

.preheader.i:                                     ; preds = %._crit_edge.i, %.preheader1.i
  %14 = phi i64 [ 0, %.preheader1.i ], [ %26, %._crit_edge.i ]
  %invariant.gep.i = getelementptr [4 x i8], ptr %.unpack17, i64 %14
  br i1 %8, label %.lr.ph.i, label %._crit_edge.i

.lr.ph.i:                                         ; preds = %.preheader.i, %.lr.ph.i
  %15 = phi float [ %22, %.lr.ph.i ], [ 0.000000e+00, %.preheader.i ]
  %16 = phi i64 [ %23, %.lr.ph.i ], [ 0, %.preheader.i ]
  %17 = getelementptr [4 x i8], ptr %11, i64 %16
  %18 = load float, ptr %17, align 4
  %19 = mul nsw i64 %16, %.unpack23.unpack
  %gep.i = getelementptr [4 x i8], ptr %invariant.gep.i, i64 %19
  %20 = load float, ptr %gep.i, align 4
  %21 = fmul float %18, %20
  %22 = fadd float %15, %21
  %23 = add nuw nsw i64 %16, 1
  %24 = icmp slt i64 %23, %.unpack6.unpack10
  br i1 %24, label %.lr.ph.i, label %._crit_edge.i

._crit_edge.i:                                    ; preds = %.lr.ph.i, %.preheader.i
  %.lcssa.i = phi float [ 0.000000e+00, %.preheader.i ], [ %22, %.lr.ph.i ]
  %25 = getelementptr [4 x i8], ptr %13, i64 %14
  store float %.lcssa.i, ptr %25, align 4
  %26 = add nuw nsw i64 %14, 1
  %27 = icmp slt i64 %26, %.unpack21.unpack25
  br i1 %27, label %.preheader.i, label %._crit_edge2.i

._crit_edge2.i:                                   ; preds = %._crit_edge.i
  %28 = add nuw nsw i64 %9, 1
  %29 = icmp slt i64 %28, %.unpack6.unpack
  br i1 %29, label %.preheader1.i, label %kernel_dynamic.exit

kernel_dynamic.exit:                              ; preds = %._crit_edge2.i, %3, %.preheader1.lr.ph.i
  store ptr %5, ptr %0, align 8
  %.repack30 = getelementptr inbounds nuw i8, ptr %0, i64 8
  store ptr %5, ptr %.repack30, align 8
  %.repack32 = getelementptr inbounds nuw i8, ptr %0, i64 16
  store i64 0, ptr %.repack32, align 8
  %.repack34 = getelementptr inbounds nuw i8, ptr %0, i64 24
  store i64 %.unpack6.unpack, ptr %.repack34, align 8
  %.repack34.repack38 = getelementptr inbounds nuw i8, ptr %0, i64 32
  store i64 %.unpack21.unpack25, ptr %.repack34.repack38, align 8
  %.repack36 = getelementptr inbounds nuw i8, ptr %0, i64 40
  store i64 %.unpack21.unpack25, ptr %.repack36, align 8
  %.repack36.repack40 = getelementptr inbounds nuw i8, ptr %0, i64 48
  store i64 1, ptr %.repack36.repack40, align 8
  ret void
}

attributes #0 = { mustprogress nofree nounwind willreturn allockind("alloc,uninitialized") allocsize(0) memory(inaccessiblemem: readwrite, errnomem: write) "alloc-family"="malloc" }
attributes #1 = { nofree nounwind memory(write, argmem: read, inaccessiblemem: readwrite, target_mem: none) }
attributes #2 = { nofree nounwind memory(readwrite, target_mem: none) }

!llvm.module.flags = !{!0}

!0 = !{i32 2, !"Debug Info Version", i32 3}
