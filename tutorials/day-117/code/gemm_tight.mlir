// 账本回归输入：D116 口径的 18-op GEMM（无朴素冗余）
// D116 结束时账本：14/18 已转，残账 C1×4（scf.for×3＋scf.yield×1）。
// 今天 --convert-scf-to-cf 把这 4 条全部转掉——18/18 清零。
// 与 gemm.mlir 的差别只有三点：下界/上界直接写常量、无重复常量、
// 无 emit_c_interface 属性（它的任务只是账本回归，不参与导出）。
module {
  func.func @gemm(%a: memref<4x6xf32, strided<[6, 1]>>,
                  %b: memref<6x3xf32, strided<[3, 1]>>) -> memref<4x3xf32> {
    %c = memref.alloc() : memref<4x3xf32>
    %zero = arith.constant 0.0 : f32
    %c0 = arith.constant 0 : index
    %c1 = arith.constant 1 : index
    %cM = arith.constant 4 : index
    %cN = arith.constant 3 : index
    %cK = arith.constant 6 : index
    scf.for %i = %c0 to %cM step %c1 {
      scf.for %j = %c0 to %cN step %c1 {
        %acc = scf.for %k = %c0 to %cK step %c1
                    iter_args(%acc = %zero) -> (f32) {
          %xa = memref.load %a[%i, %k] : memref<4x6xf32, strided<[6, 1]>>
          %xb = memref.load %b[%k, %j] : memref<6x3xf32, strided<[3, 1]>>
          %p = arith.mulf %xa, %xb : f32
          %s = arith.addf %acc, %p : f32
          scf.yield %s : f32
        }
        memref.store %acc, %c[%i, %j] : memref<4x3xf32>
      }
    }
    func.return %c : memref<4x3xf32>
  }
}
