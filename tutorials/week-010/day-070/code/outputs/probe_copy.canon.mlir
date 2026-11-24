module {
  func.func @copy_identity(%arg0: memref<2x3xf32>) -> memref<2x3xf32> {
    %alloc = memref.alloc() : memref<2x3xf32>
    memref.copy %arg0, %alloc : memref<2x3xf32> to memref<2x3xf32>
    return %alloc : memref<2x3xf32>
  }
}

