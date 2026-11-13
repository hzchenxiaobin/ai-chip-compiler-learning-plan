#map = affine_map<(d0, d1) -> (d0, d1)>
module {
  func.func @order_cast(%arg0: tensor<2x3xf32>) -> (tensor<2x3xf32>, tensor<2x3xf32>) {
    %cst = arith.constant 0.000000e+00 : f32
    %0 = tensor.empty() : tensor<2x3xf32>
    %1 = linalg.generic {indexing_maps = [#map, #map], iterator_types = ["parallel", "parallel"]} ins(%arg0 : tensor<2x3xf32>) outs(%0 : tensor<2x3xf32>) {
    ^bb0(%in: f32, %out: f32):
      %3 = arith.cmpf ogt, %in, %cst : f32
      %4 = arith.select %3, %in, %cst : f32
      linalg.yield %4 : f32
    } -> tensor<2x3xf32>
    %2 = linalg.generic {indexing_maps = [#map, #map], iterator_types = ["parallel", "parallel"]} ins(%arg0 : tensor<2x3xf32>) outs(%0 : tensor<2x3xf32>) {
    ^bb0(%in: f32, %out: f32):
      %3 = arith.cmpf ogt, %in, %cst : f32
      %4 = arith.select %3, %in, %cst : f32
      linalg.yield %4 : f32
    } -> tensor<2x3xf32>
    return %1, %2 : tensor<2x3xf32>, tensor<2x3xf32>
  }
}

