module {
  func.func @reshape_chain(%arg0: tensor<2x3xf32>) -> tensor<3x2xf32> {
    %cst = arith.constant dense<6> : tensor<1xi32>
    %cst_0 = arith.constant dense<[3, 2]> : tensor<2xi32>
    %reshape = tensor.reshape %arg0(%cst) : (tensor<2x3xf32>, tensor<1xi32>) -> tensor<6xf32>
    %reshape_1 = tensor.reshape %reshape(%cst_0) : (tensor<6xf32>, tensor<2xi32>) -> tensor<3x2xf32>
    return %reshape_1 : tensor<3x2xf32>
  }
}

