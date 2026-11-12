// matmul_dyn.mlir —— 第 62 天：特化的输入（M 动态、K=3 / N=2 静态）。
//
// 数据（与第 61 天同一份，值肉眼可核对）：
//   A(2,3) = [[1, 2, 3], [4, 5, 6]]
//   B(3,2) = [[10, 20], [30, 40], [50, 60]]
//   C(2,2) = A×B = [[220, 280], [490, 640]]
//
// 这是 specialize.py 的标准输入：M 写成 ?（batch 维，取值由运行期决定），
// K / N 静态。特化入口要做的事：
//   --specialize-shape "a=2x3,b=3x2"
//   → 把 ? 换成 2；%o 的输出类型由 mini 推导器重推（M=2, N=2，K 对账 3==3）
//   → mlir-opt 重新验证（解析 + verify）
//   → 得到全静态产物 matmul_spec.mlir
//
// 运行方式：
//   mlir-opt matmul_dyn.mlir                                # 解析 + 验证（放行）
//   mlir-opt --convert-linalg-to-loops matmul_dyn.mlir      # M 的上界是 memref.dim
//   python3 specialize.py matmul_dyn.mlir --specialize-shape "a=2x3,b=3x2" \
//           -o matmul_spec.mlir                             # 特化 + 重新验证

module {
  func.func @matmul(%a: memref<16x3xf32>, %b: memref<3x2xf32>,
                    %o: memref<16x2xf32>) {
    linalg.matmul ins(%a, %b : memref<16x3xf32>, memref<3x2xf32>)
                  outs(%o : memref<16x2xf32>)
    return
  }
}
