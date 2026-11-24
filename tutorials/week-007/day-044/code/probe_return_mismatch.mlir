// 探针 7：常见错误的现场（预期失败，rc=1）。
//
// 把细化后的结果 return 出函数：签名写 tensor<?x?xf32>，
// 解析时 func.return 的操作数类型（?x?）和签名一致，完全合法。
// 但 Pass 把 %0 细化成 2x2 之后，操作数类型变了，
// 函数签名却不会自动跟着变 —— Pass 之后的重新验证
// （mlir-opt 默认 --verify-each）当场抓住这个不一致。
//
// 结论：Value::setType 更新的是"值"，所有使用者立刻看见；
// 函数签名是函数的属性，不在自动更新之列。今天的探针都让
// matmul 结果"就地观察、不外传"，绕开这个接缝。

func.func @returns_refined(%a: tensor<2x?xf32>, %b: tensor<?x2xf32>) -> tensor<?x?xf32> {
  %0 = mini.matmul %a, %b : tensor<2x?xf32>, tensor<?x2xf32> -> tensor<?x?xf32>
  func.return %0 : tensor<?x?xf32>
}
