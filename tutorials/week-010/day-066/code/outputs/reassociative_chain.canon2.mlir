module {
  func.func @cc(%arg0: tensor<2x3x4xf32>) -> tensor<24xf32> {
    %collapsed = tensor.collapse_shape %arg0 [[0, 1, 2]] : tensor<2x3x4xf32> into tensor<24xf32>
    return %collapsed : tensor<24xf32>
  }
  func.func @ee(%arg0: tensor<24xf32>) -> tensor<2x3x4xf32> {
    %expanded = tensor.expand_shape %arg0 [[0, 1, 2]] : tensor<24xf32> into tensor<2x3x4xf32>
    return %expanded : tensor<2x3x4xf32>
  }
  func.func @ec(%arg0: tensor<24xf32>) -> tensor<24xf32> {
    return %arg0 : tensor<24xf32>
  }
  func.func @ce(%arg0: tensor<2x3x4xf32>) -> tensor<6x2x2xf32> {
    %collapsed = tensor.collapse_shape %arg0 [[0, 1], [2]] : tensor<2x3x4xf32> into tensor<6x4xf32>
    %expanded = tensor.expand_shape %collapsed [[0], [1, 2]] : tensor<6x4xf32> into tensor<6x2x2xf32>
    return %expanded : tensor<6x2x2xf32>
  }
}

