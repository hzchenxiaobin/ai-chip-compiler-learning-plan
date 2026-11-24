// 由 unrollgen.py 生成：M=5 N=7 K=3 U=2 variant=before
// 有效计算 M*N*K = 105 步；K= floor部分 2 步走主循环、余 1 步走尾部
module {
  func.func @matmul(%argA: memref<5x3xf32>, %argB: memref<3x7xf32>, %argC: memref<5x7xf32>) {
    %c0 = arith.constant 0 : index
    %c1 = arith.constant 1 : index
    %cM = arith.constant 5 : index
    %cN = arith.constant 7 : index
    %cK = arith.constant 3 : index
    %cf0 = arith.constant 0.0 : f32
    // 清零 C：精确边界 0..M × 0..N，与展开无关
    scf.for %zi = %c0 to %cM step %c1 {
      scf.for %zj = %c0 to %cN step %c1 {
        memref.store %cf0, %argC[%zi, %zj] : memref<5x7xf32>
      }
    }
    scf.for %i = %c0 to %cM step %c1 {
      scf.for %j = %c0 to %cN step %c1 {
        scf.for %k = %c0 to %cK step %c1 {
          %a = memref.load %argA[%i, %k] : memref<5x3xf32>
          %b = memref.load %argB[%k, %j] : memref<3x7xf32>
          %c = memref.load %argC[%i, %j] : memref<5x7xf32>
          %mul = arith.mulf %a, %b : f32
          %sum = arith.addf %c, %mul : f32
          memref.store %sum, %argC[%i, %j] : memref<5x7xf32>
        }
      }
    }
    return
  }
}
