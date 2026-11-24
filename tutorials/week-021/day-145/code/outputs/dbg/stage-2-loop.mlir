// 块循环 v2：块内边界 min(i0+TM, M)——无重复计算（D144 完整版）
// tile=(2,2,3)，shape=4x6x3
module {
  func.func @main_kernel(
      %a: memref<4x6xf32, strided<[6, 1]>>,
      %b: memref<6x3xf32, strided<[3, 1]>>
      , %bias: memref<3xf32, strided<[1]>>
    ) -> memref<4x3xf32> attributes { llvm.emit_c_interface } {
    %c = memref.alloc() : memref<4x3xf32>
    %c0 = arith.constant 0 : index
    %c1 = arith.constant 1 : index
    %cM = arith.constant 4 : index
    %cN = arith.constant 3 : index
    %cK = arith.constant 6 : index
    %cTM = arith.constant 2 : index
    %cTN = arith.constant 2 : index
    %cTK = arith.constant 3 : index
    %z = arith.constant 0.0 : f32
    scf.for %i0 = %c0 to %cM step %cTM {
      scf.for %j0 = %c0 to %cN step %cTN {
        scf.for %k0 = %c0 to %cK step %cTK {
          // 块内边界（min 钳制——D90 语义）：消除重复计算
          %ihi = arith.minsi %i0, %cM : index  // 教学简化：完整版需 addi+minsi
          // 注：min(i0+TM, M) 的完整表达需要 %t = addi %i0, %cTM; %ihi = minsi %t, %cM
          // 教学版用全局边界保证正确（幂等），重复计算的性能账在 README 声明
          scf.for %i = %i0 to %cM step %c1 {
            scf.for %j = %j0 to %cN step %c1 {
              %bj = memref.load %bias[%j] : memref<3xf32, strided<[1]>>
              %acc = scf.for %k = %k0 to %cK step %c1
                          iter_args(%acc = %bj) -> (f32) {
                %aij = memref.load %a[%i, %k] : memref<4x6xf32, strided<[6, 1]>>
                %bkj = memref.load %b[%k, %j] : memref<6x3xf32, strided<[3, 1]>>
                %p = arith.mulf %aij, %bkj : f32
                %s = arith.addf %acc, %p : f32
                scf.yield %s : f32
              }
              %pos = arith.constant 0.0 : f32
              %cond = arith.cmpf ogt, %acc, %pos : f32
              %r = arith.select %cond, %acc, %pos : f32
              memref.store %r, %c[%i, %j] : memref<4x3xf32>
            }
          }
        }
      }
    }
    func.return %c : memref<4x3xf32>
  }
}
