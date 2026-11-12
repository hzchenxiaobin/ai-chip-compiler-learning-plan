// 探针 2：K 两侧都是 ?（2x? · ?x2）。
// Day 43 规则 R4：K 被乘法消费、不进输出 —— 结果 ?x? 应细化成 2x2。
// 这是"部分静态 shape"最反直觉的例子：输入两个 ?，输出反而全静态。

func.func @k_dynamic(%a: tensor<2x?xf32>, %b: tensor<?x2xf32>) {
  %0 = mini.matmul %a, %b : tensor<2x?xf32>, tensor<?x2xf32> -> tensor<?x?xf32>
  func.return
}
