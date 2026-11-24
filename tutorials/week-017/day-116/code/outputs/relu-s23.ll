; 第 116 天：由 op_lowering.py 从源 IR 转换导出（函数 relu）
target triple = "aarch64-unknown-linux-gnu"
%desc = type { ptr, ptr, i64, [2 x i64], [2 x i64] }
declare ptr @malloc(i64)

define internal %desc @relu(%desc %x) noinline {
entry:
  %mem_r = call ptr @malloc(i64 24)
  %i0_r = insertvalue %desc undef, ptr %mem_r, 0
  %i1_r = insertvalue %desc %i0_r, ptr %mem_r, 1
  %i2_r = insertvalue %desc %i1_r, i64 0, 2
  %i3_r = insertvalue %desc %i2_r, i64 2, 3, 0
  %i4_r = insertvalue %desc %i3_r, i64 3, 3, 1
  %i5_r = insertvalue %desc %i4_r, i64 3, 4, 0
  %r = insertvalue %desc %i5_r, i64 1, 4, 1
  %x00_al = extractvalue %desc %x, 1
  %x00_off = extractvalue %desc %x, 2
  %x00_s0 = extractvalue %desc %x, 4, 0
  %x00_s1 = extractvalue %desc %x, 4, 1
  %x00_m0 = mul i64 0, %x00_s0
  %x00_a0 = add i64 %x00_off, %x00_m0
  %x00_m1 = mul i64 0, %x00_s1
  %x00_a1 = add i64 %x00_a0, %x00_m1
  %x00_p = getelementptr float, ptr %x00_al, i64 %x00_a1
  %x00 = load float, ptr %x00_p
  %g00 = fcmp ogt float %x00, 0.000000e+00
  %m00 = select i1 %g00, float %x00, float 0.000000e+00
  %m00_dst_al = extractvalue %desc %r, 1
  %m00_dst_off = extractvalue %desc %r, 2
  %m00_dst_s0 = extractvalue %desc %r, 4, 0
  %m00_dst_s1 = extractvalue %desc %r, 4, 1
  %m00_dst_m0 = mul i64 0, %m00_dst_s0
  %m00_dst_a0 = add i64 %m00_dst_off, %m00_dst_m0
  %m00_dst_m1 = mul i64 0, %m00_dst_s1
  %m00_dst_a1 = add i64 %m00_dst_a0, %m00_dst_m1
  %m00_dst_p = getelementptr float, ptr %m00_dst_al, i64 %m00_dst_a1
  store float %m00, ptr %m00_dst_p
  %x01_al = extractvalue %desc %x, 1
  %x01_off = extractvalue %desc %x, 2
  %x01_s0 = extractvalue %desc %x, 4, 0
  %x01_s1 = extractvalue %desc %x, 4, 1
  %x01_m0 = mul i64 0, %x01_s0
  %x01_a0 = add i64 %x01_off, %x01_m0
  %x01_m1 = mul i64 1, %x01_s1
  %x01_a1 = add i64 %x01_a0, %x01_m1
  %x01_p = getelementptr float, ptr %x01_al, i64 %x01_a1
  %x01 = load float, ptr %x01_p
  %g01 = fcmp ogt float %x01, 0.000000e+00
  %m01 = select i1 %g01, float %x01, float 0.000000e+00
  %m01_dst_al = extractvalue %desc %r, 1
  %m01_dst_off = extractvalue %desc %r, 2
  %m01_dst_s0 = extractvalue %desc %r, 4, 0
  %m01_dst_s1 = extractvalue %desc %r, 4, 1
  %m01_dst_m0 = mul i64 0, %m01_dst_s0
  %m01_dst_a0 = add i64 %m01_dst_off, %m01_dst_m0
  %m01_dst_m1 = mul i64 1, %m01_dst_s1
  %m01_dst_a1 = add i64 %m01_dst_a0, %m01_dst_m1
  %m01_dst_p = getelementptr float, ptr %m01_dst_al, i64 %m01_dst_a1
  store float %m01, ptr %m01_dst_p
  %x02_al = extractvalue %desc %x, 1
  %x02_off = extractvalue %desc %x, 2
  %x02_s0 = extractvalue %desc %x, 4, 0
  %x02_s1 = extractvalue %desc %x, 4, 1
  %x02_m0 = mul i64 0, %x02_s0
  %x02_a0 = add i64 %x02_off, %x02_m0
  %x02_m1 = mul i64 2, %x02_s1
  %x02_a1 = add i64 %x02_a0, %x02_m1
  %x02_p = getelementptr float, ptr %x02_al, i64 %x02_a1
  %x02 = load float, ptr %x02_p
  %g02 = fcmp ogt float %x02, 0.000000e+00
  %m02 = select i1 %g02, float %x02, float 0.000000e+00
  %m02_dst_al = extractvalue %desc %r, 1
  %m02_dst_off = extractvalue %desc %r, 2
  %m02_dst_s0 = extractvalue %desc %r, 4, 0
  %m02_dst_s1 = extractvalue %desc %r, 4, 1
  %m02_dst_m0 = mul i64 0, %m02_dst_s0
  %m02_dst_a0 = add i64 %m02_dst_off, %m02_dst_m0
  %m02_dst_m1 = mul i64 2, %m02_dst_s1
  %m02_dst_a1 = add i64 %m02_dst_a0, %m02_dst_m1
  %m02_dst_p = getelementptr float, ptr %m02_dst_al, i64 %m02_dst_a1
  store float %m02, ptr %m02_dst_p
  %x10_al = extractvalue %desc %x, 1
  %x10_off = extractvalue %desc %x, 2
  %x10_s0 = extractvalue %desc %x, 4, 0
  %x10_s1 = extractvalue %desc %x, 4, 1
  %x10_m0 = mul i64 1, %x10_s0
  %x10_a0 = add i64 %x10_off, %x10_m0
  %x10_m1 = mul i64 0, %x10_s1
  %x10_a1 = add i64 %x10_a0, %x10_m1
  %x10_p = getelementptr float, ptr %x10_al, i64 %x10_a1
  %x10 = load float, ptr %x10_p
  %g10 = fcmp ogt float %x10, 0.000000e+00
  %m10 = select i1 %g10, float %x10, float 0.000000e+00
  %m10_dst_al = extractvalue %desc %r, 1
  %m10_dst_off = extractvalue %desc %r, 2
  %m10_dst_s0 = extractvalue %desc %r, 4, 0
  %m10_dst_s1 = extractvalue %desc %r, 4, 1
  %m10_dst_m0 = mul i64 1, %m10_dst_s0
  %m10_dst_a0 = add i64 %m10_dst_off, %m10_dst_m0
  %m10_dst_m1 = mul i64 0, %m10_dst_s1
  %m10_dst_a1 = add i64 %m10_dst_a0, %m10_dst_m1
  %m10_dst_p = getelementptr float, ptr %m10_dst_al, i64 %m10_dst_a1
  store float %m10, ptr %m10_dst_p
  %x11_al = extractvalue %desc %x, 1
  %x11_off = extractvalue %desc %x, 2
  %x11_s0 = extractvalue %desc %x, 4, 0
  %x11_s1 = extractvalue %desc %x, 4, 1
  %x11_m0 = mul i64 1, %x11_s0
  %x11_a0 = add i64 %x11_off, %x11_m0
  %x11_m1 = mul i64 1, %x11_s1
  %x11_a1 = add i64 %x11_a0, %x11_m1
  %x11_p = getelementptr float, ptr %x11_al, i64 %x11_a1
  %x11 = load float, ptr %x11_p
  %g11 = fcmp ogt float %x11, 0.000000e+00
  %m11 = select i1 %g11, float %x11, float 0.000000e+00
  %m11_dst_al = extractvalue %desc %r, 1
  %m11_dst_off = extractvalue %desc %r, 2
  %m11_dst_s0 = extractvalue %desc %r, 4, 0
  %m11_dst_s1 = extractvalue %desc %r, 4, 1
  %m11_dst_m0 = mul i64 1, %m11_dst_s0
  %m11_dst_a0 = add i64 %m11_dst_off, %m11_dst_m0
  %m11_dst_m1 = mul i64 1, %m11_dst_s1
  %m11_dst_a1 = add i64 %m11_dst_a0, %m11_dst_m1
  %m11_dst_p = getelementptr float, ptr %m11_dst_al, i64 %m11_dst_a1
  store float %m11, ptr %m11_dst_p
  %x12_al = extractvalue %desc %x, 1
  %x12_off = extractvalue %desc %x, 2
  %x12_s0 = extractvalue %desc %x, 4, 0
  %x12_s1 = extractvalue %desc %x, 4, 1
  %x12_m0 = mul i64 1, %x12_s0
  %x12_a0 = add i64 %x12_off, %x12_m0
  %x12_m1 = mul i64 2, %x12_s1
  %x12_a1 = add i64 %x12_a0, %x12_m1
  %x12_p = getelementptr float, ptr %x12_al, i64 %x12_a1
  %x12 = load float, ptr %x12_p
  %g12 = fcmp ogt float %x12, 0.000000e+00
  %m12 = select i1 %g12, float %x12, float 0.000000e+00
  %m12_dst_al = extractvalue %desc %r, 1
  %m12_dst_off = extractvalue %desc %r, 2
  %m12_dst_s0 = extractvalue %desc %r, 4, 0
  %m12_dst_s1 = extractvalue %desc %r, 4, 1
  %m12_dst_m0 = mul i64 1, %m12_dst_s0
  %m12_dst_a0 = add i64 %m12_dst_off, %m12_dst_m0
  %m12_dst_m1 = mul i64 2, %m12_dst_s1
  %m12_dst_a1 = add i64 %m12_dst_a0, %m12_dst_m1
  %m12_dst_p = getelementptr float, ptr %m12_dst_al, i64 %m12_dst_a1
  store float %m12, ptr %m12_dst_p
  ret %desc %r
}

define void @_mlir_ciface_relu(ptr %x_p, ptr %outp) {
entry:
  %x = load %desc, ptr %x_p
  %r = call %desc @relu(%desc %x)
  store %desc %r, ptr %outp
  ret void
}
