module {
  func.func @order_arith(%arg0: f32) -> (f32, f32) {
    %cst = arith.constant 4.000000e+00 : f32
    %0 = arith.addf %arg0, %cst : f32
    return %0, %0 : f32, f32
  }
}

