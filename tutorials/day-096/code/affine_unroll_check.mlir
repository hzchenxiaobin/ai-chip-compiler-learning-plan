// affine_unroll_check.mlir —— 第 96 天的上游对照：
// 同一个 18x18x18 三重循环 matmul，交给上游 mlir-opt 的
//     --affine-loop-unroll="unroll-factor=4"
// 展开后会发生什么？（对照命令见 run_all.sh；18 % 4 = 2，有尾部）
//
// 上游会把它拆成“主循环 + 尾部循环”，和我们在 unrollgen.py / C++ 里
// 手写的结构一模一样——这是所有展开实现的公共底座：
//   scf.for/affine.for k = 0 to 16 step 4 { …4 份循环体… }
//   scf.for/affine.for k = 16 to 18 { …1 份循环体… }

module {
  func.func @matmul(%A: memref<18x18xf32>, %B: memref<18x18xf32>, %C: memref<18x18xf32>) {
    affine.for %i = 0 to 18 {
      affine.for %j = 0 to 18 {
        affine.for %k = 0 to 18 {
          %a = affine.load %A[%i, %k] : memref<18x18xf32>
          %b = affine.load %B[%k, %j] : memref<18x18xf32>
          %c = affine.load %C[%i, %j] : memref<18x18xf32>
          %m = arith.mulf %a, %b : f32
          %s = arith.addf %c, %m : f32
          affine.store %s, %C[%i, %j] : memref<18x18xf32>
        }
      }
    }
    return
  }
}
