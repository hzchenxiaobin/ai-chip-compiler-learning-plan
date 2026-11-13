// 由 tilegen.py 生成：M=5 N=7 K=3, tile 2x4x2, variant=min_bounds
// tile 网格：3 x 2 x 2 = 12 个 tile；有效计算 M*N*K = 105 步
module {
  func.func @tiled_matmul(%argA: memref<5x3xf32>, %argB: memref<3x7xf32>, %argC: memref<5x7xf32>) {
    %c0 = arith.constant 0 : index
    %c1 = arith.constant 1 : index
    %cM = arith.constant 5 : index
    %cN = arith.constant 7 : index
    %cK = arith.constant 3 : index
    %cTM = arith.constant 2 : index
    %cTN = arith.constant 4 : index
    %cTK = arith.constant 2 : index
    %cf0 = arith.constant 0.0 : f32
    // 第 0 步：清零 C。这个循环用精确边界 0..M / 0..N，不需要保护，
    // 因为它不受 tile 网格约束——保护只加在会越界的地方。
    scf.for %zi = %c0 to %cM step %c1 {
      scf.for %zj = %c0 to %cN step %c1 {
        memref.store %cf0, %argC[%zi, %zj] : memref<5x7xf32>
      }
    }
    // 第 1 步：tile 循环（外层）。尾部 tile 的点循环上界被 min(tile起点+Tile, 维度) 钳制，自动变短：静态 3 条 min，动态执行 3+6+12=21 次
    scf.for %i0 = %c0 to %cM step %cTM {
      %i1 = arith.addi %i0, %cTM : index
      %ihi = arith.minsi %i1, %cM : index
      scf.for %j0 = %c0 to %cN step %cTN {
        %j1 = arith.addi %j0, %cTN : index
        %jhi = arith.minsi %j1, %cN : index
        scf.for %k0 = %c0 to %cK step %cTK {
          %k1 = arith.addi %k0, %cTK : index
          %khi = arith.minsi %k1, %cK : index
          scf.for %i = %i0 to %ihi step %c1 {
            scf.for %j = %j0 to %jhi step %c1 {
              scf.for %k = %k0 to %khi step %c1 {
                %a = memref.load %argA[%i, %k] : memref<5x3xf32>
                %b = memref.load %argB[%k, %j] : memref<3x7xf32>
                %c = memref.load %argC[%i, %j] : memref<5x7xf32>
                %mul = arith.mulf %a, %b : f32
                %sum = arith.addf %c, %mul : f32
                memref.store %sum, %argC[%i, %j] : memref<5x7xf32>
              }
            }
          }
        }
      }
    }
    return
  }
}
