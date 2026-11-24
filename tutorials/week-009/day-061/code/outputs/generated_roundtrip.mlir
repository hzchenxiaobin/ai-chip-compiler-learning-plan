module {
  func.func @room_0_M2_K3_N2(%arg0: tensor<2x3xf32>, %arg1: tensor<3x2xf32>, %arg2: tensor<2x2xf32>) -> tensor<2x2xf32> {
    %0 = linalg.matmul ins(%arg0, %arg1 : tensor<2x3xf32>, tensor<3x2xf32>) outs(%arg2 : tensor<2x2xf32>) -> tensor<2x2xf32>
    return %0 : tensor<2x2xf32>
  }
  func.func @room_1_M2_K3_Ndyn(%arg0: tensor<2x3xf32>, %arg1: tensor<3x?xf32>, %arg2: tensor<2x?xf32>) -> tensor<2x?xf32> {
    %0 = linalg.matmul ins(%arg0, %arg1 : tensor<2x3xf32>, tensor<3x?xf32>) outs(%arg2 : tensor<2x?xf32>) -> tensor<2x?xf32>
    return %0 : tensor<2x?xf32>
  }
  func.func @room_2_M2_Kdyn_N2(%arg0: tensor<2x?xf32>, %arg1: tensor<?x2xf32>, %arg2: tensor<2x2xf32>) -> tensor<2x2xf32> {
    %0 = linalg.matmul ins(%arg0, %arg1 : tensor<2x?xf32>, tensor<?x2xf32>) outs(%arg2 : tensor<2x2xf32>) -> tensor<2x2xf32>
    return %0 : tensor<2x2xf32>
  }
  func.func @room_3_M2_Kdyn_Ndyn(%arg0: tensor<2x?xf32>, %arg1: tensor<?x?xf32>, %arg2: tensor<2x?xf32>) -> tensor<2x?xf32> {
    %0 = linalg.matmul ins(%arg0, %arg1 : tensor<2x?xf32>, tensor<?x?xf32>) outs(%arg2 : tensor<2x?xf32>) -> tensor<2x?xf32>
    return %0 : tensor<2x?xf32>
  }
  func.func @room_4_Mdyn_K3_N2(%arg0: tensor<?x3xf32>, %arg1: tensor<3x2xf32>, %arg2: tensor<?x2xf32>) -> tensor<?x2xf32> {
    %0 = linalg.matmul ins(%arg0, %arg1 : tensor<?x3xf32>, tensor<3x2xf32>) outs(%arg2 : tensor<?x2xf32>) -> tensor<?x2xf32>
    return %0 : tensor<?x2xf32>
  }
  func.func @room_5_Mdyn_K3_Ndyn(%arg0: tensor<?x3xf32>, %arg1: tensor<3x?xf32>, %arg2: tensor<?x?xf32>) -> tensor<?x?xf32> {
    %0 = linalg.matmul ins(%arg0, %arg1 : tensor<?x3xf32>, tensor<3x?xf32>) outs(%arg2 : tensor<?x?xf32>) -> tensor<?x?xf32>
    return %0 : tensor<?x?xf32>
  }
  func.func @room_6_Mdyn_Kdyn_N2(%arg0: tensor<?x?xf32>, %arg1: tensor<?x2xf32>, %arg2: tensor<?x2xf32>) -> tensor<?x2xf32> {
    %0 = linalg.matmul ins(%arg0, %arg1 : tensor<?x?xf32>, tensor<?x2xf32>) outs(%arg2 : tensor<?x2xf32>) -> tensor<?x2xf32>
    return %0 : tensor<?x2xf32>
  }
  func.func @room_7_Mdyn_Kdyn_Ndyn(%arg0: tensor<?x?xf32>, %arg1: tensor<?x?xf32>, %arg2: tensor<?x?xf32>) -> tensor<?x?xf32> {
    %0 = linalg.matmul ins(%arg0, %arg1 : tensor<?x?xf32>, tensor<?x?xf32>) outs(%arg2 : tensor<?x?xf32>) -> tensor<?x?xf32>
    return %0 : tensor<?x?xf32>
  }
}

