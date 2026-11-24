// 正例 2：秩 0 也能过。Mini_F32Tensor 不限秩（和 mini.add 同款），
// tensor<f32> * tensor<f32> -> tensor<f32> 是合法的逐元素乘。
// 对照：mini.matmul 的 Mini_F32Tensor2DPlus 要求秩 >= 2——
// 同一个 ODS 词汇表里两种约束，各自表达各自算子的"形状口味"。
func.func @mul_scalar(%a: tensor<f32>, %b: tensor<f32>) -> tensor<f32> {
  %p = mini.mul %a, %b : tensor<f32>, tensor<f32> -> tensor<f32>
  func.return %p : tensor<f32>
}
