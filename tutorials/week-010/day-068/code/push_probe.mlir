// push_probe.mlir —— 探针 1：stock 管道会不会把 linalg.transpose
// 「穿过」逐元素 linalg.generic（ReLU）推向生产者？
//
// 语义上等价的重写（今天 mini Pattern 的 MLIR 对应物）：
//   %r = relu(%x); %t = transpose(%r)   -->   %t2 = transpose(%x); %r2 = relu(%t2)
// 即 Transpose(Relu(x)) -> Relu(Transpose(x))。
//
// 本机 LLVM 18.1.8 实测（2026-11-12）：
//   mlir-opt push_probe.mlir --canonicalize
//     → exit=0，IR 原样保留（1 个 generic + 1 个 transpose，谁也没动谁）
//   结论：这条传播规则在 stock 管道里不存在，要自己写。

func.func @push_through_relu(%x: tensor<2x3xf32>) -> tensor<3x2xf32> {
  %init = tensor.empty() : tensor<2x3xf32>
  %r = linalg.generic {
    indexing_maps = [affine_map<(d0, d1) -> (d0, d1)>,
                     affine_map<(d0, d1) -> (d0, d1)>],
    iterator_types = ["parallel", "parallel"]
  } ins(%x : tensor<2x3xf32>) outs(%init : tensor<2x3xf32>) {
  ^bb0(%in: f32, %out: f32):
    %zero = arith.constant 0.0 : f32
    %cmp = arith.cmpf ogt, %in, %zero : f32
    %sel = arith.select %cmp, %in, %zero : f32
    linalg.yield %sel : f32
  } -> tensor<2x3xf32>

  %out = tensor.empty() : tensor<3x2xf32>
  %t = linalg.transpose ins(%r : tensor<2x3xf32>)
                         outs(%out : tensor<3x2xf32>)
                         permutation = [1, 0]
  return %t : tensor<3x2xf32>
}
