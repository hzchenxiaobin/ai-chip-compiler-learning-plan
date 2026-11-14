; ModuleID = '<string>'
source_filename = "<string>"

define range(i32 41, 1) i32 @step(i32 %0) {
  %2 = icmp sgt i32 %0, 20
  %3 = add nuw i32 %0, 20
  %4 = add i32 %0, -20
  %5 = select i1 %2, i32 %3, i32 %4
  ret i32 %5
}
