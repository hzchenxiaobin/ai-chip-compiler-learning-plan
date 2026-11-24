// transpose_2d.mlir —— 第 64 天：合法的 2D 转置（与教程贯穿例子同款 2x3 → 3x2）。
//
// 约定（本文件被 mlir-opt 实测接受，LLVM 18.1.8）：
//   out_shape[i] = in_shape[permutation[i]]
//   即 permutation = [1, 0] 时：memref<2x3xf32> 的结果类型必须是 memref<3x2xf32>。
//
// 运行（解析 + 验证，期望 exit=0）：
//   mlir-opt transpose_2d.mlir -o /dev/null
//
// 看它降级成双循环后的「读写下标交换」（搬家的代码形态）：
//   mlir-opt transpose_2d.mlir --convert-linalg-to-loops

func.func @transpose_2d(%in: memref<2x3xf32>, %out: memref<3x2xf32>) {
  linalg.transpose ins(%in: memref<2x3xf32>)
                   outs(%out: memref<3x2xf32>)
                   permutation = [1, 0]
  return
}
