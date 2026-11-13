#map = affine_map<(d0, d1) -> (d0, d1)>
module {
  func.func @push_through_relu(%arg0: tensor<2x3xf32>) -> tensor<3x2xf32> {
    %cst = arith.constant 0.000000e+00 : f32
    %0 = tensor.empty() : tensor<2x3xf32>
    %1 = linalg.generic {indexing_maps = [#map, #map], iterator_types = ["parallel", "parallel"]} ins(%arg0 : tensor<2x3xf32>) outs(%0 : tensor<2x3xf32>) {
    ^bb0(%in: f32, %out: f32):
      %3 = arith.cmpf ogt, %in, %cst : f32
      %4 = arith.select %3, %in, %cst : f32
      linalg.yield %4 : f32
    } -> tensor<2x3xf32>
    %2 = tensor.empty() : tensor<3x2xf32>
    %transposed = linalg.transpose ins(%1 : tensor<2x3xf32>) outs(%2 : tensor<3x2xf32>) permutation = [1, 0] 
    return %transposed : tensor<3x2xf32>
  }
}

