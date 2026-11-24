// bad_transpose.mlir —— 第 64 天：非法的转置（排列合法，但结果类型写错）。
//
// perm = [1, 0] 作用于 memref<2x3xf32>，结果第 0 维应是 3（= 输入第 1 维），
// 这里却写成 memref<2x3xf32>（第 0 维 2、第 1 维 3，都反了）。
//
// 本机实测（LLVM 18.1.8）exit=1，报错原文把约定写在错误里：
//   'linalg.transpose' op dim(result, 0) = 2 doesn't match
//   dim(input, permutation[0]) = 3
//
// 运行（期望 exit=1）：
//   mlir-opt bad_transpose.mlir -o /dev/null

func.func @bad_transpose(%in: memref<2x3xf32>, %out: memref<2x3xf32>) {
  linalg.transpose ins(%in: memref<2x3xf32>)
                   outs(%out: memref<2x3xf32>)
                   permutation = [1, 0]
  return
}
