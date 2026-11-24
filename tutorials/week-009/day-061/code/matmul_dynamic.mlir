// matmul_dynamic.mlir —— 第 61 天：动态 Shape 的 MatMul，三种待遇 + 真实执行。
//
// 数据（与 dynamic_lab.py 同一份）：
//   A(2,3) = [[1, 2, 3], [4, 5, 6]]
//   B(3,2) = [[10, 20], [30, 40], [50, 60]]
//   C(2,2) = A×B = [[220, 280], [490, 640]]
//
// 房间 1：M 动态、K/N 静态 —— Verifier 放行，循环上界运行期读取
// 房间 2：M/K/N 全动态 —— 两个 ? 各自为政，K 上界只从 A 读（缺口）
// 房间 3：main 里 memref.cast 把静态 A、O 借给动态接口，真实算出 220/280/490/640
//
// 运行方式：
//   mlir-opt matmul_dynamic.mlir                                # 解析 + 验证 + 打印
//   mlir-opt --convert-linalg-to-loops matmul_dynamic.mlir      # 看运行期 memref.dim
//   见 run_all.sh 里的完整降级 + mlir-cpu-runner 真实执行命令

module {
  func.func private @printF32(f32)
  func.func private @printNewline()

  // ---- 房间 1：M 动态、K=3 / N=2 静态 ----
  func.func @matmul_m_dynamic(%a: memref<?x3xf32>, %b: memref<3x2xf32>,
                              %o: memref<?x2xf32>) {
    linalg.matmul ins(%a, %b : memref<?x3xf32>, memref<3x2xf32>)
                  outs(%o : memref<?x2xf32>)
    return
  }

  // ---- 房间 2：M/K/N 全动态 ----
  func.func @matmul_all_dynamic(%a: memref<?x?xf32>, %b: memref<?x?xf32>,
                                %o: memref<?x?xf32>) {
    linalg.matmul ins(%a, %b : memref<?x?xf32>, memref<?x?xf32>)
                  outs(%o : memref<?x?xf32>)
    return
  }

  // ---- 房间 3：静态产物 → 动态接口的桥（memref.cast）----
  func.func @main() {
    %i0 = arith.constant 0 : index
    %i1 = arith.constant 1 : index
    %i2 = arith.constant 2 : index

    %a = memref.alloc() : memref<2x3xf32>
    %b = memref.alloc() : memref<3x2xf32>
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

    // B = [[10,20],[30,40],[50,60]]
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

    // 静态 memref 借给动态接口：cast 只改类型描述，不搬数据
    %ad = memref.cast %a : memref<2x3xf32> to memref<?x3xf32>
    %od = memref.cast %o : memref<2x2xf32> to memref<?x2xf32>
    call @matmul_m_dynamic(%ad, %b, %od)
      : (memref<?x3xf32>, memref<3x2xf32>, memref<?x2xf32>) -> ()

    // 打印 C 的四个角：期望 220 / 280 / 490 / 640
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
    memref.dealloc %b : memref<3x2xf32>
    memref.dealloc %o : memref<2x2xf32>
    return
  }
}
