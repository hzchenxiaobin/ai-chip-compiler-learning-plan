module {
  memref.global constant @storage : memref<2x3xf32> = dense<[[0.000000e+00, 1.000000e+00, 2.000000e+00], [3.000000e+00, 4.000000e+00, 5.000000e+00]]>
  func.func @transpose_view() -> (index, index, index) {
    %c0 = arith.constant 0 : index
    %c1 = arith.constant 1 : index
    %c3 = arith.constant 3 : index
    return %c0, %c1, %c3 : index, index, index
  }
  func.func @offset_view(%arg0: memref<f32>) -> (index, index, index) {
    %c1 = arith.constant 1 : index
    %c2 = arith.constant 2 : index
    return %c1, %c2, %c1 : index, index, index
  }
}

