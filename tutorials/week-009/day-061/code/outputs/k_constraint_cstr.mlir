module {
  func.func @static_ok(%arg0: tensor<2x3xf32>, %arg1: tensor<3x2xf32>, %arg2: tensor<2x2xf32>) -> tensor<2x2xf32> {
    %0 = shape.const_witness true
    %c0 = arith.constant 0 : index
    %c1 = arith.constant 1 : index
    %1 = shape.shape_of %arg0 : tensor<2x3xf32> -> !shape.shape
    %2 = shape.shape_of %arg1 : tensor<3x2xf32> -> !shape.shape
    %3 = shape.get_extent %1, %c1 : !shape.shape, index -> !shape.size
    %4 = shape.get_extent %2, %c0 : !shape.shape, index -> !shape.size
    %5 = shape.size_to_index %3 : !shape.size
    %6 = shape.size_to_index %4 : !shape.size
    %7 = arith.cmpi eq, %5, %6 : index
    cf.assert %7, "matmul: K dims must match"
    %8 = shape.assuming %0 -> (tensor<2x2xf32>) {
      %9 = linalg.matmul ins(%arg0, %arg1 : tensor<2x3xf32>, tensor<3x2xf32>) outs(%arg2 : tensor<2x2xf32>) -> tensor<2x2xf32>
      shape.assuming_yield %9 : tensor<2x2xf32>
    }
    return %8 : tensor<2x2xf32>
  }
  func.func @dynamic_checked(%arg0: tensor<?x?xf32>, %arg1: tensor<?x?xf32>, %arg2: tensor<?x?xf32>) -> tensor<?x?xf32> {
    %0 = shape.const_witness true
    %c0 = arith.constant 0 : index
    %c1 = arith.constant 1 : index
    %1 = shape.shape_of %arg0 : tensor<?x?xf32> -> !shape.shape
    %2 = shape.shape_of %arg1 : tensor<?x?xf32> -> !shape.shape
    %3 = shape.get_extent %1, %c1 : !shape.shape, index -> !shape.size
    %4 = shape.get_extent %2, %c0 : !shape.shape, index -> !shape.size
    %5 = shape.size_to_index %3 : !shape.size
    %6 = shape.size_to_index %4 : !shape.size
    %7 = arith.cmpi eq, %5, %6 : index
    cf.assert %7, "matmul: K dims must match"
    %8 = shape.assuming %0 -> (tensor<?x?xf32>) {
      %9 = linalg.matmul ins(%arg0, %arg1 : tensor<?x?xf32>, tensor<?x?xf32>) outs(%arg2 : tensor<?x?xf32>) -> tensor<?x?xf32>
      shape.assuming_yield %9 : tensor<?x?xf32>
    }
    return %8 : tensor<?x?xf32>
  }
}

