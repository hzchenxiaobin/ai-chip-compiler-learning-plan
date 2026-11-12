// 5.4 对照实验：只把上界从 %n_idx 换成 %n_plus（n+1），
// 循环体一个字都不改 —— 验证「scf.for 上界是开区间」的推断。
module {
  func.func @sum_to_n(%n: i32) -> i32 {
    %zero = arith.constant 0 : index
    %one = arith.constant 1 : index
    %n_idx = arith.index_cast %n : i32 to index
    %n_plus = arith.addi %n_idx, %one : index
    %sum_idx = scf.for %i = %one to %n_plus step %one
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
