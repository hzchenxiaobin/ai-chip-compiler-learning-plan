module {
  func.func @probe(%a: memref<2x2xf32, strided<[2, 1]>>) -> f32 {
    %c0 = arith.constant 0 : index
    %c1 = arith.constant 1 : index
    %v00 = memref.load %a[%c0, %c0] : memref<2x2xf32, strided<[2, 1]>>
    %v11 = memref.load %a[%c1, %c1] : memref<2x2xf32, strided<[2, 1]>>
    %s = arith.addf %v00, %v11 : f32
    func.return %s : f32
  }
}
