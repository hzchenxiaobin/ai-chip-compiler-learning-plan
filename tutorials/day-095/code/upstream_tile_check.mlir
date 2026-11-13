// upstream_tile_check.mlir —— 上游对照实验（第 95 天）
// 同一个主例 5x7x3、tile 2x4x2，交给上游 MLIR 的 tiling：
//   mlir-opt upstream_tile_check.mlir \
//     --test-transform-dialect-interpreter --test-transform-dialect-erase-schedule
// 输出里会出现三条 affine.min（tile 尺寸钳制）：
//   min(2, 5 - i0) / min(4, 7 - j0) / min(2, 3 - k0)
// 这就是“min 钳制是上游同款做法”的直接证据（完整输出见 outputs/upstream-tiling.txt）。

module {
  func.func @matmul(%A: memref<5x3xf32>, %B: memref<3x7xf32>, %C: memref<5x7xf32>) {
    linalg.matmul ins(%A, %B : memref<5x3xf32>, memref<3x7xf32>) outs(%C : memref<5x7xf32>)
    return
  }
  module @transforms {
    transform.sequence failures(propagate) {
    ^bb0(%arg0: !transform.any_op):
      %matmul = transform.structured.match ops{["linalg.matmul"]} in %arg0
        : (!transform.any_op) -> !transform.any_op
      %tiled, %li, %lj, %lk = transform.structured.tile_using_for %matmul[2, 4, 2]
        : (!transform.any_op) -> (!transform.any_op, !transform.any_op, !transform.any_op, !transform.any_op)
    }
  }
}
