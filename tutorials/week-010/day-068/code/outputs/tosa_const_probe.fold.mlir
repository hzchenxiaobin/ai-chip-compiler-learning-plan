module {
  func.func @const_transpose() -> tensor<3x2xf32> {
    %0 = "tosa.const"() <{value = dense<[[1.000000e+00, -4.000000e+00], [-2.000000e+00, 5.000000e+00], [3.000000e+00, -6.000000e+00]]> : tensor<3x2xf32>}> : () -> tensor<3x2xf32>
    return %0 : tensor<3x2xf32>
  }
}

