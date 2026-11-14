; 第 114 天真机验证：由 final_lowering.py 从目标形态导出（教学 ABI：描述符按指针）
target triple = "aarch64-unknown-linux-gnu"
declare ptr @malloc(i64)

define void @gemm(ptr %ap, ptr %bp, ptr %outp) {
entry:
  %a = load { ptr, ptr, i64, [2 x i64], [2 x i64] }, ptr %ap
  %b = load { ptr, ptr, i64, [2 x i64], [2 x i64] }, ptr %bp
  %mem_c = call ptr @malloc(i64 48)
  %c_1 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } undef, ptr %mem_c, 0
  %c_2 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %c_1, ptr %mem_c, 1
  %c_3 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %c_2, i64 0, 2
  %c_4 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %c_3, i64 4, 3, 0
  %c_5 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %c_4, i64 3, 3, 1
  %c_6 = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %c_5, i64 3, 4, 0
  %c = insertvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %c_6, i64 1, 4, 1
  br label %i_hdr
i_hdr:
  %i = phi i64 [ 0, %entry ], [ %in, %j_done ]
  %cmp_i = icmp slt i64 %i, 4
  br i1 %cmp_i, label %i_body, label %i_done
i_body:
  br label %j_hdr
j_hdr:
  %j = phi i64 [ 0, %i_body ], [ %jn, %k_done ]
  %cmp_j = icmp slt i64 %j, 3
  br i1 %cmp_j, label %j_body, label %j_done
j_body:
  br label %k_hdr
k_hdr:
  %k = phi i64 [ 0, %j_body ], [ %kn, %k_body ]
  %acc_h = phi float [ 0.000000e+00, %j_body ], [ %s, %k_body ]
  %cmp_k = icmp slt i64 %k, 6
  br i1 %cmp_k, label %k_body, label %k_done
k_body:
  %a_al = extractvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %a, 1
  %a_off = extractvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %a, 2
  %a_s0 = extractvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %a, 4, 0
  %a_s1 = extractvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %a, 4, 1
  %a_m0 = mul i64 %i, %a_s0
  %a_m1 = mul i64 %k, %a_s1
  %a_lin = add i64 %a_m0, %a_m1
  %a_ix = add i64 %a_lin, %a_off
  %a_ptr = getelementptr float, ptr %a_al, i64 %a_ix
  %xa = load float, ptr %a_ptr
  %b_al = extractvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %b, 1
  %b_off = extractvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %b, 2
  %b_s0 = extractvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %b, 4, 0
  %b_s1 = extractvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %b, 4, 1
  %b_m0 = mul i64 %k, %b_s0
  %b_m1 = mul i64 %j, %b_s1
  %b_lin = add i64 %b_m0, %b_m1
  %b_ix = add i64 %b_lin, %b_off
  %b_ptr = getelementptr float, ptr %b_al, i64 %b_ix
  %xb = load float, ptr %b_ptr
  %p = fmul float %xa, %xb
  %s = fadd float %acc_h, %p
  %kn = add i64 %k, 1
  br label %k_hdr
k_done:
  %acc = phi float [ %acc_h, %k_hdr ]
  %c_st_al = extractvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %c, 1
  %c_st_off = extractvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %c, 2
  %c_st_s0 = extractvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %c, 4, 0
  %c_st_s1 = extractvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %c, 4, 1
  %c_st_m0 = mul i64 %i, %c_st_s0
  %c_st_m1 = mul i64 %j, %c_st_s1
  %c_st_lin = add i64 %c_st_m0, %c_st_m1
  %c_st_ix = add i64 %c_st_lin, %c_st_off
  %c_st_ptr = getelementptr float, ptr %c_st_al, i64 %c_st_ix
  store float %acc, ptr %c_st_ptr
  %jn = add i64 %j, 1
  br label %j_hdr
j_done:
  %in = add i64 %i, 1
  br label %i_hdr
i_done:
  store { ptr, ptr, i64, [2 x i64], [2 x i64] } %c, ptr %outp
  ret void
}
