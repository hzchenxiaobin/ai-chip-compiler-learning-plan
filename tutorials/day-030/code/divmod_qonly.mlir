// divmod_qonly.mlir —— 5.4 节对照实验：只使用第一个结果 %q。
//
// 预测点：(1) 第二个结果（余数 %r）没人使用，MLIR 会报错吗？
//         (2) JIT 会打印几？
// 答案见教程 5.4：不报错——「没人用」是 Day 25 DCE 要处理的事，不是 Verifier 的事；
// JIT 打印 3（17 ÷ 5 的商；余数 2 被闲置）。

module {
  func.func @divmod(%a: i32, %b: i32) -> (i32, i32) {
    %q = arith.divsi %a, %b : i32
    %r = arith.remsi %a, %b : i32
    return %q, %r : i32, i32
  }
  func.func @main() -> i32 {
    %seventeen = arith.constant 17 : i32
    %five = arith.constant 5 : i32
    %q, %r = func.call @divmod(%seventeen, %five) : (i32, i32) -> (i32, i32)
    return %q : i32
  }
}
