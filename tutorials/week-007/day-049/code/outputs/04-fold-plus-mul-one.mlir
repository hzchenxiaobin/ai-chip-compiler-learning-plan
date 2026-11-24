module {
  func.func @combo(%arg0: tensor<2x2xf32>) -> tensor<2x2xf32> {
    %0 = mini.relu %arg0 : tensor<2x2xf32> -> tensor<2x2xf32>
    %1 = mini.relu %0 : tensor<2x2xf32> -> tensor<2x2xf32>
    return %1 : tensor<2x2xf32>
  }
}

