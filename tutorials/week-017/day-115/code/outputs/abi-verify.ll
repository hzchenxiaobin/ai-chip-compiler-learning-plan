; 第 115 天真机 ABI 验证（LLVM 22.1.0，aarch64）
; 描述符经 ptr 传递：aarch64 C ABI 上 >16B 聚合按"间接"传（x0 = 调用方副本地址，
; gcc 实测 getoff_c(按值) 与 getoff_p(指针) 汇编一字不差，见 abi-ground-truth.s）。
target triple = "aarch64-unknown-linux-gnu"
%desc = type { ptr, ptr, i64, [2 x i64], [2 x i64] }

define float @peek(ptr %d, i64 %i, i64 %j) {
entry:
  %alp = getelementptr %desc, ptr %d, i32 0, i32 1
  %al  = load ptr, ptr %alp
  %ofp = getelementptr %desc, ptr %d, i32 0, i32 2
  %of  = load i64, ptr %ofp
  %s0p = getelementptr %desc, ptr %d, i32 0, i32 4, i32 0
  %s0  = load i64, ptr %s0p
  %s1p = getelementptr %desc, ptr %d, i32 0, i32 4, i32 1
  %s1  = load i64, ptr %s1p
  %t0  = mul i64 %i, %s0
  %t1  = mul i64 %j, %s1
  %tt  = add i64 %t0, %t1
  %ix  = add i64 %tt, %of
  %p   = getelementptr float, ptr %al, i64 %ix
  %v   = load float, ptr %p
  ret float %v
}

define float @mul2_out(ptr %d, i64 %i, i64 %j, ptr %out) {
entry:
  %alp = getelementptr %desc, ptr %d, i32 0, i32 1
  %al  = load ptr, ptr %alp
  %ofp = getelementptr %desc, ptr %d, i32 0, i32 2
  %of  = load i64, ptr %ofp
  %s0p = getelementptr %desc, ptr %d, i32 0, i32 4, i32 0
  %s0  = load i64, ptr %s0p
  %s1p = getelementptr %desc, ptr %d, i32 0, i32 4, i32 1
  %s1  = load i64, ptr %s1p
  %t0  = mul i64 %i, %s0
  %t1  = mul i64 %j, %s1
  %tt  = add i64 %t0, %t1
  %ix  = add i64 %tt, %of
  %p   = getelementptr float, ptr %al, i64 %ix
  %v   = load float, ptr %p
  %w   = fmul float %v, 2.0
  store float %w, ptr %out
  ret float %v
}

define i64 @echo(ptr %p) {
entry:
  %r = ptrtoint ptr %p to i64
  ret i64 %r
}

; --- ABI 误用对照（TP8）：三种签名形态，同一个字段读取 ---
define i64 @getoff(ptr %d) {
entry:
  %fp = getelementptr %desc, ptr %d, i32 0, i32 2
  %o  = load i64, ptr %fp
  ret i64 %o
}

define i64 @getoff_byval(ptr byval(%desc) %d) {
entry:
  %s = load %desc, ptr %d
  %o = extractvalue %desc %s, 2
  ret i64 %o
}

define i64 @getoff_agg({ ptr, ptr, i64, [2 x i64], [2 x i64] } %d) {
entry:
  %o = extractvalue { ptr, ptr, i64, [2 x i64], [2 x i64] } %d, 2
  ret i64 %o
}
