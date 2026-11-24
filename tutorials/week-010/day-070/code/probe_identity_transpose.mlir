// probe_identity_transpose.mlir —— 探针 5（反例 R5：布局语义）
//
// 恒等排列（permutation = [0, 1]）的物理转置：值上是「照抄」，
// 图上看似可消除。但输入带 strided 布局（可能是某个视图），
// 输出是连续 alloc——这个 op 是把 strided 视图落地成连续 buffer 的
// 物化点，删掉它，调用方拿到的布局就变了（下游零拷贝权利跟着变）。
//
// 本机 LLVM 18.1.8 实测（2026-11-12）：
//   mlir-opt probe_identity_transpose.mlir --canonicalize → 转置保留
//   mlir-opt probe_identity_transpose.mlir --cse           → 转置保留

func.func @identity_perm_layout(%x: memref<2x3xf32, strided<[3, 1], offset: ?>>) -> memref<2x3xf32> {
  %o = memref.alloc() : memref<2x3xf32>
  linalg.transpose ins(%x : memref<2x3xf32, strided<[3, 1], offset: ?>>) outs(%o : memref<2x3xf32>) permutation = [0, 1]
  return %o : memref<2x3xf32>
}
