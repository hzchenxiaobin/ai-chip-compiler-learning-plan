module {
  func.func @bad(%a: memref<4x6xf32, strided<[6, 1]>>) -> f32 {
    %f0 = arith.constant 0.0 : f32
    %v = vector.broadcast %f0 : f32 to vector<4xf32>
    %r = vector.reduce %v : vector<4xf32> into f32
    func.return %r : f32
  }
}
