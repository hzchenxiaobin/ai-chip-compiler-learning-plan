// idem_canon.mlir —— 探针 1：--canonicalize 幂等吗（跑两遍 = 跑一遍）？
//
// 图里放一个恒等 tensor.cast（同类型同 shape，即 Day 67 的「无操作 Cast」）
// 和一个逐元素 generic，让 canonicalize 有真实工作可做。
//
// 本机 LLVM 18.1.8 实测（2026-11-12）：
//   mlir-opt idem_canon.mlir --canonicalize
//     → 恒等 tensor.cast 被删除（计数 0）
//   mlir-opt idem_canon.mlir --canonicalize --canonicalize
//     → 输出与跑一遍逐字节相同（canonicalize 内部迭代到自己的不动点）

module {
  func.func @idem_canon(%x: tensor<2x3xf32>) -> tensor<2x3xf32> {
    %cast = tensor.cast %x : tensor<2x3xf32> to tensor<2x3xf32>
    %init = tensor.empty() : tensor<2x3xf32>
    %r = linalg.generic {
      indexing_maps = [affine_map<(d0, d1) -> (d0, d1)>,
                       affine_map<(d0, d1) -> (d0, d1)>],
      iterator_types = ["parallel", "parallel"]
    } ins(%cast : tensor<2x3xf32>) outs(%init : tensor<2x3xf32>) {
    ^bb0(%in: f32, %out: f32):
      %zero = arith.constant 0.0 : f32
      %cmp = arith.cmpf ogt, %in, %zero : f32
      %sel = arith.select %cmp, %in, %zero : f32
      linalg.yield %sel : f32
    } -> tensor<2x3xf32>
    return %r : tensor<2x3xf32>
  }
}
