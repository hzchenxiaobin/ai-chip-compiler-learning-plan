// order_cast.mlir —— 探针 4：Cast 消除解锁 CSE（本周 Day 67 的组合现场）。
//
// %r1 = relu(x)
// %r2 = relu( tensor.cast(x) )   ← 恒等 cast（同类型同 shape，无操作）
// 两个 generic 语义相同，但初始 IR 里一个读 %x、一个读 %cast。
//
// 本机 LLVM 18.1.8 实测（2026-11-12）：
//   mlir-opt order_cast.mlir --canonicalize
//     → tensor.cast 计数 0（恒等 cast 被 stock 管道真实删除）
//   mlir-opt order_cast.mlir --canonicalize --cse
//     → 1 个 linalg.generic（cast 删掉后两个 generic 操作数相同，CSE 合并）
//   mlir-opt order_cast.mlir --cse --canonicalize
//     → 2 个 linalg.generic（CSE 先跑时操作数还不同；它没有第二次机会）
//
// 这正是 mini 侧「Cast 消除 × 融合」合流对的 stock 版本：
// 消除类 pass 要在使用机会的 pass 之前跑（或者把管道循环到不动点）。

module {
  func.func @order_cast(%x: tensor<2x3xf32>) -> (tensor<2x3xf32>, tensor<2x3xf32>) {
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

    %cast = tensor.cast %x : tensor<2x3xf32> to tensor<2x3xf32>
    %init2 = tensor.empty() : tensor<2x3xf32>
    %r2 = linalg.generic {
      indexing_maps = [affine_map<(d0, d1) -> (d0, d1)>,
                       affine_map<(d0, d1) -> (d0, d1)>],
      iterator_types = ["parallel", "parallel"]
    } ins(%cast : tensor<2x3xf32>) outs(%init2 : tensor<2x3xf32>) {
    ^bb0(%in: f32, %out: f32):
      %zero = arith.constant 0.0 : f32
      %cmp = arith.cmpf ogt, %in, %zero : f32
      %sel = arith.select %cmp, %in, %zero : f32
      linalg.yield %sel : f32
    } -> tensor<2x3xf32>
    return %r1, %r2 : tensor<2x3xf32>, tensor<2x3xf32>
  }
}
