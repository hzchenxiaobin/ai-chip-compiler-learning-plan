module {
  func.func @ext_trunc(%arg0: f32) -> f32 {
    %0 = arith.truncf %arg0 : f32 to f16
    %1 = arith.extf %0 : f16 to f32
    return %1 : f32
  }
}

