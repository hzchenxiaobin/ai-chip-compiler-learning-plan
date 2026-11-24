// 由 unrollgen.py 生成：M=8 N=8 K=8 U=4 variant=unroll_k
// 有效计算 M*N*K = 512 步；K= floor部分 8 步走主循环、余 0 步走尾部
module {
  func.func @matmul(%argA: memref<8x8xf32>, %argB: memref<8x8xf32>, %argC: memref<8x8xf32>) {
    %c0 = arith.constant 0 : index
    %c1 = arith.constant 1 : index
    %cM = arith.constant 8 : index
    %cN = arith.constant 8 : index
    %cK = arith.constant 8 : index
    %cU = arith.constant 4 : index
    %cMain = arith.constant 8 : index
    %d1 = arith.constant 1 : index
    %d2 = arith.constant 2 : index
    %d3 = arith.constant 3 : index
    %cf0 = arith.constant 0.0 : f32
    // 清零 C：精确边界 0..M × 0..N，与展开无关
    scf.for %zi = %c0 to %cM step %c1 {
      scf.for %zj = %c0 to %cN step %c1 {
        memref.store %cf0, %argC[%zi, %zj] : memref<8x8xf32>
      }
    }
    scf.for %i = %c0 to %cM step %c1 {
      scf.for %j = %c0 to %cN step %c1 {
        // 主循环：0 到 floor(K/U)*U=8，步长 U，体内 4 份 MAC（k, k+1, …, k+3）
        scf.for %k = %c0 to %cMain step %cU {
          %a0 = memref.load %argA[%i, %k] : memref<8x8xf32>
          %b0 = memref.load %argB[%k, %j] : memref<8x8xf32>
          %acc0 = memref.load %argC[%i, %j] : memref<8x8xf32>
          %mul0 = arith.mulf %a0, %b0 : f32
          %sum0 = arith.addf %acc0, %mul0 : f32
          memref.store %sum0, %argC[%i, %j] : memref<8x8xf32>
          %ku1 = arith.addi %k, %d1 : index
          %a1 = memref.load %argA[%i, %ku1] : memref<8x8xf32>
          %b1 = memref.load %argB[%ku1, %j] : memref<8x8xf32>
          %acc1 = memref.load %argC[%i, %j] : memref<8x8xf32>
          %mul1 = arith.mulf %a1, %b1 : f32
          %sum1 = arith.addf %acc1, %mul1 : f32
          memref.store %sum1, %argC[%i, %j] : memref<8x8xf32>
          %ku2 = arith.addi %k, %d2 : index
          %a2 = memref.load %argA[%i, %ku2] : memref<8x8xf32>
          %b2 = memref.load %argB[%ku2, %j] : memref<8x8xf32>
          %acc2 = memref.load %argC[%i, %j] : memref<8x8xf32>
          %mul2 = arith.mulf %a2, %b2 : f32
          %sum2 = arith.addf %acc2, %mul2 : f32
          memref.store %sum2, %argC[%i, %j] : memref<8x8xf32>
          %ku3 = arith.addi %k, %d3 : index
          %a3 = memref.load %argA[%i, %ku3] : memref<8x8xf32>
          %b3 = memref.load %argB[%ku3, %j] : memref<8x8xf32>
          %acc3 = memref.load %argC[%i, %j] : memref<8x8xf32>
          %mul3 = arith.mulf %a3, %b3 : f32
          %sum3 = arith.addf %acc3, %mul3 : f32
          memref.store %sum3, %argC[%i, %j] : memref<8x8xf32>
        }
        // 尾部循环：8 到 K=8，步长 1，体内 1 份 MAC
        scf.for %kt = %cMain to %cK step %c1 {
          %at = memref.load %argA[%i, %kt] : memref<8x8xf32>
          %bt = memref.load %argB[%kt, %j] : memref<8x8xf32>
          %ct = memref.load %argC[%i, %j] : memref<8x8xf32>
          %mult = arith.mulf %at, %bt : f32
          %sumt = arith.addf %ct, %mult : f32
          memref.store %sumt, %argC[%i, %j] : memref<8x8xf32>
        }
      }
    }
    return
  }
}
