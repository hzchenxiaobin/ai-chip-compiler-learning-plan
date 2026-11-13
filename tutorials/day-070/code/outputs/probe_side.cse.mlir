module {
  func.func @side_effect(%arg0: memref<2x3xf32>, %arg1: f32, %arg2: f32, %arg3: f32) {
    %c0 = arith.constant 0 : index
    memref.store %arg1, %arg0[%c0, %c0] : memref<2x3xf32>
    return
  }
}

