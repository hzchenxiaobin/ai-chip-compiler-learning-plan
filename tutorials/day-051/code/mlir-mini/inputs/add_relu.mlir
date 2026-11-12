module {
  func.func @graph(%a: tensor<2x2xf32>, %b: tensor<2x2xf32>) -> tensor<2x2xf32> {
    %t = mini.add %a, %b : tensor<2x2xf32>
    %r = mini.relu %t : tensor<2x2xf32>
    func.return %r : tensor<2x2xf32>
  }
}
