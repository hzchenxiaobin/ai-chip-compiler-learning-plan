module {
  func.func @chain(%arg0: memref<2x3x4xf32>) -> memref<2x3x4xf32> {
    %alloc = memref.alloc() : memref<3x4x2xf32>
    linalg.transpose ins(%arg0 : memref<2x3x4xf32>) outs(%alloc : memref<3x4x2xf32>) permutation = [1, 2, 0] 
    %alloc_0 = memref.alloc() : memref<2x3x4xf32>
    linalg.transpose ins(%alloc : memref<3x4x2xf32>) outs(%alloc_0 : memref<2x3x4xf32>) permutation = [2, 0, 1] 
    return %alloc_0 : memref<2x3x4xf32>
  }
}

