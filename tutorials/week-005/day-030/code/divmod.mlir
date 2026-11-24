// divmod.mlir —— 第 30 天副例：一条 op 多个结果 + JIT 可执行
//
// divmod(a, b) 返回 (商, 余数)：main 里一条 func.call 一次拿到两个结果。
// main 把两者相加：17 = 5 × 3 + 2 → q + r = 3 + 2 = 5（JIT 应打印 5）。

module {
  // 返回类型是 (i32, i32)：函数可以一次返回两个值。
  func.func @divmod(%a: i32, %b: i32) -> (i32, i32) {
    // [定义] %q  [使用] %a, %b  [类型] (i32, i32) -> i32
    %q = arith.divsi %a, %b : i32
    // [定义] %r  [使用] %a, %b  [类型] (i32, i32) -> i32
    %r = arith.remsi %a, %b : i32
    // 两个操作数、零个结果；值经函数签名流回调用方。
    return %q, %r : i32, i32
  }

  func.func @main() -> i32 {
    %seventeen = arith.constant 17 : i32
    %five = arith.constant 5 : i32
    // [定义] %q %r（一条 op 定义两个值：等号左边写了两个名字）
    // [使用] %seventeen, %five  [类型] (i32, i32) -> (i32, i32)
    %q, %r = func.call @divmod(%seventeen, %five) : (i32, i32) -> (i32, i32)
    %sum = arith.addi %q, %r : i32
    return %sum : i32
  }
}
