; 第 116 天：由 op_lowering.py 从源 IR 转换导出（函数 step）
target triple = "aarch64-unknown-linux-gnu"
declare ptr @malloc(i64)

define  i64 @step(i64 %i, i64 %k) {
entry:
  %s = add i64 %i, %k
  %p = mul i64 %s, 2
  ret i64 %p
}
