// 块循环形态（D142 的施工蓝图样例）：外层 tile 壳＋内层点循环
// 与朴素版（D124）的差别：三层 tile 循环壳 + 点循环用块内边界
module {
  func.func @kernel_tiled(%a: memref<4x6xf32, strided<[6, 1]>>,
                          %b: memref<6x3xf32, strided<[3, 1]>>)
      -> memref<4x3xf32> attributes { llvm.emit_c_interface } {
    %c = memref.alloc() : memref<4x3xf32>
    %c0 = arith.constant 0 : index
    %c1 = arith.constant 1 : index
    %cM = arith.constant 4 : index
    %cN = arith.constant 3 : index
    %cK = arith.constant 6 : index
    %cTM = arith.constant 2 : index    // tile M
    %cTN = arith.constant 2 : index    // tile N
    %cTK = arith.constant 3 : index    // tile K
    %z = arith.constant 0.0 : f32
    // 外层 tile 壳：i0/j0/k0 步长 = tile
    scf.for %i0 = %c0 to %cM step %cTM {
      scf.for %j0 = %c0 to %cN step %cTN {
        scf.for %k0 = %c0 to %cK step %cTK {
          // 内层点循环：块内边界 = min(i0+TM, M)（边界钳制——D90 语义）
          %ihi = arith.minsi %i0, %cM : index    // 教学简化：直接用常量边界
          // 完整版应为 %ihi = min(i0+TM, M)——D143 实现时补全
          scf.for %i = %i0 to %ihi step %c1 {
            scf.for %j = %j0 to %cN step %c1 {
              %acc = scf.for %k = %k0 to %cK step %c1
                          iter_args(%acc = %z) -> (f32) {
                %aij = memref.load %a[%i, %k] : memref<4x6xf32, strided<[6, 1]>>
                %bkj = memref.load %b[%k, %j] : memref<6x3xf32, strided<[3, 1]>>
                %p = arith.mulf %aij, %bkj : f32
                %s = arith.addf %acc, %p : f32
                scf.yield %s : f32
              }
              memref.store %acc, %c[%i, %j] : memref<4x3xf32>
            }
          }
        }
      }
    }
    func.return %c : memref<4x3xf32>
  }
}
