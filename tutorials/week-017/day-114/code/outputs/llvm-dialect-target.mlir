llvm.func @gemm(%a: !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>, %b: !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>) -> !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> {
  entry:   // 入口块：分配 + 描述符 + 常量
    %b_c = llvm.mlir.constant(48 : i64) : i64
    %mem_c = llvm.call @malloc(%b_c : i64) : (i64) -> !llvm.ptr
    %c_u = llvm.mlir.undef : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
    %c_off = llvm.mlir.constant(0 : i64) : i64
    %c_s0 = llvm.mlir.constant(4 : i64) : i64
    %c_s1 = llvm.mlir.constant(3 : i64) : i64
    %c_t0 = llvm.mlir.constant(3 : i64) : i64
    %c_t1 = llvm.mlir.constant(1 : i64) : i64
    %c_1 = llvm.insertvalue %mem_c, %c_u[0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> -> !llvm.ptr
    %c_2 = llvm.insertvalue %mem_c, %c_1[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> -> !llvm.ptr
    %c_3 = llvm.insertvalue %c_off, %c_2[2] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> -> i64
    %c_4 = llvm.insertvalue %c_s0, %c_3[3, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> -> i64
    %c_5 = llvm.insertvalue %c_s1, %c_4[3, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> -> i64
    %c_6 = llvm.insertvalue %c_t0, %c_5[4, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> -> i64
    %c = llvm.insertvalue %c_t1, %c_6[4, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> -> i64
    %zero = llvm.mlir.constant(0.0 : f32) : f32
    %c0 = llvm.mlir.constant(0 : i64) : i64
    %c1 = llvm.mlir.constant(1 : i64) : i64
    %cM = llvm.mlir.constant(4 : i64) : i64
    %cN = llvm.mlir.constant(3 : i64) : i64
    %cK = llvm.mlir.constant(6 : i64) : i64
    llvm.br ^i_hdr(%c0 : i64)
  ^i_hdr(%i: i64):
    %cmp_i = llvm.icmp "slt" %i, %cM : i64
    llvm.cond_br %cmp_i, ^i_body, ^i_done
  ^i_body:
    llvm.br ^j_hdr(%c0 : i64)
  ^j_hdr(%j: i64):
    %cmp_j = llvm.icmp "slt" %j, %cN : i64
    llvm.cond_br %cmp_j, ^j_body, ^j_done
  ^j_body:
    llvm.br ^k_hdr(%c0 : i64, %zero : f32)
  ^k_hdr(%k: i64, %acc_h: f32):
    %cmp_k = llvm.icmp "slt" %k, %cK : i64
    llvm.cond_br %cmp_k, ^k_body, ^k_done(%acc_h : f32)
  ^k_body:
    %a_al = llvm.extractvalue %a[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> -> !llvm.ptr
    %a_off = llvm.extractvalue %a[2] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> -> i64
    %a_s0 = llvm.extractvalue %a[4, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> -> i64
    %a_s1 = llvm.extractvalue %a[4, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> -> i64
    %a_m0 = llvm.mul %i, %a_s0 : i64
    %a_m1 = llvm.mul %k, %a_s1 : i64
    %a_lin = llvm.add %a_m0, %a_m1 : i64
    %a_ix = llvm.add %a_lin, %a_off : i64
    %a_ptr = llvm.getelementptr %a_al[%a_ix] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %xa = llvm.load %a_ptr : !llvm.ptr -> f32
    %b_al = llvm.extractvalue %b[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> -> !llvm.ptr
    %b_off = llvm.extractvalue %b[2] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> -> i64
    %b_s0 = llvm.extractvalue %b[4, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> -> i64
    %b_s1 = llvm.extractvalue %b[4, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> -> i64
    %b_m0 = llvm.mul %k, %b_s0 : i64
    %b_m1 = llvm.mul %j, %b_s1 : i64
    %b_lin = llvm.add %b_m0, %b_m1 : i64
    %b_ix = llvm.add %b_lin, %b_off : i64
    %b_ptr = llvm.getelementptr %b_al[%b_ix] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %xb = llvm.load %b_ptr : !llvm.ptr -> f32
    %p = llvm.fmul %xa, %xb : f32
    %s = llvm.fadd %acc_h, %p : f32
    %kn = llvm.add %k, %c1 : i64
    llvm.br ^k_hdr(%kn : i64, %s : f32)
  ^k_done(%acc: f32):
    %c_st_al = llvm.extractvalue %c[1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> -> !llvm.ptr
    %c_st_off = llvm.extractvalue %c[2] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> -> i64
    %c_st_s0 = llvm.extractvalue %c[4, 0] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> -> i64
    %c_st_s1 = llvm.extractvalue %c[4, 1] : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)> -> i64
    %c_st_m0 = llvm.mul %i, %c_st_s0 : i64
    %c_st_m1 = llvm.mul %j, %c_st_s1 : i64
    %c_st_lin = llvm.add %c_st_m0, %c_st_m1 : i64
    %c_st_ix = llvm.add %c_st_lin, %c_st_off : i64
    %c_st_ptr = llvm.getelementptr %c_st_al[%c_st_ix] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    llvm.store %acc, %c_st_ptr : f32, !llvm.ptr
    %jn = llvm.add %j, %c1 : i64
    llvm.br ^j_hdr(%jn : i64)
  ^j_done:
    %in = llvm.add %i, %c1 : i64
    llvm.br ^i_hdr(%in : i64)
  ^i_done:
    llvm.return %c : !llvm.struct<(ptr, ptr, i64, array<2 x i64>, array<2 x i64>)>
}

// 运行库依赖：真实 MLIR 由 MemRefToLLVM 自动声明 malloc
llvm.func @malloc(i64) -> !llvm.ptr
