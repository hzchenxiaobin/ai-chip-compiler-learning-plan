// bad_broadcast.mlir —— 第 60 天错误博物馆：linalg.generic 的 Verifier 应拒两间房。
//
// 运行（预期 exit=1，两条诊断）：
//   mlir-opt bad_broadcast.mlir
//
// 房间 1：完全失配 —— (2,3) + (4,)
//   b 的 indexing map (d0, d1) -> (d1) 推断该操作数第 0 维必须等于
//   迭代空间 d1 的尺寸 3，但实际是 4：
//     error: 'linalg.generic' op inferred input/output operand #1 has
//       shape's dimension #0 to be 3, but found 4
//
// 房间 2：维度 1 不是免死金牌 —— (3,1) + (2,3)
//   c 的 indexing map (d0, d1) -> (d0, d1) 推断两维都必须是 (2,3)，
//   但 c 是 (3,1)：第 0 维 3 ≠ 2 失配。有 1 也不能豁免别的维。

module {
  memref.global "private" constant @ga : memref<2x3xf32> = dense<
    [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]>
  memref.global "private" constant @gb : memref<4xf32> = dense<[10.0, 20.0, 30.0, 40.0]>
  memref.global "private" constant @gc : memref<3x1xf32> = dense<[[1.0], [2.0], [3.0]]>

  func.func private @printF32(f32)
  func.func private @printNewline()

  func.func @main() {
    %a = memref.get_global @ga : memref<2x3xf32>
    %b = memref.get_global @gb : memref<4xf32>
    %c = memref.get_global @gc : memref<3x1xf32>
    %o = memref.alloc() : memref<2x3xf32>

    // ---- 房间 1：(2,3) + (4,)：最右维 3 vs 4，既不相等也没有 1 ----
    linalg.generic {
      indexing_maps = [affine_map<(d0, d1) -> (d0, d1)>,
                       affine_map<(d0, d1) -> (d1)>,
                       affine_map<(d0, d1) -> (d0, d1)>],
      iterator_types = ["parallel", "parallel"]}
      ins(%a, %b : memref<2x3xf32>, memref<4xf32>)
      outs(%o : memref<2x3xf32>) {
    ^bb0(%x: f32, %y: f32, %z: f32):
      %s = arith.addf %x, %y : f32
      linalg.yield %s : f32
    }

    // ---- 房间 2：(3,1) + (2,3)：第 1 维的 1 救不了第 0 维的 3 vs 2 ----
    linalg.generic {
      indexing_maps = [affine_map<(d0, d1) -> (d0, d1)>,
                       affine_map<(d0, d1) -> (d0, d1)>,
                       affine_map<(d0, d1) -> (d0, d1)>],
      iterator_types = ["parallel", "parallel"]}
      ins(%a, %c : memref<2x3xf32>, memref<3x1xf32>)
      outs(%o : memref<2x3xf32>) {
    ^bb0(%x: f32, %y: f32, %z: f32):
      %s = arith.addf %x, %y : f32
      linalg.yield %s : f32
    }

    %i0 = arith.constant 0 : index
    %v = memref.load %o[%i0, %i0] : memref<2x3xf32>
    call @printF32(%v) : (f32) -> ()
    call @printNewline() : () -> ()
    return
  }
}
