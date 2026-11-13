#map = affine_map<(d0) -> (d0 + 1)>
#map1 = affine_map<(d0) -> (d0 + 2)>
#map2 = affine_map<(d0) -> (d0 + 3)>
module {
  func.func @matmul(%arg0: memref<18x18xf32>, %arg1: memref<18x18xf32>, %arg2: memref<18x18xf32>) {
    affine.for %arg3 = 0 to 18 {
      affine.for %arg4 = 0 to 18 {
        affine.for %arg5 = 0 to 16 step 4 {
          %0 = affine.load %arg0[%arg3, %arg5] : memref<18x18xf32>
          %1 = affine.load %arg1[%arg5, %arg4] : memref<18x18xf32>
          %2 = affine.load %arg2[%arg3, %arg4] : memref<18x18xf32>
          %3 = arith.mulf %0, %1 : f32
          %4 = arith.addf %2, %3 : f32
          affine.store %4, %arg2[%arg3, %arg4] : memref<18x18xf32>
          %5 = affine.apply #map(%arg5)
          %6 = affine.load %arg0[%arg3, %5] : memref<18x18xf32>
          %7 = affine.load %arg1[%5, %arg4] : memref<18x18xf32>
          %8 = affine.load %arg2[%arg3, %arg4] : memref<18x18xf32>
          %9 = arith.mulf %6, %7 : f32
          %10 = arith.addf %8, %9 : f32
          affine.store %10, %arg2[%arg3, %arg4] : memref<18x18xf32>
          %11 = affine.apply #map1(%arg5)
          %12 = affine.load %arg0[%arg3, %11] : memref<18x18xf32>
          %13 = affine.load %arg1[%11, %arg4] : memref<18x18xf32>
          %14 = affine.load %arg2[%arg3, %arg4] : memref<18x18xf32>
          %15 = arith.mulf %12, %13 : f32
          %16 = arith.addf %14, %15 : f32
          affine.store %16, %arg2[%arg3, %arg4] : memref<18x18xf32>
          %17 = affine.apply #map2(%arg5)
          %18 = affine.load %arg0[%arg3, %17] : memref<18x18xf32>
          %19 = affine.load %arg1[%17, %arg4] : memref<18x18xf32>
          %20 = affine.load %arg2[%arg3, %arg4] : memref<18x18xf32>
          %21 = arith.mulf %18, %19 : f32
          %22 = arith.addf %20, %21 : f32
          affine.store %22, %arg2[%arg3, %arg4] : memref<18x18xf32>
        }
        affine.for %arg5 = 16 to 18 {
          %0 = affine.load %arg0[%arg3, %arg5] : memref<18x18xf32>
          %1 = affine.load %arg1[%arg5, %arg4] : memref<18x18xf32>
          %2 = affine.load %arg2[%arg3, %arg4] : memref<18x18xf32>
          %3 = arith.mulf %0, %1 : f32
          %4 = arith.addf %2, %3 : f32
          affine.store %4, %arg2[%arg3, %arg4] : memref<18x18xf32>
        }
      }
    }
    return
  }
}

