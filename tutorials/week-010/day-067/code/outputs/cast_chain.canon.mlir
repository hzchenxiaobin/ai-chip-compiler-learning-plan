module {
  func.func @bitcast_same(%arg0: f32) -> f32 {
    return %arg0 : f32
  }
  func.func @trunc_ext(%arg0: f16) -> f16 {
    %0 = arith.extf %arg0 : f16 to f32
    %1 = arith.truncf %0 : f32 to f16
    return %1 : f16
  }
  func.func @ext_trunc(%arg0: f32) -> f32 {
    %0 = arith.truncf %arg0 : f32 to f16
    %1 = arith.extf %0 : f16 to f32
    return %1 : f32
  }
  func.func @truncsi_extsi(%arg0: i8) -> i8 {
    return %arg0 : i8
  }
  func.func @extsi_trunc(%arg0: i32) -> i32 {
    %0 = arith.trunci %arg0 : i32 to i8
    %1 = arith.extsi %0 : i8 to i32
    return %1 : i32
  }
  func.func @bitcast_chain(%arg0: f32) -> f32 {
    return %arg0 : f32
  }
}

