#map = affine_map<(d0, d1) -> (d0, d1)>
module {
  func.func @sandwich(%arg0: tensor<2x3xf32>) -> tensor<2x3xf32> {
    %cst = arith.constant 0.000000e+00 : f32
    %0 = tensor.empty() : tensor<3x2xf32>
    %transposed = linalg.transpose ins(%arg0 : tensor<2x3xf32>) outs(%0 : tensor<3x2xf32>) permutation = [1, 0] 
    %1 = tensor.empty() : tensor<3x2xf32>
    %2 = linalg.generic {indexing_maps = [#map, #map], iterator_types = ["parallel", "parallel"]} ins(%transposed : tensor<3x2xf32>) outs(%1 : tensor<3x2xf32>) {
    ^bb0(%in: f32, %out: f32):
      %4 = arith.cmpf ogt, %in, %cst : f32
      %5 = arith.select %4, %in, %cst : f32
      linalg.yield %5 : f32
    } -> tensor<3x2xf32>
    %3 = tensor.empty() : tensor<2x3xf32>
    %transposed_0 = linalg.transpose ins(%2 : tensor<3x2xf32>) outs(%3 : tensor<2x3xf32>) permutation = [1, 0] 
    return %transposed_0 : tensor<2x3xf32>
  }
}

