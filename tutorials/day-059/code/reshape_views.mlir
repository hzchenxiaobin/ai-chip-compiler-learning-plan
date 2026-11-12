// reshape_views.mlir —— 第 59 天：Reshape 在 MLIR memref 里的三种合法姿态。
//
// 与 reshape_lab.py 用同一份数据：3x4 的 12 个 f32，
// 值 = 逻辑行主序编号 0..11（值 = 物理格号，方便肉眼核对）。
//
// MLIR 把 reshape 拆成三个操作，各自表达一类变换：
//   memref.expand_shape  ：拆维（reassociation 把一维拆成多维）
//   memref.collapse_shape：合维（reassociation 把多维并成一维）
//   memref.reshape       ：通用形式（形状来自运行期 %shape 操作数）
//
// 四种「运行」方式：
//   1) 解析 + 验证 + 打印：
//        mlir-opt reshape_views.mlir
//   2) 编译期折叠（元信息变常数）：
//        mlir-opt --canonicalize reshape_views.mlir
//   3) 视图操作展开成基址+偏移运算：
//        mlir-opt --expand-strided-metadata reshape_views.mlir
//   4) 真实执行（视图上取数）：
//        mlir-opt --expand-strided-metadata --convert-func-to-llvm \
//          --finalize-memref-to-llvm --convert-arith-to-llvm \
//          --reconcile-unrealized-casts \
//          reshape_views.mlir -o reshape_views.lowered.mlir
//        mlir-cpu-runner reshape_views.lowered.mlir -e main \
//          --entry-point-result=void \
//          --shared-libs=<llvm-lib>/libmlir_runner_utils.so,<llvm-lib>/libmlir_c_runner_utils.so

module {
  // ---- 连续基座：隐式 strides = (4, 1) ----
  memref.global constant @data12 : memref<3x4xf32> = dense<
    [[0.0, 1.0, 2.0, 3.0], [4.0, 5.0, 6.0, 7.0], [8.0, 9.0, 10.0, 11.0]]>

  // ---- ① 拆维视图：(3,4) -> (3,2,2)，新 strides = (4,2,1) ----
  // reassociation [[0],[1,2]]：源第 1 维（大小 4）拆成结果的第 1、2 维（2x2）。
  // --canonicalize 会把 extract_strided_metadata 折叠成常数
  // (offset=0, sizes=3,2,2, strides=4,2,1)——零拷贝证据。
  func.func @expand_metadata()
      -> (index, index, index, index, index, index, index) {
    %g = memref.get_global @data12 : memref<3x4xf32>
    %e = memref.expand_shape %g [[0], [1, 2]]
      : memref<3x4xf32> into memref<3x2x2xf32>
    %base, %off, %sz:3, %st:3 = memref.extract_strided_metadata %e
      : memref<3x2x2xf32> -> memref<f32>, index, index, index, index,
         index, index, index
    return %off, %sz#0, %sz#1, %sz#2, %st#0, %st#1, %st#2
      : index, index, index, index, index, index, index
  }

  // ---- ② 合维视图：非连续但「可打包」的源也能合 ----
  // 列切片 (3,4) -> (3,2) strided<[4,2]>（每行取前 2 列），
  // 再把两维并成一维：外维步长 4 == 内维容量 2 x 内维步长 2，
  // 满足打包条件 -> (6,) strided<[2]> 是合法零拷贝视图。
  // --canonicalize 折叠出 (offset=0, size=6, stride=2)。
  func.func @collapse_metadata() -> (index, index, index) {
    %g = memref.get_global @data12 : memref<3x4xf32>
    %s = memref.subview %g [0, 0] [3, 2] [1, 2]
      : memref<3x4xf32> to memref<3x2xf32, strided<[4, 2]>>
    %c = memref.collapse_shape %s [[0, 1]]
      : memref<3x2xf32, strided<[4, 2]>> into memref<6xf32, strided<[2]>>
    %base, %off, %sz, %st = memref.extract_strided_metadata %c
      : memref<6xf32, strided<[2]>> -> memref<f32>, index, index, index
    return %off, %sz, %st : index, index, index
  }

  // ---- ③ 往返：expand 后 collapse 回原形 ----
  // 两次都只改元信息，--canonicalize 直接把往返折成恒等（return %arg0）：
  // 「仅修改元信息」的变换在编译期可以免费抵消。
  func.func @roundtrip(%arg0: memref<3x4xf32>) -> memref<3x4xf32> {
    %0 = memref.expand_shape %arg0 [[0], [1, 2]]
      : memref<3x4xf32> into memref<3x2x2xf32>
    %1 = memref.collapse_shape %0 [[0], [1, 2]]
      : memref<3x2x2xf32> into memref<3x4xf32>
    return %1 : memref<3x4xf32>
  }

  // ---- ④ 真实执行：三种视图上各取一个数 ----
  // v1: 拆维视图 (3,2,2) 下标 (1,1,0) = 原下标 (1,2) = 6.0
  // v2: 合维视图 (6,) 下标 4 = 偏移 4x2 = 8 -> 值 8.0
  // v3: memref.reshape 用运行期 shape [2,6]，下标 (1,4) = flat 10 -> 值 10.0
  func.func private @printF32(f32)
  func.func private @printNewline()

  func.func @main() {
    %g = memref.get_global @data12 : memref<3x4xf32>
    %i0 = arith.constant 0 : index
    %i1 = arith.constant 1 : index
    %i4 = arith.constant 4 : index
    %c2 = arith.constant 2 : index
    %c6 = arith.constant 6 : index

    // 拆维视图上取数
    %e = memref.expand_shape %g [[0], [1, 2]]
      : memref<3x4xf32> into memref<3x2x2xf32>
    %v1 = memref.load %e[%i1, %i1, %i0] : memref<3x2x2xf32>

    // 合维视图上取数（先列切片再合并）
    %s = memref.subview %g [0, 0] [3, 2] [1, 2]
      : memref<3x4xf32> to memref<3x2xf32, strided<[4, 2]>>
    %c = memref.collapse_shape %s [[0, 1]]
      : memref<3x2xf32, strided<[4, 2]>> into memref<6xf32, strided<[2]>>
    %v2 = memref.load %c[%i4] : memref<6xf32, strided<[2]>>

    // 通用 reshape：形状来自运行期 %shape = [2, 6]
    %shape = memref.alloca() : memref<2xindex>
    memref.store %c2, %shape[%i0] : memref<2xindex>
    memref.store %c6, %shape[%i1] : memref<2xindex>
    %r = memref.reshape %g(%shape)
      : (memref<3x4xf32>, memref<2xindex>) -> memref<2x6xf32>
    %v3 = memref.load %r[%i1, %i4] : memref<2x6xf32>

    call @printF32(%v1) : (f32) -> ()
    call @printNewline() : () -> ()
    call @printF32(%v2) : (f32) -> ()
    call @printNewline() : () -> ()
    call @printF32(%v3) : (f32) -> ()
    call @printNewline() : () -> ()
    return
  }
}
