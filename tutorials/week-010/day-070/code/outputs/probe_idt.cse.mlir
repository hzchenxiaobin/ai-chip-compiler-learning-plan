module {
  func.func @identity_perm_layout(%arg0: memref<2x3xf32, strided<[3, 1], offset: ?>>) -> memref<2x3xf32> {
    %alloc = memref.alloc() : memref<2x3xf32>
    linalg.transpose ins(%arg0 : memref<2x3xf32, strided<[3, 1], offset: ?>>) outs(%alloc : memref<2x3xf32>) permutation = [0, 1] 
    return %alloc : memref<2x3xf32>
  }
}

