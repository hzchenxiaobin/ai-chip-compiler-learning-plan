module {
  func.func @main_kernel(%arg0: memref<4x6xf32, strided<[6, 1]>>, %arg1: memref<6x3xf32, strided<[3, 1]>>, %arg2: memref<3xf32, strided<[1]>>) -> memref<4x3xf32> attributes {llvm.emit_c_interface} {
    %alloc = memref.alloc() : memref<4x3xf32>
    return %alloc : memref<4x3xf32>
  }
}

