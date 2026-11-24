module {
  func.func @main_kernel(%a: memref<8x8xf32, strided<[8, 1]>>,
                         %b: memref<8x8xf32, strided<[8, 1]>>,
                         %bias: memref<8xf32, strided<[1]>>)
      -> memref<8x8xf32> attributes { llvm.emit_c_interface } {
    %c = memref.alloc() : memref<8x8xf32>
    %c0 = arith.constant 0 : index
    %c1 = arith.constant 1 : index
    %cM = arith.constant 8 : index
    %cN = arith.constant 8 : index
    %cK = arith.constant 8 : index
    scf.for %i = %c0 to %cM step %c1 {
      scf.for %j = %c0 to %cN step %c1 {
        %bj = memref.load %bias[%j] : memref<8xf32, strided<[1]>>
        %acc = scf.for %k = %c0 to %cK step %c1
                    iter_args(%acc = %bj) -> (f32) {
          %aij = memref.load %a[%i, %k] : memref<8x8xf32, strided<[8, 1]>>
          %bkj = memref.load %b[%k, %j] : memref<8x8xf32, strided<[8, 1]>>
          %p = arith.mulf %aij, %bkj : f32
          %s = arith.addf %acc, %p : f32
          scf.yield %s : f32
        }
        %pos = arith.constant 0.0 : f32
        %cond = arith.cmpf ogt, %acc, %pos : f32
        %r = arith.select %cond, %acc, %pos : f32
        memref.store %r, %c[%i, %j] : memref<8x8xf32>
      }
    }
    func.return %c : memref<8x8xf32>
  }
}

