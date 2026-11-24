// 第 117 天主输入：4×6·6×3 GEMM，"朴素前端"风格
// 与 D115/D116 同一算子；strided 签名保留（ABI 契约，D115 的成果），
// 但 alloc/return 用自动布局（identity）——显式 strided 布局的 alloc
// 会被 finalize-memref-to-llvm 的 identity 检查拒绝（见 README 常见错误 1）。
// 故意保留三处"朴素冗余"：下界写成 6-6、上界写成 2×2 和 3+(6-6)、
// 重复常量 %c1a/%c1b——用于"优化前后 MLIR"对照（canonicalize + CSE 折叠）。
// llvm.emit_c_interface 让 mlir-translate 自动生成 _mlir_ciface_gemm
// 包装（D116 手写包装的真工具版，D118 执行时按 C 合同调用）。
module {
  func.func @gemm(%a: memref<4x6xf32, strided<[6, 1]>>,
                  %b: memref<6x3xf32, strided<[3, 1]>>) -> memref<4x3xf32>
      attributes { llvm.emit_c_interface } {
    %c = memref.alloc() : memref<4x3xf32>
    %zero = arith.constant 0.0 : f32
    %c1a = arith.constant 1 : index
    %c1b = arith.constant 1 : index
    %c6 = arith.constant 6 : index
    %lb = arith.subi %c6, %c6 : index
    %c2 = arith.constant 2 : index
    %ubM = arith.muli %c2, %c2 : index
    %c3 = arith.constant 3 : index
    %ubN = arith.addi %c3, %lb : index
    scf.for %i = %lb to %ubM step %c1a {
      scf.for %j = %lb to %ubN step %c1b {
        %acc = scf.for %k = %lb to %c6 step %c1a
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
