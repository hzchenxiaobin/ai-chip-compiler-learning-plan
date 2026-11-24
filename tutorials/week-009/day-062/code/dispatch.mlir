// dispatch.mlir —— 第 62 天：特化产物 + 通用回退的分发现场（cpu-runner 真实执行）。
//
// 结构（对应 products_lab.py 第 3 段的三种策略）：
//   @matmul_generic     通用版：全动态 + 运行期 K 检查（永远可用的回退路径）
//   @matmul_spec_2_3_2  特化产物 1：M=2, K=3, N=2（--specialize-shape "a=2x3" 的形态）
//   @matmul_spec_4_3_2  特化产物 2：M=4, K=3, N=2（--specialize-shape "a=4x3" 的形态）
//   @dispatch_v1        分发器 v1：缓存里只有 (2,3,2) 一份特化
//   @dispatch_v2        分发器 v2：miss 之后 JIT 加入 (4,3,2)，缓存两份特化
//
// 数据（与第 61 天同一份）：
//   A(2,3)  = [[1,2,3],[4,5,6]]
//   A2(4,3) = [[1,2,3],[4,5,6],[7,8,9],[10,11,12]]
//   B(3,2)  = [[10,20],[30,40],[50,60]]
//
// 三个场景（每个先打印 hit 标志 1/0 和 M，再打印结果——路径选择成为可观察输出）：
//   场景 1：A(2,3)×B   经 dispatch_v1 → 命中 → 220/280/490/640
//   场景 2：A2(4,3)×B  经 dispatch_v1 → 未命中 → 回退通用版 → C2 的 8 个值
//   场景 3：A2(4,3)×B  经 dispatch_v2 → 命中（缓存已长出第二份特化）→ C2 再来一遍
//
// 关键机制：命中分支里的 memref.cast 把动态视图收紧回静态类型——
// 这一步的安全性由前面的维度比较保证（cast 本身不做运行期检查，
// guard 没把住就把它删掉，这是第 61 天 k_hazard 的老路）。
//
// 运行（完整命令见 run_all.sh 第 8 步）：
//   mlir-opt $LOWER dispatch.mlir -o dispatch.lowered.mlir
//   mlir-cpu-runner dispatch.lowered.mlir -e main --entry-point-result=void \
//       --shared-libs=... | tee outputs/dispatch_exec.txt

module {
  func.func private @printF32(f32)
  func.func private @printNewline()

  // ---- 通用版：全动态，带运行期 K 检查（回退路径，永远可用）----
  func.func @matmul_generic(%a: memref<?x?xf32>, %b: memref<?x?xf32>,
                            %o: memref<?x?xf32>) {
    %c0 = arith.constant 0 : index
    %c1 = arith.constant 1 : index
    %ka = memref.dim %a, %c1 : memref<?x?xf32>
    %kb = memref.dim %b, %c0 : memref<?x?xf32>
    %eq = arith.cmpi eq, %ka, %kb : index
    cf.assert %eq, "generic: K dims must match"
    linalg.matmul ins(%a, %b : memref<?x?xf32>, memref<?x?xf32>)
                  outs(%o : memref<?x?xf32>)
    return
  }

  // ---- 特化产物 1：M=2, K=3, N=2 全静态 ----
  func.func @matmul_spec_2_3_2(%a: memref<2x3xf32>, %b: memref<3x2xf32>,
                               %o: memref<2x2xf32>) {
    linalg.matmul ins(%a, %b : memref<2x3xf32>, memref<3x2xf32>)
                  outs(%o : memref<2x2xf32>)
    return
  }

  // ---- 特化产物 2：M=4, K=3, N=2 全静态 ----
  func.func @matmul_spec_4_3_2(%a: memref<4x3xf32>, %b: memref<3x2xf32>,
                               %o: memref<4x2xf32>) {
    linalg.matmul ins(%a, %b : memref<4x3xf32>, memref<3x2xf32>)
                  outs(%o : memref<4x2xf32>)
    return
  }

  // ---- 分发器 v1：缓存只有 (2,3,2)；未命中一律回退通用版 ----
  func.func @dispatch_v1(%a: memref<?x?xf32>, %b: memref<?x?xf32>,
                         %o: memref<?x?xf32>) {
    %c0 = arith.constant 0 : index
    %c1 = arith.constant 1 : index
    %c2 = arith.constant 2 : index
    %c3 = arith.constant 3 : index
    %m = memref.dim %a, %c0 : memref<?x?xf32>
    %k = memref.dim %a, %c1 : memref<?x?xf32>
    %n = memref.dim %b, %c1 : memref<?x?xf32>
    %m2 = arith.cmpi eq, %m, %c2 : index
    %k3 = arith.cmpi eq, %k, %c3 : index
    %n2 = arith.cmpi eq, %n, %c2 : index
    %h1 = arith.andi %m2, %k3 : i1
    %hit = arith.andi %h1, %n2 : i1
    scf.if %hit {
      %ac = memref.cast %a : memref<?x?xf32> to memref<2x3xf32>
      %bc = memref.cast %b : memref<?x?xf32> to memref<3x2xf32>
      %oc = memref.cast %o : memref<?x?xf32> to memref<2x2xf32>
      func.call @matmul_spec_2_3_2(%ac, %bc, %oc)
        : (memref<2x3xf32>, memref<3x2xf32>, memref<2x2xf32>) -> ()
    } else {
      func.call @matmul_generic(%a, %b, %o)
        : (memref<?x?xf32>, memref<?x?xf32>, memref<?x?xf32>) -> ()
    }
    return
  }

  // ---- 分发器 v2：缓存长出第二份 (4,3,2)；其余仍回退通用版 ----
  func.func @dispatch_v2(%a: memref<?x?xf32>, %b: memref<?x?xf32>,
                         %o: memref<?x?xf32>) {
    %c0 = arith.constant 0 : index
    %c1 = arith.constant 1 : index
    %c2 = arith.constant 2 : index
    %c3 = arith.constant 3 : index
    %c4 = arith.constant 4 : index
    %m = memref.dim %a, %c0 : memref<?x?xf32>
    %k = memref.dim %a, %c1 : memref<?x?xf32>
    %n = memref.dim %b, %c1 : memref<?x?xf32>
    %k3 = arith.cmpi eq, %k, %c3 : index
    %n2 = arith.cmpi eq, %n, %c2 : index
    %m2 = arith.cmpi eq, %m, %c2 : index
    %m4 = arith.cmpi eq, %m, %c4 : index
    %h23 = arith.andi %m2, %k3 : i1
    %hit23 = arith.andi %h23, %n2 : i1
    %h43 = arith.andi %m4, %k3 : i1
    %hit43 = arith.andi %h43, %n2 : i1
    %any = arith.ori %hit23, %hit43 : i1
    scf.if %any {
      scf.if %hit23 {
        %ac = memref.cast %a : memref<?x?xf32> to memref<2x3xf32>
        %bc = memref.cast %b : memref<?x?xf32> to memref<3x2xf32>
        %oc = memref.cast %o : memref<?x?xf32> to memref<2x2xf32>
        func.call @matmul_spec_2_3_2(%ac, %bc, %oc)
          : (memref<2x3xf32>, memref<3x2xf32>, memref<2x2xf32>) -> ()
      } else {
        %ac = memref.cast %a : memref<?x?xf32> to memref<4x3xf32>
        %bc = memref.cast %b : memref<?x?xf32> to memref<3x2xf32>
        %oc = memref.cast %o : memref<?x?xf32> to memref<4x2xf32>
        func.call @matmul_spec_4_3_2(%ac, %bc, %oc)
          : (memref<4x3xf32>, memref<3x2xf32>, memref<4x2xf32>) -> ()
      }
    } else {
      func.call @matmul_generic(%a, %b, %o)
        : (memref<?x?xf32>, memref<?x?xf32>, memref<?x?xf32>) -> ()
    }
    return
  }

  // ---- 打印辅助 ----
  func.func @print2(%h: f32, %m: f32) {
    call @printF32(%h) : (f32) -> ()
    call @printNewline() : () -> ()
    call @printF32(%m) : (f32) -> ()
    call @printNewline() : () -> ()
    return
  }
  func.func @print4(%x0: f32, %x1: f32, %x2: f32, %x3: f32) {
    call @printF32(%x0) : (f32) -> ()
    call @printNewline() : () -> ()
    call @printF32(%x1) : (f32) -> ()
    call @printNewline() : () -> ()
    call @printF32(%x2) : (f32) -> ()
    call @printNewline() : () -> ()
    call @printF32(%x3) : (f32) -> ()
    call @printNewline() : () -> ()
    return
  }
  func.func @print8(%x0: f32, %x1: f32, %x2: f32, %x3: f32,
                    %x4: f32, %x5: f32, %x6: f32, %x7: f32) {
    call @print4(%x0, %x1, %x2, %x3) : (f32, f32, f32, f32) -> ()
    call @print4(%x4, %x5, %x6, %x7) : (f32, f32, f32, f32) -> ()
    return
  }

  // ---- main：三个场景 ----
  func.func @main() {
    %i0 = arith.constant 0 : index
    %i1 = arith.constant 1 : index
    %i2 = arith.constant 2 : index
    %i3 = arith.constant 3 : index
    %c0f = arith.constant 0.0 : f32
    %c1f = arith.constant 1.0 : f32

    // ==== 场景 1：A(2,3) × B(3,2) 经 dispatch_v1 → 命中 ====
    %a = memref.alloc() : memref<2x3xf32>
    %b = memref.alloc() : memref<3x2xf32>
    %o = memref.alloc() : memref<2x2xf32>
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
    memref.store %c0f, %o[%i0, %i0] : memref<2x2xf32>
    memref.store %c0f, %o[%i0, %i1] : memref<2x2xf32>
    memref.store %c0f, %o[%i1, %i0] : memref<2x2xf32>
    memref.store %c0f, %o[%i1, %i1] : memref<2x2xf32>

    // 静态数据借给动态视图（cast 只改类型描述，不搬数据——第 61 天的桥）
    %ad = memref.cast %a : memref<2x3xf32> to memref<?x?xf32>
    %bd = memref.cast %b : memref<3x2xf32> to memref<?x?xf32>
    %od = memref.cast %o : memref<2x2xf32> to memref<?x?xf32>
    call @dispatch_v1(%ad, %bd, %od)
      : (memref<?x?xf32>, memref<?x?xf32>, memref<?x?xf32>) -> ()

    %m1 = memref.dim %ad, %i0 : memref<?x?xf32>
    %m1i = arith.index_cast %m1 : index to i32
    %m1f = arith.sitofp %m1i : i32 to f32
    call @print2(%c1f, %m1f) : (f32, f32) -> ()
    %r00 = memref.load %o[%i0, %i0] : memref<2x2xf32>
    %r01 = memref.load %o[%i0, %i1] : memref<2x2xf32>
    %r10 = memref.load %o[%i1, %i0] : memref<2x2xf32>
    %r11 = memref.load %o[%i1, %i1] : memref<2x2xf32>
    call @print4(%r00, %r01, %r10, %r11) : (f32, f32, f32, f32) -> ()
    memref.dealloc %a : memref<2x3xf32>
    memref.dealloc %b : memref<3x2xf32>
    memref.dealloc %o : memref<2x2xf32>

    // ==== 场景 2：A2(4,3) × B(3,2) 经 dispatch_v1 → 未命中，回退通用版 ====
    %a2 = memref.alloc() : memref<4x3xf32>
    %b2 = memref.alloc() : memref<3x2xf32>
    %o2 = memref.alloc() : memref<4x2xf32>
    %w7 = arith.constant 7.0 : f32
    %w8 = arith.constant 8.0 : f32
    %w9 = arith.constant 9.0 : f32
    %w10 = arith.constant 10.0 : f32
    %w11 = arith.constant 11.0 : f32
    %w12 = arith.constant 12.0 : f32
    memref.store %v1, %a2[%i0, %i0] : memref<4x3xf32>
    memref.store %v2, %a2[%i0, %i1] : memref<4x3xf32>
    memref.store %v3, %a2[%i0, %i2] : memref<4x3xf32>
    memref.store %v4, %a2[%i1, %i0] : memref<4x3xf32>
    memref.store %v5, %a2[%i1, %i1] : memref<4x3xf32>
    memref.store %v6, %a2[%i1, %i2] : memref<4x3xf32>
    memref.store %w7, %a2[%i2, %i0] : memref<4x3xf32>
    memref.store %w8, %a2[%i2, %i1] : memref<4x3xf32>
    memref.store %w9, %a2[%i2, %i2] : memref<4x3xf32>
    memref.store %w10, %a2[%i3, %i0] : memref<4x3xf32>
    memref.store %w11, %a2[%i3, %i1] : memref<4x3xf32>
    memref.store %w12, %a2[%i3, %i2] : memref<4x3xf32>
    memref.store %u1, %b2[%i0, %i0] : memref<3x2xf32>
    memref.store %u2, %b2[%i0, %i1] : memref<3x2xf32>
    memref.store %u3, %b2[%i1, %i0] : memref<3x2xf32>
    memref.store %u4, %b2[%i1, %i1] : memref<3x2xf32>
    memref.store %u5, %b2[%i2, %i0] : memref<3x2xf32>
    memref.store %u6, %b2[%i2, %i1] : memref<3x2xf32>
    memref.store %c0f, %o2[%i0, %i0] : memref<4x2xf32>
    memref.store %c0f, %o2[%i0, %i1] : memref<4x2xf32>
    memref.store %c0f, %o2[%i1, %i0] : memref<4x2xf32>
    memref.store %c0f, %o2[%i1, %i1] : memref<4x2xf32>
    memref.store %c0f, %o2[%i2, %i0] : memref<4x2xf32>
    memref.store %c0f, %o2[%i2, %i1] : memref<4x2xf32>
    memref.store %c0f, %o2[%i3, %i0] : memref<4x2xf32>
    memref.store %c0f, %o2[%i3, %i1] : memref<4x2xf32>

    %ad2 = memref.cast %a2 : memref<4x3xf32> to memref<?x?xf32>
    %bd2 = memref.cast %b2 : memref<3x2xf32> to memref<?x?xf32>
    %od2 = memref.cast %o2 : memref<4x2xf32> to memref<?x?xf32>
    call @dispatch_v1(%ad2, %bd2, %od2)
      : (memref<?x?xf32>, memref<?x?xf32>, memref<?x?xf32>) -> ()

    %m2 = memref.dim %ad2, %i0 : memref<?x?xf32>
    %m2i = arith.index_cast %m2 : index to i32
    %m2f = arith.sitofp %m2i : i32 to f32
    call @print2(%c0f, %m2f) : (f32, f32) -> ()
    %s00 = memref.load %o2[%i0, %i0] : memref<4x2xf32>
    %s01 = memref.load %o2[%i0, %i1] : memref<4x2xf32>
    %s10 = memref.load %o2[%i1, %i0] : memref<4x2xf32>
    %s11 = memref.load %o2[%i1, %i1] : memref<4x2xf32>
    %s20 = memref.load %o2[%i2, %i0] : memref<4x2xf32>
    %s21 = memref.load %o2[%i2, %i1] : memref<4x2xf32>
    %s30 = memref.load %o2[%i3, %i0] : memref<4x2xf32>
    %s31 = memref.load %o2[%i3, %i1] : memref<4x2xf32>
    call @print8(%s00, %s01, %s10, %s11, %s20, %s21, %s30, %s31)
      : (f32, f32, f32, f32, f32, f32, f32, f32) -> ()

    // ==== 场景 3：同一份数据经 dispatch_v2 → 缓存已加入 (4,3,2)，这次命中 ====
    // 注意：linalg.matmul 的 outs 是累加语义，重放前必须清零
    // （初版在这里忘了清零，真实跑出过 440/560/980/... 恰好两倍的结果）
    memref.store %c0f, %o2[%i0, %i0] : memref<4x2xf32>
    memref.store %c0f, %o2[%i0, %i1] : memref<4x2xf32>
    memref.store %c0f, %o2[%i1, %i0] : memref<4x2xf32>
    memref.store %c0f, %o2[%i1, %i1] : memref<4x2xf32>
    memref.store %c0f, %o2[%i2, %i0] : memref<4x2xf32>
    memref.store %c0f, %o2[%i2, %i1] : memref<4x2xf32>
    memref.store %c0f, %o2[%i3, %i0] : memref<4x2xf32>
    memref.store %c0f, %o2[%i3, %i1] : memref<4x2xf32>
    call @dispatch_v2(%ad2, %bd2, %od2)
      : (memref<?x?xf32>, memref<?x?xf32>, memref<?x?xf32>) -> ()

    call @print2(%c1f, %m2f) : (f32, f32) -> ()
    %t00 = memref.load %o2[%i0, %i0] : memref<4x2xf32>
    %t01 = memref.load %o2[%i0, %i1] : memref<4x2xf32>
    %t10 = memref.load %o2[%i1, %i0] : memref<4x2xf32>
    %t11 = memref.load %o2[%i1, %i1] : memref<4x2xf32>
    %t20 = memref.load %o2[%i2, %i0] : memref<4x2xf32>
    %t21 = memref.load %o2[%i2, %i1] : memref<4x2xf32>
    %t30 = memref.load %o2[%i3, %i0] : memref<4x2xf32>
    %t31 = memref.load %o2[%i3, %i1] : memref<4x2xf32>
    call @print8(%t00, %t01, %t10, %t11, %t20, %t21, %t30, %t31)
      : (f32, f32, f32, f32, f32, f32, f32, f32) -> ()

    memref.dealloc %a2 : memref<4x3xf32>
    memref.dealloc %b2 : memref<3x2xf32>
    memref.dealloc %o2 : memref<4x2xf32>
    return
  }
}
