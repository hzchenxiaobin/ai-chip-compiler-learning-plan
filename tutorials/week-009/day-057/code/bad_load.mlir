// bad_load.mlir —— 第 57 天常见错误 3 的现场：下标个数与秩不匹配。
// 对 2x3 的 memref 用单个下标 load，Verifier 拒绝整张 IR。
//
// 预期（mlir-opt 退出码 1）：
//   error: 'memref.load' op incorrect number of indices for load, expected 2 but got 1

module {
  func.func @bad(%i: index) -> f32 {
    %s = memref.alloc() : memref<2x3xf32>
    %v = memref.load %s[%i] : memref<2x3xf32>
    return %v : f32
  }
}
