module {
  func.func @cc(%arg0: tensor<2x3x4xf32>) -> tensor<24xf32> {
    %collapsed = tensor.collapse_shape %arg0 [[0, 1, 2]] : tensor<2x3x4xf32> into tensor<24xf32>
    return %collapsed : tensor<24xf32>
  }
}

