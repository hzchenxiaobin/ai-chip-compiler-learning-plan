func.func @exercise(%a: tensor<2x3xf32>, %b: tensor<3x2xf32>,
                    %x: tensor<2x2xf32>)
    -> (tensor<?x2xf32>, tensor<2x2xf32>) {
  %c0 = mini.constant dense<5.000000e-01> : tensor<2x2xf32>
  %c1 = mini.constant dense<5.000000e-01> : tensor<2x2xf32>
  %one = mini.add %c0, %c1 : tensor<2x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
  %m = mini.matmul %a, %b : tensor<2x3xf32>, tensor<3x2xf32> -> tensor<?x2xf32>
  %s = mini.add %m, %one : tensor<?x2xf32>, tensor<2x2xf32> -> tensor<?x2xf32>
  %r = mini.relu %s : tensor<?x2xf32>
  %z = mini.constant dense<0.000000e+00> : tensor<2x2xf32>
  %t = mini.add %x, %z : tensor<2x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
  %u = mini.relu %t : tensor<2x2xf32>
  return %r, %u : tensor<?x2xf32>, tensor<2x2xf32>
}
