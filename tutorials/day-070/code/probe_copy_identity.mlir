// probe_copy_identity.mlir —— 探针 3（反例 R3：别名语义）
//
// alloc + copy + return：memref.copy 在「值」上是恒等映射，图上看似冗余。
// 但删掉它 = 返回 %x 本身 = 调用方拿到的是自己的缓冲——
// 之后任何一方原地写，另一方都会被污染。别名语义不许删。
//
// 本机 LLVM 18.1.8 实测（2026-11-12）：
//   mlir-opt probe_copy_identity.mlir --canonicalize → copy 保留
//   mlir-opt probe_copy_identity.mlir --cse           → copy 保留

func.func @copy_identity(%x: memref<2x3xf32>) -> memref<2x3xf32> {
  %c = memref.alloc() : memref<2x3xf32>
  memref.copy %x, %c : memref<2x3xf32> to memref<2x3xf32>
  return %c : memref<2x3xf32>
}
