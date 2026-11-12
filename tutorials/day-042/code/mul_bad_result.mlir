// 负例 5：结果侧写错——操作数 2x2 * 2x2 没问题，res 写成 2x3。
// 规则 1（操作数一致）通过，规则 2（结果一致）拦截。
// 预期报错：result shape must equal the operand shape: operands are
// tensor<2x2xf32> and tensor<2x2xf32>, but result is tensor<2x3xf32>（rc=1）。
func.func @mul_bad_res(%a: tensor<2x2xf32>, %b: tensor<2x2xf32>) -> tensor<2x3xf32> {
  %p = mini.mul %a, %b : tensor<2x2xf32>, tensor<2x2xf32> -> tensor<2x3xf32>
  func.return %p : tensor<2x3xf32>
}
