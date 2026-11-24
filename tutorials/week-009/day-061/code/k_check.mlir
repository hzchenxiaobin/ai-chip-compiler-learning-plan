// k_check.mlir —— 第 61 天：给动态 MatMul 装上运行期 K 检查，然后真实执行。
//
// 数据：A(2,3) 先配合法的 B(3,2)（打印 220，正常退出），
//       再配事故数据 B(2,2)（K_A=3 ≠ K_B=2，assert 触发，非零退出）。
// 与 k_hazard.mlir 同一场事故的两种结局：有检查 vs 没检查。
//
// k_constraint.mlir 里的
//   shape.cstr_require %eq, "matmul: K dims must match"
// 被 --convert-shape-constraints 物化成
//   cf.assert %eq, "matmul: K dims must match"
// （本机实测，见 outputs/k_constraint_cstr.txt）。
// 本文件手写这份物化结果——shape dialect 在 LLVM 18.1.8 上
// 对 memref 的 shape_of 还降不到 LLVM（实测 failed to materialize），
// 但「cf.assert + memref.dim」就是它的目标形态，语义一字不差。
//
// 预期输出：220，然后 abort（退出码 134）。
// 说明：降级后的 IR 里消息是 puts(@assert_msg) + abort()，
// 但本机 JIT 下 puts 的输出没能赶上 abort（缓冲被丢弃），stdout 里看不到消息——
// 这是实测结果，检查本身确定触发了。
//
// 运行：见 run_all.sh

module {
  func.func private @printF32(f32)
  func.func private @printNewline()

  func.func @mm_checked(%a: memref<?x?xf32>, %b: memref<?x?xf32>,
                        %o: memref<?x?xf32>) {
    // 运行期读维：memref.dim 是动态维度唯一的取值通道
    %c1 = arith.constant 1 : index
    %c0 = arith.constant 0 : index
    %ka = memref.dim %a, %c1 : memref<?x?xf32>   // A 的第 1 维 = K_A
    %kb = memref.dim %b, %c0 : memref<?x?xf32>   // B 的第 0 维 = K_B
    %eq = arith.cmpi eq, %ka, %kb : index
    // 上一个实验（k_hazard）里没有这 4 行：错误无声地滑过去，吐出 1.44752e+28
    cf.assert %eq, "matmul: K dims must match"
    linalg.matmul ins(%a, %b : memref<?x?xf32>, memref<?x?xf32>)
                  outs(%o : memref<?x?xf32>)
    return
  }

  func.func @main() {
    %i0 = arith.constant 0 : index
    %i1 = arith.constant 1 : index
    %i2 = arith.constant 2 : index

    %a = memref.alloc() : memref<2x3xf32>     // K_A = 3
    %b = memref.alloc() : memref<3x2xf32>     // K_B = 3 ← 第一次：合法
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

    // B = [[10,20],[30,40],[50,60]] —— 3 行，与 A 的 K 匹配
    %u1 = arith.constant 10.0 : f32
    %u2 = arith.constant 20.0 : f32
    %u3 = arith.constant 30.0 : f32
    %u4 = arith.constant 40.0 : f32
    %u5 = arith.constant 50.0 : f32
    %u6 = arith.constant 60.0 : f32
    memref.store %u1, %b[%i0, %i0] : memref<3x2xf32>
    memref.store %u2, %b[%i0, %i1] : memref<3x2xf32>
    memref.store %u3, %b[%i1, %i0] : memref<3x2xf32>
    memref.store %u4, %b[%i1, %i1] : memref<3x2xf32>
    memref.store %u5, %b[%i2, %i0] : memref<3x2xf32>
    memref.store %u6, %b[%i2, %i1] : memref<3x2xf32>

    // O 清零
    %z = arith.constant 0.0 : f32
    memref.store %z, %o[%i0, %i0] : memref<2x2xf32>
    memref.store %z, %o[%i0, %i1] : memref<2x2xf32>
    memref.store %z, %o[%i1, %i0] : memref<2x2xf32>
    memref.store %z, %o[%i1, %i1] : memref<2x2xf32>

    %ad = memref.cast %a : memref<2x3xf32> to memref<?x?xf32>
    %bd = memref.cast %b : memref<3x2xf32> to memref<?x?xf32>
    %od = memref.cast %o : memref<2x2xf32> to memref<?x?xf32>

    // ---- 第一次调用：K_A = 3 = K_B，检查放行，打印 220 ----
    call @mm_checked(%ad, %bd, %od)
      : (memref<?x?xf32>, memref<?x?xf32>, memref<?x?xf32>) -> ()
    %r00 = memref.load %o[%i0, %i0] : memref<2x2xf32>
    call @printF32(%r00) : (f32) -> ()
    call @printNewline() : () -> ()

    // ---- 第二次调用：把 B 改名成 2 行的事故数据（K_B = 2 ≠ 3）----
    // memref.cast 只认类型不认内容；直接换一个 2x2 的 B
    %bbad = memref.alloc() : memref<2x2xf32>
    memref.store %u1, %bbad[%i0, %i0] : memref<2x2xf32>
    memref.store %u2, %bbad[%i0, %i1] : memref<2x2xf32>
    memref.store %u3, %bbad[%i1, %i0] : memref<2x2xf32>
    memref.store %u4, %bbad[%i1, %i1] : memref<2x2xf32>
    memref.store %z, %o[%i0, %i0] : memref<2x2xf32>
    memref.store %z, %o[%i0, %i1] : memref<2x2xf32>
    memref.store %z, %o[%i1, %i0] : memref<2x2xf32>
    memref.store %z, %o[%i1, %i1] : memref<2x2xf32>
    %bbadd = memref.cast %bbad : memref<2x2xf32> to memref<?x?xf32>
    // 这一行之后程序应该死在 assert 上，不会走到后面的打印
    call @mm_checked(%ad, %bbadd, %od)
      : (memref<?x?xf32>, memref<?x?xf32>, memref<?x?xf32>) -> ()
    %r01 = memref.load %o[%i0, %i1] : memref<2x2xf32>
    call @printF32(%r01) : (f32) -> ()
    call @printNewline() : () -> ()

    memref.dealloc %a : memref<2x3xf32>
    memref.dealloc %b : memref<3x2xf32>
    memref.dealloc %o : memref<2x2xf32>
    memref.dealloc %bbad : memref<2x2xf32>
    return
  }
}
