; 第 118 天路线 3：JIT——lli 解释执行入口。
; 与 gemm-3.ll 拼接成单模块（run_all.sh 完成 cat），lli 不产任何中间文件：
; parse ->（可选 opt）-> MCJIT 编译到内存 -> 执行 main。
; 数据以全局常量内嵌（教学规模）；描述符在全局区构造后传给包装函数。
@A = global [24 x float] [float 5.000000e-01, float -1.000000e+00, float 2.000000e+00, float 0.000000e+00, float 1.500000e+00, float -5.000000e-01,
                          float 1.000000e+00, float 1.000000e+00, float 1.000000e+00, float 1.000000e+00, float 1.000000e+00, float 1.000000e+00,
                          float -2.000000e+00, float 5.000000e-01, float 0.000000e+00, float 3.000000e+00, float -1.000000e+00, float 2.000000e+00,
                          float 0.000000e+00, float 0.000000e+00, float 5.000000e-01, float 5.000000e-01, float 5.000000e-01, float 5.000000e-01]
@B = global [18 x float] [float 1.000000e+00, float 2.000000e+00, float 3.000000e+00,
                          float 4.000000e+00, float 5.000000e+00, float 6.000000e+00,
                          float 7.000000e+00, float 8.000000e+00, float 9.000000e+00,
                          float 1.000000e+01, float 1.100000e+01, float 1.200000e+01,
                          float 1.300000e+01, float 1.400000e+01, float 1.500000e+01,
                          float 1.600000e+01, float 1.700000e+01, float 1.800000e+01]
@Adesc = global { ptr, ptr, i64, [2 x i64], [2 x i64] } { ptr @A, ptr @A, i64 0, [2 x i64] [i64 4, i64 6], [2 x i64] [i64 6, i64 1] }
@Bdesc = global { ptr, ptr, i64, [2 x i64], [2 x i64] } { ptr @B, ptr @B, i64 0, [2 x i64] [i64 6, i64 3], [2 x i64] [i64 3, i64 1] }
@Cdesc = global { ptr, ptr, i64, [2 x i64], [2 x i64] } zeroinitializer

@.fmt = private constant [12 x i8] c"C[%d]=%.2f\0A\00"
declare i32 @printf(ptr, ...)

define i32 @main() {
entry:
  call void @_mlir_ciface_gemm(ptr @Cdesc, ptr @Adesc, ptr @Bdesc)
  br label %loop
loop:
  %i = phi i64 [ 0, %entry ], [ %next, %body ]
  %done = icmp sge i64 %i, 12
  br i1 %done, label %exit, label %body
body:
  %cptr = load ptr, ptr @Cdesc                 ; 读回 kernel 填充的 malloc 指针
  %addr = getelementptr float, ptr %cptr, i64 %i
  %v = load float, ptr %addr
  %idx32 = trunc i64 %i to i32
  call i32 (ptr, ...) @printf(ptr @.fmt, i32 %idx32, float %v)
  %next = add i64 %i, 1
  br label %loop
exit:
  ret i32 0
}
