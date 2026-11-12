// 第 63 天对照实验二：合法动态（M=?，K=3 正确）
module {
  func.func @matmul(%a: memref<?x3xf32>, %b: memref<3x2xf32>,
                    %o: memref<?x2xf32>) {
    linalg.matmul ins(%a, %b : memref<?x3xf32>, memref<3x2xf32>)
                  outs(%o : memref<?x2xf32>)
    return
  }
}
