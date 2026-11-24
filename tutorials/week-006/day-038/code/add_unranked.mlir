// 负例 C：mini.add 用了无秩张量 tensor<*xf32>。
// mini 的算子都要求 RankedTensor（有秩张量）——shape 至少在类型层面是已知的，
// 后面的 Shape 推导（第 43 天起）才有据可依。
// 迷惑点：tensor<*xf32> 和 tensor<*xf32> 类型确实"一致"，
// SameOperandsAndResultType 这关能过，但 Mini_F32Tensor 过不了。
module {
  func.func @unranked_add(%a: tensor<*xf32>, %b: tensor<*xf32>) -> tensor<*xf32> {
    %s = mini.add %a, %b : tensor<*xf32>, tensor<*xf32> -> tensor<*xf32>
    func.return %s : tensor<*xf32>
  }
}
