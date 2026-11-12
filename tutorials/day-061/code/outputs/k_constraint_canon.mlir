module {
  func.func @static_ok(%arg0: tensor<2x3xf32>, %arg1: tensor<3x2xf32>, %arg2: tensor<2x2xf32>) -> tensor<2x2xf32> {
    %0 = linalg.matmul ins(%arg0, %arg1 : tensor<2x3xf32>, tensor<3x2xf32>) outs(%arg2 : tensor<2x2xf32>) -> tensor<2x2xf32>
    return %0 : tensor<2x2xf32>
  }
  func.func @dynamic_checked(%arg0: tensor<?x?xf32>, %arg1: tensor<?x?xf32>, %arg2: tensor<?x?xf32>) -> tensor<?x?xf32> {
    %c0 = arith.constant 0 : index
    %c1 = arith.constant 1 : index
    %0 = shape.shape_of %arg0 : tensor<?x?xf32> -> tensor<2xindex>
    %1 = shape.shape_of %arg1 : tensor<?x?xf32> -> tensor<2xindex>
    %2 = shape.get_extent %0, %c1 : tensor<2xindex>, index -> !shape.size
    %3 = shape.get_extent %1, %c0 : tensor<2xindex>, index -> !shape.size
    %4 = shape.size_to_index %2 : !shape.size
    %5 = shape.size_to_index %3 : !shape.size
    %6 = arith.cmpi eq, %4, %5 : index
    %7 = shape.cstr_require %6, "matmul: K dims must match"
    %8 = shape.assuming %7 -> (tensor<?x?xf32>) {
      %9 = linalg.matmul ins(%arg0, %arg1 : tensor<?x?xf32>, tensor<?x?xf32>) outs(%arg2 : tensor<?x?xf32>) -> tensor<?x?xf32>
      shape.assuming_yield %9 : tensor<?x?xf32>
    }
    return %8 : tensor<?x?xf32>
  }
}

