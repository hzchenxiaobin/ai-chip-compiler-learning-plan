// k_hazard.mlir —— 第 61 天：未知 ≠ 任意 的运行期现场。
//
// 故意违反 K1 == K2：A(2,3) 配 B(2,2)。两个 K 在类型里都是 ? 时，
// 降出来的循环 K 上界只从 A 读（memref.dim %a, 1 → 3），
// 于是 k=2 那一步读 B[2, j] —— B 只有两行，越界。
// Verifier 不拦（静态可见的 3 vs 2 藏在 ? 后面），
// 运行期也没有检查 —— 结果就是混进垃圾值，或者直接段错误。
//
// 变体（同样实测过）：把 B 改成五行（前 3 行与合法 B 相同，第 4、5 行随便），
// 输出是 220/280/490/640、exit=0——答案看起来完全正确，
// 错误输入被无声无视，比垃圾值更难发现。
//
// 运行：见 run_all.sh（与 matmul_dynamic.mlir 同一条降级 + 执行命令）

module {
  func.func private @printF32(f32)
  func.func private @printNewline()

  func.func @matmul_all_dynamic(%a: memref<?x?xf32>, %b: memref<?x?xf32>,
                                %o: memref<?x?xf32>) {
    linalg.matmul ins(%a, %b : memref<?x?xf32>, memref<?x?xf32>)
                  outs(%o : memref<?x?xf32>)
    return
  }

  func.func @main() {
    %i0 = arith.constant 0 : index
    %i1 = arith.constant 1 : index
    %i2 = arith.constant 2 : index

    %a = memref.alloc() : memref<2x3xf32>     // K_A = 3
    %b = memref.alloc() : memref<2x2xf32>     // K_B = 2  ← 两边对不上
    %o = memref.alloc() : memref<2x2xf32>

    // A = [[1,2,3],[4,5,6]]
    %v1 = arith.constant 1.0 : f32
    %v2 = arith.constant 2.0 : f32
    %v3 = arith.constant 3.0 : f32
    %v4 = arith.constant 4.0 : f32
    %v5 = arith.constant 5.0 : f32
    %v6 = arith.constant 6.0 : f32
    memref.store %v1, %a[%i0, %i0] : memref<2x3xf32>
    memref.store %v2, %a[%i0, %i1] : memref<2x3xf32>
    memref.store %v3, %a[%i0, %i2] : memref<2x3xf32>
    memref.store %v4, %a[%i1, %i0] : memref<2x3xf32>
    memref.store %v5, %a[%i1, %i1] : memref<2x3xf32>
    memref.store %v6, %a[%i1, %i2] : memref<2x3xf32>

    // B = [[10,20],[30,40]] —— 只有 2 行，第 3 行不存在
    %u1 = arith.constant 10.0 : f32
    %u2 = arith.constant 20.0 : f32
    %u3 = arith.constant 30.0 : f32
    %u4 = arith.constant 40.0 : f32
    memref.store %u1, %b[%i0, %i0] : memref<2x2xf32>
    memref.store %u2, %b[%i0, %i1] : memref<2x2xf32>
    memref.store %u3, %b[%i1, %i0] : memref<2x2xf32>
    memref.store %u4, %b[%i1, %i1] : memref<2x2xf32>

    // O 清零
    %z = arith.constant 0.0 : f32
    memref.store %z, %o[%i0, %i0] : memref<2x2xf32>
    memref.store %z, %o[%i0, %i1] : memref<2x2xf32>
    memref.store %z, %o[%i1, %i0] : memref<2x2xf32>
    memref.store %z, %o[%i1, %i1] : memref<2x2xf32>

    // 全动态接口：类型里 K 藏在 ? 后面，Verifier 无从比较
    %ad = memref.cast %a : memref<2x3xf32> to memref<?x?xf32>
    %bd = memref.cast %b : memref<2x2xf32> to memref<?x?xf32>
    %od = memref.cast %o : memref<2x2xf32> to memref<?x?xf32>
    call @matmul_all_dynamic(%ad, %bd, %od)
      : (memref<?x?xf32>, memref<?x?xf32>, memref<?x?xf32>) -> ()

    // 若一切合法，这里本该打印 220 / 280 / 490 / 640；
    // 实际打印的是 3*B[2,j] 混着越界内存的垃圾值（见 outputs/k_hazard_exec.txt）
    %r00 = memref.load %o[%i0, %i0] : memref<2x2xf32>
    %r01 = memref.load %o[%i0, %i1] : memref<2x2xf32>
    %r10 = memref.load %o[%i1, %i0] : memref<2x2xf32>
    %r11 = memref.load %o[%i1, %i1] : memref<2x2xf32>
    call @printF32(%r00) : (f32) -> ()
    call @printNewline() : () -> ()
    call @printF32(%r01) : (f32) -> ()
    call @printNewline() : () -> ()
    call @printF32(%r10) : (f32) -> ()
    call @printNewline() : () -> ()
    call @printF32(%r11) : (f32) -> ()
    call @printNewline() : () -> ()

    memref.dealloc %a : memref<2x3xf32>
    memref.dealloc %b : memref<2x2xf32>
    memref.dealloc %o : memref<2x2xf32>
    return
  }
}
