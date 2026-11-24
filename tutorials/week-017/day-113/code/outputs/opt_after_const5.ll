; ModuleID = '<string>'
source_filename = "<string>"

define range(i32 51, 1) i32 @step5(i32 %0) {
  %2 = icmp sgt i32 %0, 25
  %3 = add nuw i32 %0, 25
  %4 = add i32 %0, -25
  %5 = select i1 %2, i32 %3, i32 %4
  ret i32 %5
}
