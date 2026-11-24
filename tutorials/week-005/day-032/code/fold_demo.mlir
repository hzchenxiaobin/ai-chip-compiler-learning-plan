// fold_demo.mlir —— 常量为什么住在属性里：一次折叠实验
// 9 条 op 里藏着一条 cast 链（extf → truncf、index_cast → sitofp），
// --canonicalize 全部折成 1 条 arith.constant 6.0：
// Pass 直接读两个 value 属性算出 2.0 × 3.0 = 6.0，
// 连转换链都被顺藤摸瓜消掉——属性「能被读出来参与计算」，类型不能。
func.func @main() -> f32 {
  %a = arith.constant 2.0 : f32
  %b = arith.constant 3.0 : f32
  %c = arith.mulf %a, %b : f32
  %d = arith.extf %c : f32 to f64      // 精度扩展
  %e = arith.truncf %d : f64 to f32    // 精度缩减
  %zi = arith.constant 0 : index
  %z = arith.index_cast %zi : index to i32  // index ↔ 整数（Day 31 见过）
  %g = arith.sitofp %z : i32 to f32    // 有符号整数 → 浮点
  %h = arith.addf %e, %g : f32
  return %h : f32
}
