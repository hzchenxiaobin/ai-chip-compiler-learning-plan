// order_arith.mlir —— 探针 3：pass 顺序敏感（常量折叠解锁 CSE）。
//
// %r1 = x + 4.0（常量直接给）
// %r2 = x + (2.0 * 2.0)（常量要 canonicalize 折出来）
// 两个 addf 语义完全相同，但初始 IR 里操作数不同。
//
// 本机 LLVM 18.1.8 实测（2026-11-12）：
//   mlir-opt order_arith.mlir --canonicalize --cse
//     → 1 个 addf（return %0, %0）——先折常量，CSE 认出双胞胎
//   mlir-opt order_arith.mlir --cse --canonicalize
//     → 2 个 addf（return %0, %1）——CSE 先跑时 %c3 还不是常量
//   mlir-opt order_arith.mlir --cse --canonicalize --cse
//     → 1 个 addf ——补一趟 cse 追平：差的是调度，不是能力
//
// 结论：mlir-opt 的 pass 按命令行顺序一次性执行，不回头。
// 「先造机会的在前，用机会的在后」——顺序是真实编译器的真实决策。

module {
  func.func @order_arith(%x: f32) -> (f32, f32) {
    %c1 = arith.constant 4.0 : f32
    %r1 = arith.addf %x, %c1 : f32
    %c2 = arith.constant 2.0 : f32
    %c3 = arith.mulf %c2, %c2 : f32
    %r2 = arith.addf %x, %c3 : f32
    return %r1, %r2 : f32, f32
  }
}
