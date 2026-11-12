// 第 31 天主示例②：结构化控制流——scf.for 是「一条持有 Region 的 Operation」。
// 循环变量 %i 和累加器 %acc 都是 Region 入口块的 BlockArgument：
//   scf.for（Operation，持 1 个 Region）
//     └─ Region（1 个 Block，带 2 个块参数：^bb0(%i: index, %acc: index)）
//         ├─ arith.addi
//         └─ scf.yield（终结符：把新累加值交还循环头）
// 注意：scf.for 的循环变量是 index 类型（循环下标专用类型，Day 30 见过它），
// 所以入口用 arith.index_cast 把 i32 的 %n 转成 index，出口再转回 i32。
// sum_to_n(5) = 1+2+3+4+5 = 15，一会儿 JIT 打印 15。
module {
  func.func @sum_to_n(%n: i32) -> i32 {
    %zero = arith.constant 0 : index
    %one = arith.constant 1 : index
    %n_idx = arith.index_cast %n : i32 to index
    // iter_args(%acc = %zero)：循环携带值——%acc 是块参数，初值 %zero
    %sum_idx = scf.for %i = %one to %n_idx step %one
                 iter_args(%acc = %zero) -> (index) {
      %new_acc = arith.addi %acc, %i : index
      scf.yield %new_acc : index
    }
    %sum = arith.index_cast %sum_idx : index to i32
    return %sum : i32
  }
  func.func @main() -> i32 {
    %five = arith.constant 5 : i32
    %r = func.call @sum_to_n(%five) : (i32) -> i32
    return %r : i32
  }
}
