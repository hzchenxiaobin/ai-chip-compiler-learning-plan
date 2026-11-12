#map = affine_map<(d0) -> (d0 + 1)>
#map1 = affine_map<(d0) -> (d0 + 2)>
module {
  func.func @matmul(%arg0: memref<2x3xf32>, %arg1: memref<3x2xf32>, %arg2: memref<2x2xf32>) {
    %c0 = arith.constant 0 : index
    %c0_0 = arith.constant 0 : index
    %c0_1 = arith.constant 0 : index
    %0 = affine.load %arg0[%c0, %c0_1] : memref<2x3xf32>
    %1 = affine.load %arg1[%c0_1, %c0_0] : memref<3x2xf32>
    %2 = affine.load %arg2[%c0, %c0_0] : memref<2x2xf32>
    %3 = arith.mulf %0, %1 : f32
    %4 = arith.addf %2, %3 : f32
    affine.store %4, %arg2[%c0, %c0_0] : memref<2x2xf32>
    %5 = affine.apply #map(%c0_1)
    %6 = affine.load %arg0[%c0, %5] : memref<2x3xf32>
    %7 = affine.load %arg1[%5, %c0_0] : memref<3x2xf32>
    %8 = affine.load %arg2[%c0, %c0_0] : memref<2x2xf32>
    %9 = arith.mulf %6, %7 : f32
    %10 = arith.addf %8, %9 : f32
    affine.store %10, %arg2[%c0, %c0_0] : memref<2x2xf32>
    %11 = affine.apply #map1(%c0_1)
    %12 = affine.load %arg0[%c0, %11] : memref<2x3xf32>
    %13 = affine.load %arg1[%11, %c0_0] : memref<3x2xf32>
    %14 = affine.load %arg2[%c0, %c0_0] : memref<2x2xf32>
    %15 = arith.mulf %12, %13 : f32
    %16 = arith.addf %14, %15 : f32
    affine.store %16, %arg2[%c0, %c0_0] : memref<2x2xf32>
    %17 = affine.apply #map(%c0_0)
    %18 = affine.load %arg0[%c0, %c0_1] : memref<2x3xf32>
    %19 = affine.load %arg1[%c0_1, %17] : memref<3x2xf32>
    %20 = affine.load %arg2[%c0, %17] : memref<2x2xf32>
    %21 = arith.mulf %18, %19 : f32
    %22 = arith.addf %20, %21 : f32
    affine.store %22, %arg2[%c0, %17] : memref<2x2xf32>
    %23 = affine.apply #map(%c0_1)
    %24 = affine.load %arg0[%c0, %23] : memref<2x3xf32>
    %25 = affine.load %arg1[%23, %17] : memref<3x2xf32>
    %26 = affine.load %arg2[%c0, %17] : memref<2x2xf32>
    %27 = arith.mulf %24, %25 : f32
    %28 = arith.addf %26, %27 : f32
    affine.store %28, %arg2[%c0, %17] : memref<2x2xf32>
    %29 = affine.apply #map1(%c0_1)
    %30 = affine.load %arg0[%c0, %29] : memref<2x3xf32>
    %31 = affine.load %arg1[%29, %17] : memref<3x2xf32>
    %32 = affine.load %arg2[%c0, %17] : memref<2x2xf32>
    %33 = arith.mulf %30, %31 : f32
    %34 = arith.addf %32, %33 : f32
    affine.store %34, %arg2[%c0, %17] : memref<2x2xf32>
    %35 = affine.apply #map(%c0)
    %36 = affine.load %arg0[%35, %c0_1] : memref<2x3xf32>
    %37 = affine.load %arg1[%c0_1, %c0_0] : memref<3x2xf32>
    %38 = affine.load %arg2[%35, %c0_0] : memref<2x2xf32>
    %39 = arith.mulf %36, %37 : f32
    %40 = arith.addf %38, %39 : f32
    affine.store %40, %arg2[%35, %c0_0] : memref<2x2xf32>
    %41 = affine.apply #map(%c0_1)
    %42 = affine.load %arg0[%35, %41] : memref<2x3xf32>
    %43 = affine.load %arg1[%41, %c0_0] : memref<3x2xf32>
    %44 = affine.load %arg2[%35, %c0_0] : memref<2x2xf32>
    %45 = arith.mulf %42, %43 : f32
    %46 = arith.addf %44, %45 : f32
    affine.store %46, %arg2[%35, %c0_0] : memref<2x2xf32>
    %47 = affine.apply #map1(%c0_1)
    %48 = affine.load %arg0[%35, %47] : memref<2x3xf32>
    %49 = affine.load %arg1[%47, %c0_0] : memref<3x2xf32>
    %50 = affine.load %arg2[%35, %c0_0] : memref<2x2xf32>
    %51 = arith.mulf %48, %49 : f32
    %52 = arith.addf %50, %51 : f32
    affine.store %52, %arg2[%35, %c0_0] : memref<2x2xf32>
    %53 = affine.apply #map(%c0_0)
    %54 = affine.load %arg0[%35, %c0_1] : memref<2x3xf32>
    %55 = affine.load %arg1[%c0_1, %53] : memref<3x2xf32>
    %56 = affine.load %arg2[%35, %53] : memref<2x2xf32>
    %57 = arith.mulf %54, %55 : f32
    %58 = arith.addf %56, %57 : f32
    affine.store %58, %arg2[%35, %53] : memref<2x2xf32>
    %59 = affine.apply #map(%c0_1)
    %60 = affine.load %arg0[%35, %59] : memref<2x3xf32>
    %61 = affine.load %arg1[%59, %53] : memref<3x2xf32>
    %62 = affine.load %arg2[%35, %53] : memref<2x2xf32>
    %63 = arith.mulf %60, %61 : f32
    %64 = arith.addf %62, %63 : f32
    affine.store %64, %arg2[%35, %53] : memref<2x2xf32>
    %65 = affine.apply #map1(%c0_1)
    %66 = affine.load %arg0[%35, %65] : memref<2x3xf32>
    %67 = affine.load %arg1[%65, %53] : memref<3x2xf32>
    %68 = affine.load %arg2[%35, %53] : memref<2x2xf32>
    %69 = arith.mulf %66, %67 : f32
    %70 = arith.addf %68, %69 : f32
    affine.store %70, %arg2[%35, %53] : memref<2x2xf32>
    return
  }
}

