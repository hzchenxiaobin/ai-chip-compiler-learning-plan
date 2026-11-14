; 第 116 天：由 op_lowering.py 从源 IR 转换导出（函数 add）
target triple = "aarch64-unknown-linux-gnu"
%desc = type { ptr, ptr, i64, [2 x i64], [2 x i64] }
declare ptr @malloc(i64)

define internal %desc @add(%desc %a, %desc %b) noinline {
entry:
  %mem_c = call ptr @malloc(i64 16)
  %i0_c = insertvalue %desc undef, ptr %mem_c, 0
  %i1_c = insertvalue %desc %i0_c, ptr %mem_c, 1
  %i2_c = insertvalue %desc %i1_c, i64 0, 2
  %i3_c = insertvalue %desc %i2_c, i64 2, 3, 0
  %i4_c = insertvalue %desc %i3_c, i64 2, 3, 1
  %i5_c = insertvalue %desc %i4_c, i64 2, 4, 0
  %c = insertvalue %desc %i5_c, i64 1, 4, 1
  %a00_al = extractvalue %desc %a, 1
  %a00_off = extractvalue %desc %a, 2
  %a00_s0 = extractvalue %desc %a, 4, 0
  %a00_s1 = extractvalue %desc %a, 4, 1
  %a00_m0 = mul i64 0, %a00_s0
  %a00_a0 = add i64 %a00_off, %a00_m0
  %a00_m1 = mul i64 0, %a00_s1
  %a00_a1 = add i64 %a00_a0, %a00_m1
  %a00_p = getelementptr float, ptr %a00_al, i64 %a00_a1
  %a00 = load float, ptr %a00_p
  %b00_al = extractvalue %desc %b, 1
  %b00_off = extractvalue %desc %b, 2
  %b00_s0 = extractvalue %desc %b, 4, 0
  %b00_s1 = extractvalue %desc %b, 4, 1
  %b00_m0 = mul i64 0, %b00_s0
  %b00_a0 = add i64 %b00_off, %b00_m0
  %b00_m1 = mul i64 0, %b00_s1
  %b00_a1 = add i64 %b00_a0, %b00_m1
  %b00_p = getelementptr float, ptr %b00_al, i64 %b00_a1
  %b00 = load float, ptr %b00_p
  %s00 = fadd float %a00, %b00
  %s00_dst_al = extractvalue %desc %c, 1
  %s00_dst_off = extractvalue %desc %c, 2
  %s00_dst_s0 = extractvalue %desc %c, 4, 0
  %s00_dst_s1 = extractvalue %desc %c, 4, 1
  %s00_dst_m0 = mul i64 0, %s00_dst_s0
  %s00_dst_a0 = add i64 %s00_dst_off, %s00_dst_m0
  %s00_dst_m1 = mul i64 0, %s00_dst_s1
  %s00_dst_a1 = add i64 %s00_dst_a0, %s00_dst_m1
  %s00_dst_p = getelementptr float, ptr %s00_dst_al, i64 %s00_dst_a1
  store float %s00, ptr %s00_dst_p
  %a01_al = extractvalue %desc %a, 1
  %a01_off = extractvalue %desc %a, 2
  %a01_s0 = extractvalue %desc %a, 4, 0
  %a01_s1 = extractvalue %desc %a, 4, 1
  %a01_m0 = mul i64 0, %a01_s0
  %a01_a0 = add i64 %a01_off, %a01_m0
  %a01_m1 = mul i64 1, %a01_s1
  %a01_a1 = add i64 %a01_a0, %a01_m1
  %a01_p = getelementptr float, ptr %a01_al, i64 %a01_a1
  %a01 = load float, ptr %a01_p
  %b01_al = extractvalue %desc %b, 1
  %b01_off = extractvalue %desc %b, 2
  %b01_s0 = extractvalue %desc %b, 4, 0
  %b01_s1 = extractvalue %desc %b, 4, 1
  %b01_m0 = mul i64 0, %b01_s0
  %b01_a0 = add i64 %b01_off, %b01_m0
  %b01_m1 = mul i64 1, %b01_s1
  %b01_a1 = add i64 %b01_a0, %b01_m1
  %b01_p = getelementptr float, ptr %b01_al, i64 %b01_a1
  %b01 = load float, ptr %b01_p
  %s01 = fadd float %a01, %b01
  %s01_dst_al = extractvalue %desc %c, 1
  %s01_dst_off = extractvalue %desc %c, 2
  %s01_dst_s0 = extractvalue %desc %c, 4, 0
  %s01_dst_s1 = extractvalue %desc %c, 4, 1
  %s01_dst_m0 = mul i64 0, %s01_dst_s0
  %s01_dst_a0 = add i64 %s01_dst_off, %s01_dst_m0
  %s01_dst_m1 = mul i64 1, %s01_dst_s1
  %s01_dst_a1 = add i64 %s01_dst_a0, %s01_dst_m1
  %s01_dst_p = getelementptr float, ptr %s01_dst_al, i64 %s01_dst_a1
  store float %s01, ptr %s01_dst_p
  %a10_al = extractvalue %desc %a, 1
  %a10_off = extractvalue %desc %a, 2
  %a10_s0 = extractvalue %desc %a, 4, 0
  %a10_s1 = extractvalue %desc %a, 4, 1
  %a10_m0 = mul i64 1, %a10_s0
  %a10_a0 = add i64 %a10_off, %a10_m0
  %a10_m1 = mul i64 0, %a10_s1
  %a10_a1 = add i64 %a10_a0, %a10_m1
  %a10_p = getelementptr float, ptr %a10_al, i64 %a10_a1
  %a10 = load float, ptr %a10_p
  %b10_al = extractvalue %desc %b, 1
  %b10_off = extractvalue %desc %b, 2
  %b10_s0 = extractvalue %desc %b, 4, 0
  %b10_s1 = extractvalue %desc %b, 4, 1
  %b10_m0 = mul i64 1, %b10_s0
  %b10_a0 = add i64 %b10_off, %b10_m0
  %b10_m1 = mul i64 0, %b10_s1
  %b10_a1 = add i64 %b10_a0, %b10_m1
  %b10_p = getelementptr float, ptr %b10_al, i64 %b10_a1
  %b10 = load float, ptr %b10_p
  %s10 = fadd float %a10, %b10
  %s10_dst_al = extractvalue %desc %c, 1
  %s10_dst_off = extractvalue %desc %c, 2
  %s10_dst_s0 = extractvalue %desc %c, 4, 0
  %s10_dst_s1 = extractvalue %desc %c, 4, 1
  %s10_dst_m0 = mul i64 1, %s10_dst_s0
  %s10_dst_a0 = add i64 %s10_dst_off, %s10_dst_m0
  %s10_dst_m1 = mul i64 0, %s10_dst_s1
  %s10_dst_a1 = add i64 %s10_dst_a0, %s10_dst_m1
  %s10_dst_p = getelementptr float, ptr %s10_dst_al, i64 %s10_dst_a1
  store float %s10, ptr %s10_dst_p
  %a11_al = extractvalue %desc %a, 1
  %a11_off = extractvalue %desc %a, 2
  %a11_s0 = extractvalue %desc %a, 4, 0
  %a11_s1 = extractvalue %desc %a, 4, 1
  %a11_m0 = mul i64 1, %a11_s0
  %a11_a0 = add i64 %a11_off, %a11_m0
  %a11_m1 = mul i64 1, %a11_s1
  %a11_a1 = add i64 %a11_a0, %a11_m1
  %a11_p = getelementptr float, ptr %a11_al, i64 %a11_a1
  %a11 = load float, ptr %a11_p
  %b11_al = extractvalue %desc %b, 1
  %b11_off = extractvalue %desc %b, 2
  %b11_s0 = extractvalue %desc %b, 4, 0
  %b11_s1 = extractvalue %desc %b, 4, 1
  %b11_m0 = mul i64 1, %b11_s0
  %b11_a0 = add i64 %b11_off, %b11_m0
  %b11_m1 = mul i64 1, %b11_s1
  %b11_a1 = add i64 %b11_a0, %b11_m1
  %b11_p = getelementptr float, ptr %b11_al, i64 %b11_a1
  %b11 = load float, ptr %b11_p
  %s11 = fadd float %a11, %b11
  %s11_dst_al = extractvalue %desc %c, 1
  %s11_dst_off = extractvalue %desc %c, 2
  %s11_dst_s0 = extractvalue %desc %c, 4, 0
  %s11_dst_s1 = extractvalue %desc %c, 4, 1
  %s11_dst_m0 = mul i64 1, %s11_dst_s0
  %s11_dst_a0 = add i64 %s11_dst_off, %s11_dst_m0
  %s11_dst_m1 = mul i64 1, %s11_dst_s1
  %s11_dst_a1 = add i64 %s11_dst_a0, %s11_dst_m1
  %s11_dst_p = getelementptr float, ptr %s11_dst_al, i64 %s11_dst_a1
  store float %s11, ptr %s11_dst_p
  ret %desc %c
}

define void @_mlir_ciface_add(ptr %a_p, ptr %b_p, ptr %outp) {
entry:
  %a = load %desc, ptr %a_p
  %b = load %desc, ptr %b_p
  %r = call %desc @add(%desc %a, %desc %b)
  store %desc %r, ptr %outp
  ret void
}
