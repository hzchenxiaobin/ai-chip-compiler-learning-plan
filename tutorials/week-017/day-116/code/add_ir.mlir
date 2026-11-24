// 第 2×2 elementwise Add（第 116 天输入①，展开形态：无 scf.for）
func @add(%a: memref<2x2xf32, strided<[2, 1]>>,
         %b: memref<2x2xf32, strided<[2, 1]>>) -> memref<2x2xf32, strided<[2, 1]>> {
  %c = memref.alloc() : memref<2x2xf32, strided<[2, 1]>>
  %c0 = arith.constant 0 : index
  %c1 = arith.constant 1 : index
  %a00 = memref.load %a[%c0, %c0] : memref<2x2xf32, strided<[2, 1]>>
  %b00 = memref.load %b[%c0, %c0] : memref<2x2xf32, strided<[2, 1]>>
  %s00 = arith.addf %a00, %b00 : f32
  memref.store %s00, %c[%c0, %c0] : memref<2x2xf32, strided<[2, 1]>>
  %a01 = memref.load %a[%c0, %c1] : memref<2x2xf32, strided<[2, 1]>>
  %b01 = memref.load %b[%c0, %c1] : memref<2x2xf32, strided<[2, 1]>>
  %s01 = arith.addf %a01, %b01 : f32
  memref.store %s01, %c[%c0, %c1] : memref<2x2xf32, strided<[2, 1]>>
  %a10 = memref.load %a[%c1, %c0] : memref<2x2xf32, strided<[2, 1]>>
  %b10 = memref.load %b[%c1, %c0] : memref<2x2xf32, strided<[2, 1]>>
  %s10 = arith.addf %a10, %b10 : f32
  memref.store %s10, %c[%c1, %c0] : memref<2x2xf32, strided<[2, 1]>>
  %a11 = memref.load %a[%c1, %c1] : memref<2x2xf32, strided<[2, 1]>>
  %b11 = memref.load %b[%c1, %c1] : memref<2x2xf32, strided<[2, 1]>>
  %s11 = arith.addf %a11, %b11 : f32
  memref.store %s11, %c[%c1, %c1] : memref<2x2xf32, strided<[2, 1]>>
  return %c : memref<2x2xf32, strided<[2, 1]>>
}
