// minic S2 完整版：图 IR → 朴素三重循环（点循环写全）
// 语义：C = relu(A @ B + bias)（bias 融在 k=0 圈）
module {
  func.func @main_kernel(
      %a: memref<4x6xf32, strided<[6, 1]>>,
      %b: memref<6x3xf32, strided<[3, 1]>>
      , %bias: memref<3xf32, strided<[1]>>
    ) -> memref<4x3xf32> attributes { llvm.emit_c_interface } {
    %c = memref.alloc() : memref<4x3xf32>
    %c0 = arith.constant 0 : index
    %cM = arith.constant 4 : index
    %cN = arith.constant 3 : index
    %cK = arith.constant 6 : index
    %c1 = arith.constant 1 : index
    scf.for %i = %c0 to %cM step %c1 {
      scf.for %j = %c0 to %cN step %c1 {
        %bj = memref.load %bias[%j] : memref<3xf32, strided<[1]>>
        %acc = scf.for %k = %c0 to %cK step %c1
                    iter_args(%acc = %bj) -> (f32) {
          %aij = memref.load %a[%i, %k] : memref<4x6xf32, strided<[6, 1]>>
          %bkj = memref.load %b[%k, %j] : memref<6x3xf32, strided<[3, 1]>>
          %p = arith.mulf %aij, %bkj : f32
          %s = arith.addf %acc, %p : f32
          scf.yield %s : f32
        }
        %pos = arith.constant 0.0 : f32
        %cond = arith.cmpf ogt, %acc, %pos : f32
        %r = arith.select %cond, %acc, %pos : f32
        memref.store %r, %c[%i, %j] : memref<4x3xf32>
      }
    }
    func.return %c : memref<4x3xf32>
  }
}