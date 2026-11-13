module {
  func.func @chain(%arg0: tensor<2x3x4xf32>) -> tensor<24xf32> {
    %cst = arith.constant dense<[6, 4]> : tensor<2xi32>
    %cst_0 = arith.constant dense<24> : tensor<1xi32>
    %reshape = tensor.reshape %arg0(%cst) : (tensor<2x3x4xf32>, tensor<2xi32>) -> tensor<6x4xf32>
    %reshape_1 = tensor.reshape %reshape(%cst_0) : (tensor<6x4xf32>, tensor<1xi32>) -> tensor<24xf32>
    return %reshape_1 : tensor<24xf32>
  }
}

