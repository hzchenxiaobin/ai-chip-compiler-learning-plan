// idem_cse.mlir —— 探针 2：--cse 幂等吗？两个相同的 generic 会不会合并？
//
// 同一个输入上做两个一模一样的逐元素 ReLU（linalg.generic）。
//
// 本机 LLVM 18.1.8 实测（2026-11-12）：
//   mlir-opt idem_cse.mlir --cse
//     → 2 个 generic 合并成 1 个（return %1, %1）
//   mlir-opt idem_cse.mlir --cse --cse
//     → 输出与跑一遍逐字节相同

module {
  func.func @idem_cse(%x: tensor<2x3xf32>) -> (tensor<2x3xf32>, tensor<2x3xf32>) {
    %init1 = tensor.empty() : tensor<2x3xf32>
    %r1 = linalg.generic {
      indexing_maps = [affine_map<(d0, d1) -> (d0, d1)>,
                       affine_map<(d0, d1) -> (d0, d1)>],
      iterator_types = ["parallel", "parallel"]
    } ins(%x : tensor<2x3xf32>) outs(%init1 : tensor<2x3xf32>) {
    ^bb0(%in: f32, %out: f32):
      %zero = arith.constant 0.0 : f32
      %cmp = arith.cmpf ogt, %in, %zero : f32
      %sel = arith.select %cmp, %in, %zero : f32
      linalg.yield %sel : f32
    } -> tensor<2x3xf32>

    %init2 = tensor.empty() : tensor<2x3xf32>
    %r2 = linalg.generic {
      indexing_maps = [affine_map<(d0, d1) -> (d0, d1)>,
                       affine_map<(d0, d1) -> (d0, d1)>],
      iterator_types = ["parallel", "parallel"]
    } ins(%x : tensor<2x3xf32>) outs(%init2 : tensor<2x3xf32>) {
    ^bb0(%in: f32, %out: f32):
      %zero = arith.constant 0.0 : f32
      %cmp = arith.cmpf ogt, %in, %zero : f32
      %sel = arith.select %cmp, %in, %zero : f32
      linalg.yield %sel : f32
    } -> tensor<2x3xf32>
    return %r1, %r2 : tensor<2x3xf32>, tensor<2x3xf32>
  }
}
