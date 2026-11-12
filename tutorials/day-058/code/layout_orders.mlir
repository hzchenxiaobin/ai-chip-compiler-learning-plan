// layout_orders.mlir —— 第 58 天：NCHW 与 NHWC 在 MLIR memref 类型里的样子。
//
// 与 layout_lab.py 用同一份数据：N=1, C=4, H=2, W=4，共 32 个 f32。
// 逻辑内容 v(n,c,h,w) = c*8 + h*4 + w（即每个元素的 NCHW 编号）。
//
// 三个角色：
//   @nchw  ：物理 NCHW 的常量存储（行主序 memref<1x4x2x4xf32>，strides=(32,8,4,1)）
//   @nhwc  ：同一逻辑张量重排后的物理 NHWC 存储（行主序 memref<1x2x4x4xf32>，strides=(32,16,4,1)）
//   transpose 视图：NCHW 存储上的零拷贝 NHWC 逻辑视图（唯一合法 strides=(32,4,1,8)）
//
// 三种「运行」方式：
//   1) 解析 + 验证 + 打印：
//        mlir-opt layout_orders.mlir
//   2) 编译期折叠（布局元数据变成常数）：
//        mlir-opt --canonicalize layout_orders.mlir
//   3) 真实执行（同一逻辑像素、两种布局各取一次数）：
//        mlir-opt --convert-func-to-llvm --finalize-memref-to-llvm \
//          --convert-arith-to-llvm --reconcile-unrealized-casts \
//          layout_orders.mlir -o layout_orders.lowered.mlir
//        mlir-cpu-runner layout_orders.lowered.mlir -e main --entry-point-result=void \
//          --shared-libs=<llvm-lib>/libmlir_runner_utils.so,<llvm-lib>/libmlir_c_runner_utils.so

module {
  // ---- 物理 NCHW：隐式 strides = (32, 8, 4, 1)，最内维是 W ----
  // 平铺顺序 0,1,2,...,31（值恰好等于物理位置，方便肉眼核对）
  memref.global constant @nchw : memref<1x4x2x4xf32> = dense<
    [[[[0.0, 1.0, 2.0, 3.0], [4.0, 5.0, 6.0, 7.0]],
      [[8.0, 9.0, 10.0, 11.0], [12.0, 13.0, 14.0, 15.0]],
      [[16.0, 17.0, 18.0, 19.0], [20.0, 21.0, 22.0, 23.0]],
      [[24.0, 25.0, 26.0, 27.0], [28.0, 29.0, 30.0, 31.0]]]]>

  // ---- 物理 NHWC：隐式 strides = (32, 16, 4, 1)，最内维是 C ----
  // 平铺顺序 0,8,16,24, 1,9,17,25, ...（同一批值，换了个物理顺序住）
  memref.global constant @nhwc : memref<1x2x4x4xf32> = dense<
    [[[[0.0, 8.0, 16.0, 24.0], [1.0, 9.0, 17.0, 25.0],
       [2.0, 10.0, 18.0, 26.0], [3.0, 11.0, 19.0, 27.0]],
      [[4.0, 12.0, 20.0, 28.0], [5.0, 13.0, 21.0, 29.0],
       [6.0, 14.0, 22.0, 30.0], [7.0, 15.0, 23.0, 31.0]]]]>

  // ---- NHWC 逻辑视图（零拷贝）：只置换元信息，不搬数据 ----
  // 在 strides=(32,8,4,1) 的 NCHW 存储上做 (n,c,h,w) -> (n,h,w,c)，
  // 唯一合法的结果 strides 是 (32, 4, 1, 8)——与 numpy 的
  // nchw.transpose(0,2,3,1) 完全同口径。
  // --canonicalize 会把返回值折叠成常数 (0, 32, 4, 1, 8)。
  func.func @nhwc_view_metadata(%x: memref<1x4x2x4xf32>)
      -> (index, index, index, index, index) {
    %t = memref.transpose %x (n, c, h, w) -> (n, h, w, c)
      : memref<1x4x2x4xf32> to memref<1x2x4x4xf32, strided<[32, 4, 1, 8]>>

    %base, %offset, %sizes:4, %strides:4 =
      memref.extract_strided_metadata %t
      : memref<1x2x4x4xf32, strided<[32, 4, 1, 8]>>
        -> memref<f32>, index, index, index, index, index,
           index, index, index, index
    return %offset, %strides#0, %strides#1, %strides#2, %strides#3
      : index, index, index, index, index
  }

  // ---- 同一逻辑像素，两种布局各算一次物理偏移（编译期折叠） ----
  // 像素 (n=0, c=2, h=1, w=3)，逻辑值 v = 2*8 + 1*4 + 3 = 23。
  // NCHW 里它住 23 号格（offset = 2*8 + 1*4 + 3*1 = 23）；
  // NHWC 里它住 30 号格（offset = 1*16 + 3*4 + 2*1 = 30）。
  // --canonicalize 会把两次「按布局元数据算地址」折叠成常数 (23, 30)：
  // 编译器不运行任何代码，就静态算出了两个不同布局下的两个家。
  func.func @same_pixel_two_offsets() -> (index, index) {
    %a = memref.get_global @nchw : memref<1x4x2x4xf32>
    %b = memref.get_global @nhwc : memref<1x2x4x4xf32>
    %base_a, %off_a, %sizes_a:4, %strides_a:4 =
      memref.extract_strided_metadata %a
      : memref<1x4x2x4xf32>
        -> memref<f32>, index, index, index, index, index,
           index, index, index, index
    %base_b, %off_b, %sizes_b:4, %strides_b:4 =
      memref.extract_strided_metadata %b
      : memref<1x2x4x4xf32>
        -> memref<f32>, index, index, index, index, index,
           index, index, index, index
    %c2 = arith.constant 2 : index
    %h1 = arith.constant 1 : index
    %w3 = arith.constant 3 : index
    // NCHW：offset = 0 + c*strides_a#1 + h*strides_a#2 + w*strides_a#3
    %a1 = arith.muli %c2, %strides_a#1 : index
    %a2 = arith.muli %h1, %strides_a#2 : index
    %a3 = arith.muli %w3, %strides_a#3 : index
    %s1 = arith.addi %off_a, %a1 : index
    %s2 = arith.addi %s1, %a2 : index
    %s3 = arith.addi %s2, %a3 : index
    // NHWC：offset = 0 + h*strides_b#1 + w*strides_b#2 + c*strides_b#3
    %b1 = arith.muli %h1, %strides_b#1 : index
    %b2 = arith.muli %w3, %strides_b#2 : index
    %b3 = arith.muli %c2, %strides_b#3 : index
    %t1 = arith.addi %off_b, %b1 : index
    %t2 = arith.addi %t1, %b2 : index
    %t3 = arith.addi %t2, %b3 : index
    return %s3, %t3 : index, index
  }

  // ---- 真实执行：同一逻辑像素，两种布局里各取一次数 ----
  // 两个 load 的下标顺序不同（NCHW 给 (n,c,h,w)，NHWC 给 (n,h,w,c)），
  // 各自按自己的布局算地址、取回同一个值 23.0。
  // 用 mlir-cpu-runner 跑（见文件头注释第 3 种运行方式），输出两行 23。
  func.func private @printF32(f32)
  func.func private @printNewline()

  func.func @main() {
    %a = memref.get_global @nchw : memref<1x4x2x4xf32>
    %b = memref.get_global @nhwc : memref<1x2x4x4xf32>
    %c0 = arith.constant 0 : index
    %c2 = arith.constant 2 : index
    %h1 = arith.constant 1 : index
    %w3 = arith.constant 3 : index
    %va = memref.load %a[%c0, %c2, %h1, %w3] : memref<1x4x2x4xf32>
    %vb = memref.load %b[%c0, %h1, %w3, %c2] : memref<1x2x4x4xf32>
    call @printF32(%va) : (f32) -> ()
    call @printNewline() : () -> ()
    call @printF32(%vb) : (f32) -> ()
    call @printNewline() : () -> ()
    return
  }
}
