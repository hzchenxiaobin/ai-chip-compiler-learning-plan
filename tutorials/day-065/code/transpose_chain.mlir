// transpose_chain.mlir —— 第 65 天静态样例：一对互逆转置（语义合计恒等）。
//
// in 2x3x4 --[1,2,0]--> 3x4x2 --[2,0,1]--> 2x3x4
// 第二个排列 [2,0,1] 恰是第一个的逆：整条链合计为恒等。
//
// 本机 LLVM 18.1.8 实测（2026-11-12）：
//   mlir-opt transpose_chain.mlir --canonicalize   → IR 原样保留（无此规则）
//   mlir-opt transpose_chain.mlir --convert-linalg-to-loops
//     → 6 层 scf.for、2 行 load、2 行 store（数据搬两遍）
// 对照：mini 的 P1（互逆消除）会把这条链整体消除为 return %in。
module {
  func.func @chain(%in: memref<2x3x4xf32>) -> memref<2x3x4xf32> {
    %0 = memref.alloc() : memref<3x4x2xf32>
    linalg.transpose ins(%in: memref<2x3x4xf32>) outs(%0: memref<3x4x2xf32>) permutation = [1, 2, 0]
    %1 = memref.alloc() : memref<2x3x4xf32>
    linalg.transpose ins(%0: memref<3x4x2xf32>) outs(%1: memref<2x3x4xf32>) permutation = [2, 0, 1]
    return %1 : memref<2x3x4xf32>
  }
}
