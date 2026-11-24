; ModuleID = 'LLVMDialectModule'
define i32 @step_dead(i32 %0) {
  %2 = add i32 2, 3
  %3 = mul i32 %2, 4
  %4 = add i32 %0, 0
  %5 = add i32 %4, 3
  %6 = icmp sgt i32 %4, %3
  br i1 %6, label %7, label %9
7:
  %8 = add i32 %4, %3
  br label %11
9:
  %10 = sub i32 %4, %3
  br label %11
11:
  %12 = phi i32 [ %8, %7 ], [ %10, %9 ]
  ret i32 %12
}
