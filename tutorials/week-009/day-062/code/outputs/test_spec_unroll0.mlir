#map = affine_map<(d0) -> (d0 + 1)>
#map1 = affine_map<(d0) -> (d0 + 2)>
module {
  func.func @matmul(%arg0: memref<2x3xf32>, %arg1: memref<3x2xf32>, %arg2: memref<2x2xf32>) {
    %c0 = arith.constant 0 : index
    affine.for %arg3 = 0 to 2 {
      affine.for %arg4 = 0 to 2 {
        %0 = affine.load %arg0[%arg3, %c0] : memref<2x3xf32>
        %1 = affine.load %arg1[%c0, %arg4] : memref<3x2xf32>
        %2 = affine.load %arg2[%arg3, %arg4] : memref<2x2xf32>
        %3 = arith.mulf %0, %1 : f32
        %4 = arith.addf %2, %3 : f32
        affine.store %4, %arg2[%arg3, %arg4] : memref<2x2xf32>
        %5 = affine.apply #map(%c0)
        %6 = affine.load %arg0[%arg3, %5] : memref<2x3xf32>
        %7 = affine.load %arg1[%5, %arg4] : memref<3x2xf32>
        %8 = affine.load %arg2[%arg3, %arg4] : memref<2x2xf32>
        %9 = arith.mulf %6, %7 : f32
        %10 = arith.addf %8, %9 : f32
        affine.store %10, %arg2[%arg3, %arg4] : memref<2x2xf32>
        %11 = affine.apply #map1(%c0)
        %12 = affine.load %arg0[%arg3, %11] : memref<2x3xf32>
        %13 = affine.load %arg1[%11, %arg4] : memref<3x2xf32>
        %14 = affine.load %arg2[%arg3, %arg4] : memref<2x2xf32>
        %15 = arith.mulf %12, %13 : f32
        %16 = arith.addf %14, %15 : f32
        affine.store %16, %arg2[%arg3, %arg4] : memref<2x2xf32>
      }
    }
    return
  }
}

