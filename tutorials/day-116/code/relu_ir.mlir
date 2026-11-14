// 第 2×2 elementwise Relu（第 116 天输入②，展开形态）
func @relu(%x: memref<2x2xf32, strided<[2, 1]>>) -> memref<2x2xf32, strided<[2, 1]>> {
  %zero = arith.constant 0.0 : f32
  %r = memref.alloc() : memref<2x2xf32, strided<[2, 1]>>
  %c0 = arith.constant 0 : index
  %c1 = arith.constant 1 : index
  %x00 = memref.load %x[%c0, %c0] : memref<2x2xf32, strided<[2, 1]>>
  %g00 = arith.cmpf ogt %x00, %zero : f32
  %m00 = arith.select %g00, %x00, %zero : f32
  memref.store %m00, %r[%c0, %c0] : memref<2x2xf32, strided<[2, 1]>>
  %x01 = memref.load %x[%c0, %c1] : memref<2x2xf32, strided<[2, 1]>>
  %g01 = arith.cmpf ogt %x01, %zero : f32
  %m01 = arith.select %g01, %x01, %zero : f32
  memref.store %m01, %r[%c0, %c1] : memref<2x2xf32, strided<[2, 1]>>
  %x10 = memref.load %x[%c1, %c0] : memref<2x2xf32, strided<[2, 1]>>
  %g10 = arith.cmpf ogt %x10, %zero : f32
  %m10 = arith.select %g10, %x10, %zero : f32
  memref.store %m10, %r[%c1, %c0] : memref<2x2xf32, strided<[2, 1]>>
  %x11 = memref.load %x[%c1, %c1] : memref<2x2xf32, strided<[2, 1]>>
  %g11 = arith.cmpf ogt %x11, %zero : f32
  %m11 = arith.select %g11, %x11, %zero : f32
  memref.store %m11, %r[%c1, %c1] : memref<2x2xf32, strided<[2, 1]>>
  return %r : memref<2x2xf32, strided<[2, 1]>>
}
