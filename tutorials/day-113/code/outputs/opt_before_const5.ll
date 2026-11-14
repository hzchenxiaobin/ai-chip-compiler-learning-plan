; ModuleID = '<string>'
source_filename = "<string>"

define i32 @step5(i32 %0) {
  %2 = add i32 2, 3
  %3 = mul i32 %2, 5
  %4 = add i32 %0, 0
  %5 = icmp sgt i32 %4, %3
  br i1 %5, label %6, label %8

6:                                                ; preds = %1
  %7 = add i32 %4, %3
  br label %10

8:                                                ; preds = %1
  %9 = sub i32 %4, %3
  br label %10

10:                                               ; preds = %8, %6
  %11 = phi i32 [ %7, %6 ], [ %9, %8 ]
  ret i32 %11
}
