module {
  func.func @combo_shape(%arg0: tensor<2x3xf32>, %arg1: tensor<3x2xf32>) -> tensor<2x2xf32> {
    %0 = mini.constant dense<1.000000e+00> : tensor<2x2xf32>
    %1 = mini.matmul %arg0, %arg1 : tensor<2x3xf32>, tensor<3x2xf32> -> tensor<?x2xf32>
    %2 = mini.mul %1, %0 : tensor<?x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
    %3 = mini.relu %2 : tensor<2x2xf32> -> tensor<2x2xf32>
    return %3 : tensor<2x2xf32>
  }
}

