module {
  func.func @kernel_dynamic(%a: memref<?x?xf32>,
                            %b: memref<?x?xf32>)
      -> memref<?x?xf32> attributes { llvm.emit_c_interface } {
    %c0 = arith.constant 0 : index
    %c1 = arith.constant 1 : index
    %z = arith.constant 0.0 : f32
    // 运行期读 shape：M/N/K 从描述符的 sizes 字段来
    %M = memref.dim %a, %c0 : memref<?x?xf32>
    %K = memref.dim %a, %c1 : memref<?x?xf32>
    %N = memref.dim %b, %c1 : memref<?x?xf32>
    // 动态 alloc：shape 是运行期值
    %c = memref.alloc(%M, %N) : memref<?x?xf32>
    scf.for %i = %c0 to %M step %c1 {
      scf.for %j = %c0 to %N step %c1 {
        %acc = scf.for %k = %c0 to %K step %c1
                    iter_args(%acc = %z) -> (f32) {
          %aij = memref.load %a[%i, %k] : memref<?x?xf32>
          %bkj = memref.load %b[%k, %j] : memref<?x?xf32>
          %p = arith.mulf %aij, %bkj : f32
          %s = arith.addf %acc, %p : f32
          scf.yield %s : f32
        }
        memref.store %acc, %c[%i, %j] : memref<?x?xf32>
      }
    }
    func.return %c : memref<?x?xf32>
  }
}
