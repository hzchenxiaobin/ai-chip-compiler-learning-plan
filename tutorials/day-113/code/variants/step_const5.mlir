// 变体 A（5.4 的对照实验）：把乘数 4 换成 5。
// 其余与 step.mlir 完全一致——预期 (2+3)*5 折叠成 25，
// 优化后 IR 里所有 20 变 25，两个目标的汇编立即数跟着变 25。
module {
  llvm.func @step5(%arg0: i32) -> i32 {
    %c2 = llvm.mlir.constant(2 : i32) : i32
    %c3 = llvm.mlir.constant(3 : i32) : i32
    %c5 = llvm.mlir.constant(5 : i32) : i32
    %c0 = llvm.mlir.constant(0 : i32) : i32
    %five = llvm.add %c2, %c3 : i32
    %s25 = llvm.mul %five, %c5 : i32
    %z = llvm.add %arg0, %c0 : i32
    %cond = llvm.icmp "sgt" %z, %s25 : i32
    llvm.cond_br %cond, ^hi, ^lo
  ^hi:
    %x1 = llvm.add %z, %s25 : i32
    llvm.br ^merge(%x1 : i32)
  ^lo:
    %x2 = llvm.sub %z, %s25 : i32
    llvm.br ^merge(%x2 : i32)
  ^merge(%m: i32):
    llvm.return %m : i32
  }
}
