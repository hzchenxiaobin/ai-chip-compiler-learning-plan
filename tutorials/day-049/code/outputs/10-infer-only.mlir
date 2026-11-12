module {
  func.func @combo_shape(%arg0: tensor<2x3xf32>, %arg1: tensor<3x2xf32>) -> tensor<2x2xf32> {
    %0 = mini.constant dense<5.000000e-01> : tensor<2x2xf32>
    %1 = mini.constant dense<5.000000e-01> : tensor<2x2xf32>
    %2 = mini.add %0, %1 : tensor<2x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
    %3 = mini.matmul %arg0, %arg1 : tensor<2x3xf32>, tensor<3x2xf32> -> tensor<2x2xf32>
    %4 = mini.mul %3, %2 : tensor<2x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
    %5 = mini.relu %4 : tensor<2x2xf32> -> tensor<2x2xf32>
    %6 = mini.relu %5 : tensor<2x2xf32> -> tensor<2x2xf32>
    return %6 : tensor<2x2xf32>
  }
}

