// 第 113 天贯穿例子：step(i32 %a) -> i32
// 语义（可用来手算验证）：
//   s20 = (2 + 3) * 4        // = 20，故意写成两步，观察目标无关优化怎么折叠它
//   z   = a + 0              // 故意加零，观察指令化简怎么消掉它
//   cond = z > s20
//   return cond ? z + s20 : z - s20
//
// 本文件是 MLIR 的 LLVM Dialect（llvm.* 一族 Operation）。
// 真实工具链里用 mlir-translate --mlir-to-llvmir 把它导出成 LLVM IR；
// 本教程用教学版 mini_translate.py 覆盖其中 9 个 op（见 README 5.2）。
//
// 只用到这些 op：
//   llvm.func / llvm.mlir.constant / llvm.add / llvm.mul / llvm.sub /
//   llvm.icmp / llvm.cond_br / llvm.br / llvm.return
module {
  llvm.func @step(%arg0: i32) -> i32 {
    %c2 = llvm.mlir.constant(2 : i32) : i32
    %c3 = llvm.mlir.constant(3 : i32) : i32
    %c4 = llvm.mlir.constant(4 : i32) : i32
    %c0 = llvm.mlir.constant(0 : i32) : i32
    %five = llvm.add %c2, %c3 : i32
    %s20 = llvm.mul %five, %c4 : i32
    %z = llvm.add %arg0, %c0 : i32
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
