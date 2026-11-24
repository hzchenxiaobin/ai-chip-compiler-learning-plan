// 层级自外向内：module（Operation，持 1 个 Region）
//   └─ Region ─ Block ^bb0 ─ func.func（Operation，持 1 个 Region）
//       └─ Region：3 个 Block 的菱形 CFG
module {
  func.func @branch_relu(%x: i32) -> i32 {
    // [定义] %c0、%neg —— 都定义在入口块 ^bb0
    %c0 = arith.constant 0 : i32
    %neg = arith.cmpi slt, %x, %c0 : i32

    // [终结符] 条件分支：真 → ^neg_zero 带 %c0；假 → ^merge 带 %x
    // 括号里的 (%c0 : i32) / (%x : i32) 是分支操作数——目标块参数的实参
    cf.cond_br %neg, ^neg_zero(%c0 : i32), ^merge(%x : i32)

  // ^neg_zero：负数路。(%zero: i32) 是后继块参数，由跳进来的边赋值
  ^neg_zero(%zero: i32):
    cf.br ^merge(%zero : i32)

  // ^merge：汇合块。%val 承担 Day 17 教科书里 phi(x, 0) 的职责
  ^merge(%val: i32):
    return %val : i32
  }
}
