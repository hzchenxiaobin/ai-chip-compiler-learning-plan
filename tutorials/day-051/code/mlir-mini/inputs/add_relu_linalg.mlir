func.func @add_relu(%a: tensor<2x2xf32>, %b: tensor<2x2xf32>) -> tensor<2x2xf32> {
  %zero = arith.constant dense<0.0> : tensor<2x2xf32>
  %t = arith.addf %a, %b : tensor<2x2xf32>
  %r = arith.maximumf %t, %zero : tensor<2x2xf32>
  return %r : tensor<2x2xf32>
}
