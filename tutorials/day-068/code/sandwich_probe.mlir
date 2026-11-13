// sandwich_probe.mlir —— 探针 2：「互逆三明治」会不会被相消？
//
// in 2x3 --[1,0]--> 3x2 --ReLU--> 3x2 --[1,0]--> 2x3
// 语义合计 = ReLU(x)：两个转置互逆（p = p^-1 = (1,0)）。
// 传播视角：把外层 T 穿过 ReLU 推向生产者，与内层 T 相邻后即可合并，
// 合并排列 r = 恒等 → 整体相消。
//
// 本机 LLVM 18.1.8 实测（2026-11-12）：
//   mlir-opt sandwich_probe.mlir --canonicalize
//     → exit=0，IR 原样保留（2 个 transpose + 1 个 generic）
//   结论：stock 管道既不传播也不相消，「合计零语义」的三明治原样活着。

module {
  func.func @sandwich(%x: tensor<2x3xf32>) -> tensor<2x3xf32> {
    %init0 = tensor.empty() : tensor<3x2xf32>
    %t0 = linalg.transpose ins(%x : tensor<2x3xf32>) outs(%init0 : tensor<3x2xf32>) permutation = [1, 0]

    %init1 = tensor.empty() : tensor<3x2xf32>
    %r = linalg.generic {
      indexing_maps = [affine_map<(d0, d1) -> (d0, d1)>,
                       affine_map<(d0, d1) -> (d0, d1)>],
      iterator_types = ["parallel", "parallel"]
    } ins(%t0 : tensor<3x2xf32>) outs(%init1 : tensor<3x2xf32>) {
    ^bb0(%in: f32, %out: f32):
      %zero = arith.constant 0.0 : f32
      %cmp = arith.cmpf ogt, %in, %zero : f32
      %sel = arith.select %cmp, %in, %zero : f32
      linalg.yield %sel : f32
    } -> tensor<3x2xf32>

    %init2 = tensor.empty() : tensor<2x3xf32>
    %t1 = linalg.transpose ins(%r : tensor<3x2xf32>) outs(%init2 : tensor<2x3xf32>) permutation = [1, 0]
    return %t1 : tensor<2x3xf32>
  }
}
