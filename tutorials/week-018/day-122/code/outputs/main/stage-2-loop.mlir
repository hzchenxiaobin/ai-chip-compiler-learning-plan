// minic S2 生成：图 IR → 循环 IR（scf.for 三重循环）
module {
  func.func @main_kernel(%a: memref<4x6xf32, strided<[6, 1]>>, %b: memref<6x3xf32, strided<[3, 1]>>, %bias: memref<3xf32, strided<[1]>>) -> memref<4x3xf32> attributes { llvm.emit_c_interface } {
    %c = memref.alloc() : memref<4x3xf32>
    %zero = arith.constant 0.0 : f32
    %c0 = arith.constant 0 : index
    %cM = arith.constant 4 : index
    %cN = arith.constant 3 : index
    %cK = arith.constant 6 : index
    %cTM = arith.constant 2 : index
    %cTN = arith.constant 3 : index
    %cTK = arith.constant 6 : index
    %c1 = arith.constant 1 : index
    scf.for %i0 = %c0 to %cM step %cTM {
      scf.for %j0 = %c0 to %cN step %cTN {
        scf.for %k0 = %c0 to %cK step %cTK {
          // 点循环：i∈[i0,min(i0+TM,M)), j∈[j0,min(j0+TN,N)), k∈[k0,min(k0+TK,K))
          // （教学版展开为注释；数值正确性由 S6 验证把关）
          // bias 融在 k=0 圈：%bias[k=0 时 j]
        }
      }
    }
    func.return %c : memref<4x3xf32>
  }
}
