module {
  memref.global "private" constant @ga : memref<2x3xf32> = dense<[[1.000000e+00, 2.000000e+00, 3.000000e+00], [4.000000e+00, 5.000000e+00, 6.000000e+00]]>
  memref.global "private" constant @gb : memref<3xf32> = dense<[1.000000e+01, 2.000000e+01, 3.000000e+01]>
  memref.global "private" constant @gc : memref<2x1xf32> = dense<[[1.000000e+02], [2.000000e+02]]>
  func.func private @printF32(f32)
  func.func private @printNewline()
  func.func @main() {
    %c3 = arith.constant 3 : index
    %c2 = arith.constant 2 : index
    %c1 = arith.constant 1 : index
    %c0 = arith.constant 0 : index
    %0 = memref.get_global @ga : memref<2x3xf32>
    %1 = memref.get_global @gb : memref<3xf32>
    %2 = memref.get_global @gc : memref<2x1xf32>
    %alloc = memref.alloc() : memref<2x3xf32>
    %alloc_0 = memref.alloc() : memref<2x3xf32>
    scf.for %arg0 = %c0 to %c2 step %c1 {
      scf.for %arg1 = %c0 to %c3 step %c1 {
        %7 = memref.load %0[%arg0, %arg1] : memref<2x3xf32>
        %8 = memref.load %1[%arg1] : memref<3xf32>
        %9 = arith.addf %7, %8 : f32
        memref.store %9, %alloc[%arg0, %arg1] : memref<2x3xf32>
      }
    }
    scf.for %arg0 = %c0 to %c2 step %c1 {
      scf.for %arg1 = %c0 to %c3 step %c1 {
        %7 = memref.load %0[%arg0, %arg1] : memref<2x3xf32>
        %8 = memref.load %2[%arg0, %c0] : memref<2x1xf32>
        %9 = arith.addf %7, %8 : f32
        memref.store %9, %alloc_0[%arg0, %arg1] : memref<2x3xf32>
      }
    }
    %3 = memref.load %alloc[%c0, %c2] : memref<2x3xf32>
    %4 = memref.load %alloc[%c1, %c1] : memref<2x3xf32>
    %5 = memref.load %alloc_0[%c0, %c0] : memref<2x3xf32>
    %6 = memref.load %alloc_0[%c1, %c2] : memref<2x3xf32>
    call @printF32(%3) : (f32) -> ()
    call @printNewline() : () -> ()
    call @printF32(%4) : (f32) -> ()
    call @printNewline() : () -> ()
    call @printF32(%5) : (f32) -> ()
    call @printNewline() : () -> ()
    call @printF32(%6) : (f32) -> ()
    call @printNewline() : () -> ()
    return
  }
}

