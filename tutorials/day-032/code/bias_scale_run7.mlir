// bias_scale_run7.mlir —— 5.4 节对照实验（JIT 打印 15）
// 与 bias_scale_run.mlir 只差一处属性：bias 的 [1][2] 元素从 6.0 改成 7.0
// 改的是 dense 属性里的一个数（数据），类型 tensor<2x3xf32> 纹丝不动
// (0.5 + 7.0) × 2.0 = 15.0 → fptosi → 15
func.func @main() -> i32 {
  %x = arith.constant dense<0.5> : tensor<2x3xf32>
  %bias = arith.constant dense<[[1.0, 2.0, 3.0], [4.0, 5.0, 7.0]]> : tensor<2x3xf32>
  %scale = arith.constant 2.0 : f32
  %c0 = arith.constant 0 : index
  %c1 = arith.constant 1 : index
  %c2 = arith.constant 2 : index
  %c3 = arith.constant 3 : index
  %out_i = scf.for %i = %c0 to %c2 step %c1 iter_args(%acc_i = %x) -> (tensor<2x3xf32>) {
    %out_j = scf.for %j = %c0 to %c3 step %c1 iter_args(%acc = %acc_i) -> (tensor<2x3xf32>) {
      %xe = tensor.extract %x[%i, %j] : tensor<2x3xf32>
      %be = tensor.extract %bias[%i, %j] : tensor<2x3xf32>
      %add = arith.addf %xe, %be : f32
      %mul = arith.mulf %add, %scale : f32
      %ins = tensor.insert %mul into %acc[%i, %j] : tensor<2x3xf32>
      scf.yield %ins : tensor<2x3xf32>
    }
    scf.yield %out_j : tensor<2x3xf32>
  }
  %r1 = arith.constant 1 : index
  %r2 = arith.constant 2 : index
  %elem = tensor.extract %out_i[%r1, %r2] : tensor<2x3xf32>
  %r = arith.fptosi %elem : f32 to i32
  return %r : i32
}
