// 探针 4：链式 matmul —— 一趟 pre-order walk 传播到底。
//
//   %0 = matmul(%a: 2x?, %b: ?x3) -> ?x?     推出 2x3
//   %1 = matmul(%0: 已细化成 2x3, %c: 3x?) -> ?x?   推出 2x?
//
// 看点一：访问 %1 时读到的 lhs 类型已经是细化后的 2x3
//         （walk 按定义序，%0 先被访问、先被 setType）。
// 看点二：N 的来源（%c 的最后一维）仍是 ?，推导诚实地保留 ?，
//         输出 2x? 而不是发明一个数字。

func.func @chain_two_matmuls(%a: tensor<2x?xf32>, %b: tensor<?x3xf32>,
                             %c: tensor<3x?xf32>) {
  %0 = mini.matmul %a, %b : tensor<2x?xf32>, tensor<?x3xf32> -> tensor<?x?xf32>
  %1 = mini.matmul %0, %c : tensor<?x?xf32>, tensor<3x?xf32> -> tensor<?x?xf32>
  func.return
}
