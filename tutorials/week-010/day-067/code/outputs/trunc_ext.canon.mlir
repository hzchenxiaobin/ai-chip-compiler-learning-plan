module {
  func.func @trunc_ext(%arg0: f16) -> f16 {
    %0 = arith.extf %arg0 : f16 to f32
    %1 = arith.truncf %0 : f32 to f16
    return %1 : f16
  }
}

