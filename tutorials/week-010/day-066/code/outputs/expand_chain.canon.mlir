module {
  func.func @ee(%arg0: tensor<24xf32>) -> tensor<2x3x4xf32> {
    %expanded = tensor.expand_shape %arg0 [[0, 1, 2]] : tensor<24xf32> into tensor<2x3x4xf32>
    return %expanded : tensor<2x3x4xf32>
  }
}

