module {
  func.func @kernel_static(%a: memref<4x6xf32, strided<[6, 1]>>,
                           %b: memref<6x3xf32, strided<[3, 1]>>)
      -> memref<4x3xf32> attributes { llvm.emit_c_interface } {
    %c = memref.alloc() : memref<4x3xf32>
    %c0 = arith.constant 0 : index
    %cM = arith.constant 4 : index
    %cN = arith.constant 3 : index
    %cK = arith.constant 6 : index
    %c1 = arith.constant 1 : index
    %z = arith.constant 0.0 : f32
    scf.for %i = %c0 to %cM step %c1 {
      scf.for %j = %c0 to %cN step %c1 {
        %acc = scf.for %k = %c0 to %cK step %c1
                    iter_args(%acc = %z) -> (f32) {
          %aij = memref.load %a[%i, %k] : memref<4x6xf32, strided<[6, 1]>>
          %bkj = memref.load %b[%k, %j] : memref<6x3xf32, strided<[3, 1]>>
          %p = arith.mulf %aij, %bkj : f32
          %s = arith.addf %acc, %p : f32
          scf.yield %s : f32
        }
        memref.store %acc, %c[%i, %j] : memref<4x3xf32>
      }
    }
    func.return %c : memref<4x3xf32>
  }
}
