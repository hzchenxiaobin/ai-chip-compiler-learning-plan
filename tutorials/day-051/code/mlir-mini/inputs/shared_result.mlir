module {
  func.func @graph_shared(%a: tensor<2x2xf32>, %b: tensor<2x2xf32>, %c: tensor<2x2xf32>) -> (tensor<2x2xf32>, tensor<2x2xf32>) {
    %t = mini.add %a, %b : tensor<2x2xf32>
    %r = mini.relu %t : tensor<2x2xf32>
    %s = mini.add %r, %c : tensor<2x2xf32>
    func.return %r, %s : tensor<2x2xf32>, tensor<2x2xf32>
  }
}
