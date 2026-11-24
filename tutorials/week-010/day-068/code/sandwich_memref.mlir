// sandwich_memref.mlir —— 探针 3（改写前）：三明治降成循环后的物理搬运。
//
// in 2x3 --[1,0]--> 3x2 --ReLU--> 3x2 --[1,0]--> 2x3（语义合计 = ReLU(x)）
// 三个 op 各自「读一遍写一遍」：每个元素被搬 3 遍（读+写共 6 次/元素）。
//
// 本机 LLVM 18.1.8 实测（2026-11-12）：
//   mlir-opt sandwich_memref.mlir --convert-linalg-to-loops
//     → 6 层 scf.for、3 行 memref.load、3 行 memref.store
//       （每行在 numel=6 的循环体里执行）
// 对照 sandwich_after.mlir（相消后）：2 层 for、1 行 load、1 行 store。

module {
  func.func @sandwich(%x: memref<2x3xf32>) -> memref<2x3xf32> {
    %0 = memref.alloc() : memref<3x2xf32>
    linalg.transpose ins(%x : memref<2x3xf32>) outs(%0 : memref<3x2xf32>) permutation = [1, 0]

    %1 = memref.alloc() : memref<3x2xf32>
    linalg.generic {
      indexing_maps = [affine_map<(d0, d1) -> (d0, d1)>,
                       affine_map<(d0, d1) -> (d0, d1)>],
      iterator_types = ["parallel", "parallel"]
    } ins(%0 : memref<3x2xf32>) outs(%1 : memref<3x2xf32>) {
    ^bb0(%in: f32, %out: f32):
      %zero = arith.constant 0.0 : f32
      %cmp = arith.cmpf ogt, %in, %zero : f32
      %sel = arith.select %cmp, %in, %zero : f32
      linalg.yield %sel : f32
    }

    %2 = memref.alloc() : memref<2x3xf32>
    linalg.transpose ins(%1 : memref<3x2xf32>) outs(%2 : memref<2x3xf32>) permutation = [1, 0]
    return %2 : memref<2x3xf32>
  }
}
