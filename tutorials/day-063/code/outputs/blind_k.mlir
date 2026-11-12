// 第 63 天复盘用：藏在 ? 后面的 K 失配（与 Day 62 k_blind 同款）
module {
  func.func @matmul(%a: memref<?x4xf32>, %b: memref<3x2xf32>,
                    %o: memref<?x2xf32>) {
    linalg.matmul ins(%a, %b : memref<?x4xf32>, memref<3x2xf32>)
                  outs(%o : memref<?x2xf32>)
    return
  }
}
