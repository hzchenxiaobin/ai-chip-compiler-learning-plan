// sandwich_after.mlir —— 探针 3（改写后）：三明治相消之后该长什么样。
//
// 传播（T 穿过 ReLU）+ 合并（相邻两转置 r = q[p[i]] = 恒等）之后，
// 图里只剩 ReLU 本体——这就是 mini 第 3 节「2 -> 0」的 MLIR 对应物。
//
// 本机 LLVM 18.1.8 实测（2026-11-12）：
//   mlir-opt sandwich_after.mlir --convert-linalg-to-loops
//     → 2 层 scf.for、1 行 memref.load、1 行 memref.store
//       （每个元素只被搬 1 遍：读一次写一次，且这次搬运是有用功）

module {
  func.func @sandwich_after(%x: memref<2x3xf32>) -> memref<2x3xf32> {
    %1 = memref.alloc() : memref<2x3xf32>
    linalg.generic {
      indexing_maps = [affine_map<(d0, d1) -> (d0, d1)>,
                       affine_map<(d0, d1) -> (d0, d1)>],
      iterator_types = ["parallel", "parallel"]
    } ins(%x : memref<2x3xf32>) outs(%1 : memref<2x3xf32>) {
    ^bb0(%in: f32, %out: f32):
      %zero = arith.constant 0.0 : f32
      %cmp = arith.cmpf ogt, %in, %zero : f32
      %sel = arith.select %cmp, %in, %zero : f32
      linalg.yield %sel : f32
    }
    return %1 : memref<2x3xf32>
  }
}
