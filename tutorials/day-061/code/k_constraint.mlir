// k_constraint.mlir —— 第 61 天：把「两个 K 运行期必须相等」写成 IR 里可检查的约束。
//
// shape dialect 的 witness（见证）机制：
//   shape.shape_of      ：取张量的形状
//   shape.get_extent    ：从形状里取某一维
//   shape.size_to_index ：维度值转成 index，参与算术比较
//   shape.cstr_require  ：「这条约束必须成立」，不成立则运行期报 msg 指定的错
//   shape.assuming      ：在 witness 成立的前提下才执行的区域
//
// 房间 1（静态）：A(2,3) 配 B(3,2)，两个 K 都是 3
//   → --canonicalize 把整条约束链折成 const_witness true，assuming 区域原地展开，
//     约束在编译期结清，运行期一分钱不花。
// 房间 2（静态失配）：A(2,4) 配 B(3,2) —— 这间房会被 linalg 自己的 Verifier
//   静态拦下（inferred ... to be 4, but found 3），进不了 witness 那一步，
//   实验放在 bad_dynamic.mlir 的房间 2。
// 房间 3（动态）：形状来自函数参数
//   → 约束原样保留，降到运行期才检查。
//
// 运行方式：
//   mlir-opt k_constraint.mlir                # 解析 + 验证
//   mlir-opt --canonicalize k_constraint.mlir  # 看静态约束折叠 / 动态约束保留

module {
  // ---- 房间 1：静态 K 匹配 → 约束编译期折成 true ----
  func.func @static_ok(%a: tensor<2x3xf32>, %b: tensor<3x2xf32>,
                       %init: tensor<2x2xf32>) -> tensor<2x2xf32> {
    %sa = shape.shape_of %a : tensor<2x3xf32> -> !shape.shape
    %sb = shape.shape_of %b : tensor<3x2xf32> -> !shape.shape
    %c1 = arith.constant 1 : index
    %c0 = arith.constant 0 : index
    %ka = shape.get_extent %sa, %c1 : !shape.shape, index -> !shape.size
    %kb = shape.get_extent %sb, %c0 : !shape.shape, index -> !shape.size
    %ia = shape.size_to_index %ka : !shape.size
    %ib = shape.size_to_index %kb : !shape.size
    %eq = arith.cmpi eq, %ia, %ib : index
    %w = shape.cstr_require %eq, "matmul: K dims must match"
    %r = shape.assuming %w -> (tensor<2x2xf32>) {
      %mm = linalg.matmul ins(%a, %b : tensor<2x3xf32>, tensor<3x2xf32>)
                          outs(%init : tensor<2x2xf32>) -> tensor<2x2xf32>
      shape.assuming_yield %mm : tensor<2x2xf32>
    }
    return %r : tensor<2x2xf32>
  }

  // ---- 房间 3：动态形状 → 约束留到运行期检查 ----
  func.func @dynamic_checked(%a: tensor<?x?xf32>, %b: tensor<?x?xf32>,
                              %init: tensor<?x?xf32>) -> tensor<?x?xf32> {
    %sa = shape.shape_of %a : tensor<?x?xf32> -> !shape.shape
    %sb = shape.shape_of %b : tensor<?x?xf32> -> !shape.shape
    %c1 = arith.constant 1 : index
    %c0 = arith.constant 0 : index
    %ka = shape.get_extent %sa, %c1 : !shape.shape, index -> !shape.size
    %kb = shape.get_extent %sb, %c0 : !shape.shape, index -> !shape.size
    %ia = shape.size_to_index %ka : !shape.size
    %ib = shape.size_to_index %kb : !shape.size
    %eq = arith.cmpi eq, %ia, %ib : index
    %w = shape.cstr_require %eq, "matmul: K dims must match"
    %r = shape.assuming %w -> (tensor<?x?xf32>) {
      %mm = linalg.matmul ins(%a, %b : tensor<?x?xf32>, tensor<?x?xf32>)
                          outs(%init : tensor<?x?xf32>) -> tensor<?x?xf32>
      shape.assuming_yield %mm : tensor<?x?xf32>
    }
    return %r : tensor<?x?xf32>
  }
}
