#map = affine_map<(d0) -> (d0 + 1)>
#map1 = affine_map<(d0) -> (d0 + 2)>
module {
  func.func @matmul(%arg0: memref<2x3xf32>, %arg1: memref<3x2xf32>, %arg2: memref<2x2xf32>) {
    %c0 = arith.constant 0 : index
    %c0_0 = arith.constant 0 : index
    affine.for %arg3 = 0 to 2 {
      %0 = affine.load %arg0[%arg3, %c0_0] : memref<2x3xf32>
      %1 = affine.load %arg1[%c0_0, %c0] : memref<3x2xf32>
      %2 = affine.load %arg2[%arg3, %c0] : memref<2x2xf32>
      %3 = arith.mulf %0, %1 : f32
      %4 = arith.addf %2, %3 : f32
      affine.store %4, %arg2[%arg3, %c0] : memref<2x2xf32>
      %5 = affine.apply #map(%c0_0)
      %6 = affine.load %arg0[%arg3, %5] : memref<2x3xf32>
      %7 = affine.load %arg1[%5, %c0] : memref<3x2xf32>
      %8 = affine.load %arg2[%arg3, %c0] : memref<2x2xf32>
      %9 = arith.mulf %6, %7 : f32
      %10 = arith.addf %8, %9 : f32
      affine.store %10, %arg2[%arg3, %c0] : memref<2x2xf32>
      %11 = affine.apply #map1(%c0_0)
      %12 = affine.load %arg0[%arg3, %11] : memref<2x3xf32>
      %13 = affine.load %arg1[%11, %c0] : memref<3x2xf32>
      %14 = affine.load %arg2[%arg3, %c0] : memref<2x2xf32>
      %15 = arith.mulf %12, %13 : f32
      %16 = arith.addf %14, %15 : f32
      affine.store %16, %arg2[%arg3, %c0] : memref<2x2xf32>
      %17 = affine.apply #map(%c0)
      %18 = affine.load %arg0[%arg3, %c0_0] : memref<2x3xf32>
      %19 = affine.load %arg1[%c0_0, %17] : memref<3x2xf32>
      %20 = affine.load %arg2[%arg3, %17] : memref<2x2xf32>
      %21 = arith.mulf %18, %19 : f32
      %22 = arith.addf %20, %21 : f32
      affine.store %22, %arg2[%arg3, %17] : memref<2x2xf32>
      %23 = affine.apply #map(%c0_0)
      %24 = affine.load %arg0[%arg3, %23] : memref<2x3xf32>
      %25 = affine.load %arg1[%23, %17] : memref<3x2xf32>
      %26 = affine.load %arg2[%arg3, %17] : memref<2x2xf32>
      %27 = arith.mulf %24, %25 : f32
      %28 = arith.addf %26, %27 : f32
      affine.store %28, %arg2[%arg3, %17] : memref<2x2xf32>
      %29 = affine.apply #map1(%c0_0)
      %30 = affine.load %arg0[%arg3, %29] : memref<2x3xf32>
      %31 = affine.load %arg1[%29, %17] : memref<3x2xf32>
      %32 = affine.load %arg2[%arg3, %17] : memref<2x2xf32>
      %33 = arith.mulf %30, %31 : f32
      %34 = arith.addf %32, %33 : f32
      affine.store %34, %arg2[%arg3, %17] : memref<2x2xf32>
    }
    return
  }
}

