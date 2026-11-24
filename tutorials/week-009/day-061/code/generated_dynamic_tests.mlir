// generated_dynamic_tests.mlir —— 由 dynamic_lab.py 第 6 节生成。
// M/N/K 各取 {静态, 动态} 的 8 种组合；输出类型由 mini 推导后写出。
// 动态维一律用 ? 表示——MLIR 的 ? 分不出「符号」和「未知」，
// 这正是 shape dialect 要用 witness 补的信息（见 k_constraint.mlir）。

module {
  // room_0_M2_K3_N2：输出 (2, 2)
  func.func @room_0_M2_K3_N2(%a: tensor<2x3xf32>, %b: tensor<3x2xf32>, %init: tensor<2x2xf32>) -> tensor<2x2xf32> {
    %r = linalg.matmul ins(%a, %b : tensor<2x3xf32>, tensor<3x2xf32>) outs(%init : tensor<2x2xf32>) -> tensor<2x2xf32>
    return %r : tensor<2x2xf32>
  }

  // room_1_M2_K3_Ndyn：输出 (2, None)
  func.func @room_1_M2_K3_Ndyn(%a: tensor<2x3xf32>, %b: tensor<3x?xf32>, %init: tensor<2x?xf32>) -> tensor<2x?xf32> {
    %r = linalg.matmul ins(%a, %b : tensor<2x3xf32>, tensor<3x?xf32>) outs(%init : tensor<2x?xf32>) -> tensor<2x?xf32>
    return %r : tensor<2x?xf32>
  }

  // room_2_M2_Kdyn_N2：输出 (2, 2)，约束 ['dim(A,1) == dim(B,0)']
  func.func @room_2_M2_Kdyn_N2(%a: tensor<2x?xf32>, %b: tensor<?x2xf32>, %init: tensor<2x2xf32>) -> tensor<2x2xf32> {
    %r = linalg.matmul ins(%a, %b : tensor<2x?xf32>, tensor<?x2xf32>) outs(%init : tensor<2x2xf32>) -> tensor<2x2xf32>
    return %r : tensor<2x2xf32>
  }

  // room_3_M2_Kdyn_Ndyn：输出 (2, None)，约束 ['dim(A,1) == dim(B,0)']
  func.func @room_3_M2_Kdyn_Ndyn(%a: tensor<2x?xf32>, %b: tensor<?x?xf32>, %init: tensor<2x?xf32>) -> tensor<2x?xf32> {
    %r = linalg.matmul ins(%a, %b : tensor<2x?xf32>, tensor<?x?xf32>) outs(%init : tensor<2x?xf32>) -> tensor<2x?xf32>
    return %r : tensor<2x?xf32>
  }

  // room_4_Mdyn_K3_N2：输出 (None, 2)
  func.func @room_4_Mdyn_K3_N2(%a: tensor<?x3xf32>, %b: tensor<3x2xf32>, %init: tensor<?x2xf32>) -> tensor<?x2xf32> {
    %r = linalg.matmul ins(%a, %b : tensor<?x3xf32>, tensor<3x2xf32>) outs(%init : tensor<?x2xf32>) -> tensor<?x2xf32>
    return %r : tensor<?x2xf32>
  }

  // room_5_Mdyn_K3_Ndyn：输出 (None, None)
  func.func @room_5_Mdyn_K3_Ndyn(%a: tensor<?x3xf32>, %b: tensor<3x?xf32>, %init: tensor<?x?xf32>) -> tensor<?x?xf32> {
    %r = linalg.matmul ins(%a, %b : tensor<?x3xf32>, tensor<3x?xf32>) outs(%init : tensor<?x?xf32>) -> tensor<?x?xf32>
    return %r : tensor<?x?xf32>
  }

  // room_6_Mdyn_Kdyn_N2：输出 (None, 2)，约束 ['dim(A,1) == dim(B,0)']
  func.func @room_6_Mdyn_Kdyn_N2(%a: tensor<?x?xf32>, %b: tensor<?x2xf32>, %init: tensor<?x2xf32>) -> tensor<?x2xf32> {
    %r = linalg.matmul ins(%a, %b : tensor<?x?xf32>, tensor<?x2xf32>) outs(%init : tensor<?x2xf32>) -> tensor<?x2xf32>
    return %r : tensor<?x2xf32>
  }

  // room_7_Mdyn_Kdyn_Ndyn：输出 (None, None)，约束 ['dim(A,1) == dim(B,0)']
  func.func @room_7_Mdyn_Kdyn_Ndyn(%a: tensor<?x?xf32>, %b: tensor<?x?xf32>, %init: tensor<?x?xf32>) -> tensor<?x?xf32> {
    %r = linalg.matmul ins(%a, %b : tensor<?x?xf32>, tensor<?x?xf32>) outs(%init : tensor<?x?xf32>) -> tensor<?x?xf32>
    return %r : tensor<?x?xf32>
  }

}
