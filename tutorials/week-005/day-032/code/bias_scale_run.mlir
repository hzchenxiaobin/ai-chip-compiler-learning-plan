// bias_scale_run.mlir —— 主示例的可执行版本（JIT 打印 13）
// 同样计算 (x + bias) × scale，但把张量算子亲手展开成标量循环：
//   外层 %i 走行（0..2 开区间，见 Day 31），内层 %j 走列（0..3）
// 每个元素用 tensor.extract 取出（结果是 f32 标量），
// 标量算完后用 tensor.insert 放回（类型从标量又变回张量）。
// 这正是 Day 88「生成三重循环」的预告：张量 op 的语义＝对每个元素做标量运算。
func.func @main() -> i32 {
  // dense<0.5> 是 splat：6 个元素全是 0.5
  %x = arith.constant dense<0.5> : tensor<2x3xf32>
  %bias = arith.constant dense<[[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]> : tensor<2x3xf32>
  // 标量常量：FloatAttr，不是 dense（张量数据才用 dense）
  %scale = arith.constant 2.0 : f32
  // 循环边界必须是 index 类型（Day 31 的教训）
  %c0 = arith.constant 0 : index
  %c1 = arith.constant 1 : index
  %c2 = arith.constant 2 : index
  %c3 = arith.constant 3 : index
  %out_i = scf.for %i = %c0 to %c2 step %c1 iter_args(%acc_i = %x) -> (tensor<2x3xf32>) {
    %out_j = scf.for %j = %c0 to %c3 step %c1 iter_args(%acc = %acc_i) -> (tensor<2x3xf32>) {
      // tensor.extract：tensor<2x3xf32> + 2 个 index → 1 个 f32
      %xe = tensor.extract %x[%i, %j] : tensor<2x3xf32>
      %be = tensor.extract %bias[%i, %j] : tensor<2x3xf32>
      // 下面三行全是 f32 标量运算
      %add = arith.addf %xe, %be : f32
      %mul = arith.mulf %add, %scale : f32
      // tensor.insert：f32 放回 tensor<2x3xf32>，返回新张量
      %ins = tensor.insert %mul into %acc[%i, %j] : tensor<2x3xf32>
      scf.yield %ins : tensor<2x3xf32>
    }
    scf.yield %out_j : tensor<2x3xf32>
  }
  // 取 [1][2] 位置：x=0.5，bias=6.0 → (0.5+6.0)×2.0 = 13.0
  %r1 = arith.constant 1 : index
  %r2 = arith.constant 2 : index
  %elem = tensor.extract %out_i[%r1, %r2] : tensor<2x3xf32>
  // f32 → i32 没有隐式转换，必须显式 cast（向零截断）
  %r = arith.fptosi %elem : f32 to i32
  return %r : i32
}
