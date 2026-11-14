// 标量 step（第 116 天输入③）：只审 A2（index 整数运算 -> i64）
func @step(%i: index, %k: index) -> index {
  %c2 = arith.constant 2 : index
  %s = arith.addi %i, %k : index
  %p = arith.muli %s, %c2 : index
  return %p : index
}
