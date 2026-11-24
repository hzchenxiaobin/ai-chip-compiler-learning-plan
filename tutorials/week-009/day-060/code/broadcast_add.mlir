// broadcast_add.mlir —— 第 60 天：linalg.generic 里广播加法的两种姿态 + 真实执行。
//
// 与 broadcast_lab.py 用同一份数据：
//   a = [[1, 2, 3],       b = [10, 20, 30],   c = [[100],
//        [4, 5, 6]]                             [200]]
//
// 广播在 MLIR 里不是拷贝，而是 indexing map（仿射映射）：
//   a(2,3) + b(3,) ：b 的映射 (d0, d1) -> (d1)   —— d0 被丢掉 = 该维走 0 步
//   a(2,3) + c(2,1)：c 的映射 (d0, d1) -> (d0, 0)—— d1 恒为 0 = 该维走 0 步
//
// 四种「运行」方式：
//   1) 解析 + 验证 + 打印：
//        mlir-opt broadcast_add.mlir
//   2) 降成显式循环（看「少一个下标」的访存）：
//        mlir-opt --convert-linalg-to-loops broadcast_add.mlir
//   3) 真实执行（打印 4 个结果值）：
//        mlir-opt --convert-linalg-to-loops --convert-scf-to-cf \
//          --convert-cf-to-llvm --convert-func-to-llvm \
//          --finalize-memref-to-llvm --convert-arith-to-llvm \
//          --reconcile-unrealized-casts \
//          broadcast_add.mlir -o broadcast_add.lowered.mlir
//        mlir-cpu-runner broadcast_add.lowered.mlir -e main \
//          --entry-point-result=void \
//          --shared-libs=<llvm-lib>/libmlir_runner_utils.so,<llvm-lib>/libmlir_c_runner_utils.so
// 预期打印（手算，运行后核对）：
//   33   = o1[0,2] = 3 + 30   （b 沿行广播）
//   25   = o1[1,1] = 5 + 20
//   101  = o2[0,0] = 1 + 100  （c 沿列广播）
//   206  = o2[1,2] = 6 + 200

module {
  memref.global "private" constant @ga : memref<2x3xf32> = dense<
    [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]>
  memref.global "private" constant @gb : memref<3xf32> = dense<[10.0, 20.0, 30.0]>
  memref.global "private" constant @gc : memref<2x1xf32> = dense<[[100.0], [200.0]]>

  func.func private @printF32(f32)
  func.func private @printNewline()

  func.func @main() {
    %a = memref.get_global @ga : memref<2x3xf32>
    %b = memref.get_global @gb : memref<3xf32>
    %c = memref.get_global @gc : memref<2x1xf32>
    %o1 = memref.alloc() : memref<2x3xf32>
    %o2 = memref.alloc() : memref<2x3xf32>

    // ---- ① 行向量（bias 姿态）：b(3,) 的 indexing map 丢掉 d0 ----
    linalg.generic {
      indexing_maps = [affine_map<(d0, d1) -> (d0, d1)>,
                       affine_map<(d0, d1) -> (d1)>,
                       affine_map<(d0, d1) -> (d0, d1)>],
      iterator_types = ["parallel", "parallel"]}
      ins(%a, %b : memref<2x3xf32>, memref<3xf32>)
      outs(%o1 : memref<2x3xf32>) {
    ^bb0(%x: f32, %y: f32, %z: f32):
      %s = arith.addf %x, %y : f32
      linalg.yield %s : f32
    }

    // ---- ② 列向量姿态：c(2,1) 的 indexing map 把 d1 钉死在 0 ----
    linalg.generic {
      indexing_maps = [affine_map<(d0, d1) -> (d0, d1)>,
                       affine_map<(d0, d1) -> (d0, 0)>,
                       affine_map<(d0, d1) -> (d0, d1)>],
      iterator_types = ["parallel", "parallel"]}
      ins(%a, %c : memref<2x3xf32>, memref<2x1xf32>)
      outs(%o2 : memref<2x3xf32>) {
    ^bb0(%x: f32, %y: f32, %z: f32):
      %s = arith.addf %x, %y : f32
      linalg.yield %s : f32
    }

    // ---- 打印 4 个值：o1[0,2]、o1[1,1]、o2[0,0]、o2[1,2] ----
    %i0 = arith.constant 0 : index
    %i1 = arith.constant 1 : index
    %i2 = arith.constant 2 : index
    %v1 = memref.load %o1[%i0, %i2] : memref<2x3xf32>
    %v2 = memref.load %o1[%i1, %i1] : memref<2x3xf32>
    %v3 = memref.load %o2[%i0, %i0] : memref<2x3xf32>
    %v4 = memref.load %o2[%i1, %i2] : memref<2x3xf32>
    call @printF32(%v1) : (f32) -> ()
    call @printNewline() : () -> ()
    call @printF32(%v2) : (f32) -> ()
    call @printNewline() : () -> ()
    call @printF32(%v3) : (f32) -> ()
    call @printNewline() : () -> ()
    call @printF32(%v4) : (f32) -> ()
    call @printNewline() : () -> ()
    return
  }
}
