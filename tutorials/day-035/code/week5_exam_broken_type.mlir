module {
  func.func @clamped_dot(%x: tensor<4xf32>, %bias: f32) -> f32 {
    %zero = arith.constant 0 : index
    %c0 = arith.constant 0 : index
    %c4 = arith.constant 4 : index
    %c1 = arith.constant 1 : index
    %sum = scf.for %i = %c0 to %c4 step %c1 iter_args(%acc = %zero) -> (f32) {
      %xi = tensor.extract %x[%i] : tensor<4xf32>
      %biased = arith.addf %xi, %bias : f32
      %clamped = arith.maximumf %biased, %zero : f32
      %new = arith.addf %acc, %clamped : f32
      scf.yield %new : f32
    }
    return %sum : f32
  }
}
