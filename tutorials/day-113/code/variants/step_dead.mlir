// 变体 B（5.4 的对照实验）：加一条计算了但从未使用的 %dead。
// 预期目标无关优化（instcombine）直接删掉它——"没用到的计算"
// 不需要任何 CPU 信息就能判定可删。
module {
  llvm.func @step_dead(%arg0: i32) -> i32 {
    %c2 = llvm.mlir.constant(2 : i32) : i32
    %c3 = llvm.mlir.constant(3 : i32) : i32
    %c4 = llvm.mlir.constant(4 : i32) : i32
    %c0 = llvm.mlir.constant(0 : i32) : i32
    %five = llvm.add %c2, %c3 : i32
    %s20 = llvm.mul %five, %c4 : i32
    %z = llvm.add %arg0, %c0 : i32
    %dead = llvm.add %z, %c3 : i32
    %cond = llvm.icmp "sgt" %z, %s20 : i32
    llvm.cond_br %cond, ^hi, ^lo
  ^hi:
    %x1 = llvm.add %z, %s20 : i32
    llvm.br ^merge(%x1 : i32)
  ^lo:
    %x2 = llvm.sub %z, %s20 : i32
    llvm.br ^merge(%x2 : i32)
  ^merge(%m: i32):
    llvm.return %m : i32
  }
}
