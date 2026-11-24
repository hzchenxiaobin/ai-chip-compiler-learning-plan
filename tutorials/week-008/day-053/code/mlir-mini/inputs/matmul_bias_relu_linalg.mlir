// 上游对照：同一张 MatMul -> Add(bias) -> Relu 图用上游方言写出来。
// linalg.matmul 算乘积，arith.addf 做 bias 加法，arith.maximumf 即 relu。
// 跑法见教程 §5.4：
//   /usr/lib/llvm-18/bin/mlir-opt matmul_bias_relu_linalg.mlir \
//       --convert-elementwise-to-linalg --linalg-fuse-elementwise-ops
module {
  func.func @mm_bias_relu(%a: tensor<2x3xf32>, %b: tensor<3x2xf32>, %bias: tensor<2x2xf32>) -> tensor<2x2xf32> {
    %init = tensor.empty() : tensor<2x2xf32>
    %m = linalg.matmul ins(%a, %b : tensor<2x3xf32>, tensor<3x2xf32>) outs(%init : tensor<2x2xf32>) -> tensor<2x2xf32>
    %cst = arith.constant dense<0.0> : tensor<2x2xf32>
    %s = arith.addf %m, %bias : tensor<2x2xf32>
    %r = arith.maximumf %s, %cst : tensor<2x2xf32>
    func.return %r : tensor<2x2xf32>
  }
}
