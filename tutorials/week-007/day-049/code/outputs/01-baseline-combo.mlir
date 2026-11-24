module {
  func.func @combo(%arg0: tensor<2x2xf32>) -> tensor<2x2xf32> {
    %0 = mini.constant dense<5.000000e-01> : tensor<2x2xf32>
    %1 = mini.constant dense<5.000000e-01> : tensor<2x2xf32>
    %2 = mini.add %0, %1 : tensor<2x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
    %3 = mini.relu %arg0 : tensor<2x2xf32> -> tensor<2x2xf32>
    %4 = mini.mul %3, %2 : tensor<2x2xf32>, tensor<2x2xf32> -> tensor<2x2xf32>
    %5 = mini.relu %4 : tensor<2x2xf32> -> tensor<2x2xf32>
    return %5 : tensor<2x2xf32>
  }
}

