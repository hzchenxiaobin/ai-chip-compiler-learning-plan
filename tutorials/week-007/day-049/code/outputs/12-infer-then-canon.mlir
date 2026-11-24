module {
  func.func @combo_shape(%arg0: tensor<2x3xf32>, %arg1: tensor<3x2xf32>) -> tensor<2x2xf32> {
    %0 = mini.matmul %arg0, %arg1 : tensor<2x3xf32>, tensor<3x2xf32> -> tensor<2x2xf32>
    %1 = mini.relu %0 : tensor<2x2xf32> -> tensor<2x2xf32>
    return %1 : tensor<2x2xf32>
  }
}

